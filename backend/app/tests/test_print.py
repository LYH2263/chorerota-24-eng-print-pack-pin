"""打印包 / 打印履历 / 核验命令的端到端测试。

直接调用接口函数（不起 HTTP 服务），核验器注入同样的取数函数。
"""
import json
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi import HTTPException

from app import seed
from app.db import connect
from app.main import week_board, generate, put_settings, GenBody
from app.print_api import print_week, list_prints
from app.printing import HISTORY_POLICY, package_path, read_package
from app.verify_print import verify


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    seed.init_db()
    return tmp_path


def fetch_json(path):
    """与核验命令相同的取数路径，只是直接调接口函数。"""
    u = urlparse(path)
    if u.path.startswith("/api/weeks/"):
        return week_board(int(u.path.split("/")[3]))
    if u.path == "/api/prints":
        q = parse_qs(u.query)
        return list_prints(week_id=int(q["week_id"][0]) if "week_id" in q else None)
    raise ValueError(path)


def test_print_writes_package_and_history_together(env):
    generate(1, GenBody())
    pkg = print_week(1)
    path = package_path(1)
    assert path.exists(), "落履历必须同时落包文件"
    on_disk = read_package(path)
    assert on_disk == pkg
    assert on_disk["household"] == "绿纸之家"
    assert on_disk["history_policy"] == HISTORY_POLICY == "append"
    assert on_disk["columns"] == ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    assert len(on_disk["slots"]) == 21  # 7 天 × 3 个 clean 任务
    prints = list_prints(week_id=1)
    assert prints["policy"] == HISTORY_POLICY  # 履历列表与包文件同钉口径
    assert len(prints["rows"]) == 1
    row = prints["rows"][0]
    assert row["id"] == on_disk["print_id"]
    assert row["week_id"] == 1
    assert row["household"] == "绿纸之家"


def test_print_does_not_change_assignments(env):
    generate(1, GenBody())
    before = week_board(1)["assignments"]
    print_week(1)
    assert week_board(1)["assignments"] == before


def test_snapshot_kept_until_reprint_then_appended(env):
    generate(1, GenBody())
    pkg1 = print_week(1)
    put_settings({"household": "新名字"})
    generate(1, GenBody(days=5))  # force 重生成，不重新打印
    # 包文件与履历保持打印瞬间值
    assert read_package(package_path(1)) == pkg1
    rows = list_prints(week_id=1)["rows"]
    assert len(rows) == 1 and rows[0]["household"] == "绿纸之家"
    # 重新打印后才与现行看板对齐，并追加履历（不覆盖）
    pkg2 = print_week(1)
    assert pkg2["household"] == "新名字"
    assert pkg2["print_id"] != pkg1["print_id"]
    assert len(pkg2["slots"]) == 15  # 5 天 × 3 任务
    rows = list_prints(week_id=1)["rows"]
    assert len(rows) == 2
    assert {r["household"] for r in rows} == {"绿纸之家", "新名字"}


def test_verify_ok_and_idempotent(env):
    generate(1, GenBody())
    print_week(1)
    assert verify(1, fetch_json=fetch_json) == []
    assert verify(1, fetch_json=fetch_json) == []  # 连跑两次退出码均为 0


def test_verify_detects_drift_until_reprint(env):
    generate(1, GenBody())
    print_week(1)
    generate(1, GenBody(days=5))  # 看板变了，包未重印
    assert verify(1, fetch_json=fetch_json) != []
    print_week(1)
    assert verify(1, fetch_json=fetch_json) == []


def test_file_failure_rolls_back_history(env, monkeypatch):
    generate(1, GenBody())

    def boom(pkg, path):
        raise OSError("disk full")

    monkeypatch.setattr("app.printing.write_package", boom)
    with pytest.raises(OSError):
        print_week(1)
    assert list_prints(week_id=1)["rows"] == [], "只落文件不写履历的反向：文件失败则履历也不留"
    assert not package_path(1).exists()


def test_history_failure_leaves_no_file(env):
    generate(1, GenBody())
    conn = connect()
    conn.execute("DROP TABLE print_history")
    conn.commit()
    conn.close()
    with pytest.raises(Exception):
        print_week(1)
    assert not package_path(1).exists(), "履历写不进去则包文件也不留"


def test_print_unknown_week_404(env):
    with pytest.raises(HTTPException) as exc:
        print_week(999)
    assert exc.value.status_code == 404
