"""
Main entry point for epubsteel.
Provides CLI interface for web scraping and EPUB generation.
"""

import logging
import sys
import argparse
from typing import List, Optional
from scraper import WebScraper
from epub_generator import EPUBGenerator
from auth import AuthHandler, create_default_auth_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EPUBSteel:
    """Main application class for epubsteel."""
    
    def __init__(self, dry_run: bool = False, verbose: bool = False):
        """
        Initialize EPUBSteel application.
        
        Args:
            dry_run: If True, don't save files, only show what would happen
            verbose: Enable verbose logging
        """
        self.dry_run = dry_run
        self.verbose = verbose
        self.auth = create_default_auth_handler()
        self.scraper = WebScraper(self.auth)
        
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def add_auth_user_agent(self, user_agent: str) -> None:
        """Add custom User-Agent header."""
        self.auth.set_user_agent(user_agent)
        self.scraper = WebScraper(self.auth)
    
    def add_basic_auth(self, username: str, password: str) -> None:
        """Add basic authentication."""
        self.auth.set_basic_auth(username, password)
        self.scraper = WebScraper(self.auth)
    
    def add_bearer_token(self, token: str) -> None:
        """Add bearer token authentication."""
        self.auth.set_bearer_token(token)
        self.scraper = WebScraper(self.auth)
    
    def scrape_to_epub(
        self,
        urls: List[str],
        output_file: str,
        title: str,
        author: str = "Unknown",
        follow_links: bool = False
    ) -> bool:
        """
        Scrape URLs and generate EPUB.
        
        Args:
            urls: List of URLs to scrape
            output_file: Output EPUB file path
            title: Book title
            author: Book author
            follow_links: If True, follow links found on pages
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Starting scraping: {len(urls)} URL(s)")
            
            # Scrape initial URLs
            to_scrape = urls.copy()
            scraped_data = []
            
            while to_scrape:
                url = to_scrape.pop(0)
                logger.info(f"Scraping: {url}")
                
                data = self.scraper.scrape_url(url)
                if data:
                    scraped_data.append(data)
                    
                    # Follow links if enabled
                    if follow_links:
                        new_links = [
                            link for link in data.get('links', [])
                            if link not in self.scraper._visited_urls
                        ]
                        to_scrape.extend(new_links[:5])  # Limit to 5 new links
            
            if not scraped_data:
                logger.error("No content scraped")
                return False
            
            logger.info(f"Scraped {len(scraped_data)} page(s)")
            
            # Generate EPUB
            logger.info(f"Generating EPUB: {title}")
            epub_gen = EPUBGenerator(title=title, author=author)
            
            for data in scraped_data:
                chapter_title = data.get('title', 'Untitled')
                chapter_content = data.get('content', '')
                
                if chapter_content:
                    epub_gen.add_chapter_from_text(chapter_title, chapter_content)
            
            # Save EPUB
            if self.dry_run:
                logger.info(f"[DRY RUN] Would save EPUB to: {output_file}")
                logger.info(f"[DRY RUN] Book info: {epub_gen.get_info()}")
                return True
            else:
                success = epub_gen.save(output_file)
                if success:
                    logger.info(f"✓ EPUB created: {output_file}")
                return success
        
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            return False
    
    def scrape_single_url(self, url: str) -> Optional[dict]:
        """
        Scrape a single URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            Scraped data dictionary or None
        """
        logger.info(f"Scraping: {url}")
        return self.scraper.scrape_url(url)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='epubsteel - Convert web content to EPUB eBooks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py -u https://example.com -o book.epub -t "My Book"
  python main.py -u https://example.com https://example.com/page2 -o output.epub -t "Title" -a "Author"
  python main.py -u https://example.com -o book.epub -t "Book" --follow-links --dry-run
        """
    )
    
    parser.add_argument(
        '-u', '--url',
        nargs='+',
        required=True,
        help='URL(s) to scrape'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output EPUB file path'
    )
    
    parser.add_argument(
        '-t', '--title',
        required=True,
        help='Book title'
    )
    
    parser.add_argument(
        '-a', '--author',
        default='Unknown',
        help='Book author (default: Unknown)'
    )
    
    parser.add_argument(
        '--follow-links',
        action='store_true',
        help='Follow links found on pages'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without saving files'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--user-agent',
        help='Custom User-Agent header'
    )
    
    parser.add_argument(
        '--username',
        help='Username for basic authentication'
    )
    
    parser.add_argument(
        '--password',
        help='Password for basic authentication'
    )
    
    parser.add_argument(
        '--bearer-token',
        help='Bearer token for authentication'
    )
    
    args = parser.parse_args()
    
    # Create application instance
    app = EPUBSteel(dry_run=args.dry_run, verbose=args.verbose)
    
    # Configure authentication
    if args.user_agent:
        app.add_auth_user_agent(args.user_agent)
    
    if args.username and args.password:
        app.add_basic_auth(args.username, args.password)
    elif args.bearer_token:
        app.add_bearer_token(args.bearer_token)
    
    # Execute scraping and EPUB generation
    success = app.scrape_to_epub(
        urls=args.url,
        output_file=args.output,
        title=args.title,
        author=args.author,
        follow_links=args.follow_links
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
