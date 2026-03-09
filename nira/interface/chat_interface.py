from __future__ import annotations

from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

try:
    import tkinter as tk
    from tkinter import scrolledtext

    TK_AVAILABLE = True
except Exception:
    tk = None
    scrolledtext = None
    TK_AVAILABLE = False

if TYPE_CHECKING:
    from nira.core.agent_runtime import RuntimeResponse
    from nira.interface.interface_manager import InterfaceManager


class ChatInterface:
    def __init__(self, manager: "InterfaceManager", prefer_gui: bool = True) -> None:
        self.manager = manager
        self.prefer_gui = prefer_gui
        self.gui_available = TK_AVAILABLE and prefer_gui
        self.history: list[dict[str, str]] = []
        self.root = None
        self._queue: Queue[tuple[str, Any]] = Queue()
        self._conversation = None
        self._progress = None
        self._context = None
        self._entry = None
        self._status_var = None

    def ensure_window(self, start_hidden: bool = False) -> bool:
        if not self.gui_available or tk is None or scrolledtext is None:
            return False
        if self.root is not None:
            if start_hidden:
                self.root.withdraw()
            else:
                self.root.deiconify()
            return True
        try:
            root = tk.Tk()
        except Exception:
            self.gui_available = False
            return False
        self.root = root
        root.title("Nira Desktop Assistant")
        root.geometry("1080x720")
        root.minsize(900, 620)
        root.configure(bg="#08111b")
        try:
            root.attributes("-alpha", 0.97)
        except Exception:
            pass

        shell = tk.Frame(root, bg="#08111b", padx=18, pady=18)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg="#08111b")
        header.pack(fill="x", pady=(0, 12))
        tk.Label(
            header,
            text="Nira",
            bg="#08111b",
            fg="#e2e8f0",
            font=("Segoe UI", 24, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text="Local desktop assistant",
            bg="#08111b",
            fg="#7dd3fc",
            font=("Segoe UI", 11),
        ).pack(side="left", padx=(12, 0), pady=(8, 0))
        self._status_var = tk.StringVar(value="Idle.")
        tk.Label(
            header,
            textvariable=self._status_var,
            bg="#08111b",
            fg="#94a3b8",
            font=("Segoe UI", 10),
        ).pack(side="right", pady=(10, 0))

        body = tk.Frame(shell, bg="#08111b")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        conversation_card = tk.Frame(body, bg="#0f172a", highlightbackground="#1e293b", highlightthickness=1)
        conversation_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(
            conversation_card,
            text="Conversation",
            bg="#0f172a",
            fg="#dbeafe",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 8))
        self._conversation = scrolledtext.ScrolledText(
            conversation_card,
            wrap="word",
            bg="#0b1220",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            font=("Consolas", 11),
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
        )
        self._conversation.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._conversation.configure(state="disabled")

        sidebar = tk.Frame(body, bg="#08111b")
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.grid_rowconfigure(1, weight=1)
        sidebar.grid_rowconfigure(3, weight=1)

        tk.Label(
            sidebar,
            text="Task Progress",
            bg="#08111b",
            fg="#dbeafe",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._progress = tk.Text(
            sidebar,
            wrap="word",
            bg="#0f172a",
            fg="#cbd5e1",
            font=("Consolas", 10),
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            height=14,
        )
        self._progress.grid(row=1, column=0, sticky="nsew")
        self._progress.configure(state="disabled")

        tk.Label(
            sidebar,
            text="Context",
            bg="#08111b",
            fg="#dbeafe",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=2, column=0, sticky="w", pady=(14, 8))
        self._context = tk.Text(
            sidebar,
            wrap="word",
            bg="#0f172a",
            fg="#cbd5e1",
            font=("Consolas", 10),
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            height=12,
        )
        self._context.grid(row=3, column=0, sticky="nsew")
        self._context.configure(state="disabled")

        footer = tk.Frame(shell, bg="#08111b")
        footer.pack(fill="x", pady=(12, 0))
        self._entry = tk.Entry(
            footer,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            bd=0,
            font=("Segoe UI", 11),
        )
        self._entry.pack(side="left", fill="x", expand=True, ipady=10)
        self._entry.bind("<Return>", lambda _event: self._submit_text())
        tk.Button(
            footer,
            text="Send",
            command=self._submit_text,
            bg="#38bdf8",
            fg="#082f49",
            relief="flat",
            bd=0,
            padx=18,
            pady=10,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(10, 0))
        tk.Button(
            footer,
            text="Voice",
            command=self.manager.handle_voice_input_async,
            bg="#0f172a",
            fg="#7dd3fc",
            relief="flat",
            bd=0,
            padx=18,
            pady=10,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(10, 0))

        root.protocol("WM_DELETE_WINDOW", self.manager.shutdown)
        if start_hidden:
            root.withdraw()
        root.after(100, self._drain_queue)
        return True

    def run_mainloop(self) -> None:
        if self.root is None and not self.ensure_window():
            self.run_console()
            return
        if self.root is not None:
            self.root.mainloop()

    def run_console(self) -> None:
        print("NIRA Local Runtime ready. Type /exit to quit, /health for runtime status, /voice for voice input.")
        while True:
            try:
                user_input = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                self.manager.shutdown()
                break
            if not user_input:
                continue
            if user_input == "/exit":
                self.manager.shutdown()
                break
            if user_input == "/health":
                print(self.manager.runtime.system_metrics.snapshot())
                continue
            if user_input == "/voice":
                self.manager.handle_voice_input()
                continue
            self.manager.handle_user_input(user_input)

    def open_panel(self) -> None:
        if self.root is None:
            if not self.ensure_window():
                return
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self._entry is not None:
            self._entry.focus_set()

    def hide_panel(self) -> None:
        if self.root is not None:
            self.root.withdraw()

    def display_user_message(self, text: str) -> None:
        self.history.append({"role": "user", "text": text})
        self._dispatch("message", ("You", text))

    def display_response(self, response: "RuntimeResponse") -> None:
        self.history.append({"role": "assistant", "text": response.text})
        self._dispatch("message", ("Nira", response.text))
        self.update_context(response.state.context)

    def display_system_message(self, text: str) -> None:
        self._dispatch("message", ("System", text))

    def display_status(self, text: str) -> None:
        self._dispatch("status", text)

    def display_task_progress(self, text: str) -> None:
        self._dispatch("progress", text)

    def update_context(self, context: dict[str, Any]) -> None:
        self._dispatch("context", dict(context))

    def display_notification(self, title: str, message: str, level: str = "info") -> None:
        self._dispatch("notification", (title, message, level))

    def _submit_text(self) -> None:
        if self._entry is None:
            return
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, "end")
        self.manager.handle_user_input_async(text)

    def _dispatch(self, kind: str, payload: Any) -> None:
        if self.root is not None and self.gui_available:
            self._queue.put((kind, payload))
            return
        self._apply_event(kind, payload)

    def _drain_queue(self) -> None:
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except Empty:
                break
            self._apply_event(kind, payload)
        if self.root is not None:
            self.root.after(100, self._drain_queue)

    def _apply_event(self, kind: str, payload: Any) -> None:
        if kind == "message":
            speaker, text = payload
            self._append_message(str(speaker), str(text))
            return
        if kind == "status":
            self._set_status(str(payload))
            return
        if kind == "progress":
            self._set_text_widget(self._progress, str(payload))
            return
        if kind == "context":
            self._set_text_widget(self._context, self._format_context(payload))
            return
        if kind == "notification":
            title, message, level = payload
            self._append_message(title, f"{level}: {message}")

    def _append_message(self, speaker: str, text: str) -> None:
        line = f"{speaker}: {text}".strip()
        if self._conversation is None:
            print(line)
            return
        self._conversation.configure(state="normal")
        self._conversation.insert("end", f"{line}\n\n")
        self._conversation.see("end")
        self._conversation.configure(state="disabled")

    def _set_status(self, text: str) -> None:
        if self._status_var is None:
            print(f"[status] {text}")
            return
        self._status_var.set(text)

    @staticmethod
    def _set_text_widget(widget, text: str) -> None:
        if widget is None:
            if text:
                print(text)
            return
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.configure(state="disabled")

    @staticmethod
    def _format_context(context: dict[str, Any]) -> str:
        lines = [
            f"Active Project: {context.get('active_project', 'Unknown')}",
            f"Language: {context.get('language', 'Unknown')}",
            f"Last Error: {context.get('last_error') or 'None'}",
            f"Working Dir: {context.get('cwd', 'Unknown')}",
        ]
        knowledge = context.get("retrieved_knowledge", [])
        if knowledge:
            first = knowledge[0]
            topic = first.get("topic", "Research")
            lines.append(f"Knowledge Hit: {topic}")
        return "\n".join(lines)
