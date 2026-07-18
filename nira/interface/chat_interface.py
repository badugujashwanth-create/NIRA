from __future__ import annotations

import ctypes
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Event
from typing import TYPE_CHECKING, Any

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, simpledialog

    TK_AVAILABLE = True
except Exception:
    tk = None
    filedialog = None
    messagebox = None
    scrolledtext = None
    simpledialog = None
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
        self._conversation_title_var = None
        self.demo_mode = False

    def ensure_window(self, start_hidden: bool = False) -> bool:
        if not self.gui_available or tk is None or scrolledtext is None:
            return False
        if self.root is not None:
            if start_hidden:
                self.root.withdraw()
            else:
                self.root.deiconify()
            return True
        if os.name == "nt":
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                pass
        try:
            root = tk.Tk()
        except Exception:
            self.gui_available = False
            return False
        self.root = root
        root.title("Nira Desktop Assistant")
        root.geometry("1120x760")
        root.minsize(960, 640)
        root.configure(bg="#08111b")
        try:
            root.attributes("-alpha", 1.0)
        except Exception:
            pass

        shell = tk.Frame(root, bg="#08111b", padx=18, pady=18)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        header = tk.Frame(shell, bg="#08111b")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        tk.Label(
            header,
            text="Nira",
            bg="#08111b",
            fg="#e2e8f0",
            font=("Segoe UI", 24, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text=("Local model enabled" if self.manager.runtime.config.local_model_enabled else "Offline-safe local assistant"),
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
        tk.Button(
            header,
            text="Privacy",
            command=self._show_privacy,
            bg="#0f172a",
            fg="#bae6fd",
            activebackground="#1e293b",
            activeforeground="#e0f2fe",
            relief="flat",
            bd=0,
            padx=12,
            pady=7,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right", padx=(0, 12), pady=(4, 0))

        body = tk.Frame(shell, bg="#08111b")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        conversation_card = tk.Frame(body, bg="#0f172a", highlightbackground="#1e293b", highlightthickness=1)
        conversation_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        conversation_toolbar = tk.Frame(conversation_card, bg="#0f172a")
        conversation_toolbar.pack(fill="x", padx=14, pady=(10, 8))
        self._conversation_title_var = tk.StringVar(value=self.manager.runtime.current_conversation.title)
        tk.Label(
            conversation_toolbar,
            textvariable=self._conversation_title_var,
            bg="#0f172a",
            fg="#dbeafe",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")
        tk.Button(
            conversation_toolbar,
            text="New",
            command=self._start_new_conversation,
            bg="#1e293b",
            fg="#e2e8f0",
            activebackground="#334155",
            activeforeground="#f8fafc",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right", padx=(8, 0))
        tk.Button(
            conversation_toolbar,
            text="Conversations",
            command=self._open_conversation_manager,
            bg="#1e293b",
            fg="#bae6fd",
            activebackground="#334155",
            activeforeground="#e0f2fe",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")
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
            width=48,
            height=12,
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
            width=34,
            height=7,
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
            width=34,
            height=6,
        )
        self._context.grid(row=3, column=0, sticky="nsew")
        self._context.configure(state="disabled")

        footer = tk.Frame(shell, bg="#08111b")
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        tk.Label(
            footer,
            text="Message Nira",
            bg="#08111b",
            fg="#cbd5e1",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 10))
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
        root.bind("<Control-n>", lambda _event: self._start_new_conversation())
        root.bind("<Control-h>", lambda _event: self._open_conversation_manager())
        root.bind("<Control-l>", lambda _event: self._entry.focus_set() if self._entry is not None else None)
        self._render_current_conversation()
        self._set_text_widget(self._progress, "No active tasks.\n\nTry a project inspection or ask a question.")
        self._set_text_widget(
            self._context,
            "Mode: " + ("Local model" if self.manager.runtime.config.local_model_enabled else "Deterministic offline")
            + "\nStorage: Local only\nSide effects: Approval required",
        )
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
        current = self.manager.runtime.current_conversation
        print(
            "NIRA Local Runtime ready. "
            f"Conversation {current.conversation_id} ({current.title}). Type /help for commands."
        )
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
            if user_input.startswith("/") and self._handle_console_command(user_input):
                continue
            self.manager.handle_user_input(user_input)

    def _handle_console_command(self, command: str) -> bool:
        runtime = self.manager.runtime
        name, _, raw_value = command.partition(" ")
        value = raw_value.strip()
        if name == "/help":
            print(
                "Commands: /health, /new [title], /sessions, /use <id>, /search <text>, "
                "/pin [id], /unpin [id], /rename <title>, /export <path>, /delete <id>, "
                "/inspect [path], /read <path>, /permissions, /privacy, /voice, /exit"
            )
            return True
        if name == "/health":
            print(runtime.health())
            return True
        if name == "/new":
            conversation = runtime.new_conversation(value or "New conversation")
            print(f"Started {conversation.conversation_id}: {conversation.title}")
            return True
        if name == "/sessions":
            for item in runtime.list_conversations():
                marker = "*" if item.pinned else " "
                active = " active" if item.conversation_id == runtime.current_conversation.conversation_id else ""
                print(f"{marker} {item.conversation_id}  {item.title}  messages={item.message_count}{active}")
            return True
        if name == "/use":
            if not value:
                print("Usage: /use <conversation-id>")
                return True
            try:
                conversation = runtime.switch_conversation(value)
            except KeyError as exc:
                print(str(exc))
            else:
                print(f"Using {conversation.conversation_id}: {conversation.title}")
            return True
        if name == "/search":
            if not value:
                print("Usage: /search <text>")
                return True
            matches = runtime.search_conversations(value)
            if not matches:
                print("No matching conversation content.")
            for match in matches:
                preview = " ".join(match["content"].split())[:96]
                print(f"{match['conversation_id']}  {match['role']}: {preview}")
            return True
        if name in {"/pin", "/unpin"}:
            conversation_id = value or runtime.current_conversation.conversation_id
            changed = runtime.pin_conversation(conversation_id, pinned=name == "/pin")
            print(("Updated " if changed else "Unknown ") + f"conversation {conversation_id}.")
            return True
        if name == "/rename":
            if not value:
                print("Usage: /rename <new title>")
                return True
            runtime.rename_conversation(runtime.current_conversation.conversation_id, value)
            print(f"Renamed current conversation to: {value}")
            return True
        if name == "/export":
            if not value:
                print("Usage: /export <markdown-path>")
                return True
            try:
                output = runtime.export_conversation(Path(value))
            except (KeyError, OSError) as exc:
                print(f"Export failed: {exc}")
            else:
                print(f"Exported conversation to {output}")
            return True
        if name == "/delete":
            conversation_id = value or runtime.current_conversation.conversation_id
            phrase = input(f"Type DELETE {conversation_id} to permanently delete this local conversation: ").strip()
            if phrase != f"DELETE {conversation_id}":
                print("Deletion cancelled.")
                return True
            changed = runtime.delete_conversation(conversation_id)
            print(("Deleted " if changed else "Unknown ") + f"conversation {conversation_id}.")
            return True
        if name == "/privacy":
            print(
                f"State directory: {runtime.config.base_dir}\n"
                f"Interaction training log enabled: {runtime.config.interaction_logging_enabled}\n"
                "Conversation history is local SQLite data. Workspace writes, processes, and network tools require approval."
            )
            return True
        if name == "/inspect":
            print(runtime.inspect_project(value or ".").output)
            return True
        if name == "/read":
            if not value:
                print("Usage: /read <workspace-relative-path>")
                return True
            print(runtime.read_workspace_file(value).output)
            return True
        if name == "/permissions":
            decisions = runtime.recent_permission_decisions()
            if not decisions:
                print("No tool permission decisions in this process.")
            for decision in decisions:
                verdict = "allowed" if decision["allowed"] else "blocked"
                print(f"{decision['timestamp']}  {decision['tool']}  {decision['access']}  {verdict}  {decision['reason']}")
            return True
        if name == "/voice":
            self.manager.handle_voice_input()
            return True
        print(f"Unknown command: {name}. Type /help.")
        return True

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

    def request_tool_approval(self, tool_name: str, args: dict[str, Any], access: Any) -> bool:
        if self.root is None or tk is None:
            return False
        completed = Event()
        decision = {"allowed": False}
        visible = {
            key: value
            for key, value in args.items()
            if key in {"action", "path", "cwd", "command", "source", "destination", "query"}
        }
        access_name = getattr(access, "value", str(access))

        def ask() -> None:
            dialog = tk.Toplevel(self.root)
            dialog.title("Nira permission request")
            dialog.geometry("540x360")
            dialog.resizable(False, False)
            dialog.configure(bg="#08111b")
            dialog.transient(self.root)
            dialog.grab_set()

            shell = tk.Frame(dialog, bg="#08111b", padx=24, pady=22)
            shell.pack(fill="both", expand=True)
            tk.Label(
                shell,
                text="Approval required",
                bg="#08111b",
                fg="#f8fafc",
                font=("Segoe UI", 18, "bold"),
            ).pack(anchor="w")
            tk.Label(
                shell,
                text="Nira paused before a side effect. Review the request and allow it once only if you initiated it.",
                bg="#08111b",
                fg="#cbd5e1",
                wraplength=480,
                justify="left",
                font=("Segoe UI", 10),
            ).pack(anchor="w", pady=(6, 16))
            detail_card = tk.Frame(shell, bg="#0f172a", padx=14, pady=12)
            detail_card.pack(fill="x")
            details = [("Tool", tool_name), ("Access", access_name)] + list(visible.items())
            for row, (key, value) in enumerate(details):
                tk.Label(
                    detail_card,
                    text=f"{str(key).replace('_', ' ').title()}:",
                    bg="#0f172a",
                    fg="#7dd3fc",
                    font=("Segoe UI", 9, "bold"),
                ).grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=2)
                tk.Label(
                    detail_card,
                    text=str(value),
                    bg="#0f172a",
                    fg="#e2e8f0",
                    wraplength=350,
                    justify="left",
                    font=("Consolas", 9),
                ).grid(row=row, column=1, sticky="nw", pady=2)

            def choose(allowed: bool) -> None:
                decision["allowed"] = allowed
                try:
                    dialog.grab_release()
                except tk.TclError:
                    pass
                dialog.destroy()
                completed.set()

            actions = tk.Frame(shell, bg="#08111b")
            actions.pack(fill="x", pady=(18, 0))
            allow_button = tk.Button(
                actions,
                text="Allow once",
                command=lambda: choose(True),
                bg="#38bdf8",
                fg="#082f49",
                activebackground="#7dd3fc",
                activeforeground="#082f49",
                relief="flat",
                bd=0,
                padx=18,
                pady=9,
                font=("Segoe UI", 10, "bold"),
            )
            allow_button.pack(side="right")
            deny_button = tk.Button(
                actions,
                text="Deny",
                command=lambda: choose(False),
                bg="#1e293b",
                fg="#f8fafc",
                activebackground="#334155",
                activeforeground="#f8fafc",
                relief="flat",
                bd=0,
                padx=18,
                pady=9,
                font=("Segoe UI", 10, "bold"),
            )
            deny_button.pack(side="right", padx=(0, 10))
            dialog.protocol("WM_DELETE_WINDOW", lambda: choose(False))
            dialog.bind("<Escape>", lambda _event: choose(False))
            deny_button.focus_set()
            if self.demo_mode:
                def auto_deny() -> None:
                    try:
                        if dialog.winfo_exists():
                            choose(False)
                    except tk.TclError:
                        return

                self.root.after_idle(lambda: self._publish_demo_window("permission", dialog))
                self.root.after(6000, auto_deny)

        self.root.after(0, ask)
        return completed.wait(timeout=120) and decision["allowed"]

    def _start_new_conversation(self) -> None:
        self.manager.runtime.new_conversation()
        self._render_current_conversation()
        if self._entry is not None:
            self._entry.focus_set()

    def _render_current_conversation(self) -> None:
        runtime = self.manager.runtime
        conversation = runtime.current_conversation
        if self._conversation_title_var is not None:
            self._conversation_title_var.set(conversation.title)
        if self._conversation is None:
            return
        self._conversation.configure(state="normal")
        self._conversation.delete("1.0", "end")
        messages = runtime.conversation_store.messages(conversation.conversation_id)
        if messages:
            for message in messages:
                speaker = "You" if message.role == "user" else "Nira"
                self._conversation.insert("end", f"{speaker}: {message.content}\n\n")
        else:
            self._conversation.insert(
                "end",
                "Nira: Start with a question, inspect this project, or open Conversations to restore prior work. "
                "Offline mode never pretends a local model is running.\n\n",
            )
        self._conversation.see("end")
        self._conversation.configure(state="disabled")

    def _open_conversation_manager(self) -> None:
        if self.root is None or tk is None:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Nira Conversations")
        dialog.geometry("680x430")
        dialog.minsize(560, 360)
        dialog.configure(bg="#08111b")
        dialog.transient(self.root)

        shell = tk.Frame(dialog, bg="#08111b", padx=18, pady=18)
        shell.pack(fill="both", expand=True)
        tk.Label(
            shell,
            text="Local conversations",
            bg="#08111b",
            fg="#e2e8f0",
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            shell,
            text="Switch, pin, export, rename, or permanently delete history stored on this device.",
            bg="#08111b",
            fg="#94a3b8",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(3, 12))
        search_row = tk.Frame(shell, bg="#08111b")
        search_row.pack(fill="x", pady=(0, 10))
        tk.Label(
            search_row,
            text="Search",
            bg="#08111b",
            fg="#cbd5e1",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 10))
        search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_row,
            textvariable=search_var,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
        )
        search_entry.pack(side="left", fill="x", expand=True, ipady=7)
        listbox = tk.Listbox(
            shell,
            bg="#0f172a",
            fg="#e2e8f0",
            selectbackground="#0369a1",
            selectforeground="#f8fafc",
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
            activestyle="dotbox",
        )
        listbox.pack(fill="both", expand=True)
        conversations: list[Any] = []

        def refresh(select_id: str | None = None) -> None:
            nonlocal conversations
            all_conversations = self.manager.runtime.list_conversations()
            query = search_var.get().strip()
            if query:
                matching_ids = {
                    str(match["conversation_id"])
                    for match in self.manager.runtime.search_conversations(query, limit=100)
                }
                lowered = query.casefold()
                conversations = [
                    item
                    for item in all_conversations
                    if lowered in item.title.casefold() or item.conversation_id in matching_ids
                ]
            else:
                conversations = all_conversations
            listbox.delete(0, "end")
            active_id = select_id or self.manager.runtime.current_conversation.conversation_id
            selected_index = 0
            for index, item in enumerate(conversations):
                marker = "Pinned" if item.pinned else "Local"
                listbox.insert("end", f"{item.title}  |  {marker}  |  {item.message_count} messages")
                if item.conversation_id == active_id:
                    selected_index = index
            if conversations:
                listbox.selection_set(selected_index)
                listbox.see(selected_index)

        def selected() -> Any | None:
            selection = listbox.curselection()
            return conversations[selection[0]] if selection else None

        def switch() -> None:
            item = selected()
            if item is None:
                return
            self.manager.runtime.switch_conversation(item.conversation_id)
            self._render_current_conversation()
            dialog.destroy()

        def pin() -> None:
            item = selected()
            if item is None:
                return
            self.manager.runtime.pin_conversation(item.conversation_id, not item.pinned)
            refresh(item.conversation_id)

        def rename() -> None:
            item = selected()
            if item is None or simpledialog is None:
                return
            title = simpledialog.askstring("Rename conversation", "New title", initialvalue=item.title, parent=dialog)
            if title:
                self.manager.runtime.rename_conversation(item.conversation_id, title)
                self._render_current_conversation()
                refresh(item.conversation_id)

        def export() -> None:
            item = selected()
            if item is None or filedialog is None:
                return
            destination = filedialog.asksaveasfilename(
                parent=dialog,
                title="Export conversation",
                defaultextension=".md",
                filetypes=[("Markdown", "*.md")],
                initialfile=f"{item.title[:48] or 'nira-conversation'}.md",
            )
            if destination:
                self.manager.runtime.export_conversation(Path(destination), item.conversation_id)

        def delete() -> None:
            item = selected()
            if item is None or messagebox is None:
                return
            confirmed = messagebox.askyesno(
                "Delete local conversation",
                f"Permanently delete '{item.title}' and all of its local messages?\n\nThis cannot be undone.",
                parent=dialog,
                default="no",
            )
            if confirmed:
                self.manager.runtime.delete_conversation(item.conversation_id)
                self._render_current_conversation()
                refresh()

        actions = tk.Frame(shell, bg="#08111b")
        actions.pack(fill="x", pady=(12, 0))
        for label, command, foreground in (
            ("Open", switch, "#082f49"),
            ("Pin / unpin", pin, "#e2e8f0"),
            ("Rename", rename, "#e2e8f0"),
            ("Export", export, "#e2e8f0"),
            ("Delete", delete, "#fecaca"),
        ):
            background = "#38bdf8" if label == "Open" else "#1e293b"
            tk.Button(
                actions,
                text=label,
                command=command,
                bg=background,
                fg=foreground,
                activebackground="#334155",
                activeforeground="#f8fafc",
                relief="flat",
                bd=0,
                padx=12,
                pady=8,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left", padx=(0, 8))
        listbox.bind("<Double-Button-1>", lambda _event: switch())
        listbox.bind("<Return>", lambda _event: switch())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        search_entry.bind("<KeyRelease>", lambda _event: refresh())
        refresh()
        search_entry.focus_set()
        if self.demo_mode and self.root is not None:
            self.root.after_idle(lambda: self._publish_demo_window("conversations", dialog))

    def _publish_demo_window(self, name: str, dialog: Any) -> None:
        if not self.demo_mode or tk is None:
            return
        try:
            handle = int(str(dialog.wm_frame()), 0)
            path = self.manager.runtime.config.base_dir / f"ui-audit-{name}-window.txt"
            path.write_text(str(handle), encoding="utf-8")
        except (OSError, ValueError, tk.TclError):
            return

    def _show_privacy(self) -> None:
        if messagebox is None:
            return
        runtime = self.manager.runtime
        model_mode = "enabled" if runtime.config.local_model_enabled else "disabled (deterministic offline mode)"
        messagebox.showinfo(
            "Nira privacy and safety",
            f"Conversation storage: local SQLite\nState directory: {runtime.config.base_dir}\n"
            f"Local model: {model_mode}\nInteraction training log: "
            f"{'enabled' if runtime.config.interaction_logging_enabled else 'disabled'}\n\n"
            "Workspace writes, processes, and network tools require explicit approval.",
            parent=self.root,
        )

    def display_user_message(self, text: str) -> None:
        self.history.append({"role": "user", "text": text})
        self._dispatch("message", ("You", text))

    def display_response(self, response: "RuntimeResponse") -> None:
        self.history.append({"role": "assistant", "text": response.text})
        self._dispatch("message", ("Nira", response.text))
        self.update_context(response.state.context)
        if self._conversation_title_var is not None:
            self._conversation_title_var.set(self.manager.runtime.current_conversation.title)

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
            self._set_status(f"{title}: {message}" if level in {"warning", "error"} else message)

    def _append_message(self, speaker: str, text: str) -> None:
        line = f"{speaker}: {text}".strip()
        if self._conversation is None:
            print(line)
            return
        self._conversation.configure(state="normal")
        self._conversation.insert("end", f"{line}\n\n")
        self._conversation.see("end")
        self._conversation.configure(state="disabled")
        if self.demo_mode:
            try:
                transcript = self._conversation.get("1.0", "end").strip()
                (self.manager.runtime.config.base_dir / "ui-audit-transcript.txt").write_text(
                    transcript,
                    encoding="utf-8",
                )
            except (OSError, tk.TclError if tk is not None else RuntimeError):
                pass

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
        workspace = Path(str(context.get("cwd", "Unknown"))).name or "Unknown"
        lines = [
            f"Active Project: {context.get('active_project', 'Unknown')}",
            f"Language: {context.get('language', 'Unknown')}",
            f"Last Error: {context.get('last_error') or 'None'}",
            f"Workspace: {workspace}",
            "Storage: Local only",
        ]
        knowledge = context.get("retrieved_knowledge", [])
        if knowledge:
            first = knowledge[0]
            topic = first.get("topic", "Research")
            lines.append(f"Knowledge Hit: {topic}")
        return "\n".join(lines)
