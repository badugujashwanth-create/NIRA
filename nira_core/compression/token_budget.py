from __future__ import annotations

from dataclasses import dataclass

from nira_core.inference import estimate_tokens


@dataclass(frozen=True, slots=True)
class BudgetedText:
    """A text chunk admitted by the context budgeter."""

    text: str
    tokens: int


class ContextBudgeter:
    """Hard final-context limiter for low KV-cache pressure."""

    def __init__(self, max_tokens: int = 400) -> None:
        self.max_tokens = max_tokens

    def trim(self, text: str, reserved_tokens: int = 0) -> BudgetedText:
        """Trim text to fit the remaining token budget."""

        budget = max(0, self.max_tokens - reserved_tokens)
        tokens = estimate_tokens(text)
        if tokens <= budget:
            return BudgetedText(text=text.strip(), tokens=tokens)
        words = text.split()
        accepted: list[str] = []
        for word in words:
            candidate = " ".join([*accepted, word])
            if estimate_tokens(candidate) > budget:
                break
            accepted.append(word)
        trimmed = " ".join(accepted).strip()
        return BudgetedText(text=trimmed, tokens=estimate_tokens(trimmed))

    def admit(self, chunks: list[str], reserved_tokens: int = 0) -> list[BudgetedText]:
        """Admit chunks until the total budget is exhausted."""

        admitted: list[BudgetedText] = []
        used = reserved_tokens
        for chunk in chunks:
            budgeted = self.trim(chunk, reserved_tokens=used)
            if budgeted.tokens <= 0 or not budgeted.text:
                break
            admitted.append(budgeted)
            used += budgeted.tokens
            if used >= self.max_tokens:
                break
        return admitted
