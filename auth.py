"""
Authentication module for handling HTTP authentication.
Supports basic auth, bearer tokens, and custom headers.
"""

import base64
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AuthHandler:
    """Handles various authentication methods for web scraping."""
    
    def __init__(self):
        """Initialize the authentication handler."""
        self.headers: Dict[str, str] = {}
        self.auth: Optional[Tuple[str, str]] = None
    
    def set_basic_auth(self, username: str, password: str) -> None:
        """
        Set basic HTTP authentication.
        
        Args:
            username: Username for authentication
            password: Password for authentication
        """
        self.auth = (username, password)
        logger.debug(f"Basic auth configured for user: {username}")
    
    def set_bearer_token(self, token: str) -> None:
        """
        Set bearer token authentication.
        
        Args:
            token: Bearer token string
        """
        self.headers['Authorization'] = f'Bearer {token}'
        logger.debug("Bearer token configured")
    
    def add_custom_header(self, key: str, value: str) -> None:
        """
        Add a custom HTTP header.
        
        Args:
            key: Header name
            value: Header value
        """
        self.headers[key] = value
        logger.debug(f"Custom header added: {key}")
    
    def set_user_agent(self, user_agent: str) -> None:
        """
        Set custom User-Agent header.
        
        Args:
            user_agent: User-Agent string
        """
        self.add_custom_header('User-Agent', user_agent)
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get all configured headers.
        
        Returns:
            Dictionary of headers
        """
        return self.headers.copy()
    
    def get_auth(self) -> Optional[Tuple[str, str]]:
        """
        Get basic auth credentials.
        
        Returns:
            Tuple of (username, password) or None
        """
        return self.auth
    
    def clear(self) -> None:
        """Clear all authentication settings."""
        self.headers.clear()
        self.auth = None
        logger.debug("Authentication cleared")


def create_default_auth_handler() -> AuthHandler:
    """
    Create an AuthHandler with default settings.
    
    Returns:
        Configured AuthHandler instance
    """
    handler = AuthHandler()
    handler.set_user_agent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    return handler
