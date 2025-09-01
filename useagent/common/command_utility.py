# heredoc_utils.py

from __future__ import annotations

import re

_HERE_OPEN_RE = re.compile(
    r"(?<!<)<<(?P<dash>-)?\s*(?P<q>['\"]?)(?P<delim>[A-Za-z0-9_]+)(?P=q)(?=\s|$)"
)


def has_heredoc(cmd: str) -> bool:
    s = cmd.replace("\r\n", "\n")
    return _HERE_OPEN_RE.search(s) is not None


def validate_heredoc(cmd: str) -> bool:
    s = cmd.replace("\r\n", "\n")
    opens: list[tuple[int, str, bool]] = []
    for m in _HERE_OPEN_RE.finditer(s):
        line_idx = s.count("\n", 0, m.start())
        delim = m.group("delim")
        allow_tabs = bool(m.group("dash"))
        opens.append((line_idx, delim, allow_tabs))
    if not opens:
        return True

    lines = s.splitlines(keepends=True)
    pending: list[tuple[int, str, bool]] = []
    i_open = 0

    for idx, line in enumerate(lines):
        # queue openings seen before this line (FIFO)
        while i_open < len(opens) and opens[i_open][0] < idx:
            pending.append(opens[i_open])
            i_open += 1

        if not pending:
            continue

        open_line, delim, allow_tabs = pending[0]
        stripped_line = (
            line[:-1] if line.endswith("\n") else line
        )  # strip trailing NL only

        if allow_tabs:
            # <<- allows leading TABS only
            if re.fullmatch(r"\t*" + re.escape(delim), stripped_line):
                pending.pop(0)
        else:
            # exact delimiter, no spaces/tabs/comments
            if stripped_line == delim:
                pending.pop(0)

    # add any openings that occur after the last processed line -> unclosed
    while i_open < len(opens):
        pending.append(opens[i_open])
        i_open += 1

    return len(pending) == 0
