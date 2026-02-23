"""Automatic email sender job - sends emails to ENRICHED leads."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.lead import Lead, LeadState
from app.models.email_thread import EmailThread
from app.models.campaign import Campaign
from app.services.gmail_service import gmail_service
from app.services.openai_service import openai_service
from app.services.state_machine import get_state_machine
from app.services.company_context import get_company_context

logger = logging.getLogger(__name__)


async def send_initial_emails():
    """
    Automatically send emails to leads in ENRICHED state.
    
    This job runs periodically and:
    1. Finds leads in ENRICHED state with emails_sent_count == 0
    2. Generates personalized emails using OpenAI
    3. Sends emails via Gmail with rate limiting
    4. Creates email thread records
    5. Transitions leads: ENRICHED -> EMAILED_1
    """
    logger.info("Starting automatic email sender job")
    
    if not gmail_service.is_authenticated():
        logger.warning("Gmail not authenticated, skipping email sending")
        return
    
    async with async_session_maker() as db:
        try:
            # Get leads in ENRICHED state that haven't been emailed yet
            query = select(Lead).where(
                Lead.state == LeadState.ENRICHED,
                Lead.emails_sent_count == 0,
            )
            
            result = await db.execute(query)
            enriched_leads = result.scalars().all()
            
            if not enriched_leads:
                logger.info("No ENRICHED leads to email")
                return
            
            logger.info(f"Found {len(enriched_leads)} ENRICHED leads to email")
            
            sent_count = 0
            skipped_count = 0
            
            for lead in enriched_leads:
                # Check rate limits before processing
                can_send, reason = gmail_service.rate_limiter.can_send()
                if not can_send:
                    logger.warning(f"Rate limit reached: {reason}. Skipping remaining leads.")
                    skipped_count = len(enriched_leads) - sent_count
                    break
                
                success = await send_email_to_lead(db, lead)
                if success:
                    sent_count += 1
                else:
                    skipped_count += 1
            
            logger.info(
                f"Email sender job completed: {sent_count} sent, {skipped_count} skipped"
            )
            
        except Exception as e:
            logger.error(f"Error in automatic email sender: {e}", exc_info=True)


async def send_email_to_lead(db: AsyncSession, lead: Lead) -> bool:
    """
    Send an email to a specific lead.
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    try:
        # Check if we can send email (state machine validation)
        state_machine = get_state_machine(db)
        can_send, reason = state_machine.can_send_email(lead)
        
        if not can_send:
            logger.warning(f"Cannot send email to lead {lead.id}: {reason}")
            return False
        
        # Check rate limits
        rate_can_send, rate_reason = gmail_service.rate_limiter.can_send()
        if not rate_can_send:
            logger.warning(f"Rate limit for lead {lead.id}: {rate_reason}")
            return False
        
        # Prepare lead data for email generation
        lead_data = {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "email": lead.email,
            "job_title": lead.job_title,
            "company_name": lead.company_name,
            "industry": lead.industry,
        }
        
        # Get LinkedIn posts for personalization
        linkedin_posts = None
        if lead.linkedin_posts_json:
            linkedin_posts = lead.linkedin_posts_json.get("posts", [])
        
        # Generate email
        logger.info(f"Generating email for lead {lead.id} ({lead.email})")
        email_content = await openai_service.generate_outreach_email(
            lead_data,
            linkedin_posts,
            prompt_variant=lead.emails_sent_count,
            company_context=get_company_context(),
        )
        
        # Send email
        send_result = await gmail_service.send_email(
            to_email=lead.email,
            subject=email_content["subject"],
            body=email_content["body"],
        )
        
        if not send_result.get("success"):
            logger.error(
                f"Failed to send email to lead {lead.id}: {send_result.get('error')}"
            )
            return False
        
        # Create email thread record
        thread = EmailThread(
            lead_id=lead.id,
            gmail_thread_id=send_result.get("thread_id"),
            gmail_message_id=send_result.get("message_id"),
            subject=email_content["subject"],
            messages_json=[{
                "role": "sent",
                "content": email_content["body"],
                "timestamp": datetime.utcnow().isoformat(),
                "gmail_id": send_result.get("message_id"),
            }],
        )
        db.add(thread)
        
        # Update lead state using state machine
        await state_machine.process_enriched(lead)
        
        # Update campaign metrics
        campaign = await db.get(Campaign, lead.campaign_id)
        if campaign:
            campaign.leads_emailed += 1
        
        await db.commit()
        
        logger.info(
            f"Successfully sent email to lead {lead.id} ({lead.email}), "
            f"thread_id: {send_result.get('thread_id')}"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending email to lead {lead.id}: {e}", exc_info=True)
        return False
