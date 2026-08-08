---
title: LangChain
description: Use OpenProxyAI with LangChain via its OpenAI-compatible endpoint — no dedicated package required.
---

# LangChain

There is no separate `langchain-openproxyai` package — because OpenProxyAI is [OpenAI-API-compatible](/integrations/openai-sdk-compatibility), LangChain's existing OpenAI integration works against it directly by overriding the base URL.

## Python

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o",
    base_url="https://api.openproxy.ai/v1",
    api_key=os.environ["OPENPROXY_KEY"],
    default_headers={
        "x-op-team": "eng-platform",
        "x-op-policy": "pii_redact,topic_guard",
    },
)

response = llm.invoke("Summarize this in one sentence.")
```

## What you get, and what you don't

Requests routed this way still go through the full [request pipeline](/core-concepts/request-pipeline) — policy enforcement, caching, budgets, and audit logging all apply exactly as they would for any other client. What you don't get through LangChain's standard `ChatOpenAI` wrapper is the typed `gateway` metadata (cost, latency, policy decision) that the dedicated [Python SDK](/integrations/python-sdk) attaches to every response — that metadata is still present on the raw HTTP response headers, but LangChain's wrapper doesn't surface it by default.

## Same pattern for JS/TS

`@langchain/openai`'s `ChatOpenAI` accepts the same `baseURL` override, with `defaultHeaders` for the OpenProxyAI-specific headers.
