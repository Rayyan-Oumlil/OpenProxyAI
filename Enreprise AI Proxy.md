# Enterprise AI Gateway

Enterprise AI Gateway / AI Proxy — a centralized security and integration layer providing controlled access to LLMs, MCP services, and enterprise APIs for end users, applications, and AI agents.

The **AI Proxy** becomes the controlled bridge for both:

1.  **Chat traffic**

    - Chat applications

    - Copilots

    - Internal AI assistants

    - Agentic applications

2.  **API calls**

    - OpenAI API

    - Azure OpenAI

    - AWS Bedrock

    - Anthropic

    - Mistral

    - Other LLM providers

**Enterprise AI Access, Security, Routing and Governance Platform** with a conversational interface on top. The critical design principle is that **the user sees one continuous enterprise conversation, while the Gateway may transparently orchestrate multiple LLMs, MCP services and APIs behind the scenes**.

### EIAG - Enterprise AI Gateway

> **Product category:** Enterprise AI Security, Access, Routing, Governance and Orchestration Platform
>
> **Primary objective:**
>
> **Provide a single enterprise-controlled interface between users/applications and Generative AI services, while enforcing identity, authorization, data protection, AI security, model routing, MCP/API security, cost control, compliance, auditability and organizational knowledge governance.**
>
> The architecture should align its AI risk controls with **NIST AI RMF / Generative AI Profile** and current OWASP GenAI security guidance. NIST's GenAI profile specifically addresses the additional risks introduced by generative AI, while OWASP's current project covers LLM and Agentic AI security risks.

## 1. Single Interface for All Generative Artificial Intelligence Systems

The user should never need a direct relationship with an external LLM provider. The Enterprise AI Gateway becomes the enterprise's trusted AI access boundary.

The external AI provider sees the Gateway's controlled service identity and API credentials rather than the employee's personal or provider-specific credentials.

This architecture provides better privacy and security without losing the benefits of conversation history, contextual awareness, and personalized user experiences.

The Enterprise AI Gateway provides a single interface through which users can access approved Generative AI services, while the Gateway transparently manages authentication, authorization, security controls, routing, conversation context, usage, and cost.

### Use-Case Scenario 1: Transparent Enterprise Access to GenAI Services

Any attempt to access an approved external GenAI solution should be transparently redirected to: **openproxyai.examplecompany.com**

The objective is to enforce this redirection without requiring a major redesign of the organization's existing network and security infrastructure, including: Firewalls, Web filtering proxies, SASE solutions, Secure Web Gateways, DNS Security and SD-WAN infrastructure

The redirection can be enforced at the DNS and/or secure web access layer by maintaining a controlled list of domain names associated with approved GenAI solutions. For example:

1.  **Access to** chatgpt.com, claude.ai, perplexity.ai or any other-approved-genai-domain.com

2.  **Will be redirected to the** Enterprise AI Gateway - **openproxyai.examplecompany.com**

3.  Augmented Prompt Redirected to the Public GenAI Provider: ChatGPT, CLAUDE

The GenAI domain list may be maintained through a combination of Enterprise security teams, Enterprise AI Governance, OpenProxyAI research and threat-intelligence capabilities, Approved OEM/vendor domain intelligence, Commercial GenAI domain classification feeds and Internal discovery and monitoring

### Use-Case Scenario 2: Shared GenAI Workspace for Users and Teams (Family Package).

A second use case is to provide users or groups of users with a dedicated Enterprise AI workspace through: **chat.openproxyai.com**

This interface provides a unified user experience for accessing multiple GenAI solutions without requiring users to manage multiple browser sessions, applications, subscriptions, API keys, or separate dashboards.

The platform can support **user-managed or group-managed provider credentials**, subject to the organization's security and acceptable-use policies.

For example, a group of ten users may collectively subscribe to premium AI services such as Claude or ChatGPT and connect the authorized accounts or API credentials to the Enterprise AI Gateway.

The Gateway then provides a unified interface and centralized management layer across those services.

The users can benefit from:

- A single interface

- Shared access to authorized AI services

- Centralized usage dashboards

- Usage visibility by user and by AI provider

- Token and request monitoring

- Cost allocation

- Quotas and rate limiting

- Conversation history

- AI-assisted prompt generation

- Model selection and orchestration

**Group-Based Cost Optimization**

For example, ten family users may share the cost of a premium AI service instead of purchasing ten independent subscriptions.

This allows the organization or user group to understand how the subscription is being consumed and identify opportunities for cost optimization.

The primary value of the shared workspace is not simply the ability to share API keys or subscriptions. The Enterprise AI Gateway can orchestrate multiple AI services behind a single interface.

The user continues to experience this as a single conversation, while the Gateway manages the underlying communication with different AI providers.

