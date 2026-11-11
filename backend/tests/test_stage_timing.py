"""StageTimer: offsets from the request origin, recorded even when the stage raises."""

import time

import pytest

from types import SimpleNamespace

from app.services.stage_timing import StageTimer, timer_for_request


def test_records_name_offset_and_duration_in_order():
    timer = StageTimer(origin=time.perf_counter())
    with timer.stage("policy"):
        time.sleep(0.02)
    with timer.stage("upstream"):
        time.sleep(0.02)

    policy, upstream = timer.as_list()
    assert (policy["name"], upstream["name"]) == ("policy", "upstream")
    assert policy["ms"] >= 15 and upstream["ms"] >= 15
    assert upstream["start_ms"] >= policy["start_ms"] + policy["ms"] - 1  # the second stage began after the first ended


def test_a_stage_that_raises_is_still_recorded_and_the_error_propagates():
    timer = StageTimer(origin=time.perf_counter())
    with pytest.raises(RuntimeError, match="boom"):
        with timer.stage("upstream"):
            raise RuntimeError("boom")

    assert [s["name"] for s in timer.as_list()] == ["upstream"]


def test_as_list_returns_copies_so_callers_cannot_alter_the_record():
    timer = StageTimer(origin=time.perf_counter())
    with timer.stage("cache"):
        pass
    snapshot = timer.as_list()
    snapshot[0]["name"] = "tampered"
    snapshot.append({"name": "extra", "start_ms": 0, "ms": 0})

    assert [s["name"] for s in timer.as_list()] == ["cache"]


def test_an_empty_timer_has_no_stages():
    assert StageTimer(origin=time.perf_counter()).as_list() == []


def test_record_adds_a_stage_timed_elsewhere_with_offsets_from_the_origin():
    timer = StageTimer(origin=10.0)
    timer.record("auth", 10.0, 10.004)
    timer.record("later", 10.010, 10.030)
    assert timer.as_list() == [{"name": "auth", "start_ms": 0, "ms": 4}, {"name": "later", "start_ms": 10, "ms": 20}]


def _request_with(span):
    return SimpleNamespace(state=SimpleNamespace(auth_span=span))


def test_the_request_clock_starts_at_authentication_when_it_was_timed():
    now = time.perf_counter()  # stages read the real clock, so the fake span must be on it (a fixed 100.0 fails on a machine up under 100 s)
    timer = timer_for_request(_request_with((now - 0.006, now - 0.001)), pipeline_start=now)
    assert timer.origin == now - 0.006
    assert timer.as_list() == [{"name": "auth", "start_ms": 0, "ms": 5}]
    with timer.stage("policy"):
        pass
    assert timer.as_list()[1]["start_ms"] >= 5  # after authentication, never before it


def test_without_an_auth_span_the_clock_starts_with_the_pipeline():
    for request in (None, SimpleNamespace(), SimpleNamespace(state=SimpleNamespace()), _request_with(None)):
        timer = timer_for_request(request, pipeline_start=50.0)
        assert timer.origin == 50.0
        assert timer.as_list() == []


def test_a_malformed_or_impossible_auth_span_is_ignored_rather_than_trusted():
    for span in (("a", "b"), (1, 2), (100.0,), (100.0, 99.0), (100.0, 100.5), "x"):  # last: ends after the pipeline began
        timer = timer_for_request(_request_with(span), pipeline_start=100.2)
        assert timer.as_list() == [], span
        assert timer.origin == 100.2
