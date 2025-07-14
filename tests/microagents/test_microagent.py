import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from useagent.microagents.microagent import load_microagent, MicroAgent

# ===================================
#         Test Area
#   Find Data at the bottom of file
# ===================================

def test_valid_microagent(tmp_path: Path):
    file = tmp_path / "test.microagent.md"
    file.write_text(VALID_CONTENT)
    agent = load_microagent(file)
    assert isinstance(agent, MicroAgent)
    assert agent.name == "ExampleAgent"
    assert agent.version == "1.2.3"
    assert "instruction" in agent.__dataclass_fields__
    assert agent.instruction

def test_invalid_version_format(tmp_path: Path):
    file = tmp_path / "bad.microagent.md"
    file.write_text(INVALID_VERSION)
    with pytest.raises(ValueError, match="Version must match format X.Y.Z"):
        load_microagent(file)


def test_invalid_version_format_2(tmp_path: Path):
    file = tmp_path / "bad.microagent.md"
    file.write_text(INVALID_VERSION_2)
    with pytest.raises(ValueError, match="Version must match format X.Y.Z"):
        load_microagent(file)


def test_missing_required_field(tmp_path: Path):
    file = tmp_path / "missing.microagent.md"
    file.write_text(MISSING_FIELD)
    with pytest.raises(ValueError, match="Missing required field: name"):
        load_microagent(file)

def test_non_file_path():
    with pytest.raises(ValueError, match="Path is empty or None"):
        load_microagent(None)

def test_path_not_a_file(tmp_path: Path):
    with pytest.raises(ValueError, match="Path does not point to a file"):
        load_microagent(tmp_path / "nonexistent.microagent.md")

def test_missing_header_structure(tmp_path: Path):
    file = tmp_path / "bad.microagent.md"
    file.write_text(MISSING_HEADER)
    with pytest.raises(ValueError, match="File does not contain a valid YAML header section"):
        load_microagent(file)

def test_agents_keyword_all(tmp_path: Path):
    file = tmp_path / "all.microagent.md"
    file.write_text(ALL_AGENTS_CONTENT)
    agent = load_microagent(file)
    assert agent.agents == []

def test_multiple_agents_and_triggers(tmp_path: Path):
    file = tmp_path / "multi.microagent.md"
    file.write_text(MULTI_AGENT_CONTENT)
    agent = load_microagent(file)
    assert len(agent.agents) == 3
    assert len(agent.triggers) == 3

def test_str_path_input(tmp_path: Path):
    file = tmp_path / "strpath.microagent.md"
    file.write_text(VALID_CONTENT)
    agent = load_microagent(str(file))
    assert isinstance(agent, MicroAgent)

def test_instruction_with_dashes(tmp_path: Path):
    file = tmp_path / "dashes.microagent.md"
    file.write_text(INSTRUCTION_WITH_DASHES)
    agent = load_microagent(file)
    assert "---" in agent.instruction
    assert "This part should also be captured." in agent.instruction

def test_instruction_with_yml_block(tmp_path: Path):
    file = tmp_path / "ymlblock.microagent.md"
    file.write_text(INSTRUCTION_WITH_YML_BLOCK)
    agent = load_microagent(file)
    assert "```yml" in agent.instruction
    assert "name: something" in agent.instruction

def test_instruction_with_raw_yaml(tmp_path: Path):
    file = tmp_path / "rawyaml.microagent.md"
    file.write_text(INSTRUCTION_WITH_RAW_YAML)
    agent = load_microagent(file)
    assert "name: not_really" in agent.instruction

def test_instruction_with_code(tmp_path: Path):
    file = tmp_path / "code.microagent.md"
    file.write_text(INSTRUCTION_WITH_CODE)
    agent = load_microagent(file)
    assert "def foo" in agent.instruction
    assert "return 42" in agent.instruction

