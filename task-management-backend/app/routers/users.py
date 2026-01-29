from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.database import get_db
from app.models import User
from app.schemas import UserResponse, ApiResponse
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=ApiResponse[dict])
async def get_users(
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    search: str = Query(None, description="Search by name or email"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of all users (for assignee dropdown)
    
    - **limit**: Items per page (default: 50, max: 100)
    - **search**: Search by name or email (optional)
    
    Returns paginated list of users
    """
    # Build query
    query = select(User)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            User.full_name.ilike(search_filter) |
            User.email.ilike(search_filter) |
            User.username.ilike(search_filter)
        )

    query = query.limit(limit)

    
    result = await db.execute(query)
    users = result.scalars().all()
    
    
    return ApiResponse(
        success=True,
        data={
            "users": [UserResponse.model_validate(user) for user in users],
        },
    )