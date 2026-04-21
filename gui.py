"""
Modern desktop GUI for epubsteel.
"""

from __future__ import annotations

import logging
import os
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, Dict, List, Optional

from auth import create_default_auth_handler
from epub_generator import EPUBGenerator
from scraper import WebScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def sanitize_filename(value: str, fallback: str = "epubsteel_export") -> str:
    """Create a filesystem-safe filename stem."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or fallback


class QueueLogHandler(logging.Handler):
    """Push log records into the GUI queue."""

    def __init__(self, sink: Callable[[str], None]) -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink(self.format(record))


class EPUBSteelGUI:
    """Desktop application for converting webpages into EPUB files."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("EPUBSteel")
        self.root.geometry("1180x760")
        self.root.minsize(1040, 700)
        self.root.configure(bg="#0b1020")

        self.output_path = ""
        self.worker_thread: Optional[threading.Thread] = None
        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.is_running = False
        self.latest_success_path: Optional[str] = None
        self.has_prompted_for_output = False

        self.auth_mode = tk.StringVar(value="none")
        self.follow_links_var = tk.BooleanVar(value=False)
        self.dry_run_var = tk.BooleanVar(value=False)
        self.verbose_var = tk.BooleanVar(value=False)
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="Add one or more URLs to begin.")

        self._setup_styles()
        self._create_layout()
        self._toggle_auth_fields()
        self.root.after(250, self._prompt_for_initial_output_file)
        self.root.after(120, self._process_queue)

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        palette: Dict[str, str] = {
            "bg": "#0b1020",
            "panel": "#121a2f",
            "panel_alt": "#19233f",
            "panel_soft": "#0f1730",
            "text": "#edf2ff",
            "muted": "#92a0bf",
            "accent": "#36cfc9",
            "accent_2": "#7ad7ff",
            "border": "#25345f",
            "field": "#0d152b",
            "button": "#1f9d96",
            "button_hover": "#32b7af",
            "danger": "#ee6b6e",
        }
        self.palette = palette

        style.configure(".", background=palette["bg"], foreground=palette["text"], font=("Segoe UI", 10))
        style.configure("App.TFrame", background=palette["bg"])
        style.configure("Card.TFrame", background=palette["panel"], relief="flat")
        style.configure("SoftCard.TFrame", background=palette["panel_soft"], relief="flat")
        style.configure("Title.TLabel", background=palette["bg"], foreground=palette["text"], font=("Segoe UI Semibold", 27))
        style.configure("Subtitle.TLabel", background=palette["bg"], foreground=palette["muted"], font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=palette["panel"], foreground=palette["text"], font=("Segoe UI Semibold", 11))
        style.configure("Body.TLabel", background=palette["panel"], foreground=palette["muted"], font=("Segoe UI", 10))
        style.configure("Value.TLabel", background=palette["panel_soft"], foreground=palette["text"], font=("Segoe UI Semibold", 11))
        style.configure("Badge.TLabel", background=palette["panel_alt"], foreground=palette["accent_2"], font=("Segoe UI Semibold", 9))

        style.configure(
            "Primary.TButton",
            background=palette["button"],
            foreground="#081018",
            borderwidth=0,
            focuscolor=palette["button"],
            padding=(16, 10),
            font=("Segoe UI Semibold", 10),
        )
        style.map("Primary.TButton", background=[("active", palette["button_hover"]), ("disabled", "#365766")])

        style.configure(
            "Secondary.TButton",
            background=palette["panel_alt"],
            foreground=palette["text"],
            borderwidth=0,
            focuscolor=palette["panel_alt"],
            padding=(14, 9),
            font=("Segoe UI", 10),
        )
        style.map("Secondary.TButton", background=[("active", "#24335c")])

        style.configure("TEntry", fieldbackground=palette["field"], foreground=palette["text"], insertcolor=palette["text"], bordercolor=palette["border"], lightcolor=palette["border"], darkcolor=palette["border"], padding=8)
        style.configure("TCombobox", fieldbackground=palette["field"], foreground=palette["text"], arrowcolor=palette["accent_2"], bordercolor=palette["border"], lightcolor=palette["border"], darkcolor=palette["border"], padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", palette["field"])], selectbackground=[("readonly", palette["panel_alt"])], selectforeground=[("readonly", palette["text"])])
        style.configure("TCheckbutton", background=palette["panel"], foreground=palette["text"])
        style.map("TCheckbutton", background=[("active", palette["panel"])])

        style.configure(
            "App.Horizontal.TProgressbar",
            troughcolor=palette["field"],
            background=palette["accent"],
            bordercolor=palette["field"],
            lightcolor=palette["accent"],
            darkcolor=palette["accent"],
            thickness=12,
        )

    def _create_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.root, style="App.TFrame", padding=22)
        outer.grid(sticky="nsew")
        outer.columnconfigure(0, weight=5)
        outer.columnconfigure(1, weight=3)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="EPUBSteel", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Turn one page or a whole reading list into a polished EPUB with a cleaner Windows workflow.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        left = ttk.Frame(outer, style="Card.TFrame", padding=18)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(9, weight=1)

        right = ttk.Frame(outer, style="Card.TFrame", padding=18)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)

        self._create_input_panel(left)
        self._create_status_panel(right)

    def _create_input_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Source URLs", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text="Paste one URL per line. You can mix articles, chapters, or documentation pages.",
            style="Body.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))

        self.urls_text = scrolledtext.ScrolledText(
            parent,
            height=8,
            wrap=tk.WORD,
            bg=self.palette["field"],
            fg=self.palette["text"],
            insertbackground=self.palette["text"],
            relief=tk.FLAT,
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        self.urls_text.grid(row=2, column=0, sticky="ew")

        meta = ttk.Frame(parent, style="Card.TFrame")
        meta.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        meta.columnconfigure(0, weight=1)
        meta.columnconfigure(1, weight=1)

        self.title_entry = self._labeled_entry(meta, 0, 0, "Book Title", "Leave blank to auto-use the first page title.")
        self.author_entry = self._labeled_entry(meta, 0, 1, "Author", "Defaults to Unknown if left empty.")
        self.output_entry = self._labeled_entry(parent, 4, 0, "Output EPUB", "Pick where the .epub file should be saved.")

        output_actions = ttk.Frame(parent, style="Card.TFrame")
        output_actions.grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Button(output_actions, text="Choose File", style="Secondary.TButton", command=self._choose_output_file).pack(side=tk.LEFT)
        ttk.Button(output_actions, text="Open Folder", style="Secondary.TButton", command=self._open_output_folder).pack(side=tk.LEFT, padx=(10, 0))

        options = ttk.Frame(parent, style="Card.TFrame")
        options.grid(row=6, column=0, sticky="ew", pady=(18, 0))
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)

        ttk.Label(options, text="Options", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(options, text="Follow a few same-domain links from each page", variable=self.follow_links_var).grid(row=1, column=0, sticky="w", pady=(8, 2))
        ttk.Checkbutton(options, text="Dry run only", variable=self.dry_run_var).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(options, text="Verbose logging", variable=self.verbose_var).grid(row=3, column=0, sticky="w", pady=2)

        auth = ttk.Frame(parent, style="SoftCard.TFrame", padding=14)
        auth.grid(row=7, column=0, sticky="ew", pady=(18, 0))
        auth.columnconfigure(0, weight=1)
        auth.columnconfigure(1, weight=1)

        ttk.Label(auth, text="Authentication", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(auth, text="Use only if the site requires credentials or a token.", style="Body.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 10))

        mode_row = ttk.Frame(auth, style="SoftCard.TFrame")
        mode_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Label(mode_row, text="Mode", style="Body.TLabel").pack(side=tk.LEFT)
        self.auth_mode_combo = ttk.Combobox(mode_row, state="readonly", textvariable=self.auth_mode, values=["none", "basic", "bearer"], width=14)
        self.auth_mode_combo.pack(side=tk.LEFT, padx=(12, 0))
        self.auth_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._toggle_auth_fields())

        self.username_entry = self._labeled_entry(auth, 3, 0, "Username", "For HTTP basic authentication.")
        self.password_entry = self._labeled_entry(auth, 3, 1, "Password", "Stored only for this session.", show="*")
        self.token_entry = self._labeled_entry(auth, 4, 0, "Bearer Token", "Paste the access token if the site expects Authorization: Bearer.")
        self.user_agent_entry = self._labeled_entry(auth, 4, 1, "User-Agent", "Leave as-is unless the site needs a custom browser signature.")
        self.user_agent_entry.insert(0, DEFAULT_USER_AGENT)

        actions = ttk.Frame(parent, style="Card.TFrame")
        actions.grid(row=8, column=0, sticky="ew", pady=(20, 0))

        self.run_button = ttk.Button(actions, text="Create EPUB", style="Primary.TButton", command=self._start_conversion)
        self.run_button.pack(side=tk.LEFT)
        ttk.Button(actions, text="Clear", style="Secondary.TButton", command=self._clear_form).pack(side=tk.LEFT, padx=(10, 0))

    def _create_status_panel(self, parent: ttk.Frame) -> None:
        summary = ttk.Frame(parent, style="SoftCard.TFrame", padding=14)
        summary.grid(row=0, column=0, sticky="ew")
        summary.columnconfigure(0, weight=1)

        ttk.Label(summary, text="Session", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.status_var, style="Badge.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Label(summary, textvariable=self.summary_var, style="Body.TLabel", wraplength=320, justify=tk.LEFT).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        metrics = ttk.Frame(parent, style="Card.TFrame")
        metrics.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        metrics.columnconfigure((0, 1), weight=1)

        self.url_count_label = self._metric_card(metrics, 0, "URLs queued", "0")
        self.chapter_count_label = self._metric_card(metrics, 1, "Chapters added", "0")

        ttk.Label(parent, text="Progress", style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(16, 6))
        self.progress_bar = ttk.Progressbar(parent, style="App.Horizontal.TProgressbar", variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=3, column=0, sticky="ew")

        ttk.Label(parent, text="Activity Log", style="Section.TLabel").grid(row=4, column=0, sticky="w", pady=(18, 8))
        self.log_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            height=18,
            bg=self.palette["field"],
            fg=self.palette["text"],
            insertbackground=self.palette["text"],
            relief=tk.FLAT,
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        self.log_text.grid(row=5, column=0, sticky="nsew")
        self.log_text.configure(state=tk.DISABLED)

    def _labeled_entry(
        self,
        parent: ttk.Frame,
        row: int,
        column: int,
        label: str,
        hint: str,
        show: Optional[str] = None,
    ) -> ttk.Entry:
        group = ttk.Frame(parent, style=parent.cget("style") or "Card.TFrame")
        group.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 10, 0), pady=(14, 0))
        group.columnconfigure(0, weight=1)

        ttk.Label(group, text=label, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(group, text=hint, style="Body.TLabel", wraplength=360, justify=tk.LEFT).grid(row=1, column=0, sticky="w", pady=(3, 6))
        entry = ttk.Entry(group, show=show or "")
        entry.grid(row=2, column=0, sticky="ew")
        return entry

    def _metric_card(self, parent: ttk.Frame, column: int, label: str, value: str) -> ttk.Label:
        card = ttk.Frame(parent, style="SoftCard.TFrame", padding=12)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 10, 0))
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text=label, style="Body.TLabel").grid(row=0, column=0, sticky="w")
        value_label = ttk.Label(card, text=value, style="Value.TLabel")
        value_label.grid(row=1, column=0, sticky="w", pady=(8, 0))
        return value_label

    def _toggle_auth_fields(self) -> None:
        mode = self.auth_mode.get()
        basic_state = "normal" if mode == "basic" else "disabled"
        bearer_state = "normal" if mode == "bearer" else "disabled"

        self.username_entry.config(state=basic_state)
        self.password_entry.config(state=basic_state)
        self.token_entry.config(state=bearer_state)

    def _choose_output_file(self) -> None:
        current_value = self.output_entry.get().strip() or self.output_path
        initial_dir = os.path.dirname(current_value) or str(Path.home() / "Downloads")
        initial_name = os.path.basename(current_value) or "epubsteel-book.epub"
        selected = filedialog.asksaveasfilename(
            title="Save EPUB As",
            defaultextension=".epub",
            filetypes=[("EPUB files", "*.epub")],
            initialdir=initial_dir,
            initialfile=initial_name,
        )
        if selected:
            self.output_path = selected
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, selected)
            self._set_summary(f"Output file selected: {selected}")

    def _prompt_for_initial_output_file(self) -> None:
        if self.has_prompted_for_output:
            return

        self.has_prompted_for_output = True
        self._set_status("Choose output")
        self._set_summary("Choose where the EPUB should be saved for this session.")
        self._choose_output_file()

        if not self.output_entry.get().strip():
            self._set_status("Ready")
            self._set_summary("Add URLs, then choose an output EPUB file to begin.")
        else:
            self._set_status("Ready")

    def _open_output_folder(self) -> None:
        output = self.output_entry.get().strip()
        directory = os.path.dirname(output) if output else ""
        if not directory:
            directory = str(Path.home() / "Downloads")
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        os.startfile(directory)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _queue_log(self, message: str) -> None:
        self.queue.put(("log", message))

    def _set_progress(self, value: float) -> None:
        self.queue.put(("progress", value))

    def _set_status(self, value: str) -> None:
        self.queue.put(("status", value))

    def _set_summary(self, value: str) -> None:
        self.queue.put(("summary", value))

    def _set_metric(self, metric: str, value: str) -> None:
        self.queue.put(("metric", (metric, value)))

    def _process_queue(self) -> None:
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self._append_log(str(payload))
            elif kind == "progress":
                self.progress_var.set(float(payload))
            elif kind == "status":
                self.status_var.set(str(payload))
            elif kind == "summary":
                self.summary_var.set(str(payload))
            elif kind == "metric":
                metric_name, metric_value = payload  # type: ignore[misc]
                if metric_name == "urls":
                    self.url_count_label.config(text=metric_value)
                elif metric_name == "chapters":
                    self.chapter_count_label.config(text=metric_value)
            elif kind == "finished":
                success, message = payload  # type: ignore[misc]
                self.is_running = False
                self.run_button.config(state=tk.NORMAL)
                if success:
                    messagebox.showinfo("EPUBSteel", str(message))
                else:
                    messagebox.showerror("EPUBSteel", str(message))

        self.root.after(120, self._process_queue)

    def _collect_inputs(self) -> Optional[Dict[str, object]]:
        urls = [line.strip() for line in self.urls_text.get("1.0", tk.END).splitlines() if line.strip()]
        title = self.title_entry.get().strip()
        author = self.author_entry.get().strip() or "Unknown"
        output = self.output_entry.get().strip()
        auth_mode = self.auth_mode.get()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        token = self.token_entry.get().strip()
        user_agent = self.user_agent_entry.get().strip() or DEFAULT_USER_AGENT

        if not urls:
            messagebox.showerror("EPUBSteel", "Add at least one URL.")
            return None
        if not output:
            messagebox.showerror("EPUBSteel", "Choose an output EPUB file.")
            return None
        if auth_mode == "basic" and (not username or not password):
            messagebox.showerror("EPUBSteel", "Basic authentication needs both username and password.")
            return None
        if auth_mode == "bearer" and not token:
            messagebox.showerror("EPUBSteel", "Paste a bearer token or switch authentication mode to none.")
            return None

        return {
            "urls": urls,
            "title": title,
            "author": author,
            "output": output,
            "auth_mode": auth_mode,
            "username": username,
            "password": password,
            "token": token,
            "user_agent": user_agent,
            "follow_links": self.follow_links_var.get(),
            "dry_run": self.dry_run_var.get(),
            "verbose": self.verbose_var.get(),
        }

    def _start_conversion(self) -> None:
        if self.is_running:
            return

        payload = self._collect_inputs()
        if not payload:
            return

        self.latest_success_path = None
        self.is_running = True
        self.run_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        urls = payload["urls"]  # type: ignore[assignment]
        self._set_status("Running")
        self._set_summary(f"Converting {len(urls)} URL(s) into an EPUB.")  # type: ignore[arg-type]
        self._set_metric("urls", str(len(urls)))
        self._set_metric("chapters", "0")
        self._queue_log("EPUBSteel session started.")

        self.worker_thread = threading.Thread(target=self._run_conversion, args=(payload,), daemon=True)
        self.worker_thread.start()

    def _run_conversion(self, payload: Dict[str, object]) -> None:
        urls: List[str] = payload["urls"]  # type: ignore[assignment]
        title: str = payload["title"]  # type: ignore[assignment]
        author: str = payload["author"]  # type: ignore[assignment]
        output: str = payload["output"]  # type: ignore[assignment]
        auth_mode: str = payload["auth_mode"]  # type: ignore[assignment]
        username: str = payload["username"]  # type: ignore[assignment]
        password: str = payload["password"]  # type: ignore[assignment]
        token: str = payload["token"]  # type: ignore[assignment]
        user_agent: str = payload["user_agent"]  # type: ignore[assignment]
        follow_links: bool = payload["follow_links"]  # type: ignore[assignment]
        dry_run: bool = payload["dry_run"]  # type: ignore[assignment]
        verbose: bool = payload["verbose"]  # type: ignore[assignment]

        handler = QueueLogHandler(self._queue_log)
        handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
        root_logger = logging.getLogger()
        original_level = root_logger.level
        if verbose:
            root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(handler)

        try:
            auth = create_default_auth_handler()
            auth.set_user_agent(user_agent)
            if auth_mode == "basic":
                auth.set_basic_auth(username, password)
                self._queue_log("Authentication mode: basic")
            elif auth_mode == "bearer":
                auth.set_bearer_token(token)
                self._queue_log("Authentication mode: bearer")
            else:
                self._queue_log("Authentication mode: none")

            scraper = WebScraper(auth_handler=auth, timeout=15)
            discovered: List[str] = []
            scraped_pages = []
            queued = list(urls)
            seen = set()

            self._set_progress(8)
            for seed in urls:
                self._queue_log(f"Queued: {seed}")

            while queued:
                current_url = queued.pop(0)
                if current_url in seen:
                    continue
                seen.add(current_url)

                self._set_summary(f"Scraping {current_url}")
                self._queue_log(f"Fetching {current_url}")
                data = scraper.scrape_url(current_url)
                if not data:
                    self._queue_log(f"Skipped: unable to scrape {current_url}")
                    continue

                scraped_pages.append(data)
                chapter_total = len(scraped_pages)
                self._set_metric("chapters", str(chapter_total))
                self._queue_log(f"Captured: {data.get('title', 'Untitled')}")

                if follow_links:
                    for link in data.get("links", []):
                        if link not in seen and link not in queued and link not in discovered:
                            discovered.append(link)
                    if discovered:
                        extra_links = discovered[:5]
                        discovered = discovered[5:]
                        queued.extend(extra_links)
                        self._queue_log(f"Added {len(extra_links)} same-domain link(s) for follow-up.")

                progress = 12 + min(58, chapter_total * 12)
                self._set_progress(progress)

            if not scraped_pages:
                raise RuntimeError("No content could be scraped from the supplied URL list.")

            resolved_title = title or scraped_pages[0].get("title", "Untitled")
            resolved_output = output
            if not resolved_output.lower().endswith(".epub"):
                resolved_output = f"{resolved_output}.epub"
            if os.path.basename(resolved_output) in {"", ".epub"}:
                resolved_output = os.path.join(resolved_output, f"{sanitize_filename(resolved_title)}.epub")

            self._set_summary(f"Building EPUB for {resolved_title}")
            self._queue_log(f"Creating EPUB: {resolved_title}")
            self._set_progress(76)

            epub = EPUBGenerator(title=resolved_title, author=author)
            epub.add_css(
                """
                body { font-family: Georgia, serif; line-height: 1.6; }
                h1, h2, h3 { font-family: Arial, sans-serif; }
                p { margin: 0 0 0.9em 0; }
                """
            )

            for index, page in enumerate(scraped_pages, start=1):
                chapter_title = str(page.get("title") or f"Chapter {index}")
                chapter_content = str(page.get("content") or "No content extracted.")
                epub.add_chapter_from_text(chapter_title, chapter_content)
                self._set_metric("chapters", str(index))
                self._set_progress(76 + min(16, index * 3))

            if dry_run:
                info = epub.get_info()
                self._set_status("Dry run complete")
                self._set_progress(100)
                self._set_summary(f"Dry run finished for {info['title']}")
                self.queue.put(("finished", (True, f"Dry run complete.\n\nTitle: {info['title']}\nAuthor: {info['author']}\nChapters: {info['chapters']}")))
                return

            os.makedirs(os.path.dirname(resolved_output) or ".", exist_ok=True)
            success = epub.save(resolved_output)
            if not success:
                raise RuntimeError("The EPUB generator could not save the file.")

            self.latest_success_path = resolved_output
            self._set_progress(100)
            self._set_status("Complete")
            self._set_summary(f"Saved EPUB to {resolved_output}")
            self.queue.put(("finished", (True, f"EPUB created successfully.\n\n{resolved_output}")))
        except Exception as exc:
            logger.exception("GUI conversion failed")
            self._set_status("Failed")
            self._set_summary(str(exc))
            self.queue.put(("finished", (False, f"Conversion failed.\n\n{exc}")))
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(original_level)

    def _clear_form(self) -> None:
        self.urls_text.delete("1.0", tk.END)
        self.title_entry.delete(0, tk.END)
        self.author_entry.delete(0, tk.END)
        self.output_entry.delete(0, tk.END)
        if self.output_path:
            self.output_entry.insert(0, self.output_path)
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.token_entry.delete(0, tk.END)
        self.user_agent_entry.delete(0, tk.END)
        self.user_agent_entry.insert(0, DEFAULT_USER_AGENT)
        self.auth_mode.set("none")
        self.follow_links_var.set(False)
        self.dry_run_var.set(False)
        self.verbose_var.set(False)
        self._toggle_auth_fields()
        self.progress_var.set(0)
        self.status_var.set("Ready")
        self.summary_var.set("Add one or more URLs to begin.")
        self.url_count_label.config(text="0")
        self.chapter_count_label.config(text="0")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)


def main() -> None:
    root = tk.Tk()
    app = EPUBSteelGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
