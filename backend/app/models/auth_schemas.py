import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

_LOGIN_RE = re.compile(r"^[a-zA-Z0-9_]{3,64}$")


class RegisterRequest(BaseModel):
    email: EmailStr
    login: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    recaptcha_token: str | None = Field(None, description="reCAPTCHA v2 response token")

    @field_validator("login")
    @classmethod
    def login_alphanumeric(cls, v: str) -> str:
        if not _LOGIN_RE.match(v):
            raise ValueError("login must be 3–64 chars: letters, digits, underscore only")
        return v


class ResendRegistrationCodeRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def code_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("code must be 6 digits")
        return v


class LoginRequest(BaseModel):
    login_or_email: str = Field(..., min_length=1, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class ResetRequestRequest(BaseModel):
    email: EmailStr
    recaptcha_token: str | None = None


class ResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("code")
    @classmethod
    def code_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("code must be 6 digits")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class MessageResponse(BaseModel):
    message: str


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    login: str
    is_email_verified: bool
    telegram_chat_id: str | None = None
    telegram_username: str | None = None
    telegram_first_name: str | None = None
    telegram_linked_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    login: str | None = Field(None, min_length=3, max_length=64)
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str | None = Field(None, min_length=8, max_length=128)

    @field_validator("login")
    @classmethod
    def login_alphanumeric(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _LOGIN_RE.match(v):
            raise ValueError("login must be 3–64 chars: letters, digits, underscore only")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str | None) -> str | None:
        return v


class GenerationHistoryItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    main_file_name: str


class GenerationHistoryDetail(BaseModel):
    id: uuid.UUID
    created_at: datetime
    main_file_name: str
    generated_ts_code: str


class GenerationCheckInputResponse(BaseModel):
    """Base64 of the original uploaded file when stored (see GENERATION_HISTORY_MAX_INPUT_BYTES)."""

    input_base64: str | None = None


class TokenUsageItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    main_file_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TokenUsageSummaryResponse(BaseModel):
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    requests_count: int
    requests: list[TokenUsageItem]


class TelegramLinkCodeResponse(BaseModel):
    link_command: str
    code_expires_at: datetime
    bot_url: str | None = None
    bot_username: str | None = None


class TelegramStatusResponse(BaseModel):
    is_linked: bool
    telegram_chat_id: str | None = None
    telegram_username: str | None = None
    telegram_first_name: str | None = None
    telegram_linked_at: datetime | None = None


class TelegramConsumeLinkRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=32)
    chat_id: str = Field(..., min_length=1, max_length=64)
    username: str | None = Field(None, max_length=64)
    first_name: str | None = Field(None, max_length=255)


class BotGenerateResponse(BaseModel):
    code: str
    cache_hit: bool
    main_file_name: str


class BotProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    login: str
    telegram_username: str | None = None
    recent_generations: list[GenerationHistoryItem]
    token_usage: TokenUsageSummaryResponse
