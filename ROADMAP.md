# RLM Runtime Roadmap

This document outlines the development roadmap for RLM Runtime.

## Phase 1: Foundation ✅

**Status: Complete**

Core functionality for recursive LLM completions with sandboxed execution.

| Feature | Status | Description |
|---------|--------|-------------|
| Orchestrator | ✅ | Recursive completion with depth/token budgets |
| Local REPL | ✅ | RestrictedPython sandboxed execution |
| Docker REPL | ✅ | Isolated container execution |
| LiteLLM Backend | ✅ | Support for 100+ LLM providers |
| Trajectory Logging | ✅ | JSONL execution traces |
| CLI | ✅ | `rlm run`, `rlm init`, `rlm logs`, `rlm doctor` |
| Snipara Integration | ✅ | Context optimization tools |
| MCP Server | ✅ | Claude Desktop/Code integration |
| Multi-Project Support | ✅ | Project switching via `set_project` |

---

## Phase 2: Stability & Distribution ✅

**Status: Complete**

Production-ready release infrastructure.

| Feature | Status | Description |
|---------|--------|-------------|
| CI/CD Pipeline | ✅ | GitHub Actions for tests (Python 3.10-3.12) |
| PyPI Release Workflow | ✅ | Automated publishing via trusted publishing |
| Streaming Support | ✅ | Real-time token streaming via `rlm.stream()` |
| Trajectory Visualizer | ✅ | Streamlit dashboard for debugging |
| Error Handling | 🔄 | Custom exception hierarchy |
| Test Coverage 90%+ | 🔄 | Comprehensive test suite |

---

## Phase 3: Execution Environments

**Status: In Progress**

More isolation and execution options.

| Feature | Status | Description |
|---------|--------|-------------|
| WebAssembly REPL | 🔄 | Browser-safe execution via Pyodide |
| Resource Quotas | ⏳ | Fine-grained CPU/memory/time limits |
| Remote Execution | ⏳ | Execute on RunPod/Modal/Lambda |
| Kubernetes Pods | ⏳ | Ephemeral pod execution |

---

## Phase 4: Observability

**Status: Planned**

Production monitoring and debugging capabilities.

| Feature | Status | Description |
|---------|--------|-------------|
| OpenTelemetry | ⏳ | Distributed tracing integration |
| Prometheus Metrics | ⏳ | Token usage, latency, error rates |
| Cost Tracking | ⏳ | Per-model cost estimation and budgets |
| Alerting | ⏳ | Budget exceeded, error rate thresholds |

---

## Phase 5: Tool Ecosystem

**Status: Planned**

Extensible plugin system for community contributions.

| Feature | Status | Description |
|---------|--------|-------------|
| Tool Marketplace | ⏳ | Registry of community tools |
| Tool Discovery | ⏳ | Auto-detect tools from installed packages |
| Tool Versioning | ⏳ | Semantic versioning for tool schemas |
| Tool Testing Framework | ⏳ | Framework for testing custom tools |

---

## Phase 6: Enterprise Features

**Status: Planned**

Team and organization support.

| Feature | Status | Description |
|---------|--------|-------------|
| API Server Mode | ⏳ | HTTP API for team deployments |
| Authentication | ⏳ | API keys, OAuth integration |
| Rate Limiting | ⏳ | Per-user/project quotas |
| Audit Logging | ⏳ | Compliance-ready execution logs |
| Multi-Tenant | ⏳ | Isolated execution per tenant |

---

## Phase 7: Advanced LLM Features

**Status: Planned**

Cutting-edge capabilities.

| Feature | Status | Description |
|---------|--------|-------------|
| Parallel Tool Calls | ⏳ | Execute multiple tools concurrently |
| Structured Outputs | ⏳ | JSON schema-constrained responses |
| Multi-Modal | ⏳ | Image/audio input support |
| Agent Memory | ⏳ | Persistent context across sessions |
| Self-Improvement | ⏳ | Learn from trajectory feedback |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| 🔄 | In Progress |
| ⏳ | Planned |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Priority Areas

1. **Test Coverage** - Help us reach 90%+ coverage
2. **WebAssembly REPL** - Implement Pyodide integration
3. **Documentation** - Improve guides and examples
4. **Tool Development** - Create useful community tools

### How to Contribute

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

See [Development](README.md#development) for setup instructions.
