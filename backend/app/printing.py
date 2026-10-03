"""看板打印包：拼装函数、原子落盘与打印事务。

口径（已拍板：追加）——每次打印新增一行打印履历，同周可有多行；
包文件记录产生它的履历编号 print_id 与 history_policy，
履历列表接口与包文件同钉 HISTORY_POLICY，核验命令据此比对。
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.db import data_dir

HISTORY_POLICY = "append"  # 追加：同周重印新增履历行，不覆盖历史行

DAY_HEADERS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def column_headers(days: int) -> list[str]:
    """列标题：前 7 列取周几，超出顺延「第 N 天」。"""
    return [DAY_HEADERS[i] if i < len(DAY_HEADERS) else f"第{i + 1}天" for i in range(days)]


def packages_dir(base=None) -> Path:
    return Path(base) if base is not None else data_dir() / "print_packages"


def package_path(week_id: int, base=None) -> Path:
    return packages_dir(base) / f"week_{week_id}.json"


def build_print_package(conn, week_id: int, *, print_id: int, printed_at: str) -> dict:
    """拼装指定周的打印包：列标题、格位清单、打印瞬间家庭名。只读，不改 assignments。"""
    week = conn.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if week is None:
        raise KeyError(f"week {week_id} not found")
    row = conn.execute("SELECT value FROM settings WHERE key='household'").fetchone()
    household = row["value"] if row else ""
    assigns = conn.execute(
        """SELECT a.day, a.task_id, a.member_id,
                  m.name AS member_name, t.title AS task_title
           FROM assignments a
           LEFT JOIN members m ON m.id = a.member_id
           LEFT JOIN tasks t ON t.id = a.task_id
           WHERE a.week_id=? ORDER BY a.day, a.task_id""",
        (week_id,)).fetchall()
    slots = [{
        "day": a["day"],
        "task_id": a["task_id"],
        "task_title": a["task_title"] or "?",
        "member_id": a["member_id"],
        "member_name": a["member_name"] or "?",
    } for a in assigns]
    days = max((a["day"] for a in assigns), default=-1) + 1
    return {
        "print_id": print_id,
        "week_id": week_id,
        "week_label": week["label"],
        "household": household,
        "printed_at": printed_at,
        "history_policy": HISTORY_POLICY,
        "columns": column_headers(days),
        "slots": slots,
    }


def write_package(pkg: dict, path) -> None:
    """原子落盘：先写临时文件再替换，避免半截包文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_package(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def record_print(conn, week_id: int) -> dict:
    """打印：同一事务内写履历行 + 落包文件，任一步失败两者都不留。

    禁止只落文件不写履历，或只写履历不落文件。不改 assignments。
    """
    if conn.execute("SELECT 1 FROM weeks WHERE id=?", (week_id,)).fetchone() is None:
        raise KeyError(f"week {week_id} not found")
    row = conn.execute("SELECT value FROM settings WHERE key='household'").fetchone()
    household = row["value"] if row else ""
    printed_at = datetime.now(timezone.utc).isoformat()
    path = package_path(week_id)
    prev_isolation = conn.isolation_level
    conn.isolation_level = None  # 手动事务，把履历行与包文件绑成同生共死
    wrote = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "INSERT INTO print_history(week_id,household,printed_at,policy) VALUES (?,?,?,?)",
                (week_id, household, printed_at, HISTORY_POLICY))
            pkg = build_print_package(conn, week_id, print_id=cur.lastrowid, printed_at=printed_at)
            write_package(pkg, path)
            wrote = True
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            if wrote:
                try:
                    path.unlink()
                except OSError:
                    pass
            raise
    finally:
        conn.isolation_level = prev_isolation
    return pkg
