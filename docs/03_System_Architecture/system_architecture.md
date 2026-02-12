# System Architecture - OpenProxyAI

## 🏗️ High-Level Architecture

### Architecture Overview

```mermaid
graph TB
    subgraph "Client Layer"
        WebUI[Web UI<br/>React + Vite]
        MobileApp[Mobile PWA]
        APIClient[API Clients<br/>SDKs]
    end
    
    subgraph "API Gateway Layer"
        Kong[Kong/Envoy<br/>API Gateway]
        RateLimit[Rate Limiter<br/>Redis]
    end
    
    subgraph "Core Services"
        AuthService[Auth Service<br/>SSO/SAML/OAuth]
        ProxyEngine[LLM Proxy Engine<br/>FastAPI]
        PolicyEngine[Policy Engine<br/>Rules + DLP]
        CostTracker[Cost Tracker<br/>Real-time metrics]
        AuditLogger[Audit Logger<br/>Compliance logs]
    end
    
    subgraph "Data Layer"
        Postgres[(PostgreSQL<br/>Users, Orgs, Config)]
        Redis[(Redis<br/>Cache, Sessions)]
        S3[S3/MinIO<br/>Audit Logs]
        VectorDB[(Vector DB<br/>PGVector/Qdrant)]
    end
    
    subgraph "LLM Providers"
        OpenAI[OpenAI]
        Anthropic[Anthropic]
        Azure[Azure OpenAI]
        Local[Local LLMs<br/>Ollama/vLLM]
    end
    
    subgraph "Observability"
        Prometheus[Prometheus]
        Grafana[Grafana]
        LangFuse[LangFuse]
    end
    
    WebUI --> Kong
    MobileApp --> Kong
    APIClient --> Kong
    
    Kong --> AuthService
    Kong --> RateLimit
    Kong --> ProxyEngine
    
    ProxyEngine --> PolicyEngine
    ProxyEngine --> CostTracker
    ProxyEngine --> AuditLogger
    
    PolicyEngine --> VectorDB
    CostTracker --> Redis
    AuditLogger --> S3
    
    AuthService --> Postgres
    ProxyEngine --> Postgres
    
    ProxyEngine --> OpenAI
    ProxyEngine --> Anthropic
    ProxyEngine --> Azure
    ProxyEngine --> Local
    
    CostTracker --> Prometheus
    ProxyEngine --> LangFuse
    Prometheus --> Grafana
```

---

## 🎯 Architecture Principles

### 1. **Security by Default**
- Zero trust architecture
- All traffic authenticated and encrypted
- Principle of least privilege
- Defense in depth

### 2. **Scalability**
- Stateless services (scale horizontally)
- Async processing where possible
- Caching aggressively
- Database read replicas

### 3. **Observability**
- Structured logging everywhere
- Distributed tracing (OpenTelemetry)
- Metrics for every operation
- Real-time dashboards

### 4. **Reliability**
- No single point of failure
- Circuit breakers for external services
- Graceful degradation
- Health checks and auto-recovery

### 5. **Simplicity**
- Boring technology (proven stacks)
- Monolith first, microservices when needed
- Minimal dependencies
- Clear abstractions

---

## 🧩 Component Architecture

### Core Components

#### 1. LLM Proxy Engine (Heart of the System)

```mermaid
sequenceDiagram
    participant Client
    participant Auth
    participant Proxy
    participant Policy
    participant Cost
    participant Audit
    participant LLM
    
    Client->>Proxy: POST /v1/chat/completions
    Proxy->>Auth: Validate token
    Auth-->>Proxy: User + Org context
    Proxy->>Policy: Check policies
    Policy->>Policy: PII detection
    Policy->>Policy: Rate limit check
    Policy-->>Proxy: Allow/Deny
    Proxy->>Cost: Check budget
    Cost-->>Proxy: OK
    Proxy->>LLM: Forward request
    LLM-->>Proxy: Stream response
    Proxy->>Cost: Record tokens
    Proxy->>Audit: Log interaction
    Proxy-->>Client: Stream response
```

