"""
Web scraping module for fetching and parsing web content.
Handles HTML parsing, link extraction, content aggregation, and simple
chapter-to-chapter navigation.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from auth import AuthHandler, create_default_auth_handler

logger = logging.getLogger(__name__)


class WebScraper:
    """Scrapes web content and extracts structured data."""

    def __init__(self, auth_handler: Optional[AuthHandler] = None, timeout: int = 10):
        self.auth = auth_handler or create_default_auth_handler()
        self.timeout = timeout
        self.session = requests.Session()
        self._visited_urls: Set[str] = set()

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a single web page."""
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(
                url,
                headers=self.auth.get_headers(),
                auth=self.auth.get_auth(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            logger.error(f"Failed to fetch {url}: {exc}")
            return None

    def fetch_binary(self, url: str) -> Optional[bytes]:
        """Fetch a binary asset such as a chapter image."""
        try:
            logger.info(f"Fetching binary: {url}")
            response = self.session.get(
                url,
                headers=self.auth.get_headers(),
                auth=self.auth.get_auth(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            logger.error(f"Failed to fetch binary {url}: {exc}")
            return None

    def parse_html(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content into BeautifulSoup object."""
        return BeautifulSoup(html_content, "html.parser")

    def extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.string or "Untitled"

        h1_tag = soup.find("h1")
        if h1_tag:
            return h1_tag.get_text(strip=True)

        return "Untitled"

    def extract_book_title(self, page_title: str) -> str:
        """Infer a broader book title from a chapter/page title."""
        cleaned = re.sub(
            r"\s*[-|:]\s*(chapter|ch\.?|episode|ep\.?|part)\s*\d+.*$",
            "",
            page_title,
            flags=re.IGNORECASE,
        ).strip()
        return cleaned or page_title or "Untitled"

    def extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from page."""
        for selector in [
            "main",
            "article",
            "div.content",
            "div.post",
            "div.entry-content",
            "div.chapter-content",
            "section.content",
        ]:
            content = soup.select_one(selector)
            if content:
                return content.get_text(separator="\n", strip=True)

        body = soup.find("body")
        if body:
            for element in body(["script", "style", "nav", "footer"]):
                element.decompose()
            return body.get_text(separator="\n", strip=True)

        return ""

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract same-domain links from page."""
        links = []
        for link in soup.find_all("a", href=True):
            url = urljoin(base_url, link["href"])
            if self._same_domain(base_url, url):
                links.append(url)
        return list(dict.fromkeys(links))

    def extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all image URLs from page."""
        images = []
        for img in soup.find_all("img", src=True):
            src = img["src"].strip()
            if not src or src.startswith("data:"):
                continue
            image_url = urljoin(base_url, src)
            if self._is_blocked_image_url(image_url):
                continue
            images.append(image_url)
        return list(dict.fromkeys(images))

    def extract_next_link(self, soup: BeautifulSoup, base_url: str, current_url: str) -> Optional[str]:
        """Find the most likely next-chapter link on a page."""
        keywords = (
            "next chapter",
            "next episode",
            "chapter next",
            "episode next",
            "read next",
            "continue",
            "following",
            "next",
            "다음화",
            "다음편",
            "다음",
            "계속",
            ">>",
            "»",
            ">",
        )

        best_match: Optional[Tuple[int, str]] = None
        for anchor in soup.find_all("a", href=True):
            candidate_url = urljoin(base_url, anchor["href"])
            if candidate_url == current_url or not self._same_domain(base_url, candidate_url):
                continue
            if self._is_blocked_navigation_url(candidate_url):
                continue

            score = self._score_next_candidate(anchor, current_url, candidate_url, keywords)
            if score <= 0:
                continue

            if best_match is None or score > best_match[0]:
                best_match = (score, candidate_url)

        return best_match[1] if best_match else None

    def scrape_chapter(self, url: str) -> Optional[Dict]:
        """Scrape a single chapter-like page with next-link inference."""
        html = self.fetch_page(url)
        if not html:
            return None

        soup = self.parse_html(html)
        title = self.extract_title(soup)
        return {
            "url": url,
            "title": title,
            "book_title": self.extract_book_title(title),
            "content": self.extract_content(soup),
            "links": self.extract_links(soup, url),
            "images": self.extract_images(soup, url),
            "next_url": self.extract_next_link(soup, url, url),
        }

    def scrape_url(self, url: str) -> Optional[Dict]:
        """Compatibility wrapper for generic scraping callers."""
        return self.scrape_chapter(url)

    def scrape_multiple(self, urls: List[str]) -> List[Dict]:
        """Scrape multiple URLs."""
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

    @staticmethod
    def _numeric_tokens(url: str) -> List[int]:
        """Extract numeric URL tokens for simple chapter sequencing heuristics."""
        return [int(token) for token in re.findall(r"\d+", url)]

    @staticmethod
    def _path_tokens(url: str) -> List[str]:
        """Extract lowercase path tokens from a URL."""
        return [token for token in re.split(r"[^a-z0-9]+", urlparse(url).path.lower()) if token]

    def _is_blocked_navigation_url(self, candidate_url: str) -> bool:
        """Reject obvious non-chapter navigation targets."""
        blocked_tokens = {
            "home",
            "index",
            "login",
            "register",
            "bookmark",
            "bookmarks",
            "comments",
            "comment",
            "reviews",
            "review",
            "characters",
            "character",
            "gallery",
            "news",
            "forum",
            "search",
            "list",
        }
        tokens = set(self._path_tokens(candidate_url))
        return bool(tokens & blocked_tokens)

    def _is_blocked_image_url(self, image_url: str) -> bool:
        """Reject tracking pixels, placeholders, and obvious non-content images."""
        parsed = urlparse(image_url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()

        blocked_hosts = {
            "www.facebook.com",
            "facebook.com",
            "connect.facebook.net",
            "google-analytics.com",
            "www.google-analytics.com",
        }
        if host in blocked_hosts:
            return True

        blocked_fragments = (
            "pixel",
            "tracker",
            "tracking",
            "spacer",
            "blank",
            "placeholder",
            "no_data",
            "no-data",
            "default-cover",
            "main_no_data",
        )
        return any(fragment in path for fragment in blocked_fragments)

    def is_probable_chapter_url(self, current_url: str, candidate_url: str) -> bool:
        """Check whether a candidate URL still looks like a chapter URL."""
        if not candidate_url or not self._same_domain(current_url, candidate_url):
            return False
        if self._is_blocked_navigation_url(candidate_url):
            return False

        current_tokens = self._path_tokens(current_url)
        candidate_tokens = self._path_tokens(candidate_url)
        chapter_markers = {"chapter", "chap", "ch", "episode", "ep", "part"}

        current_has_marker = any(token in chapter_markers for token in current_tokens)
        candidate_has_marker = any(token in chapter_markers for token in candidate_tokens)
        if current_has_marker and not candidate_has_marker:
            return False

        current_numbers = self._numeric_tokens(current_url)
        candidate_numbers = self._numeric_tokens(candidate_url)
        if current_numbers and candidate_numbers:
            for current_num, candidate_num in zip(current_numbers, candidate_numbers):
                if candidate_num > current_num:
                    return True

        shared_tokens = sum(1 for token in candidate_tokens if token in current_tokens)
        return shared_tokens >= max(2, len(current_tokens) // 2)

    def _score_next_candidate(
        self,
        anchor,
        current_url: str,
        candidate_url: str,
        keywords: Tuple[str, ...],
    ) -> int:
        """Score a candidate link as a likely next chapter."""
        score = 0

        rel_values = [value.lower() for value in anchor.get("rel", [])]
        if "next" in rel_values:
            score += 120

        text = " ".join(
            filter(
                None,
                [
                    anchor.get_text(" ", strip=True),
                    anchor.get("title"),
                    anchor.get("aria-label"),
                    " ".join(anchor.get("class", [])),
                    anchor.get("id"),
                ],
            )
        ).lower()

        for keyword in keywords:
            if keyword in text:
                score += 100 if len(keyword) > 1 else 30

        current_tokens = self._path_tokens(current_url)
        candidate_tokens = self._path_tokens(candidate_url)
        chapter_markers = {"chapter", "chap", "ch", "episode", "ep", "part"}
        current_has_marker = any(token in chapter_markers for token in current_tokens)
        candidate_has_marker = any(token in chapter_markers for token in candidate_tokens)

        if candidate_has_marker:
            score += 80
        if current_has_marker and candidate_has_marker:
            score += 40
        if current_has_marker and not candidate_has_marker:
            score -= 160

        shared_tokens = sum(1 for token in candidate_tokens if token in current_tokens)
        score += min(50, shared_tokens * 10)

        current_numbers = self._numeric_tokens(current_url)
        candidate_numbers = self._numeric_tokens(candidate_url)
        if current_numbers and candidate_numbers:
            for current_num, candidate_num in zip(current_numbers, candidate_numbers):
                difference = candidate_num - current_num
                if difference == 1:
                    score += 140
                    break
                if 1 < difference <= 3:
                    score += 35
                    break
                if difference <= 0:
                    score -= 40

        if urlparse(current_url).path != urlparse(candidate_url).path:
            score += 10

        return score

    def clear_visited(self) -> None:
        """Clear visited URLs cache."""
        self._visited_urls.clear()
