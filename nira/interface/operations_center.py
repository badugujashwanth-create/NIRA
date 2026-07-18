from __future__ import annotations

import json
from typing import Any


class OperationsCenterPresenter:
    """Render a runtime product snapshot without depending on a GUI toolkit."""

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot

    def sections(self) -> dict[str, str]:
        return {
            "Overview": self._overview(),
            "Agents": self._agents(),
            "Memory": self._memory(),
            "Workflows": self._workflows(),
            "Models": self._models(),
            "Tools & permissions": self._tools(),
            "System health": self._system(),
        }

    def _overview(self) -> str:
        agents = self.snapshot.get("agents", [])
        memory = self.snapshot.get("memory", {})
        workflows = self.snapshot.get("workflows", {})
        tools = self.snapshot.get("tools", {})
        models = self.snapshot.get("models", {})
        runtime = models.get("runtime", {})
        return "\n".join(
            (
                "NIRA OPERATIONS CENTER",
                "One local, read-only view of the canonical runtime.",
                "",
                f"Mode                 {self.snapshot.get('mode', 'unknown')}",
                f"Specialist roles     {len(agents)}",
                f"Registered tools     {tools.get('count', 0)}",
                f"Workflow templates   {workflows.get('template_count', 0)}",
                f"Local conversations  {memory.get('conversation_count', 0)}",
                f"Stored messages      {memory.get('message_count', 0)}",
                f"Loaded models        {runtime.get('loaded_count', 0)}",
                "",
                "Side effects remain default-deny. This screen observes state; it does not grant access.",
            )
        )

    def _agents(self) -> str:
        lines = ["AGENT STATUS BOARD", ""]
        for agent in self.snapshot.get("agents", []):
            status = str(agent.get("status", "idle")).upper()
            lines.append(f"{agent.get('name', 'Agent')}  [{status}]")
            lines.append(f"  {agent.get('capability', '')}")
            lines.append(f"  Last activity: {agent.get('detail', 'Ready')}")
            lines.append("")
        trace = self.snapshot.get("agent_trace", [])
        lines.append("RECENT COLLABORATION TRACE")
        if not trace:
            lines.append("No request has run in this process yet.")
        for item in trace[-12:]:
            lines.append(f"- {item.get('agent')}: {item.get('detail')}")
        return "\n".join(lines)

    def _memory(self) -> str:
        memory = self.snapshot.get("memory", {})
        current = memory.get("current_conversation", {})
        return "\n".join(
            (
                "LOCAL MEMORY EXPLORER",
                "",
                f"Storage              {memory.get('storage', 'Local')}",
                f"Conversations        {memory.get('conversation_count', 0)}",
                f"Messages             {memory.get('message_count', 0)}",
                f"Active context turns {memory.get('short_term_turns', 0)}",
                f"Research records      {memory.get('research_items', 0)}",
                "",
                f"Current session       {current.get('title', 'Unknown')}",
                f"Session messages      {current.get('message_count', 0)}",
                f"Pinned                {'yes' if current.get('pinned') else 'no'}",
                "",
                "Use Conversations in the main window to search, pin, rename, export, or delete local history.",
            )
        )

    def _workflows(self) -> str:
        workflows = self.snapshot.get("workflows", {})
        lines = ["WORKFLOW REGISTRY", ""]
        templates = workflows.get("templates", {})
        if not templates:
            lines.append("No workflow templates registered.")
        for name, payload in templates.items():
            steps = payload.get("steps", []) if isinstance(payload, dict) else []
            lines.append(f"{name}  ({len(steps)} steps)")
            for index, step in enumerate(steps, start=1):
                lines.append(f"  {index}. {step}")
            lines.append("")
        lines.append(f"Pattern detection threshold: {workflows.get('detection_threshold', 0)} successful traces")
        lines.extend(("", "LAST EXECUTED PLAN"))
        last_plan = workflows.get("last_plan", [])
        if not last_plan:
            lines.append("No request has run in this process yet.")
        for node in last_plan:
            lines.append(
                f"- [{str(node.get('status', 'pending')).upper()}] "
                f"{node.get('description', node.get('task_id', 'Task'))}"
            )
        return "\n".join(lines)

    def _models(self) -> str:
        models = self.snapshot.get("models", {})
        runtime = models.get("runtime", {})
        lines = [
            "MODEL ROUTING & CACHE",
            "",
            f"Runtime enabled       {'yes' if runtime.get('enabled') else 'no (offline-safe)'}",
            f"Loaded models        {runtime.get('loaded_count', 0)}",
            f"Cache limit          {models.get('cache_limit', 0)}",
            f"Idle unload          {models.get('idle_ttl_seconds', 0)} seconds",
            "",
            "ROUTES",
        ]
        for role, alias in models.get("routes", {}).items():
            lines.append(f"- {role}: {alias}")
        return "\n".join(lines)

    def _tools(self) -> str:
        tools = self.snapshot.get("tools", {})
        lines = [
            "TOOLS & PERMISSIONS",
            "",
            "Allowed by default: " + ", ".join(tools.get("allowed_access", [])),
            "Workspace writes, processes, and network access require explicit approval.",
            "",
            "REGISTERED TOOLS",
        ]
        lines.extend(f"- {name}" for name in tools.get("registered", []))
        lines.extend(("", "RECENT DECISIONS"))
        decisions = tools.get("recent_decisions", [])
        if not decisions:
            lines.append("No permission decisions in this process.")
        for item in decisions:
            verdict = "allowed" if item.get("allowed") else "blocked"
            lines.append(f"- {item.get('tool')} / {item.get('access')} / {verdict} / {item.get('reason')}")
        return "\n".join(lines)

    def _system(self) -> str:
        system = self.snapshot.get("system", {})
        health = system.get("health", {})
        resources = system.get("resources", {})
        performance = system.get("performance", {})
        safe_health = {
            "status": health.get("status", "unknown"),
            "mode": health.get("mode", "unknown"),
            "database_ready": bool(health.get("database_ready")),
            "local_model_enabled": bool(health.get("local_model_enabled")),
            "interaction_logging_enabled": bool(health.get("interaction_logging_enabled")),
            "registered_tools": len(health.get("tools", [])),
            "allowed_access": list(health.get("allowed_access", [])),
        }
        return "\n".join(
            (
                "SYSTEM HEALTH",
                "",
                f"Status               {health.get('status', 'unknown')}",
                f"Database             {'ready' if health.get('database_ready') else 'not ready'}",
                f"CPU                  {resources.get('cpu_percent', 0)}%",
                f"System memory        {resources.get('memory_percent', 0)}%",
                f"NIRA process RSS     {resources.get('rss_mb', 0)} MB",
                f"Recorded operations  {int(performance.get('count', 0))}",
                f"Success rate         {performance.get('success_rate', 0):.1%}",
                f"Average duration     {performance.get('avg_duration_ms', 0)} ms",
                "",
                "PRIVACY-SAFE HEALTH CONTRACT",
                json.dumps(safe_health, indent=2, sort_keys=True),
            )
        )


