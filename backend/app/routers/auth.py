from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.auth_db import User
from app.models.auth_schemas import (
    AuthTokenResponse,
    ErrorResponse,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    PasswordResetRequest,
    UserPublic,
    VerifyEmailRequest,
)
from app.services.auth_service import (
    get_public_user,
    login_user,
    register_and_send_email_code,
    reset_password,
    send_password_reset_email,
    verify_email_code,
)
from app.services.jwt_service import decode_access_token
from app.services.recaptcha import verify_recaptcha_v2


router = APIRouter(prefix="/auth", tags=["auth"])


def get_current_user(
    *,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = int(sub)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/register", response_model=MessageResponse)
def register(
    req: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        remote_ip = (request.client.host if request.client else None)  # best effort
        verify_recaptcha_v2(token=req.recaptchaToken, remote_ip=remote_ip)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="ReCaptcha validation failed")

    try:
        register_and_send_email_code(db, email=req.email, login=req.login, password=req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Verification code was sent to your email"}


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        verify_email_code(db, email=req.email, code=req.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Email verified successfully"}


@router.post("/login", response_model=AuthTokenResponse)
def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        remote_ip = (request.client.host if request.client else None)
        verify_recaptcha_v2(token=req.recaptchaToken, remote_ip=remote_ip)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="ReCaptcha validation failed")

    try:
        token, user = login_user(db, identifier=req.identifier, password=req.password)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_public_dict = get_public_user(user)
    user_public = UserPublic(**user_public_dict)
    return AuthTokenResponse(accessToken=token, user=user_public)


@router.post("/request-password-reset", response_model=MessageResponse)
def request_password_reset(
    req: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        remote_ip = (request.client.host if request.client else None)
        verify_recaptcha_v2(token=req.recaptchaToken, remote_ip=remote_ip)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="ReCaptcha validation failed")

    # Avoid leaking if user exists.
    try:
        send_password_reset_email(db, identifier=req.identifier)
    except ValueError:
        pass

    return {"message": "If your account exists, we sent a reset code to your email"}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password_endpoint(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        reset_password(db, identifier=req.identifier, code=req.code, new_password=req.newPassword)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Password has been reset"}


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return {"user": UserPublic(**get_public_user(current_user))}

