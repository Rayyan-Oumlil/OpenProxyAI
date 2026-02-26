# 10. End-User Integration

This section covers how enterprise IT teams redirect employee AI traffic through the OpenProxyAI gateway. It is the **IT Admin Deployment Guide** — the document a CISO or IT architect reads before rolling out OpenProxyAI across their organization.

## Contents

| Document | Description |
|---|---|
| [01_traffic_redirection_guide.md](./01_traffic_redirection_guide.md) | Complete guide for redirecting AI traffic to the proxy |

## Who Should Read This

- **IT Administrators** rolling out OpenProxyAI across their organization
- **Network Engineers** configuring firewall and DNS rules
- **Security Engineers** implementing TLS inspection
- **DevOps / Platform Engineers** deploying the proxy infrastructure

## Deployment Models at a Glance

| Method | Complexity | Requires Endpoint Config | Transparent to Users |
|---|---|---|---|
| PAC File | Low | Yes (GPO/MDM) | Yes |
| Browser Extension | Low | Yes (user install) | Partial |
| DNS Redirection | Medium | No | Yes |
| Firewall / WCCP | Medium-High | No | Yes |
| Reverse Proxy | Low | Yes (URL change) | No |
| TLS Inspection | High | Yes (root CA) | Yes |
