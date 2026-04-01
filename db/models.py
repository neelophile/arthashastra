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
    job = relationship("Job", back_populates="levels", foreign_keys=lambda: [job_id])


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
    __tablename__ = "employment_log"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.job_id"), nullable=False)
    hired_at = Column(DateTime, default=utcnow)
    quit_at = Column(DateTime)


class Election(Base):
    __tablename__ = 'elections'
    election_id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum("cabinet", "club"), nullable=False)
    club_id = Column(Integer, ForeignKey("clubs.club_id"))
    status = Column(Enum("upcoming", "party_window", "ongoing", "closed"), default="upcoming")
    start_date = Column(DateTime, nullable=False)
    created_by = Column(BigInteger, nullable=False)


class Candidate(Base):
    __tablename__ = 'candidates'
    candidate_id = Column(Integer, primary_key=True, autoincrement=True)
    election_id = Column(Integer, ForeignKey("elections.election_id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    party_id = Column(Integer, ForeignKey("parties.party_id"))


class Party(Base):
    __tablename__ = 'parties'
    party_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    leader_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)


class PartyMember(Base):
    __tablename__ = 'party_members'
    id = Column(Integer, primary_key=True, autoincrement=True)
    party_id = Column(Integer, ForeignKey("parties.party_id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    joined_at = Column(DateTime, default=utcnow)


class Vote(Base):
    __tablename__ = 'votes'
    vote_id = Column(Integer, primary_key=True, autoincrement=True)
    election_id = Column(Integer, ForeignKey("elections.election_id"), nullable=False)
    voter_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.candidate_id"), nullable=False)


class Club(Base):
    __tablename__ = 'clubs'
    club_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    join_type = Column(Enum("open", "approval"), default="open")


class ClubMember(Base):
    __tablename__ = 'club_members'
    id = Column(Integer, primary_key=True, autoincrement=True)
    club_id = Column(Integer, ForeignKey("clubs.club_id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("citizens.user_id"), nullable=False)
    joined_at = Column(DateTime, default=utcnow)

