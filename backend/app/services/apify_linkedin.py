"""Apify LinkedIn Profile Posts integration service."""

import logging
import re
from typing import Optional, Dict, Any, List

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

APIFY_ACTOR_ID = "apimaestro/linkedin-profile-posts"
APIFY_API_BASE = "https://api.apify.com/v2"


class ApifyLinkedInService:
    """Service for fetching LinkedIn posts via Apify."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_token = self.settings.apify_api_token
    
    def extract_linkedin_username(self, linkedin_url: str) -> Optional[str]:
        """
        Extract username from LinkedIn URL.
        
        Args:
            linkedin_url: Full LinkedIn profile URL
            
        Returns:
            Username string or None
        """
        # Pattern for linkedin.com/in/username
        patterns = [
            r"linkedin\.com/in/([^/?]+)",
            r"linkedin\.com/pub/([^/?]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, linkedin_url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    async def fetch_profile_posts(
        self, 
        linkedin_url: str,
        max_posts: int = 2,
    ) -> Dict[str, Any]:
        """
        Fetch recent posts for a LinkedIn profile.
        
        Args:
            linkedin_url: LinkedIn profile URL
            max_posts: Maximum number of posts to fetch (default 2)
            
        Returns:
            Dict containing posts data or error
        """
        # LinkedIn API always calls real API (for testing when USE_MOCK_LEADS=true)
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN not configured")
        
        username = self.extract_linkedin_username(linkedin_url)
        if not username:
            return {"success": False, "error": "Invalid LinkedIn URL", "posts": []}
        
        # Build input payload
        input_payload = {
            "username": username,
            "page_number": 1,
            # Note: Actor returns up to 100 posts per page, we'll slice after
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Start the actor run
                # Apify API requires ~ instead of / in actor ID for URL path
                actor_id_url = APIFY_ACTOR_ID.replace("/", "~")
                run_url = f"{APIFY_API_BASE}/acts/{actor_id_url}/runs"
                response = await client.post(
                    run_url,
                    params={"token": self.api_token},
                    json=input_payload,
                )
                
                if response.status_code != 201:
                    return {"success": False, "error": f"API error: {response.status_code}", "posts": []}
                
                run_data = response.json()
                run_id = run_data["data"]["id"]
                
                # Wait for run to complete (poll)
                run_status_url = f"{APIFY_API_BASE}/actor-runs/{run_id}"
                import asyncio
                max_wait = 60  # Max 60 seconds
                waited = 0
                
                while waited < max_wait:
                    status_response = await client.get(
                        run_status_url,
                        params={"token": self.api_token},
                    )
                    status_data = status_response.json()
                    status = status_data["data"]["status"]
                    
                    if status == "SUCCEEDED":
                        break
                    elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                        return {"success": False, "error": f"Run failed: {status}", "posts": []}
                    
                    await asyncio.sleep(3)
                    waited += 3
                
                if waited >= max_wait:
                    return {"success": False, "error": "Timeout waiting for results", "posts": []}
                
                # Get dataset items
                dataset_id = status_data["data"]["defaultDatasetId"]
                dataset_url = f"{APIFY_API_BASE}/datasets/{dataset_id}/items"
                
                items_response = await client.get(
                    dataset_url,
                    params={"token": self.api_token},
                )
                
                result_data = items_response.json()
                
                # Extract posts from the response
                posts = self._extract_posts(result_data, max_posts)
                
                return {
                    "success": True,
                    "username": username,
                    "posts": posts,
                    "run_id": run_id,
                }
                
        except Exception as e:
            return {"success": False, "error": str(e), "posts": []}
    
    def _extract_posts(self, result_data: Any, max_posts: int) -> List[Dict[str, Any]]:
        """
        Extract and format posts from Apify response.
        
        Args:
            result_data: Raw response from Apify
            max_posts: Maximum posts to return
            
        Returns:
            List of formatted post objects
        """
        posts = []
        
        try:
            # Handle different response structures
            if isinstance(result_data, list) and len(result_data) > 0:
                # Response is a list of results
                first_result = result_data[0]
                if isinstance(first_result, dict):
                    raw_posts = first_result.get("data", {}).get("posts", [])
                else:
                    raw_posts = []
            elif isinstance(result_data, dict):
                raw_posts = result_data.get("data", {}).get("posts", [])
            else:
                raw_posts = []
            
            for post in raw_posts[:max_posts]:
                formatted_post = {
                    "text": post.get("text", ""),
                    "posted_at": post.get("posted_at", {}).get("date"),
                    "url": post.get("url"),
                    "post_type": post.get("post_type"),
                    "stats": {
                        "reactions": post.get("stats", {}).get("total_reactions", 0),
                        "comments": post.get("stats", {}).get("comments", 0),
                    },
                }
                posts.append(formatted_post)
            
        except Exception as e:
            pass
        
        return posts


# Singleton instance
apify_linkedin_service = ApifyLinkedInService()
