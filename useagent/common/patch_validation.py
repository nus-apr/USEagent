import re
import shutil
import subprocess
import tempfile

from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

DIFF_HEADER_RE = re.compile(r"^diff --git a/.+ b/.+", re.MULTILINE)
FILE_HEADER_RE = re.compile(r"^(---|\+\+\+) ", re.MULTILINE)
MODE_CHANGE_RE = re.compile(r"^(old mode|new mode) \d{6}", re.MULTILINE)
RENAME_RE = re.compile(r"^(rename|copy) (from|to) ", re.MULTILINE)
NEW_OR_DEL_FILE_RE = re.compile(
    r"^(new file mode|deleted file mode) \d{6}", re.MULTILINE
)
SIMILARITY_RE = re.compile(r"^similarity index \d+%", re.MULTILINE)

HUNK_HEADER_RE = re.compile(
    r"""^@@\s-(\d+)(,\d+)?\s\+(\d+)(,\d+)?\s@@(?:\s.*)?$""",
    re.MULTILINE | re.VERBOSE,
)
HUNK_BODY_LINE_RE = re.compile(r"^[ +-]|^\\ No newline at end of file$")


def _split_files(content: str) -> list[tuple[int, str]]:
    starts = [m.start() for m in DIFF_HEADER_RE.finditer(content)]
    if not starts:
        return []
    starts.append(len(content))
    out: list[tuple[int, str]] = []
    for i in range(len(starts) - 1):
        s, e = starts[i], starts[i + 1]
        lno = content.count("\n", 0, s) + 1
        out.append((lno, content[s:e]))
    return out


def _block_is_header_only(block: str) -> bool:
    return any(
        r.search(block)
        for r in (MODE_CHANGE_RE, RENAME_RE, NEW_OR_DEL_FILE_RE, SIMILARITY_RE)
    )


def _validate_file_headers(block: str, base_lno: int, errors: list[str]) -> None:
    minus = re.search(r"^---\s", block, re.MULTILINE)
    plus = re.search(r"^\+\+\+\s", block, re.MULTILINE)
    if bool(minus) ^ bool(plus):
        element = minus or plus
        if not element:
            return
        pos = element.start()
        lno = base_lno + block.count("\n", 0, pos)
        errors.append(f"Unpaired file header (---/+++) near line {lno}")
    elif not minus and not plus and not _block_is_header_only(block):
        errors.append(
            f"Missing file headers (---/+++) in block starting at line {base_lno}"
        )


HUNK_BODY_LINE_RE = re.compile(r"^[ +-]|^\\ No newline at end of file$")

INDEX_LINE_RE = re.compile(r"^index ([0-9a-f]+)\.\.([0-9a-f]+)", re.MULTILINE)


def _has_create_or_delete(block: str) -> bool:
    return bool(RENAME_RE.search(block) or NEW_OR_DEL_FILE_RE.search(block))


def _validate_index_line(block: str, base_lno: int, errors: list[str]) -> None:
    m = INDEX_LINE_RE.search(block)
    if not m:
        return
    a, b = m.group(1), m.group(2)
    if (a == "0" * len(a) or b == "0" * len(b)) and not _has_create_or_delete(block):
        lno = base_lno + block.count("\n", 0, m.start())
        errors.append(f"Null blob in index line without create/delete near line {lno}")