The Gateway can therefore optimize the selection of the AI service based on: User preference, Group entitlement, Cost, Performance, Availability, Prompt type, Required capabilities, Data classification, Security risk

This allows the platform to provide AI orchestration, rather than merely AI proxying.

**Security Considerations**

User- or group-supplied provider credentials must never be exposed to other users or stored in plaintext.

Credentials should be stored in an enterprise-grade secrets-management system and protected through: Encryption at rest, Encryption in transit, Access control, Credential isolation, Key rotation, Secret expiration, Audit logging

Where possible, OAuth/OIDC-based delegated authorization should be preferred over users manually entering long-lived API keys.

The Enterprise AI Gateway should also ensure that provider credentials are never exposed to the browser, client-side JavaScript, other users, or unauthorized administrators.

The two scenarios serve different deployment and governance requirements.

| **Capability** | **Scenario 1 – Enterprise Access** | **Scenario 2 – Shared AI Workspace** |
|:---|:---|:---|
| Primary interface | Existing GenAI URL transparently redirected to Enterprise Gateway | chat.openproxyai.com |
| Target users | Enterprise users | Users / teams / groups |
| Identity | Enterprise SSO | Enterprise/Google authentication |
| Provider credentials | Enterprise-managed | User/group-managed or enterprise-managed |
| AI providers | Enterprise-approved | Authorized providers |
| Central security policy | Mandatory | Configurable/mandatory |
| DLP | Enterprise-controlled | Enterprise-controlled where applicable |
| Conversation history | Enterprise-managed | User/group-managed |
| Cost control | Enterprise / department | Group / user / provider |
| LLM orchestration | Yes | Yes |
| Local LLM | Yes | Yes, where authorized |
| MCP | Yes | Yes, where authorized |
| API integration | Yes | Yes, where authorized |
| Deployment | DMZ/Core/Private | Cloud/Core/Private |
| Primary objective | Enterprise governance and security | Unified AI experience and cost optimization |

The **chat.openproxyai.com (Use Case 2)** platform can be used as a demonstration and reference implementation of the Enterprise AI Gateway solution. It can be adapted to support multiple deployment and use-case models, including:

- **Enterprise Package:** An enterprise-grade solution for organizations to securely govern, monitor, and control the use of Generative AI services.

- **SASE Integration:** Integration with SASE solutions to provide centralized AI traffic steering, security enforcement, and policy control.

- **Family Package:** A solution for families to govern and monitor the use of Generative AI services by family members.

- **Classroom / School Package:** A solution for schools and educational institutions to control, monitor, and govern the use of AI by students, teachers, and staff.

The same core platform can therefore support different levels of identity management, policy enforcement, monitoring, content protection, and AI governance depending on the target environment.

The **demo.openproxyai.com** can expose typical dashboard that will be provided for Enterprise company for better AI usage visibility.

**Chat interface**

The user interface should support:

**Input**

- Text

- Images

- PDF

- Word

- Excel

- PowerPoint

- Voice

- Video

- URLs where approved

**Output**

- Text

- Tables

- Images

- Charts

- Documents

- Code

- Structured results

- AI-generated artifacts

## 2. Per-Turn Dynamic Model Routing & Context Orchestration

### 2.1 Purpose and Core Principle

The **Enterprise AI Gateway shall support Per-Turn Dynamic Model Routing**, enabling a single end-user conversation to be dynamically processed by multiple authorized Large Language Models (LLMs), AI services, local models, MCP services, enterprise AI capabilities, or combinations thereof.

The end user shall experience the interaction as **one continuous conversation** and shall not be required to initiate separate conversations with different AI providers.

The Enterprise AI Gateway shall maintain ownership of the conversation state. Individual models and AI services shall be treated as **execution engines**, rather than owners of the conversation.

The Gateway may disclose the model or AI service selected for a given request where required by the organization's transparency, regulatory, audit, or Responsible AI policies.

### 2.2 Key Mandatory Controls

#### 2.2.1 Canonical Conversation State

Enterprise AI Gateway shall maintain a **provider-independent Canonical Conversation State** that is not dependent on the native conversation state of any individual LLM provider.

Where authorized, the Canonical Conversation State may include:

- Conversation ID

- User identity

- Session information

- Conversation topic

- Tags and hashtags

- Relevant conversation history

- User preferences

- Approved memories

- Active persona

- System instructions

- Enterprise policies

- Security classification

- Data classification

- Previous model responses

- Attachments

- Tool results

- MCP results

- User feedback

- Model selection history

- Routing decisions

- Relevant security decisions

The Gateway shall determine which elements of the Canonical Conversation State are required for each individual model or AI-service invocation.

**Verify that:**

1.  A conversation can continue when the backend model changes between turns.

2.  Conversation continuity does not depend on a provider-specific conversation ID.

