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
| Multi-Project Support | ✅ | Per-project `rlm.toml` configuration |

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
| Error Handling | ✅ | Custom exception hierarchy |
| Test Coverage 90%+ | 🔄 | Currently at 87% (462 tests) |

---

## Phase 3: Execution Environments

**Status: In Progress**

More isolation and execution options.

| Feature | Status | Description |
|---------|--------|-------------|
| WebAssembly REPL | ✅ | Browser-safe execution via Pyodide |
| Resource Quotas | ✅ | CPU/memory tracking in LocalREPL, limits in DockerREPL |
| Docker Resource Reporting | 🔄 | Report actual usage (not just limits) from containers |
| Remote Execution | ⏳ | Execute on RunPod/Modal/Lambda |
| Kubernetes Pods | ⏳ | Ephemeral pod execution |

---

## Phase 4: Observability

**Status: In Progress**

Production monitoring and debugging capabilities.

| Feature | Status | Description |
|---------|--------|-------------|
| Cost Tracking | ✅ | Per-model pricing, cost budgets, token breakdown |
| Token Budget Enforcement | ✅ | Now enforced (was configured but not checked) |
| OpenTelemetry | ⏳ | Distributed tracing integration |
| Prometheus Metrics | ⏳ | Token usage, latency, error rates |
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

1. **Test Coverage** - Push from 87% to 90%+ coverage
2. **Docker Resource Reporting** - Report actual CPU/memory usage from containers
3. **OpenTelemetry Integration** - Distributed tracing for observability
4. **Tool Development** - Create useful community tools
5. **Documentation** - Improve guides and examples

### How to Contribute

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

See [Development](README.md#development) for setup instructions.
