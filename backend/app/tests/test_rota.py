from app.engines.rota import build_week_slots, swap_legal, apply_swap

def test_round_robin_covers_grid():
    slots = build_week_slots([1, 2, 3], [10, 20], days=7)
    assert len(slots) == 14
    assert slots[0]["member_id"] == 1
    assert slots[1]["member_id"] == 2
    assert slots[3]["member_id"] == 1  # wraps

def test_swap_rejects_same_assignee():
    slots = [{"day": 0, "task_id": 1, "member_id": 9}, {"day": 1, "task_id": 1, "member_id": 9}]
    r = swap_legal(slots, 0, 1, 1, 1)
    assert r["ok"] is False and r["reason"] == "same_assignee"

def test_apply_swap_exchanges():
    slots = build_week_slots([1, 2], [10], days=2)
    out = apply_swap(slots, 0, 10, 1, 10)
    assert out[0]["member_id"] == 2 and out[1]["member_id"] == 1
