from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.inputs import LoginIn, RegisterIn

router = APIRouter(prefix="/auth", tags=["auth"])


def _token(user: User) -> dict:
    return {"access_token": create_access_token(user.id), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "full_name": user.full_name}}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise AppError("email_taken", "An account with this email already exists.", 409, "Sign in instead.")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name)
    db.add(user)
    db.commit()
    return _token(user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise AppError("invalid_credentials", "Email or password is incorrect.", 401)
    return _token(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name}
