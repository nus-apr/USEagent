from typing import TYPE_CHECKING

from useagent.flags import USEBENCH_ENABLED

if TYPE_CHECKING:
    from useagent.tasks.usebench_task import UseBenchTask as _UseBenchTask
else:
    _UseBenchTask = None  # type: ignore

UseBenchTask = None
if USEBENCH_ENABLED:
    try:
        from useagent.tasks.usebench_task import UseBenchTask as _UseBenchTask  # type: ignore[assignment]
        UseBenchTask = _UseBenchTask
    except ImportError:
        # keep None; runtime guards will produce a friendly error
        UseBenchTask = None