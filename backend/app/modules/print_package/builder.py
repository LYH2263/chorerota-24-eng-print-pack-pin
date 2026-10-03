"""打印包纯拼装函数：不读钟、不读库、不碰文件系统，输出只由入参决定。"""

import json

DAY_TITLES: tuple[str, ...] = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

CELL_FIELDS = ("day", "column_title", "task_id", "task_title", "member_id", "member_name")


def column_titles(days: int = 7) -> list[dict]:
    """day 0..days-1 的列标题，例如 [{"day": 0, "title": "周一"}, ...]。"""
    return [{"day": d, "title": DAY_TITLES[d]} for d in range(days)]


def build_print_package(*, print_id: int, printed_at: str, week: dict,
                        household: str, assignments: list[dict],
                        days: int = 7) -> dict:
    """把看板形状的 assignments 装配成打印包 dict。

    - assignments 元素需含 day/task_id/task_title/member_id/member_name
      （与 GET /api/weeks/{id}/board 的格位形状一致）。
    - 格位按 (day, task_id) 确定性排序。
    - day 超出 range(days) 抛 ValueError。
    """
    for a in assignments:
        if a["day"] not in range(days):
            raise ValueError(f"day out of range: {a['day']}")

    cells = []
    for a in sorted(assignments, key=lambda x: (x["day"], x["task_id"])):
        day = a["day"]
        cells.append({
            "day": day,
            "column_title": DAY_TITLES[day],
            "task_id": a["task_id"],
            "task_title": a["task_title"],
            "member_id": a["member_id"],
            "member_name": a["member_name"],
        })

    return {
        "schema_version": 1,
        "print_id": print_id,
        "printed_at": printed_at,
        "week": {"id": week["id"], "label": week["label"]},
        "household": household,
        "column_titles": column_titles(days),
        "cells": cells,
    }


def encode_package(package: dict) -> bytes:
    """打印包序列化为 UTF-8 字节：中文不转义、缩进 2、末尾换行。"""
    text = json.dumps(package, ensure_ascii=False, indent=2)
    return (text + "\n").encode("utf-8")
