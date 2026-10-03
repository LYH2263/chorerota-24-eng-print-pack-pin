# Chorerota · 家庭值日轮转

底座：成员+任务 → round-robin 生成周表 → 申请对调 → 确认改表。

| 服务 | 端口 |
| --- | --- |
| 前端 | 5100 |
| API | 10100 |

```bash
docker compose up --build
pytest backend/app/tests
```

种子含 clean/dirty。0-1 空桩：`streak_badge` / `skip_week` / `chore_photo`。

## 看板打印包

- `POST /api/weeks/{id}/print`：拼装打印包落盘（`$DATA_DIR/print_packages/week_<id>.json`，含列标题、格位清单、打印瞬间家庭名），并写入打印履历行（编号、周、打印瞬间家庭名）。两者同事务同生共死；打印不改 assignments。
- `GET /api/prints?week_id=<id>`：打印履历列表。口径已拍板为**追加**（同周重印新增履历行，不覆盖），履历列表的 `policy` 与包文件的 `history_policy` 同钉此口径。
- 打印后只改家庭名或 force 重生成而不重印：包文件与履历保持打印瞬间值；重新打印后才与现行看板对齐。
- 核验：`docker compose exec backend python -m app.verify_print <week_id> --api http://localhost:10100`，逐格比对包内格位与看板接口，并核对履历中的家庭名快照；只读，连跑两次退出码均为 0，不一致为 1。

源文件：打印 API `app/print_api.py` · 拼装函数 `app/printing.py` · 核验命令 `app/verify_print.py`。
