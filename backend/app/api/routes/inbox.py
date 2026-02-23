"""Unified inbox routes for email management."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from app.api.deps import get_db
from app.models.lead import Lead
from app.models.email_thread import EmailThread, ReplySentiment
from app.schemas.email_thread import EmailThreadResponse, EmailMessageCreate
from app.services.gmail_service import gmail_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def list_threads(
    db: AsyncSession = Depends(get_db),
    requires_human: Optional[bool] = None,
    has_reply: Optional[bool] = None,
):
    """
    List all email threads.
    
    Args:
        requires_human: Filter threads needing human attention
        has_reply: Filter threads with/without replies
    """
    # Exclude draft threads (generated but not yet sent — no gmail_thread_id)
    query = select(EmailThread).join(Lead).where(EmailThread.gmail_thread_id.isnot(None))

    if requires_human is not None:
        query = query.where(EmailThread.requires_human == requires_human)

    if has_reply is not None:
        query = query.where(EmailThread.has_reply == has_reply)

    query = query.order_by(EmailThread.updated_at.desc())
    
    result = await db.execute(query)
    threads = result.scalars().all()
    
    # Enrich with lead info
    thread_responses = []
    for thread in threads:
        lead = await db.get(Lead, thread.lead_id)
        thread_responses.append({
            "id": thread.id,
            "lead_id": thread.lead_id,
            "lead_name": f"{lead.first_name} {lead.last_name}" if lead else "Unknown",
            "lead_email": lead.email if lead else None,
            "lead_company": lead.company_name if lead else None,
            "lead_state": lead.state.value if lead else None,
            "subject": thread.subject,
            "gmail_thread_id": thread.gmail_thread_id,
            "messages_count": len(thread.messages_json) if thread.messages_json else 0,
            "has_reply": thread.has_reply,
            "requires_human": thread.requires_human,
            "reply_sentiment": thread.reply_sentiment.value if thread.reply_sentiment else None,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
        })
    
    return {"threads": thread_responses, "total": len(thread_responses)}


@router.get("/{thread_id}")
async def get_thread(thread_id: int, db: AsyncSession = Depends(get_db)):
    """Get thread details with all messages."""
    thread = await db.get(EmailThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    lead = await db.get(Lead, thread.lead_id)
    
    # Try to get fresh messages from Gmail if authenticated
    messages = thread.messages_json or []
    if gmail_service.is_authenticated() and thread.gmail_thread_id:
        try:
            gmail_result = await gmail_service.get_thread_messages(thread.gmail_thread_id)
            if gmail_result.get("success"):
                # Update with Gmail messages
                gmail_messages = gmail_result.get("messages", [])
                # Merge with our tracked messages
                for gm in gmail_messages:
                    existing = next(
                        (m for m in messages if m.get("gmail_id") == gm.get("id")),
                        None
                    )
                    if not existing:
                        messages.append({
                            "role": "received" if not gm.get("is_sent") else "sent",
                            "content": gm.get("body", ""),
                            "timestamp": gm.get("date", ""),
                            "gmail_id": gm.get("id"),
                        })
                
                thread.messages_json = messages
                await db.commit()
        except Exception as e:
            logger.error(f"Error fetching Gmail messages: {e}")
    
    return {
        "id": thread.id,
        "lead_id": thread.lead_id,
        "lead_name": f"{lead.first_name} {lead.last_name}" if lead else "Unknown",
        "lead_email": lead.email if lead else None,
        "lead_company": lead.company_name if lead else None,
        "lead_job_title": lead.job_title if lead else None,
        "lead_state": lead.state.value if lead else None,
        "subject": thread.subject,
        "gmail_thread_id": thread.gmail_thread_id,
        "messages": messages,
        "has_reply": thread.has_reply,
        "requires_human": thread.requires_human,
        "reply_sentiment": thread.reply_sentiment.value if thread.reply_sentiment else None,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }


@router.post("/{thread_id}/reply")
async def reply_to_thread(
    thread_id: int,
    message: EmailMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a manual reply to a thread.
    
    This is for human takeover situations.
    """
    thread = await db.get(EmailThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    lead = await db.get(Lead, thread.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check Gmail authentication
    if not gmail_service.is_authenticated():
        raise HTTPException(status_code=400, detail="Gmail not authenticated")
    
    # Send reply
    send_result = await gmail_service.send_email(
        to_email=lead.email,
        subject=f"Re: {thread.subject}",
        body=message.content,
        thread_id=thread.gmail_thread_id,
    )
    
    if not send_result["success"]:
        raise HTTPException(status_code=500, detail=send_result["error"])
    
    # Add message to thread
    thread.add_message(
        role="sent",
        content=message.content,
        gmail_id=send_result.get("message_id"),
    )
    thread.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Reply sent",
        "message_id": send_result.get("message_id"),
    }


@router.get("/summary/stats")
async def inbox_stats(db: AsyncSession = Depends(get_db)):
    """Get inbox statistics."""
    # Total threads
    total_result = await db.execute(select(func.count(EmailThread.id)))
    total = total_result.scalar()
    
    # Threads with replies
    replies_result = await db.execute(
        select(func.count(EmailThread.id)).where(EmailThread.has_reply == True)
    )
    with_replies = replies_result.scalar()
    
    # Threads requiring human
    human_result = await db.execute(
        select(func.count(EmailThread.id)).where(EmailThread.requires_human == True)
    )
    requires_human = human_result.scalar()
    
    # By sentiment
    sentiment_counts = {}
    for sentiment in ReplySentiment:
        result = await db.execute(
            select(func.count(EmailThread.id))
            .where(EmailThread.reply_sentiment == sentiment)
        )
        sentiment_counts[sentiment.value] = result.scalar()
    
    return {
        "total_threads": total,
        "with_replies": with_replies,
        "requires_human": requires_human,
        "sentiment_breakdown": sentiment_counts,
    }
    