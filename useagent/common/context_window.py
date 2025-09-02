"""
This file covers the fact that some messages and content need to be fit / cut into a context window limit.
This requires first a tokenization, as context limits are set for tokens (and not for string).
Different models need different tokenizers, but for now we have two larger tribes:

- TikToken, for OpenAI Models
- Sentenpiece (through Huggingface Transformers) for Google Models (gemini + gemma)

We have seen issues for some bash output, see Issue #30
"""

from pathlib import Path

import sentencepiece as spm
import tiktoken
from loguru import logger
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import ModelRequestParameters
from sentencepiece import SentencePieceProcessor
from tiktoken import Encoding

from useagent.config import ConfigSingleton

GEMMA_3_TOKENIZER_PATH = (
    Path(__file__).parent / "tokenizers" / "gemma-3-4b-it"
).absolute()


async def fit_messages_into_context_window(
    messages: list[ModelMessage], safety_buffer: float = 0.85
) -> list[ModelMessage]:
    """
    Tries to reduce messages into the context window, using the model and the context window provided in the ConfigSingleton.
    This needs a internet connection, as well as a valid token to work, as it actually calls the API.
    """
    # DevNote: I am not super duper happy about this, but at least we are 100% its the same behaviour as if we use the API in our runs.
    if not ConfigSingleton.is_initialized() or not ConfigSingleton.config.model:
        logger.warning(
            "[Support] Tried to shrink a list of {len(messages)} messages into context window, but ConfigSingleton was not initialzied or model not available"
        )
        return messages
    context_limit: int = ConfigSingleton.config.lookup_model_context_window()
    running_messages: list[ModelMessage] = messages
    running_context_tokens: int = await count_tokens(running_messages)
    while running_context_tokens > 0 and running_context_tokens >= (
        context_limit * safety_buffer
    ):
        # We need / should always remove two, to remove pairs of request / answer and not have dangling things.
        running_messages = running_messages[2:]
        running_context_tokens = await count_tokens(running_messages)
    if len(messages) != len(running_messages):
        logger.debug(
            f"[Support] Shrank a list of {len(messages)} messages to a list of {len(running_messages)} to fit into a context window of {context_limit}"
        )
    return running_messages


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
    usage = await model.count_tokens(
        messages=messages,
        model_settings=None,
        model_request_parameters=ModelRequestParameters(),
    )
    return usage.total_tokens


# TODO: Deprecate this properly in favour of using the API
def fit_message_into_context_window(content: str) -> str:
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
                content, _lookup_tokenizer_for_google_models(model_name), context_limit
            )
        else:
            return _fit_message_into_context_window(
                content, _lookup_tiktoken_encoding(model_name), context_limit
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
