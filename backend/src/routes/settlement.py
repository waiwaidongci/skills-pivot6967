from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from src.config.database import connection
from src.constants.enums import Role, Settlement
from src.controllers.auth import allow
from src.models.identity import User
from src.models.settlement import SettlementEntry, SettlementLine, SettlementRun, SettlementTotal
from src.models.source import Dataset
from src.schemas.requests import SettlementRequest
from src.services.audit import record
from src.services.settlement import valid_period
from src.utils import views
from src.utils.time import iso
from src.utils.wakeup import wake

router = APIRouter(prefix='/settlements')
internal = allow(Role.ADMIN, Role.ANALYST)


@router.get('')
def index(db: Session = Depends(connection), actor: User = Depends(internal)):
    query = select(SettlementRun).order_by(SettlementRun.id.desc()).limit(100)
    return [views.settlement(item) for item in db.scalars(query)]


@router.get('/ledger')
def ledger(period: str = Query(...), db: Session = Depends(connection), actor: User = Depends(internal)):
    period = valid_period(period)
    query = select(SettlementEntry).where(SettlementEntry.period == period).order_by(SettlementEntry.id)
    entries = []
    for entry in db.scalars(query):
        totals = db.scalars(select(SettlementTotal).where(SettlementTotal.entry_id == entry.id)
                            .order_by(SettlementTotal.id))
        entries.append({'id': entry.id, 'dataset_id': entry.dataset_id, 'settlement_id': entry.settlement_id,
                        'learner_count': entry.learner_count, 'author': entry.author,
                        'created_at': iso(entry.created_at),
                        'totals': [{'channel': row.channel, 'delta_fen': row.delta_fen,
                                    'cumulative_fen': row.cumulative_fen} for row in totals]})
    current = entries[-1]['totals'] if entries else []
    return {'period': period, 'entries': entries,
            'totals': [{'channel': row['channel'], 'cumulative_fen': row['cumulative_fen']} for row in current]}


@router.get('/{settlement_id}')
def detail(settlement_id: int, offset: int = Query(0, ge=0), limit: int = Query(1000, ge=1, le=5000),
           db: Session = Depends(connection), actor: User = Depends(internal)):
    job = db.get(SettlementRun, settlement_id)
    if not job:
        raise HTTPException(404, '找不到该结算记录')
    view = views.settlement(job)
    entry = db.get(SettlementEntry, job.entry_id) if job.entry_id else None
    if entry:
        totals = db.scalars(select(SettlementTotal).where(SettlementTotal.entry_id == entry.id)
                            .order_by(SettlementTotal.id))
        lines = db.scalars(select(SettlementLine).where(SettlementLine.entry_id == entry.id)
                           .order_by(SettlementLine.id).offset(offset).limit(limit))
        count = db.scalar(select(func.count()).select_from(SettlementLine)
                          .where(SettlementLine.entry_id == entry.id))
        view.update(entry_id=entry.id, learner_count=entry.learner_count, line_count=count,
                    totals=[{'channel': row.channel, 'delta_fen': row.delta_fen,
                             'cumulative_fen': row.cumulative_fen} for row in totals],
                    lines=[{'learner_id': row.learner_id, 'channel': row.channel,
                            'amount_fen': row.amount_fen} for row in lines])
    return view


@router.post('', status_code=202)
def create(body: SettlementRequest, db: Session = Depends(connection), actor: User = Depends(internal)):
    if not db.get(Dataset, body.dataset_id):
        raise HTTPException(404, '找不到指定的数据批次')
    period = valid_period(body.period)
    pending = (SettlementRun.period == period, SettlementRun.dataset_id == body.dataset_id,
               SettlementRun.status.in_([Settlement.QUEUED, Settlement.RUNNING]))
    existing = db.scalar(select(SettlementRun).where(*pending).order_by(SettlementRun.id))
    if existing:
        return views.settlement(existing)
    job = SettlementRun(dataset_id=body.dataset_id, period=period, author=actor.username)
    db.add(job)
    db.flush()
    record(db, actor.username, 'settlement.queued', job.id, period=period, dataset_id=body.dataset_id)
    db.commit()
    wake()
    return views.settlement(job)
