"""Debug endpoints for testing and troubleshooting."""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.services.openai_service import openai_service
from app.services.apify_leads import apify_leads_service
from app.services.apify_linkedin import apify_linkedin_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/campaigns/{campaign_id}/query")
async def get_campaign_query(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get the OpenAI-generated Apify query for a campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    query_json = None
    if campaign.apify_query_json:
        try:
            query_json = json.loads(campaign.apify_query_json)
        except:
            query_json = campaign.apify_query_json
    
    return {
        "campaign_id": campaign_id,
        "keywords": campaign.keywords,
        "status": campaign.status.value,
        "apify_query": query_json,
        "error_message": campaign.error_message,
    }


@router.get("/campaigns/{campaign_id}/details")
async def get_campaign_debug_details(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get full debug details for a campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get all leads for this campaign
    leads_query = select(Lead).where(Lead.campaign_id == campaign_id)
    result = await db.execute(leads_query)
    leads = result.scalars().all()
    
    query_json = None
    if campaign.apify_query_json:
        try:
            query_json = json.loads(campaign.apify_query_json)
        except:
            query_json = campaign.apify_query_json
    
    return {
        "campaign": {
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
        },
        "apify_query": query_json,
        "leads": [
            {
                "id": lead.id,
                "state": lead.state.value,
                "full_name": lead.full_name,
                "email": lead.email,
                "linkedin_url": lead.linkedin_url,
                "job_title": lead.job_title,
                "company_name": lead.company_name,
                "has_email": bool(lead.email),
                "has_linkedin": bool(lead.linkedin_url),
            }
            for lead in leads
        ],
        "lead_count": len(leads),
        "missing_leads": campaign.leads_found - len(leads),
    }


@router.get("/test-openai")
async def test_openai(keywords: str = Query(..., description="Keywords to test")):
    """Test OpenAI query generation directly (no database)."""
    try:
        query_params = await openai_service.generate_apify_query(keywords)
        return {
            "success": True,
            "keywords": keywords,
            "generated_query": query_params.model_dump(),
            "query_json": query_params.model_dump_json(),
        }
    except Exception as e:
        logger.error(f"OpenAI test failed: {e}", exc_info=True)
        return {
            "success": False,
            "keywords": keywords,
            "error": str(e),
            "error_type": type(e).__name__,
        }


@router.get("/campaigns/{campaign_id}/raw-leads")
async def get_raw_leads(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get raw lead data to see what Apify returned (for invalid leads)."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get all leads for this campaign
    leads_query = select(Lead).where(Lead.campaign_id == campaign_id)
    result = await db.execute(leads_query)
    leads = result.scalars().all()
    
    return {
        "campaign_id": campaign_id,
        "leads_found": campaign.leads_found,
        "leads_valid": campaign.leads_valid,
        "leads_in_db": len(leads),
        "missing_leads": campaign.leads_found - len(leads),
        "leads": [
            {
                "id": lead.id,
                "email": lead.email,
                "linkedin_url": lead.linkedin_url,
                "full_name": lead.full_name,
                "job_title": lead.job_title,
                "company_name": lead.company_name,
                "is_valid": bool(lead.email and lead.linkedin_url),
            }
            for lead in leads
        ],
    }


@router.get("/campaigns/{campaign_id}/enriched-leads")
async def get_enriched_leads(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get enriched leads with LinkedIn posts data - view in browser to see enrichment results."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get all leads for this campaign
    leads_query = select(Lead).where(Lead.campaign_id == campaign_id)
    result = await db.execute(leads_query)
    leads = result.scalars().all()
    
    enriched_leads = []
    for lead in leads:
        enrichment_status = {
            "has_posts": bool(lead.linkedin_posts_json and lead.linkedin_posts_json.get("posts")),
            "posts_count": len(lead.linkedin_posts_json.get("posts", [])) if lead.linkedin_posts_json else 0,
            "has_error": bool(lead.linkedin_posts_json and lead.linkedin_posts_json.get("error")),
            "is_mock_mode": bool(lead.linkedin_posts_json and lead.linkedin_posts_json.get("mock_mode")),
        }
        
        enriched_leads.append({
            "id": lead.id,
            "state": lead.state.value,
            "full_name": lead.full_name,
            "email": lead.email,
            "linkedin_url": lead.linkedin_url,
            "job_title": lead.job_title,
            "company_name": lead.company_name,
            "enrichment_status": enrichment_status,
            "linkedin_posts_json": lead.linkedin_posts_json,
            "enriched_at": lead.updated_at.isoformat() if lead.state.value == "ENRICHED" else None,
        })
    
    return {
        "campaign": {
            "id": campaign.id,
            "keywords": campaign.keywords,
            "status": campaign.status.value,
            "leads_found": campaign.leads_found,
            "leads_valid": campaign.leads_valid,
            "leads_enriched": campaign.leads_enriched,
        },
        "enrichment_summary": {
            "total_leads": len(leads),
            "enriched_count": sum(1 for l in leads if l.state.value == "ENRICHED"),
            "with_posts": sum(1 for l in leads if l.linkedin_posts_json and l.linkedin_posts_json.get("posts")),
            "with_errors": sum(1 for l in leads if l.linkedin_posts_json and l.linkedin_posts_json.get("error")),
            "mock_mode_count": sum(1 for l in leads if l.linkedin_posts_json and l.linkedin_posts_json.get("mock_mode")),
        },
        "leads": enriched_leads,
    }


@router.get("/leads/{lead_id}/enrichment")
async def get_lead_enrichment(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed enrichment data for a specific lead - view in browser."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {
        "lead": {
            "id": lead.id,
            "full_name": lead.full_name,
            "email": lead.email,
            "linkedin_url": lead.linkedin_url,
            "state": lead.state.value,
            "job_title": lead.job_title,
            "company_name": lead.company_name,
        },
        "enrichment": {
            "has_data": bool(lead.linkedin_posts_json),
            "linkedin_posts_json": lead.linkedin_posts_json,
            "posts_count": len(lead.linkedin_posts_json.get("posts", [])) if lead.linkedin_posts_json else 0,
            "username": lead.linkedin_posts_json.get("username") if lead.linkedin_posts_json else None,
            "mock_mode": lead.linkedin_posts_json.get("mock_mode", False) if lead.linkedin_posts_json else False,
            "has_error": bool(lead.linkedin_posts_json and lead.linkedin_posts_json.get("error")),
            "error": lead.linkedin_posts_json.get("error") if lead.linkedin_posts_json else None,
        },
        "timestamps": {
            "created_at": lead.created_at.isoformat(),
            "updated_at": lead.updated_at.isoformat(),
        },
    }


@router.get("/test-linkedin")
async def test_linkedin(linkedin_url: str = Query(..., description="LinkedIn profile URL to test"), max_posts: int = Query(2, description="Maximum posts to fetch")):
    """Test LinkedIn profile posts actor directly - view results in browser."""
    try:
        result = await apify_linkedin_service.fetch_profile_posts(linkedin_url, max_posts=max_posts)
        return {
            "success": result.get("success", False),
            "linkedin_url": linkedin_url,
            "username": result.get("username"),
            "posts_count": len(result.get("posts", [])),
            "posts": result.get("posts", []),
            "run_id": result.get("run_id"),
            "mock_mode": result.get("mock_mode", False),
            "error": result.get("error"),
            "full_result": result,
        }
    except Exception as e:
        return {
            "success": False,
            "linkedin_url": linkedin_url,
            "error": str(e),
            "error_type": type(e).__name__,
        }


@router.get("/health")
async def health_check():
    """Simple health check endpoint with service configuration status."""
    return {
        "status": "ok",
        "services": {
            "openai": "configured" if openai_service.settings.openai_api_key else "missing",
            "apify": "configured" if apify_leads_service.api_token else "missing",
        }
    }
