"""Reply monitoring job - checks for new replies every hour."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.lead import Lead, LeadState
from app.models.email_thread import EmailThread, ReplySentiment
from app.services.gmail_service import gmail_service
from app.services.openai_service import openai_service
from app.services.state_machine import get_state_machine

logger = logging.getLogger(__name__)


async def check_all_replies():
    """
    Check all active email threads for new replies.
    
    This job runs every hour and:
    1. Gets all threads for leads in WAITING state
    2. Checks Gmail for new replies
    3. Classifies reply sentiment
    4. Updates lead state accordingly
    """
    logger.info("Starting reply monitoring job")
    
    if not gmail_service.is_authenticated():
        logger.warning("Gmail not authenticated, skipping reply check")
        return
    
    async with async_session_maker() as db:
        try:
            # Get leads in WAITING state
            waiting_leads_query = select(Lead).where(Lead.state == LeadState.WAITING)
            result = await db.execute(waiting_leads_query)
            waiting_leads = result.scalars().all()
            
            if not waiting_leads:
                logger.info("No leads in WAITING state")
                return
            
            logger.info(f"Checking {len(waiting_leads)} leads for replies")
            
            for lead in waiting_leads:
                await check_lead_replies(db, lead)
            
            logger.info("Reply monitoring job completed")
            
        except Exception as e:
            logger.error(f"Error in reply monitoring: {e}")


async def check_lead_replies(db: AsyncSession, lead: Lead):
    """
    Check a single lead's email threads for replies.
    """
    # Get threads for this lead
    threads_query = select(EmailThread).where(
        EmailThread.lead_id == lead.id,
        EmailThread.gmail_thread_id.isnot(None),
    )
    result = await db.execute(threads_query)
    threads = result.scalars().all()
    
    if not threads:
        return
    
    for thread in threads:
        if thread.has_reply:
            # Already processed this reply
            continue
        
        try:
            # Check Gmail for new messages
            gmail_result = await gmail_service.get_thread_messages(thread.gmail_thread_id)
            
            if not gmail_result.get("success"):
                continue
            
            messages = gmail_result.get("messages", [])
            
            # Find received messages (not sent by us)
            received_messages = [m for m in messages if not m.get("is_sent")]
            
            if not received_messages:
                continue
            
            # We have a reply!
            logger.info(f"Found reply for lead {lead.id}")
            
            # Get the latest reply
            latest_reply = received_messages[-1]
            reply_body = latest_reply.get("body", "")
            
            # Classify sentiment
            sentiment = await openai_service.classify_reply_sentiment(reply_body)
            
            # Update thread
            thread.has_reply = True
            thread.reply_sentiment = ReplySentiment[sentiment]
            thread.last_checked_at = datetime.utcnow()
            
            # Add received message to thread
            thread.add_message(
                role="received",
                content=reply_body,
                gmail_id=latest_reply.get("id"),
            )
            
            # Update lead state based on sentiment
            state_machine = get_state_machine(db)
            
            if sentiment == "POSITIVE":
                await state_machine.handle_positive_reply(lead)
                thread.requires_human = True
                logger.info(f"Lead {lead.id} marked as INTERESTED - human takeover")
                
            elif sentiment == "NEGATIVE":
                await state_machine.handle_negative_reply(lead)
                logger.info(f"Lead {lead.id} marked as NOT_INTERESTED")
                
                # Send polite follow-up asking why
                await send_polite_followup(db, lead, thread)
            
            # For NEUTRAL, keep waiting
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error checking thread {thread.id}: {e}")
            continue


async def send_polite_followup(db: AsyncSession, lead: Lead, thread: EmailThread):
    """
    Send a polite follow-up after a negative reply.
    """
    if not gmail_service.is_authenticated():
        return
    
    # Check rate limits
    can_send, _ = gmail_service.rate_limiter.can_send()
    if not can_send:
        logger.warning("Rate limit hit, skipping polite followup")
        return
    
    # Get original email
    original_email = ""
    if thread.messages_json:
        sent_messages = [m for m in thread.messages_json if m.get("role") == "sent"]
        if sent_messages:
            original_email = sent_messages[0].get("content", "")
    
    # Generate polite follow-up
    lead_data = {
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "company_name": lead.company_name,
    }
    
    followup = await openai_service.generate_polite_followup(
        lead_data,
        original_email,
        is_after_rejection=True,
    )
    
    # Send the follow-up
    send_result = await gmail_service.send_email(
        to_email=lead.email,
        subject=followup["subject"],
        body=followup["body"],
        thread_id=thread.gmail_thread_id,
    )
    
    if send_result.get("success"):
        # Add to thread
        thread.add_message(
            role="sent",
            content=followup["body"],
            gmail_id=send_result.get("message_id"),
        )
        
        # Update lead
        lead.emails_sent_count += 1
        lead.last_email_at = datetime.utcnow()
        
        # Close the lead after polite follow-up
        state_machine = get_state_machine(db)
        await state_machine.close_lead(lead, "Polite followup sent after rejection")
        
        await db.commit()
        logger.info(f"Sent polite followup to lead {lead.id}")
