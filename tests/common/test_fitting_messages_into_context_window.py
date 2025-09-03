# tests/test_context_window_fit.py
from typing import Any

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from useagent.common.context_window import MARKER_TEXT
from useagent.common.context_window import count_tokens as real_count_tokens
from useagent.common.context_window import fit_messages_into_context_window
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
        return sum(len(str(m)) for m in messages)

    monkeypatch.setattr(
        "useagent.common.context_window.count_tokens", _fake_count_tokens
    )
    return _fake_count_tokens


def make_model_repsonse_message(txt: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=txt)])


def make_user_message(txt: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=txt)])


async def _text_with_min_tokens(min_tokens: int, seed: str = "tok") -> str:
    # Build text until its tokenization >= min_tokens
    chunks = []
    # use space-separated tokens to avoid BPE merging
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
async def test_long_messages_should_be_reduced(patch_count_tokens) -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    msg: str = "x" * 200
    messages: list[str] = [msg for _ in range(10)]
    out = await fit_messages_into_context_window(
        messages,
        safety_buffer=1.0,
        delay_between_model_calls_in_seconds=0.0,
    )
    total = await patch_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()
    assert len(out) < len(messages)


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_oversized_newest_gets_marker() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    budget = 1000
    newest_cap = int(budget * 0.60)
    second_cap = int(budget * 0.30)

    small_txt = await _text_with_min_tokens(second_cap - 20)  # under cap
    big_txt = await _text_with_min_tokens(newest_cap + 50)  # over cap

    messages = [
        make_model_repsonse_message(small_txt),
        make_model_repsonse_message(big_txt),
    ]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert len(out) == 2
    assert _has_marker(out[-1])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_newest_oversized_both_get_markers() -> None:
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
    assert _has_marker(out[-1])
    assert _has_marker(out[-2])
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_only_oldest_exceeds_window_keep_length_and_mark_only_oldest() -> None:
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
    assert _has_marker(out[0])
    for m in out[1:]:
        assert not _has_marker(m)
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_ten_messages_oversized_result_two_newest_with_markers() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    budget = 1000
    # make each message individually over the total budget
    msgs = [
        make_model_repsonse_message(await _text_with_min_tokens(budget + 100))
        for _ in range(10)
    ]

    out = await fit_messages_into_context_window(
        msgs, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) >= 2
    assert _has_marker(out[-1])
    assert _has_marker(out[-2])
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


# --- Boundary: exactly at caps -> no markers, no trimming ---


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


# --- Single message list, oversized -> kept and marked ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_message_oversized_kept_and_marked() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 200
    big = await _text_with_min_tokens(400)
    messages = [make_model_repsonse_message(big)]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) == 1
    assert _has_marker(out[0])
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


# --- Marker bigger than cap -> result becomes empty text (no marker) ---


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
    # Message retained but emptied to fit because marker cannot fit
    assert len(out) == 1
    # must not contain marker if marker itself can't fit
    assert not _has_marker(out[0])
    # content is empty
    assert getattr(out[0].parts[0], "content", None) == ""
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


# --- Second-newest over 30% cap while total < budget -> still marked ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_second_newest_marked_even_if_total_under_budget() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 2000
    budget = 2000
    newest_cap = int(budget * 0.60)
    second_cap = int(budget * 0.30)

    # keep total well under budget, but violate the 30% cap
    older = make_model_repsonse_message(await _text_with_min_tokens(50))
    second_txt = await _text_with_min_tokens(second_cap + 80)
    newest_txt = await _text_with_min_tokens(int(newest_cap * 0.5))
    messages = [
        older,
        make_model_repsonse_message(second_txt),
        make_model_repsonse_message(newest_txt),
    ]

    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) == 3
    assert _has_marker(out[-2])  # second-newest capped
    assert not _has_marker(out[-1])  # newest under its cap
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


# --- Mixed roles: user (second-newest) and assistant (newest) both oversized, both marked, types preserved ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mixed_roles_both_marked_and_types_preserved() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    budget = 1000
    newest_cap = int(budget * 0.60)
    second_cap = int(budget * 0.30)

    older = make_model_repsonse_message(await _text_with_min_tokens(60))
    second_user = make_user_message(await _text_with_min_tokens(second_cap + 120))
    newest_assistant = make_model_repsonse_message(
        await _text_with_min_tokens(newest_cap + 120)
    )
    messages = [older, second_user, newest_assistant]

    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )

    assert len(out) == 3
    # types preserved
    from pydantic_ai.messages import ModelRequest, ModelResponse

    assert isinstance(out[-2], ModelRequest)
    assert isinstance(out[-1], ModelResponse)
    # markers present
    assert _has_marker(out[-2])
    assert _has_marker(out[-1])
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


# --- Marker is inserted in the middle (prefix and suffix non-empty) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_marker_inserts_in_middle_with_prefix_and_suffix() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 500
    big = await _text_with_min_tokens(800)
    messages = [make_model_repsonse_message(big)]
    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    content = out[0].parts[0].content
    assert MARKER_TEXT in content
    prefix, _, suffix = content.partition(MARKER_TEXT)
    assert prefix != ""
    assert suffix != ""


# --- Shrink older before dropping: after capping newest two, older message is truncated (list length unchanged) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_shrink_older_before_drop_prefers_truncation_over_removal() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 800
    budget = 800
    newest_cap = int(budget * 0.60)
    second_cap = int(budget * 0.30)

    oldest = make_model_repsonse_message(await _text_with_min_tokens(500))
    second_newest = make_model_repsonse_message(
        await _text_with_min_tokens(second_cap + 150)
    )
    newest = make_model_repsonse_message(await _text_with_min_tokens(newest_cap + 150))
    messages = [oldest, make_model_repsonse_message("tiny"), second_newest, newest]

    out = await fit_messages_into_context_window(
        messages, safety_buffer=1.0, delay_between_model_calls_in_seconds=0.0
    )
    assert len(out) == len(messages)  # nothing dropped; oldest shrunk instead
    # some older message (likely index 0) should carry a marker now
    assert any(_has_marker(m) for m in out[:-2])
    total = await real_count_tokens(out)
    assert total <= ConfigSingleton.config.lookup_model_context_window()


# --- Safety buffer < 1 reduces budget; caps follow the reduced budget ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_safety_buffer_affects_caps_and_budget() -> None:
    ConfigSingleton.config.context_window_limits["openai:gpt-5-mini"] = 1000
    safety_buffer = 0.5
    effective_budget = int(1000 * safety_buffer)
    newest_cap = int(effective_budget * 0.60)
    second_cap = int(effective_budget * 0.30)

    second_txt = await _text_with_min_tokens(second_cap + 60)
    newest_txt = await _text_with_min_tokens(newest_cap + 60)
    messages = [
        make_model_repsonse_message(await _text_with_min_tokens(40)),
        make_model_repsonse_message(second_txt),
        make_model_repsonse_message(newest_txt),
    ]

    out = await fit_messages_into_context_window(
        messages, safety_buffer=safety_buffer, delay_between_model_calls_in_seconds=0.0
    )
    assert _has_marker(out[-1])
    assert _has_marker(out[-2])
    total = await real_count_tokens(out)
    assert total <= int(
        ConfigSingleton.config.lookup_model_context_window() * safety_buffer
    )
