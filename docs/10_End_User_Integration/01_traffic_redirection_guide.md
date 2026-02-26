# End-User Integration: Traffic Redirection Guide

**OpenProxyAI — IT Admin Deployment Reference**

> This guide explains how to redirect employee AI traffic (ChatGPT, Claude, Mistral, etc.) from the public internet to your internal OpenProxyAI gateway, so that all prompts pass through your security, compliance, and observability controls.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Method 1: PAC File (Proxy Auto-Configuration)](#2-method-1-pac-file)
3. [Method 2: Browser Extension / Plugin](#3-method-2-browser-extension)
4. [Method 3: DNS Redirection](#4-method-3-dns-redirection)
5. [Method 4: Layer 4 / Firewall Interception (WCCP)](#5-method-4-firewall-interception)
6. [Method 5: Reverse Proxy Model](#6-method-5-reverse-proxy-model)
7. [TLS Inspection & Certificate Deployment](#7-tls-inspection)
8. [Browser Extension Development Guide](#8-browser-extension-development)
9. [Reference Tools & Repos](#9-reference-tools)
10. [Decision Matrix](#10-decision-matrix)

---

## 1. Architecture Overview

### The Goal

Instead of employees hitting `api.openai.com`, `api.anthropic.com`, or `api.mistral.ai` directly, all traffic is routed through your OpenProxyAI instance:

```
Employee Device
      │
      ▼
OpenProxyAI Gateway (openproxai.yourdomain.com)
      │
      ├──► OpenAI (api.openai.com)
      ├──► Anthropic (api.anthropic.com)
      ├──► Azure OpenAI
      └──► Mistral, Cohere, etc.
```

### What Gets Intercepted

- **API traffic:** SDK calls from developer tools, scripts, CI/CD pipelines
- **Browser traffic:** ChatGPT.com, Claude.ai, Mistral.ai web interfaces
- **Application traffic:** Copilot, Cursor, VS Code extensions using LLM APIs

### Forward Proxy vs. Reverse Proxy

| Model | How It Works | Best For |
|---|---|---|
| **Forward Proxy** | Client is configured to send traffic through the proxy | API traffic, developer tools |
| **Reverse Proxy** | Users access `openproxai.yourdomain.com` instead of the AI vendor URL | Browser-based chat interfaces |
| **Transparent Proxy** | Network intercepts traffic without client configuration | Full org rollout, no endpoint config |

---

## 2. Method 1: PAC File

A **Proxy Auto-Configuration (PAC)** file is a JavaScript function that browsers and OS-level HTTP clients call to decide whether to use a proxy for a given URL.

### How It Works

1. You host a `.pac` file on an internal web server
2. Clients are pointed to the PAC file URL via GPO, Intune, or MDM
3. When a browser opens `chat.openai.com`, it calls the PAC function
4. The PAC function returns `PROXY openproxai.yourdomain.com:8080`
5. The browser routes the request through your gateway

### Sample PAC File

```javascript
function FindProxyForURL(url, host) {
  // AI provider domains to intercept
  var aiDomains = [
    "api.openai.com",
    "chat.openai.com",
    "chatgpt.com",
    "api.anthropic.com",
    "claude.ai",
    "api.mistral.ai",
    "chat.mistral.ai",
    "api.cohere.ai",
    "generativelanguage.googleapis.com",
    "api.groq.com"
  ];

  for (var i = 0; i < aiDomains.length; i++) {
    if (dnsDomainIs(host, aiDomains[i]) || host === aiDomains[i]) {
      return "PROXY openproxai.yourdomain.com:8080";
    }
  }

  // All other traffic goes direct
  return "DIRECT";
}
```

### Hosting the PAC File

```nginx
# nginx config — serve the PAC file with correct MIME type
server {
    listen 80;
    server_name internal-pac.yourdomain.com;

    location /proxy.pac {
        root /var/www/pac;
        types { }
        default_type application/x-ns-proxy-autoconfig;
        add_header Cache-Control "no-cache, no-store";
    }
}
```

### Deploying via Group Policy (Windows)

```
Computer Configuration
  └── Administrative Templates
        └── Windows Components
              └── Internet Explorer
                    └── Use automatic proxy configuration script
                          → Value: http://internal-pac.yourdomain.com/proxy.pac
```

### Deploying via Intune (macOS / Windows)

```xml
<!-- Intune Wi-Fi profile — ProxyPACURL -->
<dict>
    <key>ProxyType</key>
    <string>Auto</string>
    <key>ProxyPACURL</key>
    <string>http://internal-pac.yourdomain.com/proxy.pac</string>
</dict>
```

### Deploying via Chrome Enterprise Policy

```json
{
  "ProxySettings": {
    "ProxyMode": "pac_script",
    "ProxyPacUrl": "http://internal-pac.yourdomain.com/proxy.pac"
  }
}
```

### Pros & Cons

| Pros | Cons |
|---|---|
| No network changes required | Requires endpoint configuration |
| Granular per-domain control | Users can bypass if they have admin rights |
| Works for browser + OS-level HTTP clients | Does not intercept non-HTTP traffic |
| Easy to update centrally | PAC file must be reachable from all clients |

---

## 3. Method 2: Browser Extension

A browser extension intercepts requests at the browser level before they leave the device. This is the most user-visible method but also the most controllable.

### Architecture

```
User types prompt in ChatGPT
         │
         ▼
Chrome Extension (background.js)
  └── Intercepts fetch() / XHR to api.openai.com
  └── Rewrites request to openproxai.yourdomain.com/v1/chat/completions
  └── Injects Authorization header with org API key
         │
         ▼
OpenProxyAI Gateway
```

### Chrome Extension: `manifest.json`

```json
{
  "manifest_version": 3,
  "name": "OpenProxyAI Redirector",
  "version": "1.0.0",
  "description": "Routes AI API traffic through your organization's OpenProxyAI gateway",
  "permissions": [
    "declarativeNetRequest",
    "storage"
  ],
  "host_permissions": [
    "https://api.openai.com/*",
    "https://api.anthropic.com/*",
    "https://api.mistral.ai/*",
    "https://openproxai.yourdomain.com/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup.html",
    "default_icon": "icon.png"
  }
}
```

### Chrome Extension: `background.js`

```javascript
// background.js — Intercept and redirect AI API requests
chrome.webRequest.onBeforeRequest.addListener(
  function(details) {
    const proxyBase = "https://openproxai.yourdomain.com";
    const url = new URL(details.url);

    // Map vendor endpoints to proxy endpoints
    const redirectMap = {
      "api.openai.com": proxyBase,
      "api.anthropic.com": proxyBase,
      "api.mistral.ai": proxyBase,
      "api.cohere.ai": proxyBase
    };

    if (redirectMap[url.hostname]) {
      const newUrl = proxyBase + url.pathname + url.search;
      return { redirectUrl: newUrl };
    }
  },
  {
    urls: [
      "https://api.openai.com/*",
      "https://api.anthropic.com/*",
      "https://api.mistral.ai/*",
      "https://api.cohere.ai/*"
    ]
  },
  ["blocking"]
);
```

### Firefox Extension: `background.js`

```javascript
// Firefox uses browser.webRequest (Manifest V2)
browser.webRequest.onBeforeRequest.addListener(
  function(details) {
    const proxyBase = "https://openproxai.yourdomain.com";
    const url = new URL(details.url);

    const aiHosts = [
      "api.openai.com",
      "api.anthropic.com",
      "api.mistral.ai"
    ];

    if (aiHosts.includes(url.hostname)) {
      return { redirectUrl: proxyBase + url.pathname + url.search };
    }
  },
  { urls: ["<all_urls>"] },
  ["blocking"]
);
```

### Packaging & Distribution

**Chrome (.crx):**
```bash
# Pack extension from Chrome DevTools
# chrome://extensions → Developer mode → Pack extension
# Or use crx3 tool:
npx crx3 pack ./extension-dir --output openproxyai-redirector.crx
```

**Firefox (.xpi):**
```bash
# Sign with Mozilla's web-ext tool
npm install -g web-ext
web-ext sign --api-key=$AMO_JWT_ISSUER --api-secret=$AMO_JWT_SECRET
# Or for self-hosted (enterprise):
web-ext build  # produces .zip, rename to .xpi
```

**Enterprise deployment:**
- Chrome: Push via Chrome Enterprise `ExtensionInstallForcelist` policy
- Firefox: Use `extensions.autoDisableScopes` + signed XPI via MDM
- Edge: Use `ExtensionInstallForcelist` in Microsoft Edge policies

### Pros & Cons

| Pros | Cons |
|---|---|
| Fine-grained control per request | Only covers browser traffic (not SDK/CLI) |
| Can inject org headers/tokens | Requires browser extension management |
| Works without network changes | Users on unmanaged devices can uninstall |
| Can show UI feedback to users | Manifest V3 limits some capabilities |

---

## 4. Method 3: DNS Redirection

Override DNS so that AI provider domains resolve to your proxy's IP address instead of the vendor's servers.

### How It Works

```
Employee: curl https://api.openai.com/v1/chat/completions
         │
         ▼
DNS Query: api.openai.com → ?
         │
         ▼
Internal DNS Server (overridden zone)
  api.openai.com → 10.0.1.50  (your proxy IP)
         │
         ▼
OpenProxyAI at 10.0.1.50 receives the request
  └── Uses SNI to identify the target vendor
  └── Forwards to real api.openai.com
```

### DNS Override Configuration

**BIND / named.conf:**
```
zone "api.openai.com" {
    type master;
    file "/etc/bind/zones/openai-override.db";
};
```

**Zone file (`openai-override.db`):**
```
$TTL 300
@   IN  SOA ns1.yourdomain.com. admin.yourdomain.com. (
            2026022601 ; Serial
            3600       ; Refresh
            900        ; Retry
            604800     ; Expire
            300 )      ; Minimum TTL

@   IN  NS  ns1.yourdomain.com.
@   IN  A   10.0.1.50    ; OpenProxyAI gateway IP
*   IN  A   10.0.1.50    ; Catch all subdomains
```

**Windows DNS Server (PowerShell):**
```powershell
# Create a new primary zone for the AI domain
Add-DnsServerPrimaryZone -Name "api.openai.com" -ZoneFile "openai-override.dns"

# Add A record pointing to your proxy
Add-DnsServerResourceRecordA `
  -ZoneName "api.openai.com" `
  -Name "@" `
  -IPv4Address "10.0.1.50"

# Wildcard for subdomains
Add-DnsServerResourceRecordA `
  -ZoneName "api.openai.com" `
  -Name "*" `
  -IPv4Address "10.0.1.50"
```

**Pi-hole / dnsmasq:**
```
# /etc/dnsmasq.d/ai-proxy.conf
address=/api.openai.com/10.0.1.50
address=/api.anthropic.com/10.0.1.50
address=/api.mistral.ai/10.0.1.50
address=/chat.openai.com/10.0.1.50
address=/claude.ai/10.0.1.50
```

### Important: TLS Handling

When you redirect DNS, the client still expects a valid TLS certificate for `api.openai.com`. Your proxy must either:

1. **Terminate TLS** with a certificate for `api.openai.com` (requires deploying a root CA — see [Section 7](#7-tls-inspection))
2. **Use SNI passthrough** — read the SNI header and forward to the real vendor without decrypting

**HAProxy SNI passthrough config:**
```haproxy
frontend ai_sni_passthrough
    bind *:443
    mode tcp
    tcp-request inspect-delay 5s
    tcp-request content accept if { req_ssl_hello_type 1 }

    use_backend openai_backend  if { req_ssl_sni -i api.openai.com }
    use_backend anthropic_backend if { req_ssl_sni -i api.anthropic.com }

backend openai_backend
    mode tcp
    server openai_real api.openai.com:443 ssl verify required

backend anthropic_backend
    mode tcp
    server anthropic_real api.anthropic.com:443 ssl verify required
```

### Pros & Cons

| Pros | Cons |
|---|---|
| No endpoint configuration needed | Requires TLS handling (root CA or SNI passthrough) |
| Transparent to users | Can be bypassed with custom DNS (8.8.8.8) |
| Works for all traffic types | DNS propagation delay |
| Centrally managed | Harder to debug |

---

## 5. Method 4: Firewall Interception (WCCP / Layer 4)

Intercept traffic at the network level using firewall rules or WCCP (Web Cache Communication Protocol). No endpoint configuration required.

### iptables / nftables (Linux Gateway)

```bash
# Redirect outbound HTTPS to AI domains through the proxy
# Requires the gateway to be the default route for the network segment

# Using iptables
iptables -t nat -A PREROUTING \
  -p tcp \
  --dport 443 \
  -m string --string "api.openai.com" --algo bm \
  -j DNAT --to-destination 10.0.1.50:443

# Using nftables (modern alternative)
table ip nat {
  chain prerouting {
    type nat hook prerouting priority -100;
    tcp dport 443 ip daddr { 104.18.7.192/24 } dnat to 10.0.1.50:443
  }
}
```

> **Note:** IP-based rules require maintaining a list of vendor IP ranges, which change frequently. DNS-based or SNI-based interception is more reliable.

### pfSense / OPNsense

1. Navigate to **Firewall → NAT → Port Forward**
2. Add rule:
   - Interface: LAN
   - Protocol: TCP
   - Destination: AI vendor IP ranges (or use pfBlockerNG for domain-based blocking)
   - Redirect target IP: `10.0.1.50` (your proxy)
   - Redirect target port: `443`

### Cisco ASA / Firepower (WCCP)

```
# Enable WCCP on the ASA
wccp web-cache redirect-list AI_DOMAINS
wccp interface inside in

# Define the redirect ACL
access-list AI_DOMAINS extended permit tcp any host api.openai.com eq 443
access-list AI_DOMAINS extended permit tcp any host api.anthropic.com eq 443
```

### Zscaler / Bluecoat ProxySG

If your organization already uses Zscaler or Bluecoat, you can add OpenProxyAI as a **chained proxy** or configure SSL inspection policies to forward AI traffic to your gateway before it reaches the vendor.

**Zscaler chained proxy:**
```
Zscaler Cloud → Forward AI traffic → OpenProxyAI → Vendor API
```

Configure in Zscaler Admin Portal:
- **Policy → Forwarding Control → Add Rule**
- Destination: AI vendor domains
- Action: Forward to `openproxai.yourdomain.com:8080`

### Pros & Cons

| Pros | Cons |
|---|---|
| Completely transparent to endpoints | Requires network-level access |
| Catches all traffic types | Complex to configure correctly |
| No client software needed | IP ranges change; domain-based rules preferred |
| Works for unmanaged devices | TLS inspection still needed for payload visibility |

---

## 6. Method 5: Reverse Proxy Model

Instead of intercepting traffic to vendor URLs, you give employees a single internal URL to use: `openproxai.yourdomain.com`. This is the simplest model for **new deployments** where you control the tooling.

### How It Works

```
Developer code:
  client = OpenAI(
    api_key="org-key-abc123",
    base_url="https://openproxai.yourdomain.com/v1"
  )

# All requests go to your proxy, which routes to the right vendor
```

### nginx Reverse Proxy Config

```nginx
server {
    listen 443 ssl http2;
    server_name openproxai.yourdomain.com;

    ssl_certificate     /etc/ssl/openproxai.crt;
    ssl_certificate_key /etc/ssl/openproxai.key;

    # OpenAI-compatible endpoint
    location /v1/ {
        proxy_pass http://openproxyai-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Streaming support
        proxy_buffering off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }

    # Admin dashboard
    location /admin/ {
        proxy_pass http://openproxyai-backend:8000/admin/;
        # Add IP allowlist for admin access
        allow 10.0.0.0/8;
        deny all;
    }
}
```

### SDK Integration (One-Line Change)

```python
# Before (direct to OpenAI)
from openai import OpenAI
client = OpenAI(api_key="sk-...")

# After (through OpenProxyAI)
from openai import OpenAI
client = OpenAI(
    api_key="openproxyai-org-key-abc123",
    base_url="https://openproxai.yourdomain.com/v1"
)

# Everything else stays the same
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Environment Variable Approach

```bash
# .env file (or system environment)
OPENAI_API_KEY=openproxyai-org-key-abc123
OPENAI_BASE_URL=https://openproxai.yourdomain.com/v1

# The OpenAI SDK reads these automatically — zero code changes
```

### Pros & Cons

| Pros | Cons |
|---|---|
| Simplest to implement | Requires developers to update their base URL |
| No network changes | Does not intercept browser-based chat UIs |
| Full TLS with your own cert | Requires onboarding/change management |
| Works for all SDK languages | |

---

## 7. TLS Inspection

To inspect the **content** of HTTPS requests (read prompts, apply DLP, filter PII), your proxy must perform TLS termination. This requires deploying a **root CA certificate** to all client devices.

### Why TLS Inspection Is Needed

Without TLS inspection, you can see:
- Which AI domain was accessed (via SNI)
- How much data was transferred (byte count)
- Timing information

With TLS inspection, you can see:
- The full prompt text
- The model requested
- The response content
- Apply PII detection, DLP, content filtering

### Generating a Root CA

```bash
# Generate root CA private key
openssl genrsa -out openproxyai-root-ca.key 4096

# Generate self-signed root CA certificate (10 year validity)
openssl req -new -x509 -days 3650 \
  -key openproxyai-root-ca.key \
  -out openproxyai-root-ca.crt \
  -subj "/C=CA/O=YourOrg/CN=OpenProxyAI Root CA"

# Generate proxy server key and CSR
openssl genrsa -out openproxyai-proxy.key 2048
openssl req -new \
  -key openproxyai-proxy.key \
  -out openproxyai-proxy.csr \
  -subj "/C=CA/O=YourOrg/CN=openproxai.yourdomain.com"

# Sign the proxy cert with your root CA
openssl x509 -req -days 825 \
  -in openproxyai-proxy.csr \
  -CA openproxyai-root-ca.crt \
  -CAkey openproxyai-root-ca.key \
  -CAcreateserial \
  -out openproxyai-proxy.crt
```

### Deploying the Root CA to Clients

**Windows (Group Policy):**
```
Computer Configuration
  └── Windows Settings
        └── Security Settings
              └── Public Key Policies
                    └── Trusted Root Certification Authorities
                          → Import openproxyai-root-ca.crt
```

**Windows (PowerShell / Intune):**
```powershell
Import-Certificate `
  -FilePath "openproxyai-root-ca.crt" `
  -CertStoreLocation "Cert:\LocalMachine\Root"
```

**macOS (MDM / Jamf):**
```xml
<!-- Configuration Profile payload -->
<dict>
    <key>PayloadType</key>
    <string>com.apple.security.root</string>
    <key>PayloadContent</key>
    <data>
        <!-- Base64-encoded DER certificate -->
    </data>
</dict>
```

**Linux (system-wide):**
```bash
# Ubuntu / Debian
cp openproxyai-root-ca.crt /usr/local/share/ca-certificates/
update-ca-certificates

# RHEL / CentOS / Fedora
cp openproxyai-root-ca.crt /etc/pki/ca-trust/source/anchors/
update-ca-trust extract
```

**Chrome (enterprise policy):**
```json
{
  "CertificateTransparencyEnforcementDisabledForCas": [
    "sha256/BASE64_ENCODED_SPKI_HASH"
  ]
}
```

### Squid TLS Bump Configuration

```
# /etc/squid/squid.conf

# Define AI domains to intercept
acl ai_domains dstdomain .openai.com .anthropic.com .mistral.ai .cohere.ai

# TLS bump (splice = passthrough, bump = intercept)
ssl_bump bump ai_domains
ssl_bump splice all

# Certificate for bumping
https_port 3129 intercept ssl-bump \
  cert=/etc/squid/openproxyai-root-ca.crt \
  key=/etc/squid/openproxyai-root-ca.key \
  generate-host-certificates=on \
  dynamic_cert_mem_cache_size=4MB

# Forward to OpenProxyAI backend
cache_peer openproxyai-backend.internal parent 8000 0 no-query no-digest
never_direct allow ai_domains
```

---

## 8. Browser Extension Development Guide

A complete walkthrough for building a production-ready browser extension that redirects AI traffic.

### Project Structure

```
openproxyai-extension/
├── manifest.json          ← Extension manifest (Chrome MV3)
├── background.js          ← Service worker (request interception)
├── popup.html             ← Extension popup UI
├── popup.js               ← Popup logic
├── content.js             ← Content script (optional, for page injection)
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── rules/
    └── redirect_rules.json  ← Declarative net request rules (MV3)
```

### `manifest.json` (Chrome Manifest V3)

```json
{
  "manifest_version": 3,
  "name": "OpenProxyAI Gateway",
  "version": "1.0.0",
  "description": "Routes AI API calls through your organization's secure gateway",
  "permissions": [
    "declarativeNetRequest",
    "storage",
    "notifications"
  ],
  "host_permissions": [
    "https://*.openai.com/*",
    "https://*.anthropic.com/*",
    "https://*.mistral.ai/*",
    "https://openproxai.yourdomain.com/*"
  ],
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "declarative_net_request": {
    "rule_resources": [{
      "id": "ruleset_1",
      "enabled": true,
      "path": "rules/redirect_rules.json"
    }]
  }
}
```

### `rules/redirect_rules.json` (Declarative Net Request)

```json
[
  {
    "id": 1,
    "priority": 1,
    "action": {
      "type": "redirect",
      "redirect": {
        "transform": {
          "host": "openproxai.yourdomain.com"
        }
      }
    },
    "condition": {
      "requestDomains": ["api.openai.com"],
      "resourceTypes": ["xmlhttprequest", "fetch"]
    }
  },
  {
    "id": 2,
    "priority": 1,
    "action": {
      "type": "redirect",
      "redirect": {
        "transform": {
          "host": "openproxai.yourdomain.com"
        }
      }
    },
    "condition": {
      "requestDomains": ["api.anthropic.com"],
      "resourceTypes": ["xmlhttprequest", "fetch"]
    }
  },
  {
    "id": 3,
    "priority": 1,
    "action": {
      "type": "redirect",
      "redirect": {
        "transform": {
          "host": "openproxai.yourdomain.com"
        }
      }
    },
    "condition": {
      "requestDomains": ["api.mistral.ai"],
      "resourceTypes": ["xmlhttprequest", "fetch"]
    }
  }
]
```

### `background.js` (Service Worker)

```javascript
// background.js — OpenProxyAI Extension Service Worker

const PROXY_HOST = "openproxai.yourdomain.com";
const AI_DOMAINS = [
  "api.openai.com",
  "api.anthropic.com",
  "api.mistral.ai",
  "api.cohere.ai",
  "generativelanguage.googleapis.com"
];

// Track redirect count for the popup badge
let redirectCount = 0;

chrome.declarativeNetRequest.onRuleMatchedDebug?.addListener((info) => {
  redirectCount++;
  chrome.action.setBadgeText({ text: String(redirectCount) });
  chrome.action.setBadgeBackgroundColor({ color: "#10b981" });
});

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_STATS") {
    sendResponse({ redirectCount, proxyHost: PROXY_HOST });
  }
  if (message.type === "RESET_STATS") {
    redirectCount = 0;
    chrome.action.setBadgeText({ text: "" });
    sendResponse({ success: true });
  }
});
```

### `popup.html`

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      width: 280px;
      padding: 16px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0B0C0F;
      color: #e5e7eb;
    }
    .header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
    .status { display: flex; align-items: center; gap: 6px; color: #10b981; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: #10b981; }
    .stat { background: #1a1b1e; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
    .stat-label { font-size: 11px; color: #6b7280; text-transform: uppercase; }
    .stat-value { font-size: 24px; font-weight: 700; color: #10b981; }
    .proxy-url { font-size: 11px; color: #6b7280; word-break: break-all; }
  </style>
</head>
<body>
  <div class="header">
    <strong>OpenProxyAI</strong>
    <div class="status"><div class="dot"></div> Active</div>
  </div>
  <div class="stat">
    <div class="stat-label">Requests Proxied</div>
    <div class="stat-value" id="count">0</div>
  </div>
  <div class="stat">
    <div class="stat-label">Gateway</div>
    <div class="proxy-url" id="proxy-url">Loading...</div>
  </div>
  <script src="popup.js"></script>
</body>
</html>
```

### Building & Packaging

```bash
# Install web-ext for Firefox
npm install -g web-ext

# Build Firefox extension (.xpi)
web-ext build --source-dir ./openproxyai-extension --artifacts-dir ./dist

# Run in Firefox for testing
web-ext run --source-dir ./openproxyai-extension

# For Chrome: Load unpacked in chrome://extensions (Developer Mode)
# For production Chrome: Pack via chrome://extensions → Pack Extension
```

---

## 9. Reference Tools

### Proxy Servers

| Tool | Language | Best For |
|---|---|---|
| **HAProxy** | C | High-performance TCP/HTTP load balancing, SNI routing |
| **Squid** | C | HTTP/HTTPS forward proxy with TLS bump |
| **nginx** | C | Reverse proxy, SSL termination |
| **Traefik** | Go | Cloud-native, Docker/K8s integration |
| **Envoy** | C++ | Service mesh, WASM plugins, CNCF standard |

### LLM-Specific Proxy / Gateway Open Source

| Project | Language | Stars | Notes |
|---|---|---|---|
| **LiteLLM** | Python | 33K+ | Unifies 100+ LLMs, most popular |
| **Portkey Gateway** | TypeScript | 6K+ | Cleanest architecture |
| **Bifrost** | Go | 2K+ | 50x faster than LiteLLM |
| **Helicone** | Rust/TS | 3K+ | "The NGINX of LLMs" |
| **Envoy AI Gateway** | Go/C++ | CNCF | Enterprise-grade |

### Browser Extension Boilerplates

| Repo | Description |
|---|---|
| `PlasmoHQ/plasmo` | Full-stack browser extension framework (React) |
| `fregante/browser-extension-template` | Minimal MV3 template |
| `nicholasgasior/chrome-extension-boilerplate` | Simple redirect extension |

### Network Tools

| Tool | Use Case |
|---|---|
| `mitmproxy` | Intercept and inspect HTTPS traffic during development |
| `Charles Proxy` | macOS GUI proxy for debugging |
| `Wireshark` | Packet capture for network-level debugging |
| `curl --proxy` | Test proxy configuration from CLI |

### Testing Your Setup

```bash
# Test that traffic is going through the proxy
curl -v \
  --proxy http://openproxai.yourdomain.com:8080 \
  https://api.openai.com/v1/models \
  -H "Authorization: Bearer your-org-key"

# Test DNS override
nslookup api.openai.com your-internal-dns-server

# Test PAC file
curl http://internal-pac.yourdomain.com/proxy.pac

# Test TLS certificate
openssl s_client -connect openproxai.yourdomain.com:443 -servername api.openai.com
```

---

## 10. Decision Matrix

Use this to choose the right deployment method for your organization.

| Scenario | Recommended Method | Reason |
|---|---|---|
| Small team, developers only | Reverse Proxy (Method 5) | One-line SDK change, no network work |
| Managed Windows devices | PAC File (Method 2) | GPO deployment, easy to maintain |
| Mixed OS, managed devices | PAC File + Browser Extension | Covers both API and browser traffic |
| Full org rollout, unmanaged devices | DNS Redirection (Method 3) | No endpoint config needed |
| Maximum security, full content inspection | TLS Inspection (Section 7) + DNS | See all prompt content |
| Existing Zscaler/ProxySG deployment | Chained Proxy (Method 4) | Leverage existing infrastructure |
| University / campus network | DNS + Firewall (Methods 3+4) | Central control, no per-device config |
| Zero-trust / cloud-first org | Reverse Proxy + SSO | Integrate with identity provider |

---

## Appendix: AI Domains Reference

Complete list of domains to intercept for major AI providers:

```
# OpenAI
api.openai.com
chat.openai.com
chatgpt.com
*.openai.com

# Anthropic
api.anthropic.com
claude.ai
*.anthropic.com

# Mistral
api.mistral.ai
chat.mistral.ai
*.mistral.ai

# Google (Gemini)
generativelanguage.googleapis.com
aistudio.google.com

# Cohere
api.cohere.ai
dashboard.cohere.ai

# Groq
api.groq.com

# Together AI
api.together.xyz

# Perplexity
api.perplexity.ai
www.perplexity.ai

# Azure OpenAI (org-specific)
*.openai.azure.com
```

---

*Last Updated: February 2026 | OpenProxyAI Documentation*
