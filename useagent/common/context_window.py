"""
This file covers the fact that some messages and content need to be fit / cut into a context window limit.
This requires first a tokenization, as context limits are set for tokens (and not for string).
Different models need different tokenizers, but for now we have two larger tribes:

- TikToken, for OpenAI Models
- Sentenpiece (through Huggingface Transformers) for Google Models (gemini + gemma)
- Model-API (all-but OpenAI)

We have seen issues for some bash output, see Issue #30
"""

import json
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

import sentencepiece as spm
import tiktoken
from loguru import logger
from pydantic_ai.messages import (
    BaseToolCallPart,
    BaseToolReturnPart,
    BinaryContent,
    FileUrl,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolReturnPart,
    UserContent,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from sentencepiece import SentencePieceProcessor
from tiktoken import Encoding

from useagent.config import ConfigSingleton

GEMMA_3_TOKENIZER_PATH = (
    Path(__file__).parent / "tokenizers" / "gemma-3-4b-it"
).absolute()


async def fit_messages_into_context_window(
    messages: list[ModelMessage],
    safety_buffer: float = 0.85,
    delay_between_model_calls_in_seconds: float = 0.25,
) -> list[ModelMessage]:
    # DevNote - Current Logic:
    # We cut the first message to be at most 60% of our Budget
    # Second message can be at most 30% of our budget
    # If these cuts do not yield to a fitting context window, we discard the oldest messages until the result fits.
    if not ConfigSingleton.is_initialized() or not ConfigSingleton.config.model:
        logger.warning(
            f"[Support] Tried to shrink a list of {len(messages)} messages into context window, but ConfigSingleton was not initialzied or model not available"
        )
        return messages

    context_limit: int = ConfigSingleton.config.lookup_model_context_window()
    budget: int = int(context_limit * safety_buffer)
    if await count_tokens(messages) <= budget:
        # Messages are short, do nothing
        return messages

    newest_cap: int = int(budget * 0.60)
    second_cap: int = int(budget * 0.30)

    capped = await _apply_per_turn_caps(messages, newest_cap, second_cap)

    total_after_caps = await count_tokens(capped)
    if total_after_caps <= budget:
        out = capped
    else:
        shrunk = await _shrink_from_oldest_to_budget(capped, budget)
        if await count_tokens(shrunk) <= budget:
            out = shrunk
        else:
            out = await _trim_oldest_until_in_budget(
                shrunk, budget, delay_between_model_calls_in_seconds
            )

    if len(messages) != len(out):
        logger.debug(
            f"[Support] Shrank a list of {len(messages)} messages to a list of {len(out)} to fit into a context window of {context_limit}"
        )

    # DevNote: See Issue 30 - Tools must be in pairs of call-->response, and our cutting can leave orphaned responses. We just kick out orphans too, to have a simple solution.
    out = remove_orphaned_tool_responses(out)

    current = await count_tokens(out)
    if current > budget:
        if out:
            # Keep only the newest message and force-fit it.
            newest = out[-1]
            out = await _force_fit_single(newest, budget)
        else:
            # If we somehow ended empty, try force-fitting the newest from capped.
            if capped:
                newest = capped[-1]
                out = await _force_fit_single(newest, budget)

    if messages and not out:
        try:
            logger.warning(
                "[Support] Shrinking tools remained impossible after removing orphans - trying to salvage the newest three messages into context window."
            )
            out = await _salvage_most_recent_triplet(
                original_messages=messages, safety_buffer=safety_buffer
            )
        except Exception:
            logger.error(
                "[Support] It was impossible to salvage the last three messages, replacing message history with a dummy."
            )
            out = [_make_context_pruned_notice()]

    return out


def remove_orphaned_tool_responses(messages: list[ModelMessage]) -> list[ModelMessage]:
    seen_calls: set[str] = set()
    out: list[ModelMessage] = []

    for m in messages:
        if isinstance(m, ModelResponse):
            for p in getattr(m, "parts", []) or []:
                if isinstance(p, BaseToolCallPart):
                    seen_calls.add(p.tool_call_id)
            out.append(m)
            continue

        if isinstance(m, ModelRequest):
            parts = []
            has_tool_return = False
            kept_any_tool_return = False
            for p in getattr(m, "parts", []) or []:
                if isinstance(p, ToolReturnPart):
                    has_tool_return = True
                    if p.tool_call_id in seen_calls:
                        parts.append(p)
                        kept_any_tool_return = True
                    # else: drop orphaned return
                else:
                    parts.append(p)

            if has_tool_return and not kept_any_tool_return:
                # message was only orphaned tool returns -> drop entire message
                if parts:
                    # if non-tool-return parts remain, keep them
                    out.append(ModelRequest(parts=parts))
                continue

            out.append(ModelRequest(parts=parts))
            continue

        out.append(m)
    return out


def _is_tool_return_message(m: ModelMessage) -> bool:
    """True if the message contains ToolReturnPart(s) and no assistant tool-call parts.
    Used to avoid selecting a lone tool-return as the only survivor."""
    if not isinstance(m, ModelRequest):
        return False
    parts = getattr(m, "parts", []) or []
    has_return = any(isinstance(p, ToolReturnPart) for p in parts)
    # Treat as "tool-return message" if it has returns (regardless of other user parts),
    # since keeping it alone would re-orphan those returns.
    return has_return


async def _force_fit_single(msg: ModelMessage, cap: int) -> list[ModelMessage]:
    if isinstance(msg, ModelRequest):
        parts = getattr(msg, "parts", []) or []
        if any(isinstance(p, ToolReturnPart) for p in parts):
            kept = [p for p in parts if not isinstance(p, ToolReturnPart)]
            if kept:
                msg = ModelRequest(parts=kept)
            else:
                # lone orphan: keep a placeholder request so we don't re-orphan and drop it
                return [ModelRequest(parts=[])]
    fitted = await _truncate_message_to_cap(msg, cap)
    return [fitted]


async def count_tokens(
    messages: list[ModelMessage],
) -> int:
    """
    Counts the tokens of a given list, using the Pydantic and Model API.
    This means this function only works online !

    It will also incurr costs, but not too much compared to normal inference.

    Returns the token count, or -1 on miss-initialization.
    """
    if not ConfigSingleton.is_initialized() or not ConfigSingleton.config.model:
        return -1
    model = ConfigSingleton.config.model
    if isinstance(model, OpenAIResponsesModel) or isinstance(model, OpenAIChatModel):
        return _count_openai_tokens(messages=messages)
    else:
        usage = await model.count_tokens(
            messages=messages,
            model_settings=None,
            model_request_parameters=ModelRequestParameters(),
        )
        return usage.total_tokens


# --- helpers ---
MARKER_TEXT = "[[ cut for context size ]]"


def _make_same_kind_text_message_like(orig: ModelMessage, text: str) -> ModelMessage:
    if isinstance(orig, ModelRequest):
        return ModelRequest(parts=[UserPromptPart(content=text)])
    return ModelResponse(parts=[TextPart(content=text)])


def _msg_set_text(m: ModelMessage, text: str) -> ModelMessage:
    return _make_same_kind_text_message_like(m, text)


def _msg_get_text(m: ModelMessage) -> str:
    parts = list(_iter_parts([m]))
    return "\n".join(p for p in parts if p)


async def _truncate_message_to_cap(m: ModelMessage, token_cap: int) -> ModelMessage:
    if token_cap <= 0:
        return _msg_set_text(m, "")
    if await count_tokens([m]) <= token_cap:
        return m

    marker_msg = _make_same_kind_text_message_like(m, MARKER_TEXT)
    if await count_tokens([marker_msg]) > token_cap:
        return _msg_set_text(m, "")

    txt = _msg_get_text(m)
    lo, hi = 0, len(txt) // 2
    best_text = MARKER_TEXT  # always at least the marker

    while lo <= hi:
        k = (lo + hi) // 2
        cand_text = f"{txt[:k]}{MARKER_TEXT}{txt[-k:]}" if k > 0 else MARKER_TEXT
        cand_msg = _make_same_kind_text_message_like(m, cand_text)
        t = await count_tokens([cand_msg])
        if t <= token_cap:
            best_text = cand_text
            lo = k + 1
        else:
            hi = k - 1

    return _msg_set_text(m, best_text)


async def _cap_message(msg: ModelMessage, token_cap: int) -> ModelMessage:
    """Cap a single message to token_cap, preserving tool return structure when present."""
    if isinstance(msg, ModelRequest) and any(
        isinstance(p, ToolReturnPart) for p in getattr(msg, "parts", []) or []
    ):
        return await _truncate_tool_return_message(msg, token_cap)
    return await _truncate_message_to_cap(msg, token_cap)


async def _apply_per_turn_caps(
    messages: list[ModelMessage],
    newest_cap: int,
    second_newest_cap: int,
) -> list[ModelMessage]:
    if not messages:
        return messages
    out = list(messages)
    out[-1] = await _cap_message(out[-1], newest_cap)
    if len(out) >= 2:
        out[-2] = await _cap_message(out[-2], second_newest_cap)
    return out


async def _trim_oldest_until_in_budget(
    messages: list[ModelMessage],
    budget_tokens: int,
    delay_between_model_calls_in_seconds: float,
) -> list[ModelMessage]:
    """
    Drops the OLDEST SINGLE message at a time until within budget, and force-fits the last survivor if needed.
    """
    running = list(messages)
    tokens = await count_tokens(running)

    while tokens > budget_tokens and running:
        if len(running) == 1:
            # Single survivor – force-fit instead of dropping to []
            fitted = await _force_fit_single(running[0], budget_tokens)
            running = fitted if fitted else []
            break

        # Drop the OLDEST single message (index 0)
        running = running[1:]

        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles.get(
                "bash-tool-speed-bumper", False
            )
        ):
            time.sleep(delay_between_model_calls_in_seconds)

        tokens = await count_tokens(running)

    return running


