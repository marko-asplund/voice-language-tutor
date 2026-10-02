from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class Setup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_language: Short
    native_language: Short
    level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    student_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""


class Turn(BaseModel):
    turn_id: str
    sequence: int
    speaker: Literal["learner", "tutor"]
    text: Text


class Mistake(BaseModel):
    turn_id: Short
    original: Text
    corrected: Text
    explanation: Text
    category: Literal["grammar", "word_choice", "expression"]


class Vocabulary(BaseModel):
    turn_id: Short
    term: Text
    translation: Text
    example: Text
    example_kind: Literal["conversation", "generated"]


class Review(BaseModel):
    schema_version: Literal["1"]
    summary: Text
    mistakes: list[Mistake] = Field(max_length=5)
    new_vocabulary: list[Vocabulary] = Field(max_length=8)
    suggested_next_topics: list[Short] = Field(min_length=3, max_length=3)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 502,
        retryable: bool = False,
        upstream_status: int | None = None,
    ):
        self.code, self.message, self.status, self.retryable = code, message, status, retryable
        self.upstream_status = upstream_status
        super().__init__(code)
