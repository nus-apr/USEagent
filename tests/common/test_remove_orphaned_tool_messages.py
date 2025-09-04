# tests/test_remove_orphaned_tool_responses.py
import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
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


@pytest.mark.asyncio
async def test_remove_orphaned_should_drop_leading_and_middle() -> None:
    orphan1 = _tool_return_msg("call_a")
    mid_text = _text_resp("hello")
    orphan2 = _tool_return_msg("call_b")
    kept_tail = _tool_call_msg("call_c")  # no return present, fine
    msgs = [orphan1, mid_text, orphan2, kept_tail]

    out = remove_orphaned_tool_responses(msgs)

    assert out == [mid_text, kept_tail]
    # no tool returns remain
    assert all(
        not any(isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or [])
        for m in out
    )


@pytest.mark.asyncio
async def test_remove_orphaned_should_keep_returns_with_prior_calls() -> None:
    call = _tool_call_msg("call_x")
    ret = _tool_return_msg("call_x", "value")
    msgs = [call, ret]

    out = remove_orphaned_tool_responses(msgs)

    assert out == msgs  # intact pair
    # return preserved because matching call appeared earlier
    assert any(isinstance(p, ToolReturnPart) for p in out[1].parts)


@pytest.mark.asyncio
async def test_remove_orphaned_should_strip_message_if_only_orphan_parts() -> None:
    orphan_only = _tool_return_msg("nope")
    mixed = ModelRequest(
        parts=[
            ToolReturnPart(tool_name="dummy", tool_call_id="ghost", content="x"),
            TextPart(content="keep me"),
        ]
    )
    msgs = [orphan_only, mixed]

    out = remove_orphaned_tool_responses(msgs)

    # first message dropped entirely; second had orphan part removed but text kept
    assert len(out) == 1
    assert isinstance(out[0], ModelRequest)
    assert all(not isinstance(p, ToolReturnPart) for p in out[0].parts)
    assert any(isinstance(p, TextPart) for p in out[0].parts)
