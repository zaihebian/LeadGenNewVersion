"""Gmail API service with OAuth2 and rate limiting."""

import base64
import json
import logging
import asyncio
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import get_settings

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


class RateLimiter:
    """Simple rate limiter for Gmail API calls."""
    
    def __init__(self, max_per_day: int, min_interval_seconds: int):
        self.max_per_day = max_per_day
        self.min_interval = timedelta(seconds=min_interval_seconds)
        self.daily_count = 0
        self.last_send_time: Optional[datetime] = None
        self.day_start: datetime = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _reset_if_new_day(self):
        """Reset counter if it's a new day."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if today > self.day_start:
            self.daily_count = 0
            self.day_start = today
    
    def can_send(self) -> tuple[bool, Optional[str]]:
        """Check if we can send an email now."""
        self._reset_if_new_day()
        
        if self.daily_count >= self.max_per_day:
            return False, f"Daily limit reached ({self.max_per_day} emails/day)"
        
        if self.last_send_time:
            time_since_last = datetime.utcnow() - self.last_send_time
            if time_since_last < self.min_interval:
                wait_time = (self.min_interval - time_since_last).seconds
                return False, f"Rate limit: wait {wait_time} seconds"
        
        return True, None
    
    def record_send(self):
        """Record that an email was sent."""
        self.daily_count += 1
        self.last_send_time = datetime.utcnow()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limit stats."""
        self._reset_if_new_day()
        return {
            "daily_sent": self.daily_count,
            "daily_limit": self.max_per_day,
            "remaining": self.max_per_day - self.daily_count,
            "can_send_now": self.can_send()[0],
        }


