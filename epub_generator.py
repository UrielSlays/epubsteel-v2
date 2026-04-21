"""
EPUB generation module for creating eBook files.
Handles metadata, content formatting, and EPUB file creation.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from ebooklib import epub
import os

logger = logging.getLogger(__name__)


class EPUBGenerator:
    """Generates EPUB eBook files from scraped content."""
    
    def __init__(self, title: str = "Untitled", author: str = "Unknown"):
        """
        Initialize EPUB generator.
        
        Args:
            title: Book title
            author: Book author
        """
        self.title = title
        self.author = author
        self.book = epub.EpubBook()
        self.chapters: List[epub.EpubHtml] = []
        self._setup_book()
    
    def _setup_book(self) -> None:
        """Set up basic book properties."""
        self.book.set_identifier(f'epubsteel_{datetime.now().timestamp()}')
        self.book.set_title(self.title)
        self.book.add_author(self.author)
        self.book.set_language('en')
    
    def set_metadata(self, key: str, value: str) -> None:
        """
        Set custom metadata.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        logger.debug(f"Setting metadata: {key} = {value}")
        # Add custom metadata if supported
        if key == 'description':
            self.book.add_metadata('DC', 'description', value)
        elif key == 'rights':
            self.book.add_metadata('DC', 'rights', value)
    
    def add_chapter(self, title: str, content: str) -> None:
        """
        Add a chapter to the book.
        
        Args:
            title: Chapter title
            content: Chapter HTML content
        """
        chapter = epub.EpubHtml()
        chapter.set_id(f'chapter_{len(self.chapters)}')
        chapter.set_title(title)
        chapter.content = self._format_content(content)
        
        self.chapters.append(chapter)
        self.book.add_item(chapter)
        logger.info(f"Added chapter: {title}")
    
    def add_chapter_from_text(self, title: str, text: str) -> None:
        """
        Add a chapter from plain text.
        
        Args:
            title: Chapter title
            text: Plain text content
        """
        html_content = self._text_to_html(text)
        self.add_chapter(title, html_content)
    
    @staticmethod
    def _format_content(content: str) -> str:
        """
        Format content for EPUB.
        
        Args:
            content: Raw HTML content
            
        Returns:
            Formatted HTML content
        """
        # Wrap content in basic HTML structure if needed
        if not content.startswith('<'):
            content = f'<p>{content}</p>'
        
        return f"""
        <html>
        <head>
            <meta charset="utf-8"/>
        </head>
        <body>
            {content}
        </body>
        </html>
        """
    
    @staticmethod
    def _text_to_html(text: str) -> str:
        """
        Convert plain text to HTML.
        
        Args:
            text: Plain text content
            
        Returns:
            HTML content
        """
        # Split text into paragraphs and wrap in <p> tags
        paragraphs = text.split('\n\n')
        html_paragraphs = [f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()]
        return '\n'.join(html_paragraphs)
    
    def add_cover_image(self, image_path: str) -> None:
        """
        Add a cover image to the book.
        
        Args:
            image_path: Path to cover image file
        """
        if not os.path.exists(image_path):
            logger.warning(f"Cover image not found: {image_path}")
            return
        
        try:
            with open(image_path, 'rb') as img_file:
                image_data = img_file.read()
            
            image_name = os.path.basename(image_path)
            item = epub.EpubImage()
            item.set_filename(f'images/{image_name}')
            item.set_content(image_data)
            
            self.book.add_item(item)
            logger.info(f"Added cover image: {image_name}")
        except Exception as e:
            logger.error(f"Failed to add cover image: {e}")
    
    def add_css(self, css_content: str) -> None:
        """
        Add CSS stylesheet to book.
        
        Args:
            css_content: CSS content
        """
        style = epub.EpubItem()
        style.set_id('style_default')
        style.set_filename('style/default.css')
        style.set_content(css_content)
        
        self.book.add_item(style)
        logger.info("Added CSS stylesheet")
    
    def create_table_of_contents(self) -> None:
        """Create and add table of contents."""
        if not self.chapters:
            logger.warning("No chapters to create table of contents")
            return
        
        self.book.toc = tuple(self.chapters)
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        
        # Define Table of Contents
        self.book.spine = ['nav'] + self.chapters
        logger.info("Table of contents created")
    
    def save(self, filepath: str) -> bool:
        """
        Save EPUB file.
        
        Args:
            filepath: Output file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure we have content
            if not self.chapters:
                logger.warning("No chapters in book, adding placeholder")
                self.add_chapter_from_text("Empty Book", "This book contains no content.")
            
            # Create TOC if needed
            if not self.book.toc:
                self.create_table_of_contents()
            
            # Create output directory if needed
            output_dir = os.path.dirname(filepath)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            epub.write_epub(filepath, self.book, {})
            logger.info(f"EPUB saved: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save EPUB: {e}")
            return False
    
    def get_info(self) -> Dict[str, str]:
        """
        Get book information.
        
        Returns:
            Dictionary with book metadata
        """
        return {
            'title': self.title,
            'author': self.author,
            'chapters': len(self.chapters),
            'identifier': self.book.get_identifier()
        }
