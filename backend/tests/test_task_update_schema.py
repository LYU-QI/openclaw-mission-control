from app.schemas.tasks import TaskUpdate


def test_task_update_blank_comment_normalizes_to_none() -> None:
    payload = TaskUpdate(comment="   ")

    assert payload.comment is None
