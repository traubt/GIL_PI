from . import db
from sqlalchemy import text


def get_urgent_cases_received(from_date, to_date):
    sql = text("""
        SELECT
            ref_number AS `מספר הפניה`,
            TRIM(CONCAT(COALESCE(first_name, ''), ' ', COALESCE(last_name, ''))) AS `שם מבוטח`,
            id_number AS `תעודת זהות`,
            claim_number AS `מספר תביעה`,
            insurance AS `חברת ביטוח`,
            status AS `סטטוס`,
            case_status AS `סטטוס תיק`,
            investigator AS `חוקר`,
            received_date AS `תאריך קבלה`
        FROM gil_insured
        WHERE received_date BETWEEN :from_date AND :to_date
          AND severity = 'דחוף'
        ORDER BY received_date DESC, id DESC
    """)

    rows = db.session.execute(sql, {
        "from_date": from_date,
        "to_date": to_date
    }).mappings().all()

    return [dict(row) for row in rows]

def get_open_tasks_report(from_date, to_date):
    sql = text("""
        SELECT
            t.id AS 'מספר משימה',
            gi.ref_number AS 'מספר הפניה',
            TRIM(CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, ''))) AS 'שם מלא',
            t.title AS 'כותרת משימה',
            t.description AS 'תיאור',
            t.due_date AS 'תאריך יעד',
            t.status AS 'סטטוס',
            t.source AS 'מקור',
            t.date_created AS 'תאריך יצירה',
            t.date_modified AS 'תאריך עדכון'
        FROM gil_tasks t
        LEFT JOIN gil_insured gi
            ON gi.id = t.case_id
        LEFT JOIN toc_users u
            ON u.id = t.user_id
        WHERE t.due_date BETWEEN :from_date AND :to_date
          AND COALESCE(t.status, '') NOT IN ('הושלמה', 'סגורה', 'completed', 'closed')
        ORDER BY t.due_date ASC, t.id DESC
    """)

    rows = db.session.execute(sql, {
        "from_date": from_date,
        "to_date": to_date
    }).mappings().all()

    return [dict(row) for row in rows]