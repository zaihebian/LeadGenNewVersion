"""Pydantic schemas for Lead."""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, EmailStr

from app.models.lead import LeadState


class LeadBase(BaseModel):
    """Base lead schema."""
    first_name: str
    last_name: str
    email: EmailStr
    linkedin_url: str


class LeadCreate(LeadBase):
    """Schema for creating a lead from Apify data."""
    campaign_id: int
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    headline: Optional[str] = None
    city: Optional[str] = None
    state_region: Optional[str] = None
    country: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    company_website: Optional[str] = None
    company_linkedin: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    company_description: Optional[str] = None


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""
    state: Optional[LeadState] = None
    linkedin_posts_json: Optional[Dict[str, Any]] = None
    personalization_angle: Optional[str] = None
    emails_sent_count: Optional[int] = None
    last_email_at: Optional[datetime] = None


class LeadResponse(LeadBase):
    """Schema for lead response."""
    id: int
    campaign_id: int
    state: LeadState
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    headline: Optional[str] = None
    city: Optional[str] = None
    state_region: Optional[str] = None
    country: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    linkedin_posts_json: Optional[Dict[str, Any]] = None
    personalization_angle: Optional[str] = None
    emails_sent_count: int
    last_email_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    """Schema for paginated lead list."""
    leads: List[LeadResponse]
    total: int
    page: int
    per_page: int
