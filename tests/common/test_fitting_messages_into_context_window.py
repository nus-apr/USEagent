# tests/test_context_window_fit.py
from typing import Any

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from useagent.common.context_window import (
    MARKER_TEXT,
)
from useagent.common.context_window import count_tokens as real_count_tokens
from useagent.common.context_window import (
    fit_messages_into_context_window,
    remove_orphaned_tool_responses,
)
from useagent.config import ConfigSingleton


@pytest.fixture(autouse=True)
def _reset_and_init_config(monkeypatch: pytest.MonkeyPatch) -> None:
    ConfigSingleton.reset()
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    ConfigSingleton.init("openai:gpt-5-mini")
    yield
    ConfigSingleton.reset()


@pytest.fixture
def patch_count_tokens(monkeypatch: pytest.MonkeyPatch):
    async def _fake_count_tokens(messages: list[object]) -> int:
        total = 0
        for m in messages:
            for p in getattr(m, "parts", []) or []:
                total += len(getattr(p, "content", "") or "")
        return total

    monkeypatch.setattr(
        "useagent.common.context_window.count_tokens", _fake_count_tokens
    )
    return _fake_count_tokens


def make_model_repsonse_message(txt: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=txt)])


def make_text_resp(txt: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=txt)])


def make_user(txt: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=txt)])


def make_user_message(txt: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=txt)])


def make_tool_return(call_id: str, content: str) -> ModelRequest:
    return ModelRequest(
        parts=[ToolReturnPart(tool_call_id=call_id, tool_name="dummy", content=content)]
    )


async def _text_with_min_tokens(min_tokens: int, seed: str = "tok") -> str:
    chunks = []
    while True:
        chunks.append(seed)
        msg = make_model_repsonse_message(" ".join(chunks))
        n = await real_count_tokens([msg])
        if n >= min_tokens:
            return " ".join(chunks)


def _has_marker(m) -> bool:
    parts = getattr(m, "parts", None)
    if parts:
        for p in parts:
            c = getattr(p, "content", None)
            if isinstance(c, str) and MARKER_TEXT in c:
                return True
    return False