def _flatten_user_content(content: str | Sequence[UserContent]) -> str:
    if isinstance(content, str):
        return content
    out: list[str] = []
    for c in content:
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, FileUrl):
            out.append(c.url)
        elif isinstance(c, BinaryContent):
            out.append(c.identifier or "<binary>")
        else:
            out.append(str(c))
    return "\n".join(out)


def _part_to_text(part: object) -> str:
    if isinstance(part, SystemPromptPart):
        return part.content
    if isinstance(part, UserPromptPart):
        return _flatten_user_content(part.content)
    if isinstance(part, RetryPromptPart):
        return str(part.content)
    if isinstance(part, ToolReturnPart):
        return part.model_response_str()
    if isinstance(part, BaseToolReturnPart):
        return str(part.content)
    if isinstance(part, TextPart):
        return part.content
    if isinstance(part, ThinkingPart):
        return part.content or ""
    if isinstance(part, BaseToolCallPart):
        # include tool name + args text for a conservative estimate
        try:
            return f"{part.tool_name}({json.dumps(part.args)})"
        except Exception:
            return f"{part.tool_name}"
    # Unknown part type: best-effort string
    return getattr(part, "content", "") if hasattr(part, "content") else str(part)


def _iter_parts(messages: Iterable[ModelMessage]) -> Iterable[str]:
    for m in messages:
        if isinstance(m, (ModelRequest, ModelResponse)):
            for p in m.parts:
                yield _part_to_text(p)
        else:
            # Defensive: try generic access
            for p in getattr(m, "parts", []) or []:
                yield _part_to_text(p)


