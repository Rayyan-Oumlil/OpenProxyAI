"""A read-only query over an org's own logs and scores, built from a structured spec instead of SQL text (Phase 5, slice 5.9).

Why not accept SQL: the only way to make arbitrary SQL safe against a shared database is a parser you trust completely, and a mistake in
one exposes other tenants. A structured spec has no such surface. Everything the caller can choose is looked up in an allowlist here
(views, columns, operators, aggregates), every value is a bound parameter, and nothing the caller sends ever becomes SQL text.

What it cannot do, on purpose: joins, subqueries, functions beyond the listed aggregates, anything that writes, and any column that
holds free text a user typed (error messages, request metadata, comments). Those stay in the request log and scores views that already
have their own access rules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, field_validator, model_validator
from sqlalchemy import Select, and_, func, select
from sqlalchemy.sql.elements import ColumnElement

from app.models.request_log import RequestLog
from app.models.request_score import RequestScore

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365
MAX_LIMIT = 1_000
MAX_SELECT = 12
MAX_WHERE = 12
MAX_IN_VALUES = 50

Kind = Literal["text", "int", "number", "time", "uuid"]


@dataclass(frozen=True)
class View:
    name: str
    table: Any
    columns: dict[str, tuple[Any, Kind]]  # name -> (SQLAlchemy column or expression, kind)
    time_column: str


def _day(column):
    return func.date_trunc("day", column)


REQUESTS = View(
    "requests",
    RequestLog,
    {
        "created_at": (RequestLog.created_at, "time"), "day": (_day(RequestLog.created_at), "time"),
        "model": (RequestLog.model, "text"), "provider": (RequestLog.provider, "text"), "status_code": (RequestLog.status_code, "int"),
        "prompt_tokens": (RequestLog.prompt_tokens, "int"), "completion_tokens": (RequestLog.completion_tokens, "int"),
        "total_tokens": (RequestLog.total_tokens, "int"), "cost_usd": (RequestLog.cost_usd, "number"),
        "latency_ms": (RequestLog.latency_ms, "int"), "ttft_ms": (RequestLog.ttft_ms, "int"),
        "user_id": (RequestLog.user_id, "uuid"), "api_key_id": (RequestLog.api_key_id, "uuid"),
        "data_class": (RequestLog.request_metadata["data_class"]["class"].astext, "text"),
        "source": (RequestLog.request_metadata["source"].astext, "text"),
    },
    "created_at",
)
SCORES = View(
    "scores",
    RequestScore,
    {
        "created_at": (RequestScore.created_at, "time"), "day": (_day(RequestScore.created_at), "time"),
        "score_name": (RequestScore.score_name, "text"), "value": (RequestScore.value, "number"), "source": (RequestScore.source, "text"),
        "experiment_id": (RequestScore.experiment_id, "uuid"), "variant_id": (RequestScore.variant_id, "uuid"),
    },
    "created_at",
)
VIEWS = {v.name: v for v in (REQUESTS, SCORES)}

AGGREGATES = ("count", "sum", "avg", "min", "max", "p50", "p95")
NUMERIC_KINDS = ("int", "number")
OPERATORS = {"=": "eq", "!=": "ne", ">": "gt", ">=": "ge", "<": "lt", "<=": "le", "in": "in"}
ORDERED_KINDS = ("int", "number", "time")


class Aggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agg: Literal["count", "sum", "avg", "min", "max", "p50", "p95"]
    column: str | None = None
    as_: str | None = Field(default=None, alias="as", pattern=r"^[a-z][a-z0-9_]{0,40}$")


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    op: Literal["=", "!=", ">", ">=", "<", "<=", "in"]
    # Strict, so a JSON true is not quietly read as 1 and a number is not quietly read as text.
    value: StrictStr | StrictInt | StrictFloat | list[StrictStr | StrictInt | StrictFloat]


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str  # a selected column, or an aggregate's alias
    dir: Literal["asc", "desc"] = "asc"


class QuerySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: Literal["requests", "scores"]
    select: list[Annotated[str, Field(max_length=60)] | Aggregate] = Field(min_length=1, max_length=MAX_SELECT)
    where: list[Condition] = Field(default_factory=list, max_length=MAX_WHERE)
    group_by: list[str] = Field(default_factory=list, max_length=MAX_SELECT)
    order_by: list[Order] = Field(default_factory=list, max_length=4)
    limit: int = Field(default=100, ge=1, le=MAX_LIMIT)
    since: datetime | None = None
    until: datetime | None = None

    @field_validator("since", "until")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC).replace(tzinfo=None) if value is not None and value.tzinfo else value

    @model_validator(mode="after")
    def _window(self) -> "QuerySpec":
        start, end = self.bounds()
        if start >= end:
            raise ValueError("since must be before until")
        if end - start > timedelta(days=MAX_WINDOW_DAYS):
            raise ValueError(f"the window can be at most {MAX_WINDOW_DAYS} days")
        return self

    def bounds(self) -> tuple[datetime, datetime]:
        end = self.until or datetime.now(UTC).replace(tzinfo=None)
        return (self.since or end - timedelta(days=DEFAULT_WINDOW_DAYS)), end


class QueryError(ValueError):
    """The spec asks for something outside the allowlist. The message says what, and is safe to show."""


def _column(view: View, name: str) -> tuple[ColumnElement, Kind]:
    if name not in view.columns:
        raise QueryError(f"'{name}' is not a column of {view.name}; choose from: {', '.join(sorted(view.columns))}")
    return view.columns[name]


def _coerce(value: Any, kind: Kind, column: str) -> Any:
    try:
        if kind == "int":
            if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
                raise ValueError
            return int(value)
        if kind == "number":
            if isinstance(value, bool):
                raise ValueError
            return float(value)
        if kind == "time":
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed
        if kind == "uuid":
            return uuid.UUID(str(value))
        if isinstance(value, (bool, dict, list)):
            raise ValueError
        text = str(value)
        if len(text) > 200:
            raise ValueError
        return text
    except (ValueError, TypeError, OverflowError):
        raise QueryError(f"the value for '{column}' is not a valid {kind}") from None


def _condition(view: View, condition: Condition) -> ColumnElement:
    column, kind = _column(view, condition.column)
    if condition.op in (">", ">=", "<", "<=") and kind not in ORDERED_KINDS:
        raise QueryError(f"'{condition.column}' is a {kind} and can only be compared with = != in")
    if condition.op == "in":
        if not isinstance(condition.value, list) or not 0 < len(condition.value) <= MAX_IN_VALUES:
            raise QueryError(f"'in' needs a list of 1 to {MAX_IN_VALUES} values")
        return column.in_([_coerce(v, kind, condition.column) for v in condition.value])
    if isinstance(condition.value, list):
        raise QueryError(f"'{condition.op}' takes a single value, not a list")
    value = _coerce(condition.value, kind, condition.column)
    return {"=": column == value, "!=": column != value, ">": column > value, ">=": column >= value, "<": column < value, "<=": column <= value}[condition.op]


def _aggregate(view: View, item: Aggregate) -> tuple[ColumnElement, str]:
    if item.agg == "count":
        if item.column is not None:
            _column(view, item.column)
        expression = func.count() if item.column is None else func.count(_column(view, item.column)[0])
    else:
        if item.column is None:
            raise QueryError(f"'{item.agg}' needs a column")
        column, kind = _column(view, item.column)
        if item.agg in ("min", "max"):
            if kind not in ORDERED_KINDS:
                raise QueryError(f"'{item.agg}' needs a number or a time, and '{item.column}' is a {kind}")
            expression = func.min(column) if item.agg == "min" else func.max(column)
        else:
            if kind not in NUMERIC_KINDS:
                raise QueryError(f"'{item.agg}' needs a number, and '{item.column}' is a {kind}")
            if item.agg == "sum":
                expression = func.sum(column)
            elif item.agg == "avg":
                expression = func.avg(column)
            else:
                expression = func.percentile_cont(0.5 if item.agg == "p50" else 0.95).within_group(column)
    label = item.as_ or (f"{item.agg}_{item.column}" if item.column else item.agg)
    return expression.label(label), label


def compile_query(spec: QuerySpec, org_id: uuid.UUID) -> tuple[Select, list[str]]:
    """The SELECT for ``spec`` (always limited to ``org_id`` and a time window) and the names of its output columns."""
    view = VIEWS[spec.view]
    outputs: list[ColumnElement] = []
    names: list[str] = []
    plain: list[str] = []
    has_aggregate = False
    for item in spec.select:
        if isinstance(item, Aggregate):
            expression, label = _aggregate(view, item)
            has_aggregate = True
        else:
            column, _ = _column(view, item)
            expression, label = column.label(item), item
            plain.append(item)
        if label in names:
            raise QueryError(f"'{label}' is selected twice")
        outputs.append(expression)
        names.append(label)

    for column in spec.group_by:
        _column(view, column)
    if has_aggregate and set(plain) != set(spec.group_by):
        raise QueryError("with an aggregate, every plain column you select must be in group_by, and group_by can hold nothing else")
    if not has_aggregate and spec.group_by:
        raise QueryError("group_by needs an aggregate in select")

    start, end = spec.bounds()
    time_column = view.columns[view.time_column][0]
    conditions = [view.table.org_id == org_id, time_column >= start, time_column < end]
    conditions += [_condition(view, c) for c in spec.where]

    query = select(*outputs).select_from(view.table).where(and_(*conditions))
    if spec.group_by:
        query = query.group_by(*[_column(view, c)[0] for c in spec.group_by])
    for order in spec.order_by:
        if order.column not in names:
            raise QueryError(f"order_by '{order.column}' must be one of the selected columns: {', '.join(names)}")
        position = names.index(order.column)
        query = query.order_by(outputs[position].desc() if order.dir == "desc" else outputs[position].asc())
    return query.limit(spec.limit), names
