# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial open-source release preparation
- MIT license adoption
- GitHub Actions workflow for automated PyPI publishing

### Changed
- Updated project metadata in pyproject.toml
- Enhanced documentation structure

## [0.1.0] - 2025-09-17

### Added
- Initial release of MRRA (Mobility Retrieve-and-Reflect Agent)
- Core components:
  - TrajectoryBatch for data normalization
  - MobilityGraph for graph construction
  - GraphRAGGenerate for graph-based retrieval
  - ReflectionOrchestrator for multi-agent coordination
- Multi-agent reflection system with configurable subagents
- MCP (Model Control Protocol) tools integration
- Support for three prediction tasks:
  - `next_position`: Predict next location after given time
  - `future_position`: Predict location at specific future time
  - `full_day_traj`: Generate complete daily trajectory
- Activity extraction and purpose assignment
- Caching mechanism for performance optimization
- Support for OpenAI-compatible LLM endpoints
- Comprehensive documentation in English and Chinese

### Features
- Graph-based retrieval with temporal, spatial, and pattern reasoning
- Configurable aggregation strategies (confidence-weighted voting)
- MCP tools for weather, maps, and geographic services
- Flexible configuration system for LLM, retriever, and MCP settings
- Grid-based spatial discretization for mobility analysis
- Time-aware trajectory processing with timezone support

### Dependencies
- Python 3.10+
- pandas, numpy, networkx for data processing
- pydantic for configuration management
- langchain-core, langchain-openai for LLM integration
- Optional: langchain-mcp-adapters, mcp for tool integration

### Documentation
- Comprehensive README with quickstart examples
- Chinese documentation (README_zh.md)
- Detailed usage guide (docs/MRRA_使用指南.md)
- Architecture documentation and API reference