3.  Provider-specific conversation history can be disabled without losing the enterprise conversation.

4.  The Gateway can reconstruct the required context for a new model.

5.  The Gateway maintains an auditable record of which context elements were supplied to each backend invocation.

#### 2.2.2 Minimum Necessary Context and Data Protection

The Gateway **shall not blindly transmit the complete conversation history to every model**.

For each invocation, the Gateway shall construct a **Context Package** containing only the information that is:

- relevant to the current request;

- authorized for the requesting user;

- authorized for the selected model or provider;

- compatible with the applicable data classification;

- permitted by enterprise security and privacy policies; and

- necessary for completing the requested task.

Confidential, restricted, regulated, or otherwise sensitive information shall not be transmitted to an external LLM provider unless explicitly permitted by enterprise policy.

Context selection shall therefore follow the principle of **minimum necessary disclosure**.

**User Request → Canonical Conversation State → Authorization & Policy Evaluation → Context Selection → Model/Capability Routing → Provider-Specific Context Package → AI Invocation**

**Test whether:**

- Restricted information is removed when routing to an unauthorized provider.

- Irrelevant previous conversation content is excluded.

- Attachments are subject to the same policy controls as prompts.

- MCP and tool outputs are security-classified before reuse.

- Switching from an internal to an external model triggers a new context-authorization decision.

#### 2.2.3 Per-Turn Dynamic Model Routing

The Gateway shall dynamically determine the appropriate authorized AI capability for **each user turn**.

Model selection shall not be permanently bound to a particular user, department, application, or conversation.

Routing decisions should consider relevant attributes including:

**Identity**

- User identity

- Role

- Group membership

- Authorization

- Entitlements

**Content**

- Prompt intent

- Data classification

- Security classification

- Required capability

- Required tools

- Sensitivity of attachments

**Conversation**

- Current topic

- Relevant previous turns

- Active persona

- Approved memory

- Current task state

**Operational Requirements**

- Model availability

- Performance

- Latency requirements

- Cost

- Capacity

- Provider availability

- Enterprise policy

- Security risk

The routing engine shall only select models and services that are **authorized for the applicable user, use case, and data classification**.

#### 2.2.4 Single Conversation, Multiple Backend Invocations

A single enterprise conversation may use different processing engines for different turns.

The Enterprise AI Gateway shall maintain a **canonical conversation state** independently of any individual LLM provider.

The conversation should therefore not be considered a conversation owned by ChatGPT, Claude, DeepSeek, or another provider.

The conversation belongs to the Enterprise AI Gateway, while individual LLMs are execution engines used to process individual turns or subtasks.

Example:

> Enterprise Conversation \#10245
>
> Turn 1 → Claude
>
> Turn 2 → ChatGPT
>
> Turn 3 → DeepSeek
>
> Turn 4 → Internal LLM
>
> Turn 5 → Claude
>
> Turn 6 → Internal LLM + MCP

The Gateway maintains the continuity of the conversation across these different executions.

### 3. Context Orchestration

#### 3.3.1 Context Selection Engine

For every new user request, the Gateway shall evaluate the Canonical Conversation State and determine which context elements are required for the next processing step.

The Context Selection Engine should evaluate:

1.  Current user request

2.  Conversation intent

3.  Relevant previous turns

4.  Conversation topic and tags

5.  User preferences

6.  Approved memories

7.  Active persona

8.  Attachments

9.  Previous AI responses

10. Tool and MCP results

11. Security classification

12. Data classification

13. User authorization

14. Provider authorization

15. Applicable enterprise policies

The resulting context shall be assembled into a **provider-specific Context Package**.

#### 3.2 Context Isolation

Context supplied to one model shall not automatically become available to another model.

A new authorization and context-selection decision shall occur whenever the Gateway changes:

- model;

- provider;

- AI service;

- tool;

- MCP service; or

- data-processing boundary.

This is particularly important when transitioning between:

> **Internal AI → External AI**
>
> or
>
> **Approved Provider A → Provider B with different data-processing conditions**

### 4. Capability-Based Model Routing

The Gateway shall provide an abstraction layer between enterprise applications and individual AI providers.

Enterprise applications should request the **required capability**, rather than directly hard-code a specific model wherever practical.

The Gateway may map an abstract capability to one or more currently authorized models.

This abstraction enables the organization to replace, add, suspend, or upgrade models without requiring redesign of consuming applications.

Examples of abstract capabilities include:

> GENERAL_REASONING
>
> SUMMARIZATION
>
> CODE_GENERATION
>
> DEEP_RESEARCH
>
> DOCUMENT_ANALYSIS
>
> CREATIVE_WRITING
>
> ENTERPRISE_SEARCH
>
> CONFIDENTIAL_REASONING
>
> MULTIMODAL_ANALYSIS