def _encoding_for(model_name: str) -> tiktoken.Encoding:
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        return tiktoken.get_encoding("o200k_base")


def _with_tool_return_text(p: ToolReturnPart, text: str) -> ToolReturnPart:
    # Rebuild the part with the same identity, new content
    return ToolReturnPart(
        tool_name=p.tool_name, tool_call_id=p.tool_call_id, content=text
    )


def _tool_return_text(p: ToolReturnPart) -> str:
    try:
        return p.model_response_str()
    except Exception:
        return getattr(p, "content", "") or ""


async def _truncate_tool_return_message(
    m: ModelMessage, token_cap: int
) -> ModelMessage:
    """
    Shrink *only* ToolReturnPart contents inside a ModelRequest ('tool' message),
    keeping role and tool_call_id intact.
    """
    if not isinstance(m, ModelRequest):
        return m

    # Collect tool-return parts
    parts = list(getattr(m, "parts", []) or [])
    ret_idx: list[int] = []
    ret_texts: list[str] = []
    for i, p in enumerate(parts):
        if isinstance(p, ToolReturnPart):
            ret_idx.append(i)
            ret_texts.append(_tool_return_text(p))

    if not ret_idx:
        # Nothing tool-return-like to shrink
        return m

    if token_cap <= 0:
        # Keep structure, empty the return contents
        new_parts = parts[:]
        for pos in ret_idx:
            new_parts[pos] = _with_tool_return_text(new_parts[pos], "")
        return ModelRequest(parts=new_parts)

    # Fast path: already within cap
    if await count_tokens([m]) <= token_cap:
        return m

    # Try with markers using a shared head/tail crop across all return parts
    lo, hi = 0, max((len(t) for t in ret_texts), default=0) // 2
    best_parts: list | None = None

    def crop(s: str, k: int) -> str:
        return f"{s[:k]}{MARKER_TEXT}{s[-k:]}" if k > 0 else MARKER_TEXT

    while lo <= hi:
        k = (lo + hi) // 2
        trial = parts[:]
        for pos, txt in zip(ret_idx, ret_texts):
            trial[pos] = _with_tool_return_text(trial[pos], crop(txt, k))
        trial_msg = ModelRequest(parts=trial)
        t = await count_tokens([trial_msg])
        if t <= token_cap:
            best_parts = trial
            lo = k + 1
        else:
            hi = k - 1

    if best_parts is None:
        # If even pure markers don't fit, empty contents
        best_parts = parts[:]
        for pos in ret_idx:
            best_parts[pos] = _with_tool_return_text(best_parts[pos], "")

    return ModelRequest(parts=best_parts)


