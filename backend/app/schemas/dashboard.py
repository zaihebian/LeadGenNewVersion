"""Pydantic schemas for dashboard."""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Schema for dashboard statistics."""
    leads_contacted: int
    replies_received: int
    interested_leads: int
    not_interested_leads: int
    closed_leads: int
    awaiting_reply: int
    total_leads: int
    total_campaigns: int
