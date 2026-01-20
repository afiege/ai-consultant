"""Service for crawling websites and extracting company information."""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from urllib.parse import urlparse


class WebCrawler:
    """Crawl websites and extract company information."""

    USER_AGENT = 'Mozilla/5.0 (compatible; AI-Consultant-Bot/1.0)'
    TIMEOUT = 30  # seconds

    @staticmethod
    def validate_url(url: str) -> tuple[bool, str]:
        """
        Validate URL format.

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
            # Fetch page
            headers = {'User-Agent': WebCrawler.USER_AGENT}
            response = requests.get(url, headers=headers, timeout=WebCrawler.TIMEOUT)
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
