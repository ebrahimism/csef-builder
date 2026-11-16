"""Versioned runtime data, never a caller-created verification capability."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, field_validator, model_validator


Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
FactID = Annotated[str, Field(pattern=r"^[A-Z]+-[0-9]{3}$")]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    schema_version: Literal[1] = 1

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be the integer 1")
        return value


class OwnerFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: FactID
    kind: Literal["requirement", "constraint", "decision"]
    text: str


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str
    answer: str


class ProjectRevision(Record):
    version: Annotated[int, Field(ge=1)]
    sha256: Hash
    goal: Annotated[str, Field(min_length=1)]
    answers: dict[str, str | Answer]
    facts: list[OwnerFact]

    @model_validator(mode="after")
    def unique_facts(self):
        if len({f.id for f in self.facts}) != len(self.facts):
            raise ValueError("duplicate owner fact ID")
        return self


class StageSpec(Record):
    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    title: Annotated[str, Field(min_length=1)]
    role: Annotated[str, Field(min_length=1)]


class FileChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str
    content: str


class ChangeProposal(Record):
    summary: str
    files: Annotated[list[FileChange], Field(min_length=1, max_length=40)]
    # Omission supports the existing small-file adapter. Explicit bases bind it.
    base_revision: Hash | None = None


class VerificationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    id: str
    exit_code: int
    stdout: str
    stderr: str
    expected_exit: int
    expected_json: JsonValue
    actual_json: JsonValue = None
    passed: bool
    timed_out: bool = False
    overflow: bool = False
    elapsed_s: Annotated[float, Field(ge=0)] | None = None


class VerificationRecord(Record):
    evaluation_id: Annotated[str, Field(pattern=r"^eval-[0-9a-f]{32}$")]
    run_id: Annotated[str, Field(pattern=r"^run-[0-9a-f]{32}$")]
    status: Literal["pass", "fail", "review", "blocked"]
    measurement_only: bool
    source_sha256: Hash
    spec_sha256: Hash
    source_manifest: dict[str, Hash]
    boundary: dict[str, JsonValue] | None
    error: str | None
    cases: list[VerificationCase]
    finished_at: str

    @model_validator(mode="after")
    def passing_is_complete(self):
        if self.status == "pass" and (
            self.measurement_only or self.error is not None or not self.cases
            or not self.boundary or self.boundary.get("verified") is not True
            or any(not c.passed or c.timed_out or c.overflow for c in self.cases)
        ):
            raise ValueError("incomplete passing verification")
        return self


def checked(model, value):
    """Translate strict shape rejection to the existing application error."""
    from .core import Refused
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise Refused(f"invalid {model.__name__}: {exc}") from exc