### 5. Multi-Model Task and Prompt Orchestration

The Gateway should support orchestration beyond the simple **one request → one model** pattern.

A single user request may be decomposed into multiple authorized subtasks and processed by different AI services: Research LLM1, Reasoning LLM2 AND Enterprise Data LLM3.

Each subtask shall independently inherit the applicable:

- identity controls;

- authorization controls;

- data-classification controls;

- security policies;

- context restrictions;

- model/provider restrictions; and

- audit requirements.

The orchestrator shall not use task decomposition as a mechanism to bypass security controls.

### 6. Dynamic Model Parameters

Each model invocation may require a different provider-specific configuration.

Example:

| **Turn** | **Purpose** | **Selected Capability** | **Creativity** |
|:---|:---|:---|:---|
| 1 | Creative brainstorming | Creative model | High |
| 2 | Technical analysis | Reasoning model | Low |
| 3 | Confidential enterprise analysis | Internal model | Low |

The Gateway shall abstract commonly required behavioral parameters at the enterprise level.

The Gateway shall translate the enterprise-level behavior policy into provider-specific settings where supported.

Applications shall not assume that parameters such as **temperature have identical semantics across providers**.

### 7. Dynamic Creativity and Behavior Policy

The Gateway should support a broader **Behavior Policy** rather than relying exclusively on raw model parameters.

The enterprise abstraction may include:

- Creativity

- Determinism

- Reasoning depth

- Response length

- Citation requirement

- Tool access

- Structured-output requirement

- Response format

- Safety controls

The mapping between the enterprise behavior policy and provider-specific parameters shall be centrally governed and auditable.

### 8. Dynamic Persona Management

The Gateway shall maintain a **Conversation Persona State** separately from individual LLM providers.

Persona information shall be reconstructed into the appropriate system instructions or configuration for each model invocation.

Persona state should be **session-aware and context-aware**, rather than being permanently attached to the user.

A persona shall never supersede:

- security policy;

- user authorization;

- data classification;

- Responsible AI requirements;

- provider restrictions; or

- tool authorization.

### 9. Topic, Tag and Hashtag Architecture

The Gateway should support topic classification to improve context selection, memory management, search, routing, and conversation organization.

Classification may be:

- User-defined

- Automatically generated

> The Gateway may automatically identify relevant topics or tags based on the conversation.
>
> Tags should be treated as **metadata and routing/context signals**, not as security authorization.
>
> should not by itself authorize or de-authorize data processing. Security decisions must originate from authoritative enterprise policy and classification mechanisms.

### 10. Non-Purely Deterministic Model Routing

Model routing should not rely exclusively on static rules=.

The routing architecture should support a combination of:

- policy-based routing;

- capability-based routing;

- context-aware routing;

- data-classification routing;

- risk-based routing;

- performance-aware routing;

- availability-aware routing;

- cost-aware routing; and

- adaptive routing.

However, **security and compliance boundaries shall remain deterministic and enforceable**.

### 11. Model Failover and Resilience

The Gateway shall support controlled failover when the preferred model or AI service is unavailable, degraded, rate-limited, or otherwise unsuitable.

Failover shall only occur to an **authorized alternative**.

The alternative model must satisfy applicable requirements for:

- security;

- data classification;

- provider authorization;

- required capabilities;

- geographic or processing restrictions;

- tool access; and

- enterprise policy.

The Gateway shall not lower security restrictions simply to preserve availability.

### 12. Model Performance Monitoring

The Gateway should centrally monitor AI-service performance to support model selection, service management, optimization, and governance.

Monitoring should cover relevant dimensions such as:

- availability;

- latency;

- error rates;

- invocation failures;

- rate-limit events;

- token/resource consumption;

- cost;

- failover events;

- tool execution;

- policy violations; and

- user feedback.

Performance information used by the routing engine should itself be auditable.

### 13. Model Auditability

Every model invocation shall generate sufficient audit information to reconstruct the material processing decision, subject to applicable privacy and retention requirements.

Audit records should capture, where appropriate:

| **Audit Element**   | **Requirement**                              |
|:--------------------|:---------------------------------------------|
| Conversation ID     | Identify the canonical conversation          |
| Turn/Request ID     | Identify individual requests                 |
| User identity       | Identify requesting principal                |
| Timestamp           | Record processing event                      |
| Selected provider   | Record selected AI provider/service          |
| Selected model      | Record model/version where available         |
| Routing reason      | Explain why the backend was selected         |
| Data classification | Record applicable classification             |
| Context decision    | Record what context categories were approved |
| Persona             | Record active persona/policy                 |
| Behavior policy     | LOW/MEDIUM/HIGH or equivalent                |
| Tools/MCP           | Record services invoked                      |
| Failover            | Record failover event and reason             |
| Policy decision     | Record applicable security decision          |
| Output status       | Success, blocked, failed, filtered, etc.     |

