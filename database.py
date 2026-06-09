from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./redboard.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, unique=True, nullable=True)
    company = Column(String, nullable=True)
    role = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    verification_sent_at = Column(DateTime, nullable=True)
    consent_given = Column(Boolean, default=False)
    consent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime)
    last_login = Column(DateTime, nullable=True)
    review_count = Column(Integer, default=0)

class Review(Base):
    __tablename__ = "reviews"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    project_name = Column(String, nullable=True)
    proposal = Column(Text, nullable=False)
    context = Column(Text)
    team = Column(String)
    objectives = Column(Text)
    risks_known = Column(Text)
    timeline = Column(String)
    stakeholders = Column(Text)
    tech_stack = Column(Text)
    synthesis = Column(Text)
    agent_outputs = Column(Text)
    verdict = Column(String)
    confidence = Column(String)
    pdf_path = Column(String)
    files = Column(Text)
    file_names = Column(Text)
    created_at = Column(DateTime)
    is_deleted = Column(Boolean, default=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    detail = Column(Text)
    ip_address = Column(String)
    created_at = Column(DateTime)

class OTPStore(Base):
    __tablename__ = "otp_store"
    id = Column(String, primary_key=True)
    email = Column(String, nullable=False)
    otp_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()