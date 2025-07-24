from pydantic import conint, constr

NonEmptyStr = constr(strip_whitespace=True, min_length=1)
PositiveInt = conint(gt=0)  # strictly > 0
NonNegativeInt = conint(ge=0)  # ≥ 0
