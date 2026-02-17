import pytest

from useagent.agents.meta.agent import _has_real_doubts


@pytest.mark.agent
class TestHasRealDoubts:
    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "none",
            "None",
            "NONE",
            "none.",
            "None.",
            "no",
            "No",
            "NO",
            "no.",
            "No.",
            "n/a",
            "N/A",
            "no doubt",
            "No doubt.",
            "no doubts",
            "No doubts.",
            "  none  ",
            " no. ",
            "\tnone\n",
        ],
    )
    def test_no_real_doubts(self, value):
        assert _has_real_doubts(value) is False

    @pytest.mark.parametrize(
        "value",
        [
            "I'm unsure about X",
            "Maybe the edge case isn't handled",
            "not sure",
            "yes",
            "The implementation might break for negative inputs",
        ],
    )
    def test_has_real_doubts(self, value):
        assert _has_real_doubts(value) is True
