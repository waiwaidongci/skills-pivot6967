# 002 渠道服务费月结表结构

应用启动时以 SQLAlchemy 模型自动补建下列新表，既有表不受影响。

- `settlement_runs` 结算任务：数据批次、结算月份、租约与状态（queued / running / posted / superseded / failed）。
- `settlement_periods` 每月一行的入账状态：最近入账的数据批次与渠道累计（分），入账时行级加锁串行化。
- `settlement_entries` 入账批次头：`(period, dataset_id)` 唯一，中断重试不会重复入账。
- `settlement_lines` 逐人逐渠道明细（分），每名确认学员合计恰为 100 分。
- `settlement_totals` 每渠道相对上次入账的正负差额与累计（分），与明细在同一事务写入。

新旧批次一律按数据批次入库先后（`datasets.id`）认定；`dataset_id` 不大于 `last_dataset_id` 的任务记为 superseded，旧批不能倒冲。
