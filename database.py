import os
import time
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, LargeBinary, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from datetime import datetime

def get_database_url():
    url = os.getenv("DATABASE_URL", "sqlite:///./mrxscan.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

DATABASE_URL = get_database_url()

engine = None
SessionLocal = None
Base = declarative_base()

def get_engine():
    global engine
    if engine is None:
        db_url = get_database_url()
        print(f"Connecting to database...")
        if db_url.startswith("postgresql"):
            engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True
            )
        else:
            engine = create_engine(db_url)
    return engine

def get_session_local():
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return SessionLocal

class Classification(Base):
    __tablename__ = "classifications"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DatasetImage(Base):
    __tablename__ = "dataset_images"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    classification = Column(String(255), nullable=False, index=True)
    image_data = Column(LargeBinary, nullable=True)
    image_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Embedding(Base):
    __tablename__ = "embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    classification = Column(String(255), nullable=False, index=True)
    embedding_data = Column(LargeBinary, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScanHistory(Base):
    __tablename__ = "scan_history"
    
    id = Column(Integer, primary_key=True, index=True)
    predicted_class = Column(String(255), nullable=False)
    confidence = Column(Float, nullable=False)
    scanned_at = Column(DateTime, default=datetime.utcnow)

def init_db(max_retries=5, retry_delay=3):
    db_url = get_database_url()
    is_postgres = db_url.startswith("postgresql")
    print(f"Database type: {'PostgreSQL' if is_postgres else 'SQLite'}")
    print(f"Attempting to connect to database...")
    
    for attempt in range(max_retries):
        try:
            eng = get_engine()
            print(f"Creating tables: classifications, dataset_images, embeddings, scan_history...")
            Base.metadata.create_all(bind=eng)
            print("All database tables created successfully!")
            return True
        except Exception as e:
            print(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Could not connect to database after all retries.")
                return False

def get_db():
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()
