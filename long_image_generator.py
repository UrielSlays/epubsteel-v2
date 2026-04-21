"""
Create a single long vertical image from a sequence of chapter images.
"""

from __future__ import annotations

import os
from typing import List

from PIL import Image


class LongImageGenerator:
    """Stitch images into one continuous webtoon-style file."""

    def __init__(self, background: str = "white") -> None:
        self.background = background

    def save(self, filepath: str, image_paths: List[str]) -> bool:
        usable_paths = [path for path in image_paths if os.path.exists(path)]
        if not usable_paths:
            return False

        images = [Image.open(path).convert("RGB") for path in usable_paths]
        try:
            max_width = max(image.width for image in images)
            total_height = sum(image.height for image in images)

            canvas = Image.new("RGB", (max_width, total_height), self.background)
            y_position = 0
            for image in images:
                if image.width != max_width:
                    ratio = max_width / image.width
                    resized_height = max(1, int(image.height * ratio))
                    image = image.resize((max_width, resized_height), Image.Resampling.LANCZOS)
                canvas.paste(image, (0, y_position))
                y_position += image.height

            output_dir = os.path.dirname(filepath)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            canvas.save(filepath)
            return True
        finally:
            for image in images:
                image.close()
