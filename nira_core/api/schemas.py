from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    task_type: str | None = None


class AgentRunRequest(BaseModel):
    task: str = Field(min_length=1)
    task_type: str | None = None


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=32)


class MemoryPinRequest(BaseModel):
    pinned: bool = True


class WorkflowRunRequest(BaseModel):
    goal: str = Field(min_length=1)
    seed_sources: list[dict[str, str]] = Field(default_factory=list)


class ToolRunRequest(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CapabilityRecommendRequest(BaseModel):
    goal: str = Field(min_length=1)
    max_ram_mb: int = Field(default=512, ge=32, le=4096)
    permissions: list[str] = Field(default_factory=list)
