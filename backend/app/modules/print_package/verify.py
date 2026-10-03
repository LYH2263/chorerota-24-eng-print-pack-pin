"""打印包核验命令（只读）。

把指定打印包内格位与现行看板接口逐格比对，并核对履历行中的家庭名快照。
只读 GET，确定性：连跑两次结果一致，无漂移退出码 0。

退出码：0=一致；1=发现漂移；2=传输/参数错误。
用法：
  python -m app.modules.print_package.verify \
      --base-url http://localhost:10100 --print-id 1
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

from .builder import DAY_TITLES

CELL_COMPARE_FIELDS = ("member_id", "member_name", "task_title")


class VerifyError(RuntimeError):
    """传输层/HTTP/解析问题，区别于业务漂移。"""


def fetch_json(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise VerifyError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise VerifyError(f"network error for {url}: {e.reason}") from e
    except TimeoutError as e:
        raise VerifyError(f"timeout for {url}") from e
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise VerifyError(f"invalid JSON from {url}: {e}") from e


def _index_cells(cells, source: str, problems: list) -> dict:
    indexed = {}
    for c in cells:
        key = (c["day"], c["task_id"])
        if key in indexed:
            problems.append(f"duplicate cell key in {source}: (day={key[0]}, task_id={key[1]})")
        indexed[key] = c
    return indexed


def verify_print(base_url: str, print_id: int, timeout: float = 5.0) -> list:
    """返回问题字符串列表；空列表表示包、履历、现行看板完全一致。"""
    base = base_url.rstrip("/")
    record = fetch_json(f"{base}/api/print-records/{print_id}", timeout)
    package = fetch_json(f"{base}/api/print-records/{print_id}/package", timeout)
    week_id = record["week_id"]
    board = fetch_json(f"{base}/api/weeks/{week_id}/board", timeout)

    problems = []

    # 履历行家庭名快照必须与包内字段一致。
    if record.get("household") != package.get("household"):
        problems.append(
            f"household snapshot mismatch: record={record.get('household')!r} "
            f"package={package.get('household')!r}")
    if week_id != package.get("week", {}).get("id"):
        problems.append(
            f"week_id mismatch: record={week_id} package={package.get('week', {}).get('id')}")

    # 列标题应为周一..周日。
    expected_titles = [{"day": d, "title": DAY_TITLES[d]} for d in range(7)]
    if package.get("column_titles") != expected_titles:
        problems.append(f"column_titles mismatch: {package.get('column_titles')!r}")

    pkg = _index_cells(package.get("cells", []), "package", problems)
    brd = _index_cells(board.get("assignments", []), "board", problems)

    pkg_keys, brd_keys = set(pkg), set(brd)
    for key in sorted(pkg_keys - brd_keys):
        problems.append(f"cell in package but missing on board: (day={key[0]}, task_id={key[1]})")
    for key in sorted(brd_keys - pkg_keys):
        problems.append(f"cell on board but not in package: (day={key[0]}, task_id={key[1]})")

    for key in sorted(pkg_keys & brd_keys):
        p, b = pkg[key], brd[key]
        day, task_id = key
        if p.get("column_title") != DAY_TITLES[day]:
            problems.append(
                f"cell (day={day}, task_id={task_id}) column_title mismatch: "
                f"{p.get('column_title')!r} != {DAY_TITLES[day]!r}")
        field_diffs = []
        for f in CELL_COMPARE_FIELDS:
            if p.get(f) != b.get(f):
                field_diffs.append(f"{f} package={p.get(f)!r} board={b.get(f)!r}")
        if field_diffs:
            problems.append(
                f"cell (day={day}, task_id={task_id}) drift: " + "; ".join(field_diffs))

    return problems


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="核验打印包与现行看板是否一致（只读）")
    p.add_argument("--base-url", required=True, help="API 根地址，如 http://localhost:10100")
    p.add_argument("--print-id", required=True, type=int, help="打印履历编号")
    p.add_argument("--timeout", type=float, default=5.0, help="HTTP 超时秒数")
    return p


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        problems = verify_print(args.base_url, args.print_id, args.timeout)
    except VerifyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if problems:
        for msg in problems:
            print(msg, file=sys.stderr)
        return 1
    print(f"OK print_id={args.print_id} cells checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
