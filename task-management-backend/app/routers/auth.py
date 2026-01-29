from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select

from app.database import get_db
from app.models import User
from app.schemas import (
    UserCreate,
    UserResponse,
    UserLogin,
    ApiResponse,
)
from app.utils.security import (
    verify_password,
    get_password_hash,
    create_token_for_user,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user
    
    - **email**: User email (must be unique)
    - **username**: Username
    - **password**: Password (min 8 characters)
    - **full_name**: Full name of the user
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return ApiResponse(
        success=True,
        data=UserResponse.model_validate(new_user),
        message="User registered successfully"
    )


@router.post("/login", response_model=ApiResponse[dict])
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login user and return JWT token
    
    - **email**: User email
    - **password**: User password
    
    Returns access token and user information
    """
    # Get user by email
    result = await db.execute(
        select(User).where(
            or_(
                User.email == credentials.identifier,
                User.username == credentials.identifier
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_token_for_user(user.id, user.email)
    
    return ApiResponse(
        success=True,
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user)
        },
        message="Login successful"
    )


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    
    Requires valid JWT token in Authorization header
    """
    return ApiResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
        message="User retrieved successfully"
    )
