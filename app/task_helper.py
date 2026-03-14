from datetime import datetime, date
from flask import current_app
from .models import db, GilTask


def create_task_record(
    case_id: int,
    user_id: int,
    title: str,
    description: str | None = None,
    due_date=None,
    status: str = "פתוחה",
    creator_id: int | None = None,
    commit: bool = False
):
    """
    Generic helper to create a task in gil_task.

    Args:
        case_id: insured/case id
        user_id: assignee user id
        title: task title
        description: optional task description
        due_date: date or YYYY-MM-DD string
        status: defaults to 'פתוחה'
        creator_id: creator user id
        commit: if True, commit immediately. Usually keep False.

    Returns:
        GilTask row or None on failure
    """
    try:
        if not case_id:
            raise ValueError("case_id is required")
        if not user_id:
            raise ValueError("user_id is required")
        if not (title or "").strip():
            raise ValueError("title is required")

        # normalize due_date
        if isinstance(due_date, str) and due_date.strip():
            due_date = datetime.strptime(due_date.strip(), "%Y-%m-%d").date()
        elif due_date == "":
            due_date = None

        row = GilTask(
            case_id=int(case_id),
            user_id=int(user_id),
            title=(title or "").strip(),
            description=(description or "").strip() or None,
            due_date=due_date if isinstance(due_date, date) else None,
            status=(status or "פתוחה").strip(),
            creator_id=creator_id
        )

        db.session.add(row)

        if commit:
            db.session.commit()

        return row

    except Exception:
        current_app.logger.exception("create_task_record failed")
        return None