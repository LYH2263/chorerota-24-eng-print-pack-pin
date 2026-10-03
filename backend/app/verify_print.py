"""核验命令：打印包 vs 看板接口逐格比对，并核对打印履历中的家庭名快照。

用法: python -m app.verify_print <week_id> [--api http://localhost:10100] [--packages-dir DIR]
只读：不改任何状态，连跑结果一致；全部通过退出码 0，否则 1。
"""
import argparse
import json
import os
import sys
import urllib.request

from app.printing import HISTORY_POLICY, column_headers, package_path


def verify(week_id: int, *, fetch_json, packages_dir=None) -> list[str]:
    """逐项核验，返回问题清单（空 = 通过）。fetch_json(path) 调看板/履历接口。"""
    path = package_path(week_id, packages_dir)
    if not path.exists():
        return [f"包文件不存在: {path}"]
    try:
        pkg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"包文件不可读: {e}"]
    try:
        board = fetch_json(f"/api/weeks/{week_id}/board")
        prints = fetch_json(f"/api/prints?week_id={week_id}")
    except Exception as e:
        return [f"接口不可达: {e}"]

    errors = []

    # 1) 格位逐格比对：包内 (day, task_id) -> member_id vs 看板接口
    pkg_cells = {(s["day"], s["task_id"]): s["member_id"] for s in pkg.get("slots", [])}
    board_cells = {(a["day"], a["task_id"]): a["member_id"] for a in board.get("assignments", [])}
    for cell in sorted(pkg_cells.keys() | board_cells.keys()):
        if cell not in pkg_cells:
            errors.append(f"格位{cell} 包内缺失（看板 member={board_cells[cell]}）")
        elif cell not in board_cells:
            errors.append(f"格位{cell} 看板缺失（包内 member={pkg_cells[cell]}）")
        elif pkg_cells[cell] != board_cells[cell]:
            errors.append(f"格位{cell} 成员不一致: 包内={pkg_cells[cell]} 看板={board_cells[cell]}")

    # 2) 列标题与看板天数一致
    days = max((d for d, _ in board_cells), default=-1) + 1
    if pkg.get("columns") != column_headers(days):
        errors.append("列标题与看板天数不一致")

    # 3) 履历核对：口径同钉，最新履历行的家庭名快照与编号须与包内一致
    if prints.get("policy") != HISTORY_POLICY:
        errors.append(f"履历口径不符: {prints.get('policy')!r} != {HISTORY_POLICY!r}")
    if pkg.get("history_policy") != HISTORY_POLICY:
        errors.append(f"包内口径不符: {pkg.get('history_policy')!r} != {HISTORY_POLICY!r}")
    rows = prints.get("rows", [])
    if not rows:
        errors.append("履历缺失：有包文件却无履历行")
    else:
        latest = max(rows, key=lambda r: r["id"])  # 追加口径：编号最大者即最近一次打印
        if latest.get("household") != pkg.get("household"):
            errors.append(f"家庭名快照不符: 履历={latest.get('household')!r} 包内={pkg.get('household')!r}")
        if latest.get("id") != pkg.get("print_id"):
            errors.append(f"履历编号不符: 履历={latest.get('id')} 包内={pkg.get('print_id')}")
    return errors


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="verify_print", description="核验打印包与看板接口、打印履历是否一致（只读）")
    p.add_argument("week_id", type=int)
    p.add_argument("--api", default=os.environ.get("API_BASE", "http://localhost:10100"))
    p.add_argument("--packages-dir", default=None, help="包文件目录，默认 $DATA_DIR/print_packages")
    args = p.parse_args(argv)

    def fetch_json(path):
        with urllib.request.urlopen(args.api + path, timeout=10) as resp:
            return json.load(resp)

    errors = verify(args.week_id, fetch_json=fetch_json, packages_dir=args.packages_dir)
    if errors:
        for e in errors:
            print(f"FAIL {e}", file=sys.stderr)
        return 1
    print(f"OK week={args.week_id} 打印包与看板、履历一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
