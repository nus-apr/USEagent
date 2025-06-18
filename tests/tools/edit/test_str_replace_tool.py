import pytest
from pathlib import Path
from useagent.tools.edit import str_replace
from useagent.tools.base import ToolError, CLIResult

@pytest.mark.tool
@pytest.mark.asyncio
async def test_str_replace_success(tmp_path: Path):
    file = tmp_path / "sample.txt"
    file.write_text("hello world\nthis is a test")

    result = await str_replace(str(file), "hello", "hi")
    assert isinstance(result, CLIResult)
    assert "has been edited" in result.output
    assert "hi world" in file.read_text()
    assert "hello" not in file.read_text()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_str_replace_no_occurrence(tmp_path: Path):
    file = tmp_path / "no_match.txt"
    file.write_text("hello world\nno match here")

    with pytest.raises(ToolError, match=r"old_str `nomatch` did not appear verbatim"):
        await str_replace(str(file), "nomatch", "replace")


@pytest.mark.tool
@pytest.mark.asyncio
async def test_str_replace_multiple_occurrences(tmp_path: Path):
    file = tmp_path / "multiple.txt"
    file.write_text("repeat this repeat again")

    with pytest.raises(ToolError, match=r"Multiple occurrences of old_str"):
        await str_replace(str(file), "repeat", "once")


@pytest.mark.tool
@pytest.mark.asyncio
async def test_str_replace_tabs_handled(tmp_path: Path):
    file = tmp_path / "tabs.txt"
    file.write_text("a\tb\tc")

    result = await str_replace(str(file), "a\tb\tc", "x y z")
    assert isinstance(result, CLIResult)
    assert "has been edited" in result.output
    assert "x y z" in file.read_text()
    assert "a" not in file.read_text()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_str_replace_multiline_new_string(tmp_path: Path):
    file = tmp_path / "multiline.txt"
    file.write_text("change this line")

    new_value = "line1\nline2"
    result = await str_replace(str(file), "this line", new_value)

    content = file.read_text()
    assert "line1" in content
    assert "line2" in content
    assert isinstance(result, CLIResult)
    assert "has been edited" in result.output
    assert "snippet" in result.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_str_replace_edge_case_empty_file(tmp_path: Path):
    file = tmp_path / "empty.txt"
    file.write_text("")

    with pytest.raises(ToolError, match="did not appear verbatim"):
        await str_replace(str(file), "anything", "nothing")


@pytest.mark.tool
@pytest.mark.asyncio
async def test_str_replace_exact_line_match(tmp_path: Path):
    file = tmp_path / "line_match.txt"
    file.write_text("replace me\nand not me")

    result = await str_replace(str(file), "replace me", "done")
    assert isinstance(result, CLIResult)
    assert "done" in file.read_text()
    assert "replace me" not in file.read_text()
