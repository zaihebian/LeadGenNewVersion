"""Search routes for initiating lead collection."""

import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.schemas.lead import LeadCreate
from app.models.campaign import Campaign, CampaignStatus
from app.models.lead import Lead, LeadState
from app.services.openai_service import openai_service
from app.services.apify_leads import apify_leads_service
from app.services.apify_linkedin import apify_linkedin_service
from app.services.state_machine import get_state_machine

logger = logging.getLogger(__name__)

router = APIRouter()


async def collect_and_enrich_leads(campaign_id: int, keywords: str):
    """
    Background task to collect leads from Apify and enrich them.
    
    This runs after the API returns to avoid timeout.
    """
    from app.database import async_session_maker
    
    async with async_session_maker() as db:
        try:
            # Get campaign
            campaign = await db.get(Campaign, campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return
            
            campaign.status = CampaignStatus.COLLECTING
            await db.commit()
            
            # Generate Apify query from keywords using OpenAI
            query_params = await openai_service.generate_apify_query(keywords)
            campaign.apify_query_json = query_params.model_dump_json()
            await db.commit()
            
            # Run Apify leads search
            result = await apify_leads_service.run_leads_search(query_params)
            raw_leads = result.get("leads", [])
            campaign.leads_found = len(raw_leads)
            
            # Filter valid leads (must have email AND LinkedIn)
            valid_leads = apify_leads_service.filter_valid_leads(raw_leads)
            campaign.leads_valid = len(valid_leads)
            await db.commit()
            
            # Create lead records
            for lead_data in valid_leads:
                transformed = apify_leads_service.transform_lead_data(lead_data, campaign_id)
                lead = Lead(
                    campaign_id=campaign_id,
                    state=LeadState.COLLECTED,
                    first_name=transformed["first_name"],
                    last_name=transformed["last_name"],
                    full_name=transformed.get("full_name"),
                    email=transformed["email"],
                    linkedin_url=transformed["linkedin_url"],
                    job_title=transformed.get("job_title"),
                    headline=transformed.get("headline"),
                    city=transformed.get("city"),
                    state_region=transformed.get("state_region"),
                    country=transformed.get("country"),
                    company_name=transformed.get("company_name"),
                    company_domain=transformed.get("company_domain"),
                    company_website=transformed.get("company_website"),
                    company_linkedin=transformed.get("company_linkedin"),
                    industry=transformed.get("industry"),
                    company_size=transformed.get("company_size"),
                    company_description=transformed.get("company_description"),
                )
                db.add(lead)
            
            await db.commit()
            
            # Enrich leads with LinkedIn posts
            campaign.status = CampaignStatus.ENRICHING
            await db.commit()
            
            leads_query = select(Lead).where(Lead.campaign_id == campaign_id)
            result = await db.execute(leads_query)
            leads = result.scalars().all()
            
            state_machine = get_state_machine(db)
            
            for lead in leads:
                try:
                    # Fetch LinkedIn posts
                    posts_result = await apify_linkedin_service.fetch_profile_posts(
                        lead.linkedin_url,
                        max_posts=2,
                    )
                    
                    if posts_result.get("success"):
                        lead.linkedin_posts_json = {
                            "posts": posts_result.get("posts", []),
                            "username": posts_result.get("username"),
                        }
                    
                    # Transition to ENRICHED
                    await state_machine.process_collected(lead)
                    campaign.leads_enriched += 1
                    await db.commit()
                    
                except Exception as e:
                    logger.error(f"Error enriching lead {lead.id}: {e}")
                    # Still transition to ENRICHED even without posts
                    lead.linkedin_posts_json = {"posts": [], "error": str(e)}
                    await state_machine.process_collected(lead)
                    await db.commit()
            
            # Mark campaign as active
            campaign.status = CampaignStatus.ACTIVE
            await db.commit()
            
            logger.info(f"Campaign {campaign_id} completed: {campaign.leads_valid} leads collected")
            
        except Exception as e:
            logger.error(f"Error in lead collection: {e}")
            campaign.status = CampaignStatus.FAILED
            campaign.error_message = str(e)
            await db.commit()


@router.post("", response_model=SearchResponse)
async def start_search(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new lead search campaign.
    
    This creates a campaign and starts background collection.
    """
    # Create campaign
    campaign = Campaign(
        keywords=request.keywords,
        status=CampaignStatus.PENDING,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    
    # Start background collection
    background_tasks.add_task(collect_and_enrich_leads, campaign.id, request.keywords)
    
    return SearchResponse(
        campaign_id=campaign.id,
        status="started",
        message=f"Campaign started. Collecting leads for: {request.keywords}",
    )


@router.get("/campaigns")
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    """List all campaigns."""
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = result.scalars().all()
    
    return {
        "campaigns": [
            {
                "id": c.id,
                "keywords": c.keywords,
                "status": c.status.value,
                "leads_found": c.leads_found,
                "leads_valid": c.leads_valid,
                "leads_enriched": c.leads_enriched,
                "created_at": c.created_at.isoformat(),
            }
            for c in campaigns
        ]
    }


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get campaign details."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "id": campaign.id,
        "keywords": campaign.keywords,
        "status": campaign.status.value,
        "leads_found": campaign.leads_found,
        "leads_valid": campaign.leads_valid,
        "leads_enriched": campaign.leads_enriched,
        "leads_emailed": campaign.leads_emailed,
        "error_message": campaign.error_message,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": campaign.updated_at.isoformat(),
    }
