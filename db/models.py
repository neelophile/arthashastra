from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, Text, BigInteger
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone


Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class Citizen(Base):
    __tablename__ = 'citizens'
    user_id = Column(BigInteger, primary_key=True)
    current_job_id = Column(Integer, ForeignKey("jobs.job_id"))
    job_level_id = Column(Integer, ForeignKey("job_levels.job_level_id"))
    last_quit = Column(DateTime)
    total_income = Column(Integer, default=0)


class Wallet(Base):
    __tablename__ = 'wallets'
    user_id = Column(BigInteger, ForeignKey("citizens.user_id"), primary_key=True)
    balance = Column(Integer, default=0)


class Transaction(Base):
    __tablename__ = 'transactions'
    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    from_id = Column(BigInteger, ForeignKey("citizens.user_id"))
    to_id = Column(BigInteger, ForeignKey("citizens.user_id"))
    amount = Column(Integer, nullable=False)
    type = Column(Enum("payment", "tax", "fine", "treasury"), nullable=False)
    bounty_id = Column(Integer, ForeignKey("bounties.bounty_id"))
    timestamp = Column(DateTime, default=utcnow)


class Job(Base):
    __tablename__ = 'jobs'
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(50), nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    levels = relationship("JobLevel", back_populates="job", foreign_keys=lambda: [JobLevel.job_id])


class JobLevel(Base):
    __tablename__ = 'job_levels'
    job_level_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.job_id"), nullable=False)
    level = Column(Integer, nullable=False)
    title = Column(String(50), nullable=False)
    xp_required = Column(Integer, nullable=False)
    promotes_to_job_id = Column(Integer, ForeignKey("jobs.job_id"))
    job = relationship("Job", back_populates="levels", foreign_keys=lambda: [JobLevel.job_id])


class JobXP(Base):
    __tablename__ = 'job_xp'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.job_id"), nullable=False)
    xp = Column(Integer, default=0)


class Bounty(Base):
    __tablename__ = 'bounties'
    bounty_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("citizens.user_id"))
    description = Column(Text, nullable=False)
    prize = Column(Integer)
    status = Column(Enum("open", "taken", "completed", "disputed"), default="open")
    channel_id = Column(BigInteger)
    created_at = Column(DateTime, default=utcnow)


class NegotiationLog(Base):
    __tablename__ = 'negotiation_log'
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    bounty_id = Column(Integer, ForeignKey("bounties.bounty_id"), nullable=False)
    proposed_by = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    amount = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=utcnow)


class EmploymentLog(Base):
    __tablename__ = 'employment_log'
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.job_id"), nullable=False)
    hired_at = Column(DateTime, default=utcnow)
    quit_at = Column(DateTime)


class Treasury(Base):
    __tablename__ = 'treasury'
    id = Column(Integer, primary_key=True, autoincrement=True)
    balance = Column(Integer, default=0)


class Fine(Base):
    __tablename__ = 'fines'
    fine_id = Column(Integer, primary_key=True, autoincrement=True)
    issued_to = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    amount = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)


class Config(Base):
    __tablename__ = 'config'
    key = Column(String(50), primary_key=True)
    value = Column(String(50), nullable=False)

