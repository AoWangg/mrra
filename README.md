MRRA: Mobility Retrieve-and-Reflect Agent

Overview
- MRRA is a plug-and-play Python package for mobility trajectories with columns `user_id`, `timestamp`, `latitude`, `longitude`.
- It composes a GraphRAG retriever with multi-agent reflection to support tasks like next point, future time, and full-day trajectory.

Features
- Data normalization (`TrajectoryBatch`) and mobility graph construction (`MobilityGraph`).
- Graph-based retriever (`GraphRAGGenerate`) returning LangChain Documents.
- Multi-agent reflection with strict JSON outputs and configurable aggregator.
- MCP tools integration (adapters-first) with graceful fallback.

Install
- From source (recommended in a virtual env):
  - `pip install -e .`
- Optional MCP extras: `pip install -e .[mcp]`

Quickstart
```
import pandas as pd
from mrra.data.trajectory import TrajectoryBatch
from mrra.graph.pattern import PatternGenerate
from mrra.retriever.graph_rag import GraphRAGGenerate
from mrra.agents.builder import build_mrra_agent

df = pd.DataFrame({
    'user_id': ['user_1','user_1','user_1'],
    'timestamp': ['2023-01-01 09:00:00','2023-01-01 12:00:00','2023-01-01 18:00:00'],
    'latitude': [31.2304,31.2404,31.2504],
    'longitude':[121.4737,121.4837,121.4937],
})

tb = TrajectoryBatch(df)
pattern = PatternGenerate(tb)
retriever = GraphRAGGenerate(tb=tb)

agent = build_mrra_agent(
    llm={
        # OpenAI-compatible endpoint
        "provider":"openai-compatible",
        "model":"qwen-plus",
        "base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key":"YOUR_API_KEY"  # prefer env var in production
    },
    retriever=retriever,
    reflection={
        "max_round": 3,
        "subAgents": [
            {"name":"temporal", "prompt":"Temporal reasoning subagent.", "mcp": {"weather":{}}},
            {"name":"spatial",  "prompt":"Spatial reasoning subagent.",  "mcp": {"maps":{}}},
            {"name":"pattern",  "prompt":"Profile/pattern subagent.",  "mcp": {}},
        ],
        "aggregator": "confidence_weighted_voting"
    }
)

res = agent.invoke({"task":"next_position", "user_id":"user_1", "t":"2023-01-02 09:30:00"})
print(res)
```

Tasks
- `next_position`: next point after time `t`.
- `future_position`: point at a future time `t`.
- `full_day_traj`: full-day path for a given `date`.

MCP Integration (Amap example)
- Configure subagents with MCP:
```
reflection={
  "subAgents": [
    {"name":"spatial", "prompt":"...", "mcp": {"gmap": {"url": "https://mcp.amap.com/sse?key=YOUR_AMAP_KEY", "transport":"sse"}}}
  ]
}
```
- The package uses `langchain-mcp-adapters` first; falls back to `langchain-mcp` toolkit; and finally to raw MCP SSE discovery.

Data format
- Required columns: `user_id`, `timestamp` (ISO), `latitude`, `longitude`.
- Optional tz handling via `TrajectoryBatch(..., tz=...)`.

Dev and demos
- Create env (example): `conda create -n mrra-py310 python=3.10`
- ISP data demo: `python scripts/verify_isp.py` (expects `scripts/isp` as input; file is git-ignored by default)

Security notes
- Do not commit API keys. Prefer environment variables or secret managers.
- Large data (like `scripts/isp`) is git-ignored by default.

License
- Specify your license here.

中文文档
- See `README_zh.md` for Chinese documentation.
