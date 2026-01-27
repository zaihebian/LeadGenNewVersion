"""Lead state machine with strict transition rules."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead, LeadState
from app.models.email_thread import EmailThread, ReplySentiment

logger = logging.getLogger(__name__)


# Valid state transitions
VALID_TRANSITIONS: Dict[LeadState, list[LeadState]] = {
    LeadState.COLLECTED: [LeadState.ENRICHED],
    LeadState.ENRICHED: [LeadState.EMAILED_1],
    LeadState.EMAILED_1: [LeadState.INTERESTED, LeadState.NOT_INTERESTED, LeadState.EMAILED_2],
    LeadState.INTERESTED: [LeadState.CLOSED],
    LeadState.NOT_INTERESTED: [LeadState.CLOSED],
    LeadState.EMAILED_2: [LeadState.CLOSED],
    LeadState.CLOSED: [],  # Terminal state - no transitions allowed
}

# Maximum emails per lead
MAX_EMAILS_PER_LEAD = 2

# Max AI replies after certain states
MAX_AI_REPLIES_AFTER_INTEREST = 0
MAX_AI_REPLIES_AFTER_REFUSAL = 1


class StateMachineError(Exception):
    """Error raised for invalid state transitions."""
    pass


class LeadStateMachine:
    """
    State machine for managing lead lifecycle.
    
    States:
    - COLLECTED: Lead returned by Apify leads-finder
    - ENRICHED: LinkedIn post data added
    - EMAILED_1: First email sent, waiting for reply
    - INTERESTED: Positive reply received, human takeover
    - NOT_INTERESTED: Negative reply handled
    - EMAILED_2: Final follow-up sent, waiting for reply or closing
    - CLOSED: Terminal state
    
    Rules:
    - Max 2 emails per lead
    - 0 AI replies after interest (human takeover)
    - 1 AI reply after refusal (polite followup)
    - No loops or repeat transitions
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def can_transition(self, current_state: LeadState, target_state: LeadState) -> bool:
        """Check if a state transition is valid."""
        valid_targets = VALID_TRANSITIONS.get(current_state, [])
        return target_state in valid_targets
    
    async def transition(
        self,
        lead: Lead,
        target_state: LeadState,
        reason: Optional[str] = None,
    ) -> Lead:
        """
        Transition a lead to a new state.
        
        Args:
            lead: The lead to transition
            target_state: The target state
            reason: Optional reason for the transition
            
        Returns:
            Updated lead
            
        Raises:
            StateMachineError: If transition is invalid
        """
        if not self.can_transition(lead.state, target_state):
            raise StateMachineError(
                f"Invalid transition: {lead.state.value} -> {target_state.value}"
            )
        
        old_state = lead.state
        lead.state = target_state
        lead.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(lead)
        
        logger.info(
            f"Lead {lead.id} transitioned: {old_state.value} -> {target_state.value}"
            f" (reason: {reason})"
        )
        
        return lead
    
    async def process_collected(self, lead: Lead) -> Lead:
        """
        Process a COLLECTED lead (enrich with LinkedIn data).
        Transitions to ENRICHED.
        """
        if lead.state != LeadState.COLLECTED:
            raise StateMachineError(f"Lead must be COLLECTED, got {lead.state.value}")
        
        # Enrichment happens externally, this just marks it done
        return await self.transition(lead, LeadState.ENRICHED, "LinkedIn enrichment complete")
    
    async def process_enriched(self, lead: Lead) -> Lead:
        """
        Process an ENRICHED lead (send first email).
        Transitions to EMAILED_1.
        """
        if lead.state != LeadState.ENRICHED:
            raise StateMachineError(f"Lead must be ENRICHED, got {lead.state.value}")
        
        if lead.emails_sent_count >= MAX_EMAILS_PER_LEAD:
            raise StateMachineError("Max emails already sent")
        
        # Email sending happens externally, this marks it done
        lead.emails_sent_count = 1
        lead.last_email_at = datetime.utcnow()
        
        return await self.transition(lead, LeadState.EMAILED_1, "First email sent")
    
    async def handle_positive_reply(self, lead: Lead) -> Lead:
        """
        Handle a positive reply - transition to INTERESTED.
        This triggers human takeover.
        """
        if lead.state != LeadState.EMAILED_1:
            raise StateMachineError(f"Lead must be EMAILED_1, got {lead.state.value}")
        
        lead = await self.transition(lead, LeadState.INTERESTED, "Positive reply received")
        
        # Mark any email threads as requiring human
        threads = await self.db.execute(
            select(EmailThread).where(EmailThread.lead_id == lead.id)
        )
        for thread in threads.scalars():
            thread.requires_human = True
            thread.reply_sentiment = ReplySentiment.POSITIVE
        
        await self.db.commit()
        
        return lead
    
    async def handle_negative_reply(self, lead: Lead) -> Lead:
        """
        Handle a negative reply - transition to NOT_INTERESTED.
        One polite follow-up will be sent.
        """
        if lead.state != LeadState.EMAILED_1:
            raise StateMachineError(f"Lead must be EMAILED_1, got {lead.state.value}")
        
        return await self.transition(lead, LeadState.NOT_INTERESTED, "Negative reply received")
    
    async def handle_no_reply(self, lead: Lead) -> Lead:
        """
        Handle no reply after 14 days - send follow-up and transition to EMAILED_2.
        """
        if lead.state != LeadState.EMAILED_1:
            raise StateMachineError(f"Lead must be EMAILED_1, got {lead.state.value}")
        
        if lead.emails_sent_count >= MAX_EMAILS_PER_LEAD:
            # Already at max, go straight to closed
            return await self.transition(lead, LeadState.CLOSED, "Max emails reached")
        
        lead.emails_sent_count = 2
        lead.last_email_at = datetime.utcnow()
        
        return await self.transition(lead, LeadState.EMAILED_2, "No reply - follow-up sent")
    
    async def close_lead(self, lead: Lead, reason: str = "Process complete") -> Lead:
        """
        Close a lead - terminal state.
        """
        terminal_states = [LeadState.INTERESTED, LeadState.NOT_INTERESTED, LeadState.EMAILED_2]
        
        if lead.state not in terminal_states:
            raise StateMachineError(
                f"Can only close from terminal states, got {lead.state.value}"
            )
        
        return await self.transition(lead, LeadState.CLOSED, reason)
    
    def can_send_email(self, lead: Lead) -> tuple[bool, Optional[str]]:
        """
        Check if we can send an email to this lead.
        
        Returns:
            Tuple of (can_send, reason_if_not)
        """
        # Check max emails
        if lead.emails_sent_count >= MAX_EMAILS_PER_LEAD:
            return False, "Max emails (2) already sent"
        
        # Check state-specific rules
        if lead.state == LeadState.INTERESTED:
            return False, "Lead is INTERESTED - human takeover required"
        
        if lead.state == LeadState.CLOSED:
            return False, "Lead is CLOSED"
        
        if lead.state == LeadState.NOT_INTERESTED:
            # Can send one polite follow-up
            if lead.emails_sent_count >= 2:
                return False, "Polite follow-up already sent"
        
        return True, None
    
    def get_lead_status_summary(self, lead: Lead) -> Dict[str, Any]:
        """Get a summary of the lead's current status."""
        can_email, email_reason = self.can_send_email(lead)
        
        return {
            "state": lead.state.value,
            "emails_sent": lead.emails_sent_count,
            "max_emails": MAX_EMAILS_PER_LEAD,
            "can_send_email": can_email,
            "email_blocked_reason": email_reason,
            "is_terminal": lead.state == LeadState.CLOSED,
            "requires_human": lead.state == LeadState.INTERESTED,
        }


def get_state_machine(db: AsyncSession) -> LeadStateMachine:
    """Factory function to get state machine instance."""
    return LeadStateMachine(db)
