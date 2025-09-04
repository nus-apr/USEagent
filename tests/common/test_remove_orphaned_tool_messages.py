import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from useagent.common.context_window import remove_orphaned_tool_responses


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
