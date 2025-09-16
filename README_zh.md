MRRA：移动轨迹检索与反思智能体（Mobility Retrieve-and-Reflect Agent）

概述
- 面向包含 `user_id / timestamp / latitude / longitude` 的移动轨迹数据。
- 将图检索（GraphRAG）与多子智能体反思融合，支持“下一点 / 未来时刻 / 全天轨迹”等任务。

特性
- 数据标准化（`TrajectoryBatch`）与移动图构建（`MobilityGraph`）。
- 基于图的检索器（`GraphRAGGenerate`），返回 LangChain `Document`。
- 多子智能体反思：严格 JSON 输出（proposal/point、confidence、rationale），聚合策略可配置。
- MCP 工具接入：优先 `langchain-mcp-adapters`，并提供 toolkit/原生 SSE 降级方案。

安装
- 源码安装（建议使用虚拟环境）：
  - `pip install -e .`
- MCP 可选依赖：`pip install -e .[mcp]`

快速开始
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
        # OpenAI 兼容端点（如 Qwen/DashScope）
        "provider":"openai-compatible",
        "model":"qwen-plus",
        "base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key":"YOUR_API_KEY"  # 生产环境建议使用环境变量
    },
    retriever=retriever,
    reflection={
        "max_round": 3,
        "subAgents": [
            {"name":"temporal", "prompt":"你是时间模式子智能体。", "mcp": {"weather":{}}},
            {"name":"spatial",  "prompt":"你是空间模式子智能体。", "mcp": {"maps":{}}},
            {"name":"pattern",  "prompt":"你是画像/模式子智能体。", "mcp": {}},
        ],
        "aggregator": "confidence_weighted_voting"
    }
)

res = agent.invoke({"task":"next_position", "user_id":"user_1", "t":"2023-01-02 09:30:00"})
print(res)
```

任务
- `next_position`：指定时间点之后的下一位置。
- `future_position`：指定未来时间点的位置。
- `full_day_traj`：指定日期的全天轨迹。

MCP 接入（高德示例）
```
reflection={
  "subAgents": [
    {"name":"spatial", "prompt":"...", "mcp": {"gmap": {"url": "https://mcp.amap.com/sse?key=YOUR_AMAP_KEY", "transport":"sse"}}}
  ]
}
```
- 包内优先使用 `langchain-mcp-adapters`；若不可用，回退到 `langchain-mcp` toolkit；再回退到原生 MCP SSE 封装。

数据格式
- 必须列：`user_id`, `timestamp`（ISO），`latitude`, `longitude`。
- 可选：通过 `TrajectoryBatch(..., tz=...)` 指定时区。

开发与示例
- 创建环境：`conda create -n mrra-py310 python=3.10`
- ISP 数据演示：`python scripts/verify_isp.py`（需提供 `scripts/isp`，该文件默认被 git 忽略）

安全提示
- 请勿将 API Key 提交到仓库。生产环境推荐使用环境变量或密钥管理服务。
- 大文件（如 `scripts/isp`）已默认加入 `.gitignore`。

许可证
- 请在此处填写你的许可证信息。

