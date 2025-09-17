<div align="center">
  
  <img src="assets/icon.svg" alt="MRRA Icon" width="120" height="120">
  
  # 🗺️ MRRA
  **Mobility Retrieve-and-Reflect Agent**
  
  *GraphRAG + Multi-Agent Reflection for Intelligent Mobility Analysis*
  
  [![PyPI version](https://img.shields.io/pypi/v/mrra.svg)](https://pypi.org/project/mrra/)
  [![PyPI downloads](https://img.shields.io/pypi/dm/mrra.svg)](https://pypi.org/project/mrra/)
  [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![CI](https://github.com/AoWangg/mrra/workflows/CI/badge.svg)](https://github.com/AoWangg/mrra/actions)
  
  [🚀 Quick Start](#-quick-start) • [📖 Documentation](#-documentation) • [🌟 Features](#-features) • [🛠️ Installation](#️-installation)
  
</div>

---

## 🎯 Overview

**MRRA** is a cutting-edge Python package that revolutionizes mobility trajectory analysis through the fusion of **GraphRAG** (Graph-based Retrieval-Augmented Generation) and **multi-agent reflection**. Simply provide trajectory data with `user_id`, `timestamp`, `latitude`, `longitude` columns, and unlock intelligent predictions for next locations, future positions, and complete daily routes.

<div align="center">
  <img src="assets/mrra-framwork.png" alt="MRRA Framework" width="800">
</div>

## ✨ Key Features

<table>
<tr>
<td>

### 🧠 **Intelligent Architecture**
- **GraphRAG Integration**: Advanced graph-based retrieval system
- **Multi-Agent Reflection**: Sophisticated agent orchestration with confidence weighting
- **Temporal-Spatial Reasoning**: Deep understanding of mobility patterns

</td>
<td>

### 🔧 **Developer Friendly**
- **Plug-and-Play**: Ready-to-use with minimal configuration
- **LangChain Compatible**: Seamless integration with LangChain ecosystem
- **MCP Tools**: Built-in support for weather, maps, and geospatial services

</td>
</tr>
<tr>
<td>

### 📊 **Data Processing**
- **Flexible Input**: Standard trajectory format support
- **Graph Construction**: Automatic mobility graph generation
- **Pattern Recognition**: Intelligent activity and behavior detection

</td>
<td>

### 🎯 **Prediction Tasks**
- **Next Position**: Predict immediate next location
- **Future Position**: Forecast location at specific time
- **Full Day Trajectory**: Generate complete daily route patterns

</td>
</tr>
</table>

## 🛠️ Installation

### Quick Install
```bash
pip install mrra
```

### Development Install
```bash
git clone https://github.com/AoWangg/mrra.git
cd mrra
pip install -e .
```

### Optional Dependencies
```bash
# For MCP tools integration
pip install mrra[mcp]

# For development
pip install mrra[dev]
```

## 🚀 Quick Start

### Basic Usage

```python
import pandas as pd
from mrra.data.trajectory import TrajectoryBatch
from mrra.retriever.graph_rag import GraphRAGGenerate
from mrra.agents.builder import build_mrra_agent

# 📊 Prepare your trajectory data
df = pd.DataFrame({
    'user_id': ['user_1', 'user_1', 'user_1'],
    'timestamp': ['2023-01-01 09:00:00', '2023-01-01 12:00:00', '2023-01-01 18:00:00'],
    'latitude': [31.2304, 31.2404, 31.2504],
    'longitude': [121.4737, 121.4837, 121.4937],
})

# 🔄 Create trajectory batch and retriever
tb = TrajectoryBatch(df)
retriever = GraphRAGGenerate(tb=tb)

# 🤖 Build MRRA agent
agent = build_mrra_agent(
    llm={
        "provider": "openai-compatible",
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "YOUR_API_KEY"  # Use environment variables in production
    },
    retriever=retriever,
    reflection={
        "max_round": 3,
        "subAgents": [
            {"name": "temporal", "prompt": "Temporal reasoning specialist", "mcp": {"weather": {}}},
            {"name": "spatial", "prompt": "Spatial analysis expert", "mcp": {"maps": {}}},
            {"name": "pattern", "prompt": "Behavior pattern analyst", "mcp": {}},
        ],
        "aggregator": "confidence_weighted_voting"
    }
)

# 🎯 Make predictions
result = agent.invoke({
    "task": "next_position", 
    "user_id": "user_1", 
    "t": "2023-01-02 09:30:00"
})
print(result)
```

### Advanced MCP Integration

```python
# 🗺️ Configure with real-world services
reflection_config = {
    "subAgents": [
        {
            "name": "spatial", 
            "prompt": "Expert in spatial analysis with real-time map data", 
            "mcp": {
                "gmap": {
                    "url": "https://mcp.amap.com/sse?key=YOUR_AMAP_KEY", 
                    "transport": "sse"
                }
            }
        }
    ]
}
```

## 🎯 Supported Tasks

| Task | Description | Input | Output |
|------|-------------|-------|--------|
| `next_position` | Predict the next location after given time | `user_id`, `t` | Next coordinate prediction |
| `future_position` | Predict location at specific future time | `user_id`, `t` | Future coordinate prediction |
| `full_day_traj` | Generate complete daily trajectory | `user_id`, `date` | Full day route sequence |

## 📊 Data Format

### Required Columns
- `user_id`: Unique identifier for each user
- `timestamp`: ISO format timestamp (e.g., "2023-01-01 09:00:00")
- `latitude`: Latitude coordinate (float)
- `longitude`: Longitude coordinate (float)

## 🌍 MCP Tools Integration

MRRA supports multiple MCP integration strategies with graceful fallback:

1. **Primary**: `langchain-mcp-adapters` (recommended)
2. **Fallback**: `langchain-mcp` toolkit
3. **Native**: Raw MCP SSE discovery

### Supported Services
- 🗺️ **Maps**: Google Maps, Amap, OpenStreetMap
- 🌤️ **Weather**: Real-time weather data
- 📍 **Geocoding**: Address to coordinate conversion

## 📖 Documentation

- 🏠 **Homepage**: [mrra.tech](https://www.mrra.tech/)
- 📚 **Documentation**: [mrra.tech/en/docs](https://mrra.tech/en/docs)
- 🇨🇳 **中文文档**: [mrra.tech/zh/docs](https://mrra.tech/zh/docs)


## 🧪 Examples & Demos

```bash
# 🌟 GeoLife dataset demo
python scripts/verify_geolife.py

# 🔍 Retriever testing
python scripts/check_retriever.py
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup
```bash
# Create environment
conda create -n mrra-dev python=3.10
conda activate mrra-dev

# Install in development mode
pip install -e .[dev]

# Run tests
pytest

# Code formatting
ruff format .
ruff check .
```

## 🔒 Security & Best Practices

- 🔐 **Never commit API keys** - Use environment variables or secret managers
- 📁 **Large datasets** are git-ignored by default
- 🛡️ **Secure MCP connections** with proper authentication

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built on the shoulders of giants:
- [LangChain](https://github.com/langchain-ai/langchain) for LLM orchestration
- [NetworkX](https://github.com/networkx/networkx) for graph processing
- [Pandas](https://github.com/pandas-dev/pandas) for data manipulation

## 📊 Project Stats

<div align="center">

![GitHub stars](https://img.shields.io/github/stars/AoWangg/mrra?style=social)
![GitHub forks](https://img.shields.io/github/forks/AoWangg/mrra?style=social)
![GitHub issues](https://img.shields.io/github/issues/AoWangg/mrra)
![GitHub pull requests](https://img.shields.io/github/issues-pr/AoWangg/mrra)

</div>

---

<div align="center">
  <sub>🚀 <strong>Ready to revolutionize mobility analysis?</strong> <a href="#-quick-start">Get started now!</a></sub>
</div>