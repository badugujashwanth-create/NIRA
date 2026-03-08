from __future__ import annotations

import logging
import re
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Callable

from nira_agent.ai.intent_parser import Intent, IntentParser
from nira_agent.ai.prompting import build_clarification_prompt
from nira_agent.ai.structured_output import StructuredModelOutput
from nira_agent.automation.manager import AutomationManager
from nira_agent.automation.models import ToolCall, ToolResult
from nira_agent.core.confidence_engine import DecisionConfidenceEngine
from nira_agent.core.context_snapshot import ContextSnapshotEngine
from nira_agent.core.edr_analysis import EDRAnalyzer
from nira_agent.core.exceptions import ExecutionTimeout, RiskViolation, SimulationError, ToolFailure, ValidationError
from nira_agent.core.personality_middleware import PersonalityMiddleware
from nira_agent.core.risk_engine import RiskAssessment, RiskClassifier
from nira_agent.core.simulation import SimulationEngine
from nira_agent.core.syscall_profile import SyscallProfiler
from nira_agent.memory.manager import MemoryManager
from nira_agent.memory.short_term import ShortTermMemory
from nira_agent.performance import PerformanceGuard
from nira_agent.routing.hybrid_router import HybridRouter, RouteDecision


logger = logging.getLogger(__name__)


ConfirmCallback = Callable[[ToolCall, RiskAssessment], bool]
CriticalPhraseCallback = Callable[[str, ToolCall], bool]
ActivityGetter = Callable[[], object | None]
HintGetter = Callable[[], str]


@dataclass
class ControllerResult:
    text: str
    confidence: float
    provider: str
    escalated: bool
    tool_results: list[ToolResult]
    errors: list[str]


