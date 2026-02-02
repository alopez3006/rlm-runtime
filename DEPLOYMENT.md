# Deployment Guide

This document covers deployment strategies, Docker usage, CI/CD, and production considerations for RLM Runtime.

## Table of Contents

- [Overview](#overview)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Serverless Deployment](#serverless-deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Production Checklist](#production-checklist)
- [Monitoring](#monitoring)
- [Scaling](#scaling)

---

## Overview

RLM Runtime can be deployed in various environments:

| Environment | Use Case | Isolation |
|-------------|----------|-----------|
| Local | Development | Limited |
| Docker | Production, untrusted code | Full |
| WebAssembly | Serverless, browser | Full |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌───────────┐  ┌───────────┐  ┌───────────┐
│  RLM Pod  │  │  RLM Pod  │  │  RLM Pod  │
│  (Docker) │  │  (Docker) │  │  (Docker) │
└───────────┘  └───────────┘  └───────────┘
        │             │             │
        └─────────────┼─────────────┘
                      ▼
        ┌───────────────────────────────┐
        │     Shared Storage (Logs)     │
        └───────────────────────────────┘
```

---

## Docker Deployment

### Basic Docker Setup

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install RLM Runtime
RUN pip install rlm-runtime[docker,mcp]

# Copy entrypoint
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["mcp-serve"]
```

```bash
# Build image
docker build -t rlm-runtime:latest .

# Run container
docker run -d \
  --name rlm \
  -p 8080:8080 \
  -e RLM_MODEL=gpt-4o \
  -e RLM_ENVIRONMENT=docker \
  -v rlm-logs:/app/logs \
  rlm-runtime:latest
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  rlm:
    build: .
    ports:
      - "8080:8080"
    environment:
      - RLM_MODEL=gpt-4o
      - RLM_ENVIRONMENT=docker
      - RLM_LOG_DIR=/app/logs
      - RLM_DOCKER_MEMORY=1g
      - RLM_DOCKER_CPUS=2.0
      - SNIPARA_API_KEY=${SNIPARA_API_KEY}
      - SNIPARA_PROJECT_SLUG=${SNIPARA_PROJECT_SLUG}
    volumes:
      - rlm-logs:/app/logs
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
    healthcheck:
      test: ["CMD", "rlm", "doctor"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  rlm-logs:
```

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f rlm

# Stop services
docker-compose down
```

### Production Docker Image

```dockerfile
# Production-optimized Dockerfile
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Build and install RLM
RUN pip install --no-cache-dir \
    --prefix=/install \
    rlm-runtime[docker,mcp,visualizer]

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Create non-root user
RUN useradd -m rlm && chown -R rlm:rlm /app
USER rlm

# Default environment
ENV RLM_ENVIRONMENT=docker \
    RLM_LOG_DIR=/app/logs \
    RLM_DOCKER_MEMORY=512m \
    RLM_DOCKER_CPUS=1.0

# Create log directory
RUN mkdir -p /app/logs && chown rlm:rlm /app/logs

EXPOSE 8080

CMD ["mcp-serve"]
```

---

## Kubernetes Deployment

### Deployment Config

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rlm-runtime
  labels:
    app: rlm-runtime
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rlm-runtime
  template:
    metadata:
      labels:
        app: rlm-runtime
    spec:
      serviceAccountName: rlm
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: rlm
        image: rlm-runtime:latest
        ports:
        - containerPort: 8080
        env:
        - name: RLM_MODEL
          value: "gpt-4o"
        - name: RLM_ENVIRONMENT
          value: "docker"
        - name: RLM_LOG_DIR
          value: "/app/logs"
        - name: SNIPARA_API_KEY
          valueFrom:
            secretKeyRef:
              name: rlm-secrets
              key: snipara-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        volumeMounts:
        - name: logs
          mountPath: /app/logs
        livenessProbe:
          exec:
            command: ["rlm", "doctor"]
          initialDelaySeconds: 30
          periodSeconds: 60
        readinessProbe:
          exec:
            command: ["rlm", "doctor"]
          initialDelaySeconds: 10
          periodSeconds: 30
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: rlm-logs-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: rlm-service
spec:
  selector:
    app: rlm-runtime
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

### HPA (Horizontal Pod Autoscaler)

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rlm-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rlm-runtime
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Serverless Deployment

### AWS Lambda

```python
# lambda/handler.py
import json
from rlm import RLM
import asyncio

# Cold start initialization
rlm = RLM(
    model="gpt-4o-mini",
    environment="docker",
)

async def handler(event, context):
    """Lambda handler for RLM Runtime."""
    try:
        prompt = event.get("prompt", "")
        result = await rlm.completion(prompt)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "response": result.response,
                "trajectory_id": str(result.trajectory_id),
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

# For Lambda with Docker
# Use AWS Lambda Container Image Support
```

### Google Cloud Functions

```python
# main.py
from rlm import RLM
import asyncio

rlm = None

def init_rlm():
    global rlm
    if rlm is None:
        rlm = RLM(
            model="gpt-4o-mini",
            environment="docker",
        )

def completion(request):
    init_rlm()

    request_json = request.get_json(silent=True)
    prompt = request_json.get("prompt", "")

    result = asyncio.run(rlm.completion(prompt))

    return {"response": result.response}
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: Deployment environment
        required: true
        default: staging
        type: choice
        options:
        - staging
        - production

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -e ".[dev]"
        pip install rlm-runtime[docker]

    - name: Run tests
      run: pytest --cov=rlm

    - name: Lint
      run: |
        ruff check src/
        mypy src/

    - name: Build Docker image
      run: |
        docker build -t rlm-runtime:${{ github.sha }} .
        docker tag rlm-runtime:${{ github.sha }} rlm-runtime:latest

  deploy-staging:
    needs: test
    if: github.event_name == 'workflow_dispatch' && github.event.inputs.environment == 'staging'
    runs-on: ubuntu-latest
    environment: staging
    steps:
    - name: Deploy to staging
      run: |
        # Push to registry
        docker push registry.example.com/rlm-runtime:${{ github.sha }}

        # Update Kubernetes
        kubectl set image deployment/rlm-runtime \
          rlm=registry.example.com/rlm-runtime:${{ github.sha }} \
          -n staging

  deploy-production:
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
    - name: Deploy to production
      run: |
        # Wait for staging validation
        echo "Deployment to production requires manual approval"
        # This would typically use a manual approval step in GitHub Actions
```

---

## Production Checklist

### Security

- [ ] Use API keys from secrets manager
- [ ] Enable Docker network isolation (`docker_network_disabled=true`)
- [ ] Restrict file access with `allowed_paths`
- [ ] Use non-root user in containers
- [ ] Enable TLS for MCP server
- [ ] Rotate API keys regularly
- [ ] Audit logs for sensitive data

### Performance

- [ ] Set appropriate `max_depth` and `token_budget`
- [ ] Configure `max_parallel` based on workload
- [ ] Use Docker memory limits to prevent OOM
- [ ] Enable logging for debugging
- [ ] Monitor token usage and costs
- [ ] Use caching where appropriate

### Reliability

- [ ] Set appropriate timeouts
- [ ] Configure retry logic for API calls
- [ ] Set up health checks
- [ ] Configure log rotation
- [ ] Set up alerts for errors
- [ ] Backup trajectory logs

### Monitoring

```bash
# Key metrics to monitor
- Request latency (p50, p95, p99)
- Error rate
- Token usage per request
- Cost per day
- Container memory/CPU
- Queue depth (if async)
```

---

## Monitoring

### Prometheus Metrics

```python
# metrics.py
from prometheus_client import Counter, Histogram, start_http_server

# Start metrics server
start_http_server(8000)

# Define metrics
REQUEST_COUNT = Counter('rlm_requests_total', 'Total requests')
REQUEST_LATENCY = Histogram('rlm_request_duration_seconds', 'Request latency')
TOKEN_USAGE = Histogram('rlm_tokens_used_total', 'Tokens per request')
COST_USAGE = Counter('rlm_cost_usd_total', 'Total cost in USD')
```

### Health Checks

```bash
# Check health
curl http://localhost:8080/health

# Response
{
  "status": "healthy",
  "version": "2.0.0",
  "components": {
    "llm": "healthy",
    "repl": "healthy",
    "storage": "healthy"
  }
}
```

### Logging

```python
# Structured logging with structlog
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.RealLogger,
)

log = structlog.get_logger()
```

---

## Scaling

### Horizontal Scaling

1. **Load Balancer** - Distribute requests across RLM pods
2. **Stateless Design** - No shared state between requests
3. **Shared Storage** - Use S3 or similar for trajectory logs
4. **Connection Pooling** - For database-backed features

### Vertical Scaling

1. **Increase Memory** - For larger code execution
2. **Increase CPU** - For parallel tool execution
3. **GPU Support** - If using GPU-accelerated models

### Request Queuing

```python
# Use a queue for high-load scenarios
import asyncio
from redis import Redis
from rq import Queue

redis = Redis()
queue = Queue('rlm-tasks', connection=redis)

def process_completion(prompt, **kwargs):
    rlm = RLM(**kwargs)
    result = asyncio.run(rlm.completion(prompt))
    return result

# Enqueue task
job = queue.enqueue(
    process_completion,
    "Your prompt here",
    model="gpt-4o-mini",
)
```
