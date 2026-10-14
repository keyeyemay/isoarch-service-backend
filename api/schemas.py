from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt


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


class ServiceResponse(ServiceDraftResponse):
    status: Literal["published"]
    created_at: datetime
    creator_id: int
    moderator_id: int | None
    formed_at: datetime | None
    deleted_at: datetime | None
    completed_at: datetime | None
    is_creator: Literal[0, 1]
    is_liked: Literal[0, 1]
    likes_count: int
    image_url: str
    video_url: str


class PublishRequest(InputModel):
    description: str = Field(min_length=1, max_length=10000)
    delta_n15: float
    delta_c13: float


class LikeRequest(InputModel):
    like: Annotated[StrictInt, Field(ge=0, le=1)]


class UserRegister(InputModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
