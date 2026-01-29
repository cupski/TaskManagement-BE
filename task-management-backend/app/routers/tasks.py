from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, date, timezone

from app.database import get_db
from app.models import Task, User, TaskStatus
from app.schemas import (
    TaskCreate,
    TaskResponse,
    TaskStatusUpdate,
    TaskStats,
    ApiResponse,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=ApiResponse[dict])
async def get_tasks(
    limit: int = Query(20, ge=1, le=100),
    cursor: datetime | None = Query(None, description="Cursor for infinite scroll"),
    status_filter: TaskStatus | None = Query(None, alias="status"),
    assignee_id: UUID | None = Query(None),
    created_by_id: UUID | None = Query(None),
    deadline_from: datetime | None = Query(None),
    deadline_to: datetime | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("created_at", pattern="^(created_at|deadline)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Infinite scroll task list (cursor-based)
    """

    # Base query
    query = select(Task).options(
        selectinload(Task.assignee),
        selectinload(Task.created_by)
    )

    filters = []

    if status_filter:
        filters.append(Task.status == status_filter)

    if assignee_id:
        filters.append(Task.assignee_id == assignee_id)

    if created_by_id:
        filters.append(Task.created_by_id == created_by_id)

    if deadline_from:
        filters.append(Task.deadline >= deadline_from)

    if deadline_to:
        filters.append(Task.deadline <= deadline_to)

    if search:
        keyword = f"%{search}%"
        filters.append(
            or_(
                Task.title.ilike(keyword),
                Task.description.ilike(keyword)
            )
        )

    if filters:
        query = query.where(and_(*filters))

    # Sorting field
    sort_column = getattr(Task, sort_by)

    # Cursor condition
    if cursor:
        if sort_order == "asc":
            query = query.where(sort_column > cursor)
        else:
            query = query.where(sort_column < cursor)

    # Order
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Fetch limit + 1
    query = query.limit(limit + 1)

    result = await db.execute(query)
    tasks = result.scalars().all()

    has_more = len(tasks) > limit
    if has_more:
        tasks = tasks[:limit]

    next_cursor = getattr(tasks[-1], sort_by) if tasks else None

    return ApiResponse(
        success=True,
        data={
            "items": [TaskResponse.model_validate(t) for t in tasks],
            "has_more": has_more,
            "next_cursor": next_cursor,
        },
        message="Tasks retrieved successfully"
    )


@router.post("", response_model=ApiResponse[TaskResponse], status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new task
    
    - **title**: Task title (required, max 200 chars)
    - **description**: Task description (optional)
    - **status**: Task status (default: todo)
    - **deadline**: Task deadline (required)
    - **assignee_id**: User ID to assign the task to (required)
    """
    # Verify assignee exists
    assignee_result = await db.execute(
        select(User).where(User.id == task_data.assignee_id)
    )
    assignee = assignee_result.scalar_one_or_none()
    
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignee not found"
        )
    
    # Create task
    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        deadline=task_data.deadline,
        assignee_id=task_data.assignee_id,
        created_by_id=current_user.id
    )
    
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    # Load relationships
    await db.refresh(new_task, ["assignee", "created_by"])
    
    return ApiResponse(
        success=True,
        data=TaskResponse.model_validate(new_task),
        message="Task created successfully"
    )


@router.get("/{task_id}", response_model=ApiResponse[TaskResponse])
async def get_task_by_id(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get task by ID
    
    - **task_id**: UUID of the task
    """
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.assignee), selectinload(Task.created_by))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return ApiResponse(
        success=True,
        data=TaskResponse.model_validate(task),
        message="Task retrieved successfully"
    )



@router.patch("/{task_id}/status", response_model=ApiResponse[TaskResponse])
async def update_task_status(
    task_id: UUID,
    status_data: TaskStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update only the status of a task
    
    - **status**: New status (todo, in_progress, or done)
    """
    # Get task
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.assignee), selectinload(Task.created_by))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    task.status = status_data.status
    
    await db.commit()
    await db.refresh(task)
    await db.refresh(task, ["assignee", "created_by"])
    
    return ApiResponse(
        success=True,
        data=TaskResponse.model_validate(task),
        message="Task status updated successfully"
    )


@router.delete("/{task_id}", response_model=ApiResponse[dict])
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a task
    
    - **task_id**: UUID of the task to delete
    """
    # Get task
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    await db.delete(task)
    await db.commit()
    
    return ApiResponse(
        success=True,
        data={},
        message="Task deleted successfully"
    )


@router.get("/stats/summary", response_model=ApiResponse[TaskStats])
async def get_task_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get task statistics
    
    Returns:
    - Total tasks
    - Tasks by status
    - Overdue tasks
    - Tasks due today
    - My assigned tasks
    - Tasks created by me
    """
    # Total tasks
    total_result = await db.execute(select(func.count(Task.id)))
    total_tasks = total_result.scalar()
    
    # Tasks by status
    status_counts = {}
    for task_status in TaskStatus:
        status_result = await db.execute(
            select(func.count(Task.id)).where(Task.status == task_status)
        )
        status_counts[task_status.value] = status_result.scalar()
    
    # Overdue tasks
    now = datetime.now(timezone.utc)
    overdue_result = await db.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.deadline < now,
                Task.status != TaskStatus.DONE
            )
        )
    )
    overdue_tasks = overdue_result.scalar()
    
    # Tasks due today
    today = date.today()
    due_today_result = await db.execute(
        select(func.count(Task.id)).where(
            func.date(Task.deadline) == today
        )
    )
    tasks_due_today = due_today_result.scalar()
    
    # My assigned tasks
    my_tasks_result = await db.execute(
        select(func.count(Task.id)).where(Task.assignee_id == current_user.id)
    )
    my_tasks = my_tasks_result.scalar()
    
    # Tasks created by me
    created_by_me_result = await db.execute(
        select(func.count(Task.id)).where(Task.created_by_id == current_user.id)
    )
    created_by_me = created_by_me_result.scalar()
    
    stats = TaskStats(
        total_tasks=total_tasks,
        by_status=status_counts,
        overdue_tasks=overdue_tasks,
        tasks_due_today=tasks_due_today,
        my_tasks=my_tasks,
        created_by_me=created_by_me
    )
    
    return ApiResponse(
        success=True,
        data=stats,
        message="Statistics retrieved successfully"
    )
