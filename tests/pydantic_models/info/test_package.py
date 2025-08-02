import pytest
from pydantic import ValidationError

from useagent.pydantic_models.info.package import Package, Source


@pytest.mark.pydantic_model
@pytest.mark.parametrize("name", ["pkg", " pkg", "pkg ", " pkg "])
@pytest.mark.parametrize("version", ["1.0", " 1.0", "1.0 ", " 1.0 ", "05.1.5"])
def test_valid_package(name: str, version: str):
    Package(name=name, version=version, source=Source.PROJECT)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("version", ["v1.0", " V1.0", "V1.0 "])
def test_versions_can_start_with_v(version: str):
    Package(name="test-package", version=version, source=Source.PROJECT)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("name", ["", " ", "\t", "\n"])
def test_invalid_name(name: str):
    with pytest.raises(ValidationError):
        Package(name=name, version="1.0", source=Source.SYSTEM)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("version", ["", " ", "\t", "\n"])
def test_invalid_version_empty(version: str):
    with pytest.raises(ValidationError):
        Package(name="pkg", version=version, source=Source.SYSTEM)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("version", ["x1.0", "-1.0"])
def test_invalid_version_format(version: str):
    with pytest.raises(ValidationError):
        Package(name="pkg", version=version, source=Source.SYSTEM)


@pytest.mark.pydantic_model
def test_version_with_postfix():
    # We do want some postfixes, like .post0 from datutil, .dev or +cpu (like llm packages often do)
    Package(name="python-dateutil", version="2.9.0.post0", source=Source.PROJECT)


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert Package.get_output_instructions()