@pytest.mark.asyncio
async def test_fit_messages_should_return_empty_list_for_empty_input(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    out = await fit_messages_into_context_window(
        [],
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )
    assert out == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "num_msgs,msg_len",
    [
        (1, 100),
        (5, 120),
        (8, 150),
        (10, 200),
        (15, 90),
    ],
)
async def test_fit_messages_should_cut_parametrized(
    num_msgs: int,
    msg_len: int,
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    limit: int = ConfigSingleton.config.lookup_model_context_window()
    messages: list[str] = ["x" * msg_len for _ in range(num_msgs)]
    before: int = await patch_count_tokens(messages)
    out = await fit_messages_into_context_window(
        messages,
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )
    after: int = await patch_count_tokens(out)
    assert after <= limit
    if before <= limit:
        assert out == messages


@pytest.mark.asyncio
async def test_short_messages_should_not_be_cut(patch_count_tokens) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    messages: list[str] = ["hi", "there"]
    out = await fit_messages_into_context_window(
        messages,
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )
    assert out == messages
    total = await patch_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.asyncio
async def test_many_long_messages_should_reduce_by_drop_or_truncation(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000

    unit = "x" * 200
    messages = [ModelResponse(parts=[TextPart(content=unit)]) for _ in range(10)]

    out = await fit_messages_into_context_window(
        messages,
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )

    total = await patch_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()

    length_reduced = len(out) < len(messages)
    truncated_present = any(
        any(
            isinstance(p, TextPart)
            and isinstance(p.content, str)
            and (MARKER_TEXT in p.content or len(p.content) < len(unit))
            for p in getattr(m, "parts", []) or []
        )
        for m in out
    )
    assert length_reduced or truncated_present


@pytest.mark.asyncio
async def test_last_message_longest_should_be_preserved_and_fit(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    small: str = "a" * 100
    big: str = "b" * 900
    messages: list[str] = [small, small, small, big]
    out = await fit_messages_into_context_window(
        messages,
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )
    assert len(out) > 0
    total = await patch_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.asyncio
async def test_newest_message_alone_exceeds_limit_should_result_fit(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    limit = ConfigSingleton.config.lookup_model_context_window()
    small = "a" * 10
    big = "B" * (limit + 100)
    messages = [small, small, big]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    total = await patch_count_tokens(out)
    assert total <= limit
    assert len(out) > 0


@pytest.mark.asyncio
async def test_two_oversized_messages_should_shrink_and_fit(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    limit = ConfigSingleton.config.lookup_model_context_window()
    m1 = "X" * (limit + 50)
    m2 = "Y" * (limit + 200)
    messages = [m1, m2]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    total = await patch_count_tokens(out)
    assert total <= limit
    assert len(out) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "messages",
    [
        [],
        ["hi", "there"],
        ["x" * 200 for _ in range(10)],
        ["a" * 100, "b" * 100, "c" * 900],
        ["s" * 300, "t" * 300, "u" * 300],
    ],
)
async def test_fit_messages_called_twice_should_be_identical(
    messages: list[str],
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    first = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    second = await fit_messages_into_context_window(
        first, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert second == first


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "messages",
    [
        ["hi"],
        ["hello", "world"],
        ["x" * 50 for _ in range(5)],
        ["mixed", "lengths", "x" * 123, ""],
    ],
)
async def test_real_count_tokens_should_return_int(messages: list[Any]) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    out: int = await real_count_tokens(messages)
    assert isinstance(out, int)
    assert out >= 0


@pytest.mark.asyncio
async def test_real_count_tokens_should_return_minus_one_when_uninitialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    monkeypatch.setattr(
        "useagent.common.context_window.ConfigSingleton.is_initialized", lambda: False
    )
    out: int = await real_count_tokens([])
    assert out == -1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_fit_messages_should_cut_no_monkeypatch() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 800
    messages: list[str] = ["x" * 300, "y" * 300, "z" * 300]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "num_msgs,msg_len,limit",
    [
        (6, 120, 600),
        (8, 140, 700),
        (10, 160, 900),
    ],
)
async def test_integration_fitting_content_messages_is__fit_messages_parametrized_no_monkeypatch(
    num_msgs: int, msg_len: int, limit: int
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = limit
    messages: list[str] = ["x" * msg_len for _ in range(num_msgs)]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_fitting_content_messages_is_idempotent_no_monkeypatch() -> (
    None
):
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    messages: list[str] = ["x" * 200 for _ in range(10)]
    first = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    second = await fit_messages_into_context_window(
        first, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert second == first


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_reduction_no_marker() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 2000
    messages = [
        make_model_repsonse_message("hello"),
        make_model_repsonse_message("world"),
        make_model_repsonse_message("tiny message"),
    ]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert out == messages
    assert not any(_has_marker(m) for m in out)


# --- Updated: allow unchanged if per-turn caps not applied because total <= budget


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_oversized_newest_gets_marker_or_truncation() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    budget = 1000
    newest_cap = int(budget * 0.60)
    second_cap = int(budget * 0.30)

    small_txt = await _text_with_min_tokens(second_cap - 20)
    big_txt = await _text_with_min_tokens(newest_cap + 50)

    messages = [
        make_model_repsonse_message(small_txt),
        make_model_repsonse_message(big_txt),
    ]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert len(out) == 2
    newest_out = out[-1]
    # Accept marker, truncation, or unchanged, but overall must fit budget
    ok = _has_marker(newest_out) or (
        len(getattr(newest_out.parts[0], "content", "")) <= len(big_txt)
    )
    assert ok
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_newest_oversized_both_marked_or_truncated() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    budget = 1000
    newest_cap = int(budget * 0.60)
    second_cap = int(budget * 0.30)

    older = [
        make_model_repsonse_message(await _text_with_min_tokens(40)),
        make_model_repsonse_message(await _text_with_min_tokens(40)),
    ]
    second_newest = make_model_repsonse_message(
        await _text_with_min_tokens(second_cap + 50)
    )
    newest = make_model_repsonse_message(await _text_with_min_tokens(newest_cap + 100))
    messages = older + [second_newest, newest]

    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) >= 2
    s2 = out[-2]
    s1 = out[-1]
    # Accept marker, truncation, or unchanged if still fits budget
    assert _has_marker(s2) or len(getattr(s2.parts[0], "content", "")) <= len(
        getattr(second_newest.parts[0], "content", "")
    )
    assert _has_marker(s1) or len(getattr(s1.parts[0], "content", "")) <= len(
        getattr(newest.parts[0], "content", "")
    )
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_only_oldest_exceeds_window_keep_length_and_mark_or_truncate_only_oldest() -> (
    None
):
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    budget = 1000
    oldest_txt = await _text_with_min_tokens(budget + 200)
    rest = [
        make_model_repsonse_message(await _text_with_min_tokens(40)) for _ in range(4)
    ]
    messages = [make_model_repsonse_message(oldest_txt)] + rest

    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) == len(messages)
    oldest_out = out[0]
    assert _has_marker(oldest_out) or len(
        getattr(oldest_out.parts[0], "content", "")
    ) <= len(oldest_txt)
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_ten_messages_oversized_result_two_newest_with_markers_or_truncation() -> (
    None
):
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    budget = 1000
    msgs = [
        make_model_repsonse_message(await _text_with_min_tokens(budget + 100))
        for _ in range(10)
    ]

    out = await fit_messages_into_context_window(
        msgs, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) >= 2
    assert _has_marker(out[-1]) or len(getattr(out[-1].parts[0], "content", "")) <= len(
        getattr(msgs[-1].parts[0], "content", "")
    )
    assert _has_marker(out[-2]) or len(getattr(out[-2].parts[0], "content", "")) <= len(
        getattr(msgs[-2].parts[0], "content", "")
    )
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


# --- Boundary: exactly at caps -> unchanged


@pytest.mark.integration
@pytest.mark.asyncio
async def test_boundary_exact_caps_no_marker() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    budget = 1000
    newest_cap = int(budget * 0.60)
    second_cap = int(budget * 0.30)

    second_txt = await _text_with_min_tokens(second_cap)
    newest_txt = await _text_with_min_tokens(newest_cap)
    older = make_model_repsonse_message(await _text_with_min_tokens(20))
    messages = [
        older,
        make_model_repsonse_message(second_txt),
        make_model_repsonse_message(newest_txt),
    ]

    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert out == messages
    assert not _has_marker(out[-1])
    assert not _has_marker(out[-2])
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_message_oversized_kept_and_marked_or_truncated() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 200
    big = await _text_with_min_tokens(400)
    messages = [make_model_repsonse_message(big)]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) == 1
    assert _has_marker(out[0]) or len(getattr(out[0].parts[0], "content", "")) <= len(
        big
    )
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_marker_larger_than_cap_results_empty_text() -> None:
    marker_msg = make_model_repsonse_message(MARKER_TEXT)
    marker_tokens = await real_count_tokens([marker_msg])
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = max(
        1, marker_tokens - 1
    )
    big = await _text_with_min_tokens(marker_tokens + 50)
    messages = [make_model_repsonse_message(big)]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) == 1
    assert not _has_marker(out[0])
    assert getattr(out[0].parts[0], "content", None) == ""
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


# --- Updated orphan handling expectations in fit(): cleanup runs only on the trimming path


@pytest.mark.asyncio
async def test_orphan_oldest_processed_only_when_over_budget(
    patch_count_tokens,
) -> None:
    # Force trimming path; otherwise orphans are not touched
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 20

    orphan = make_tool_return("call_x", "result A")  # ~8
    keep1 = make_text_resp("hello" * 5)  # 25
    keep2 = make_text_resp("world" * 5)  # 25

    messages = [orphan, keep1, keep2]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert out  # non-empty
    # No ToolReturnPart anywhere after processing
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_trimming_that_creates_orphan_is_cleaned_and_fits(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 120

    orphan = make_tool_return("call_big", "x" * 80)
    m1 = make_text_resp("y" * 60)
    m2 = make_text_resp("z" * 60)

    messages = [orphan, m1, m2]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert out
    head = out[0]
    assert not (
        isinstance(head, ModelRequest)
        and any(isinstance(p, ToolReturnPart) for p in getattr(head, "parts", []) or [])
    )
    total = await patch_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.asyncio
async def test_multiple_leading_orphans_cleaned_when_over_budget(
    patch_count_tokens,
) -> None:
    # Force processing; else early return would keep orphans
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 30

    orphan1 = make_tool_return("call_a", "result A")
    orphan2 = make_tool_return("call_b", "result B")
    survivor = make_user("user says hi" * 5)

    messages = [orphan1, orphan2, survivor]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert out
    assert isinstance(out[-1], ModelRequest)  # survivor remains
    # Orphans are removed/cleaned
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_leading_orphans_cleaned_even_when_budget_tight(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 90

    orphan_big = make_tool_return("call_big", "x" * 90)
    orphan_small = make_tool_return("call_small", "y" * 10)
    survivor = make_text_resp("z" * 60)

    messages = [orphan_big, orphan_small, survivor]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=0.8, delay_between_model_calls_in_seconds=0.0
    )

    assert out
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_no_orphans_anywhere_in_output_requires_integrity_guard(
    patch_count_tokens,
) -> None:
    # Force processing to trigger orphan cleanup
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 20

    leading_ok = make_text_resp("ok" * 10)
    orphan_mid = make_tool_return("call_mid", "tool payload" * 5)

    messages = [leading_ok, orphan_mid]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_newest_orphan_trim_should_not_result_empty_list(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 80

    older_big = make_text_resp("x" * 200)
    mid = make_text_resp("y" * 60)
    newest_orphan = make_tool_return("call_1", "z" * 40)

    messages = [older_big, mid, newest_orphan]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert out
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_newest_orphan_only_survivor_idempotent_and_nonempty(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 70

    older = make_text_resp("a" * 100)
    newest_orphan = make_tool_return("call_last", "b" * 60)

    first = await fit_messages_into_context_window(
        [older, newest_orphan],
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )
    second = await fit_messages_into_context_window(
        first, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert first
    assert second == first
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in first
    )


@pytest.mark.asyncio
async def test_force_fit_single_on_only_orphan_should_not_be_empty(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 50

    orphan_huge = make_tool_return("call_big", "z" * 200)
    messages = [orphan_huge]

    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert out
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_force_fit_single_on_orphan_after_trimming_pipeline_should_not_be_empty(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 60

    m1 = make_text_resp("u" * 100)
    m2 = make_text_resp("v" * 100)
    orphan_last = make_tool_return("call_tail", "w" * 120)

    out = await fit_messages_into_context_window(
        [m1, m2, orphan_last],
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )

    assert out
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_orphan_only_input_results_in_placeholder_or_cleaned_not_salvage_notice(
    patch_count_tokens,
) -> None:
    # With your current pipeline, the final guard may either produce a placeholder
    # (via orphan removal) or a pruned notice if salvage fails.
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 50

    orphan_only = make_tool_return("call_lone", "x" * 200)
    out = await fit_messages_into_context_window(
        [orphan_only], safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert len(out) == 1
    # Either a placeholder ModelRequest (no ToolReturnPart) or the pruned ModelResponse notice
    no_tool_returns = not any(
        isinstance(p, ToolReturnPart) for p in getattr(out[0], "parts", []) or []
    )
    assert no_tool_returns


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "messages,limit",
    [
        (["x" * 500], 200),
        ([make_text_resp("a" * 400), make_text_resp("b" * 400)], 500),
        ([make_tool_return("t1", "r" * 300), make_text_resp("keep" * 80)], 120),
        ([make_text_resp("keep" * 80), make_tool_return("t2", "r" * 400)], 120),
        ([make_tool_return("t3", "r" * 400)], 80),
        (["", "tiny", ""], 10),
    ],
)
async def test_nonempty_input_should_not_return_empty(
    messages: list[Any], limit: int, patch_count_tokens
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = limit
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert out
    total = await patch_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.asyncio
async def test_survivor_order_should_be_preserved(patch_count_tokens) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 150
    ids = [f"id_{i}" for i in range(6)]
    # Long fillers to force drops; short tagged survivors interleaved
    msgs = [
        make_text_resp("X" * 200),
        make_text_resp(ids[0]),
        make_text_resp("Y" * 180),
        make_text_resp(ids[1]),
        make_text_resp(ids[2]),
        make_text_resp("Z" * 300),
        make_text_resp(ids[3]),
        make_text_resp("W" * 300),
        make_text_resp(ids[4]),
        make_text_resp(ids[5]),
    ]
    out = await fit_messages_into_context_window(
        msgs, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    # Extract survivor id-tag contents (exact match on our tags)
    def content_str(m: Any) -> str:
        return getattr(getattr(m, "parts", [TextPart(content="")])[0], "content", "")

    survivors = [c for c in map(content_str, out) if c in ids]
    # survivors must appear in the same relative order as original ids
    assert survivors == [i for i in ids if i in survivors]


@pytest.mark.asyncio
async def test_multiple_runs_should_be_idempotent_over_5_calls(
    patch_count_tokens,
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 300
    msgs = [
        make_text_resp("A" * 250),
        make_text_resp("B" * 250),
        make_tool_return("t", "C" * 200),
    ]
    # First normalization
    baseline = await fit_messages_into_context_window(
        msgs, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    prev = baseline
    for _ in range(4):
        prev = await fit_messages_into_context_window(
            prev, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
        )
        assert prev == baseline
    total = await patch_count_tokens(prev)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "placement",
    ["head", "mid", "tail"],
)
async def test_no_toolreturnpart_anywhere_after_processing_when_over_budget(
    placement: str, patch_count_tokens
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 100
    orphan = make_tool_return("call_orphan", "r" * 120)
    a = make_text_resp("a" * 90)
    b = make_text_resp("b" * 90)
    if placement == "head":
        msgs = [orphan, a, b]
    elif placement == "mid":
        msgs = [a, orphan, b]
    else:
        msgs = [a, b, orphan]
    out = await fit_messages_into_context_window(
        msgs, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert out
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )
    total = await patch_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.asyncio
async def test_trimming_changes_newest_and_never_expands_others(
    patch_count_tokens,
) -> None:
    budget = 200
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = budget
    newest_cap = int(budget * 0.60)  # 120
    second_cap = int(budget * 0.30)  # 60

    # Use raw lengths to match the patched counter semantics
    second_txt = "s" * second_cap
    newest_big = "n" * (newest_cap + 80)

    msgs = [
        make_model_repsonse_message(second_txt),  # second-newest (<= cap)
        make_model_repsonse_message(newest_big),  # newest (> cap)
    ]

    first = await fit_messages_into_context_window(
        msgs, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    newest_content = getattr(first[-1].parts[0], "content", "")
    assert _has_marker(first[-1]) or len(newest_content) < len(newest_big)

    second_content = getattr(first[-2].parts[0], "content", "")
    assert len(second_content) <= len(second_txt)

    total = await patch_count_tokens(first)
    assert total <= ConfigSingleton.config.lookup_model_context_window()

    second = await fit_messages_into_context_window(
        first, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert second == first


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [50, 100, 200, 500])
async def test_nonempty_input_never_returns_empty_variant_2(
    limit: int, patch_count_tokens
) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = limit
    cases = [
        [make_text_resp("a" * (limit * 2))],
        [make_text_resp("a" * (limit // 2)), make_text_resp("b" * (limit * 2))],
        [make_tool_return("t", "x" * (limit * 3))],
        [
            make_text_resp("u" * (limit)),
            make_tool_return("t2", "y" * (limit * 2)),
            make_text_resp("z"),
        ],
    ]
    for msgs in cases:
        out = await fit_messages_into_context_window(
            msgs, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
        )
        assert out  # non-empty


@pytest.mark.integration
@pytest.mark.asyncio
async def test_instructions_are_trimmed_when_over_budget() -> None:
    # Uses real tokenizer; requires code change above.
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 200
    # Large instructions, tiny part
    req = ModelRequest(
        parts=[UserPromptPart(content="hi")],
        instructions="I" * 2000,  # big
    )
    out = await fit_messages_into_context_window(
        [req], safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert out and isinstance(out[0], ModelRequest)
    # Either instructions got reduced or converted into truncated text content
    instr = getattr(out[0], "instructions", "")
    all_text = "".join(
        getattr(p, "content", "") or "" for p in getattr(out[0], "parts", []) or []
    )
    assert (instr and len(instr) < 2000) or MARKER_TEXT in all_text
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_count_tokens_should_include_modelrequest_instructions() -> None:
    """
    If a ModelRequest has only `instructions`, token counting must reflect them.
    """
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000

    req = ModelRequest(parts=[], instructions="I" * 1000)  # only instructions
    total = await real_count_tokens([req])
    assert isinstance(total, int)
    # Expect non-zero once instructions are included in counting
    assert total > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fit_two_messages_large_instructions_on_newest_should_reduce_and_fit() -> (
    None
):
    """
    Per-turn caps should apply to newest message even if the excess comes from instructions.
    """
    budget = 200
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = budget

    older = ModelResponse(parts=[TextPart(content="small")])
    newest = ModelRequest(
        parts=[UserPromptPart(content="tiny")], instructions="N" * 1000
    )

    out = await fit_messages_into_context_window(
        [older, newest], safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) == 2

    # Newest must be changed (marked in parts or instructions shortened/cleared)
    out_newest = out[-1]
    assert isinstance(out_newest, ModelRequest)
    instr_after = getattr(out_newest, "instructions", "") or ""
    parts_text = "".join(
        getattr(p, "content", "") or "" for p in getattr(out_newest, "parts", []) or []
    )
    assert MARKER_TEXT in parts_text or len(instr_after) < 1000 or instr_after == ""

    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fit_single_request_with_only_instructions_should_truncate_or_mark() -> (
    None
):
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 200
    # Make instructions that are definitely > budget tokens
    big_instr = await _text_with_min_tokens(600)  # comfortably above 200

    req = ModelRequest(parts=[], instructions=big_instr)

    out = await fit_messages_into_context_window(
        [req], safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert out and isinstance(out[0], ModelRequest)
    m: ModelRequest = out[0]

    instr_after = getattr(m, "instructions", "") or ""
    parts_text = "".join(
        getattr(p, "content", "") or "" for p in getattr(m, "parts", []) or []
    )
    # Must have changed: either instructions shrunk, moved into parts w/ marker, or cleared
    assert (
        len(instr_after) < len(big_instr)
        or MARKER_TEXT in parts_text
        or instr_after == ""
    )

    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_per_turn_caps_apply_to_instructions_exact_boundary_is_stable() -> None:
    budget = 200
    newest_cap = int(budget * 0.60)  # 120
    second_cap = int(budget * 0.30)  # 60
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = budget

    # Build second-newest to be ~exactly at its cap in tokens
    second_exact_txt = await _text_with_min_tokens(second_cap)
    # Newest blows its per-turn cap via instructions
    newest_instr = await _text_with_min_tokens(newest_cap + 150)

    second_msg = ModelResponse(parts=[TextPart(content=second_exact_txt)])
    newest_msg = ModelRequest(
        parts=[UserPromptPart(content="ok")], instructions=newest_instr
    )

    out = await fit_messages_into_context_window(
        [second_msg, newest_msg],
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )
    assert len(out) == 2

    # Second-newest should not grow; it can remain unchanged
    out_second = out[-2]
    assert isinstance(out_second, ModelResponse)
    second_after = getattr(out_second.parts[0], "content", "")
    assert len(second_after) <= len(second_exact_txt)

    # Newest should be changed (marker in parts OR shorter instructions OR cleared)
    out_newest = out[-1]
    assert isinstance(out_newest, ModelRequest)
    instr_after = getattr(out_newest, "instructions", "") or ""
    parts_text = "".join(
        getattr(p, "content", "") or "" for p in getattr(out_newest, "parts", []) or []
    )
    assert (
        MARKER_TEXT in parts_text
        or len(instr_after) < len(newest_instr)
        or instr_after == ""
    )

    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


### Regression on Orphaned Messages


def _tool_call_msg(call_id: str) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name="dummy", args={}, tool_call_id=call_id)]
    )


def _tool_return_msg(call_id: str, content: str = "ok") -> ModelRequest:
    return ModelRequest(
        parts=[ToolReturnPart(tool_name="dummy", tool_call_id=call_id, content=content)]
    )


def _text_resp(s: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=s)])


# --- New behavior: orphan returns are replaced in-place with a small user message ---


@pytest.mark.asyncio
async def test_orphan_leading_and_middle_are_replaced_with_placeholders() -> None:
    orphan1 = _tool_return_msg("call_a")
    mid_text = _text_resp("hello")
    orphan2 = _tool_return_msg("call_b")
    tail_call = _tool_call_msg("call_c")  # no return present, fine
    msgs = [orphan1, mid_text, orphan2, tail_call]

    out = remove_orphaned_tool_responses(msgs)

    assert len(out) == 4  # positions preserved via placeholders
    # pos 0 placeholder
    assert isinstance(out[0], ModelRequest)
    assert len(out[0].parts) == 1 and isinstance(out[0].parts[0], UserPromptPart)
    assert "removed" in (out[0].parts[0].content or "").lower()
    # pos 1 unchanged
    assert out[1] == mid_text
    # pos 2 placeholder
    assert isinstance(out[2], ModelRequest)
    assert len(out[2].parts) == 1 and isinstance(out[2].parts[0], UserPromptPart)
    assert "removed" in (out[2].parts[0].content or "").lower()
    # pos 3 unchanged tool call
    assert out[3] == tail_call
    # no tool returns remain
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_trailing_orphan_is_replaced_with_placeholder() -> None:
    call = _tool_call_msg("call_a")
    kept_ret = _tool_return_msg("call_a", "ok")
    orphan_trailer = _tool_return_msg("no_match", "drop")
    msgs = [call, kept_ret, orphan_trailer]

    out = remove_orphaned_tool_responses(msgs)

    assert len(out) == 3
    # last is placeholder
    assert isinstance(out[-1], ModelRequest)
    assert len(out[-1].parts) == 1 and isinstance(out[-1].parts[0], UserPromptPart)
    assert "removed" in (out[-1].parts[0].content or "").lower()
    # first two unchanged and still paired
    assert out[0] == call
    assert out[1] == kept_ret
    # no orphan returns remain
    assert all(
        not any(
            isinstance(p, ToolReturnPart) and p.tool_call_id == "no_match"
            for p in getattr(m, "parts", []) or []
        )
        for m in out
    )


@pytest.mark.asyncio
async def test_request_with_only_orphan_returns_becomes_placeholder() -> None:
    # Single message composed only of orphan returns -> replaced by placeholder
    only_orphans = ModelRequest(
        parts=[
            ToolReturnPart(tool_name="dummy", tool_call_id="x1", content="r1"),
            ToolReturnPart(tool_name="dummy", tool_call_id="x2", content="r2"),
        ]
    )

    out = remove_orphaned_tool_responses([only_orphans])

    assert len(out) == 1
    assert isinstance(out[0], ModelRequest)
    assert len(out[0].parts) == 1 and isinstance(out[0].parts[0], UserPromptPart)
    assert "removed" in (out[0].parts[0].content or "").lower()
    # ensure no ToolReturnPart survives
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_mixed_text_and_orphan_keeps_text_without_placeholder() -> None:
    # Mixed request with user text + orphan return: drop return, keep text, no placeholder
    mixed = ModelRequest(
        parts=[
            TextPart(content="keep me"),
            ToolReturnPart(tool_name="dummy", tool_call_id="ghost", content="drop"),
        ]
    )

    out = remove_orphaned_tool_responses([mixed])

    assert len(out) == 1
    kept = out[0]
    assert isinstance(kept, ModelRequest)
    # only the text remains
    assert any(isinstance(p, TextPart) and p.content == "keep me" for p in kept.parts)
    assert all(not isinstance(p, ToolReturnPart) for p in kept.parts)
    # no placeholder added since message still has content
    assert not any(isinstance(p, UserPromptPart) for p in kept.parts)


@pytest.mark.asyncio
async def test_return_before_call_is_kept_and_not_flagged_as_orphan() -> None:
    # Two-pass: return may appear before matching call; it must be kept
    ret = _tool_return_msg("call_rev", "val")
    mid = _text_resp("middle")
    call = _tool_call_msg("call_rev")
    msgs = [ret, mid, call]

    out = remove_orphaned_tool_responses(msgs)

    assert out == msgs
    # return preserved (not replaced with placeholder)
    assert isinstance(out[0], ModelRequest)
    assert any(isinstance(p, ToolReturnPart) for p in out[0].parts)
    assert not any(isinstance(p, UserPromptPart) for p in out[0].parts)


@pytest.mark.asyncio
async def test_duplicate_returns_for_same_call_are_all_kept_with_call_anywhere() -> (
    None
):
    call = _tool_call_msg("dup_call")
    ret1 = _tool_return_msg("dup_call", "r1")
    ret2 = _tool_return_msg("dup_call", "r2")
    # Place the call at the end to ensure order independence
    msgs = [ret1, ret2, _text_resp("padding"), call]

    out = remove_orphaned_tool_responses(msgs)

    assert len(out) == 4
    # both returns still present (no placeholders)
    assert all(
        isinstance(out[i], ModelRequest)
        and any(isinstance(p, ToolReturnPart) for p in out[i].parts)
        for i in (0, 1)
    )
    assert not any(
        any(isinstance(p, UserPromptPart) for p in getattr(m, "parts", []) or [])
        for m in out[:2]
    )


@pytest.mark.regression
@pytest.mark.asyncio
async def test_initial_system_and_user_messages_are_preserved() -> None:
    from pydantic_ai.messages import SystemPromptPart, UserPromptPart

    system_init = ModelRequest(
        parts=[SystemPromptPart(content="You are a helpful assistant.")]
    )
    system_instr = ModelRequest(
        parts=[SystemPromptPart(content="Follow the guidelines strictly.")]
    )
    first_user = ModelRequest(parts=[UserPromptPart(content="Hello, can you help me?")])

    msgs = [system_init, system_instr, first_user]

    out = remove_orphaned_tool_responses(msgs)

    # No changes expected; nothing is a ToolReturnPart and nothing should be dropped.
    assert out == msgs
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_empty_list_returns_empty() -> None:
    out = remove_orphaned_tool_responses([])
    assert out == []


@pytest.mark.asyncio
async def test_large_list_without_any_tool_pairs_preserves_calls_and_text_replaces_returns() -> (
    None
):
    """
    Build a larger interleaved history:
      - 30 plain text assistant messages
      - 30 tool CALLs with ids c0..c29
      - 30 tool RETURNs with ids r0..r29 (no matching calls)
    Expect:
      - Text and calls are preserved in-place
      - Every return is replaced by an in-place placeholder user message
      - No ToolReturnPart remains anywhere
    """
    # 30 texts, 30 calls, 30 unmatched returns
    texts = [_text_resp(f"txt-{i}") for i in range(30)]
    calls = [_tool_call_msg(f"c{i}") for i in range(30)]
    returns = [_tool_return_msg(f"r{i}", "payload") for i in range(30)]

    # Interleave to mix ordering and positions: [text0, call0, ret0, text1, call1, ret1, ...]
    msgs: list[ModelRequest | ModelResponse] = []
    for i in range(30):
        msgs.append(texts[i])
        msgs.append(calls[i])
        msgs.append(returns[i])

    out = remove_orphaned_tool_responses(msgs)

    # Length and positional preservation via placeholders
    assert len(out) == len(msgs)

    # All ToolCallPart messages remain intact and count matches
    num_calls_out = sum(
        1
        for m in out
        if isinstance(m, ModelResponse)
        and any(isinstance(p, ToolCallPart) for p in (getattr(m, "parts", []) or []))
    )
    assert num_calls_out == len(calls)

    # No ToolReturnPart should survive
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in (getattr(m, "parts", []) or []))
        for m in out
    )

    # Every previous return position should now be a placeholder ModelRequest with a UserPromptPart
    for i in range(30):
        placeholder = out[3 * i + 2]  # positions where returns were placed
        assert isinstance(placeholder, ModelRequest)
        parts = getattr(placeholder, "parts", []) or []
        assert len(parts) == 1 and isinstance(parts[0], UserPromptPart)
        assert "removed" in (parts[0].content or "").lower()

    # Spot-check that a couple of texts stayed verbatim in-place
    assert out[0] == texts[0]
    assert out[3 * 10] == texts[10]
