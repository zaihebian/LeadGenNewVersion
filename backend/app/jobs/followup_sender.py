"""Follow-up sender job - sends follow-ups to leads with no reply after 14 days."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.config import get_settings
from app.models.lead import Lead, LeadState
from app.models.email_thread import EmailThread
from app.services.gmail_service import gmail_service
from app.services.openai_service import openai_service
from app.services.state_machine import get_state_machine

logger = logging.getLogger(__name__)


async def send_followups():
    """
    Check for leads that need follow-up after 14 days of no reply.
    
    This job runs periodically and:
    1. Finds leads in EMAILED_1 state
    2. Checks if 14 days have passed since last email
    3. Sends a follow-up email
    4. Transitions lead to EMAILED_2
    """
    logger.info("Starting follow-up sender job")
    
    if not gmail_service.is_authenticated():
        logger.warning("Gmail not authenticated, skipping follow-ups")
        return
    
    settings = get_settings()
    followup_days = settings.no_reply_followup_days
    
    async with async_session_maker() as db:
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=followup_days)
            
            # Get leads in EMAILED_1 state with last email before cutoff
            query = select(Lead).where(
                Lead.state == LeadState.EMAILED_1,
                Lead.last_email_at.isnot(None),
                Lead.last_email_at < cutoff_date,
                Lead.emails_sent_count < 2,  # Haven't sent follow-up yet
            )
            
            result = await db.execute(query)
            leads_needing_followup = result.scalars().all()
            
            if not leads_needing_followup:
                logger.info("No leads need follow-up")
                return
            
            logger.info(f"Found {len(leads_needing_followup)} leads needing follow-up")
            
            for lead in leads_needing_followup:
                await send_lead_followup(db, lead)
            
            logger.info("Follow-up sender job completed")
            
        except Exception as e:
            logger.error(f"Error in follow-up sender: {e}")


async def send_lead_followup(db: AsyncSession, lead: Lead):
    """
    Send a follow-up email to a specific lead.
    """
    # Check rate limits
    can_send, reason = gmail_service.rate_limiter.can_send()
    if not can_send:
        logger.warning(f"Rate limit: {reason}, skipping lead {lead.id}")
        return
    
    try:
        # Get the original email thread
        threads_query = select(EmailThread).where(
            EmailThread.lead_id == lead.id
        ).order_by(EmailThread.created_at.desc())
        
        result = await db.execute(threads_query)
        thread = result.scalars().first()
        
        if not thread:
            logger.warning(f"No email thread found for lead {lead.id}")
            return
        
        # Get original email content
        original_email = ""
        if thread.messages_json:
            sent_messages = [m for m in thread.messages_json if m.get("role") == "sent"]
            if sent_messages:
                original_email = sent_messages[0].get("content", "")
        
        # Generate follow-up email
        lead_data = {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "company_name": lead.company_name,
            "job_title": lead.job_title,
        }
        
        followup = await openai_service.generate_polite_followup(
            lead_data,
            original_email,
            is_after_rejection=False,  # This is a no-reply follow-up
        )
        
        # Send the email
        send_result = await gmail_service.send_email(
            to_email=lead.email,
            subject=followup["subject"],
            body=followup["body"],
            thread_id=thread.gmail_thread_id,
        )
        
        if not send_result.get("success"):
            logger.error(f"Failed to send follow-up to lead {lead.id}: {send_result.get('error')}")
            return
        
        # Add message to thread
        thread.add_message(
            role="sent",
            content=followup["body"],
            gmail_id=send_result.get("message_id"),
        )
        
        # Update lead state
        state_machine = get_state_machine(db)
        await state_machine.handle_no_reply(lead)
        
        await db.commit()
        logger.info(f"Sent follow-up to lead {lead.id}")
        
    except Exception as e:
        logger.error(f"Error sending follow-up to lead {lead.id}: {e}")


async def close_stale_leads():
    """
    Close leads that have been in EMAILED_2 state for too long.
    
    This is a cleanup job that can be run less frequently.
    """
    async with async_session_maker() as db:
        try:
            # Get leads in EMAILED_2 state for more than 14 days
            cutoff_date = datetime.utcnow() - timedelta(days=14)
            
            query = select(Lead).where(
                Lead.state == LeadState.EMAILED_2,
                Lead.updated_at < cutoff_date,
            )
            
            result = await db.execute(query)
            stale_leads = result.scalars().all()
            
            state_machine = get_state_machine(db)
            
            for lead in stale_leads:
                await state_machine.close_lead(lead, "No response after final follow-up")
            
            await db.commit()
            
            if stale_leads:
                logger.info(f"Closed {len(stale_leads)} stale leads")
                
        except Exception as e:
            logger.error(f"Error closing stale leads: {e}")
