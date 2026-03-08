from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from nira_agent.ai.confidence import ConfidenceScorer
from nira_agent.ai.llm_client import CloudFallbackClient, LocalLlamaClient
from nira_agent.ai.personality import PersonalityEngine
from nira_agent.ai.structured_output import StructuredOutputParser
from nira_agent.automation.manager import AutomationManager
from nira_agent.config import ConfigLoader
from nira_agent.core.confidence_engine import DecisionConfidenceEngine
from nira_agent.core.context_snapshot import ContextSnapshotEngine
from nira_agent.core.edr_analysis import EDRAnalyzer
from nira_agent.core.execution_controller import ExecutionController
from nira_agent.core.personality_middleware import PersonalityMiddleware
from nira_agent.core.risk_engine import RiskAssessment, RiskClassifier
from nira_agent.core.simulation import SimulationEngine
from nira_agent.core.syscall_profile import SyscallProfiler
from nira_agent.logging_setup import setup_logging
from nira_agent.memory.compressor import ConversationCompressor
from nira_agent.memory.context_builder import ContextBuilder
from nira_agent.memory.long_term import LongTermMemoryStore
from nira_agent.memory.manager import MemoryManager
from nira_agent.memory.preferences import UserPreferences
from nira_agent.memory.short_term import ShortTermMemory
from nira_agent.monitoring.activity import ActivityTracker
from nira_agent.monitoring.proactive import ProactiveCoordinator
from nira_agent.monitoring.triggers import TriggerEngine
from nira_agent.performance import PerformanceGuard, PerformanceLimits
from nira_agent.routing.cache import TTLCache
from nira_agent.routing.hybrid_router import HybridRouter
from nira_agent.security.audit import SecureAuditLogger
from nira_agent.security.auth import PassphraseAuth, SecurityTierEnforcer
from nira_agent.security.encryption import EncryptionManager
from nira_agent.storage.sql_store import DBConfig, SQLStore
from nira_agent.system_validation import run_system_health_checks
from nira_agent.ui.app_state import StateStore


logger = logging.getLogger(__name__)


