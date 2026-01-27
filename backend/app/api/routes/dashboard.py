"""Dashboard routes for metrics and statistics."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db
from app.models.lead import Lead, LeadState
from app.models.campaign import Campaign
from app.models.email_thread import EmailThread
from app.schemas.dashboard import DashboardStats

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """
    Get dashboard statistics.
    
    Returns metrics on leads, replies, and campaign performance.
    """
    # Total leads
    total_leads_result = await db.execute(select(func.count(Lead.id)))
    total_leads = total_leads_result.scalar() or 0
    
    # Leads contacted (EMAILED_1 or beyond)
    contacted_states = [
        LeadState.EMAILED_1,
        LeadState.INTERESTED,
        LeadState.NOT_INTERESTED,
        LeadState.EMAILED_2,
        LeadState.CLOSED,
    ]
    contacted_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.state.in_(contacted_states))
    )
    leads_contacted = contacted_result.scalar() or 0
    
    # Replies received (leads with email threads that have replies)
    replies_result = await db.execute(
        select(func.count(func.distinct(EmailThread.lead_id)))
        .where(EmailThread.has_reply == True)
    )
    replies_received = replies_result.scalar() or 0
    
    # Interested leads
    interested_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.state == LeadState.INTERESTED)
    )
    interested_leads = interested_result.scalar() or 0
    
    # Not interested leads
    not_interested_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.state == LeadState.NOT_INTERESTED)
    )
    not_interested_leads = not_interested_result.scalar() or 0
    
    # Closed leads
    closed_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.state == LeadState.CLOSED)
    )
    closed_leads = closed_result.scalar() or 0
    
    # Awaiting reply (EMAILED_1 or EMAILED_2 state)
    awaiting_result = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.state.in_([LeadState.EMAILED_1, LeadState.EMAILED_2])
        )
    )
    awaiting_reply = awaiting_result.scalar() or 0
    
    # Total campaigns
    campaigns_result = await db.execute(select(func.count(Campaign.id)))
    total_campaigns = campaigns_result.scalar() or 0
    
    return DashboardStats(
        leads_contacted=leads_contacted,
        replies_received=replies_received,
        interested_leads=interested_leads,
        not_interested_leads=not_interested_leads,
        closed_leads=closed_leads,
        awaiting_reply=awaiting_reply,
        total_leads=total_leads,
        total_campaigns=total_campaigns,
    )


@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_db)):
    """
    Get detailed overview with breakdown by state.
    """
    # Get counts per state
    state_counts = {}
    for state in LeadState:
        result = await db.execute(
            select(func.count(Lead.id)).where(Lead.state == state)
        )
        state_counts[state.value] = result.scalar() or 0
    
    # Get recent campaigns
    recent_campaigns_result = await db.execute(
        select(Campaign)
        .order_by(Campaign.created_at.desc())
        .limit(5)
    )
    recent_campaigns = recent_campaigns_result.scalars().all()
    
    # Get leads requiring attention
    attention_result = await db.execute(
        select(Lead)
        .where(Lead.state == LeadState.INTERESTED)
        .order_by(Lead.updated_at.desc())
        .limit(10)
    )
    attention_leads = attention_result.scalars().all()
    
    return {
        "state_breakdown": state_counts,
        "recent_campaigns": [
            {
                "id": c.id,
                "keywords": c.keywords,
                "status": c.status.value,
                "leads_valid": c.leads_valid,
                "created_at": c.created_at.isoformat(),
            }
            for c in recent_campaigns
        ],
        "leads_requiring_attention": [
            {
                "id": l.id,
                "name": f"{l.first_name} {l.last_name}",
                "email": l.email,
                "company": l.company_name,
                "updated_at": l.updated_at.isoformat(),
            }
            for l in attention_leads
        ],
    }
