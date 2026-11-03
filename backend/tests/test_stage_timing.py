"""StageTimer: offsets from the request origin, recorded even when the stage raises."""

import time

import pytest

from app.services.stage_timing import StageTimer


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