def test_instruction_with_md_block(tmp_path: Path):
    file = tmp_path / "markdown.microagent.md"
    file.write_text(INSTRUCTION_WITH_MD)
    agent = load_microagent(file)
    assert "# Heading" in agent.instruction
    assert "*markdown*" in agent.instruction


def test_instruction_with_blank_lines_preserved(tmp_path: Path):
    file = tmp_path / "blanklines.microagent.md"
    file.write_text(INSTRUCTION_WITH_BLANK_LINES)
    agent = load_microagent(file)
    assert agent.instruction.startswith("\n\n")
    assert "First line" in agent.instruction
    assert agent.instruction.endswith("\n")

def test_instruction_with_leading_whitespace(tmp_path: Path):
    file = tmp_path / "leading.microagent.md"
    file.write_text(INSTRUCTION_WITH_LEADING_SPACE)
    agent = load_microagent(file)
    assert "    Indented line" in agent.instruction
    assert agent.instruction.startswith("Indented line") is False

def test_empty_instruction_is_valid(tmp_path: Path):
    file = tmp_path / "empty.microagent.md"
    file.write_text(EMPTY_INSTRUCTION)
    agent = load_microagent(file)
    assert agent.instruction.strip() == ""



# ================================================
#               Data Area               
#    Examples used in the Tests           
# ================================================


VALID_CONTENT = """---
name: ExampleAgent
version: 1.2.3
agents:
  - edit
triggers:
  - git
  - diff
---

# Example Instruction
Some instruction text.
"""

INVALID_YAML = """---
name: 
version: notaversion
agents: []
triggers: []
---
"""

MISSING_HEADER = """# No YAML header
This is not valid.
"""

MISSING_FIELD = """---
version: 1.0.0
agents:
  - edit
triggers:
  - git
---
"""

INVALID_VERSION = """---
name: ValidName
version: notaversion
agents:
  - edit
triggers:
  - diff
---
"""

INVALID_VERSION_2 = """---
name: ValidName
version: 1.B.22
agents:
  - edit
triggers:
  - diff
---
"""

ALL_AGENTS_CONTENT = """---
name: AllAgents
version: 2.0.0
agents:
  - all
triggers:
  - push
---
Applies to all agents.
"""

MULTI_AGENT_CONTENT = """---
name: MultiAgent
version: 3.1.4
agents:
  - edit
  - analyze
  - write
triggers:
  - commit
  - push
  - merge
---
Handles multiple agents and triggers.
"""

INSTRUCTION_WITH_DASHES = """---
name: DashedAgent
version: 1.0.0
agents:
  - edit
triggers:
  - update
---
This is a section.

----
This part should also be captured.
"""

INSTRUCTION_WITH_YML_BLOCK = """---
name: YamlBlockAgent
version: 1.0.1
agents:
  - edit
triggers:
  - sync
---
```yml
name: something
version: 2.0.0
```
"""

INSTRUCTION_WITH_RAW_YAML = """---
name: RawYamlAgent
version: 1.0.2
agents:
  - write
triggers:
  - build
---

name: not_really
version: 2.0.0
"""

INSTRUCTION_WITH_CODE = """---
name: CodeAgent
version: 1.0.3
agents:
  - exec
triggers:
  - run
---

```python
def foo():
    return 42
```
"""

INSTRUCTION_WITH_MD = """---
name: MarkdownAgent
version: 1.0.4
agents:
  - render
triggers:
  - display

---
# Heading

Some *markdown* content.
"""

INSTRUCTION_WITH_LEADING_SPACE = """---
name: LeadingSpace
version: 1.0.0
agents:
  - one
triggers:
  - evt
---

    Indented line
Still here
"""

INSTRUCTION_WITH_BLANK_LINES = """---
name: BlankLines
version: 1.0.0
agents:
  - one
triggers:
  - evt
---


First line

Last line

"""

EMPTY_INSTRUCTION = """---
name: EmptyInstruction
version: 1.0.0
agents:
  - one
triggers:
  - evt
---
"""