## 2. Enterprise Memory, Knowledge Governance & Model Output Trust

## Enterprise Memory

### 3.1 Multi Levels Memory

**A. Session memory**

Only valid for the current conversation.

**B. User memory**

Preferences explicitly or implicitly approved by the user.

**C. Team knowledge**

Approved information shared with a team.

**D. Enterprise knowledge**

Approved organizational knowledge.

**E. Enterprise facts**

Validated structured facts.

**F. RAG knowledge**

Documents and indexed knowledge.

This distinction is essential.

**Chat history must never automatically become enterprise truth.**

### 3.2. Feedback-to-knowledge pipeline

The system should not immediately convert this into enterprise knowledge.

This is necessary to avoid knowledge poisoning. Data/model poisoning is explicitly recognized as an LLM security risk by OWASP

Conversation usage on Local LLM training (1) or on RAG and Facts Databases data requires:

 approval

 sanitization

 PII removal

 classification

 quality control

 licensing validation

 poisoning detection

**Memory Governance**

Because the Gateway maintains **Approved Memories**, memory requires its own governance controls.

The architecture should differentiate:

Conversation History

≠

Session Context

≠

User Preference

≠

Approved Long-Term Memory

≠

Enterprise Record

Memory storage and retrieval should be subject to explicit authorization, retention, classification, deletion, and audit policies.

## 3. Identity & Authorization Management

### 4.1 Identity and SSO

> The Gateway should integrate with enterprise identity using standard protocols.
>
> Recommended:

- OpenID Connect

- OAuth 2.x

- SAML where required

- SCIM for provisioning

- MFA inherited from enterprise IdP

- AD/Entra ID groups

- device identity where available

### 4.2 Authorization model

> I recommend combining:
>
> **RBAC**
>
> Who is the user?
>
> **ABAC**
>
> What are the attributes?
>
> **PBAC**
>
> What policy applies?
>
> **Risk-based authorization**
>
> What is happening **right now**?

### 4.3 Real-time authorization

**Dynamic Context-Aware Authorization**.

Example 1:

DevOp

> DevOps
>
> ├── ChatGPT → ALLOW
>
> ├── Claude → ALLOW
>
> ├── Internal LLM → ALLOW
>
> └── MCP → Conditional

But then the **content changes the decision**.

DevOps user

> "Explain Kubernetes deployment."
>
> → Low risk → inexpensive model

"Analyze this confidential production configuration."

→ Confidential → external model prohibited → Internal LLM

### Agent identity

## 4. Security

**DLP integration**

The Gateway should integrate with the enterprise DLP platform rather than attempt to replace it.

**PII anonymization**

**Threat detection**

The Gateway should detect at minimum:

- Prompt injection

- Indirect prompt injection

- Sensitive information disclosure

- Malicious files

- Data exfiltration

- Jailbreak attempts

- Credential leakage

- Malicious URLs

- Tool abuse

- Excessive agency

- Model manipulation

- MCP tool poisoning

- Rogue MCP servers

- Supply-chain risks

- Abnormal usage

- Account takeover

- Automated abuse

**Threat detection**

The Gateway should detect at minimum:

- Prompt injection

- Indirect prompt injection

- Sensitive information disclosure

- Malicious files

- Data exfiltration

- Jailbreak attempts

- Credential leakage

- Malicious URLs

- Tool abuse

- Excessive agency

- Model manipulation

- MCP tool poisoning

- Rogue MCP servers

- Supply-chain risks

- Abnormal usage

- Account takeover

- Automated abuse

**MCP Security Gateway**

The Gateway should implement current MCP authorization/security requirements where applicable, including OAuth-based authorization for HTTP transports and resource/audience binding.

**Never simply pass through an MCP bearer token.**

The current MCP authorization specification explicitly addresses token audience binding and states that token passthrough is forbidden.

**Rate limiting**

Rate limits should exist at multiple levels:

**SOC integration**

The Gateway should integrate with the existing enterprise SOC/SIEM.

Generate security events such as:

- AI-PROMPT-INJECTION-DETECTED

- AI-DLP-BLOCK

- AI-SECRET-EXFILTRATION

- AI-UNAUTHORIZED-MODEL

- AI-UNAUTHORIZED-MCP

- AI-TOOL-ABUSE

- AI-EXCESSIVE-AGENCY

- AI-ANOMALOUS-USAGE

- AI-COST-THRESHOLD

- AI-DATA-CLASSIFICATION-VIOLATION

These should be available through standard interfaces such as:

- Syslog

- CEF

- JSON

- REST API

- Webhooks

- OpenTelemetry

The product should avoid creating a proprietary telemetry island.

**AI Security Posture & Risk Management (AISPRM)**

