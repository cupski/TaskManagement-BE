from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from pydantic import BaseModel
from datetime import datetime, date, timezone

from app.database import get_db
from app.models import Task, User, TaskStatus
from app.schemas import ApiResponse, TaskResponse
from app.utils.dependencies import get_current_user
from app.config import settings

router = APIRouter(prefix="/chatbot", tags=["Chatbot (Bonus)"])


class ChatbotQuery(BaseModel):
    """Schema for chatbot query"""
    query: str
    context: dict | None = None


class ChatbotResponse(BaseModel):
    """Schema for chatbot response"""
    response: str
    tasks: list[TaskResponse] | None = None
    query_type: str
    metadata: dict


async def parse_natural_language_query(query: str, db: AsyncSession, user: User) -> ChatbotResponse:
    """
    Parse natural language query and return appropriate response
    
    This is a simple rule-based parser. For production, use LangChain with LLM.
    """
    query_lower = query.lower()
    now = datetime.now(timezone.utc)
    today = date.today()
    
    # Initialize response
    response_text = ""
    tasks_data = None
    query_type = "unknown"
    
    # Pattern 1: Show/List pending/incomplete/not completed tasks
    if any(word in query_lower for word in ["pending", "incomplete", "not completed", "not done", "todo"]):
        query_type = "list_incomplete_tasks"
        
        result = await db.execute(
            select(Task).where(
                Task.status != TaskStatus.DONE
            ).limit(10)
        )
        tasks = result.scalars().all()
        
        # Load relationships
        for task in tasks:
            await db.refresh(task, ["assignee", "created_by"])
        
        tasks_data = [TaskResponse.model_validate(task) for task in tasks]
        count = len(tasks_data)
        
        response_text = f"I found {count} incomplete tasks. "
        if count > 0:
            response_text += "Here they are:\n"
            for i, task in enumerate(tasks_data[:5], 1):
                response_text += f"{i}. {task.title} (Status: {task.status.value}, Assignee: {task.assignee.full_name})\n"
            if count > 5:
                response_text += f"... and {count - 5} more."
    
    # Pattern 2: Count completed/done tasks
    elif any(word in query_lower for word in ["how many", "count", "number of"]) and any(word in query_lower for word in ["completed", "done", "finished"]):
        query_type = "count_completed_tasks"
        
        result = await db.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.DONE)
        )
        count = result.scalar()
        
        response_text = f"You have {count} completed task{'s' if count != 1 else ''}."
    
    # Pattern 3: Tasks due today
    elif any(word in query_lower for word in ["due today", "today's tasks", "deadline today"]):
        query_type = "tasks_due_today"
        
        result = await db.execute(
            select(Task).where(
                func.date(Task.deadline) == today
            ).limit(10)
        )
        tasks = result.scalars().all()
        
        for task in tasks:
            await db.refresh(task, ["assignee", "created_by"])
        
        tasks_data = [TaskResponse.model_validate(task) for task in tasks]
        count = len(tasks_data)
        
        response_text = f"There {'are' if count != 1 else 'is'} {count} task{'s' if count != 1 else ''} due today."
        if count > 0:
            response_text += " Here they are:\n"
            for i, task in enumerate(tasks_data, 1):
                response_text += f"{i}. {task.title} (Assignee: {task.assignee.full_name})\n"
    
    # Pattern 4: Overdue tasks
    elif any(word in query_lower for word in ["overdue", "late", "past deadline"]):
        query_type = "overdue_tasks"
        
        result = await db.execute(
            select(Task).where(
                and_(
                    Task.deadline < now,
                    Task.status != TaskStatus.DONE
                )
            ).limit(10)
        )
        tasks = result.scalars().all()
        
        for task in tasks:
            await db.refresh(task, ["assignee", "created_by"])
        
        tasks_data = [TaskResponse.model_validate(task) for task in tasks]
        count = len(tasks_data)
        
        response_text = f"You have {count} overdue task{'s' if count != 1 else ''}."
        if count > 0:
            response_text += " Here they are:\n"
            for i, task in enumerate(tasks_data, 1):
                response_text += f"{i}. {task.title} (Deadline: {task.deadline.strftime('%Y-%m-%d')}, Assignee: {task.assignee.full_name})\n"
    
    # Pattern 5: My tasks / assigned to me
    elif any(word in query_lower for word in ["my tasks", "assigned to me", "my assignments"]):
        query_type = "my_tasks"
        
        result = await db.execute(
            select(Task).where(
                Task.assignee_id == user.id
            ).limit(10)
        )
        tasks = result.scalars().all()
        
        for task in tasks:
            await db.refresh(task, ["assignee", "created_by"])
        
        tasks_data = [TaskResponse.model_validate(task) for task in tasks]
        count = len(tasks_data)
        
        response_text = f"You have {count} task{'s' if count != 1 else ''} assigned to you."
        if count > 0:
            response_text += " Here they are:\n"
            for i, task in enumerate(tasks_data[:5], 1):
                response_text += f"{i}. {task.title} (Status: {task.status.value})\n"
            if count > 5:
                response_text += f"... and {count - 5} more."
    
    # Pattern 6: Tasks in progress
    elif "in progress" in query_lower or "ongoing" in query_lower:
        query_type = "tasks_in_progress"
        
        result = await db.execute(
            select(Task).where(
                Task.status == TaskStatus.IN_PROGRESS
            ).limit(10)
        )
        tasks = result.scalars().all()
        
        for task in tasks:
            await db.refresh(task, ["assignee", "created_by"])
        
        tasks_data = [TaskResponse.model_validate(task) for task in tasks]
        count = len(tasks_data)
        
        response_text = f"There {'are' if count != 1 else 'is'} {count} task{'s' if count != 1 else ''} in progress."
        if count > 0:
            response_text += " Here they are:\n"
            for i, task in enumerate(tasks_data, 1):
                response_text += f"{i}. {task.title} (Assignee: {task.assignee.full_name})\n"
    
    # Pattern 7: All tasks / summary
    elif any(word in query_lower for word in ["all tasks", "show all", "list all"]):
        query_type = "all_tasks"
        
        # Get counts by status
        todo_count = await db.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.TODO)
        )
        in_progress_count = await db.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.IN_PROGRESS)
        )
        done_count = await db.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.DONE)
        )
        
        todo = todo_count.scalar()
        in_progress = in_progress_count.scalar()
        done = done_count.scalar()
        total = todo + in_progress + done
        
        response_text = f"You have {total} tasks in total:\n"
        response_text += f"- To Do: {todo}\n"
        response_text += f"- In Progress: {in_progress}\n"
        response_text += f"- Done: {done}"
    
    # Default: Unknown query
    else:
        query_type = "unknown"
        response_text = "I'm sorry, I couldn't understand your query. Try asking:\n"
        response_text += "- 'Show me all pending tasks'\n"
        response_text += "- 'How many tasks are completed?'\n"
        response_text += "- 'What tasks are due today?'\n"
        response_text += "- 'Show overdue tasks'\n"
        response_text += "- 'Show my tasks'\n"
        response_text += "- 'What tasks are in progress?'"
    
    return ChatbotResponse(
        response=response_text,
        tasks=tasks_data,
        query_type=query_type,
        metadata={
            "execution_time": 0.1,
            "model_used": "rule_based_parser"
        }
    )


