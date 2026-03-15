from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .common import GatewayMeta

@dataclass
class Message:
    role: str
    content: str | list[Any]

@dataclass
class Delta:
    role: str | None = None
    content: str | None = None

@dataclass
class Choice:
    index: int
    message: Message | None = None
    delta: Delta | None = None
    finish_reason: str | None = None

@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

@dataclass
class ChatCompletion:
    id: str
    object: str
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    gateway: GatewayMeta = field(default_factory=GatewayMeta)

@dataclass
class ChatCompletionChunk:
    id: str
    object: str
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    gateway: GatewayMeta = field(default_factory=GatewayMeta)