Risk score calculation.

The actual scoring model should be configurable by the GRC/security team.

NIST AI RMF provides an appropriate governance foundation for this risk-management layer

**Policy decision engine**

The heart of the system should be a **policy decision point**, not hard-coded application logic.

Policies should ideally be expressed using open policy mechanisms rather than proprietary rules.

**Privacy architecture**

The Gateway must know what the user sent, but external LLMs should only receive what policy permits.

**Parallel security processing**

Use parallel processing wherever the decision dependencies allow it.

**Performance architecture**

Security checks should be divided into:

**Synchronous**

Required before sending request:

- Authentication

- Authorization

- DLP

- Data classification

- Risk

- Model policy

- Prompt injection

- Routing

**Asynchronous**

Can happen after/alongside the transaction:

- Advanced analytics

- Cost aggregation

- Usage reporting

- Knowledge extraction

- Long-term classification

- ML model improvement

- SOC enrichment

This prevents the security architecture from becoming the performance bottleneck.

**Policy Enforcement Before Routing and Invocation**

I recommend separating **routing** from **authorization**.

User Request

Identity + Authorization

Data / Security Classification

Policy Enforcement

Context Selection

Capability Identification

Candidate Model Selection

Risk / Performance / Cost Optimization

Authorized Model Invocation

The single chat with an enduser can be mapped to multiples chats with differnets models.

The user experiences this as **one conversation**. However, in the backend the context all chat history, persona and preference switch between multiples Models.

The webinterface will map each end user request to a specific API calls to one of the authorized LLMs.

This will allow maximum flexibility, therefore one chat from End user will be mapped to multiple communication in the backend, prompt 1 will go to Claude, Prompt 2 to ChatGPT, prompt 3 to DeepSeak, Prompt 4 to Internal LLM.

Each API can have completely different setting : Temperature, System Message, randomness. Therfore, the first prompt can be sith temperature 1.5 to be more creative if the questions is generale, then the subsequent questions can be with temperature 0 if the question is specific.

### 2. The Gateway should be more than an LLM proxy

The product therefore contains:

1.  **Enterprise AI Chat Gateway**

2.  **LLM/API Gateway**

3.  **MCP Gateway**

4.  **AI Security Gateway**

5.  **AI Governance & Risk Engine**

All five share the same **identity, policy, catalog, audit and risk-control plane**.

Define RBAC to AI Applications.

Central Management, Deployment, Enforcement and Monitoring of AI Usage by Human and by Agent AI.

### Deployment Scenarios:

The Enterprise AI Gateway can be implemented as a highly scalable, containerized solution.

The web-interface and gateway components may be deployed as Docker containers and managed through Kubernetes or an equivalent container orchestration platform. The Docker instances to be hosted behind NGINX or any other commercial load balancer and secured by Enterprise WAF Web Application Firewalls.

The architecture should support both horizontal and vertical scalability, including: Horizontal scaling by adding gateway instances, Vertical scaling of individual instances, Load balancing, High availability, Automatic health checking, Automatic failover, Kubernetes-based orchestration, Container lifecycle management, Rolling upgrades and Zero- or minimal-downtime maintenance

The solution should support two deployment models (Geo-Location).

> **Centralized model:** All branches and locations forward GenAI traffic to a centrally hosted Enterprise AI Gateway. This model provides centralized governance, policy enforcement, monitoring, logging, and cost management.
>
> **Distributed model -** Each major branch or geographical location can have a local Enterprise AI Gateway instance. The distributed model should be aligned with the organization's SD-WAN architecture, allowing traffic to be dynamically directed to the nearest or most appropriate AI Gateway instance.
>
> Both models should use the same centralized policy, service catalogue, security and governance framework.

Deployment Scenarios Based on functions are:

> **EAIG-EXT — External/DMZ Gateway:**
>
> Handles:

- Public GenAI

- External LLM APIs

- Approved external MCP

- Public-facing AI applications

- External integrations

- Internet-facing AI services

This is forward proxy deployed in the DMZ LAN networks, same location as traditional Web Filtering Policy. The appliance should be the nearest possible to the Internet proxies.

This scenario should support both explicit and transparent redirection.

**EAIG-INT-API — Internal API Gateway**

These appliances are installed in internal Networks with or without any exposure to Internet Services.

These appliances will expose all Local LLMs, Local MCP Services and all Enterprise APIs.

**EAIG-INT-Data — Internal API Gateway**

These appliances are installed in internal Networks with or without any exposure to Internet Services.

These appliances will expose all Local Data based on MCP Services

**Central AI Control Plane -** All instances should use common Central AI control Plane. This prevents policy divergence between all instances.

Central Visisbility, Security and Monitoring Plane.

Typical Infrastructure Scenarios include the deployment of the following Modules:

