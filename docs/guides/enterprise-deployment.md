# Enterprise Deployment — OpenProxyAI

Guide for IT administrators to intercept and route employee AI traffic through the OpenProxyAI gateway. This enables centralized audit, policy enforcement, and cost control across your organization.

---

## What You Achieve

When employees access OpenAI, Anthropic, Azure, or other LLM APIs from your network, traffic flows through the gateway instead:

```
Before:
  Employee → ChatGPT API → OpenAI
  (No audit, no policy, no cost control)

After:
  Employee → ChatGPT (configured to use gateway) → OpenProxyAI Gateway → OpenAI
  (Full audit trail, policies enforced, costs tracked)
```

Benefits:

- **Complete audit trail:** Every request logged with user, model, cost, policy action
- **Policy enforcement:** Block models, enforce guardrails, redact PII
- **Cost control:** Per-user budgets, department chargebacks, spending alerts
- **Compliance:** HIPAA, SOC 2, GDPR ready — immutable logs, encrypted storage

---

## Method 1: PAC File (Browser + Desktop Apps)

Use a **Proxy Auto-Config (PAC)** file to redirect LLM API traffic to the gateway.

### How It Works

A PAC file is JavaScript that returns the proxy server for a given URL. Deploy it on your organization's web server or DNS:

```javascript
// openproxy.pac
function FindProxyForURL(url, host) {
  // OpenAI API
  if (host === 'api.openai.com' || host === 'api-models.openai.com') {
    return 'HTTPS proxy.company.com:8080';
  }

  // Anthropic API
  if (host === 'api.anthropic.com') {
    return 'HTTPS proxy.company.com:8080';
  }

  // Azure OpenAI
  if (host.match(/.*\.openai\.azure\.com$/)) {
    return 'HTTPS proxy.company.com:8080';
  }

  // Mistral API
  if (host === 'api.mistral.ai') {
    return 'HTTPS proxy.company.com:8080';
  }

  // Everything else goes direct
  return 'DIRECT';
}
```

Save as `openproxy.pac` and serve at `http://proxy.company.com/openproxy.pac`.

### Deployment (Windows via Group Policy)

1. Save the PAC file to your web server
2. In Group Policy Editor (`gpedit.msc`):
   - Computer Configuration → Administrative Templates → Windows Components → Internet Explorer
   - Select "Use automatic configuration script"
   - Set URL to `http://proxy.company.com/openproxy.pac`
   - Apply to your organization's user/computer group

Employees' browsers will automatically route LLM traffic through the gateway.

### Deployment (macOS via JAMF/MDM)

1. Create a WiFi or global proxy profile in JAMF
2. Set:
   - Protocol: Auto-Proxy
   - Auto-Proxy URL: `http://proxy.company.com/openproxy.pac`
3. Deploy to macOS users

### Browser Extensions

For browsers that don't support PAC or mobile devices, deploy a proxy extension:

- **Chrome:** Use `proxy-pac-extension` or Foxit proxy extension
- **Firefox:** Use `FoxyProxy` extension
- **Safari:** Use `SwitchyOmega` extension

Configure each to point to `http://proxy.company.com/openproxy.pac`.

---

## Method 2: DNS Redirection

Override internal DNS to redirect LLM API hostnames to the gateway.

### How It Works

Add DNS A records that point LLM API domains to your gateway:

```
api.openai.com              → 10.0.1.100  (your gateway IP)
api.anthropic.com           → 10.0.1.100
*.openai.azure.com          → 10.0.1.100
api.mistral.ai              → 10.0.1.100
api.cohere.ai               → 10.0.1.100
```

Employees' applications now resolve these domains to your gateway instead of the real API.

### DNS Configuration

Edit your internal DNS server (Microsoft DNS, BIND, etc.):

**Microsoft DNS:**

```
Zone: openai.com
Name: api
Type: A Record
IP Address: 10.0.1.100

Zone: anthropic.com
Name: api
Type: A Record
IP Address: 10.0.1.100
```

**BIND (Linux/Unix):**

```
$ORIGIN company.com
api.openai.com.      IN A  10.0.1.100
api.anthropic.com.   IN A  10.0.1.100
```

### TLS Certificate Considerations

Since DNS redirection makes the gateway impersonate these APIs, the gateway must present a valid TLS certificate for these hostnames.

**Option A: Certificate with SANs**

Request a wildcard certificate that covers:

```
*.openai.com
*.anthropic.com
*.openai.azure.com
api.mistral.ai
api.cohere.ai
```

This is expensive and unwieldy.

**Option B: Use a reverse proxy (better)**

Deploy an HTTPS reverse proxy in front of the gateway that:

1. Listens on 443 for `api.openai.com`, `api.anthropic.com`, etc.
2. Presents a certificate for those domains
3. Routes traffic to the actual gateway backend

Example (nginx):

```nginx
server {
  listen 443 ssl;
  server_name api.openai.com api.anthropic.com;

  ssl_certificate /path/to/cert.pem;
  ssl_certificate_key /path/to/key.pem;

  location / {
    proxy_pass http://openproxy-gateway:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
  }
}
```

**Option C: HSTS preload (TLS inspection)**

If using DNS redirection with a corporate proxy that performs TLS inspection:

1. Set up the proxy to perform TLS inspection
2. Install the corporate CA certificate on all devices
3. The proxy decrypts traffic, inspects it, and re-encrypts

Note: This requires careful implementation and employee consent.

---

## Method 3: Firewall / NGFW Interception

Block direct egress to LLM APIs; force all traffic through the gateway.

### How It Works

Configure your Next-Generation Firewall (NGFW) to:

1. **Identify LLM API traffic** — By domain name (SNI in TLS handshake)
2. **Block direct access** — Return TCP reset or HTTP redirect
3. **Redirect to gateway** — Forward to `https://gateway.company.com`

