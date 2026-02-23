"""Lead management routes."""

import csv
import io
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
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
from app.services.company_context import get_company_context

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/export/csv")
async def export_leads_csv(
    db: AsyncSession = Depends(get_db),
    state: Optional[LeadState] = None,
    campaign_id: Optional[int] = None,
):
    """
    Download all leads with enriched post data as CSV.
    Respects state and campaign_id filters when provided.
    Includes first_message_subject and first_message_body columns when an
    email has been sent to the lead.
    """
    query = select(Lead).order_by(Lead.created_at.desc())
    if state:
        query = query.where(Lead.state == state)
    if campaign_id is not None:
        query = query.where(Lead.campaign_id == campaign_id)
    result = await db.execute(query)
    leads = result.scalars().all()

    # Fetch the earliest EmailThread per lead (ordered by id asc so first thread wins)
    lead_ids = [l.id for l in leads]
    thread_by_lead: dict[int, EmailThread] = {}
    if lead_ids:
        threads_result = await db.execute(
            select(EmailThread)
            .where(EmailThread.lead_id.in_(lead_ids))
            .order_by(EmailThread.id.asc())
        )
        for thread in threads_result.scalars().all():
            if thread.lead_id not in thread_by_lead:
                thread_by_lead[thread.lead_id] = thread

    max_posts = 5
    lead_headers = [
        "id", "campaign_id", "state", "first_name", "last_name", "full_name", "email",
        "linkedin_url", "job_title", "company_name", "industry", "created_at",
        "first_message_subject", "first_message_body",
    ]
    post_headers = []
    for i in range(1, max_posts + 1):
        post_headers.extend([f"post_{i}_text", f"post_{i}_date", f"post_{i}_url"])
    headers = lead_headers + post_headers

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for lead in leads:
        row = [
            lead.id, lead.campaign_id, lead.state.value if lead.state else "",
            lead.first_name or "", lead.last_name or "", lead.full_name or "",
            lead.email or "", lead.linkedin_url or "", lead.job_title or "",
            lead.company_name or "", lead.industry or "",
            lead.created_at.isoformat() if lead.created_at else "",
        ]

        # First message subject and body
        thread = thread_by_lead.get(lead.id)
        first_subject = ""
        first_body = ""
        if thread:
            first_subject = thread.subject or ""
            sent_msgs = [m for m in (thread.messages_json or []) if m.get("role") == "sent"]
            if sent_msgs:
                first_body = (
                    sent_msgs[0].get("content", "")
                    .replace("\n", " ")
                    .replace("\r", " ")
                )
        row.extend([first_subject, first_body])

        posts = []
        if lead.linkedin_posts_json and isinstance(lead.linkedin_posts_json.get("posts"), list):
            posts = lead.linkedin_posts_json["posts"]
        for i in range(max_posts):
            if i < len(posts):
                p = posts[i]
                text = (p.get("text") or "").replace("\n", " ").replace("\r", " ")[:5000]
                row.append(text)
                row.append(p.get("posted_at") or "")
                row.append(p.get("url") or "")
            else:
                row.extend(["", "", ""])
        writer.writerow(row)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_enriched.csv"},
    )


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
    Send an email to a lead (TEST ONLY - Manual trigger).
    
    NOTE: In production, emails are automatically sent by the email_sender job
    for leads in ENRICHED state. This endpoint is for testing purposes only.
    
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
        prompt_variant=lead.emails_sent_count,
        company_context=get_company_context(),
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
    elif lead.state == LeadState.EMAILED_1:
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


@router.post("/{lead_id}/generate-first-message")
async def generate_first_message(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Generate (and persist as a draft) the first outreach message for a lead.

    Available whether or not Gmail is connected. If Gmail is not connected this
    is the primary way to preview message quality and populate first_message_*
    in the CSV export. If Gmail is connected users can still call this to
    preview before the auto-sender fires.

    Calling this multiple times for the same lead overwrites the existing draft.
    """
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.state not in (LeadState.ENRICHED, LeadState.COLLECTED):
        raise HTTPException(
            status_code=400,
            detail=f"Lead must be in ENRICHED state to generate a message (current: {lead.state.value})",
        )

    lead_data = {
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "email": lead.email,
        "job_title": lead.job_title,
        "company_name": lead.company_name,
        "industry": lead.industry,
    }

    linkedin_posts = None
    if lead.linkedin_posts_json:
        linkedin_posts = lead.linkedin_posts_json.get("posts", [])

    email_content = await openai_service.generate_outreach_email(
        lead_data,
        linkedin_posts,
        prompt_variant=0,
        company_context=get_company_context(),
    )

    # Upsert: overwrite existing draft (no gmail_thread_id) or create new one
    existing_result = await db.execute(
        select(EmailThread).where(
            EmailThread.lead_id == lead_id,
            EmailThread.gmail_thread_id.is_(None),
        )
    )
    draft = existing_result.scalars().first()
    now = datetime.utcnow().isoformat()

    if draft:
        draft.subject = email_content["subject"]
        draft.messages_json = [{"role": "sent", "content": email_content["body"], "timestamp": now}]
        draft.updated_at = datetime.utcnow()
    else:
        draft = EmailThread(
            lead_id=lead_id,
            subject=email_content["subject"],
            messages_json=[{"role": "sent", "content": email_content["body"], "timestamp": now}],
        )
        db.add(draft)

    await db.commit()

    return {
        "subject": email_content["subject"],
        "body": email_content["body"],
    }


@router.post("/generate-all-first-messages")
async def generate_all_first_messages(db: AsyncSession = Depends(get_db)):
    """
    Generate first outreach messages for all ENRICHED leads that have not been
    emailed yet and do not already have a draft thread.

    Saves a draft EmailThread (gmail_thread_id = None) per lead so that
    first_message_subject / first_message_body are populated in CSV export
    even when Gmail is not connected.
    """
    query = select(Lead).where(
        Lead.state == LeadState.ENRICHED,
        Lead.emails_sent_count == 0,
    )
    result = await db.execute(query)
    enriched_leads = result.scalars().all()

    if not enriched_leads:
        return {"generated": 0, "skipped": 0, "message": "No ENRICHED leads without emails found"}

    lead_ids = [l.id for l in enriched_leads]
    existing_drafts_result = await db.execute(
        select(EmailThread.lead_id).where(
            EmailThread.lead_id.in_(lead_ids),
            EmailThread.gmail_thread_id.is_(None),
        )
    )
    leads_with_drafts = {row[0] for row in existing_drafts_result.all()}

    generated = 0
    skipped = 0

    for lead in enriched_leads:
        if lead.id in leads_with_drafts:
            skipped += 1
            continue

        try:
            lead_data = {
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "job_title": lead.job_title,
                "company_name": lead.company_name,
                "industry": lead.industry,
            }
            linkedin_posts = None
            if lead.linkedin_posts_json:
                linkedin_posts = lead.linkedin_posts_json.get("posts", [])

            email_content = await openai_service.generate_outreach_email(
                lead_data,
                linkedin_posts,
                prompt_variant=0,
                company_context=get_company_context(),
            )

            draft = EmailThread(
                lead_id=lead.id,
                subject=email_content["subject"],
                messages_json=[{
                    "role": "sent",
                    "content": email_content["body"],
                    "timestamp": datetime.utcnow().isoformat(),
                }],
            )
            db.add(draft)
            await db.commit()
            generated += 1

        except Exception as e:
            logger.error(f"Error generating message for lead {lead.id}: {e}", exc_info=True)
            skipped += 1

    return {
        "generated": generated,
        "skipped": skipped,
        "message": f"Generated {generated} messages, skipped {skipped}",
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