class ExecutionController:
    """Centralized execution pipeline for backend reasoning and tool safety."""

    def __init__(
        self,
        *,
        cfg,
        router: HybridRouter,
        automation: AutomationManager,
        memory: MemoryManager,
        short_term: ShortTermMemory,
        long_term,
        context_builder,
        state_store,
        personality,
        personality_middleware: PersonalityMiddleware,
        context_snapshot_engine: ContextSnapshotEngine,
        risk_classifier: RiskClassifier,
        edr_analyzer: EDRAnalyzer,
        syscall_profiler: SyscallProfiler,
        simulation_engine: SimulationEngine,
        confidence_engine: DecisionConfidenceEngine,
        performance: PerformanceGuard,
        route_executor: ThreadPoolExecutor,
        llm_timeout_sec: int,
        audit,
        sql_store,
        confirm_callback: ConfirmCallback,
        critical_phrase_callback: CriticalPhraseCallback,
        activity_getter: ActivityGetter,
        proactive_hint_getter: HintGetter,
    ) -> None:
        self.cfg = cfg
        self.router = router
        self.automation = automation
        self.memory = memory
        self.short_term = short_term
        self.long_term = long_term
        self.context_builder = context_builder
        self.state = state_store
        self.personality = personality
        self.personality_middleware = personality_middleware
        self.snapshot_engine = context_snapshot_engine
        self.risk_classifier = risk_classifier
        self.edr_analyzer = edr_analyzer
        self.syscall_profiler = syscall_profiler
        self.simulation_engine = simulation_engine
        self.confidence_engine = confidence_engine
        self.performance = performance
        self.route_executor = route_executor
        self.llm_timeout_sec = llm_timeout_sec
        self.audit = audit
        self.sql_store = sql_store
        self.confirm_callback = confirm_callback
        self.critical_phrase_callback = critical_phrase_callback
        self.activity_getter = activity_getter
        self.proactive_hint_getter = proactive_hint_getter

        self.intent_parser = IntentParser()
        self._pipeline_lock = threading.Lock()
        self._tool_usage: dict[str, int] = {}
        self._tool_history: dict[str, tuple[int, int]] = {}
        self._recent_failures: deque[str] = deque(maxlen=12)

    def process(self, user_input: str, manual_cloud: bool = False) -> ControllerResult:
        if not self.performance.wait_for_inference_slot(timeout_sec=10):
            return ControllerResult(
                text="System is busy. Please retry in a moment.",
                confidence=0.0,
                provider="local",
                escalated=False,
                tool_results=[],
                errors=["busy"],
            )
        if not self._pipeline_lock.acquire(blocking=False):
            return ControllerResult(
                text="Another request is running. Please wait until it completes.",
                confidence=0.0,
                provider="local",
                escalated=False,
                tool_results=[],
                errors=["pipeline_locked"],
            )

        decision: RouteDecision | None = None
        tool_results: list[ToolResult] = []
        confidence_score = 0.0
        final_text = ""
        errors: list[str] = []
        pipeline: list[str] = []

        try:
            self.personality_middleware.ingest_user_text(user_input)
            self.state.update(last_user_input=user_input)
            self.memory.add_user_turn(user_input)

            # 1) user_input
            pipeline.append("user_input")
            # 2) intent_analysis
            intent = self.intent_parser.parse(user_input)
            pipeline.append("intent_analysis")

            # 3) context_snapshot
            snapshot = self.snapshot_engine.build(
                activity_event=self.activity_getter(),
                recent_tool_failures=list(self._recent_failures),
                tool_usage=self._tool_usage,
            )
            pipeline.append("context_snapshot")
            recent_turns = self.short_term.snapshot()[-2:]
            recent_hint = " | ".join(f"{t.role}:{self._compact(t.content, 36)}" for t in recent_turns)
            routing_context = self._build_routing_context(
                snapshot=snapshot,
                memory_summary=self.memory.latest_summary,
                recent_hint=recent_hint,
                proactive_hint=self.proactive_hint_getter(),
            )

            # 4) edr_analysis (pre-route estimation from intent)
            intent_call = self._intent_to_call(intent)
            pre_edr = self.edr_analyzer.analyze(intent_call) if intent_call else None
            pipeline.append("edr_analysis")

            # 5) syscall_profile_analysis (pre-route estimation from intent)
            pre_syscall = self.syscall_profiler.project(intent_call) if intent_call else None
            pipeline.append("syscall_profile_analysis")

            # 6) hybrid_router
            system_prompt = self.personality.build_system_prompt()
            prompt = self._build_router_prompt(
                user_input=user_input,
                context_block=routing_context,
                intent=intent,
                pre_edr_summary=(pre_edr.summary if pre_edr else "N/A"),
                pre_syscall_summary=(self._syscall_summary(pre_syscall) if pre_syscall else "N/A"),
            )
            decision = self._route_with_timeout(system_prompt, prompt, manual_cloud)
            pipeline.append("hybrid_router")

            # 7) structured_decision
            output = decision.output
            calls, parse_result = self.automation.parse_model_tool_calls(output)
            if not output.json_valid or not output.schema_valid or not parse_result.ok:
                raise ValidationError(
                    "Structured decision invalid.",
                    {
                        "json_valid": output.json_valid,
                        "schema_valid": output.schema_valid,
                        "validation_errors": output.validation_errors,
                        "parse_error": parse_result.output,
                    },
                )
            command = calls[0] if calls else None
            pipeline.append("structured_decision")
            if len(calls) > 1:
                logger.warning("Only one command allowed per request; truncating %s calls.", len(calls))
                self.audit.log("command_truncated", {"original_count": len(calls), "kept": command.tool if command else ""})

            # 8) risk_classification
            risk_items: list[RiskAssessment] = []
            spec = None
            if command:
                command, spec = self.risk_classifier.sanitize_and_validate(command)
                risk_items = [self.risk_classifier.classify(command, spec)]
            pipeline.append("risk_classification")

            confidence = self.confidence_engine.evaluate(
                user_input=user_input,
                output=output,
                registry=self.automation.registry,
                context_snapshot=snapshot,
                risk_assessments=risk_items,
                historical_success=self._tool_history,
            )
            confidence_score = confidence.score
            if confidence.needs_clarification:
                raw_response = build_clarification_prompt(user_input)
                errors.extend(confidence.reasons)
                self._update_memory(user_input, raw_response)
                pipeline.append("memory_update")
                final_text = self._redact_system_data(raw_response, snapshot)
                pipeline.append("response_generation")
                final_text = self._apply_personality(final_text)
                pipeline.append("personality_filter")
                self._log_interaction(user_input, final_text, confidence_score, decision, tool_results, errors, pipeline)
                return ControllerResult(
                    text=final_text,
                    confidence=confidence_score,
                    provider=decision.provider,
                    escalated=decision.escalated,
                    tool_results=tool_results,
                    errors=errors,
                )

            if command:
                risk = risk_items[0]
                if risk.warning_message:
                    self.audit.log("risk_warning", {"tool": command.tool, "level": risk.level, "warning": risk.warning_message})

                edr = self.edr_analyzer.analyze(command)
                projection = self.syscall_profiler.project(command)

                # 9) simulation_if_needed
                simulation = None
                if risk.level in {"high", "critical"}:
                    simulation = self.simulation_engine.simulate(command, risk, edr, projection)
                    self.simulation_engine.persist(self.sql_store, command, risk, simulation)
                    self.audit.log(
                        "simulation",
                        {
                            "tool": command.tool,
                            "risk": risk.level,
                            "summary": simulation.summary,
                        },
                    )
                pipeline.append("simulation_if_needed")

                # 10) confirmation_if_required
                if risk.requires_confirmation:
                    confirmed = self.confirm_callback(command, risk)
                    phrase_ok = True
                    if risk.level == "critical":
                        phrase_ok = self.critical_phrase_callback(risk.exact_confirmation_phrase, command)
                    self.risk_classifier.enforce_confirmation(risk, confirmed=confirmed, phrase_ok=phrase_ok)
                pipeline.append("confirmation_if_required")

                # 11) execution
                tool_result = self._execute_one(command, projection)
                tool_results.append(tool_result)
                self._record_tool_history(command.tool, tool_result.ok)
                pipeline.append("execution")

                # 7b) tool failure repair loop (max one retry)
                if not tool_result.ok:
                    repaired_output = self._repair_once(
                        user_input=user_input,
                        context_text=routing_context,
                        system_prompt=system_prompt,
                        failed_call=command,
                        failed_result=tool_result,
                        manual_cloud=manual_cloud,
                    )
                    if repaired_output is None:
                        raise ToolFailure(f"Tool execution failed after one repair attempt: {tool_result.output}")
                    output = repaired_output

                # 12) reflection
                feedback = self.automation.tool_feedback_text(tool_results)
                reflection_prompt = self._build_reflection_prompt(user_input, feedback, routing_context)
                reflection = self._route_with_timeout(system_prompt, reflection_prompt, manual_cloud)
                if reflection.output.message.strip():
                    output = reflection.output
                pipeline.append("reflection")

            # 13) memory_update + 14) response_generation
            raw_response = output.message.strip() if output.message.strip() else "Task completed."
            if tool_results and any(not row.ok for row in tool_results):
                raw_response = "Execution failed safely. Please refine the request."
            self._update_memory(user_input, raw_response)
            pipeline.append("memory_update")
            final_text = self._redact_system_data(raw_response, snapshot)
            pipeline.append("response_generation")

            # 15) personality_filter
            final_text = self._apply_personality(final_text)
            pipeline.append("personality_filter")
            self._log_interaction(user_input, final_text, confidence_score, decision, tool_results, errors, pipeline)
            return ControllerResult(
                text=final_text,
                confidence=confidence_score,
                provider=decision.provider,
                escalated=decision.escalated,
                tool_results=tool_results,
                errors=errors,
            )
        except (ValidationError, RiskViolation, SimulationError, ToolFailure, ExecutionTimeout) as exc:
            logger.warning("Controlled pipeline error: %s", exc)
            errors.append(str(exc))
            raw_fallback = self._user_safe_error(exc)
            if decision is None:
                decision = self._empty_decision()
            self._update_memory(user_input, raw_fallback)
            pipeline.append("memory_update")
            fallback = raw_fallback
            pipeline.append("response_generation")
            fallback = self._apply_personality(fallback)
            pipeline.append("personality_filter")
            self._log_interaction(user_input, fallback, confidence_score, decision, tool_results, errors, pipeline)
            return ControllerResult(
                text=fallback,
                confidence=confidence_score,
                provider=decision.provider,
                escalated=decision.escalated,
                tool_results=tool_results,
                errors=errors,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("Unhandled controller error")
            errors.append(str(exc))
            raw_fallback = "Internal error occurred. Execution aborted safely."
            if decision is None:
                decision = self._empty_decision()
            self._update_memory(user_input, raw_fallback)
            pipeline.append("memory_update")
            fallback = raw_fallback
            pipeline.append("response_generation")
            fallback = self._apply_personality(fallback)
            pipeline.append("personality_filter")
            self._log_interaction(user_input, fallback, confidence_score, decision, tool_results, errors, pipeline)
            return ControllerResult(
                text=fallback,
                confidence=confidence_score,
                provider=decision.provider,
                escalated=decision.escalated,
                tool_results=tool_results,
                errors=errors,
            )
        finally:
            self.performance.throttle_cpu()
            self._pipeline_lock.release()

    def _route_with_timeout(self, system_prompt: str, user_prompt: str, manual_cloud: bool) -> RouteDecision:
        future = self.route_executor.submit(self.router.route, system_prompt, user_prompt, manual_cloud)
        try:
            return future.result(timeout=self.llm_timeout_sec)
        except TimeoutError as exc:
            raise ExecutionTimeout(f"Routing timeout after {self.llm_timeout_sec}s") from exc
        except Exception as exc:
            raise ValidationError(f"Routing failed: {exc}") from exc

    def _execute_one(self, call: ToolCall, projection) -> ToolResult:
        start = self.syscall_profiler.begin()
        result = self.automation.engine.execute(call)
        profile = self.syscall_profiler.end(call=call, start_token=start, ok=result.ok, projection=projection)
        self.syscall_profiler.persist(self.sql_store, profile)
        if not result.ok:
            self._recent_failures.append(f"{call.tool}: {result.output}")
        self._tool_usage[call.tool] = self._tool_usage.get(call.tool, 0) + 1
        return result

    def _repair_once(
        self,
        *,
        user_input: str,
        context_text: str,
        system_prompt: str,
        failed_call: ToolCall,
        failed_result: ToolResult,
        manual_cloud: bool,
    ) -> StructuredModelOutput | None:
        repair_prompt = (
            "Tool execution failed. Propose one corrected command only.\n"
            "Output strict JSON schema with keys: message, tool_calls, confidence, goal_achieved.\n"
            f"User input: {user_input}\n"
            f"Failed command: {failed_call.tool} args={failed_call.args}\n"
            f"Failure: {failed_result.output}\n"
            f"Context: {context_text}\n"
            "Do not repeat the same failing arguments."
        )
        decision = self._route_with_timeout(system_prompt, repair_prompt, manual_cloud)
        output = decision.output
        calls, parse_result = self.automation.parse_model_tool_calls(output)
        if not parse_result.ok or not calls:
            self._log_repair_attempt(failed_call.tool, 1, failed_result.output, False)
            return None

        repaired_call = calls[0]
        repaired_call, spec = self.risk_classifier.sanitize_and_validate(repaired_call)
        risk = self.risk_classifier.classify(repaired_call, spec)
        if risk.level in {"high", "critical"}:
            simulation = self.simulation_engine.simulate(
                repaired_call,
                risk,
                self.edr_analyzer.analyze(repaired_call),
                self.syscall_profiler.project(repaired_call),
            )
            self.simulation_engine.persist(self.sql_store, repaired_call, risk, simulation)
        if risk.requires_confirmation:
            confirmed = self.confirm_callback(repaired_call, risk)
            phrase_ok = True
            if risk.level == "critical":
                phrase_ok = self.critical_phrase_callback(risk.exact_confirmation_phrase, repaired_call)
            self.risk_classifier.enforce_confirmation(risk, confirmed=confirmed, phrase_ok=phrase_ok)

        result = self._execute_one(repaired_call, self.syscall_profiler.project(repaired_call))
        self._record_tool_history(repaired_call.tool, result.ok)
        self._log_repair_attempt(repaired_call.tool, 1, failed_result.output, result.ok)
        if not result.ok:
            return None
        return output

    def _log_repair_attempt(self, command: str, attempt: int, error_text: str, success: bool) -> None:
        if self.sql_store:
            self.sql_store.insert_repair_attempt(
                command_name=command,
                attempt_no=attempt,
                error_text=error_text,
                success=success,
            )
        self.audit.log(
            "repair_attempt",
            {
                "command": command,
                "attempt": attempt,
                "error": error_text,
                "success": success,
            },
        )

    def _record_tool_history(self, tool_name: str, success: bool) -> None:
        ok, fail = self._tool_history.get(tool_name, (0, 0))
        if success:
            ok += 1
        else:
            fail += 1
        self._tool_history[tool_name] = (ok, fail)

    def _update_memory(self, user_input: str, response_text: str) -> None:
        self.state.update(last_response=response_text)
        self.memory.add_assistant_turn(response_text)
        self.long_term.append("interaction", f"user={user_input} | assistant={response_text}")

    def _log_interaction(
        self,
        user_input: str,
        final_text: str,
        confidence: float,
        decision: RouteDecision,
        tool_results: list[ToolResult],
        errors: list[str],
        pipeline: list[str],
    ) -> None:
        self.audit.log(
            "interaction",
            {
                "input": user_input,
                "response": final_text,
                "confidence": confidence,
                "provider": decision.provider,
                "escalated": decision.escalated,
                "tool_results": [r.__dict__ for r in tool_results],
                "errors": errors,
                "pipeline": pipeline,
            },
        )

    def _apply_personality(self, text: str) -> str:
        mode = self.personality.current()
        return self.personality_middleware.apply(text, tone=mode.tone, mode_name=mode.name)

    @staticmethod
    def _redact_system_data(text: str, snapshot) -> str:
        redacted = text
        sensitive_fragments = [
            snapshot.current_project_path,
            snapshot.active_window,
            *snapshot.recently_modified_files,
        ]
        for token in sensitive_fragments:
            if not token or token == "N/A":
                continue
            if token in redacted:
                redacted = redacted.replace(token, "[redacted]")
        return redacted

    @staticmethod
    def _syscall_summary(projection) -> str:
        return (
            f"intensity={projection.syscall_intensity}; "
            f"cost={projection.kernel_transition_cost}; "
            f"subsystems={','.join(projection.subsystem_involvement)}"
        )

    def _build_router_prompt(
        self,
        *,
        user_input: str,
        context_block: str,
        intent: Intent,
        pre_edr_summary: str,
        pre_syscall_summary: str,
    ) -> str:
        scoped_tools = self._intent_scoped_tools(intent)
        tools = ", ".join(scoped_tools) if scoped_tools else "none"
        return (
            "JSON only: message,tool_calls,confidence,goal_achieved(optional); max one tool_call.\n"
            f"intent={intent.kind}/{intent.action}; edr={self._compact(pre_edr_summary, 56)}; "
            f"sys={self._compact(pre_syscall_summary, 48)}; tools={tools}; "
            f"ctx={context_block}; user={self._compact(user_input, 96)}"
        )

    def _build_reflection_prompt(self, user_input: str, tool_feedback: str, context_block: str) -> str:
        return (
            "Return strict JSON with keys: message, tool_calls, confidence, goal_achieved.\n"
            "If goal achieved set goal_achieved=true and tool_calls=[].\n"
            f"User: {self._compact(user_input, 180)}\n"
            f"ToolFeedback: {self._compact(tool_feedback, 220)}\n"
            f"Context: {context_block}\n"
        )

    def _build_routing_context(self, snapshot, memory_summary: str, recent_hint: str, proactive_hint: str) -> str:
        # Keep routing context compact to avoid slow local-model prompt evaluation.
        snap = (
            f"time={snapshot.time_of_day}; idle={int(snapshot.user_idle_duration_sec)}s; "
            f"window={self._compact(snapshot.active_window, 20)}; "
            f"proj={self._compact(snapshot.current_project_path.split('\\\\')[-1], 16)}; "
            f"freq_tools={','.join(snapshot.frequently_used_tools[:2]) or 'none'}; "
            f"failures={','.join(snapshot.recent_tool_failures[-2:]) or 'none'}"
        )
        mem = self._compact(memory_summary or "none", 28)
        recent = self._compact(recent_hint or "none", 34)
        proactive = self._compact(proactive_hint or "none", 28)
        raw = f"{snap}; mem={mem}; recent={recent}; proactive={proactive}"
        limit = int(getattr(self.cfg, "route_context_chars", 320))
        return self._compact(raw, max(80, min(120, limit)))

    @staticmethod
    def _compact(text: str, limit: int) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: max(8, limit - 3)] + "..."

    def _intent_scoped_tools(self, intent: Intent) -> list[str]:
        all_tools = set(self.automation.registry.list_tools())
        action = intent.action.strip()
        if action in all_tools:
            return [action]
        if intent.kind == "llm" or action in {"none", "chat"}:
            return []
        preferred = ["read_file", "list_directory", "write_file", "open_app", "open_url", "run_workflow"]
        return [name for name in preferred if name in all_tools][:3]

    @staticmethod
    def _intent_to_call(intent: Intent) -> ToolCall | None:
        if intent.kind not in {"automation", "workflow"}:
            return None
        action = intent.action.strip()
        if not action or action in {"none", "chat", "undo", "run_mode"}:
            return None
        return ToolCall(tool=action, args=dict(intent.args))

    @staticmethod
    def _user_safe_error(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            return "I need clearer details before executing that. Please provide specific target and parameters."
        if isinstance(exc, RiskViolation):
            return "Execution blocked by risk policy. Provide explicit confirmation to continue."
        if isinstance(exc, SimulationError):
            return "High-risk simulation failed, so execution was not started."
        if isinstance(exc, ExecutionTimeout):
            return "Model routing timed out. Please retry."
        if isinstance(exc, ToolFailure):
            return "Tool execution failed twice and was aborted safely."
        return "Request could not be completed safely."

    @staticmethod
    def _empty_decision() -> RouteDecision:
        return RouteDecision(
            output=StructuredModelOutput(
                message="",
                tool_calls=[],
                confidence=0.0,
                json_valid=False,
                schema_valid=False,
                validation_errors=["no_decision"],
                raw="",
            ),
            provider="local",
            confidence=0.0,
            used_cache=False,
            escalated=False,
            errors=["no_decision"],
        )
