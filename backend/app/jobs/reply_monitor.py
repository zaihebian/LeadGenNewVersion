"""Reply monitoring job - checks for new replies every hour."""

import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.lead import Lead, LeadState
from app.models.email_thread import EmailThread, ReplySentiment
from app.services.gmail_service import gmail_service
from app.services.openai_service import openai_service
from app.services.state_machine import get_state_machine

logger = logging.getLogger(__name__)


def extract_email_from_header(header_value: str) -> Optional[str]:
    """
    Extract email address from email header (e.g., "Name <email@example.com>" or "email@example.com").
    
    Returns:
        Email address if found, None otherwise
    """
    if not header_value:
        return None
    
    # Try to extract email from format "Name <email@example.com>"
    match = re.search(r'<([^>]+)>', header_value)
    if match:
        return match.group(1).strip().lower()
    
    # Try to extract email directly
    match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', header_value)
    if match:
        return match.group(1).strip().lower()
    
    return None


async def check_all_replies():
    """
    Check all active email threads for new replies.
    
    This job runs every hour and:
    1. Gets all threads for leads in EMAILED_1 or EMAILED_2 state
    2. Checks Gmail for new replies
    3. Classifies reply sentiment
    4. Updates lead state accordingly
    """
    logger.info("=" * 60)
    logger.info("Starting reply monitoring job")
    
    if not gmail_service.is_authenticated():
        logger.warning("Gmail not authenticated, skipping reply check")
        return
    
    async with async_session_maker() as db:
        try:
            # Get leads in EMAILED_1 or EMAILED_2 state (waiting for replies)
            waiting_leads_query = select(Lead).where(
                Lead.state.in_([LeadState.EMAILED_1, LeadState.EMAILED_2])
            )
            result = await db.execute(waiting_leads_query)
            waiting_leads = result.scalars().all()
            
            if not waiting_leads:
                logger.info("No leads waiting for replies - job completed")
                return
            
            logger.info(f"Found {len(waiting_leads)} leads waiting for replies to check")
            
            replies_found = 0
            for lead in waiting_leads:
                found_reply = await check_lead_replies(db, lead)
                if found_reply:
                    replies_found += 1
            
            logger.info(
                f"Reply monitoring job completed: checked {len(waiting_leads)} leads, "
                f"found {replies_found} replies"
            )
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error in reply monitoring: {e}", exc_info=True)


