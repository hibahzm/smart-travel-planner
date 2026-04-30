from __future__ import annotations

import re
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=100)
    webhook_url: str | None = Field(default=None, description="Discord/Slack webhook for trip delivery")

    @field_validator("username")
    @classmethod
    def alphanumeric(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username must be alphanumeric (underscores allowed)")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    webhook_url: str | None

    model_config = {"from_attributes": True}


class UpdateWebhookRequest(BaseModel):
    webhook_url: str = Field(max_length=1000)
