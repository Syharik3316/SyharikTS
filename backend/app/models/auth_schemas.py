from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    recaptchaToken: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=128)  # email or login
    password: str = Field(min_length=1, max_length=256)
    recaptchaToken: str


class PasswordResetRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=128)  # email or login
    recaptchaToken: str


class ResetPasswordRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=128)  # email or login
    code: str = Field(min_length=4, max_length=16)
    newPassword: str = Field(min_length=8, max_length=256)


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    login: str
    emailVerified: bool


class AuthTokenResponse(BaseModel):
    accessToken: str
    user: UserPublic


class MeResponse(BaseModel):
    user: UserPublic


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str

