from __future__ import annotations

from typing import Any, Dict, List
import logging

from mrra.agents.subagents import make_llm, build_subagent
from mrra.agents.reflection import ReflectionOrchestrator

try:
    from mrra.tools.mcp_weather import weather_tool
    from mrra.tools.mcp_maps import maps_tool
    from mrra.tools.mcp_gmap import gmap_tools
except Exception:  # pragma: no cover
    weather_tool = None  # type: ignore
    maps_tool = None  # type: ignore


def build_mrra_agent(llm: Dict[str, Any], retriever: Any, reflection: Dict[str, Any]):
    logger = logging.getLogger("mrra.builder")
    """Assemble MRRA agent.

    llm: {provider, model, base_url, api_key, temperature?, timeout?}
    retriever: LangChain BaseRetriever or Runnable
    reflection: {
        "max_round": int,
        "subAgents": [ {"name": str, "prompt": str?, "mcp": {"weather":{}, "maps":{}}?}, ... ],
        "aggregator": str
    }
    """
    logger.info(
        f"building MRRA agent with model={llm.get('model')} provider={llm.get('provider')}"
    )
    llm_obj = make_llm(**llm)
    subagents: Dict[str, Any] = {}
    for sa in reflection.get("subAgents", []):
        tools: List[Any] = []
        mcp = sa.get("mcp", {}) or {}
        if mcp.get("weather") and weather_tool is not None:
            tools.append(weather_tool)
        if mcp.get("maps") and maps_tool is not None:
            tools.append(maps_tool)
        gmap_cfg = mcp.get("gmap")
        if gmap_cfg:
            try:
                tools.extend(gmap_tools(gmap_cfg))
            except Exception as e:  # pragma: no cover - external service optional
                logger = logging.getLogger("mrra.builder")
                logger.warning(f"failed to init gmap MCP tools: {e}")
        logger.info(f"add subagent name={sa['name']} tools={len(tools)}")
        subagents[sa["name"]] = build_subagent(
            sa["name"], llm_obj, sa.get("prompt"), tools
        )

    return ReflectionOrchestrator(
        subagents=subagents,
        retriever=retriever,
        max_round=int(reflection.get("max_round", 3)),
        aggregator=str(reflection.get("aggregator", "confidence_weighted_voting")),
    )
