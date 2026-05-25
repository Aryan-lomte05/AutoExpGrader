from sqlalchemy import Column, Integer, String, Float, Boolean, Text, JSON, ForeignKey, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    branch = Column(String, nullable=False)
    year_of_study = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    
    total_marks = Column(Integer, default=15)
    grading_components = Column(JSON, default={})
    late_penalty_per_day = Column(Float, default=1.0)
    signature_required = Column(Boolean, default=True)
    signature_owners = Column(JSON, default=[])

    divisions = relationship("Division", back_populates="course", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="course", cascade="all, delete-orphan")

class Division(Base):
    __tablename__ = "divisions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)

    course = relationship("Course", back_populates="divisions")
    batches = relationship("Batch", back_populates="division", cascade="all, delete-orphan")

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=False)

    division = relationship("Division", back_populates="batches")
    students = relationship("Student", back_populates="batch", cascade="all, delete-orphan")

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)

    batch = relationship("Batch", back_populates="students")
    submissions = relationship("StudentSubmission", back_populates="student", cascade="all, delete-orphan")

class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    name = Column(String, nullable=False)
    short_code = Column(String, nullable=True)
    deadline = Column(String, nullable=True) # ISO format
    max_marks = Column(Float, nullable=True)

    course = relationship("Course", back_populates="experiments")
    lab_manual = relationship("LabManual", back_populates="experiment", uselist=False, cascade="all, delete-orphan")
    submissions = relationship("StudentSubmission", back_populates="experiment", cascade="all, delete-orphan")

class LabManual(Base):
    __tablename__ = "lab_manuals"
    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    pdf_path = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=True)

    experiment = relationship("Experiment", back_populates="lab_manual")

class StudentSubmission(Base):
    __tablename__ = "student_submissions"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    submission_timestamp = Column(String, nullable=False)
    pdf_path = Column(String, nullable=False)
    
    status = Column(String, default="WAITING") # WAITING, PROCESSING, GRADED, FLAGGED
    signature_present = Column(Boolean, nullable=True)
    days_late = Column(Float, nullable=True)
    raw_score = Column(Float, nullable=True)
    late_penalty = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    
    scores_json = Column(JSON, default={}) # breakdown
    flags = Column(JSON, default=[])
    instructor_note = Column(Text, nullable=True)
    
    student = relationship("Student", back_populates="submissions")
    experiment = relationship("Experiment", back_populates="submissions")

class QueueJob(Base):
    __tablename__ = "queue_jobs"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("student_submissions.id"), nullable=False)
    status = Column(String, default="WAITING") # WAITING, PROCESSING, DONE, FAILED
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())

class GlobalSettings(Base):
    __tablename__ = "global_settings"
    id = Column(Integer, primary_key=True, index=True)
    app_mode = Column(String, default="DEV") # DEV or PROD
    google_ai_studio_key = Column(String, nullable=True)
    ollama_base_url = Column(String, default="http://localhost:11434")
    signature_detection_enabled = Column(Boolean, default=True)
    signature_confidence_threshold = Column(Float, default=0.7)

Base.metadata.create_all(bind=engine)
