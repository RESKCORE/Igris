"""Authentication and authorization dependency for OpsPilot dashboard users."""

from typing import Optional
from fastapi import Depends, Header, HTTPException, status
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User, UserRole, generate_uuid


def seed_default_users(db: Session) -> None:
    """Ensure default demo dashboard users exist in the database."""
    default_users = [
        {"email": "owner@example.com", "name": "Business Owner", "role": UserRole.owner.value},
        {"email": "staff@example.com", "name": "Operations Staff", "role": UserRole.staff.value},
        {"email": "auditor@example.com", "name": "Compliance Reviewer", "role": UserRole.auditor.value},
    ]
    for u in default_users:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            db.add(User(
                id=generate_uuid(),
                email=u["email"],
                name=u["name"],
                role=u["role"],
            ))
    db.commit()


def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_role: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve current user via JWT token or developer bypass."""
    # 1. Developer bypass mode
    if settings.DEV_AUTH_BYPASS:
        role = x_user_role.lower() if x_user_role and x_user_role.lower() in [r.value for r in UserRole] else UserRole.owner.value
        email = f"{role}@example.com"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                id=f"dev-{role}-id",
                email=email,
                name=f"Dev {role.capitalize()}",
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    # 2. Production JWT token authentication
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing or malformed Authorization header."},
        )

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": f"Token verification failed: {str(e)}"},
        )

    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token_payload", "message": "Token does not contain an email claim."},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            id=payload.get("sub", generate_uuid()),
            email=email,
            name=payload.get("user_metadata", {}).get("name", email.split("@")[0]),
            role=payload.get("user_metadata", {}).get("role", UserRole.owner.value),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user

