"""Apify Leads Finder integration service."""

import csv
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx

from app.config import get_settings
from app.schemas.search import ApifyQueryParams
from app.utils.location_mapper import normalize_locations

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
        # Check if mock mode is enabled
        if self.settings.use_mock_leads:
            logger.info("MOCK MODE: Reading leads from CSV file instead of Apify API")
            return await self._read_leads_from_csv()
        
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
            # Normalize locations to exact Apify allowed values (safety net in case OpenAI didn't normalize properly)
            normalized_locations = normalize_locations(query_params.contact_location)
            if normalized_locations:
                input_payload["contact_location"] = normalized_locations
            else:
                logger.warning("All location values were invalid after normalization, skipping contact_location")
        if query_params.contact_city:
            input_payload["contact_city"] = query_params.contact_city
        if query_params.company_industry:
            input_payload["company_industry"] = query_params.company_industry
        if query_params.company_keywords:
            input_payload["company_keywords"] = query_params.company_keywords
        if query_params.size:
            input_payload["size"] = query_params.size
        
        logger.info(f"Running Apify leads search with params: {json.dumps(input_payload, indent=2)}")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Start the actor run
            # Apify API requires ~ instead of / in actor ID for URL path
            actor_id_url = APIFY_ACTOR_ID.replace("/", "~")
            run_url = f"{APIFY_API_BASE}/acts/{actor_id_url}/runs"
            logger.info(f"Calling Apify API: {run_url}")
            logger.info(f"Actor ID: {APIFY_ACTOR_ID}")
            response = await client.post(
                run_url,
                params={"token": self.api_token},
                json=input_payload,
            )
            
            if response.status_code != 201:
                logger.error(f"Failed to start Apify run. URL: {run_url}")
                logger.error(f"Status: {response.status_code}")
                logger.error(f"Response: {response.text}")
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
    
    async def _read_leads_from_csv(self) -> Dict[str, Any]:
        """
        Read leads from CSV file (mock mode).
        
        Returns:
            Dict containing leads and mock run_id
        """
        # Get the path to the CSV file
        csv_path = Path(__file__).parent.parent.parent / "data" / "dataset_sample.csv"
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        leads = []
        # Try multiple encodings to handle various character sets
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding, errors='replace') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Convert CSV row to dict (already in correct format)
                        leads.append(dict(row))
                logger.info(f"MOCK MODE: Retrieved {len(leads)} leads from CSV (using {encoding} encoding)")
                break
            except UnicodeDecodeError:
                logger.warning(f"Failed to read CSV with {encoding} encoding, trying next...")
                leads = []
                continue
            except Exception as e:
                logger.error(f"Error reading CSV with {encoding} encoding: {e}")
                leads = []
                continue
        
        if not leads:
            raise ValueError(f"Failed to read CSV file with any encoding. Tried: {', '.join(encodings)}")
        
        logger.info(f"MOCK MODE: Retrieved {len(leads)} leads from CSV")
        return {"leads": leads, "run_id": "mock_run_123"}
    
    def filter_valid_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter leads to only include those with email AND LinkedIn URL.
        
        Args:
            leads: Raw leads from Apify or CSV
            
        Returns:
            Filtered list of valid leads
        """
        valid_leads = []
        for lead in leads:
            email = lead.get("email", "").strip() if lead.get("email") else ""
            linkedin = lead.get("linkedin", "").strip() if lead.get("linkedin") else ""
            
            # CRITICAL: Check for both presence AND non-empty strings
            # This ensures required database fields will have values
            if email and linkedin:
                valid_leads.append(lead)
            else:
                logger.debug(f"Skipping lead without email or LinkedIn: {lead.get('full_name', 'Unknown')}")
        
        logger.info(f"Filtered to {len(valid_leads)} valid leads out of {len(leads)}")
        return valid_leads
    
    def transform_lead_data(self, apify_lead: Dict[str, Any], campaign_id: int) -> Dict[str, Any]:
        """
        Transform Apify lead data or CSV lead data to our schema format.
        
        Args:
            apify_lead: Raw lead data from Apify or CSV
            campaign_id: ID of the campaign
            
        Returns:
            Transformed lead data matching LeadCreate schema
        """
        # Helper function to convert empty strings to None for optional fields
        def to_none_if_empty(value):
            if value is None:
                return None
            stripped = str(value).strip()
            return stripped if stripped else None
        
        # Required fields - must be non-empty strings
        first_name = str(apify_lead.get("first_name", "")).strip()
        last_name = str(apify_lead.get("last_name", "")).strip()
        email = str(apify_lead.get("email", "")).strip()
        linkedin_url = str(apify_lead.get("linkedin", "")).strip()
        
        # Ensure required fields are not empty (filter_valid_leads should have caught this, but be defensive)
        if not first_name or not last_name or not email or not linkedin_url:
            raise ValueError(f"Required field missing in lead data: first_name={bool(first_name)}, last_name={bool(last_name)}, email={bool(email)}, linkedin={bool(linkedin_url)}")
        
        return {
            "campaign_id": campaign_id,
            "first_name": first_name,
            "last_name": last_name,
            "full_name": to_none_if_empty(apify_lead.get("full_name")),
            "email": email,
            "linkedin_url": linkedin_url,
            "job_title": to_none_if_empty(apify_lead.get("job_title")),
            "headline": to_none_if_empty(apify_lead.get("headline")),
            "city": to_none_if_empty(apify_lead.get("city")),
            "state_region": None,  # Not in CSV
            "country": to_none_if_empty(apify_lead.get("country")),
            "company_name": to_none_if_empty(apify_lead.get("company_name")),
            "company_domain": None,  # Not in CSV
            "company_website": None,  # Not in CSV
            "company_linkedin": None,  # Not in CSV
            "industry": to_none_if_empty(apify_lead.get("industry")),
            "company_size": None,  # Not in CSV
            "company_description": to_none_if_empty(apify_lead.get("company_description")),
        }


# Singleton instance
apify_leads_service = ApifyLeadsService()
