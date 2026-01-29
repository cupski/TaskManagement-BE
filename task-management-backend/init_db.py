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
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
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
        ]
        
        for user in users:
            session.add(user)
        
        await session.commit()
        
        # Create demo tasks
        for user in users:
            tasks = [
                Task(
                    id=uuid.uuid4(),
                    title="Design Database Schema",
                    description="Create comprehensive ERD showing relationships between users, tasks, and other entities. Include proper indexing strategy.",
                    status=TaskStatus.TODO,
                    deadline=datetime.now() + timedelta(days=3),
                    assignee_id=user.id,
                    created_by_id=users[0].id,
                ),
                Task(
                    id=uuid.uuid4(),
                    title="Implement API Endpoints",
                    description="FastAPI CRUD operations for tasks and users. Include proper validation and error handling.",
                    status=TaskStatus.IN_PROGRESS,
                    deadline=datetime.now() + timedelta(days=5),
                    assignee_id=user.id,
                    created_by_id=users[0].id,
                ),
                Task(
                    id=uuid.uuid4(),
                    title="Setup Development Environment",
                    description="Docker configuration, dependencies installation, and database setup.",
                    status=TaskStatus.DONE,
                    deadline=datetime.now() - timedelta(days=1),
                    assignee_id=user.id,
                    created_by_id=users[1].id,
                ),
            ]
            
            for task in tasks:
                session.add(task)
        
        await session.commit()
        print("Database initialized with seed data")
        print(f"Created {len(users)} users and {len(users) * 3} demo tasks")


if __name__ == "__main__":
    asyncio.run(init_db())