def _validate_hunks(block: str, base_lno: int, errors: list[str]) -> None:
    headers = list(HUNK_HEADER_RE.finditer(block))
    if not headers:
        if _block_is_header_only(block):
            return
        if re.search(r"^---\s", block, re.MULTILINE) or re.search(
            r"^\+\+\+\s", block, re.MULTILINE
        ):
            errors.append(f"Missing hunk for block starting at line {base_lno}")
        return

    # Only treat the next "diff --git" as a section boundary; do NOT use ^---/^\+\+\+.
    section_bounds = [
        m.start() for m in re.finditer(r"^diff --git ", block, re.MULTILINE)
    ]
    section_bounds.append(len(block))

    for i, h in enumerate(headers):
        h_lno = base_lno + block.count("\n", 0, h.start())
        hdr_eol = block.find("\n", h.start())
        if hdr_eol == -1:
            errors.append(f"Truncated hunk header at line {h_lno}")
            continue
        body_start = hdr_eol + 1

        next_hunk_start = headers[i + 1].start() if i + 1 < len(headers) else None
        next_section_after_h = min(
            (p for p in section_bounds if p > h.start()), default=len(block)
        )
        body_end = (
            min(next_hunk_start, next_section_after_h)
            if next_hunk_start is not None
            else next_section_after_h
        )
        body = block[body_start:body_end]

        lines = (
            body.splitlines()
        )  # do not trim trailing empties; valid hunk lines must start with ' ', '+', '-'
        if not lines:
            errors.append(f"Empty hunk body after header at line {h_lno}")
            continue

        invalid = [ln for ln in lines if ln and not HUNK_BODY_LINE_RE.match(ln)]
        if invalid:
            first = invalid[0]
            rel = lines.index(first) + 1
            errors.append(
                f"Invalid hunk body line at {h_lno + rel}: {first!r} "
                "(expected ' ', '+', '-', or '\\\\ No newline at end of file')"
            )
            continue

        old_len = int(h.group(2)[1:]) if h.group(2) else 1
        new_len = int(h.group(4)[1:]) if h.group(4) else 1

        # Count using first character only; robust to stray '\r' at EOL.
        old_lines = sum(1 for ln in lines if ln[:1] == " " or ln[:1] == "-")
        new_lines = sum(1 for ln in lines if ln[:1] == " " or ln[:1] == "+")

        if old_lines != old_len or new_lines != new_len:
            errors.append(
                f"Hunk length mismatch at line {h_lno}: "
                f"expected -{old_len},+{new_len} but saw -{old_lines},+{new_lines}"
            )


def _git_sanity_check(content: str, errors: list[str]) -> None:
    # Skip if no index lines (minimal diffs); git can be overly strict here
    if not re.search(r"^index [0-9a-f]+\.\.[0-9a-f]+", content, re.MULTILINE):
        return
    git = shutil.which("git")
    if not git:
        errors.append("git not found on PATH; skipped `git apply --stat`")
        return

    with tempfile.NamedTemporaryFile("w+", suffix=".patch", delete=True) as tf:
        tf.write(content)
        tf.flush()
        p = subprocess.run(
            [git, "apply", "--stat", tf.name],
            capture_output=True,
            text=True,
        )
        if p.returncode != 0:
            msg = (p.stderr or p.stdout).strip()
            errors.append(f"`git apply --stat` failed: {msg}")


def _unidiff_sanity_check(content: str, errors: list[str]) -> None:
    try:
        ps = PatchSet(content.splitlines(keepends=True))
    except UnidiffParseError as e:
        errors.append(f"unidiff parse error: {e}")
        return

    for pfile in ps:
        for h in pfile:
            old_lines = sum(1 for ln in h if ln.is_removed or ln.is_context)
            new_lines = sum(1 for ln in h if ln.is_added or ln.is_context)
            if old_lines != h.source_length or new_lines != h.target_length:
                errors.append(
                    f"unidiff length mismatch: -{h.source_length},+{h.target_length} "
                    f"but saw -{old_lines},+{new_lines}"
                )


def _is_valid_patch(content: str) -> bool:
    if not DIFF_HEADER_RE.search(content):
        raise ValueError("Missing or malformed 'diff --git' header")

    errors: list[str] = []
    blocks = _split_files(content)
    if not blocks:
        raise ValueError("Missing or malformed 'diff --git' header")

    for base_lno, block in blocks:
        _validate_index_line(block, base_lno, errors)
        _validate_file_headers(block, base_lno, errors)
        _validate_hunks(block, base_lno, errors)
        for m in re.finditer(r"^@@", block, re.MULTILINE):
            line_end = block.find("\n", m.start())
            line = block[m.start() : (line_end if line_end != -1 else len(block))]
            if not HUNK_HEADER_RE.match(line):
                lno = base_lno + block.count("\n", 0, m.start())
                errors.append(f"Malformed hunk header at line {lno}")

    if not errors:
        _git_sanity_check(content, errors)
        _unidiff_sanity_check(content, errors)

    if errors:
        raise ValueError("Patch validation failed:\n- " + "\n- ".join(errors))
    return True
