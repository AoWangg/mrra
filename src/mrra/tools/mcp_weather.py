from __future__ import annotations

from typing import Dict, Any

try:
    # Prefer modern core tool decorator
    from langchain_core.tools import tool
except Exception:  # pragma: no cover
    try:
        from langchain.tools import tool  # type: ignore
    except Exception:  # fallback shim

        def tool(_name=None, return_direct=False):  # type: ignore
            def deco(fn):
                return fn

            return deco


def _mock_weather(location: str, when: str) -> Dict[str, Any]:
    # Deterministic stub for offline/demo usage
    return {
        "location": location,
        "when": when,
        "precip_prob": 0.2,
        "temp": 24.0,
        "desc": "partly cloudy",
        "source": "stub",
    }


@tool("weather_lookup")
def weather_tool(location: str, when: str) -> Dict[str, Any]:
    """查询指定地点/时间的天气，返回降雨概率和温度等字段。若无法连接 MCP，将返回离线 stub。"""
    # TODO: Connect to MCP server if configured. For now, return mock data.
    # You can enable MCP via environment variables and implement an adapter here.
    return _mock_weather(location, when)
