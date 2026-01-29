import asyncio
from app.database import engine, Base, AsyncSessionLocal
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.utils.security import get_password_hash
from datetime import datetime, timedelta
from sqlalchemy import select
import uuid


async def init_db():
    """Initialize database and create seed data"""
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        # Check if users already exist
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("Database already initialized with data")
            return
        
        # Create demo users
        users = [
            User(
                id=uuid.uuid4(),
                email="john@example.com",
                username="john",
                full_name="John Doe",
                password_hash=get_password_hash("password123"),
            ),
            User(
                id=uuid.uuid4(),
                email="sarah@example.com",
                username="sarah",
                full_name="Sarah Smith",
                password_hash=get_password_hash("password123"),
            ),
            User(
                id=uuid.uuid4(),
                email="mike@example.com",
                username="mike",
                full_name="Mike Johnson",
                password_hash=get_password_hash("password123"),
            ),
            User(
                id=uuid.uuid4(),
                email="emily@example.com",
                username="emily",
                full_name="Emily Davis",
                password_hash=get_password_hash("password123"),
            ),
            User(
                id=uuid.uuid4(),
                email="alex@example.com",
                username="alex",
                full_name="Alex Wilson",
                password_hash=get_password_hash("password123"),
            ),
        ]
        
        for user in users:
            session.add(user)
        
        await session.commit()
        
        # Create demo tasks
        statuses = (
            [TaskStatus.TODO] * 4
            + [TaskStatus.IN_PROGRESS] * 3
            + [TaskStatus.DONE] * 3
        )

        now = datetime.now()

        task_counter = 1

        for idx, assignee in enumerate(users):
            creator = users[(idx + 1) % len(users)]

            for i, status in enumerate(statuses):
                if status == TaskStatus.TODO:
                    deadline = now + timedelta(days=3 + i)
                elif status == TaskStatus.IN_PROGRESS:
                    deadline = now + timedelta(days=1 + i)
                else:  # DONE
                    deadline = now - timedelta(days=1 + i)

                task = Task(
                    id=uuid.uuid4(),
                    title=f"Task {task_counter} for {assignee.full_name}",
                    description=(
                        f"This is demo task #{task_counter} assigned to "
                        f"{assignee.full_name} with status {status.value}."
                    ),
                    status=status,
                    deadline=deadline,
                    assignee_id=assignee.id,
                    created_by_id=creator.id,
                )

                session.add(task)
                task_counter += 1

        await session.commit()

        print("Database initialized with seed data")
        print(f"Created {len(users)} users and {task_counter - 1} demo tasks")



if __name__ == "__main__":
    asyncio.run(init_db())