@router.post("/query", response_model=ApiResponse[ChatbotResponse])
async def query_chatbot(
    query_data: ChatbotQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Query AI Chatbot about tasks
    
    **Example queries:**
    - "Show me all tasks that are not completed"
    - "How many tasks are done?"
    - "What tasks are due today?"
    - "Show overdue tasks"
    - "Show my tasks"
    - "What tasks are in progress?"
    
    **Note:** This is a simple rule-based implementation.
    For production, integrate with OpenAI/Gemini using LangChain.
    Set ENABLE_AI_CHATBOT=True and provide API keys in .env
    """
    if not query_data.query or not query_data.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty"
        )
    
    # Parse query and get response
    chatbot_response = await parse_natural_language_query(
        query_data.query,
        db,
        current_user
    )
    
    return ApiResponse(
        success=True,
        data=chatbot_response,
        message="Query processed successfully"
    )


@router.get("/examples", response_model=ApiResponse[dict])
async def get_chatbot_examples():
    """
    Get example queries for the chatbot
    """
    examples = {
        "queries": [
            "Show me all pending tasks",
            "How many tasks are completed?",
            "What tasks are due today?",
            "Show overdue tasks",
            "Show my tasks",
            "What tasks are in progress?",
            "List all tasks"
        ],
        "tips": [
            "Be specific in your questions",
            "Use keywords like 'show', 'list', 'how many', 'count'",
            "Mention task status: pending, completed, in progress, overdue",
            "Ask about deadlines: today, overdue, due soon"
        ]
    }
    
    return ApiResponse(
        success=True,
        data=examples,
        message="Chatbot examples retrieved"
    )
