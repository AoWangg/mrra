from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class LLMConfig:
    provider: str = "openai-compatible"
    model: str = ""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.2
    timeout: Optional[float] = 60.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrieverConfig:
    k: int = 8
    max_hops: int = 2
    hour_weight: float = 0.5
    dow_weight: float = 0.3
    recent_weight: float = 0.2


@dataclass
class MCPConfig:
    enable: bool = True
    # Optionally configure endpoints or socket paths if using MCP
    endpoint: Optional[str] = None
    timeout: float = 10.0


@dataclass
class MRRAConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    retriever: RetrieverConfig = field(default_factory=RetrieverConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