**Responsibilities:**
- Request ingestion and validation
- Provider routing (smart selection)
- Request transformation (OpenAI → Anthropic format)
- Response streaming
- Error handling and retries

**Technology:**
- **Framework:** FastAPI (async, high performance)
- **Library:** LiteLLM (provider abstraction)
- **Language:** Python 3.11+

**Key Design Decisions:**
- ✅ Async/await for non-blocking I/O
- ✅ Streaming responses (SSE) for chat
- ✅ Provider failover (automatic retry)
- ✅ Request/response middleware pipeline

---

#### 2. Authentication & Authorization Service

```mermaid
graph LR
    subgraph "Auth Methods"
        APIKey[API Key]
        OAuth[OAuth 2.0]
        SAML[SAML SSO]
        LDAP[LDAP/AD]
    end
    
    subgraph "Auth Service"
        Validator[Token Validator]
        RBAC[RBAC Engine]
        Session[Session Manager]
    end
    
    subgraph "Data Store"
        Users[(Users)]
        Orgs[(Organizations)]
        Permissions[(Permissions)]
    end
    
    APIKey --> Validator
    OAuth --> Validator
    SAML --> Validator
    LDAP --> Validator
    
    Validator --> RBAC
    Validator --> Session
    
    RBAC --> Permissions
    Session --> Users
    Users --> Orgs
```

**Multi-Tenancy Model:**
```
Organization (Tenant)
  └── Departments
        └── Users
              └── API Keys
```

**Permission Model:**
```json
{
  "user_id": "usr_123",
  "org_id": "org_456",
  "department_id": "dept_789",
  "roles": ["user", "developer"],
  "permissions": [
    "llm:call:gpt-4",
    "llm:call:claude-3",
    "docs:upload",
    "analytics:view:department"
  ],
  "budget": {
    "daily_limit_usd": 50.00,
    "monthly_limit_usd": 1000.00
  }
}
```

---

#### 3. Policy Enforcement Engine

```mermaid
graph TD
    Request[Incoming Request] --> PreCheck{Pre-flight Checks}
    
    PreCheck -->|Check 1| RateLimit[Rate Limit]
    PreCheck -->|Check 2| Budget[Budget Check]
    PreCheck -->|Check 3| Whitelist[Model Whitelist]
    
    RateLimit --> Allowed1{Within Limit?}
    Budget --> Allowed2{Budget OK?}
    Whitelist --> Allowed3{Model Allowed?}
    
    Allowed1 -->|No| Deny[Return 429]
    Allowed2 -->|No| Deny2[Return 402]
    Allowed3 -->|No| Deny3[Return 403]
    
    Allowed1 -->|Yes| ContentCheck[Content Inspection]
    Allowed2 -->|Yes| ContentCheck
    Allowed3 -->|Yes| ContentCheck
    
    ContentCheck --> PII[PII Detection]
    ContentCheck --> Toxicity[Toxicity Check]
    ContentCheck --> Custom[Custom Rules]
    
    PII --> Action{Action}
    Toxicity --> Action
    Custom --> Action
    
    Action -->|Block| Deny4[Return 403]
    Action -->|Redact| Redact[Redact + Continue]
    Action -->|Alert| Alert[Alert + Continue]
    Action -->|Allow| Forward[Forward to LLM]
```

**Policy Types:**

1. **Rate Limits**
   ```python
   {
     "per_user": "100 requests/hour",
     "per_department": "10,000 requests/hour",
     "per_org": "100,000 requests/hour"
   }
   ```

2. **Budget Controls**
   ```python
   {
     "user_daily_limit": "$10",
     "dept_monthly_limit": "$5,000",
     "org_monthly_limit": "$100,000",
     "alert_threshold": 0.8  # Alert at 80%
   }
   ```

3. **Content Policies**
   ```python
   {
     "pii_detection": True,
     "pii_action": "redact",  # or "block" or "alert"
     "toxicity_check": True,
     "toxicity_threshold": 0.7,
     "custom_regex_blocks": [
       r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
       r"\b\d{16}\b"  # Credit card
     ]
   }
   ```

