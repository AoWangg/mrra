# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation
- Install from source: `pip install -e .`
- Install with MCP tools: `pip install -e .[mcp]`
- Development dependencies: `pip install -e .[dev]`

### Testing and Linting
- Run tests: `pytest` (uses pytest>=7)
- Code formatting/linting: `ruff check` and `ruff format` (uses ruff>=0.5.0)

### Example Scripts
- Check retriever functionality: `python scripts/check_retriever.py`
- Verify with Geolife dataset: `python scripts/verify_geolife.py`

## Architecture Overview

MRRA (Mobility Retrieve-and-Reflect Agent) is a GraphRAG + multi-agent reflection system for mobility trajectory analysis. The codebase follows a modular architecture:

### Core Data Flow
1. **TrajectoryBatch** (`src/mrra/data/trajectory.py`) - Normalizes mobility data with required columns: `user_id`, `timestamp`, `latitude`, `longitude`
2. **MobilityGraph** (`src/mrra/graph/mobility_graph.py`) - Builds NetworkX MultiDiGraph with user, location, hour, and day-of-week nodes
3. **GraphRAGGenerate** (`src/mrra/retriever/graph_rag.py`) - LangChain BaseRetriever that performs graph-based retrieval
4. **ReflectionOrchestrator** (`src/mrra/agents/reflection.py`) - Coordinates multiple subagents with weighted voting aggregation

### Agent System
- **build_mrra_agent()** (`src/mrra/agents/builder.py`) - Main factory function that assembles the complete system
- **Subagents** - Specialized agents (temporal, spatial, pattern) with optional MCP tool integration
- **MCP Tools** - Optional Model Control Protocol integrations for weather, maps, and gmap services

### Key Components
- **Config classes** (`src/mrra/config.py`) - Structured configuration for LLM, retriever, and MCP settings
- **Activity analysis** (`src/mrra/analysis/activity_purpose.py`) - Purpose assignment for trajectory activities
- **Caching** (`src/mrra/persist/cache.py`) - Persistence layer for trajectory data
- **Geo utilities** (`src/mrra/utils/geo.py`) - Geographic coordinate processing

### Supported Tasks
- `next_position` - Predict next location after given time
- `future_position` - Predict location at specific future time
- `full_day_traj` - Generate complete daily trajectory path

### LLM Integration
- OpenAI-compatible endpoints (default provider)
- Configurable models, temperature, timeouts
- Structured JSON outputs from subagents with confidence scoring

### MCP Integration Pattern
The system uses a three-tier MCP fallback strategy:
1. `langchain-mcp-adapters` (preferred)
2. `langchain-mcp` toolkit
3. Raw MCP SSE discovery