class NiraRuntime:
    """Production-oriented runtime with a centralized execution controller."""

    def __init__(self) -> None:
        self.cfg = ConfigLoader().load()
        setup_logging(Path.home() / ".nira_agent" / "logs" / "runtime.log")

        self.sql_store = SQLStore(
            DBConfig(
                host=self.cfg.db_host,
                port=self.cfg.db_port,
                user=self.cfg.db_user,
                password=self.cfg.db_password,
                database=self.cfg.db_name,
            ),
            enabled=self.cfg.sql_enabled,
        )
        if self.sql_store.available:
            logger.info("SQL storage enabled: %s", self.cfg.db_settings())
        else:
            logger.warning("SQL storage unavailable; file fallback remains active.")

        self.encryption = EncryptionManager(
            key_env=self.cfg.encrypt_key_env,
            passphrase_env=self.cfg.passphrase_env,
        )
        self.audit = SecureAuditLogger(self.encryption, sql_store=self.sql_store)
        self.passphrase_auth = PassphraseAuth(env_key=self.cfg.passphrase_env)
        self.tier_enforcer = SecurityTierEnforcer(current_tier=self.cfg.permission_default)

        self.preferences = UserPreferences(sql_store=self.sql_store)
        mode = self.preferences.get("mode", "focus")
        self.state = StateStore()
        self.personality = PersonalityEngine(mode)
        self.state.update(mode=self.personality.current().name, tone=self.personality.current().tone)
        self.personality_middleware = PersonalityMiddleware(cooldown_sec=12, emotional_ttl_sec=900)

        self.short_term = ShortTermMemory(
            max_turns=self.cfg.max_history_turns,
            compress_every_n_turns=self.cfg.compress_every_n_turns,
            token_threshold=self.cfg.memory_compress_token_threshold,
        )
        self.long_term = LongTermMemoryStore(self.encryption, sql_store=self.sql_store)
        self.memory = MemoryManager(
            short_term=self.short_term,
            long_term=self.long_term,
            compressor=ConversationCompressor(),
        )
        self.context_builder = ContextBuilder()

        self.performance = PerformanceGuard(
            PerformanceLimits(
                cpu_throttle_ms=self.cfg.cpu_throttle_ms,
                inference_cooldown_ms=self.cfg.inference_cooldown_ms,
                max_context_chars=self.cfg.max_context_chars,
            )
        )
        self.executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="nira-agent")
        self.route_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="nira-route")

        local = LocalLlamaClient(
            base_url=self.cfg.local_llm_base_url,
            timeout_sec=self.cfg.local_llm_timeout_sec,
            model=self.cfg.local_llm_model,
        )
        cloud = CloudFallbackClient(
            endpoint=self.cfg.cloud_endpoint if self.cfg.cloud_fallback_enabled else None,
            api_key=self.cfg.cloud_api_key if self.cfg.cloud_fallback_enabled else None,
            timeout_sec=self.cfg.cloud_timeout_sec,
        )
        self.router = HybridRouter(
            local_client=local,
            cloud_client=cloud,
            scorer=ConfidenceScorer(),
            parser=StructuredOutputParser(),
            cache=TTLCache(ttl_sec=self.cfg.route_cache_ttl_sec, max_items=self.cfg.route_cache_max_items),
            escalation_threshold=self.cfg.escalation_threshold,
            manual_cloud_escalation_only=self.cfg.manual_cloud_escalation_only,
        )

        # Controller owns risk/confirmation gates; tool engine confirmation is neutralized.
        self.automation = AutomationManager(permission_level=self.cfg.permission_default, confirm_fn=lambda _call: True)
        self.workflow_path = self._resolve_workflow_path(self.cfg.dsl_workflow_file)
        workflow_result = self.automation.load_workflows_if_exists(self.workflow_path)
        logger.info("Workflow load status: %s", workflow_result.output)

        self.trigger_engine = TriggerEngine(self.cfg.distraction_apps)
        self.proactive = ProactiveCoordinator(self.trigger_engine, cooldown_sec=self.cfg.proactive_cooldown_sec)
        self.activity = ActivityTracker(interval_sec=self.cfg.monitor_interval_sec)
        self._last_suggestion: str | None = None
        self._suggestion_lock = threading.Lock()
        self.activity.subscribe(self._on_activity_event)

        self.controller = ExecutionController(
            cfg=self.cfg,
            router=self.router,
            automation=self.automation,
            memory=self.memory,
            short_term=self.short_term,
            long_term=self.long_term,
            context_builder=self.context_builder,
            state_store=self.state,
            personality=self.personality,
            personality_middleware=self.personality_middleware,
            context_snapshot_engine=ContextSnapshotEngine(project_root=Path.cwd()),
            risk_classifier=RiskClassifier(self.automation.registry, project_root=Path.cwd()),
            edr_analyzer=EDRAnalyzer(),
            syscall_profiler=SyscallProfiler(),
            simulation_engine=SimulationEngine(),
            confidence_engine=DecisionConfidenceEngine(threshold=self.cfg.clarification_threshold),
            performance=self.performance,
            route_executor=self.route_executor,
            llm_timeout_sec=self.cfg.llm_route_timeout_sec,
            audit=self.audit,
            sql_store=self.sql_store,
            confirm_callback=self._confirm_high_risk_execution,
            critical_phrase_callback=self._confirm_critical_phrase,
            activity_getter=self.proactive.latest_event,
            proactive_hint_getter=self._consume_proactive_hint,
        )

        self._pending_lock = threading.Lock()
        self._pending_futures: set[Future] = set()
        self._print_lock = threading.Lock()

    def start(self) -> None:
        logger.info("Nira runtime started")
        self.audit.log("startup", {"mode": self.personality.current().name})
        self.activity.start()
        self._cli_loop()

    def _cli_loop(self) -> None:
        print(
            "Nira Hybrid Agent ready. Commands: /exit, /mode <Focus|Calm|Strategy|Night>, "
            "/undo, /dnd <on|off>, /cloud <prompt>, /health"
        )
        while True:
            try:
                user_input = input("\nYou> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break

            if not user_input:
                continue
            if user_input.lower() == "/exit":
                break

            if self._handle_command(user_input):
                continue

            self._submit_interaction(user_input, manual_cloud=False)

        self.shutdown()

    def _handle_command(self, cmd: str) -> bool:
        lower = cmd.lower()
        if lower.startswith("/mode "):
            mode = cmd.split(" ", 1)[1].strip()
            current = self.personality.set_mode(mode)
            self.state.update(mode=current.name, tone=current.tone)
            self.preferences.set("mode", mode.lower())
            print(f"Nira> Mode switched to {current.name}.")
            return True

        if lower == "/undo":
            result = self.automation.undo_last()
            print(f"Nira> {result.output}")
            self.audit.log("undo", {"ok": result.ok, "message": result.output})
            return True

        if lower.startswith("/dnd "):
            value = cmd.split(" ", 1)[1].strip().lower()
            enabled = value in {"1", "on", "true", "yes"}
            self.state.update(dnd=enabled)
            print(f"Nira> DND {'enabled' if enabled else 'disabled'}.")
            return True

        if lower.startswith("/cloud "):
            prompt = cmd.split(" ", 1)[1].strip()
            self._submit_interaction(prompt, manual_cloud=True)
            return True

        if lower == "/health":
            report = run_system_health_checks(self)
            print(f"Nira> System health {'OK' if report.ok else 'DEGRADED'}")
            print(report.to_json())
            return True

        return False

    def _submit_interaction(self, user_input: str, manual_cloud: bool) -> None:
        future = self.executor.submit(self._run_interaction_task, user_input, manual_cloud)
        with self._pending_lock:
            self._pending_futures.add(future)
        future.add_done_callback(self._on_interaction_done)

    def _on_interaction_done(self, future: Future) -> None:
        with self._pending_lock:
            self._pending_futures.discard(future)
        try:
            response = future.result()
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            response = f"Internal error: {exc}"
            logger.exception("Interaction task failed")
        with self._print_lock:
            print(f"\nNira> {response}")

    def _run_interaction_task(self, user_input: str, manual_cloud: bool) -> str:
        result = self.controller.process(user_input=user_input, manual_cloud=manual_cloud)
        return result.text

    def _confirm_high_risk_execution(self, call, risk: RiskAssessment) -> bool:
        # High and critical operations always require explicit user confirmation.
        check = self.tier_enforcer.confirm_dangerous(
            call=call,
            passphrase_auth=self.passphrase_auth,
            provided_passphrase=None,
        )
        if not check.allowed:
            print(f"Nira> Additional authentication required for '{call.tool}'.")
            candidate = input("Passphrase (or blank to cancel): ").strip()
            verify = self.passphrase_auth.verify(candidate)
            if not verify.allowed:
                print(f"Nira> {verify.reason}")
                return False
        confirm = input(f"Type YES to run '{call.tool}' ({risk.level} risk): ").strip()
        return confirm == "YES"

    @staticmethod
    def _confirm_critical_phrase(expected_phrase: str, call) -> bool:
        if not expected_phrase:
            return False
        typed = input(f"Type exact phrase '{expected_phrase}' for '{call.tool}': ").strip()
        return typed == expected_phrase

    def _on_activity_event(self, event) -> None:
        suggestion = self.proactive.on_event(
            event=event,
            dnd=bool(self.state.get().dnd),
            proactive_enabled=self.cfg.proactive_enabled,
        )
        if suggestion:
            with self._suggestion_lock:
                self._last_suggestion = suggestion

    def _consume_proactive_hint(self) -> str:
        with self._suggestion_lock:
            value = self._last_suggestion or self.proactive.system_state_hint()
            self._last_suggestion = None
        return value

    @staticmethod
    def _resolve_workflow_path(filename: str) -> Path:
        cwd_path = Path.cwd() / filename
        if cwd_path.exists():
            return cwd_path
        package_path = Path(__file__).resolve().parent / filename
        return package_path

    def shutdown(self) -> None:
        self.activity.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.route_executor.shutdown(wait=False, cancel_futures=True)
        self.audit.log("shutdown", {"status": "ok"})
        logger.info("Nira runtime stopped")


def main() -> int:
    runtime = NiraRuntime()
    runtime.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
