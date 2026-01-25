"""Campaign model for tracking search campaigns."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CampaignStatus(str, enum.Enum):
    """Campaign status."""
    PENDING = "PENDING"
    COLLECTING = "COLLECTING"
    ENRICHING = "ENRICHING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Campaign(Base):
    """Campaign entity for tracking lead search operations."""
    
    __tablename__ = "campaigns"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Search parameters
    keywords: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Generated Apify query (from OpenAI)
    apify_query_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus),
        default=CampaignStatus.PENDING,
        nullable=False
    )
    
    # Metrics
    leads_found: Mapped[int] = mapped_column(Integer, default=0)
    leads_valid: Mapped[int] = mapped_column(Integer, default=0)  # With email + LinkedIn
    leads_enriched: Mapped[int] = mapped_column(Integer, default=0)
    leads_emailed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    leads = relationship("Lead", back_populates="campaign", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Campaign {self.id}: {self.keywords[:30]}... ({self.status.value})>"
