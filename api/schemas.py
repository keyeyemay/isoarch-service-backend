from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str | None
    email: str | None


class ServiceDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    delta_n15: float | None
    delta_c13: float | None
    image_file: str | None
    video_file: str | None
    image_url: str
    video_url: str


class ServiceResponse(ServiceDraftResponse):
    status: Literal["published"]
    created_at: datetime
    creator_id: int
    moderator_id: int | None
    formed_at: datetime | None
    completed_at: datetime | None
    is_creator: Literal[0, 1]
    is_liked: Literal[0, 1]
    likes_count: int


class PublishRequest(InputModel):
    title: str | None = Field(default=None, min_length=1, max_length=255, description="Название; если не задано, сохраняется прежнее")
    description: str = Field(min_length=1, max_length=10000, description="Описание рациона и результатов исследования")
    delta_n15: float = Field(description="Значение δ¹⁵N, ‰")
    delta_c13: float = Field(description="Значение δ¹³C, ‰")


class LikeRequest(InputModel):
    like: Annotated[StrictInt, Field(ge=0, le=1)]


class UserLogin(InputModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("username")
    @classmethod
    def clean_username(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Username must not be blank")
        return value


class UserRegister(UserLogin):
    full_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LikeResponse(BaseModel):
    like: Literal[0, 1]
    likes_count: int
