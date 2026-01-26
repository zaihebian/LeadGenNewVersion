"""OpenAI service for query generation, email writing, and sentiment analysis."""

import json
import logging
from typing import Optional, Dict, Any, List

from openai import AsyncOpenAI

from app.config import get_settings
from app.schemas.search import ApifyQueryParams
from app.utils.location_mapper import normalize_locations

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for OpenAI API interactions."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
    
    async def generate_apify_query(self, keywords: str) -> ApifyQueryParams:
        """
        Convert free-text keywords into structured Apify query parameters.
        
        Args:
            keywords: User's free-text search keywords
            
        Returns:
            ApifyQueryParams with structured search parameters
        """
        system_prompt = """You are an expert at converting natural language lead search queries into structured parameters for Apify's leads-finder API.

IMPORTANT: You can ONLY use these exact field names (all fields accept arrays unless noted):

People targeting:
- contact_job_title: Array of job titles to include (e.g., ["CTO", "Head of Marketing", "VP Engineering"])
- contact_not_job_title: Array of job titles to exclude
- seniority_level: Array from [Founder, Owner, C-Level, Director, VP, Head, Manager, Senior, Entry, Trainee]
- functional_level: Array from [C-Level, Finance, Product, Engineering, Design, HR, IT, Legal, Marketing, Operations, Sales, Support]

Location (Include):
- contact_location: Array of regions/countries/states. MUST be lowercase. Map: "US"->"united states", "UK"->"united kingdom", "CA"->"california, us". Examples: ["united states"], ["united kingdom"], ["california, us"]
- contact_city: Array of cities (use this INSTEAD of contact_location when user wants city-level targeting only)

Location (Exclude):
- contact_not_location: Array of regions/countries/states to exclude
- contact_not_city: Array of cities to exclude

Email quality:
- email_status: Array from ["validated", "not_validated", "unknown"] (default: ["validated"])

Company targeting:
- company_domain: Array of specific domains (e.g., ["google.com", "apple.com"])
- size: Array from ["0-1", "2-10", "11-20", "21-50", "51-100", "101-200", "201-500", "501-1000", "1001-2000", "2001-5000", "10000+"]
- company_industry: Array of industries to include (e.g., ["computer software", "internet", "saas", "fintech"])
- company_not_industry: Array of industries to exclude
- company_keywords: Array of free-text keywords to include (e.g., ["startup", "fintech"])
- company_not_keywords: Array of free-text keywords to exclude
- min_revenue: String (e.g., "100K", "1M", "10B")
- max_revenue: String (e.g., "100K", "1M", "10B")
- funding: Array from [Seed, Angel, Series A, Series B, Series C, Series D, Series E, Series F, Venture, Debt, Convertible, PE, Other]

Apify Examples:
Example 1: {"contact_job_title": ["Head of Marketing","VP Marketing","CMO"], "functional_level": ["marketing"], "contact_location": ["united states"], "company_industry": ["computer software","internet","saas"], "email_status": ["validated"]}
Example 2: {"contact_job_title": ["CTO","Head of Engineering"], "contact_location": ["united kingdom"], "email_status": ["validated","unknown"]}
Example 3: {"contact_city": ["amsterdam"]} (contact_location left empty for city-only targeting)

CRITICAL RULES:
1. ONLY use the field names listed above - do not invent new fields
2. contact_location MUST be lowercase (e.g., "united kingdom" not "United Kingdom")
3. If user mentions a city for targeting, use contact_city and leave contact_location empty
4. Return only fields that are clearly specified in the query
5. Omit any fields not mentioned above

Return a JSON object with only the relevant fields from the list above."""

        user_prompt = f"Convert this lead search query into structured parameters: {keywords}"
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Generated Apify query from keywords: {result}")
            
            # Valid Apify field names (only these are accepted by the API)
            valid_apify_fields = {
                "contact_job_title", "contact_not_job_title",
                "seniority_level", "functional_level",
                "contact_location", "contact_city",
                "contact_not_location", "contact_not_city",
                "email_status",
                "company_domain", "size", "company_industry", "company_not_industry",
                "company_keywords", "company_not_keywords",
                "min_revenue", "max_revenue", "funding"
            }
            
            # Filter out any invalid fields that OpenAI might have generated
            filtered_result = {}
            invalid_fields = []
            for key, value in result.items():
                if key in valid_apify_fields:
                    filtered_result[key] = value
                else:
                    invalid_fields.append(key)
            
            if invalid_fields:
                logger.warning(f"OpenAI generated invalid fields (removed): {invalid_fields}. Only using valid Apify fields.")
            
            # Normalize contact_location values to ensure they match Apify's exact requirements
            contact_location = filtered_result.get("contact_location")
            if contact_location:
                contact_location = normalize_locations(contact_location)
                if not contact_location:
                    logger.warning("All location values were invalid, removing contact_location")
                    contact_location = None
                filtered_result["contact_location"] = contact_location
            
            # Build ApifyQueryParams with defaults (only fields in our schema)
            query_params = ApifyQueryParams(
                fetch_count=self.settings.max_leads_per_run,
                contact_job_title=filtered_result.get("contact_job_title"),
                contact_location=filtered_result.get("contact_location"),
                contact_city=filtered_result.get("contact_city"),
                seniority_level=filtered_result.get("seniority_level"),
                functional_level=filtered_result.get("functional_level"),
                company_industry=filtered_result.get("company_industry"),
                company_keywords=filtered_result.get("company_keywords"),
                size=filtered_result.get("size"),
            )
            
            return query_params
            
        except Exception as e:
            logger.error(f"Error generating Apify query: {e}")
            raise
    
    async def generate_outreach_email(
        self,
        lead_data: Dict[str, Any],
        linkedin_posts: Optional[List[Dict[str, Any]]] = None,
        prompt_variant: int = 0,
    ) -> Dict[str, str]:
        """
        Generate a personalized outreach email for a lead.
        
        Args:
            lead_data: Lead information (name, title, company, etc.)
            linkedin_posts: Recent LinkedIn posts for personalization
            prompt_variant: Which internal prompt variant to use (0-2)
            
        Returns:
            Dict with 'subject' and 'body' keys
        """
        # Internal prompt variants (not exposed to user)
        prompt_variants = [
            # Variant 0: Direct value proposition
            """Write a brief, personalized cold email. Focus on:
- A specific pain point relevant to their role/industry
- A clear, concise value proposition
- A soft call to action (question, not meeting request)
Keep it under 100 words. Be conversational, not salesy.""",

            # Variant 1: Curiosity-driven
            """Write a short, curiosity-driven cold email. Focus on:
- Lead with an insight or observation about their industry
- Reference something specific about them or their company
- End with an intriguing question
Keep it under 100 words. Sound like a peer, not a vendor.""",

            # Variant 2: Problem-aware
            """Write a concise problem-aware cold email. Focus on:
- Acknowledge a common challenge in their role
- Share a brief relevant insight or approach
- Offer to share more if relevant
Keep it under 100 words. Be helpful, not pushy.""",
        ]
        
        # Build context about the lead
        lead_context = f"""Lead Information:
- Name: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
- Job Title: {lead_data.get('job_title', 'Unknown')}
- Company: {lead_data.get('company_name', 'Unknown')}
- Industry: {lead_data.get('industry', 'Unknown')}"""

        # Add LinkedIn posts for personalization
        post_context = ""
        if linkedin_posts:
            posts_text = []
            for i, post in enumerate(linkedin_posts[:2]):  # Max 2 posts
                text = post.get("text", "")[:500]  # Limit post length
                if text:
                    posts_text.append(f"Post {i+1}: {text}")
            
            if posts_text:
                post_context = f"""
                
Recent LinkedIn Activity (use for personalization):
{chr(10).join(posts_text)}"""
        
        system_prompt = f"""You are an expert cold email writer. {prompt_variants[prompt_variant % 3]}

{lead_context}{post_context}

Return a JSON object with 'subject' (compelling, under 50 chars) and 'body' (the email content).
Do not include [Your Name] or similar placeholders - end naturally."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the personalized outreach email."},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Generated email for {lead_data.get('email')}")
            
            return {
                "subject": result.get("subject", "Quick question"),
                "body": result.get("body", ""),
            }
            
        except Exception as e:
            logger.error(f"Error generating email: {e}")
            raise
    
    async def classify_reply_sentiment(self, reply_text: str) -> str:
        """
        Classify the sentiment of a reply email.
        
        Args:
            reply_text: The text of the reply email
            
        Returns:
            Sentiment classification: "POSITIVE", "NEGATIVE", or "NEUTRAL"
        """
        system_prompt = """Analyze this email reply and classify the sender's intent:

