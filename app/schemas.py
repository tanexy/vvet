from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .signs import SignId

FindingValue = Literal["yes", "no", "not_sure"]


class ExtractRequest(BaseModel):
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class Finding(BaseModel):
    sign_id: SignId
    value: FindingValue
    quote: str = Field(min_length=1)


class ExtractResponse(BaseModel):
    findings: list[Finding]
    escalate: bool
    reason: str
