from enum import StrEnum

class Role(StrEnum):
    ADMIN = 'admin'
    ANALYST = 'analyst'
    VIEWER = 'viewer'

class Status(StrEnum):
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETE = 'complete'
    FAILED = 'failed'

class Review(StrEnum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    RETURNED = 'returned'

class Settlement(StrEnum):
    QUEUED = 'queued'
    RUNNING = 'running'
    POSTED = 'posted'
    SUPERSEDED = 'superseded'
    FAILED = 'failed'
