from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, select, func, or_, and_
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
    search: str | None = Query(None),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    query = select(Task).options(
        selectinload(Task.assignee),
        selectinload(Task.created_by)
    )

    filters = []

    if status_filter and status_filter != "all":
        filters.append(Task.status == status_filter)

    if assignee_id:
        filters.append(Task.assignee_id == assignee_id)

    if created_by_id:
        filters.append(Task.created_by_id == created_by_id)

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

    sort_column = Task.deadline

    if cursor:
        if sort_order == "asc":
            query = query.where(sort_column > cursor)
        else:
            query = query.where(sort_column < cursor)

    query = query.order_by(
        sort_column.asc() if sort_order == "asc"
        else sort_column.desc()
    )

    query = query.limit(limit + 1)

    result = await db.execute(query)
    tasks = result.scalars().all()

    has_more = len(tasks) > limit
    if has_more:
        tasks = tasks[:limit]

    next_cursor = tasks[-1].deadline if tasks else None

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
    assignee_result = await db.execute(
        select(User).where(User.id == task_data.assignee_id)
    )
    assignee = assignee_result.scalar_one_or_none()
    
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignee not found"
        )
    
    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        deadline=task_data.deadline,
        assignee_id=task_data.assignee_id,
        created_by_id=current_user.id
    )
    
    try:
        db.add(new_task)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.assignee),
            selectinload(Task.created_by),
        )
        .where(Task.id == new_task.id)
    )

    new_task = result.scalar_one()

    return ApiResponse(
        success=True,
        data=TaskResponse.model_validate(new_task),
        message="Task created successfully",
    )


@router.patch("/{task_id}/status", response_model=ApiResponse[TaskResponse])
async def update_task_status(
    task_id: UUID,
    status_data: TaskStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    
    if (
        task.created_by_id != current_user.id
        and task.assignee_id != current_user.id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to update this task")
    
    task.status = status_data.status
    
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.assignee),
            selectinload(Task.created_by),
        )
        .where(Task.id == task_id)
    )

    task = result.scalar_one()


    return ApiResponse(
        success=True,
        data=TaskResponse.model_validate(task),
        message="Task status updated successfully",
    )


@router.delete("/{task_id}", response_model=ApiResponse[dict])
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    if (
        task.created_by_id != current_user.id
        and task.assignee_id != current_user.id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to delete this task")
    
    try:
        await db.delete(task)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return ApiResponse(
        success=True,
        data={},
        message="Task deleted successfully",
    )

@router.get("/stats/summary", response_model=ApiResponse[TaskStats])
async def get_task_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            func.count(Task.id).label("total"),
            func.count(
                case((Task.status == TaskStatus.TODO, 1))
            ).label("todo"),
            func.count(
                case((Task.status == TaskStatus.IN_PROGRESS, 1))
            ).label("in_progress"),
            func.count(
                case((Task.status == TaskStatus.DONE, 1))
            ).label("done"),
        )
    )

    row = result.one()

    stats = TaskStats(
        total=row.total,
        todo=row.todo,
        in_progress=row.in_progress,
        done=row.done,
    )

    return ApiResponse(
        success=True,
        data=stats,
        message="Statistics retrieved successfully",
    )

