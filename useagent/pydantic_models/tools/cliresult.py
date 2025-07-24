import base64
import binascii

from pydantic import field_validator, model_validator
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


@dataclass(kw_only=True, frozen=True)
class CLIResult:
    """Represents the result of a tool execution. Can be rendered as a CLI output."""

    output: NonEmptyStr | None = None
    error: NonEmptyStr | None = None
    base64_image: NonEmptyStr | None = None
    system: NonEmptyStr | None = None

    @field_validator("base64_image")
    @classmethod
    def validate_base64_image(cls, v: str) -> str:
        if v is None:
            return None  # If there is no image, we don't validate. We only validate if we are given a image.
        try:
            base64.b64decode(v, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("Invalid base64-encoded image data")
        return v

    @model_validator(mode="after")
    def check_at_least_one_output(self) -> "CLIResult":
        if self.output is None and self.error is None and self.base64_image is None:
            raise ValueError(
                "At least one of output, error, or base64_image must be provided"
            )
        return self

    def __add__(self, other: "CLIResult"):
        def combine_fields(
            field: str | None, other_field: str | None, concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        return CLIResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            base64_image=combine_fields(self.base64_image, other.base64_image, False),
            system=combine_fields(self.system, other.system),
        )
