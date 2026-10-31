"""Routes for managing and retrieving dashboard users."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User, UserRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead, summary="Get current authenticated dashboard user")
def get_current_dashboard_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated or active dev user profile."""
    return current_user


@router.get("", response_model=List[UserRead], summary="List available dashboard users")
def list_dashboard_users(db: Session = Depends(get_db)) -> List[User]:
    """List registered users and roles for the dashboard."""
    return db.query(User).all()

