"""
Web scraping module for fetching and parsing web content.
Handles HTML parsing, link extraction, and content aggregation.
"""

import logging
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from auth import AuthHandler, create_default_auth_handler

logger = logging.getLogger(__name__)


class WebScraper:
    """Scrapes web content and extracts structured data."""
    
    def __init__(self, auth_handler: Optional[AuthHandler] = None, timeout: int = 10):
        """
        Initialize the web scraper.
        
        Args:
            auth_handler: AuthHandler instance for authentication
            timeout: Request timeout in seconds
        """
        self.auth = auth_handler or create_default_auth_handler()
        self.timeout = timeout
        self.session = requests.Session()
        self._visited_urls: Set[str] = set()
    
    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a single web page.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content or None if fetch fails
        """
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(
                url,
                headers=self.auth.get_headers(),
                auth=self.auth.get_auth(),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def parse_html(self, html_content: str) -> BeautifulSoup:
        """
        Parse HTML content into BeautifulSoup object.
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html_content, 'html.parser')
    
    def extract_title(self, soup: BeautifulSoup) -> str:
        """
        Extract page title.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Page title
        """
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.string or "Untitled"
        
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text(strip=True)
        
        return "Untitled"
    
    def extract_content(self, soup: BeautifulSoup) -> str:
        """
        Extract main content from page.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Main content text
        """
        # Try common content containers
        for selector in ['main', 'article', 'div.content', 'div.post']:
            content = soup.select_one(selector)
            if content:
                return content.get_text(separator='\n', strip=True)
        
        # Fallback to body
        body = soup.find('body')
        if body:
            # Remove script and style elements
            for element in body(['script', 'style', 'nav', 'footer']):
                element.decompose()
            return body.get_text(separator='\n', strip=True)
        
        return ""
    
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract all links from page.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for relative link resolution
            
        Returns:
            List of absolute URLs
        """
        links = []
        for link in soup.find_all('a', href=True):
            url = urljoin(base_url, link['href'])
            # Only include links from same domain
            if self._same_domain(base_url, url):
                links.append(url)
        return list(set(links))
    
    def extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract all image URLs from page.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for relative link resolution
            
        Returns:
            List of absolute image URLs
        """
        images = []
        for img in soup.find_all('img', src=True):
            url = urljoin(base_url, img['src'])
            images.append(url)
        return images
    
    def scrape_url(self, url: str) -> Optional[Dict]:
        """
        Scrape a single URL and extract all content.
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary with extracted data or None
        """
        html = self.fetch_page(url)
        if not html:
            return None
        
        soup = self.parse_html(html)
        
        return {
            'url': url,
            'title': self.extract_title(soup),
            'content': self.extract_content(soup),
            'links': self.extract_links(soup, url),
            'images': self.extract_images(soup, url)
        }
    
    def scrape_multiple(self, urls: List[str]) -> List[Dict]:
        """
        Scrape multiple URLs.
        
        Args:
            urls: List of URLs to scrape
            
        Returns:
            List of scraped data dictionaries
        """
        results = []
        for url in urls:
            if url not in self._visited_urls:
                data = self.scrape_url(url)
                if data:
                    results.append(data)
                    self._visited_urls.add(url)
        return results
    
    @staticmethod
    def _same_domain(url1: str, url2: str) -> bool:
        """Check if two URLs belong to the same domain."""
        return urlparse(url1).netloc == urlparse(url2).netloc
    
    def clear_visited(self) -> None:
        """Clear visited URLs cache."""
        self._visited_urls.clear()
