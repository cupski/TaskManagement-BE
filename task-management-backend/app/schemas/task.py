from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional

from app.models.task import TaskStatus
from app.schemas.user import UserResponse


class TaskBase(BaseModel):
    """Base task schema"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    deadline: datetime
    assignee_id: UUID


class TaskCreate(TaskBase):
    """Schema for creating a task"""
    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    deadline: Optional[datetime] = None
    assignee_id: Optional[UUID] = None


class TaskStatusUpdate(BaseModel):
    """Schema for updating only task status"""
    status: TaskStatus


class TaskResponse(TaskBase):
    """Schema for task response"""
    id: UUID
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    assignee: UserResponse
    created_by: UserResponse
    
    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    """Schema for paginated task list"""
    items: list[TaskResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class TaskStats(BaseModel):
    """Schema for task statistics"""
    total: int
    todo: int
    in_progress: int
    done: int
