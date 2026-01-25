"""Apify Leads Finder integration service."""

import logging
from typing import Optional, Dict, Any, List

import httpx

from app.config import get_settings
from app.schemas.search import ApifyQueryParams

logger = logging.getLogger(__name__)

APIFY_ACTOR_ID = "code_crafter/leads-finder"
APIFY_API_BASE = "https://api.apify.com/v2"


class ApifyLeadsService:
    """Service for interacting with Apify Leads Finder actor."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_token = self.settings.apify_api_token
    
    async def run_leads_search(self, query_params: ApifyQueryParams) -> Dict[str, Any]:
        """
        Run the leads-finder actor with given parameters.
        
        Args:
            query_params: Query parameters for the leads search
            
        Returns:
            Dict containing run results or error
        """
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN not configured")
        
        # Build input payload
        input_payload = {
            "fetch_count": query_params.fetch_count,
            "email_status": query_params.email_status,
        }
        
        # Add optional parameters
        if query_params.contact_job_title:
            input_payload["contact_job_title"] = query_params.contact_job_title
        if query_params.contact_location:
            input_payload["contact_location"] = query_params.contact_location
        if query_params.contact_city:
            input_payload["contact_city"] = query_params.contact_city
        if query_params.seniority_level:
            input_payload["seniority_level"] = query_params.seniority_level
        if query_params.functional_level:
            input_payload["functional_level"] = query_params.functional_level
        if query_params.company_industry:
            input_payload["company_industry"] = query_params.company_industry
        if query_params.company_keywords:
            input_payload["company_keywords"] = query_params.company_keywords
        if query_params.size:
            input_payload["size"] = query_params.size
        
        logger.info(f"Running Apify leads search with params: {input_payload}")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Start the actor run
            run_url = f"{APIFY_API_BASE}/acts/{APIFY_ACTOR_ID}/runs"
            response = await client.post(
                run_url,
                params={"token": self.api_token},
                json=input_payload,
            )
            
            if response.status_code != 201:
                logger.error(f"Failed to start Apify run: {response.text}")
                raise Exception(f"Apify API error: {response.status_code}")
            
            run_data = response.json()
            run_id = run_data["data"]["id"]
            logger.info(f"Started Apify run: {run_id}")
            
            # Wait for run to complete (poll)
            run_status_url = f"{APIFY_API_BASE}/actor-runs/{run_id}"
            while True:
                status_response = await client.get(
                    run_status_url,
                    params={"token": self.api_token},
                )
                status_data = status_response.json()
                status = status_data["data"]["status"]
                
                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    raise Exception(f"Apify run failed with status: {status}")
                
                # Wait before polling again
                import asyncio
                await asyncio.sleep(5)
            
            # Get dataset items
            dataset_id = status_data["data"]["defaultDatasetId"]
            dataset_url = f"{APIFY_API_BASE}/datasets/{dataset_id}/items"
            
            items_response = await client.get(
                dataset_url,
                params={"token": self.api_token},
            )
            
            leads = items_response.json()
            logger.info(f"Retrieved {len(leads)} leads from Apify")
            
            return {"leads": leads, "run_id": run_id}
    
    def filter_valid_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter leads to only include those with email AND LinkedIn URL.
        
        Args:
            leads: Raw leads from Apify
            
        Returns:
            Filtered list of valid leads
        """
        valid_leads = []
        for lead in leads:
            email = lead.get("email")
            linkedin = lead.get("linkedin")
            
            if email and linkedin:
                valid_leads.append(lead)
            else:
                logger.debug(f"Skipping lead without email or LinkedIn: {lead.get('full_name')}")
        
        logger.info(f"Filtered to {len(valid_leads)} valid leads out of {len(leads)}")
        return valid_leads
    
    def transform_lead_data(self, apify_lead: Dict[str, Any], campaign_id: int) -> Dict[str, Any]:
        """
        Transform Apify lead data to our schema format.
        
        Args:
            apify_lead: Raw lead data from Apify
            campaign_id: ID of the campaign
            
        Returns:
            Transformed lead data matching LeadCreate schema
        """
        return {
            "campaign_id": campaign_id,
            "first_name": apify_lead.get("first_name", ""),
            "last_name": apify_lead.get("last_name", ""),
            "full_name": apify_lead.get("full_name"),
            "email": apify_lead.get("email"),
            "linkedin_url": apify_lead.get("linkedin"),
            "job_title": apify_lead.get("job_title"),
            "headline": apify_lead.get("headline"),
            "city": apify_lead.get("city"),
            "state_region": apify_lead.get("state"),
            "country": apify_lead.get("country"),
            "company_name": apify_lead.get("company_name"),
            "company_domain": apify_lead.get("company_domain"),
            "company_website": apify_lead.get("company_website"),
            "company_linkedin": apify_lead.get("company_linkedin"),
            "industry": apify_lead.get("industry"),
            "company_size": apify_lead.get("company_size"),
            "company_description": apify_lead.get("company_description"),
        }


# Singleton instance
apify_leads_service = ApifyLeadsService()
