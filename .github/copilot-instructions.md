# GitHub Copilot Instructions for epubsteel

## Project Overview
epubsteel is a Python tool for scraping web content and converting it into EPUB eBooks.

## Key Guidelines
1. **Web Scraping**: Use BeautifulSoup for HTML parsing and requests for HTTP calls
2. **EPUB Generation**: Leverage ebooklib for EPUB format creation
3. **Authentication**: Support basic auth and custom headers for protected content
4. **Error Handling**: Implement robust error handling for network and parsing failures
5. **CLI**: Provide user-friendly command-line interface with argparse

## Code Standards
- Use type hints where applicable
- Document functions with docstrings
- Follow PEP 8 conventions
- Add logging for debugging
- Include proper exception handling

## Testing
- Create unit tests for core modules
- Test with various web sources
- Validate EPUB output compatibility

## Features to Implement
- URL-based content scraping
- Multi-page content aggregation
- EPUB metadata customization
- Progress indicators for long operations
- Dry-run mode for testing
