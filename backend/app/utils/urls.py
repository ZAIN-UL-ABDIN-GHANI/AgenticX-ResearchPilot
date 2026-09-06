"""
URL validation and SSRF prevention utilities.
"""

import ipaddress
from urllib.parse import urlparse
from app.core.logging import get_logger

logger = get_logger(__name__)


def is_safe_url(url: str) -> bool:
    """
    Check if URL is safe to fetch (SSRF prevention).
    
    Blocks:
    - Localhost (127.0.0.1, ::1)
    - Private IPs (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Link-local IPs (169.254.0.0/16)
    - Reserved IPs
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return False
        
        # Check for localhost
        if hostname in ("localhost", "127.0.0.1", "::1", "[::1]"):
            return False
        
        # Check for private/reserved IPs
        try:
            ip = ipaddress.ip_address(hostname)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                return False
        except ValueError:
            # Not an IP, assume it's safe
            pass
        
        # Check scheme
        if parsed.scheme not in ("http", "https"):
            return False
        
        return True
    
    except Exception as exc:
        logger.error(f"Error checking URL safety: {str(exc)}")
        return False


def normalize_url(url: str) -> str:
    """Normalize URL for consistent comparison."""
    return url.strip().lower()


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""
