"""Pydantic schemas for search operations."""

from typing import Optional, Dict, Any

from pydantic import BaseModel


class SearchRequest(BaseModel):
    """Schema for initiating a lead search."""
    keywords: str


class SearchResponse(BaseModel):
    """Schema for search response."""
    campaign_id: int
    status: str
    message: str


class ApifyQueryParams(BaseModel):
    """Schema for Apify leads-finder query parameters."""
    fetch_count: int = 5
    contact_job_title: Optional[list[str]] = None
    contact_location: Optional[list[str]] = None
    contact_city: Optional[list[str]] = None
    seniority_level: Optional[list[str]] = None
    functional_level: Optional[list[str]] = None
    company_industry: Optional[list[str]] = None
    company_keywords: Optional[list[str]] = None
    size: Optional[list[str]] = None
    email_status: list[str] = ["validated"]