### Firewall Rules

**Example (Palo Alto Networks):**

1. Create an application object for OpenAI API:
   - Name: `openai-api`
   - Category: `cloud-services`
   - Risk: `medium`

2. Create a security policy:
   - From: Internal users
   - To: Outbound
   - Application: `openai-api`
   - Action: Redirect to `https://gateway.company.com`

3. Create an SSL/TLS inspection rule:
   - Decrypt and inspect HTTPS traffic to LLM APIs
   - Log all traffic

**Example (Cisco ASA):**

```
class-map openai-api
  match application-group OpenAI
  match application-group Anthropic

policy-map openproxy-policy
  class openai-api
    redirect https://gateway.company.com

service-policy openproxy-policy global
```

### Advantages

- No client configuration needed
- Catches all traffic, including mobile and VPN
- Enables TLS inspection for policy enforcement

### Disadvantages

- Requires corporate NGFW (not all organizations have one)
- TLS inspection can impact performance
- Requires ongoing maintenance of application signatures

---

## Method 4: Reverse Proxy Model

Simplest method: Ask employees to configure their AI applications to use the gateway URL instead of the real API.

### How It Works

The gateway acts as a drop-in replacement for OpenAI, Anthropic, etc. Employees configure:

```
OPENAI_API_KEY=opai_xxxxxxxxxxxxxx
OPENAI_BASE_URL=https://gateway.company.com
```

Or in their application:

```python
from openproxy import OpenProxy

client = OpenProxy(
  api_key="opai_xxxxxxxxxxxxxx",
  base_url="https://gateway.company.com"
)
```

The gateway proxies requests to the real providers.

### SDK Migration Path

Most applications require only 1 line change:

**Before (OpenAI SDK):**

```python
import openai
client = openai.OpenAI(api_key="sk-...")
response = client.chat.completions.create(
  model="gpt-4o-mini",
  messages=[{"role": "user", "content": "Hello"}]
)
```

**After (OpenProxyAI SDK):**

```python
from openproxy import OpenProxy  # Change 1: Use OpenProxyAI SDK
client = OpenProxy(api_key="opai_...")  # Change 2: Use gateway API key
response = client.chat.completions.create(
  model="openai/gpt-4o-mini",  # Note: Add provider prefix
  messages=[{"role": "user", "content": "Hello"}]
)
```

### Advantages

- Full control over request/response
- Easy to audit (check base URL configuration)
- Works across all platforms

### Disadvantages

- Requires per-application configuration
- Employees must switch to the OpenProxyAI SDK or equivalent
- Not transparent to legacy applications

---

## Implementation Checklist

### Phase 1: Pilot (Single team)

- [ ] Deploy OpenProxyAI gateway to staging environment
- [ ] Choose a method (PAC file is easiest)
- [ ] Configure 1-2 test applications to route through gateway
- [ ] Verify logs appear in the admin console
- [ ] Test policy enforcement (e.g., block a keyword)
- [ ] Monitor performance (latency, error rates)

### Phase 2: Rollout (Organization-wide)

- [ ] Publish PAC file / DNS changes / NGFW rules to all networks
- [ ] Notify employees via email + documentation
- [ ] Set up training for admins
- [ ] Configure budget limits per department
- [ ] Enable audit logging
- [ ] Set up alerts for cost overages

### Phase 3: Hardening (Ongoing)

- [ ] Review audit logs weekly
- [ ] Update PII detection patterns
- [ ] Rotate API keys quarterly
- [ ] Review and tune rate limits
- [ ] Test disaster recovery / backup procedures

---

## TLS Inspection Considerations

If using DNS redirection or firewall interception, you may need TLS inspection.

### What TLS Inspection Does

1. Gateway intercepts HTTPS traffic destined for `api.openai.com`
2. Decrypts it (using corporate CA certificate installed on employee device)
3. Inspects request/response for policy violations
4. Re-encrypts and forwards

### Privacy & Legal Considerations

- **Disclosure:** Inform employees that AI traffic is inspected
- **Consent:** Ensure they consent to TLS inspection (check local laws)
- **GDPR:** If in EU, ensure lawful basis for inspection (consent or legitimate interest)
- **Logging:** Log what is inspected; delete logs per retention policy

### Certificate Pinning

Some applications use certificate pinning (they reject any certificate other than the real OpenAI certificate). For those apps:

1. Disable certificate pinning (if you control the application)
2. Use a whitelist to bypass TLS inspection for that app
3. Migrate to OpenProxyAI SDK instead

---

## Monitoring and Alerts

### Key Metrics to Monitor

- **Request latency:** Should be <200ms overhead
- **Error rate:** Should be <0.1%
- **Cache hit ratio:** Should be >20% if caching enabled
- **Cost tracking:** Daily spend vs. budget
- **Policy violations:** Number of blocked requests

### Alert Rules

Set up alerts for:

- Cost exceeds 80% of daily budget
- Error rate exceeds 1%
- Latency exceeds 1 second
- Repeated policy violations from same user
- Provider outages (502/503 responses)

---

## Rollback Plan

If the gateway causes issues:

1. **Disable PAC file** — Employees' browsers will go direct to LLM APIs
2. **Revert DNS records** — Restore real IP addresses
3. **Disable NGFW rules** — Allow direct outbound to LLM APIs
4. **Update base URLs** — Tell applications to use real LLM API URLs

Rollback should take <15 minutes.

---

## Next Steps

- **Admin Console** — Log in and create API keys for your teams
- **Policy Configuration** — Set up guardrails, budget limits, and audit retention
- **SDKs** — Point application developers to [guides/sdks.md](./sdks.md)
- **Support** — Contact your account manager for deployment assistance
