import pytest

from src.repositories.task_repository import TaskRepository


@pytest.mark.asyncio
async def test_count_user_tasks(db_session):
    user_id = "user-pagination-test"
    await db_session.execute(
        __import__("sqlalchemy").text(
            "INSERT INTO users (id, email, name, \"createdAt\", \"updatedAt\") "
            "VALUES (:id, :email, :name, NOW(), NOW())"
        ),
        {"id": user_id, "email": "pagination@test.local", "name": "Pagination"},
    )
    for index in range(3):
        await db_session.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO tasks (id, user_id, status, generated_clips_ids, created_at, updated_at) "
                "VALUES (:id, :user_id, 'completed', '{}', NOW(), NOW())"
            ),
            {"id": f"task-{index}", "user_id": user_id},
        )
    await db_session.commit()

    total = await TaskRepository.count_user_tasks(db_session, user_id)
    assert total == 3

    page = await TaskRepository.get_user_tasks(
        db_session, user_id, limit=2, offset=0
    )
    assert len(page) == 2

    tail = await TaskRepository.get_user_tasks(
        db_session, user_id, limit=2, offset=2
    )
    assert len(tail) == 1
