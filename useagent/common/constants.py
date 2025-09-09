"""
Glossary:

- Output Retries: pydantic framework re-tries to fit a model response into a output type
- Bash tool delay: A mandated sleep before the bash tool is executed, e.g. to avoid Gemini API overload

"""

from typing import Final

# =============================================================
#                 Workflow / Meta Constants
# =============================================================

MAX_DOUBT_REITERATIONS: Final[int] = (
    2  # Counter starts from 0, so 2 retries means it runs up to two doubt sessions.
)

# =============================================================
#                 Agent and Pydantic Constants
# =============================================================

META_AGENT_REQUEST_LIMIT: Final[int] = 100
META_AGENT_OUTPUT_RETRIES: Final[int] = 10
META_AGENT_RETRIES: Final[int] = 3
META_AGENT_BASH_TOOL_DELAY: Final[float] = 0.25  # In Seconds

SEARCH_AGENT_REQUEST_LIMIT: Final[int] = 110
SEARCH_AGENT_RETRIES: Final[int] = 5
SEARCH_AGENT_OUTPUT_RETRIES: Final[int] = 6
SEARCH_AGENT_BASH_TOOL_DELAY: Final[float] = 0.3  # In Seconds

PROBING_AGENT_WORKDIR_REQUEST_LIMIT: Final[int] = 25
PROBING_AGENT_COMMAND_REQUEST_LIMIT: Final[int] = 115
PROBING_AGENT_GIT_REQUEST_LIMIT: Final[int] = 115
PROBING_AGENT_PACKAGE_REQUEST_LIMIT: Final[int] = 100
PROBE_ENVIRONMENT_RETRIES: Final[int] = 3
PROBING_AGENT_BASH_TOOL_DELAY: Final[float] = 0.4  # In Seconds
PROBING_AGENT_OUTPUT_RETRIES: Final[int] = 3

EXECUTE_TESTS_AGENT_REQUEST_LIMIT: Final[int] = 115
EXECUTE_TESTS_RETRIES: Final[int] = 3
EXECUTE_TESTS_AGENT_BASH_TOOL_DELAY: Final[float] = 0.35  # In Seconds
EXECUTE_TESTS_OUTPUT_RETRIES: Final[int] = 6

EDIT_CODE_AGENT_REQUEST_LIMIT: Final[int] = 110
EDIT_CODE_RETRIES: Final[int] = 4
EDIT_CODE_AGENT_RETRIES: Final[int] = 4
# DevNote: The diff-entries are hard to get right for the model. But they must fit their schema to make any sense.
EDIT_CODE_AGENT_OUTPUT_RETRIES: Final[int] = 12

VCS_AGENT_REQUEST_LIMIT: Final[int] = 100
VCS_AGENT_RETRIES: Final[int] = 3
VCS_AGENT_OUTPUT_RETRIES: Final[int] = 6
VCS_AGENT_BASH_TOOL_DELAY: Final[float] = 0.35  # In Seconds

ADVISOR_AGENT_RETRIES: Final[int] = 2
ADVISOR_AGENT_OUTPUT_RETRIES: Final[int] = 3


# =============================================================
#                        Tools
# =============================================================

# DevNote: The timeout is quite large, but we have seen commands that need so long
# An example is `apt-get install openjdk-jdk-8` or similar large packages.
BASH_TOOL_DEFAULT_MAX_TIMEOUT: Final[float] = 3600  # In Seconds
BASH_TOOL_REDUCED_TIMEOUT_FOR_EOF_COMMANDS: Final[float] = 8  # In Seconds

BASH_TOOL_MAX_LINE_LENGTH_FOR_EOF_COMMANDS: Final[int] = 10  # In 'len(command.lines())'

BASH_TOOL_OUTPUT_MAX_LENGTH: Final[int] = 1000000  # In MB (1000000 = 10MB)

BASH_TOOL_MESSAGE_RESPONSE_CONTEXT_LENGTH_BUFFER: Final[float] = (
    0.4  # in % of how much one message can be of the context window
)

DIFF_STORE_INTERACTION_DELAY: Final[float] = (
    0.3  # In seconds, needed to avoid model overload similar to bash tool.
)


# =============================================================
#                        SETUP
# =============================================================

DEFAULT_GIT_USER: Final[str] = "USEagent"
DEFAULT_GIT_EMAIL: Final[str] = "useagent@useagent.com"

# =============================================================
#                 Logging & Display
# =============================================================

COMMAND_OUTPUT_MAX_PRINT_CUT_OFF: Final[int] = 100
