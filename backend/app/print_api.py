"""打印 API：触发打印（落包文件 + 写履历行）与打印履历列表。"""
from fastapi import APIRouter, HTTPException

from app.db import connect
from app.printing import HISTORY_POLICY, record_print

router = APIRouter()


@router.post("/api/weeks/{week_id}/print")
def print_week(week_id: int):
    conn = connect()
    try:
        return record_print(conn, week_id)
    except KeyError:
        raise HTTPException(404, "week not found")
    finally:
        conn.close()


@router.get("/api/prints")
def list_prints(week_id: int | None = None):
    conn = connect()
    if week_id is None:
        rows = [dict(r) for r in conn.execute("SELECT * FROM print_history ORDER BY id DESC")]
    else:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM print_history WHERE week_id=? ORDER BY id DESC", (week_id,))]
    conn.close()
    return {"policy": HISTORY_POLICY, "rows": rows}
