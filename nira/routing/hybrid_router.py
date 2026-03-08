from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from nira_agent.ai.confidence import ConfidenceScorer
from nira_agent.ai.llm_client import CloudFallbackClient, LLMTextResult, LocalLlamaClient
from nira_agent.ai.structured_output import StructuredModelOutput, StructuredOutputParser
from nira_agent.routing.cache import TTLCache


logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    output: StructuredModelOutput
    provider: str
    confidence: float
    used_cache: bool
    escalated: bool
    errors: list[str]


class HybridRouter:
    def __init__(
        self,
        local_client: LocalLlamaClient,
        cloud_client: CloudFallbackClient,
        scorer: ConfidenceScorer,
        parser: StructuredOutputParser,
        cache: TTLCache[RouteDecision],
        escalation_threshold: float,
        manual_cloud_escalation_only: bool,
    ) -> None:
        self.local_client = local_client
        self.cloud_client = cloud_client
        self.scorer = scorer
        self.parser = parser
        self.cache = cache
        self.escalation_threshold = escalation_threshold
        self.manual_cloud_escalation_only = manual_cloud_escalation_only

    def route(
        self,
        system_prompt: str,
        user_prompt: str,
        escalate_to_cloud: bool = False,
    ) -> RouteDecision:
        key = self._cache_key(system_prompt, user_prompt, escalate_to_cloud)
        cached = self.cache.get(key)
        if cached:
            return RouteDecision(
                output=cached.output,
                provider=cached.provider,
                confidence=cached.confidence,
                used_cache=True,
                escalated=cached.escalated,
                errors=list(cached.errors),
            )

        errors: list[str] = []
        local_raw = self.local_client.generate(system_prompt, user_prompt)
        if not local_raw.ok:
            errors.append(f"local: {local_raw.error}")

        local_decision = self._build_decision(local_raw, user_prompt, errors)
        should_escalate = self._should_escalate(local_decision, escalate_to_cloud)
        if not should_escalate:
            self.cache.set(key, local_decision)
            return local_decision

        cloud_raw = self.cloud_client.generate(system_prompt, user_prompt)
        if not cloud_raw.ok:
            errors.append(f"cloud: {cloud_raw.error}")
            local_decision.errors = errors
            self.cache.set(key, local_decision)
            return local_decision

        cloud_decision = self._build_decision(cloud_raw, user_prompt, errors, escalated=True)
        self.cache.set(key, cloud_decision)
        return cloud_decision

    def _build_decision(
        self,
        raw: LLMTextResult,
        user_prompt: str,
        errors: list[str],
        escalated: bool = False,
    ) -> RouteDecision:
        output = self.parser.parse(raw.text if raw.ok else "")
        confidence = self.scorer.score(user_prompt, output)
        return RouteDecision(
            output=output,
            provider=raw.provider,
            confidence=confidence,
            used_cache=False,
            escalated=escalated,
            errors=list(errors),
        )

    def _should_escalate(self, local_decision: RouteDecision, manual_request: bool) -> bool:
        if not self.cloud_client.is_configured():
            return False
        if manual_request:
            return True
        if self.manual_cloud_escalation_only:
            return False
        return local_decision.confidence < self.escalation_threshold

    @staticmethod
    def _cache_key(system_prompt: str, user_prompt: str, escalate: bool) -> str:
        payload = f"{system_prompt}\n::{user_prompt}\n::{int(escalate)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