async def check_lead_replies(db: AsyncSession, lead: Lead) -> bool:
    """
    Check a single lead's email threads for replies.
    
    Returns:
        True if a reply was found and processed, False otherwise
    """
    logger.info(f"Checking lead {lead.id} ({lead.email}) for replies")
    
    # Get threads for this lead
    threads_query = select(EmailThread).where(
        EmailThread.lead_id == lead.id,
        EmailThread.gmail_thread_id.isnot(None),
    )
    result = await db.execute(threads_query)
    threads = result.scalars().all()
    
    if not threads:
        logger.debug(f"Lead {lead.id} has no email threads")
        return False
    
    logger.info(f"Lead {lead.id} has {len(threads)} thread(s) to check")
    
    # Get authenticated user's email for comparison
    user_email = await gmail_service.get_authenticated_user_email()
    if not user_email:
        logger.warning(f"Cannot get user email for lead {lead.id}, skipping reply check")
        return False
    
    logger.debug(f"Authenticated user email: {user_email}")
    logger.debug(f"Lead email: {lead.email}")
    
    reply_found = False
    
    for thread in threads:
        if thread.has_reply:
            logger.debug(
                f"Thread {thread.id} for lead {lead.id} already has reply, skipping"
            )
            continue
        
        try:
            logger.info(
                f"Checking thread {thread.id} (Gmail thread: {thread.gmail_thread_id}) "
                f"for lead {lead.id}"
            )
            
            # Check Gmail for new messages
            gmail_result = await gmail_service.get_thread_messages(thread.gmail_thread_id)
            
            if not gmail_result.get("success"):
                logger.warning(
                    f"Failed to get thread messages for thread {thread.id}: "
                    f"{gmail_result.get('error')}"
                )
                continue
            
            messages = gmail_result.get("messages", [])
            logger.debug(f"Thread {thread.id} has {len(messages)} message(s)")
            
            # Find received messages by comparing From email addresses
            received_messages = []
            lead_email_lower = lead.email.lower() if lead.email else ""
            user_email_lower = user_email.lower()
            
            for msg in messages:
                from_header = msg.get("from", "")
                from_email = extract_email_from_header(from_header)
                is_sent_flag = msg.get("is_sent", False)
                
                logger.debug(
                    f"Message {msg.get('id')}: From='{from_header}' "
                    f"(extracted: {from_email}), is_sent={is_sent_flag}"
                )
                
                # Check if this is a reply from the lead
                # It's a reply if:
                # 1. From email matches lead's email, AND
                # 2. From email does NOT match user's email
                if from_email and from_email == lead_email_lower:
                    if from_email != user_email_lower:
                        logger.info(
                            f"Found reply from lead! Message {msg.get('id')}: "
                            f"From={from_email} matches lead email"
                        )
                        received_messages.append(msg)
                    else:
                        logger.debug(
                            f"Message {msg.get('id')} is from user ({from_email}), "
                            f"not a reply"
                        )
                elif not is_sent_flag:
                    # Fallback: if is_sent is False and From doesn't match user, it's likely a reply
                    if from_email and from_email != user_email_lower:
                        logger.info(
                            f"Found potential reply! Message {msg.get('id')}: "
                            f"From={from_email}, is_sent=False"
                        )
                        received_messages.append(msg)
            
            if not received_messages:
                logger.debug(f"No replies found in thread {thread.id}")
                continue
            
            # We have a reply!
            logger.info(
                f"✓ Found {len(received_messages)} reply/replies for lead {lead.id} "
                f"in thread {thread.id}"
            )
            reply_found = True
            
            # Get the latest reply
            latest_reply = received_messages[-1]
            reply_body = latest_reply.get("body", "")
            reply_from = latest_reply.get("from", "")
            
            logger.info(
                f"Processing latest reply from {reply_from} "
                f"(message ID: {latest_reply.get('id')})"
            )
            
            # Classify sentiment
            logger.info(f"Classifying reply sentiment for lead {lead.id}")
            sentiment = await openai_service.classify_reply_sentiment(reply_body)
            logger.info(f"Reply sentiment for lead {lead.id}: {sentiment}")
            
            # Update thread flags
            logger.info(
                f"Updating thread {thread.id}: has_reply=True, "
                f"reply_sentiment={sentiment}"
            )
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
            
            # Only process replies for EMAILED_1 leads (EMAILED_2 replies are handled by closing)
            if lead.state == LeadState.EMAILED_1:
                if sentiment == "POSITIVE":
                    logger.info(
                        f"Lead {lead.id} received POSITIVE reply - transitioning to INTERESTED"
                    )
                    await state_machine.handle_positive_reply(lead)
                    thread.requires_human = True
                    logger.info(
                        f"✓ Lead {lead.id} marked as INTERESTED - human takeover required. "
                        f"Thread {thread.id} requires_human=True"
                    )
                    
                elif sentiment == "NEGATIVE":
                    logger.info(
                        f"Lead {lead.id} received NEGATIVE reply - transitioning to NOT_INTERESTED"
                    )
                    await state_machine.handle_negative_reply(lead)
                    logger.info(f"✓ Lead {lead.id} marked as NOT_INTERESTED")
                    
                    # Send polite follow-up asking why
                    await send_polite_followup(db, lead, thread)
                
                elif sentiment == "NEUTRAL":
                    logger.info(
                        f"Lead {lead.id} received NEUTRAL reply - keeping in {lead.state.value} state"
                    )
            elif lead.state == LeadState.EMAILED_2:
                # Replies to follow-up emails - mark thread for human review and close lead
                logger.info(
                    f"Lead {lead.id} in EMAILED_2 received {sentiment} reply - marking for review"
                )
                thread.requires_human = True
                if sentiment == "POSITIVE":
                    thread.reply_sentiment = ReplySentiment.POSITIVE
                    await state_machine.close_lead(lead, "Reply received after follow-up")
                elif sentiment == "NEGATIVE":
                    thread.reply_sentiment = ReplySentiment.NEGATIVE
                    await state_machine.close_lead(lead, "Negative reply after follow-up")
                else:
                    thread.reply_sentiment = ReplySentiment.NEUTRAL
                    await state_machine.close_lead(lead, "Neutral reply after follow-up")
            
            # Commit changes
            await db.commit()
            logger.info(f"✓ Successfully processed reply for lead {lead.id}")
            
        except Exception as e:
            logger.error(
                f"Error checking thread {thread.id} for lead {lead.id}: {e}",
                exc_info=True
            )
            continue
    
    return reply_found


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
