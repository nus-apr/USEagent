import json

import pytest
from pydantic_ai.usage import Usage

from useagent.state.usage_tracker import UsageTracker


def test_add_should_not_create_base_key_without_call_suffix() -> None:
    tracker = UsageTracker()
    tracker.add("foo", Usage(requests=1))

    assert "foo" not in tracker.usage
    assert "foo-call-no-1" in tracker.usage


def test_add_should_store_usage_with_incrementing_keys() -> None:
    tracker = UsageTracker()

    u1 = Usage(requests=1)
    u2 = Usage(requests=2)

    tracker.add("foo", u1)
    tracker.add("foo", u2)
    tracker.add("bar", u1)

    assert tracker.counts["foo"] == 2
    assert tracker.counts["bar"] == 1

    assert "foo-call-no-1" in tracker.usage
    assert "foo-call-no-2" in tracker.usage
    assert "bar-call-no-1" in tracker.usage

    assert tracker.usage["foo-call-no-1"].requests == 1
    assert tracker.usage["foo-call-no-2"].requests == 2


def test_group_should_sum_usage_per_base_name() -> None:
    tracker = UsageTracker()

    tracker.add("foo", Usage(requests=1, request_tokens=5))
    tracker.add("foo", Usage(requests=2, request_tokens=10))
    tracker.add("bar", Usage(requests=3))

    grouped = tracker.group()

    assert "foo" in grouped.usage
    assert "bar" in grouped.usage

    foo_usage = grouped.usage["foo"]
    bar_usage = grouped.usage["bar"]

    assert foo_usage.requests == 3
    assert foo_usage.request_tokens == 15
    assert bar_usage.requests == 3


def test_group_should_not_mutate_original_tracker() -> None:
    tracker = UsageTracker()
    tracker.add("foo", Usage(requests=1))
    grouped = tracker.group()

    assert "foo" not in tracker.usage
    assert "foo" in grouped.usage


def test_to_json_should_serialize_usage_dict() -> None:
    tracker = UsageTracker()

    tracker.add(
        "foo",
        Usage(
            requests=1,
            request_tokens=2,
            response_tokens=3,
            total_tokens=5,
            details={"x": 9},
        ),
    )

    result = tracker.to_json()

    assert "foo-call-no-1" in result
    usage_json = result["foo-call-no-1"]

    assert usage_json["requests"] == 1
    assert usage_json["request_tokens"] == 2
    assert usage_json["response_tokens"] == 3
    assert usage_json["total_tokens"] == 5
    assert usage_json["details"] == {"x": 9}


@pytest.mark.parametrize("invalid_key", ["", "   ", "\n"])
def test_add_should_reject_invalid_nonemptystr_keys(invalid_key) -> None:
    tracker = UsageTracker()
    usage = Usage(requests=1)

    with pytest.raises(ValueError):
        tracker.add(invalid_key, usage)


def test_to_json_and_from_json_should_roundtrip_with_two_entries(tmp_path) -> None:
    tracker = UsageTracker()
    tracker.add("foo", Usage(requests=1, request_tokens=10))
    tracker.add("bar", Usage(requests=2, response_tokens=20))

    path = tmp_path / "usage.json"
    with path.open("w") as f:
        json.dump(tracker.to_json(), f)

    with path.open() as f:
        loaded = json.load(f)
    restored = UsageTracker.from_json(loaded)

    assert restored.usage["foo-call-no-1"].requests == 1
    assert restored.usage["foo-call-no-1"].request_tokens == 10
    assert restored.usage["bar-call-no-1"].requests == 2
    assert restored.usage["bar-call-no-1"].response_tokens == 20


def test_group_should_correctly_sum_interleaved_keys() -> None:
    tracker = UsageTracker()
    tracker.usage = {
        "foo-call-no-1": Usage(requests=1),
        "foo-call-no-9": Usage(requests=2),
        "bar-call-no-2": Usage(requests=3),
    }

    grouped = tracker.group()
    assert grouped.usage["foo"].requests == 3
    assert grouped.usage["bar"].requests == 3


def test_to_json_and_from_json_should_work_with_empty_tracker(tmp_path) -> None:
    tracker = UsageTracker()

    path = tmp_path / "empty.json"
    with path.open("w") as f:
        json.dump(tracker.to_json(), f)

    with path.open() as f:
        loaded = json.load(f)
    restored = UsageTracker.from_json(loaded)

    assert restored.usage == {}


def test_from_json_should_work_with_empty_dict(tmp_path) -> None:
    path = tmp_path / "empty_input.json"
    with path.open("w") as f:
        json.dump({}, f)

    with path.open() as f:
        loaded = json.load(f)
    restored = UsageTracker.from_json(loaded)

    assert isinstance(restored, UsageTracker)
    assert restored.usage == {}


def test_from_json_should_work_with_partial_fields() -> None:
    data = {
        "foo-call-no-1": {
            "requests": 1,
            "request_tokens": None,
            "response_tokens": None,
            "total_tokens": None,
            "details": None,
        }
    }
    tracker = UsageTracker.from_json(data)
    assert tracker.usage["foo-call-no-1"].requests == 1
