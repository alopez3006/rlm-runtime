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

## Phase 8: Sub-LLM Orchestration

**Status: Planned**

Recursive sub-LLM calls within a single completion. The model can delegate focused sub-problems to fresh LLM calls with their own context window and budget. Based on Alex Zhang's RLM paper.

See [docs/sub-llm-orchestration.md](docs/sub-llm-orchestration.md) for full specification.

| Feature | Status | Description |
|---------|--------|-------------|
| `rlm_sub_complete` tool | ⏳ | Spawn a sub-LLM call with its own context and budget |
| `rlm_batch_complete` tool | ⏳ | Parallel sub-LLM calls with shared budget |
| Auto-context injection | ⏳ | Auto-query Snipara for sub-calls with `context_query` parameter |
| Budget inheritance | ⏳ | Sub-calls get fraction (50%) of parent's remaining budget |
| Cost guardrails | ⏳ | Per-session dollar cap, max sub-calls per turn, depth limits |
| Nested trajectory logging | ⏳ | Sub-calls logged as nested entries in JSONL trajectory |

**Prerequisites:** Phase 1 (Orchestrator) ✅, Phase 4 (Cost Tracking) ✅, Snipara integration ✅

---

## Phase 9: Autonomous RLM Agent

**Status: Planned**

Full autonomous agent loop: observe → think → act → terminate. The model explores documentation, writes code, spawns sub-LLM calls, and terminates via FINAL/FINAL_VAR protocol when ready.

See [docs/autonomous-agent.md](docs/autonomous-agent.md) for full specification.

| Feature | Status | Description |
|---------|--------|-------------|
| `AgentRunner` class | ⏳ | Main agent loop with configurable limits |
| `FINAL("answer")` protocol | ⏳ | Natural language termination signal |
| `FINAL_VAR("var")` protocol | ⏳ | Return computed REPL variable as result |
| Iteration budget | ⏳ | Max observe-think-act cycles (default: 10) |
| Hard safety limits | ⏳ | Absolute caps: 50 iterations, $10, 600s timeout |
| Graceful degradation | ⏳ | Force FINAL with best answer when limits hit |
| `rlm agent` CLI command | ⏳ | Run agent from command line |
| MCP tools (`agent_run`, `agent_status`, `agent_cancel`) | ⏳ | Agent control via MCP |
| Trajectory visualizer extension | ⏳ | Agent iteration timeline, cost chart, call tree |
| Deterministic replay tests | ⏳ | Record and replay agent trajectories for testing |

**Prerequisites:** Phase 8 (Sub-LLM Orchestration), Snipara REPL Context Bridge ✅

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

1. **Sub-LLM Orchestration (Phase 8)** - `rlm_sub_complete` and budget inheritance
2. **Autonomous Agent (Phase 9)** - FINAL/FINAL_VAR protocol and agent loop
3. **Test Coverage** - Push from 87% to 90%+ coverage
4. **Docker Resource Reporting** - Report actual CPU/memory usage from containers
5. **OpenTelemetry Integration** - Distributed tracing for observability
6. **Documentation** - Improve guides and examples

### How to Contribute

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

See [Development](README.md#development) for setup instructions.
