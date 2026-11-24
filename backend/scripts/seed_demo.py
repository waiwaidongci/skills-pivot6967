import json
from sqlalchemy import func, select
from src.config.database import Session
from src.constants.enums import Role, Settlement
from src.domain.demo import demo_rows
from src.domain.settlement import assess
from src.domain.spec import SPEC
from src.models.identity import User
from src.models.settlement import SettlementEntry, SettlementRun
from src.models.source import Dataset
from src.services.datasets import save
from src.services.settlement import post
from src.utils.security import hash_password
from src.utils.time import now

SEED_PERIOD = '2026-11'


def seed_settlement(db, dataset):
    """为演示批次入账一期渠道服务费；已入账则跳过，可安全重复执行。"""
    existing = db.scalar(select(SettlementEntry).where(SettlementEntry.period == SEED_PERIOD,
                                                       SettlementEntry.dataset_id == dataset.id))
    if existing:
        return existing.id
    job = SettlementRun(dataset_id=dataset.id, period=SEED_PERIOD, author='seed', attempt=1)
    db.add(job)
    db.flush()
    lines, totals, learner_count = assess(dataset.rows, SEED_PERIOD)
    post(db, job, lines, totals, learner_count)
    job.finished_at = now()
    assert job.status == Settlement.POSTED
    return job.entry_id


def seed():
    with Session.begin() as db:
        for role in Role:
            if not db.get(User, role.value):
                db.add(User(username=role.value, role=role, password_hash=hash_password(f'{role.value}-demo-2611')))
        item, created = save(db, SPEC['default_dataset'], SPEC['sample_name'], demo_rows(), 'seed')
        entry_id = seed_settlement(db, item)
        return {'users': db.scalar(select(func.count()).select_from(User)),
                'datasets': db.scalar(select(func.count()).select_from(Dataset)),
                'seed_dataset_id': item.id, 'row_count': item.row_count, 'checksum': item.checksum,
                'created_dataset': created, 'settlement_entry_id': entry_id}


if __name__ == '__main__':
    print(json.dumps(seed(), ensure_ascii=False))
