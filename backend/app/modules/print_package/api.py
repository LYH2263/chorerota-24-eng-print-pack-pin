"""打印包 API：对指定周生成不可变打印包文件并追加打印履历。

追加口径：每次 POST /weeks/{id}/print 新增一条 print_records 行和一个
print_packages/print_{id}.json；旧行旧文件永不改动。打印不触碰 assignments。
履历行与包文件同生共灭（见 print_week 的补偿逻辑），杜绝只落一边。
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.db import connect, db_path
from .builder import build_print_package, encode_package

router = APIRouter(prefix="/api")


def _data_dir() -> Path:
    # db_path() 会确保 DATA_DIR 存在；包目录就建在它下面（Docker 卷 /data）。
    return db_path().parent


def _packages_dir() -> Path:
    d = _data_dir() / "print_packages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _record_dict(row) -> dict:
    return {
        "id": row["id"],
        "week_id": row["week_id"],
        "week_label": row["week_label"],
        "household": row["household"],
        "package_path": row["package_path"],
        "created_at": row["created_at"],
    }


def _load_board_snapshot(c, week_id: int):
    """同一连接上读取周、格位（含成员名/任务名）与家庭名快照。"""
    week = c.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if not week:
        return None, [], ""
    assigns = [dict(r) for r in c.execute(
        "SELECT * FROM assignments WHERE week_id=?", (week_id,))]
    members = {r["id"]: r["name"] for r in c.execute("SELECT id,name FROM members")}
    tasks = {r["id"]: r["title"] for r in c.execute("SELECT id,title FROM tasks")}
    for a in assigns:
        a["member_name"] = members.get(a["member_id"], "?")
        a["task_title"] = tasks.get(a["task_id"], "?")
    hrow = c.execute("SELECT value FROM settings WHERE key='household'").fetchone()
    household = hrow["value"] if hrow else ""
    return week, assigns, household


@router.post("/weeks/{week_id}/print", status_code=201)
def print_week(week_id: int):
    packages_dir = _packages_dir()
    c = connect()
    try:
        week, assigns, household = _load_board_snapshot(c, week_id)
        if not week:
            raise HTTPException(404, "week not found")

        now = datetime.now(timezone.utc).isoformat()
        rel_path_placeholder = ""
        cur = c.execute(
            "INSERT INTO print_records(week_id,week_label,household,package_path,created_at)"
            " VALUES (?,?,?,?,?)",
            (week_id, week["label"], household, rel_path_placeholder, now))
        print_id = cur.lastrowid
        rel_path = f"print_packages/print_{print_id}.json"

        package = build_print_package(
            print_id=print_id,
            printed_at=now,
            week={"id": week["id"], "label": week["label"]},
            household=household,
            assignments=assigns)
        payload = encode_package(package)

        # 先落临时文件（事务未提交，失败可整体回滚，无履历行残留）。
        tmp_path = packages_dir / f".print_{print_id}.{uuid.uuid4().hex}.tmp"
        try:
            fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            try:
                os.write(fd, payload)
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            c.rollback()
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(500, "package_write_failed")

        c.execute("UPDATE print_records SET package_path=? WHERE id=?",
                  (rel_path, print_id))
        c.commit()  # 履历行先持久化

        try:
            os.replace(tmp_path, packages_dir / f"print_{print_id}.json")
        except OSError:
            # 改名失败：补偿删除履历行，保证不会只写履历不落文件。
            c.execute("DELETE FROM print_records WHERE id=?", (print_id,))
            c.commit()
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(500, "package_replace_failed")

        row = c.execute("SELECT * FROM print_records WHERE id=?", (print_id,)).fetchone()
        return _record_dict(row)
    finally:
        c.close()


@router.get("/print-records")
def list_print_records(week_id: int | None = None):
    c = connect()
    try:
        if week_id is None:
            rows = c.execute("SELECT * FROM print_records ORDER BY id DESC").fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM print_records WHERE week_id=? ORDER BY id DESC",
                (week_id,)).fetchall()
        return [_record_dict(r) for r in rows]
    finally:
        c.close()


def _get_record_or_404(c, print_id: int):
    row = c.execute("SELECT * FROM print_records WHERE id=?", (print_id,)).fetchone()
    if not row:
        raise HTTPException(404, "print record not found")
    return row


@router.get("/print-records/{print_id}")
def get_print_record(print_id: int):
    c = connect()
    try:
        return _record_dict(_get_record_or_404(c, print_id))
    finally:
        c.close()


@router.get("/print-records/{print_id}/package")
def get_print_package(print_id: int):
    c = connect()
    try:
        row = _get_record_or_404(c, print_id)
    finally:
        c.close()
    path = _data_dir() / row["package_path"]
    # 防御：包路径不得逃出包目录。
    if not path.resolve().is_relative_to(_packages_dir().resolve()):
        raise HTTPException(400, "invalid package path")
    if not path.is_file():
        raise HTTPException(410, "package_file_missing")
    return json.loads(path.read_text(encoding="utf-8"))
