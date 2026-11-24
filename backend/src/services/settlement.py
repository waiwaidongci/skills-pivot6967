"""渠道服务费月结的排队、计算与一次性入账。"""

import logging
from datetime import date, timedelta
from sqlalchemy import and_, or_, select
from src.config.database import Session
from src.constants.enums import Settlement
from src.domain.settlement import assess
from src.domain.spec import CHANNELS
from src.models.settlement import SettlementEntry, SettlementLine, SettlementPeriod, SettlementRun, SettlementTotal
from src.models.source import Dataset
from src.services.audit import record
from src.utils.time import now

log = logging.getLogger(__name__)


def valid_period(period):
    try:
        if not isinstance(period, str) or date.fromisoformat(f'{period}-01').isoformat()[:7] != period:
            raise ValueError
    except ValueError:
        raise ValueError('结算月份须为有效的 YYYY-MM') from None
    return period


def claim_settlement():
    stamp = now()
    with Session.begin() as db:
        query = select(SettlementRun).where(
            or_(SettlementRun.status == Settlement.QUEUED,
                and_(SettlementRun.status == Settlement.RUNNING, SettlementRun.lease_until < stamp)))
        job = db.scalar(query.order_by(SettlementRun.id).limit(1).with_for_update(skip_locked=True))
        if job is None:
            return None
        if job.attempt >= 3:
            job.status = Settlement.FAILED
            job.error = '后台进程多次中断，请重新发起结算'
            job.finished_at = stamp
            record(db, 'worker', 'settlement.failed', job.id, reason=job.error)
            return None
        job.status = Settlement.RUNNING
        job.attempt += 1
        job.lease_until = stamp + timedelta(minutes=3)
        rows = db.get(Dataset, job.dataset_id).rows
        return job.id, job.attempt, rows, job.period


def execute_settlement(lease):
    job_id, attempt, rows, period = lease
    failure = None
    try:
        lines, totals, learner_count = assess(rows, period)
    except ValueError as error:
        failure = str(error)[:500]
    except Exception:
        log.exception('Settlement %s failed', job_id)
        failure = '结算失败，请检查字段口径后重试'
    with Session.begin() as db:
        job = db.get(SettlementRun, job_id, with_for_update=True)
        if job.attempt != attempt or job.status != Settlement.RUNNING:
            return
        job.lease_until = None
        job.finished_at = now()
        if failure:
            job.status = Settlement.FAILED
            job.error = failure
            record(db, 'worker', 'settlement.failed', job.id, attempt=attempt, reason=failure)
            return
        post(db, job, lines, totals, learner_count)


def post(db, job, lines, totals, learner_count):
    """在同一事务内写入明细与合计；按入库先后认新旧，只结正负差额。

    调用方须持有事务。月份状态行加锁串行化并发入账；(period, dataset_id)
    唯一约束兜底，中断重试不会重复入账。
    """
    state = db.get(SettlementPeriod, job.period, with_for_update=True)
    if state is None:
        state = SettlementPeriod(period=job.period, last_dataset_id=0, totals={})
        db.add(state)
        db.flush()
    existing = db.scalar(select(SettlementEntry).where(SettlementEntry.period == job.period,
                                                       SettlementEntry.dataset_id == job.dataset_id))
    if existing:
        # 同一批次同一月份只入账一次，重试直接认领旧账。
        job.status = Settlement.POSTED
        job.entry_id = existing.id
        record(db, 'worker', 'settlement.posted', job.id, entry_id=existing.id, note='该批次已入账，跳过重复结算')
        return
    if job.dataset_id <= state.last_dataset_id:
        # 旧批不能倒冲：已有同等或更新批次入账。
        job.status = Settlement.SUPERSEDED
        record(db, 'worker', 'settlement.superseded', job.id, period=job.period,
               dataset_id=job.dataset_id, last_dataset_id=state.last_dataset_id)
        return
    if learner_count == 0 and state.last_dataset_id == 0:
        job.status = Settlement.FAILED
        job.error = '该批次在该结算月份没有确认学员'
        record(db, 'worker', 'settlement.failed', job.id, reason=job.error)
        return
    entry = SettlementEntry(period=job.period, dataset_id=job.dataset_id, settlement_id=job.id,
                            learner_count=learner_count, author=job.author)
    db.add(entry)
    db.flush()
    for line in lines:
        db.add(SettlementLine(entry_id=entry.id, **line))
    previous = state.totals or {}
    for channel in CHANNELS:
        db.add(SettlementTotal(entry_id=entry.id, channel=channel,
                               delta_fen=totals[channel] - previous.get(channel, 0),
                               cumulative_fen=totals[channel]))
    state.last_dataset_id = job.dataset_id
    state.totals = {channel: totals[channel] for channel in CHANNELS}
    state.updated_at = now()
    job.status = Settlement.POSTED
    job.entry_id = entry.id
    record(db, 'worker', 'settlement.posted', job.id, entry_id=entry.id, period=job.period,
           learners=learner_count)
