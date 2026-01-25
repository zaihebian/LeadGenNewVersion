"""Pydantic schemas."""

from app.schemas.lead import LeadCreate, LeadResponse, LeadUpdate, LeadListResponse
from app.schemas.email_thread import EmailThreadResponse, EmailMessageCreate
from app.schemas.campaign import CampaignCreate, CampaignResponse
from app.schemas.search import SearchRequest, SearchResponse, ApifyQueryParams
from app.schemas.dashboard import DashboardStats

__all__ = [
    "LeadCreate", "LeadResponse", "LeadUpdate", "LeadListResponse",
    "EmailThreadResponse", "EmailMessageCreate",
    "CampaignCreate", "CampaignResponse",
    "SearchRequest", "SearchResponse", "ApifyQueryParams",
    "DashboardStats",
]
