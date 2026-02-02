# Security Guide

This document covers security considerations, best practices, and the security model for RLM Runtime.

## Table of Contents

- [Security Overview](#security-overview)
- [Sandboxing](#sandboxing)
- [Secrets Management](#secrets-management)
- [Network Security](#network-security)
- [Data Privacy](#data-privacy)
- [Vulnerability Reporting](#vulnerability-reporting)
- [Compliance](#compliance)

---

## Security Overview

RLM Runtime implements multiple layers of security:

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  • Input validation                                          │
│  • Prompt injection detection                                │
│  • Output sanitization                                       │
├─────────────────────────────────────────────────────────────┤
│                    Sandbox Layer                             │
│  • Local REPL: RestrictedPython                              │
│  • Docker: Container isolation                               │
│  • WebAssembly: Pyodide sandbox                              │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                      │
│  • Network isolation                                         │
│  • Resource limits                                           │
│  • Secrets management                                        │
└─────────────────────────────────────────────────────────────┘
```

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Malicious code execution | Sandboxed REPL environments |
| Data exfiltration | Network isolation, read-only filesystems |
| Prompt injection | Input validation, output sanitization |
| Resource exhaustion | Budget limits, timeouts |
| Secrets leakage | Secure storage, environment variables |
| Unauthorized access | Authentication, authorization |

---

## Sandboxing

### Local REPL (RestrictedPython)

The local REPL uses RestrictedPython to limit what code can do:

```python
from rlm.repl.local import LocalREPL

repl = LocalREPL(
    timeout=30,
    output_limit=102400,  # 100KB output limit
)

# Blocked operations:
# - Import of network modules (socket, requests, etc.)
# - File I/O operations
# - System calls (os.system, subprocess)
# - Access to private attributes (_private)
```

**Allowed modules:**
```python
ALLOWED_MODULES = [
    "json", "re", "math", "statistics",
    "datetime", "time", "random",
    "collections", "itertools", "functools",
    "typing", "copy", "pprint",
    "base64", "hashlib", "hmac",
]
```

### Docker REPL

Docker provides stronger isolation:

```python
from rlm import RLM

rlm = RLM(
    environment="docker",
    docker_image="python:3.11-slim",
    docker_network_disabled=True,  # No network access
    docker_memory="512m",          # Memory limit
    docker_cpus=1.0,               # CPU limit
    docker_timeout=30,             # Execution timeout
)
```

**Docker security features:**
- Process isolation
- Network disabled by default
- Resource limits (CPU, memory)
- Read-only filesystem (configurable)
- Non-root user execution
- No privileged mode

### WebAssembly REPL

Pyodide provides browser-grade sandboxing:

```python
from rlm import RLM

rlm = RLM(environment="wasm")
```

**WebAssembly security:**
- Full sandbox isolation
- No host system access
- No network by default
- Limited filesystem (in-memory)
- No native code execution

---

## Secrets Management

### Environment Variables

```bash
# Use environment variables for secrets
export RLM_API_KEY=sk-...
export SNIPARA_API_KEY=rlm_...
export DATABASE_URL=postgresql://...
```

### Docker Secrets

```yaml
# docker-compose.yml
services:
  rlm:
    image: rlm-runtime:latest
    environment:
      - RLM_API_KEY_FILE=/run/secrets/api_key
    secrets:
      - api_key

secrets:
  api_key:
    file: ./secrets/api_key
```

### Kubernetes Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: rlm-secrets
type: Opaque
stringData:
  snipara-api-key: "rlm_..."
  openai-api-key: "sk-..."
```

```yaml
# deployment.yaml
env:
  - name: SNIPARA_API_KEY
    valueFrom:
      secretKeyRef:
        name: rlm-secrets
        key: snipara-api-key
```

### Cloud Secrets Manager

```python
# Use AWS Secrets Manager
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        raise Exception(f"Failed to retrieve secret: {e}")

# Use in configuration
secret = get_secret("rlm/production/api-keys")
```

### GitHub Actions Secrets

```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        env:
          SNIPARA_API_KEY: ${{ secrets.SNIPARA_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          # Deploy with secrets
```

---

## Network Security

### Docker Network Isolation

```python
from rlm import RLM

rlm = RLM(
    environment="docker",
    docker_network_disabled=True,  # Default: no network
)

# To enable network (not recommended)
rlm = RLM(
    environment="docker",
    docker_network_disabled=False,
    # Consider adding network policies
)
```

### MCP Server Security

```bash
# Run MCP server with TLS
rlm mcp-serve --host 0.0.0.0 --port 8080 --tls

# Or behind a reverse proxy with TLS
# Nginx configuration:
# location /mcp {
#     proxy_pass http://localhost:8080;
#     proxy_set_header Host $host;
#     proxy_set_header X-Real-IP $remote_addr;
#     proxy_ssl_verify on;
# }
```

### Firewall Rules

```bash
# iptables rules for RLM container
# Block outbound traffic except to LLM API
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -d api.openai.com -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -j DROP
```

---

## Data Privacy

### Trajectory Logging

Trajectory logs contain sensitive data. Protect them:

```python
from rlm import RLM

# Configure log directory with restricted permissions
rlm = RLM(
    model="gpt-4o-mini",
    log_dir="./logs",  # Ensure this directory has restricted access
)

# Log rotation
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "logs/trajectory.jsonl",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
)
```

### PII Handling

```python
# Sanitize PII from logs
def sanitize_for_logging(text: str) -> str:
    """Remove or mask PII from text."""
    import re

    # Mask email addresses
    text = re.sub(r'[\w\.-]+@[\w\.-]+', '[EMAIL]', text)

    # Mask phone numbers
    text = re.sub(r'\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}', '[PHONE]', text)

    # Mask SSN
    text = re.sub(r'\d{3}-\d{2}-\d{4}', '[SSN]', text)

    return text
```

### Data Retention

```bash
# Log rotation policy
# Keep last 30 days of logs
# Daily rotation at midnight
# Compress old logs
```

---

## Vulnerability Reporting

### Reporting Process

If you discover a security vulnerability in RLM Runtime, please report it responsibly:

1. **Do not** disclose publicly
2. **Do not** attempt to exploit further
3. **Report** via email to: `security@snipara.com`

### Vulnerability Categories

- **Code execution** - Ability to escape sandbox
- **Data leakage** - Access to unauthorized data
- **Authentication** - Bypass of auth mechanisms
- **Authorization** - Privilege escalation
- **Injection** - Prompt injection, code injection
- **Denial of service** - Resource exhaustion

### Response Process

| Timeline | Action |
|----------|--------|
| 24 hours | Acknowledge receipt |
| 7 days | Initial assessment |
| 30 days | Fix deployment |
| 45 days | Public disclosure |

---

## Compliance

### GDPR Compliance

RLM Runtime can be configured for GDPR compliance:

```python
# Data minimization
rlm = RLM(
    model="gpt-4o-mini",  # Use smaller models when possible
    token_budget=4000,    # Minimize data in prompts
)

# Data retention
# Implement log rotation and automatic deletion

# Right to be forgotten
# Provide mechanism to delete trajectory data
```

### SOC 2 Controls

| Control | Implementation |
|---------|----------------|
| Access control | RBAC, secret management |
| Change management | Code review, testing |
| Data protection | Encryption, masking |
| Incident response | Logging, alerting |
| Risk assessment | Regular security reviews |

### Audit Logging

```python
import logging
import structlog

# Enable audit logging
audit_log = logging.getLogger("audit")
audit_log.setLevel(logging.INFO)

# Add audit middleware
audit_log.info(
    "completion_request",
    trajectory_id=str(result.trajectory_id),
    user_id=user_id,
    model=model,
    token_count=result.total_tokens,
    duration_ms=result.duration_ms,
)
```

---

## Best Practices Checklist

### Development

- [ ] Use environment variables for all secrets
- [ ] Never commit secrets to version control
- [ ] Use the sandbox for all code execution
- [ ] Validate all inputs
- [ ] Implement proper error handling
- [ ] Write security-focused tests

### Deployment

- [ ] Use Docker with network isolation
- [ ] Set resource limits (memory, CPU)
- [ ] Configure timeouts
- [ ] Enable TLS for all endpoints
- [ ] Use secrets management
- [ ] Implement log rotation

### Operations

- [ ] Monitor for anomalies
- [ ] Review logs regularly
- [ ] Rotate secrets periodically
- [ ] Keep dependencies updated
- [ ] Conduct security audits
- [ ] Have incident response plan

---

## Security Contacts

- **General security**: `security@snipara.com`
- **Documentation**: See [Snipara Documentation](https://snipara.com/docs)
- **Support**: `support@snipara.com`
