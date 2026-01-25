"""Pydantic schemas for Campaign."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

from app.models.campaign import CampaignStatus


class CampaignCreate(BaseModel):
    """Schema for creating a campaign."""
    keywords: str


class CampaignResponse(BaseModel):
    """Schema for campaign response."""
    id: int
    keywords: str
    status: CampaignStatus
    leads_found: int
    leads_valid: int
    leads_enriched: int
    leads_emailed: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    """Schema for campaign list."""
    campaigns: List[CampaignResponse]
    total: int
