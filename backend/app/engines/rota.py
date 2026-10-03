"""Round-robin weekly chore assignments + swap legality."""

def build_week_slots(member_ids: list[int], task_ids: list[int], days: int = 7) -> list[dict]:
    """Assign each (day, task) to members in round-robin by task then day."""
    if not member_ids or not task_ids:
        return []
    slots = []
    idx = 0
    for day in range(days):
        for tid in task_ids:
            mid = member_ids[idx % len(member_ids)]
            slots.append({"day": day, "task_id": tid, "member_id": mid})
            idx += 1
    return slots


def swap_legal(slots: list[dict], a_day: int, a_task: int, b_day: int, b_task: int) -> dict:
    """Two slots may swap only if both exist, different assignees, same week grid."""
    def find(day, task):
        for s in slots:
            if s["day"] == day and s["task_id"] == task:
                return s
        return None
    sa, sb = find(a_day, a_task), find(b_day, b_task)
    if sa is None or sb is None:
        return {"ok": False, "reason": "slot_missing"}
    if sa["member_id"] == sb["member_id"]:
        return {"ok": False, "reason": "same_assignee"}
    if a_day == b_day and a_task == b_task:
        return {"ok": False, "reason": "same_slot"}
    return {
        "ok": True,
        "reason": "",
        "a_member": sa["member_id"],
        "b_member": sb["member_id"],
    }


def apply_swap(slots: list[dict], a_day: int, a_task: int, b_day: int, b_task: int) -> list[dict]:
    check = swap_legal(slots, a_day, a_task, b_day, b_task)
    if not check["ok"]:
        raise ValueError(check["reason"])
    out = [dict(s) for s in slots]
    ia = next(i for i, s in enumerate(out) if s["day"] == a_day and s["task_id"] == a_task)
    ib = next(i for i, s in enumerate(out) if s["day"] == b_day and s["task_id"] == b_task)
    out[ia]["member_id"], out[ib]["member_id"] = out[ib]["member_id"], out[ia]["member_id"]
    return out