def _count_openai_tokens(
    messages: list[ModelMessage], model_name: str = "gpt-4o"
) -> int:
    enc = _encoding_for(model_name)
    total: int = 0
    # Join parts with separators to approximate message/part boundaries
    for text in _iter_parts(messages):
        if not text:
            continue
        total += len(enc.encode(text))
        total += 3  # small delimiter fudge per part
    return total


async def _salvage_most_recent_triplet(
    original_messages: list[ModelMessage],
    safety_buffer: float,
) -> list[ModelMessage]:
    if not ConfigSingleton.is_initialized() or not ConfigSingleton.config.model:
        raise ValueError("Config/model not initialized")
    context_limit: int = ConfigSingleton.config.lookup_model_context_window()
    budget: int = int(context_limit * safety_buffer)

    # newest 3, preserving order
    triplet: list[ModelMessage] = original_messages[-3:]
    triplet = remove_orphaned_tool_responses(triplet)

    if not triplet:
        raise ValueError("Context salvage failed: 0 messages after orphan removal")

    # caps: third-newest=10%, second-newest=25%, newest=50%
    third_cap: int = int(budget * 0.10)
    second_cap: int = int(budget * 0.25)
    newest_cap: int = int(budget * 0.50)

    capped: list[ModelMessage] = []
    n = len(triplet)
    for idx, m in enumerate(triplet):
        # map positions to caps
        if n == 1:
            cap = newest_cap
        elif n == 2:
            cap = second_cap if idx == 0 else newest_cap
        else:
            cap = third_cap if idx == 0 else (second_cap if idx == 1 else newest_cap)

        if isinstance(m, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or []
        ):
            capped_msg = await _truncate_tool_return_message(m, cap)
        else:
            capped_msg = await _truncate_message_to_cap(m, cap)
        capped.append(capped_msg)

    capped = remove_orphaned_tool_responses(capped)

    if not capped:
        raise ValueError("Context salvage failed: 0 messages after truncation")

    return capped


async def _shrink_from_oldest_to_budget(
    messages: list[ModelMessage],
    budget_tokens: int,
) -> list[ModelMessage]:
    if not messages:
        return messages

    out = list(messages)
    total = await count_tokens(out)
    if total <= budget_tokens:
        return out

    # Greedily truncate from oldest toward newest
    for i in range(len(out)):
        total = await count_tokens(out)
        if total <= budget_tokens:
            break
        # compute cap for this message given others fixed
        others = out[:i] + out[i + 1 :]
        other_tokens = await count_tokens(others)
        cap_for_this = max(0, budget_tokens - other_tokens)

        m = out[i]
        if isinstance(m, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in getattr(m, "parts", []) or []
        ):
            out[i] = await _truncate_tool_return_message(m, cap_for_this)
        else:
            out[i] = await _truncate_message_to_cap(m, cap_for_this)

    # If still over budget and only one message remains, force-fit that one
    if out and (await count_tokens(out)) > budget_tokens and len(out) == 1:
        only = out[0]
        cap = max(0, budget_tokens)
        if isinstance(only, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in getattr(only, "parts", []) or []
        ):
            out[0] = await _truncate_tool_return_message(only, cap)
        else:
            out[0] = await _truncate_message_to_cap(only, cap)

    return out


_FALLBACK_NOTICE: str = (
    "Conversation history was pruned because it exceeded the model's context window. "
    "Only this notice is kept so the chat can continue."
)