class OperationsCenter:
    def __init__(self, parent: Any, runtime: Any) -> None:
        self.parent = parent
        self.runtime = runtime
        self.window = None
        self._notebook = None
        self._tab_widgets: dict[str, Any] = {}
        self._updated_var = None

    def open(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self.window.deiconify()
                    self.window.lift()
                    self.refresh()
                    return
            except tk.TclError:
                self.window = None

        window = tk.Toplevel(self.parent)
        self.window = window
        window.title("NIRA Operations Center")
        self._center_on_parent(window, 960, 680)
        window.minsize(760, 540)
        window.configure(bg="#08111b")
        window.transient(self.parent)

        shell = tk.Frame(window, bg="#08111b", padx=18, pady=18)
        shell.pack(fill="both", expand=True)
        header = tk.Frame(shell, bg="#08111b")
        header.pack(fill="x", pady=(0, 12))
        tk.Label(
            header,
            text="Operations Center",
            bg="#08111b",
            fg="#e2e8f0",
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left")
        self._updated_var = tk.StringVar(value="")
        tk.Label(
            header,
            textvariable=self._updated_var,
            bg="#08111b",
            fg="#94a3b8",
            font=("Segoe UI", 9),
        ).pack(side="right", padx=(12, 0))
        tk.Button(
            header,
            text="Refresh",
            command=self.refresh,
            bg="#38bdf8",
            fg="#082f49",
            relief="flat",
            bd=0,
            padx=14,
            pady=7,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        style = ttk.Style(window)
        style.theme_use("clam")
        style.configure("Nira.TNotebook", background="#08111b", borderwidth=0)
        style.configure(
            "Nira.TNotebook.Tab",
            background="#0f172a",
            foreground="#cbd5e1",
            padding=(11, 8),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Nira.TNotebook.Tab",
            background=[("selected", "#0369a1")],
            foreground=[("selected", "#f8fafc")],
        )
        notebook = ttk.Notebook(shell, style="Nira.TNotebook")
        self._notebook = notebook
        notebook.pack(fill="both", expand=True)
        window.bind("<Escape>", lambda _event: window.withdraw())
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        self.refresh()

    def _center_on_parent(self, window: Any, width: int, height: int) -> None:
        self.parent.update_idletasks()
        parent_width = max(self.parent.winfo_width(), width)
        parent_height = max(self.parent.winfo_height(), height)
        x = self.parent.winfo_rootx() + ((parent_width - width) // 2)
        y = self.parent.winfo_rooty() + ((parent_height - height) // 2)
        x = max(0, min(x, self.parent.winfo_screenwidth() - width))
        y = max(0, min(y, self.parent.winfo_screenheight() - height))
        window.geometry(f"{width}x{height}+{x}+{y}")

    def refresh(self) -> None:
        import tkinter as tk
        from tkinter import scrolledtext

        if self.window is None or self._notebook is None:
            return
        snapshot = self.runtime.product_snapshot()
        sections = OperationsCenterPresenter(snapshot).sections()
        for title, content in sections.items():
            widget = self._tab_widgets.get(title)
            if widget is None:
                frame = tk.Frame(self._notebook, bg="#0b1220", padx=14, pady=14)
                widget = scrolledtext.ScrolledText(
                    frame,
                    wrap="word",
                    bg="#0b1220",
                    fg="#dbeafe",
                    insertbackground="#dbeafe",
                    relief="flat",
                    bd=0,
                    padx=10,
                    pady=10,
                    font=("Consolas", 10),
                )
                widget.pack(fill="both", expand=True)
                self._notebook.add(frame, text=title)
                self._tab_widgets[title] = widget
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", content)
            widget.configure(state="disabled")
        if self._updated_var is not None:
            self._updated_var.set(f"Updated {snapshot.get('generated_at', '')}")

    def select_tab(self, title: str) -> None:
        if self._notebook is None:
            return
        titles = list(self._tab_widgets)
        if title in titles:
            self._notebook.select(titles.index(title))

    def hide(self) -> None:
        if self.window is None:
            return
        try:
            self.window.withdraw()
        except Exception:
            self.window = None
