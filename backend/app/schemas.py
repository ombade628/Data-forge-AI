from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ColumnSpec(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    data_type: Literal["string", "integer", "number", "boolean"] = "string"
    description: str = ""
    required: bool = True
    allowed_values: list[str] = Field(default_factory=list)


class DatasetSpecification(BaseModel):
    dataset_type: str = "custom"
    languages: list[str] = Field(default_factory=lambda: ["English"])
    columns: list[ColumnSpec] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    role: str
    created_at: datetime


class PromptAnalyzeRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=10_000)
    record_count: int = Field(default=100, ge=1, le=100_000)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    specification: DatasetSpecification


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    status: str
    specification: dict[str, Any]
    created_at: datetime


class GenerationRequest(BaseModel):
    record_count: int = Field(ge=1, le=100_000)


class GenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    status: str
    requested_records: int
    generated_records: int
    error_message: str | None
    usage: dict[str, Any]
    created_at: datetime


class DatasetVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version_number: int
    schema_definition: dict[str, Any]
    record_count: int
    quality_report: dict[str, Any]
    created_at: datetime

from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ColumnSpec(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    data_type: Literal["string", "integer", "number", "boolean"] = "string"
    description: str = ""
    required: bool = True
    allowed_values: list[str] = Field(default_factory=list)


class DatasetSpecification(BaseModel):
    dataset_type: str = "custom"
    languages: list[str] = Field(default_factory=lambda: ["English"])
    columns: list[ColumnSpec] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)

    @field_validator("columns")
    @classmethod
    def no_duplicate_columns(cls, columns: list[ColumnSpec]) -> list[ColumnSpec]:
        names = [c.name for c in columns]
        if len(names) != len(set(names)):
            dupes = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"Duplicate column names: {', '.join(dupes)}")
        return columns


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    role: str
    created_at: datetime


class PromptAnalyzeRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=10_000)
    record_count: int = Field(default=100, ge=1, le=100_000)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    specification: DatasetSpecification


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    status: str
    specification: dict[str, Any]
    created_at: datetime


class GenerationRequest(BaseModel):
    record_count: int = Field(ge=1, le=100_000)


class GenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    status: str
    requested_records: int
    generated_records: int
    error_message: str | None
    usage: dict[str, Any]
    created_at: datetime


class DatasetVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version_number: int
    schema_definition: dict[str, Any]
    record_count: int
    quality_report: dict[str, Any]
    created_at: datetime