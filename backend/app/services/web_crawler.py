"""Service for crawling websites and extracting company information."""

import requests
import socket
import ipaddress
import logging
from bs4 import BeautifulSoup
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Private/internal IP ranges that should be blocked (SSRF protection)
BLOCKED_IP_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),       # Loopback
    ipaddress.ip_network('10.0.0.0/8'),        # Private Class A
    ipaddress.ip_network('172.16.0.0/12'),     # Private Class B
    ipaddress.ip_network('192.168.0.0/16'),    # Private Class C
    ipaddress.ip_network('169.254.0.0/16'),    # Link-local
    ipaddress.ip_network('0.0.0.0/8'),         # "This" network
    ipaddress.ip_network('100.64.0.0/10'),     # Shared address space (CGNAT)
    ipaddress.ip_network('198.18.0.0/15'),     # Benchmark testing
    ipaddress.ip_network('224.0.0.0/4'),       # Multicast
    ipaddress.ip_network('240.0.0.0/4'),       # Reserved for future use
    ipaddress.ip_network('::1/128'),           # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),          # IPv6 unique local
    ipaddress.ip_network('fe80::/10'),         # IPv6 link-local
]

# Blocked hostnames
BLOCKED_HOSTNAMES = [
    'localhost',
    'localhost.localdomain',
    'ip6-localhost',
    'ip6-loopback',
]


