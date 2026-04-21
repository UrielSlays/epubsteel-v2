"""
Simple PDF generation from chapter text using Pillow.
"""

from __future__ import annotations

import os
import textwrap
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont


class PDFGenerator:
    """Generate a basic multi-page PDF without external PDF libraries."""

    def __init__(self, title: str = "Untitled", author: str = "Unknown") -> None:
        self.title = title
        self.author = author
        self.chapters: List[Dict[str, str]] = []
        self.page_width = 1240
        self.page_height = 1754
        self.margin = 90
        self.body_font = ImageFont.load_default()
        self.title_font = ImageFont.load_default()
        self.line_height = 24

    def add_chapter(self, title: str, text: str) -> None:
        self.chapters.append({"title": title, "text": text})

    def save(self, filepath: str) -> bool:
        if not self.chapters:
            self.add_chapter("Empty Book", "This book contains no content.")

        pages = self._render_pages()
        output_dir = os.path.dirname(filepath)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        first_page, rest = pages[0], pages[1:]
        first_page.save(filepath, save_all=True, append_images=rest, resolution=100.0)
        return True

    def _render_pages(self) -> List[Image.Image]:
        pages: List[Image.Image] = []
        image, draw, y_position = self._new_page()

        for chapter_index, chapter in enumerate(self.chapters, start=1):
            chapter_lines = self._wrap_text(f"{chapter_index:03d} {chapter['title']}", draw, heading=True)
            body_lines: List[str] = []
            for paragraph in chapter["text"].splitlines():
                if not paragraph.strip():
                    body_lines.append("")
                    continue
                body_lines.extend(self._wrap_text(paragraph.strip(), draw, heading=False))

            required_lines = len(chapter_lines) + len(body_lines) + 4
            available_lines = int((self.page_height - self.margin - y_position) / self.line_height)
            if required_lines > available_lines and y_position > self.margin:
                pages.append(image)
                image, draw, y_position = self._new_page()

            for line in chapter_lines:
                draw.text((self.margin, y_position), line, fill="black", font=self.title_font)
                y_position += self.line_height
            y_position += self.line_height

            for line in body_lines:
                if y_position > self.page_height - self.margin - self.line_height:
                    pages.append(image)
                    image, draw, y_position = self._new_page()
                draw.text((self.margin, y_position), line, fill="black", font=self.body_font)
                y_position += self.line_height
            y_position += self.line_height * 2

        pages.append(image)
        return pages

    def _new_page(self):
        image = Image.new("RGB", (self.page_width, self.page_height), "white")
        draw = ImageDraw.Draw(image)
        y_position = self.margin

        for line in self._wrap_text(self.title, draw, heading=True):
            draw.text((self.margin, y_position), line, fill="black", font=self.title_font)
            y_position += self.line_height

        y_position += self.line_height
        return image, draw, y_position

    def _wrap_text(self, text: str, draw: ImageDraw.ImageDraw, heading: bool) -> List[str]:
        if not text:
            return [""]

        max_width = self.page_width - (self.margin * 2)
        wrapped: List[str] = []
        width_guess = 90 if heading else 110
        for paragraph in textwrap.wrap(text, width=width_guess) or [""]:
            line = paragraph
            while draw.textlength(line, font=self.title_font if heading else self.body_font) > max_width and len(line) > 5:
                line = line[:-5]
            wrapped.append(line)
        return wrapped
