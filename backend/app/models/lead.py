"""Lead model with state machine."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LeadState(str, enum.Enum):
    """Lead state machine states."""
    COLLECTED = "COLLECTED"      # Returned by leads-finder
    ENRICHED = "ENRICHED"        # LinkedIn post data added
    EMAILED_1 = "EMAILED_1"      # First email sent, waiting for reply
    INTERESTED = "INTERESTED"    # Positive reply, human takeover
    NOT_INTERESTED = "NOT_INTERESTED"  # Negative reply handled
    EMAILED_2 = "EMAILED_2"      # Final follow-up sent, waiting for reply or closing
    CLOSED = "CLOSED"            # Terminal state


class Lead(Base):
    """Lead entity storing contact information and state."""
    
    __tablename__ = "leads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    
    # State machine
    state: Mapped[LeadState] = mapped_column(
        Enum(LeadState), 
        default=LeadState.COLLECTED,
        nullable=False
    )
    
    # Person data from Apify leads-finder
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    linkedin_url: Mapped[str] = mapped_column(String(500), nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    headline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Location
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state_region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Company data
    company_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company_domain: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company_website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    company_linkedin: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Enrichment data (LinkedIn posts)
    linkedin_posts_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Personalization
    personalization_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Email tracking
    emails_sent_count: Mapped[int] = mapped_column(Integer, default=0)
    last_email_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="leads")
    email_threads = relationship("EmailThread", back_populates="lead", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Lead {self.id}: {self.full_name} ({self.state.value})>"
