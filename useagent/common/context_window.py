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
from sentencepiece import SentencePieceProcessor
from tiktoken import Encoding

from useagent.config import ConfigSingleton

GEMMA_3_TOKENIZER_PATH = (
    Path(__file__).parent / "tokenizers" / "gemma-3-4b-it"
).absolute()


def fit_message_into_context_window(content: str) -> str:
    """
    Looks up the models context window, and if applicable load the right encoding to shorten the content within the content window.

    Does nothing if either the model is not known or the model window is not exceeded.
    """
    if ConfigSingleton.is_initialized() and (
        context_limit := ConfigSingleton.config.lookup_model_context_window() > 0
    ):
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
    safety_buffer: float = 0.9,
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
            # TODO: add real support for ChatGPT
            logger.warning("CHATGPT Context Windows are currently not Supported [TODO]")
            return content
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
    encoder = tiktoken.encoding_for_model(model_descriptor)
    if encoder:
        return encoder
    return tiktoken.encoding_for_model("gpt-4o")
