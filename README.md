# epubsteel

A powerful Python tool for scraping web content and converting it into EPUB eBooks. Perfect for archiving blog posts, articles, documentation, and web content.

## Features

- **Web Scraping**: Extract content from web pages using BeautifulSoup
- **Multi-URL Support**: Scrape multiple URLs and combine into a single EPUB
- **Link Following**: Optional automatic link discovery and scraping
- **Authentication**: Support for basic auth, bearer tokens, and custom headers
- **EPUB Generation**: Create valid, readable EPUB files with proper metadata
- **Image Support**: Include images from scraped pages
- **Custom Metadata**: Set book title, author, and other metadata
- **Dry-Run Mode**: Preview what will be scraped without creating files
- **Verbose Logging**: Detailed logging for debugging
- **User-Agent Control**: Customize User-Agent headers for compatibility

## Installation

### Prerequisites
- Python 3.7 or higher
- pip package manager

### Setup

1. Clone or download the epubsteel repository
2. Install dependencies:

\\\ash
pip install -r requirements.txt
\\\

## Usage

### Basic Usage

Convert a single webpage to EPUB:

\\\ash
python main.py -u https://example.com -o book.epub -t "My Book Title"
\\\

### Multiple URLs

Scrape and combine multiple pages:

\\\ash
python main.py -u https://example.com https://example.com/page2 https://example.com/page3 \
  -o output.epub -t "Multi-Page Book" -a "Author Name"
\\\

### Follow Links

Automatically follow links found on pages:

\\\ash
python main.py -u https://example.com -o book.epub -t "Book" --follow-links
\\\

### Authentication

#### Basic Authentication

\\\ash
python main.py -u https://example.com -o book.epub -t "Protected Content" \
  --username myuser --password mypass
\\\

#### Bearer Token

\\\ash
python main.py -u https://example.com -o book.epub -t "API Content" \
  --bearer-token "your-token-here"
\\\

### Custom User-Agent

\\\ash
python main.py -u https://example.com -o book.epub -t "Book" \
  --user-agent "Mozilla/5.0 (Custom)"
\\\

### Dry-Run Mode

Preview what will be scraped without creating files:

\\\ash
python main.py -u https://example.com -o book.epub -t "Test Book" --dry-run
\\\

### Verbose Output

Enable detailed logging:

\\\ash
python main.py -u https://example.com -o book.epub -t "Book" -v
\\\

## Command-Line Options

\\\
-u, --url              URL(s) to scrape (required, can specify multiple)
-o, --output           Output EPUB file path (required)
-t, --title            Book title (required)
-a, --author           Book author (default: Unknown)
--follow-links         Follow links found on pages
--dry-run              Show what would be done without saving
-v, --verbose          Enable verbose logging
--user-agent           Custom User-Agent header
--username             Username for basic authentication
--password             Password for basic authentication
--bearer-token         Bearer token for authentication
\\\

## Project Structure

\\\
epubsteel/
├── main.py                  # CLI entry point
├── auth.py                  # Authentication handling
├── scraper.py               # Web scraping module
├── epub_generator.py        # EPUB generation
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── .github/
    └── copilot-instructions.md  # GitHub Copilot instructions
\\\

## Module Overview

### auth.py
Handles HTTP authentication including:
- Basic authentication (username/password)
- Bearer token authentication
- Custom headers
- User-Agent customization

### scraper.py
Web scraping functionality:
- Page fetching with retry capability
- HTML parsing with BeautifulSoup
- Content extraction (title, text, links, images)
- Multi-page scraping
- Same-domain link filtering

### epub_generator.py
EPUB file creation:
- Book metadata management
- Chapter addition
- Content formatting
- CSS styling support
- Image inclusion
- Table of contents generation

### main.py
Command-line interface and orchestration:
- Argument parsing
- Authentication setup
- Scraping workflow
- EPUB generation coordination

## Dependencies

- **requests**: HTTP client library
- **beautifulsoup4**: HTML parsing
- **ebooklib**: EPUB file creation
- **lxml**: HTML parsing backend
- **Pillow**: Image processing
- **python-dateutil**: Date utilities
- **click**: CLI framework
- **rich**: Rich text and formatting

## Examples

### Archive a Blog

\\\ash
python main.py \
  -u https://myblog.com/article1 https://myblog.com/article2 \
  -o my-blog-archive.epub \
  -t "My Blog Archive" \
  -a "Blog Author"
\\\

### Extract Documentation

\\\ash
python main.py \
  -u https://docs.example.com/guide \
  -o documentation.epub \
  -t "API Documentation" \
  --follow-links \
  -v
\\\

### Protected Content with Auth

\\\ash
python main.py \
  -u https://secure.example.com/content \
  -o protected.epub \
  -t "Protected Content" \
  --username admin \
  --password secret123
\\\

## Limitations

- Some JavaScript-rendered content may not be captured (use Selenium for dynamic content)
- Large documents may take time to process
- Image extraction depends on availability and accessibility
- Some DRM-protected content cannot be scraped

## Troubleshooting

### Connection Refused
Try with a custom User-Agent:
\\\ash
python main.py -u https://example.com -o book.epub -t "Test" \
  --user-agent "Mozilla/5.0"
\\\

### Authentication Errors
Verify credentials and try verbose mode:
\\\ash
python main.py -u https://example.com -o book.epub -t "Test" \
  --username user --password pass -v
\\\

### No Content Extracted
Check the HTML structure and try following links:
\\\ash
python main.py -u https://example.com -o book.epub -t "Test" --dry-run -v
\\\

## Development

### Adding Custom Content Extractors

Edit \scraper.py\ to customize content extraction:

\\\python
def extract_content(self, soup: BeautifulSoup) -> str:
    # Add custom selectors for your target site
    content = soup.select_one('your-custom-selector')
    if content:
        return content.get_text(strip=True)
    # ... fallback logic
\\\

### Custom Styling

Add CSS styling to generated EPUBs by modifying \epub_generator.py\:

\\\python
css_content = """
body { font-family: 'Georgia', serif; }
p { margin-bottom: 1em; }
"""
epub_gen.add_css(css_content)
\\\

## License

This project is provided as-is for educational and personal use.

## Disclaimer

This tool should be used responsibly and in compliance with:
- Website terms of service
- Copyright laws
- Robots.txt guidelines
- Local and international laws

Always respect the intellectual property rights of content authors.

## Contributing

Contributions are welcome! Areas for improvement:

- Support for more content extraction patterns
- JavaScript rendering support
- Parallel scraping
- Progress bars and better UI
- Unit test coverage
- Configuration file support

## Support

For issues, questions, or suggestions, please refer to the project documentation or create an issue in the repository.

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Author**: epubsteel Development Team