4. **Model Policies**
   ```python
   {
     "allowed_models": [
       "gpt-4",
       "claude-3-sonnet",
       "llama-3-70b"
     ],
     "blocked_features": [
       "code_interpreter",
       "web_browsing"
     ]
   }
   ```

---

#### 4. Cost Tracking & Analytics

**Real-time Token Counting:**

```python
# Token counting pipeline
Request --> Count Input Tokens
        --> Forward to LLM
        --> Count Output Tokens
        --> Calculate Cost
        --> Update Metrics
        --> Check Budget
        --> Alert if Needed
```

**Cost Calculation:**

```python
cost = (input_tokens * input_price) + (output_tokens * output_price)

# Example: GPT-4
input_price = $0.03 / 1K tokens
output_price = $0.06 / 1K tokens

request_cost = (500 * 0.03/1000) + (1500 * 0.06/1000)
             = $0.015 + $0.090
             = $0.105
```

**Aggregation Levels:**

```
Organization
  ├── Total spend
  ├── By Department
  │     ├── Engineering: $5,234
  │     ├── Product: $2,100
  │     └── Sales: $890
  ├── By Model
  │     ├── GPT-4: $4,500
  │     ├── Claude-3: $2,800
  │     └── Llama-3: $924
  ├── By User
  │     └── Top 10 spenders
  └── By Time
        ├── Hourly
        ├── Daily
        └── Monthly
```

---

#### 5. Audit Logging System

**What Gets Logged:**

```json
{
  "id": "log_abc123",
  "timestamp": "2026-02-12T10:30:45.123Z",
  "request": {
    "user_id": "usr_123",
    "org_id": "org_456",
    "dept_id": "dept_789",
    "model": "gpt-4",
    "input_tokens": 500,
    "prompt_hash": "sha256:abc...",  // Not full prompt (privacy)
    "prompt_sample": "What is...",   // First 50 chars
    "metadata": {
      "ip_address": "10.0.1.5",
      "user_agent": "openproxyai-sdk/1.0",
      "request_id": "req_xyz789"
    }
  },
  "response": {
    "output_tokens": 1500,
    "completion_hash": "sha256:def...",
    "latency_ms": 2340,
    "provider": "openai",
    "cost_usd": 0.105
  },
  "policy": {
    "policies_applied": ["rate_limit", "pii_check"],
    "pii_detected": false,
    "actions_taken": []
  },
  "compliance": {
    "data_classification": "internal",
    "retention_days": 90,
    "encrypted": true
  }
}
```

**Storage Strategy:**

- **Hot storage** (last 30 days): PostgreSQL
- **Warm storage** (31-90 days): S3 + Parquet
- **Cold storage** (90+ days): S3 Glacier
- **Search**: Elasticsearch (optional, enterprise only)

**Compliance Export:**

```bash
# Generate SOC 2 audit report
$ openproxyai audit export \
    --start-date 2026-01-01 \
    --end-date 2026-12-31 \
    --format csv \
    --include pii-access,cost-anomalies,policy-violations
```

---

## 🔄 Data Flow Architecture

### Request Flow (Normal Path)

```mermaid
sequenceDiagram
    participant U as User/SDK
    participant G as API Gateway
    participant A as Auth Service
    participant P as Proxy Engine
    participant PE as Policy Engine
    participant C as Cost Tracker
    participant L as LLM Provider
    participant AL as Audit Logger
    
    U->>G: POST /v1/chat/completions
    G->>A: Validate Bearer token
    A->>A: Check token, load user context
    A-->>G: User{id, org, dept, perms}
    G->>P: Forward request + context
    P->>PE: Check policies
    PE->>PE: Rate limit OK?
    PE->>PE: Budget OK?
    PE->>PE: Content OK? (PII scan)
    PE-->>P: ALLOW
    P->>C: Pre-deduct estimate
    P->>L: Forward to LLM
    L-->>P: Stream response
    P->>C: Update actual cost
    P->>AL: Log request/response (async)
    P-->>U: Stream response
```