- Two Central Proxy on HQ DMZ Networks

- Two Local Proxies on Each Branch Networks.

- Two Internal Frontend Proxy for Internal AI Endpoints and MCP Services

- Two Internal backend proxy for exposure of Internal Dat Services.

**API and protocol support**

The product should be protocol-neutral.

**Northbound**

- HTTPS

- REST

- WebSocket

- Server-Sent Events

- OpenAI-compatible APIs

- MCP

- OAuth/OIDC

**Southbound**

- OpenAI-compatible API

- Provider-specific APIs

- REST

- GraphQL

- MCP

- WebSocket/SSE where applicable

**Enterprise integration**

- LDAP/AD

- Entra ID/SSO

- SIEM

- DLP

- GRC

- CMDB

- ITSM

- API Gateway

- EDR

- CASB/SASE

**No vendor lock-in**

### AI Service Catalog

> The catalog is effectively the **enterprise AI marketplace**.
>
> **GenAI Chat**
>
> Examples:

- ChatGPT

- Claude

- Perplexity

- Other approved services

> The catalog should expose:

- Service name

- Provider

- Model

- Version

- Business owner

- Technical owner

- Approved departments

- Data classification allowed

- Geography

- Regulatory restrictions

- Cost

- Availability

- Risk rating

- Approved use cases

- Prohibited use cases

- Retention policy

- Whether training on submitted data is permitted

- Whether files are permitted

- Whether MCP is supported

> **LLM Registry**
>
> Every model should have a formal record.
>
> The model registry becomes the source used by the routing engine.
>
> **MCP Registry**
>
> MCP should be treated as a first-class enterprise service. The Gateway should not simply forward MCP requests.
>
> Who is invoking the tool, which agent is invoking it, what tool is being invoked, what data is being accessed, what action is being performed and whether that action is authorized.
>
> This is particularly important because MCP tools can expose data and execute actions. The MCP specification itself emphasizes user consent, authorization and protection of data/tool operations
>
> **API Registry**
>
> Every API should have:

- API owner

- Business owner

- Authentication method

- Authorization model

- Data classification

- Allowed agents

- Allowed users

- Allowed operations

- Read/write/delete permissions

- Rate limit

- Risk level

- Audit requirement

**14.1 Provider and Model Registry**

Maintain a centrally governed registry containing approved:

- providers;

- models;

- model versions;

- AI services;

- deployment locations;

- data classifications permitted;

- use cases permitted;

- tools permitted;

- MCP services permitted;

- capabilities;

- availability status; and

- applicable policies.

The routing engine shall select only capabilities registered and authorized in this registry.

5.  **Agentic AI applications**

This means your applications don't need to be individually integrated with every LLM provider.

**AI Gateway/Proxy** controls **LLM communication** - **Agent → AI Gateway → LLM**

**MCP Gateway** controls **agent → tool/resource communication**.- **Agent → MCP Gateway → Enterprise Tools/APIs**

**AI Gateway = "Who can talk to which LLM, under what policy?"**

**MCP/API Gateway = "What can an AI agent do inside the enterprise?"**

**Chat collaboration**

> Your collaboration concept should distinguish:
>
> **Private conversation**
>
> Only user can see it.
>
> **Shared conversation**
>
> User explicitly shares it.
>
> **Team knowledge**
>
> A selected artifact/fact is published to the team.
>
> **Enterprise knowledge**
>
> An approved knowledge artifact becomes enterprise-wide.

**End-user education**

> The portal should dynamically educate users.
>
> For example:
>
> ⚠️ This document is classified as CONFIDENTIAL. It cannot be submitted to the selected external AI service.
>
> Or:
>
> ℹ️ This request was automatically routed to the Internal Enterprise LLM because it contains confidential information.
>
> Or:
>
> 🔒 Claude is not currently authorized for your department.
>
> This turns security controls into **user education rather than silent blocking**.

**Cost management**

**Observability**

The Gateway should produce a unified AI telemetry model.

Metrics:

- Response time

- Time to first token

- Token usage

- Model usage

- Cost

- Error rate

- Policy blocks

- DLP blocks

- Prompt injection attempts

- MCP calls

- API calls

- User satisfaction

- Model quality

| **Function** | **Purpose** |
|--------------|-------------|

| **LLM routing** | Decide which model/provider receives the request |
|-----------------|--------------------------------------------------|

| **Authentication** | Centralize API keys/OAuth/service identities |
|--------------------|----------------------------------------------|

| **Authorization** | Control which users/apps can access which models |
|-------------------|--------------------------------------------------|

| **Rate limiting** | Prevent abuse and runaway consumption |
|-------------------|---------------------------------------|

| **Quota management** | Control usage by department/application/user |
|----------------------|----------------------------------------------|

