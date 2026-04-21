"""
Modern desktop GUI for epubsteel chapter downloads.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from auth import create_default_auth_handler
from epub_generator import EPUBGenerator
from long_image_generator import LongImageGenerator
from pdf_generator import PDFGenerator
from scraper import WebScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def sanitize_filename(value: str, fallback: str = "untitled") -> str:
    cleaned = "".join(char for char in value if char not in '<>:"/\\|?*').strip().rstrip(".")
    cleaned = " ".join(cleaned.split())
    return cleaned[:120] or fallback


class QueueLogHandler(logging.Handler):
    """Push log records into the GUI queue."""

    def __init__(self, sink: Callable[[str], None]) -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink(self.format(record))


class EPUBSteelGUI:
    """Desktop application for downloading books chapter by chapter."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("EPUBSteel")
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = min(1220, max(900, screen_width - 80))
        window_height = min(820, max(680, screen_height - 120))
        pos_x = max(20, (screen_width - window_width) // 2)
        pos_y = max(20, (screen_height - window_height) // 2)
        self.root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
        self.root.minsize(860, 620)
        self.root.resizable(True, True)
        self.root.configure(bg="#0b1020")

        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.has_prompted_for_session = False
        self.session_folder = ""
        self.downloaded_chapters = 0

        self.auth_mode = tk.StringVar(value="none")
        self.verbose_var = tk.BooleanVar(value=False)
        self.format_var = tk.StringVar(value="epub")
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="Choose a session folder, then add one or more book URLs.")
        self.session_var = tk.StringVar(value="No session folder selected yet.")
        self.book_count_var = tk.StringVar(value="0")
        self.chapter_count_var = tk.StringVar(value="0")
        self.progress_var = tk.DoubleVar(value=0)

        self._setup_styles()
        self._create_layout()
        self._toggle_auth_fields()
        self.root.after(250, self._prompt_for_session_folder)
        self.root.after(120, self._process_queue)

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        self.palette: Dict[str, str] = {
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
        }

        palette = self.palette
        style.configure(".", background=palette["bg"], foreground=palette["text"], font=("Segoe UI", 10))
        style.configure("App.TFrame", background=palette["bg"])
        style.configure("Card.TFrame", background=palette["panel"])
        style.configure("SoftCard.TFrame", background=palette["panel_soft"])
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

        style.configure(
            "TEntry",
            fieldbackground=palette["field"],
            foreground=palette["text"],
            insertcolor=palette["text"],
            bordercolor=palette["border"],
            lightcolor=palette["border"],
            darkcolor=palette["border"],
            padding=8,
        )
        style.configure(
            "TCombobox",
            fieldbackground=palette["field"],
            foreground=palette["text"],
            arrowcolor=palette["accent_2"],
            bordercolor=palette["border"],
            lightcolor=palette["border"],
            darkcolor=palette["border"],
            padding=6,
        )
        style.map("TCombobox", fieldbackground=[("readonly", palette["field"])], selectforeground=[("readonly", palette["text"])])
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

        shell = ttk.Frame(self.root, style="App.TFrame")
        shell.grid(sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(shell, bg=self.palette["bg"], highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        outer = ttk.Frame(self.canvas, style="App.TFrame", padding=22)
        outer.columnconfigure(0, weight=5)
        outer.columnconfigure(1, weight=3)
        outer.rowconfigure(1, weight=1)
        self.outer_window = self.canvas.create_window((0, 0), window=outer, anchor="nw")

        outer.bind("<Configure>", self._on_outer_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        header = ttk.Frame(outer, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="EPUBSteel", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Download books chapter by chapter in order, save the raw chapter files, then export to EPUB or PDF.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        left = ttk.Frame(outer, style="Card.TFrame", padding=18)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(7, weight=1)

        right = ttk.Frame(outer, style="Card.TFrame", padding=18)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)

        self._create_input_panel(left)
        self._create_status_panel(right)
        self._create_footer(outer)

    def _create_input_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Book URLs", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text="Paste one book or first-chapter URL per line. The downloader will follow the next chapter link in sequence.",
            style="Body.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))

        self.urls_text = scrolledtext.ScrolledText(
            parent,
            height=9,
            wrap=tk.WORD,
            bg=self.palette["field"],
            fg=self.palette["text"],
            insertbackground=self.palette["text"],
            relief=tk.FLAT,
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        self.urls_text.grid(row=2, column=0, sticky="nsew")

        meta = ttk.Frame(parent, style="Card.TFrame")
        meta.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        meta.columnconfigure(0, weight=1)
        meta.columnconfigure(1, weight=1)

        self.author_entry = self._labeled_entry(meta, 0, 0, "Author", "Used for the final export metadata. Defaults to Unknown.")

        format_group = ttk.Frame(meta, style="Card.TFrame")
        format_group.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        format_group.columnconfigure(0, weight=1)
        ttk.Label(format_group, text="Export Format", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(format_group, text="Choose the format generated after the chapter download finishes.", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 6))
        self.format_combo = ttk.Combobox(format_group, state="readonly", textvariable=self.format_var, values=["epub", "pdf", "long-image"])
        self.format_combo.grid(row=2, column=0, sticky="ew")

        session = ttk.Frame(parent, style="SoftCard.TFrame", padding=14)
        session.grid(row=4, column=0, sticky="ew", pady=(18, 0))
        session.columnconfigure(0, weight=1)
        ttk.Label(session, text="Session Folder", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(session, textvariable=self.session_var, style="Body.TLabel", wraplength=650, justify=tk.LEFT).grid(row=1, column=0, sticky="w", pady=(4, 10))

        session_actions = ttk.Frame(session, style="SoftCard.TFrame")
        session_actions.grid(row=2, column=0, sticky="w")
        ttk.Button(session_actions, text="New Session Folder", style="Secondary.TButton", command=self._prompt_for_session_folder).pack(side=tk.LEFT)
        ttk.Button(session_actions, text="Open Session Folder", style="Secondary.TButton", command=self._open_session_folder).pack(side=tk.LEFT, padx=(10, 0))

        auth = ttk.Frame(parent, style="SoftCard.TFrame", padding=14)
        auth.grid(row=5, column=0, sticky="ew", pady=(18, 0))
        auth.columnconfigure(0, weight=1)
        auth.columnconfigure(1, weight=1)

        ttk.Label(auth, text="Authentication", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(auth, text="Use this only if the site needs basic auth or a bearer token.", style="Body.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 10))

        mode_row = ttk.Frame(auth, style="SoftCard.TFrame")
        mode_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Label(mode_row, text="Mode", style="Body.TLabel").pack(side=tk.LEFT)
        self.auth_mode_combo = ttk.Combobox(mode_row, state="readonly", textvariable=self.auth_mode, values=["none", "basic", "bearer"], width=14)
        self.auth_mode_combo.pack(side=tk.LEFT, padx=(12, 0))
        self.auth_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._toggle_auth_fields())

        self.username_entry = self._labeled_entry(auth, 3, 0, "Username", "For HTTP basic authentication.")
        self.password_entry = self._labeled_entry(auth, 3, 1, "Password", "Stored only for this session.", show="*")
        self.token_entry = self._labeled_entry(auth, 4, 0, "Bearer Token", "Used if the site expects Authorization: Bearer.")
        self.user_agent_entry = self._labeled_entry(auth, 4, 1, "User-Agent", "Leave this alone unless the site needs a custom browser signature.")
        self.user_agent_entry.insert(0, DEFAULT_USER_AGENT)

        options = ttk.Frame(parent, style="Card.TFrame")
        options.grid(row=6, column=0, sticky="ew", pady=(18, 0))
        ttk.Checkbutton(options, text="Verbose logging", variable=self.verbose_var).pack(side=tk.LEFT)

        actions = ttk.Frame(parent, style="Card.TFrame")
        actions.grid(row=7, column=0, sticky="ew", pady=(20, 0))

        self.start_button = ttk.Button(actions, text="Start", style="Primary.TButton", command=self._start_download)
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = ttk.Button(actions, text="Stop", style="Secondary.TButton", command=self._stop_download)
        self.stop_button.pack(side=tk.LEFT, padx=(10, 0))
        self.stop_button.config(state=tk.DISABLED)
        ttk.Button(actions, text="Clear", style="Secondary.TButton", command=self._clear_form).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(actions, text="Downloads continue chapter by chapter until the book ends, an error occurs, or you stop the run.", style="Body.TLabel").pack(side=tk.LEFT, padx=(14, 0))

    def _create_status_panel(self, parent: ttk.Frame) -> None:
        summary = ttk.Frame(parent, style="SoftCard.TFrame", padding=14)
        summary.grid(row=0, column=0, sticky="ew")
        summary.columnconfigure(0, weight=1)

        ttk.Label(summary, text="Session", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.status_var, style="Badge.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Label(summary, textvariable=self.summary_var, style="Body.TLabel", wraplength=330, justify=tk.LEFT).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        metrics = ttk.Frame(parent, style="Card.TFrame")
        metrics.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        metrics.columnconfigure((0, 1), weight=1)

        self.book_count_label = self._metric_card(metrics, 0, "Books queued", self.book_count_var)
        self.chapter_count_label = self._metric_card(metrics, 1, "Chapters saved", self.chapter_count_var)

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

    def _create_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent, style="App.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(
            footer,
            text="Tip: drag the window edges or use the bottom-right grip to resize the app.",
            style="Subtitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        grip = ttk.Sizegrip(footer)
        grip.grid(row=0, column=1, sticky="se")
        grip.configure(cursor="size_nw_se")

    def _on_outer_configure(self, _event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.outer_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        if event.delta:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        elif getattr(event, "num", None) == 4:
            self.canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.canvas.yview_scroll(1, "units")

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
        ttk.Label(group, text=hint, style="Body.TLabel", wraplength=330, justify=tk.LEFT).grid(row=1, column=0, sticky="w", pady=(3, 6))
        entry = ttk.Entry(group, show=show or "")
        entry.grid(row=2, column=0, sticky="ew")
        return entry

    def _metric_card(self, parent: ttk.Frame, column: int, label: str, variable: tk.StringVar) -> ttk.Label:
        card = ttk.Frame(parent, style="SoftCard.TFrame", padding=12)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 10, 0))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=label, style="Body.TLabel").grid(row=0, column=0, sticky="w")
        value_label = ttk.Label(card, textvariable=variable, style="Value.TLabel")
        value_label.grid(row=1, column=0, sticky="w", pady=(8, 0))
        return value_label

    def _toggle_auth_fields(self) -> None:
        mode = self.auth_mode.get()
        basic_state = "normal" if mode == "basic" else "disabled"
        bearer_state = "normal" if mode == "bearer" else "disabled"
        self.username_entry.config(state=basic_state)
        self.password_entry.config(state=basic_state)
        self.token_entry.config(state=bearer_state)

    def _prompt_for_session_folder(self) -> None:
        if self.is_running:
            messagebox.showwarning("EPUBSteel", "Stop the current run before changing the session folder.")
            return

        initial_dir = str(Path.home() / "Downloads")
        selected_base = filedialog.askdirectory(title="Choose a parent folder for this session", initialdir=initial_dir)
        if not selected_base:
            if self.has_prompted_for_session and self.session_folder:
                return
            selected_base = initial_dir

        self.has_prompted_for_session = True
        session_name = f"epubsteel_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_folder = os.path.join(selected_base, session_name)
        os.makedirs(self.session_folder, exist_ok=True)
        self.session_var.set(self.session_folder)
        self._set_summary(f"Session folder ready: {self.session_folder}")

    def _open_session_folder(self) -> None:
        if not self.session_folder:
            self._prompt_for_session_folder()
        if self.session_folder:
            os.makedirs(self.session_folder, exist_ok=True)
            os.startfile(self.session_folder)

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
                if metric_name == "books":
                    self.book_count_var.set(metric_value)
                elif metric_name == "chapters":
                    self.chapter_count_var.set(metric_value)
            elif kind == "finished":
                success, message = payload  # type: ignore[misc]
                self.is_running = False
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                if success:
                    messagebox.showinfo("EPUBSteel", str(message))
                else:
                    messagebox.showerror("EPUBSteel", str(message))

        self.root.after(120, self._process_queue)

    def _collect_inputs(self) -> Optional[Dict[str, object]]:
        urls = [line.strip() for line in self.urls_text.get("1.0", tk.END).splitlines() if line.strip()]
        author = self.author_entry.get().strip() or "Unknown"
        auth_mode = self.auth_mode.get()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        token = self.token_entry.get().strip()
        user_agent = self.user_agent_entry.get().strip() or DEFAULT_USER_AGENT

        if not urls:
            messagebox.showerror("EPUBSteel", "Add at least one book URL.")
            return None
        if not self.session_folder:
            self._prompt_for_session_folder()
            if not self.session_folder:
                messagebox.showerror("EPUBSteel", "Choose a session folder before starting.")
                return None
        if auth_mode == "basic" and (not username or not password):
            messagebox.showerror("EPUBSteel", "Basic authentication needs both username and password.")
            return None
        if auth_mode == "bearer" and not token:
            messagebox.showerror("EPUBSteel", "Paste a bearer token or switch authentication mode to none.")
            return None

        return {
            "urls": urls,
            "author": author,
            "auth_mode": auth_mode,
            "username": username,
            "password": password,
            "token": token,
            "user_agent": user_agent,
            "verbose": self.verbose_var.get(),
            "format": self.format_var.get(),
        }

    def _start_download(self) -> None:
        if self.is_running:
            return

        payload = self._collect_inputs()
        if not payload:
            return

        self.stop_event.clear()
        self.is_running = True
        self.downloaded_chapters = 0
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.book_count_var.set(str(len(payload["urls"])))
        self.chapter_count_var.set("0")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._set_status("Running")
        self._set_summary(f"Downloading {len(payload['urls'])} book(s) chapter by chapter into {self.session_folder}.")
        self._queue_log("EPUBSteel session started.")

        self.worker_thread = threading.Thread(target=self._run_downloads, args=(payload,), daemon=True)
        self.worker_thread.start()

    def _stop_download(self) -> None:
        if not self.is_running:
            return
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED)
        self._set_status("Stopping")
        self._set_summary("Stopping after the current request finishes...")
        self._queue_log("Stop requested by user.")

    def _run_downloads(self, payload: Dict[str, object]) -> None:
        urls: List[str] = payload["urls"]  # type: ignore[assignment]
        author: str = payload["author"]  # type: ignore[assignment]
        auth_mode: str = payload["auth_mode"]  # type: ignore[assignment]
        username: str = payload["username"]  # type: ignore[assignment]
        password: str = payload["password"]  # type: ignore[assignment]
        token: str = payload["token"]  # type: ignore[assignment]
        user_agent: str = payload["user_agent"]  # type: ignore[assignment]
        verbose: bool = payload["verbose"]  # type: ignore[assignment]
        export_format: str = payload["format"]  # type: ignore[assignment]

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
            elif auth_mode == "bearer":
                auth.set_bearer_token(token)

            scraper = WebScraper(auth_handler=auth, timeout=15)
            for book_index, start_url in enumerate(urls, start=1):
                if self.stop_event.is_set():
                    break
                self._set_summary(f"Book {book_index}/{len(urls)}: starting from {start_url}")
                self._queue_log(f"Starting book {book_index}: {start_url}")
                self._download_book(scraper, start_url, author, export_format)
                self._set_progress((book_index / len(urls)) * 100)

            if self.stop_event.is_set():
                self._set_status("Stopped")
                self.queue.put(("finished", (True, f"Stopped by user.\n\nSession folder:\n{self.session_folder}")))
            else:
                self._set_status("Complete")
                self._set_summary(f"Finished. Files are in {self.session_folder}")
                self._set_progress(100)
                self.queue.put(("finished", (True, f"Downloads complete.\n\nSession folder:\n{self.session_folder}")))
        except Exception as exc:
            logger.exception("Download session failed")
            self._set_status("Failed")
            self._set_summary(str(exc))
            self.queue.put(("finished", (False, f"Download failed.\n\n{exc}")))
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(original_level)

    def _download_book(self, scraper: WebScraper, start_url: str, author: str, export_format: str) -> None:
        current_url = start_url
        chapter_index = 0
        seen_urls = set()
        collected: List[Dict[str, object]] = []
        book_folder = ""
        chapters_folder = ""
        resolved_book_title = ""
        all_image_paths: List[str] = []

        while current_url and not self.stop_event.is_set():
            if current_url in seen_urls:
                self._queue_log("Detected a loop in chapter links. Stopping this book.")
                break

            seen_urls.add(current_url)
            chapter = scraper.scrape_chapter(current_url)
            if not chapter:
                if collected:
                    self._queue_log(f"Stopping this book because the next chapter could not be downloaded: {current_url}")
                    break
                raise RuntimeError(f"Failed to download chapter URL: {current_url}")

            chapter_index += 1
            chapter_title = str(chapter.get("title") or f"Chapter {chapter_index}")
            chapter_content = str(chapter.get("content") or "").strip()
            chapter_images = [str(url) for url in chapter.get("images", []) if str(url).strip()]
            if not chapter_content and not chapter_images:
                raise RuntimeError(f"No chapter content found at: {current_url}")

            if not resolved_book_title:
                resolved_book_title = str(chapter.get("book_title") or chapter_title or "Untitled")
                book_folder = self._prepare_book_folder(resolved_book_title)
                chapters_folder = os.path.join(book_folder, "chapters")
                os.makedirs(chapters_folder, exist_ok=True)
                self._queue_log(f"Book folder created: {book_folder}")

            chapter_filename = f"{chapter_index:04d} - {sanitize_filename(chapter_title, f'chapter-{chapter_index:04d}')}"
            if chapter_content:
                chapter_path = os.path.join(chapters_folder, f"{chapter_filename}.txt")
                with open(chapter_path, "w", encoding="utf-8") as file_handle:
                    file_handle.write(chapter_title + "\n\n")
                    file_handle.write(chapter_content + "\n")
                    file_handle.write(f"\nSource URL: {current_url}\n")

            downloaded_image_paths = self._save_chapter_images(scraper, chapters_folder, chapter_filename, chapter_images)
            all_image_paths.extend(downloaded_image_paths)

            collected.append(
                {
                    "title": chapter_title,
                    "content": chapter_content,
                    "url": current_url,
                    "image_paths": downloaded_image_paths,
                }
            )
            self.downloaded_chapters += 1
            self._set_metric("chapters", str(self.downloaded_chapters))
            self._set_summary(f"{resolved_book_title}: saved chapter {chapter_index}")
            if downloaded_image_paths:
                self._queue_log(f"Saved chapter {chapter_index:04d}: {chapter_title} with {len(downloaded_image_paths)} image(s)")
            else:
                self._queue_log(f"Saved chapter {chapter_index:04d}: {chapter_title}")
            self._set_progress(min(95, 5 + (self.downloaded_chapters * 3)))

            next_url = str(chapter.get("next_url") or "").strip()
            if not next_url:
                self._queue_log("No next chapter link found. This book is complete.")
                break
            if not scraper.is_probable_chapter_url(current_url, next_url):
                self._queue_log(f"Stopping this book because the detected next link does not look like another chapter: {next_url}")
                break
            current_url = next_url

        if collected and not self.stop_event.is_set():
            self._export_book(book_folder, resolved_book_title, author, export_format, collected, all_image_paths)

    def _save_chapter_images(
        self,
        scraper: WebScraper,
        chapters_folder: str,
        chapter_filename: str,
        image_urls: List[str],
    ) -> List[str]:
        if not image_urls:
            return []

        image_folder = os.path.join(chapters_folder, chapter_filename)
        os.makedirs(image_folder, exist_ok=True)
        saved_paths: List[str] = []
        missing_images: List[str] = []

        for image_index, image_url in enumerate(image_urls, start=1):
            binary = scraper.fetch_binary(image_url)
            parsed_path = Path(urlparse(image_url).path)
            extension = parsed_path.suffix.lower()
            if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
                extension = ".jpg"
            source_name = sanitize_filename(parsed_path.name, f"image-{image_index:03d}{extension}")

            if not binary:
                missing_images.append(f"{image_index:03d} | {source_name} | {image_url}")
                placeholder_path = os.path.join(image_folder, f"{image_index:03d} - MISSING - {source_name}.txt")
                with open(placeholder_path, "w", encoding="utf-8") as placeholder_file:
                    placeholder_file.write("Image download failed.\n")
                    placeholder_file.write(f"Original file name: {source_name}\n")
                    placeholder_file.write(f"Original URL: {image_url}\n")
                continue

            image_path = os.path.join(image_folder, f"{image_index:03d}{extension}")
            with open(image_path, "wb") as file_handle:
                file_handle.write(binary)
            saved_paths.append(image_path)

        if missing_images:
            missing_report_path = os.path.join(image_folder, "_missing_images.txt")
            with open(missing_report_path, "w", encoding="utf-8") as missing_report:
                missing_report.write("The following chapter images failed to download.\n")
                missing_report.write("Use the original URL to retrieve them manually.\n\n")
                for line in missing_images:
                    missing_report.write(line + "\n")
            self._queue_log(f"Some chapter images failed and placeholders were saved in: {image_folder}")

        return saved_paths

    def _prepare_book_folder(self, book_title: str) -> str:
        folder_name = sanitize_filename(book_title, "untitled-book")
        candidate = os.path.join(self.session_folder, folder_name)
        suffix = 2
        while os.path.exists(candidate):
            candidate = os.path.join(self.session_folder, f"{folder_name} ({suffix})")
            suffix += 1
        os.makedirs(candidate, exist_ok=True)
        return candidate

    def _export_book(
        self,
        book_folder: str,
        book_title: str,
        author: str,
        export_format: str,
        chapters: List[Dict[str, object]],
        all_image_paths: List[str],
    ) -> None:
        self._queue_log(f"Converting {book_title} to {export_format.upper()}...")
        extension = "png" if export_format == "long-image" else export_format
        export_path = os.path.join(book_folder, f"{sanitize_filename(book_title)}.{extension}")

        if export_format == "long-image":
            generator = LongImageGenerator()
            if not generator.save(export_path, all_image_paths):
                notes_path = os.path.join(book_folder, "long-image-missing-assets.txt")
                with open(notes_path, "w", encoding="utf-8") as notes_file:
                    notes_file.write("LONG IMAGE export could not be generated because no downloaded image files were available.\n")
                    notes_file.write("Check chapter folders for placeholder files named '* - MISSING - *.txt'.\n")
                self._queue_log(f"Skipped LONG IMAGE export for {book_title}: no downloaded images were available.")
        elif export_format == "pdf":
            generator = PDFGenerator(title=book_title, author=author)
            for chapter in chapters:
                generator.add_chapter(str(chapter["title"]), str(chapter["content"]))
            generator.save(export_path)
        else:
            generator = EPUBGenerator(title=book_title, author=author)
            generator.add_css(
                """
                body { font-family: Georgia, serif; line-height: 1.6; }
                h1, h2, h3 { font-family: Arial, sans-serif; }
                p { margin: 0 0 0.9em 0; }
                """
            )
            for chapter in chapters:
                generator.add_chapter_from_text(str(chapter["title"]), str(chapter["content"]))
            if not generator.save(export_path):
                raise RuntimeError(f"Failed to save {export_format.upper()} export for {book_title}.")

        self._queue_log(f"Export saved: {export_path}")

    def _clear_form(self) -> None:
        if self.is_running:
            messagebox.showwarning("EPUBSteel", "Stop the current run before clearing the form.")
            return

        self.urls_text.delete("1.0", tk.END)
        self.author_entry.delete(0, tk.END)
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.token_entry.delete(0, tk.END)
        self.user_agent_entry.delete(0, tk.END)
        self.user_agent_entry.insert(0, DEFAULT_USER_AGENT)
        self.auth_mode.set("none")
        self.verbose_var.set(False)
        self.format_var.set("epub")
        self.book_count_var.set("0")
        self.chapter_count_var.set("0")
        self.progress_var.set(0)
        self.status_var.set("Ready")
        self.summary_var.set("Choose a session folder, then add one or more book URLs.")
        self._toggle_auth_fields()
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)


def main() -> None:
    root = tk.Tk()
    app = EPUBSteelGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