class WebCrawler:
    """Crawl websites and extract company information."""

    USER_AGENT = 'Mozilla/5.0 (compatible; AI-Consultant-Bot/1.0)'
    TIMEOUT = 30  # seconds

    @staticmethod
    def _is_ip_blocked(ip_str: str) -> bool:
        """Check if an IP address is in a blocked range (SSRF protection)."""
        try:
            ip = ipaddress.ip_address(ip_str)
            for blocked_range in BLOCKED_IP_RANGES:
                if ip in blocked_range:
                    return True
            return False
        except ValueError:
            # Invalid IP address format
            return True  # Block by default if we can't parse

    @staticmethod
    def _resolve_and_validate_host(hostname: str) -> Tuple[bool, str]:
        """
        Resolve hostname to IP and validate it's not internal (SSRF protection).

        Args:
            hostname: The hostname to resolve and validate

        Returns:
            Tuple of (is_safe, error_message)
        """
        # Check blocked hostnames
        hostname_lower = hostname.lower()
        if hostname_lower in BLOCKED_HOSTNAMES:
            return False, f"Access to '{hostname}' is blocked for security reasons"

        try:
            # Resolve hostname to IP addresses
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                if WebCrawler._is_ip_blocked(ip_str):
                    logger.warning(f"SSRF protection: Blocked request to internal IP {ip_str} for host {hostname}")
                    return False, f"Access to internal network addresses is blocked for security reasons"

            return True, ""

        except socket.gaierror as e:
            return False, f"Could not resolve hostname: {str(e)}"
        except Exception as e:
            logger.error(f"Error validating host {hostname}: {e}")
            return False, f"Error validating hostname: {str(e)}"

    @staticmethod
    def validate_url(url: str) -> Tuple[bool, str]:
        """
        Validate URL format and check for SSRF vulnerabilities.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return False, "Invalid URL format"

            if result.scheme not in ['http', 'https']:
                return False, "Only HTTP and HTTPS URLs are supported"

            # Extract hostname (remove port if present)
            hostname = result.netloc.split(':')[0]

            # Check if hostname is an IP address directly
            try:
                if WebCrawler._is_ip_blocked(hostname):
                    return False, "Access to internal network addresses is blocked for security reasons"
            except ValueError:
                # Not an IP address, it's a hostname - will be validated during DNS resolution
                pass

            # Resolve hostname and validate IP addresses (SSRF protection)
            is_safe, error_msg = WebCrawler._resolve_and_validate_host(hostname)
            if not is_safe:
                return False, error_msg

            return True, ""
        except Exception as e:
            return False, f"Invalid URL: {str(e)}"

    @staticmethod
    def crawl_website(url: str) -> Dict[str, Optional[str]]:
        """
        Crawl website and extract company information.

        Args:
            url: Website URL to crawl

        Returns:
            Dictionary with extracted information:
            {
                'title': Page title,
                'description': Meta description,
                'main_content': Main text content,
                'headings': All headings (H1-H3)
            }
        """
        # Validate URL
        is_valid, error_msg = WebCrawler.validate_url(url)
        if not is_valid:
            raise ValueError(error_msg)

        try:
            # Fetch page with redirect handling for SSRF protection
            headers = {'User-Agent': WebCrawler.USER_AGENT}

            # Make request without following redirects initially
            session = requests.Session()
            response = session.get(
                url,
                headers=headers,
                timeout=WebCrawler.TIMEOUT,
                allow_redirects=False
            )

            # Manually follow redirects with SSRF validation
            redirect_count = 0
            max_redirects = 5

            while response.is_redirect and redirect_count < max_redirects:
                redirect_url = response.headers.get('Location')
                if not redirect_url:
                    break

                # Handle relative redirects
                if not redirect_url.startswith(('http://', 'https://')):
                    parsed_original = urlparse(url)
                    redirect_url = f"{parsed_original.scheme}://{parsed_original.netloc}{redirect_url}"

                # Validate redirect URL for SSRF
                is_valid, error_msg = WebCrawler.validate_url(redirect_url)
                if not is_valid:
                    logger.warning(f"SSRF protection: Blocked redirect to {redirect_url}: {error_msg}")
                    raise ValueError(f"Redirect blocked for security reasons: {error_msg}")

                # Follow redirect
                response = session.get(
                    redirect_url,
                    headers=headers,
                    timeout=WebCrawler.TIMEOUT,
                    allow_redirects=False
                )
                redirect_count += 1

            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title = None
            if soup.title:
                title = soup.title.string.strip() if soup.title.string else None

            # Extract meta description
            description = None
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description = meta_desc['content'].strip()

            # Extract headings (H1-H3)
            headings = []
            for tag in ['h1', 'h2', 'h3']:
                for heading in soup.find_all(tag):
                    text = heading.get_text().strip()
                    if text:
                        headings.append(f"{tag.upper()}: {text}")

            # Extract main content
            # Remove script and style elements
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()

            # Get text from body
            main_content = []
            if soup.body:
                # Get paragraphs
                for p in soup.body.find_all('p'):
                    text = p.get_text().strip()
                    if text and len(text) > 20:  # Filter out very short paragraphs
                        main_content.append(text)

            # Limit content length
            combined_content = "\n\n".join(main_content[:20])  # First 20 paragraphs
            if len(combined_content) > 5000:
                combined_content = combined_content[:5000] + "..."

            return {
                'title': title,
                'description': description,
                'main_content': combined_content,
                'headings': "\n".join(headings[:15])  # First 15 headings
            }

        except requests.Timeout:
            raise Exception(f"Request timeout: Website took longer than {WebCrawler.TIMEOUT} seconds to respond")
        except requests.RequestException as e:
            raise Exception(f"Error fetching website: {str(e)}")
        except Exception as e:
            raise Exception(f"Error crawling website: {str(e)}")

    @staticmethod
    def format_extracted_info(crawled_data: Dict[str, Optional[str]]) -> str:
        """
        Format extracted information into readable text.

        Args:
            crawled_data: Dictionary from crawl_website()

        Returns:
            Formatted text content
        """
        sections = []

        if crawled_data.get('title'):
            sections.append(f"Page Title: {crawled_data['title']}")

        if crawled_data.get('description'):
            sections.append(f"Description: {crawled_data['description']}")

        if crawled_data.get('headings'):
            sections.append(f"Key Sections:\n{crawled_data['headings']}")

        if crawled_data.get('main_content'):
            sections.append(f"Main Content:\n{crawled_data['main_content']}")

        return "\n\n".join(sections)
