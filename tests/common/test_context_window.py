import pytest
from sentencepiece import SentencePieceProcessor

from useagent.common.context_window import (
    _fit_message_into_context_window,
    _lookup_tokenizer_for_google_models,
)
from useagent.config import ConfigSingleton


@pytest.fixture(autouse=True)
def reset_config():
    ConfigSingleton.reset()
    yield
    ConfigSingleton.reset()


# We know that google-gla:gemini-2.5-flash has a Context Limit of 1048576 tokens


# Helpers
def _token_len(tokenizer: SentencePieceProcessor, text: str) -> int:
    return len(tokenizer.encode(text))


@pytest.fixture(scope="module")
def spm_tokenizer() -> SentencePieceProcessor:
    tok = _lookup_tokenizer_for_google_models("google-gla:gemini-2.5-flash ")
    assert isinstance(tok, SentencePieceProcessor)
    return tok


def test_lookup_tokenizer_for_known_google_gemini_25():
    tokenizer = _lookup_tokenizer_for_google_models("google-gla:gemini-2.5-flash ")
    assert tokenizer
    assert isinstance(tokenizer, SentencePieceProcessor)


def test_lookup_tokenizer_for_known_google_gemini_20():
    tokenizer = _lookup_tokenizer_for_google_models("google-gla:gemini-2.0-flash ")
    assert tokenizer
    assert isinstance(tokenizer, SentencePieceProcessor)


def test_fit_into_context_window_with_a_supported_model_short_message_should_be_kept():
    tokenizer = _lookup_tokenizer_for_google_models("google-gla:gemini-2.5-flash ")
    message = "Hello World"
    result = _fit_message_into_context_window(
        message, tokenizer, max_tokens=1000, safety_buffer=0.9
    )

    assert result
    assert result == message


def test_message_exceeding_max_tokens_should_contain_marker(
    spm_tokenizer: SentencePieceProcessor,
):
    msg = "lorem ipsum " * 500
    res = _fit_message_into_context_window(
        msg, spm_tokenizer, max_tokens=200, safety_buffer=0.9
    )
    assert "[[ ... Cut to fit Context Window ... ]]" in res


def test_message_exceeding_max_tokens_should_be_shorter(
    spm_tokenizer: SentencePieceProcessor,
):
    msg = "lorem ipsum " * 500
    res = _fit_message_into_context_window(
        msg, spm_tokenizer, max_tokens=200, safety_buffer=0.9
    )
    assert len(res) < len(msg)


def test_safety_buffer_should_influence_cut(spm_tokenizer: SentencePieceProcessor):
    # Choose a size where: 0.5*max < tokens(msg) <= 0.9*max
    base = "alpha beta gamma delta " * 120
    tokens = _token_len(spm_tokenizer, base)
    max_tokens = (
        tokens + 30
    )  # slightly above current length, so it will not be affected.
    keep_relaxed = _fit_message_into_context_window(
        base, spm_tokenizer, max_tokens=max_tokens, safety_buffer=0.95
    )
    keep_aggressive = _fit_message_into_context_window(
        base, spm_tokenizer, max_tokens=max_tokens, safety_buffer=0.5
    )
    assert keep_relaxed == base
    assert "[[ ... Cut to fit Context Window ... ]]" in keep_aggressive


def test_below_max_but_above_effective_should_trim(
    spm_tokenizer: SentencePieceProcessor,
):
    msg = "zeta eta theta iota kappa " * 200
    n = _token_len(spm_tokenizer, msg)
    max_tokens = n + 50  # below hard cap
    safety_buffer = 0.8  # effective threshold below n
    res = _fit_message_into_context_window(
        msg, spm_tokenizer, max_tokens=max_tokens, safety_buffer=safety_buffer
    )
    assert "[[ ... Cut to fit Context Window ... ]]" in res
    assert _token_len(spm_tokenizer, res) <= max_tokens


@pytest.mark.parametrize("text", ["", "\t", "\n", "    "])
def test_empty_strings_should_roundtrip(
    text: str, spm_tokenizer: SentencePieceProcessor
):
    res = _fit_message_into_context_window(
        text, spm_tokenizer, max_tokens=100, safety_buffer=0.9
    )
    assert res == text


def test_at_limit_with_full_buffer_should_not_shorten(
    spm_tokenizer: SentencePieceProcessor,
):
    msg = ("abcd " * 2000).strip()
    n = _token_len(spm_tokenizer, msg)
    res = _fit_message_into_context_window(
        msg, spm_tokenizer, max_tokens=n, safety_buffer=1.0
    )
    assert res == msg


def test_zero_buffer_should_leave_message_unfiltered(
    spm_tokenizer: SentencePieceProcessor,
):
    msg = "some long text " * 1000
    res = _fit_message_into_context_window(
        msg, spm_tokenizer, max_tokens=100, safety_buffer=0.0
    )
    assert res == msg


def test_max_tokens_minus_one_should_leave_message_unfiltered(
    spm_tokenizer: SentencePieceProcessor,
):
    msg = "any content " * 500
    res = _fit_message_into_context_window(
        msg, spm_tokenizer, max_tokens=-1, safety_buffer=0.9
    )
    assert res == msg


def test_max_tokens_zero_should_leave_message_unfiltered(
    spm_tokenizer: SentencePieceProcessor,
):
    msg = "any content " * 500
    res = _fit_message_into_context_window(
        msg, spm_tokenizer, max_tokens=0, safety_buffer=0.9
    )
    assert res == msg
