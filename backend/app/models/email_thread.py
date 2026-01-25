"""Email thread model for tracking conversations."""

import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, Integer, DateTime, Enum, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReplySentiment(str, enum.Enum):
    """Sentiment classification for replies."""
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class EmailThread(Base):
    """Email thread tracking conversations with leads."""
    
    __tablename__ = "email_threads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)
    
    # Gmail thread tracking
    gmail_thread_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    gmail_message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Email content
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Messages stored as JSON array
    # Each message: {role: "sent"|"received", content: str, timestamp: str, gmail_id: str}
    messages_json: Mapped[List[dict]] = mapped_column(JSON, default=list)
    
    # Reply tracking
    reply_sentiment: Mapped[Optional[ReplySentiment]] = mapped_column(
        Enum(ReplySentiment), 
        nullable=True
    )
    has_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationship
    lead = relationship("Lead", back_populates="email_threads")
    
    def __repr__(self) -> str:
        return f"<EmailThread {self.id}: {self.subject[:30]}...>"
    
    def add_message(self, role: str, content: str, gmail_id: Optional[str] = None):
        """Add a message to the thread."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "gmail_id": gmail_id,
        }
        if self.messages_json is None:
            self.messages_json = []
        self.messages_json = self.messages_json + [message]