class GmailService:
    """Service for Gmail API interactions."""
    
    def __init__(self):
        self.settings = get_settings()
        self.credentials: Optional[Credentials] = None
        self.rate_limiter = RateLimiter(
            max_per_day=self.settings.max_emails_per_day,
            min_interval_seconds=self.settings.min_email_interval_seconds,
        )
        self._credentials_store: Dict[str, Any] = {}
        self._user_email: Optional[str] = None
    
    def get_oauth_flow(self) -> Flow:
        """Create OAuth2 flow for Gmail authorization."""
        client_config = {
            "web": {
                "client_id": self.settings.gmail_client_id,
                "client_secret": self.settings.gmail_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.settings.gmail_redirect_uri],
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=self.settings.gmail_redirect_uri,
        )
        
        return flow
    
    def get_authorization_url(self) -> str:
        """Get the OAuth2 authorization URL."""
        flow = self.get_oauth_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url
    
    async def handle_oauth_callback(self, authorization_code: str) -> Dict[str, Any]:
        """
        Handle OAuth2 callback and store credentials.
        
        Args:
            authorization_code: The authorization code from Google
            
        Returns:
            Dict with success status and user email
        """
        try:
            flow = self.get_oauth_flow()
            flow.fetch_token(code=authorization_code)
            
            self.credentials = flow.credentials
            
            # Store credentials
            self._credentials_store = {
                "token": self.credentials.token,
                "refresh_token": self.credentials.refresh_token,
                "token_uri": self.credentials.token_uri,
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
                "scopes": list(self.credentials.scopes),
            }
            
            # Get user email
            service = build("gmail", "v1", credentials=self.credentials)
            profile = service.users().getProfile(userId="me").execute()
            user_email = profile.get("emailAddress")
            
            # Store user email for reply detection
            self._user_email = user_email
            
            return {
                "success": True,
                "email": user_email,
            }
            
        except Exception as e:
            logger.error(f"OAuth callback error: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_credentials(self) -> Optional[Credentials]:
        """Get valid credentials, refreshing if needed."""
        if not self._credentials_store:
            return None
        
        credentials = Credentials(
            token=self._credentials_store.get("token"),
            refresh_token=self._credentials_store.get("refresh_token"),
            token_uri=self._credentials_store.get("token_uri"),
            client_id=self._credentials_store.get("client_id"),
            client_secret=self._credentials_store.get("client_secret"),
            scopes=self._credentials_store.get("scopes"),
        )
        
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                self._credentials_store["token"] = credentials.token
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                return None
        
        return credentials
    
    def is_authenticated(self) -> bool:
        """Check if Gmail is authenticated."""
        creds = self._get_credentials()
        return creds is not None and creds.valid
    
    async def get_authenticated_user_email(self) -> Optional[str]:
        """
        Get the authenticated user's email address.
        
        Returns:
            User email if authenticated, None otherwise
        """
        if self._user_email:
            return self._user_email
        
        credentials = self._get_credentials()
        if not credentials:
            return None
        
        try:
            service = build("gmail", "v1", credentials=credentials)
            profile = service.users().getProfile(userId="me").execute()
            user_email = profile.get("emailAddress")
            self._user_email = user_email
            return user_email
        except Exception as e:
            logger.error(f"Failed to get user email: {e}")
            return None
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email via Gmail API.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            thread_id: Optional Gmail thread ID for replies
            
        Returns:
            Dict with success status and message info
        """
        # Check rate limit
        can_send, reason = self.rate_limiter.can_send()
        if not can_send:
            return {"success": False, "error": reason}
        
        credentials = self._get_credentials()
        if not credentials:
            return {"success": False, "error": "Not authenticated with Gmail"}
        
        try:
            service = build("gmail", "v1", credentials=credentials)
            
            # Create message
            message = MIMEText(body)
            message["to"] = to_email
            message["subject"] = subject
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            
            body_data = {"raw": raw_message}
            if thread_id:
                body_data["threadId"] = thread_id
            
            # Send message
            result = service.users().messages().send(
                userId="me",
                body=body_data,
            ).execute()
            
            # Record successful send
            self.rate_limiter.record_send()
            
            logger.info(f"Sent email to {to_email}, message ID: {result.get('id')}")
            
            return {
                "success": True,
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_thread_messages(self, thread_id: str) -> Dict[str, Any]:
        """
        Get all messages in a Gmail thread.
        
        Args:
            thread_id: Gmail thread ID
            
        Returns:
            Dict with messages list
        """
        credentials = self._get_credentials()
        if not credentials:
            return {"success": False, "error": "Not authenticated"}
        
        try:
            service = build("gmail", "v1", credentials=credentials)
            
            thread = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="full",
            ).execute()
            
            messages = []
            for msg in thread.get("messages", []):
                # Parse message
                headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
                
                # Get body
                body = self._extract_body(msg["payload"])
                
                messages.append({
                    "id": msg["id"],
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "body": body,
                    "is_sent": "SENT" in msg.get("labelIds", []),
                })
            
            # Include user email for reply detection
            user_email = await self.get_authenticated_user_email()
            
            return {
                "success": True,
                "messages": messages,
                "user_email": user_email,
            }
            
        except Exception as e:
            logger.error(f"Failed to get thread: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_for_replies(self, thread_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Check multiple threads for new replies.
        
        Args:
            thread_ids: List of Gmail thread IDs to check
            
        Returns:
            List of threads with new replies
        """
        credentials = self._get_credentials()
        if not credentials:
            return []
        
        replies = []
        service = build("gmail", "v1", credentials=credentials)
        
        for thread_id in thread_ids:
            try:
                thread = service.users().threads().get(
                    userId="me",
                    id=thread_id,
                    format="full",
                ).execute()
                
                messages = thread.get("messages", [])
                
                # Check if there are received messages (not sent by us)
                for msg in messages:
                    labels = msg.get("labelIds", [])
                    if "INBOX" in labels and "SENT" not in labels:
                        # This is a received message
                        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
                        body = self._extract_body(msg["payload"])
                        
                        replies.append({
                            "thread_id": thread_id,
                            "message_id": msg["id"],
                            "from": headers.get("From", ""),
                            "subject": headers.get("Subject", ""),
                            "body": body,
                            "date": headers.get("Date", ""),
                        })
                        
            except Exception as e:
                logger.error(f"Error checking thread {thread_id}: {e}")
                continue
        
        return replies
    
    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Extract plain text body from message payload."""
        if "body" in payload and payload["body"].get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    if part["body"].get("data"):
                        return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                elif "parts" in part:
                    # Nested multipart
                    result = self._extract_body(part)
                    if result:
                        return result
        
        return ""
    
    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get current rate limiting statistics."""
        return self.rate_limiter.get_stats()


# Singleton instance
gmail_service = GmailService()
