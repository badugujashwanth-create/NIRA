from __future__ import annotations

from collections import deque

class PatternDetector:
    def __init__(self, threshold: int = 2, max_patterns: int = 256) -> None:
        self.threshold = max(2, threshold)
        self._counts: dict[str, int] = {}
        self._recent = deque(maxlen=max_patterns)

    def observe(self, trace: list[str]) -> tuple[bool, str]:
        normalized = " -> ".join(trace)
        if normalized not in self._counts and len(self._recent) == self._recent.maxlen and self._recent:
            oldest = self._recent.popleft()
            self._counts.pop(oldest, None)
        if normalized not in self._counts:
            self._recent.append(normalized)
        self._counts[normalized] = self._counts.get(normalized, 0) + 1
        return self._counts[normalized] >= self.threshold, normalized
