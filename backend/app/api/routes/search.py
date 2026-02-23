"""Search routes for initiating lead collection."""

import csv
import io
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
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
from app.services.company_context import save_company_context, get_company_context

logger = logging.getLogger(__name__)

router = APIRouter()


async def _enrich_leads_for_campaign(campaign_id: int, db: AsyncSession) -> None:
    """
    Shared enrichment loop: fetch LinkedIn posts for every COLLECTED lead
    in the campaign and transition each to ENRICHED.

    Used by both the search flow and the upload flow.
    """
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        logger.error(f"Campaign {campaign_id} not found during enrichment")
        return

    campaign.status = CampaignStatus.ENRICHING
    await db.commit()

    leads_query = select(Lead).where(Lead.campaign_id == campaign_id)
    result = await db.execute(leads_query)
    leads = result.scalars().all()

    logger.info(f"[Campaign {campaign_id}] Starting enrichment for {len(leads)} leads")

    state_machine = get_state_machine(db)

    for lead in leads:
        try:
            logger.info(
                f"[Campaign {campaign_id}] Enriching lead {lead.id}: "
                f"{lead.full_name} ({lead.email})"
            )
            logger.info(
                f"[Campaign {campaign_id}] Lead {lead.id} LinkedIn URL: {lead.linkedin_url}"
            )

            posts_result = await apify_linkedin_service.fetch_profile_posts(
                lead.linkedin_url,
                max_posts=2,
            )

            logger.info(
                f"[Campaign {campaign_id}] Lead {lead.id} enrichment result: "
                f"success={posts_result.get('success')}, "
                f"posts_count={len(posts_result.get('posts', []))}, "
                f"mock_mode={posts_result.get('mock_mode', False)}"
            )

            if posts_result.get("success"):
                lead.linkedin_posts_json = {
                    "posts": posts_result.get("posts", []),
                    "username": posts_result.get("username"),
                    "mock_mode": posts_result.get("mock_mode", False),
                }
                logger.info(
                    f"[Campaign {campaign_id}] Lead {lead.id} enriched successfully."
                )
            else:
                error_msg = posts_result.get("error", "Unknown error")
                lead.linkedin_posts_json = {"posts": [], "error": error_msg}
                logger.warning(
                    f"[Campaign {campaign_id}] Lead {lead.id} enrichment failed: {error_msg}"
                )

            await state_machine.process_collected(lead)
            campaign.leads_enriched += 1
            await db.commit()

        except Exception as e:
            logger.error(
                f"[Campaign {campaign_id}] Error enriching lead {lead.id}: {e}",
                exc_info=True,
            )
            lead.linkedin_posts_json = {"posts": [], "error": str(e)}
            await state_machine.process_collected(lead)
            await db.commit()

    campaign.status = CampaignStatus.ACTIVE
    await db.commit()
    logger.info(f"Campaign {campaign_id} enrichment complete: {campaign.leads_enriched} leads enriched")


async def collect_and_enrich_leads(campaign_id: int, keywords: str):
    """
    Background task to collect leads from Apify and enrich them.

    This runs after the API returns to avoid timeout.
    """
    from app.database import async_session_maker

    async with async_session_maker() as db:
        try:
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

            # Enrich with LinkedIn posts (shared helper)
            await _enrich_leads_for_campaign(campaign_id, db)

        except Exception as e:
            logger.error(f"Error in lead collection: {e}")
            campaign = await db.get(Campaign, campaign_id)
            if campaign:
                campaign.status = CampaignStatus.FAILED
                campaign.error_message = str(e)
                await db.commit()


async def enrich_uploaded_leads(campaign_id: int):
    """
    Background task for upload flow: enrich COLLECTED leads that came from a CSV.

    Skips Apify collection and goes straight to LinkedIn enrichment.
    """
    from app.database import async_session_maker

    async with async_session_maker() as db:
        try:
            await _enrich_leads_for_campaign(campaign_id, db)
        except Exception as e:
            logger.error(f"Error enriching uploaded leads for campaign {campaign_id}: {e}")
            campaign = await db.get(Campaign, campaign_id)
            if campaign:
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
    campaign = Campaign(
        keywords=request.keywords,
        status=CampaignStatus.PENDING,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    background_tasks.add_task(collect_and_enrich_leads, campaign.id, request.keywords)

    return SearchResponse(
        campaign_id=campaign.id,
        status="started",
        message=f"Campaign started. Collecting leads for: {request.keywords}",
    )


@router.post("/upload", response_model=SearchResponse)
async def upload_leads(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a CSV file of leads to start a campaign.

    Required CSV columns: email, linkedin, first_name, last_name
    Optional columns: full_name, job_title, headline, city, country,
                      company_name, industry, company_description

    Rows missing email or linkedin are skipped. Leads enter the pipeline
    at the COLLECTED state and proceed through enrichment and outreach
    identically to search-sourced leads.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    # Read and parse CSV
    try:
        contents = await file.read()
        text = contents.decode("utf-8-sig")  # handles BOM if present
    except UnicodeDecodeError:
        try:
            text = contents.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Unable to decode CSV file. Please use UTF-8 encoding.")

    reader = csv.DictReader(io.StringIO(text))
    raw_rows = [dict(row) for row in reader]

    if not raw_rows:
        raise HTTPException(status_code=400, detail="CSV file is empty or has no data rows")

    # Validate and filter rows
    valid_leads = apify_leads_service.filter_valid_leads(raw_rows)

    if not valid_leads:
        raise HTTPException(
            status_code=400,
            detail=(
                "No valid leads found in the CSV. "
                "Every row must have both 'email' and 'linkedin' columns with values."
            ),
        )

    # Create campaign
    campaign = Campaign(
        keywords=f"[Upload] {file.filename}",
        status=CampaignStatus.PENDING,
        leads_found=len(raw_rows),
        leads_valid=len(valid_leads),
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    # Insert leads as COLLECTED
    for lead_data in valid_leads:
        try:
            transformed = apify_leads_service.transform_lead_data(lead_data, campaign.id)
        except ValueError as e:
            logger.warning(f"Skipping row due to transform error: {e}")
            continue

        lead = Lead(
            campaign_id=campaign.id,
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

    # Start enrichment in the background (skip Apify collection)
    background_tasks.add_task(enrich_uploaded_leads, campaign.id)

    return SearchResponse(
        campaign_id=campaign.id,
        status="started",
        message=f"Upload accepted. Enriching {len(valid_leads)} leads from {file.filename}",
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

    query_json = None
    if campaign.apify_query_json:
        try:
            query_json = json.loads(campaign.apify_query_json)
        except Exception:
            query_json = campaign.apify_query_json

    return {
        "id": campaign.id,
        "keywords": campaign.keywords,
        "status": campaign.status.value,
        "leads_found": campaign.leads_found,
        "leads_valid": campaign.leads_valid,
        "leads_enriched": campaign.leads_enriched,
        "leads_emailed": campaign.leads_emailed,
        "error_message": campaign.error_message,
        "apify_query": query_json,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": campaign.updated_at.isoformat(),
    }


@router.post("/company-info")
async def upload_company_info(file: UploadFile = File(...)):
    """Upload a .txt or .md file with company info to enrich cold email context."""
    if not file.filename or not file.filename.lower().endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only .txt and .md files are allowed")
    text = (await file.read()).decode("utf-8")
    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")
    save_company_context(text)
    return {"message": "Company info saved", "length": len(text)}


@router.get("/company-info")
async def get_company_info():
    """Return the currently stored company context."""
    ctx = get_company_context()
    return {"has_context": ctx is not None, "text": ctx or ""}
