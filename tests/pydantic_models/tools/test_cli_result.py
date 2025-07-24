import pytest
from pydantic import ValidationError

from useagent.pydantic_models.tools.cliresult import CLIResult


@pytest.mark.pydantic_model
def test_valid_cli_result_fields():
    CLIResult(output="done", error="warn", base64_image=None, system="linux")


@pytest.mark.pydantic_model
@pytest.mark.parametrize("field", ["output", "error", "base64_image", "system"])
@pytest.mark.parametrize("value", ["", " ", "\n"])
def test_invalid_empty_fields(field: str, value: str):
    kwargs = {field: value}
    with pytest.raises(ValidationError):
        CLIResult(**kwargs)


@pytest.mark.pydantic_model
def test_add_output_and_error():
    a = CLIResult(output="a", error="x")
    b = CLIResult(output="b", error="y")
    result = a + b
    assert result.output == "ab"
    assert result.error == "xy"


@pytest.mark.pydantic_model
def test_add_image_conflict_raises():
    a = CLIResult(base64_image="img1")
    b = CLIResult(base64_image="img2")
    with pytest.raises(ValueError):
        _ = a + b


@pytest.mark.pydantic_model
def test_add_partial_fields():
    a = CLIResult(output="out")
    b = CLIResult(error="err")
    result = a + b
    assert result.output == "out"
    assert result.error == "err"


@pytest.mark.pydantic_model
def test_valid_base64_image():
    # This is a 1x1 red pixel base64 image.
    VALID_PNG_B64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMA"
        "AQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    CLIResult(base64_image=VALID_PNG_B64)


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "bad_b64", ["notbase64", "!!!###$$$", "aGVsbG8"]  # valid base64, but not an image
)
def test_invalid_base64_image(bad_b64: str):
    with pytest.raises(ValidationError):
        CLIResult(base64_image=bad_b64)


@pytest.mark.pydantic_model
def test_all_outputs_none_raises():
    with pytest.raises(ValidationError):
        CLIResult(system="linux")