def _make_context_pruned_notice() -> ModelMessage:
    """Create a single assistant message explaining that history was dropped."""
    return ModelResponse(parts=[TextPart(content=_FALLBACK_NOTICE)])


# TODO: Deprecate this properly in favour of using the API
def fit_message_into_context_window(content: str, safety_buffer: float = 0.75) -> str:
    """
    Looks up the models context window, and if applicable load the right encoding to shorten the content within the content window.

    Does nothing if either the model is not known or the model window is not exceeded.
    """
    if not content or not isinstance(content, str):
        return content

    if (
        ConfigSingleton.is_initialized()
        and ConfigSingleton.config.lookup_model_context_window() > 0
    ):
        context_limit = ConfigSingleton.config.lookup_model_context_window()
        model_name = ConfigSingleton.config.model_descriptor
        if "google" in model_name or "gemini" in model_name:
            return _fit_message_into_context_window(
                content,
                _lookup_tokenizer_for_google_models(model_name),
                context_limit,
                safety_buffer=safety_buffer,
            )
        else:
            return _fit_message_into_context_window(
                content,
                _lookup_tiktoken_encoding(model_name),
                context_limit,
                safety_buffer=safety_buffer,
            )
    else:
        # Model unknown / unsupported, just do nothing.
        return content


def _fit_message_into_context_window(
    content: str,
    tokenizer: SentencePieceProcessor | Encoding,
    max_tokens: int = -1,
    safety_buffer: float = 0.75,
) -> str:
    # separate method to allow for unit testing without ConfigSingleton and side-effect free behaviour.
    # Default Strategy: Remove content in the Middle.
    effective_max_length: int = int(max_tokens * safety_buffer)
    if effective_max_length < 1:
        return content
    marker: str = "\n[[ ... Cut to fit Context Window ... ]]\n"

    match tokenizer:
        case SentencePieceProcessor():
            ids = tokenizer.encode(content)  # type: ignore[attr-defined]
            if len(ids) <= effective_max_length:
                # Short enough - do nothing and return
                return content

            marker_ids = tokenizer.encode(marker)  # type: ignore[attr-defined]
            keep = max_tokens - len(marker_ids)
            half = keep // 2

            beginning = ids[:half]
            end = ids[-(keep - half) :]
            cut_ids = beginning + marker_ids + end
            return tokenizer.decode(cut_ids)  # type: ignore[attr-defined]
        case Encoding():
            ids = tokenizer.encode(content)
            if len(ids) <= effective_max_length:
                return content

            marker_ids = tokenizer.encode(marker)
            keep = max_tokens - len(marker_ids)
            half = keep // 2

            beginning = ids[:half]
            end = ids[-(keep - half) :]
            cut_ids = beginning + marker_ids + end
            return tokenizer.decode(cut_ids)
        case _:
            logger.warning(
                "Tried to tokenize but received an unsupported Tokenizer - returning initial content."
            )
            return content


def _lookup_tokenizer_for_google_models(
    model_descriptor: str,
) -> SentencePieceProcessor:
    # A quick search said Google uses the same `SentencePiece` Tokenizer for its models, which is a pretrained tokenizer that is hosted on hugging face.
    # https://huggingface.co/google/gemma-3-4b-it
    # TODO: Shall we have a different lookup? Are there other models to use here?
    sp = spm.SentencePieceProcessor()
    sp.load(str(GEMMA_3_TOKENIZER_PATH / "tokenizer.model"))  # type: ignore[attr-defined]
    return sp


def _lookup_tiktoken_encoding(model_descriptor: str) -> Encoding:
    # See Tiktokens Github Repository: https://github.com/openai/tiktoken
    # And particularly their Encoding Lookup: https://github.com/openai/tiktoken/blob/main/tiktoken/model.py
    try:
        _model_descriptor: str = (
            model_descriptor[len("openai:") :]
            if model_descriptor.startswith("openai:")
            else model_descriptor
        )
        # TODO: Better lookup here, our model names will likely not match
        encoder = tiktoken.encoding_for_model(_model_descriptor)

    except KeyError:
        logger.debug(
            f"Tried to lookup encoding for {model_descriptor}, failed and default to o200k_base"
        )
        return tiktoken.get_encoding(
            "o200k_base"
        )  # GPT4 and 5 have o200k_base, it's the most common
    else:
        return encoder
