from __future__ import annotations

from typing import Any, Dict, List, Callable, Union

try:
    # Preferred: langchain-mcp-adapters (newer recommended integration)
    from langchain_mcp_adapters.sessions import (
        SSEConnection,
        WebsocketConnection,
        StreamableHttpConnection,
        StdioConnection,
    )  # type: ignore
    from langchain_mcp_adapters.tools import load_mcp_tools  # type: ignore

    HAVE_ADAPTERS = True
except Exception:  # pragma: no cover
    HAVE_ADAPTERS = False

try:
    # Fallback 1: langchain-mcp toolkit
    from langchain_mcp.toolkit import MCPToolkit  # type: ignore
except Exception:  # pragma: no cover
    MCPToolkit = None  # type: ignore

try:
    # Fallback 2: raw MCP client
    import anyio
    from mcp import ClientSession  # type: ignore
    from mcp.transport.sse import SseClientTransport  # type: ignore
    from mcp.types import TextContent  # type: ignore
except Exception:  # pragma: no cover
    ClientSession = None  # type: ignore
    SseClientTransport = None  # type: ignore
    TextContent = None  # type: ignore

try:
    from langchain_core.tools import Tool
except Exception:  # pragma: no cover
    try:
        from langchain.tools import Tool  # type: ignore
    except Exception:  # last resort shim
        Tool = None  # type: ignore


def _tools_via_langchain_mcp(url: str) -> List[Any]:
    if MCPToolkit is None or Tool is None:
        return []
    try:
        tk = MCPToolkit.from_sse(url=url, name="gmap")  # type: ignore[attr-defined]
        return tk.get_tools()  # returns List[Tool]
    except Exception:
        # Graceful fallback; caller will attempt raw SSE
        return []


def _sync_call_sse(url: str, tool_name: str, args: Dict[str, Any]) -> str:
    """Call a remote MCP tool over SSE synchronously and return text content."""
    if ClientSession is None or SseClientTransport is None:
        raise RuntimeError(
            "mcp library not installed; please `pip install mcp langchain-mcp`"
        )

    async def _run() -> str:
        transport = await SseClientTransport.connect(url)
        async with transport:
            async with ClientSession(transport) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)
                # Extract first text content
                for c in result.content:
                    if isinstance(c, TextContent):
                        return c.text
                # Fallback stringify
                return str(result.model_dump())

    return anyio.run(_run)


def _discover_tools(url: str) -> List[Dict[str, Any]]:
    if ClientSession is None or SseClientTransport is None:
        return []

    async def _run() -> List[Dict[str, Any]]:
        transport = await SseClientTransport.connect(url)
        async with transport:
            async with ClientSession(transport) as session:
                await session.initialize()
                tools = await session.list_tools()
                return [t.model_dump() for t in tools.tools]

    return anyio.run(_run)


def _connection_from_cfg(cfg: Dict[str, Any]):
    transport = (cfg.get("transport") or "sse").lower()
    url = cfg.get("url")
    if transport == "sse":
        return SSEConnection(url=url)
    if transport == "websocket":
        return WebsocketConnection(url=url)
    if transport == "streamable_http":
        return StreamableHttpConnection(url=url)
    if transport == "stdio":
        # requires command + args
        return StdioConnection(command=cfg["command"], args=cfg.get("args", []))
    # default to sse
    return SSEConnection(url=url)


def gmap_tools(cfg: Union[str, Dict[str, Any]]) -> List[Any]:
    """Return a list of LangChain Tools backed by an MCP server (Amap),
    following LangChain's adapters-first approach.

    cfg: either url string or dict with {url, transport}

    Preference order:
    1) langchain-mcp-adapters: load_mcp_tools + Connection
    2) langchain-mcp toolkit: MCPToolkit.from_sse
    3) raw MCP SSE discovery wrapper
    """
    if isinstance(cfg, str):
        cfg = {"url": cfg, "transport": "sse"}

    # Preferred: adapters
    if HAVE_ADAPTERS:
        try:
            conn = _connection_from_cfg(cfg)

            async def _run():
                tools = await load_mcp_tools(None, connection=conn)  # type: ignore
                return tools

            return anyio.run(_run)
        except Exception:
            pass

    # Fallback: langchain-mcp toolkit (sse only)
    url = cfg.get("url")
    tools = _tools_via_langchain_mcp(url)
    if tools:
        return tools

    # Fallback dynamic wrappers
    if Tool is None:
        return []

    discovered = _discover_tools(url)
    wrapped: List[Any] = []
    for t in discovered:
        name = t.get("name") or "gmap_tool"
        desc = t.get("description") or "Remote MCP tool"

        def _make(name: str) -> Callable[[str], str]:
            def _fn(input_json: str) -> str:
                import json

                try:
                    args = json.loads(input_json) if input_json else {}
                except Exception:
                    # If not JSON, treat as query string
                    args = {"query": input_json}
                return _sync_call_sse(url, name, args)

            return _fn

        wrapped.append(
            Tool(
                name=f"gmap_{name}",
                description=f"{desc}. 输入应为JSON字符串参数。",
                func=_make(name),
            )
        )
    return wrapped
