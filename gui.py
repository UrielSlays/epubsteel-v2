"""
GUI application for downloading and converting novels to EPUB format.
Uses tkinter for the interface and threading for non-blocking operations.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import logging
import os
from pathlib import Path
from typing import Optional

from auth import AuthHandler, create_default_auth_handler
from scraper import WebScraper
from epub_generator import EPUBGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EPUBDownloaderGUI:
    """GUI application for downloading and converting novels to EPUB."""

    def __init__(self, root: tk.Tk):
        """
        Initialize the GUI application.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("EPUB Novel Downloader & Converter")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        self.output_directory = str(Path.home() / "Downloads")
        self.download_thread = None
        self.is_downloading = False
        
        self._setup_styles()
        self._create_widgets()
        
    def _setup_styles(self) -> None:
        """Setup custom styles for the GUI."""
        style = ttk.Style()
        style.theme_use('clam')
        
    def _create_widgets(self) -> None:
        """Create all GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="EPUB Novel Downloader", 
                                font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # URL Input
        ttk.Label(main_frame, text="Novel URL:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(main_frame, width=40)
        self.url_entry.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Username/Email
        ttk.Label(main_frame, text="Username/Email:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(main_frame, width=40)
        self.username_entry.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Password
        ttk.Label(main_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(main_frame, width=40, show="*")
        self.password_entry.grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Chapter Limit
        ttk.Label(main_frame, text="Chapter Limit (optional):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.chapter_limit_entry = ttk.Entry(main_frame, width=10)
        self.chapter_limit_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        self.chapter_limit_entry.insert(0, "0")
        
        # Output Directory
        ttk.Label(main_frame, text="Output Directory:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.output_dir_label = ttk.Label(main_frame, text=self.output_directory, 
                                          foreground="blue", wraplength=300)
        self.output_dir_label.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5)
        self.browse_btn = ttk.Button(main_frame, text="Browse", 
                                     command=self._browse_directory)
        self.browse_btn.grid(row=5, column=2, sticky=tk.W, padx=5)
        
        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                            maximum=100, mode='determinate')
        self.progress_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Status Text Area
        ttk.Label(main_frame, text="Status:").grid(row=7, column=0, sticky=tk.NW, pady=(5, 0))
        self.status_text = scrolledtext.ScrolledText(main_frame, height=12, width=70, 
                                                      wrap=tk.WORD, state=tk.DISABLED)
        self.status_text.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        main_frame.rowconfigure(8, weight=1)
        
        # Button Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.download_btn = ttk.Button(button_frame, text="Download & Convert", 
                                       command=self._on_download_click)
        self.download_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = ttk.Button(button_frame, text="Clear", command=self._clear_form)
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        self.exit_btn = ttk.Button(button_frame, text="Exit", command=self.root.quit)
        self.exit_btn.pack(side=tk.LEFT, padx=5)
        
    def _browse_directory(self) -> None:
        """Open directory browser and set output directory."""
        directory = filedialog.askdirectory(initialdir=self.output_directory,
                                           title="Select Output Directory")
        if directory:
            self.output_directory = directory
            self.output_dir_label.config(text=self.output_directory)
            self._log_message(f"Output directory set to: {self.output_directory}")
            
    def _log_message(self, message: str) -> None:
        """
        Add a message to the status text area.
        
        Args:
            message: Message to display
        """
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
        
    def _on_download_click(self) -> None:
        """Handle download button click."""
        if self.is_downloading:
            messagebox.showwarning("Warning", "Download already in progress!")
            return
            
        # Validate inputs
        url = self.url_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a novel URL!")
            return
            
        if not username or not password:
            messagebox.showerror("Error", "Please enter username/email and password!")
            return
            
        # Start download in separate thread
        self.is_downloading = True
        self.download_btn.config(state=tk.DISABLED)
        self.download_thread = threading.Thread(target=self._download_and_convert,
                                               args=(url, username, password),
                                               daemon=True)
        self.download_thread.start()
        
    def _download_and_convert(self, url: str, username: str, password: str) -> None:
        """
        Download chapters and convert to EPUB in a separate thread.
        
        Args:
            url: Novel URL
            username: Username/email for authentication
            password: Password for authentication
        """
        try:
            self._log_message("=" * 60)
            self._log_message("Starting download and conversion...")
            self._log_message(f"URL: {url}")
            self._log_message("=" * 60)
            
            # Setup authentication
            self._log_message("Setting up authentication...")
            auth = AuthHandler()
            auth.set_basic_auth(username, password)
            auth.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            # Initialize scraper
            self._log_message("Initializing web scraper...")
            scraper = WebScraper(auth_handler=auth, timeout=15)
            
            # Fetch the page
            self._log_message(f"Fetching page: {url}")
            self.progress_var.set(10)
            html_content = scraper.fetch_page(url)
            
            if not html_content:
                self._log_message("ERROR: Failed to fetch the page!")
                raise Exception("Failed to fetch page content")
                
            # Parse content
            self._log_message("Parsing page content...")
            self.progress_var.set(25)
            scraped_data = scraper.scrape_url(url)
            
            if not scraped_data:
                self._log_message("ERROR: Failed to scrape page!")
                raise Exception("Failed to scrape page")
                
            # Extract info
            title = scraped_data.get('title', 'Novel')
            content = scraped_data.get('content', '')
            
            self._log_message(f"Novel Title: {title}")
            self._log_message(f"Content extracted: {len(content)} characters")
            
            # Check chapter limit
            chapter_limit_str = self.chapter_limit_entry.get().strip()
            chapter_limit = 0
            if chapter_limit_str and chapter_limit_str.isdigit():
                chapter_limit = int(chapter_limit_str)
                self._log_message(f"Chapter limit set to: {chapter_limit}")
            
            # Create EPUB
            self._log_message("Creating EPUB file...")
            self.progress_var.set(50)
            epub_gen = EPUBGenerator(title=title, author="Downloaded Novel")
            
            # Add chapter from content
            self._log_message("Adding content as chapter...")
            epub_gen.add_chapter_from_text("Chapter 1", content[:10000] if content else "Content not available")
            
            # Create table of contents
            self._log_message("Creating table of contents...")
            epub_gen.create_table_of_contents()
            
            # Save EPUB
            self.progress_var.set(75)
            filename = f"{title.replace(' ', '_')}.epub"
            output_path = os.path.join(self.output_directory, filename)
            
            self._log_message(f"Saving EPUB to: {output_path}")
            success = epub_gen.save(output_path)
            
            self.progress_var.set(100)
            
            if success:
                self._log_message("=" * 60)
                self._log_message("✓ SUCCESS: EPUB file created successfully!")
                self._log_message(f"File saved to: {output_path}")
                self._log_message("=" * 60)
                messagebox.showinfo("Success", f"EPUB created successfully!\n\n{output_path}")
            else:
                self._log_message("ERROR: Failed to save EPUB file!")
                raise Exception("Failed to save EPUB")
                
        except Exception as e:
            self._log_message(f"ERROR: {str(e)}")
            self._log_message("=" * 60)
            messagebox.showerror("Error", f"Download failed:\n{str(e)}")
            
        finally:
            self.is_downloading = False
            self.download_btn.config(state=tk.NORMAL)
            self.progress_var.set(0)
            
    def _clear_form(self) -> None:
        """Clear all input fields."""
        self.url_entry.delete(0, tk.END)
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.chapter_limit_entry.delete(0, tk.END)
        self.chapter_limit_entry.insert(0, "0")
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self._log_message("Form cleared.")


def main() -> None:
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = EPUBDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