| **Logging** | Record API calls, model, latency, tokens, errors |
|-------------|--------------------------------------------------|

| **Cost tracking** | Attribute LLM consumption to applications/users |
|-------------------|-------------------------------------------------|

| **DLP/PII detection** | Detect sensitive information before sending to LLM |
|-----------------------|----------------------------------------------------|

| **Prompt-injection protection** | Detect malicious instructions |
|---------------------------------|-------------------------------|

| **Content filtering** | Apply enterprise safety policies |
|-----------------------|----------------------------------|

| **Model fallback** | Switch provider/model when one is unavailable |
|--------------------|-----------------------------------------------|

| **Caching** | Reduce repeated LLM calls and cost |
|-------------|------------------------------------|

| **Observability** | Monitor latency, failures, token usage and model performance |
|----|----|

**Three types of traffic**

| **Source** | **Protocol / Interface** | **AI Gateway handles** |
|----|----|----|
| **End users** | Browser / HTTPS | Chat → LLM |
| **AI Agents** | MCP | Tools, resources, enterprise actions |
| **Agentic applications** | REST / GraphQL APIs | Enterprise services + LLM APIs |
| **Applications** | LLM APIs | Model inference |
| **Agents** | MCP + APIs | LLM + tools + enterprise data |

**AI Gateway administration console**

The administrator portal should contain:

Dashboard

AI Services

> ├── GenAI Chat
>
> ├── LLMs
>
> ├── MCP Servers
>
> ├── MCP Tools
>
> ├── APIs
>
> └── Local AI

Identity & Access

> ├── Users
>
> ├── Groups
>
> ├── Roles
>
> └── Entitlements

Policies

> ├── Model Policy
>
> ├── DLP Policy
>
> ├── MCP Policy
>
> ├── API Policy
>
> ├── Cost Policy
>
> └── Risk Policy

Security

├── Threats

├── DLP

├── Prompt Injection

└── Anomalies

Knowledge

> ├── RAG
>
> ├── Facts
>
> ├── Memories
>
> └── Training Candidates

Operations

> ├── Usage
>
> ├── Cost
>
> ├── Performance
>
> └── Availability

Audit

> ├── User Activity
>
> ├── AI Requests
>
> ├── MCP Calls
>
> ├── Policy Decisions
>
> └── Administrative Actions.

**Caching and hashes**

But cryptographic hashes should be used for **identity/integrity**, not as a replacement for semantic retrieval.

**Product differentiation**

**1. Multi-LLM abstraction**

One interface, many models.

**2. Dynamic model routing**

Different prompts in the same conversation can use different models.

**3. AI-aware authorization**

Authorization changes according to user + content + risk.

**4. Unified MCP/API/LLM security**

One policy framework for:

LLM

MCP

API

Agent

User

**5. Enterprise AI Service Catalog**

One approved catalog for all AI capabilities.

**6. Internal + external AI**

Public and private models under one governance model.

**7. Enterprise AI memory**

Controlled personal/team/enterprise knowledge.

**8. AI risk engine**

CASB-like visibility and control for AI.

**9. AI security gateway**

DLP + PII + threat detection + prompt injection + audit.

**10. Vendor independence**

No dependence on one LLM provider.

Identity + Service Discovery + Authorization + Risk Assessment + DLP + Security Inspection + Model Routing + MCP Governance + API Governance + Conversation Management + Knowledge Management + Cost Management + Audit.

Central governance.

AI Service Catalog │ │ Policies │ │ Approved Models │ │ Approved MCP │ │ RBAC │ │ Security Policies │ │ Audit / Reporting

Enterprise AI Access, Security, Routing and Governance Platform

**Proposed product logical modules**

| **\#** | **Module** | **Primary responsibility** |
|----|----|----|
| 1 | **AI Web Portal** | Enterprise ChatGPT-like user experience |
| 2 | **Identity & Access** | SSO, RBAC, ABAC, entitlements |
| 3 | **AI Service Catalog** | Approved GenAI, LLM, MCP, API and local AI registry |
| 4 | **AI Policy Engine** | Central policy decision and enforcement |
| 5 | **LLM Gateway & Router** | Multi-provider abstraction and dynamic routing |
| 6 | **MCP Gateway** | MCP discovery, authorization, security and auditing |
| 7 | **Enterprise API Gateway** | Agent/application API access |
| 8 | **AI Security Engine** | DLP, PII, prompt injection, threat detection |
| 9 | **AI Risk & Compliance Engine** | Risk scoring, geography, regulations, GRC integration |
| 10 | **Conversation & Memory Engine** | Context, tags, history, personalization |
| 11 | **Knowledge & RAG Engine** | Enterprise facts, RAG, approved organizational knowledge |
| 12 | **AI Operations & Governance** | Cost, quota, monitoring, audit, SOC, reporting |
