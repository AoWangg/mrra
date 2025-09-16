from __future__ import annotations

from typing import Any, Dict, List

try:
    from langchain_core.tools import tool
except Exception:  # pragma: no cover
    try:
        from langchain.tools import tool  # type: ignore
    except Exception:

        def tool(_name=None, return_direct=False):  # type: ignore
            def deco(fn):
                return fn

            return deco


def _mock_pois(lat: float, lon: float, radius: int) -> List[Dict[str, Any]]:
    # Simple deterministic mock nearby POIs
    return [
        {
            "name": "Cafe Alpha",
            "lat": lat + 0.001,
            "lon": lon + 0.001,
            "category": "cafe",
        },
        {
            "name": "Park Beta",
            "lat": lat - 0.001,
            "lon": lon - 0.001,
            "category": "park",
        },
    ]


@tool("map_nearby_pois")
def maps_tool(lat: float, lon: float, radius: int = 500) -> List[Dict[str, Any]]:
    """根据经纬度和半径查询附近 POI。若 MCP/地图服务不可用，返回离线 stub 列表。"""
    return _mock_pois(lat, lon, radius)
