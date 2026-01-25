"""Lead management routes."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from app.api.deps import get_db
from app.models.lead import Lead, LeadState
from app.models.email_thread import EmailThread
from app.models.campaign import Campaign
from app.schemas.lead import LeadResponse, LeadListResponse
from app.services.state_machine import get_state_machine
from app.services.openai_service import openai_service
from app.services.gmail_service import gmail_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=LeadListResponse)
async def list_leads(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    state: Optional[LeadState] = None,
    campaign_id: Optional[int] = None,
):
    """
    List leads with pagination and filtering.
    
    Args:
        page: Page number (1-indexed)
        per_page: Items per page
        state: Filter by lead state
        campaign_id: Filter by campaign
    """
    # Build query
    query = select(Lead)
    count_query = select(func.count(Lead.id))
    
    if state:
        query = query.where(Lead.state == state)
        count_query = count_query.where(Lead.state == state)
    
    if campaign_id:
        query = query.where(Lead.campaign_id == campaign_id)
        count_query = count_query.where(Lead.campaign_id == campaign_id)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * per_page
    query = query.order_by(Lead.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    leads = result.scalars().all()
    
    return LeadListResponse(
        leads=[LeadResponse.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{lead_id}")
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Get lead details including status summary."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    state_machine = get_state_machine(db)
    status_summary = state_machine.get_lead_status_summary(lead)
    
    # Get email threads
    threads_query = select(EmailThread).where(EmailThread.lead_id == lead_id)
    threads_result = await db.execute(threads_query)
    threads = threads_result.scalars().all()
    
    return {
        "lead": LeadResponse.model_validate(lead),
        "status": status_summary,
        "email_threads": [
            {
                "id": t.id,
                "subject": t.subject,
                "messages_count": len(t.messages_json) if t.messages_json else 0,
                "has_reply": t.has_reply,
                "requires_human": t.requires_human,
                "reply_sentiment": t.reply_sentiment.value if t.reply_sentiment else None,
            }
            for t in threads
        ],
    }


@router.post("/{lead_id}/send-email")
async def send_email_to_lead(
    lead_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Send an email to a lead.
    
    This generates a personalized email and sends it via Gmail.
    """
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check if we can send email
    state_machine = get_state_machine(db)
    can_send, reason = state_machine.can_send_email(lead)
    
    if not can_send:
        raise HTTPException(status_code=400, detail=reason)
    
    # Check Gmail authentication
    if not gmail_service.is_authenticated():
        raise HTTPException(status_code=400, detail="Gmail not authenticated")
    
    # Check rate limits
    rate_can_send, rate_reason = gmail_service.rate_limiter.can_send()
    if not rate_can_send:
        raise HTTPException(status_code=429, detail=rate_reason)
    
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
    email_content = await openai_service.generate_outreach_email(
        lead_data,
        linkedin_posts,
        prompt_variant=lead.emails_sent_count,  # Different variant for follow-ups
    )
    
    # Send email
    send_result = await gmail_service.send_email(
        to_email=lead.email,
        subject=email_content["subject"],
        body=email_content["body"],
    )
    
    if not send_result["success"]:
        raise HTTPException(status_code=500, detail=send_result["error"])
    
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
    
    # Update lead state
    if lead.state == LeadState.ENRICHED:
        await state_machine.process_enriched(lead)
        await state_machine.start_waiting(lead)
    elif lead.state == LeadState.WAITING:
        # This is a follow-up
        await state_machine.handle_no_reply(lead)
    
    # Update campaign metrics
    campaign = await db.get(Campaign, lead.campaign_id)
    if campaign:
        campaign.leads_emailed += 1
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Email sent to {lead.email}",
        "thread_id": send_result.get("thread_id"),
        "subject": email_content["subject"],
    }


@router.get("/states/summary")
async def get_states_summary(db: AsyncSession = Depends(get_db)):
    """Get summary of leads by state."""
    result = await db.execute(
        select(Lead.state, func.count(Lead.id))
        .group_by(Lead.state)
    )
    
    state_counts = {state.value: 0 for state in LeadState}
    for state, count in result.all():
        state_counts[state.value] = count
    
    return {"states": state_counts}
