from datetime import datetime
from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
from src.constants.enums import Settlement
from src.utils.time import now

class SettlementRun(Base):
    __tablename__ = 'settlement_runs'

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    period: Mapped[str] = mapped_column(String(7), index=True)
    status: Mapped[str] = mapped_column(String(20), default=Settlement.QUEUED, index=True)
    error: Mapped[str | None] = mapped_column(String(500))
    entry_id: Mapped[int | None]
    attempt: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[datetime | None]
    author: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=now)
    finished_at: Mapped[datetime | None]

class SettlementPeriod(Base):
    __tablename__ = 'settlement_periods'

    period: Mapped[str] = mapped_column(String(7), primary_key=True)
    last_dataset_id: Mapped[int] = mapped_column(default=0)
    totals: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(default=now)

class SettlementEntry(Base):
    __tablename__ = 'settlement_entries'
    __table_args__ = (UniqueConstraint('period', 'dataset_id'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(7), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    settlement_id: Mapped[int] = mapped_column(ForeignKey('settlement_runs.id'))
    learner_count: Mapped[int]
    author: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=now)

class SettlementLine(Base):
    __tablename__ = 'settlement_lines'

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey('settlement_entries.id'), index=True)
    learner_id: Mapped[str] = mapped_column(String(80))
    channel: Mapped[str] = mapped_column(String(20))
    amount_fen: Mapped[int]

class SettlementTotal(Base):
    __tablename__ = 'settlement_totals'

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey('settlement_entries.id'), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    delta_fen: Mapped[int]
    cumulative_fen: Mapped[int]