### Policy Violation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant P as Proxy
    participant PE as Policy Engine
    participant N as Notification Service
    
    U->>P: Request with PII
    P->>PE: Check content
    PE->>PE: PII detected (SSN)
    PE->>PE: Policy: BLOCK + ALERT
    PE->>N: Send alert to admin
    N->>N: Email admin
    N->>N: Slack webhook
    PE-->>P: DENY + reason
    P-->>U: 403 Forbidden<br/>"PII detected in prompt"
```

### Cost Limit Exceeded Flow

```mermaid
sequenceDiagram
    participant U as User
    participant P as Proxy
    participant C as Cost Tracker
    participant N as Notification
    
    U->>P: Request
    P->>C: Check budget
    C->>C: User spent $49.80/$50 daily
    C->>C: This request = $1.50
    C->>C: Would exceed limit
    C->>N: Alert user + admin
    C-->>P: DENY (budget exceeded)
    P-->>U: 402 Payment Required<br/>"Daily budget exceeded"
```

---

## 🗄️ Data Architecture

### Database Schema (Core Tables)

```sql
-- Organizations (Tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan VARCHAR(50) NOT NULL, -- 'free', 'starter', 'growth', 'enterprise'
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Departments
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    budget_monthly_usd DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    dept_id UUID REFERENCES departments(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50), -- 'admin', 'user', 'viewer'
    budget_daily_usd DECIMAL(10,2),
    budget_monthly_usd DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- API Keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL, -- First 8 chars for display
    name VARCHAR(100),
    permissions JSONB DEFAULT '[]',
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- LLM Requests (Hot storage - last 30 days)
CREATE TABLE llm_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    org_id UUID NOT NULL REFERENCES organizations(id),
    dept_id UUID REFERENCES departments(id),
    model VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd DECIMAL(10,6) NOT NULL,
    latency_ms INTEGER,
    status VARCHAR(50), -- 'success', 'error', 'blocked'
    error_message TEXT,
    prompt_hash VARCHAR(64),
    request_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast queries
CREATE INDEX idx_requests_user_date ON llm_requests(user_id, created_at DESC);
CREATE INDEX idx_requests_org_date ON llm_requests(org_id, created_at DESC);
CREATE INDEX idx_requests_created_at ON llm_requests(created_at DESC);

-- Cost aggregations (Materialized view for performance)
CREATE MATERIALIZED VIEW daily_costs AS
SELECT 
    org_id,
    dept_id,
    user_id,
    model,
    DATE(created_at) as date,
    SUM(cost_usd) as total_cost,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    COUNT(*) as request_count
FROM llm_requests
WHERE status = 'success'
GROUP BY org_id, dept_id, user_id, model, DATE(created_at);

-- Policies
CREATE TABLE policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'rate_limit', 'budget', 'content', 'model'
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit logs (Compliance)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL, -- 'llm_request', 'settings_changed', 'user_added'
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_org_date ON audit_logs(org_id, created_at DESC);
```

### Redis Data Structures

```python
# Rate limiting (sliding window)
ZADD rate_limit:user:{user_id} {timestamp} {request_id}
ZREMRANGEBYSCORE rate_limit:user:{user_id} 0 {timestamp - 3600}
ZCARD rate_limit:user:{user_id}  # Count requests in last hour

# Budget tracking (real-time spend)
HSET budget:user:{user_id}:daily {date} {amount}
HINCRBY budget:user:{user_id}:daily {date} {cost}

# Session management
SETEX session:{token} 86400 {user_data_json}

# Cache model pricing
SET model:pricing:gpt-4 '{input: 0.03, output: 0.06}'
EXPIRE model:pricing:gpt-4 3600

# Provider health check
SETEX provider:openai:health 60 'healthy'
SET provider:openai:latency_p95 250
```

---

## 🚀 Deployment Architecture

### Docker Compose (MVP / Single-server)

```yaml
version: '3.8'

services:
  proxy:
    image: openproxyai/proxy:latest
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://user:pass@postgres:5432/openproxyai
      REDIS_URL: redis://redis:6379
    
  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: openproxyai
      POSTGRES_USER: user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
  
  admin_ui:
    image: openproxyai/admin-ui:latest
    ports:
      - "3000:3000"
    environment:
      API_URL: http://proxy:8000

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes (Production)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openproxyai-proxy
spec:
  replicas: 3
  selector:
    matchLabels:
      app: openproxyai-proxy
  template:
    metadata:
      labels:
        app: openproxyai-proxy
    spec:
      containers:
      - name: proxy
        image: openproxyai/proxy:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: openproxyai-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: openproxyai-secrets
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

---

## 📊 Scalability Strategy

### Horizontal Scaling

```mermaid
graph LR
    LB[Load Balancer] --> P1[Proxy 1]
    LB --> P2[Proxy 2]
    LB --> P3[Proxy 3]
    LB --> Pn[Proxy N]
    
    P1 --> PG[(PostgreSQL<br/>Primary)]
    P2 --> PG
    P3 --> PG
    Pn --> PG
    
    P1 --> R1[(Redis<br/>Cluster)]
    P2 --> R1
    P3 --> R1
    Pn --> R1
    
    PG --> PGR1[(Read Replica 1)]
    PG --> PGR2[(Read Replica 2)]
```

**Scaling Triggers:**

| Metric | Threshold | Action |
|--------|-----------|--------|
| CPU Utilization | > 70% | Add 1 pod |
| Memory | > 80% | Add 1 pod |
| Request Queue | > 100 | Add 2 pods |
| Response Time p95 | > 2s | Add 1 pod |

### Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Request Latency** | < 100ms overhead | p95 |
| **Throughput** | 1,000+ req/sec per pod | Load test |
| **Database Queries** | < 10ms | p95 |
| **Cache Hit Rate** | > 90% | Redis stats |
| **Availability** | 99.9% | Uptime |

---

## 🔐 Security Architecture

### Defense in Depth

```
Layer 1: Network Security
  ├── TLS 1.3 encryption
  ├── DDoS protection (Cloudflare)
  └── Firewall rules

Layer 2: API Gateway
  ├── Rate limiting
  ├── IP whitelisting (enterprise)
  └── Request validation

Layer 3: Authentication
  ├── Token validation
  ├── MFA (enterprise)
  └── Session management

Layer 4: Authorization
  ├── RBAC
  ├── Resource-level permissions
  └── Org/dept isolation

Layer 5: Application Security
  ├── Input sanitization
  ├── SQL injection prevention
  ├── XSS protection
  └── CSRF tokens

Layer 6: Data Security
  ├── Encryption at rest
  ├── PII detection/redaction
  └── Audit logging

Layer 7: Monitoring
  ├── Anomaly detection
  ├── Security alerts
  └── Incident response
```

### Secrets Management

```python
# Never in code
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")  # ❌ Bad

# Use secret manager
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(vault_url=VAULT_URL, credential=credential)
db_password = client.get_secret("db-password").value  # ✅ Good
```

---

## 🎯 Technology Stack Summary

### Backend
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **LLM Library:** LiteLLM
- **Database:** PostgreSQL 16 + PGVector
- **Cache:** Redis 7
- **Queue:** Redis + RQ (simple) or Celery (if needed)
- **Object Storage:** S3 / MinIO

### Frontend
- **Framework:** React 18+ TypeScript
- **Build:** Vite
- **UI Library:** Tailwind CSS + shadcn/ui
- **State:** Zustand (simple) or React Query
- **Charts:** Recharts

### DevOps
- **Container:** Docker
- **Orchestration:** Kubernetes (optional)
- **CI/CD:** GitHub Actions
- **Monitoring:** Prometheus + Grafana
- **Logs:** ELK Stack (optional) or CloudWatch
- **Tracing:** OpenTelemetry

### Infrastructure
- **Cloud:** Azure (primary), AWS (compatible)
- **IaC:** Terraform
- **Secrets:** Azure Key Vault / AWS Secrets Manager

---

*Next: [LLM Proxy Engine →](../03_LLM_Proxy_Engine/README.md)*
