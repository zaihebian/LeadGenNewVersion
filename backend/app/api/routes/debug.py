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