- POSITIVE: Shows interest, asks questions, wants to learn more, requests a call/meeting
- NEGATIVE: Explicit rejection, not interested, asks to stop contacting, unsubscribe request
- NEUTRAL: Automatic replies, out of office, unclear intent, forwarding to someone else

Return a JSON object with 'sentiment' (POSITIVE, NEGATIVE, or NEUTRAL) and 'reasoning' (brief explanation)."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Classify this reply:\n\n{reply_text}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            result = json.loads(response.choices[0].message.content)
            sentiment = result.get("sentiment", "NEUTRAL").upper()
            logger.info(f"Classified reply as {sentiment}: {result.get('reasoning', '')}")
            
            return sentiment
            
        except Exception as e:
            logger.error(f"Error classifying sentiment: {e}")
            return "NEUTRAL"
    
    async def generate_polite_followup(
        self,
        lead_data: Dict[str, Any],
        original_email: str,
        is_after_rejection: bool = False,
    ) -> Dict[str, str]:
        """
        Generate a polite follow-up email.
        
        Args:
            lead_data: Lead information
            original_email: The original email that was sent
            is_after_rejection: Whether this is after a negative reply
            
        Returns:
            Dict with 'subject' and 'body' keys
        """
        if is_after_rejection:
            prompt = """Write a very brief, polite follow-up asking why it's not a fit.
Be respectful of their decision. Max 50 words. This is the final message."""
        else:
            prompt = """Write a brief follow-up email (no reply after 14 days).
Reference the original email briefly. Different angle. Max 75 words.
Be respectful of their time. Soft close only."""

        system_prompt = f"""{prompt}

Lead: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')} at {lead_data.get('company_name', 'their company')}

Original email context:
{original_email[:300]}...

Return JSON with 'subject' (use "Re: [original subject]" format) and 'body'."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the follow-up email."},
                ],
                response_format={"type": "json_object"},
                temperature=0.6,
            )
            
            result = json.loads(response.choices[0].message.content)
            return {
                "subject": result.get("subject", "Following up"),
                "body": result.get("body", ""),
            }
            
        except Exception as e:
            logger.error(f"Error generating followup: {e}")
            raise


# Singleton instance
openai_service = OpenAIService()
