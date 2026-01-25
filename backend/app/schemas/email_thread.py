"""Pydantic schemas for EmailThread."""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel

from app.models.email_thread import ReplySentiment


class EmailMessage(BaseModel):
    """Schema for a single email message."""
    role: str  # "sent" or "received"
    content: str
    timestamp: str
    gmail_id: Optional[str] = None


class EmailMessageCreate(BaseModel):
    """Schema for creating/sending an email message."""
    content: str


class EmailThreadBase(BaseModel):
    """Base email thread schema."""
    subject: str


class EmailThreadResponse(EmailThreadBase):
    """Schema for email thread response."""
    id: int
    lead_id: int
    gmail_thread_id: Optional[str] = None
    messages_json: List[Dict[str, Any]]
    reply_sentiment: Optional[ReplySentiment] = None
    has_reply: bool
    requires_human: bool
    created_at: datetime
    updated_at: datetime
    
    # Include lead summary
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    lead_company: Optional[str] = None

    class Config:
        from_attributes = True


class EmailThreadListResponse(BaseModel):
    """Schema for email thread list."""
    threads: List[EmailThreadResponse]
    total: int
