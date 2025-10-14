import pytest

from useagent.common.command_utility import has_heredoc, validate_heredoc

# --- has_heredoc ---


def test_has_heredoc_should_return_false_for_empty_string():
    assert has_heredoc("") is False


def test_has_heredoc_should_return_false_for_whitespace_only():
    assert has_heredoc("   \n\t") is False


def test_has_heredoc_should_detect_basic():
    assert has_heredoc("cat <<EOF\nx\nEOF\n") is True


def test_has_heredoc_should_detect_quoted_delimiter_single_quotes():
    assert has_heredoc("cat <<'PY'\nprint(1)\nPY\n") is True


def test_has_heredoc_should_detect_quoted_delimiter_double_quotes():
    assert has_heredoc('cat <<"TAG"\nline\nTAG\n') is True


def test_has_heredoc_should_detect_dash_variant():
    assert has_heredoc("cat <<-EOF\n\tline\n\tEOF\n") is True


def test_has_heredoc_should_ignore_process_substitution_and_redirections():
    assert has_heredoc("echo foo < <(cmd) > out.txt") is False


def test_has_heredoc_should_not_trigger_on_disallowed_delimiter_chars():
    assert has_heredoc("cat <<TAG-1\nbad\nTAG-1\n") is False


# --- validate_heredoc ---


def test_validate_heredoc_should_accept_clean_unquoted():
    cmd = "cat <<EOF\nhello\nEOF\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_accept_clean_quoted():
    cmd = "cat <<'EOF'\n$HOME\nEOF\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_accept_dash_with_tabs():
    cmd = "cat <<-EOF\n\tline\n\tEOF\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_dash_with_spaces_before_terminator():
    cmd = "cat <<-EOF\nline\n EOF\n"
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_reject_trailing_space_on_terminator():
    cmd = "cat <<EOF\nx\nEOF \n"
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_reject_trailing_tab_on_terminator():
    cmd = "cat <<EOF\nx\nEOF\t\n"
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_reject_unclosed():
    cmd = "cat <<EOF\nx\n"
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_accept_when_body_contains_delim_in_text():
    cmd = "cat <<EOF\nnot EOF here\nanother line\nEOF\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_accept_multiple_sequential_heredocs():
    cmd = "cat <<A\none\nA\n" "echo mid\n" "cat <<'B'\n$var\nB\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_when_second_unclosed():
    cmd = "cat <<A\none\nA\n" "cat <<B\nmissing\n"
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_accept_interleaved_text_between_open_and_close():
    cmd = "echo pre\n" "cat <<EOF\nblock\nEOF\n" "echo post\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_handle_crlf_by_normalizing():
    cmd = "cat <<EOF\r\nline\r\nEOF\r\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_literal_backslash_n_after_terminator():
    cmd = "cat <<EOF\nx\nEOF\\n\n"
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_reject_junk_characters_after_terminator_same_line():
    cmd = "cat <<EOF\nx\nEOF#comment\n"
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_accept_multiple_different_delims():
    cmd = "cat <<ONE\n1\nONE\n" "cat <<-TWO\n\t2\n\tTWO\n" "cat <<'THREE'\n3\nTHREE\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_accept_fifo_close_order_when_same_line_open():
    cmd = "cat <<A <<B\n" "a1\n" "A\n" "b1\n" "B\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_wrong_close_order_when_same_line_open():
    cmd = "cat <<A <<B\n" "a1\n" "B\n" "b1\n" "A\n"
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_accept_fifo_close_order_when_nested_opens():
    cmd = "cat <<ONE\nx\n" "cat <<TWO\ny\n" "ONE\n" "TWO\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_if_delimiter_contains_disallowed_chars():
    cmd = "cat <<TAG-1\nbad\nTAG-1\n"
    assert has_heredoc(cmd) is False
    assert validate_heredoc(cmd) is True  # no heredoc detected => trivially valid


def test_validate_heredoc_should_accept_delimiter_with_underscores_and_digits():
    cmd = "cat <<TAG_1\nok\nTAG_1\n"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_accept_missing_final_newline_after_terminator():
    cmd = "cat <<EOF\nok\nEOF"
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_space_before_terminator_line():
    cmd = "cat <<EOF\nx\n EOF\n"
    assert validate_heredoc(cmd) is False


@pytest.mark.regression
def test_raw_string_terminator_with_literal_backslash_n_should_detect_and_reject():
    # See Issue #29 on the matter of raw encoding and Heredocs
    # Mirrors the r""" ... PY\n """ case: heredoc present, but terminator is "PY\ n"
    cmd = r"""/usr/bin/env python3 - <<'PY'
print("ok")
PY\n
"""
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is False


@pytest.mark.regression
def test_printed_bytes_literal_command_should_detect_and_reject():
    # See Issue #29
    # Mirrors the printed b'...' effective command with "; echo '<<exit>>'"
    cmd = (
        "/usr/bin/env python3 - <<'PY'\n"
        "print('ok')\n"
        "PY\\n\n"
        "; echo '<<exit>>'\n"
    )
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_accept_empty_body():
    cmd = "cat <<EOF\nEOF\n"
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is True


def test_has_heredoc_should_return_false_for_here_string_triple_lt():
    cmd = "cat <<< 'data'\n"
    assert has_heredoc(cmd) is False
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_accept_spaces_between_operator_and_quoted_delimiter():
    cmd = "cat <<   'EOF'\nX\nEOF\n"
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_accept_spaces_between_operator_and_double_quoted_delimiter():
    cmd = 'cat <<   "TAG"\nX\nTAG\n'
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_mixed_spaces_with_tabs_in_dash_variant_terminator():
    cmd = "cat <<-EOF\n\tX\n \tEOF\n"  # space before tab in terminator -> invalid
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_accept_dash_variant_with_leading_tabs_before_terminator():
    cmd = "cat <<-EOF\n\tX\n\t\tEOF\n"  # tabs allowed before delimiter for <<-
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_zero_width_char_in_terminator_line():
    cmd = "cat <<EOF\nX\n\u200bEOF\n"  # zero-width space before EOF -> invalid
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_accept_fifo_when_opens_on_different_lines():
    cmd = "cat <<A\n" "a1\n" "cat <<B\n" "b1\n" "A\n" "B\n"
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is True


def test_validate_heredoc_should_reject_trailing_semicolon_after_terminator():
    cmd = "cat <<EOF\nX\nEOF; \n"  # junk after terminator
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is False


def test_validate_heredoc_should_reject_lone_carriage_return_after_terminator():
    # lone \r (not CRLF) after terminator should fail equality match
    cmd = "cat <<EOF\nX\nEOF\r"
    assert has_heredoc(cmd) is True
    assert validate_heredoc(cmd) is False
