from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import json
import os
import shutil
import asyncio
from datetime import datetime

import models
from webhook_parser import parse_google_form_webhook
from pdf_extractor import get_pdf_page_image_bytes, get_pdf_page_count
from worker import start_worker

app = FastAPI(title="AntigravityGrader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    start_worker()

def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- COURSES ---
@app.post("/api/courses")
def create_course(payload: Dict[str, Any], db: Session = Depends(get_db)):
    course = models.Course(
        name=payload.get("name"),
        branch=payload.get("branch"),
        year_of_study=payload.get("year_of_study"),
        academic_year=payload.get("academic_year"),
        total_marks=payload.get("total_marks", 15),
        grading_components=payload.get("grading_components", {}),
        late_penalty_per_day=payload.get("late_penalty_per_day", 1.0),
        signature_required=payload.get("signature_required", True),
        signature_owners=payload.get("signature_owners", [])
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    
    for div_data in payload.get("divisions", []):
        division = models.Division(name=div_data["name"], course_id=course.id)
        db.add(division)
        db.commit()
        db.refresh(division)
        
        for batch_data in div_data.get("batches", []):
            batch = models.Batch(name=batch_data["name"], division_id=division.id)
            db.add(batch)
            db.commit()
            db.refresh(batch)
            
            for student_data in batch_data.get("students", []):
                student = models.Student(
                    roll_number=student_data["roll_number"], 
                    name=student_data["name"], 
                    batch_id=batch.id
                )
                db.add(student)
                
    db.commit()
    return {"status": "created", "course_id": course.id}

@app.get("/api/courses")
def list_courses(db: Session = Depends(get_db)):
    courses = db.query(models.Course).all()
    # Mocking stats for the overview
    result = []
    for c in courses:
        result.append({
            "id": c.id,
            "name": c.name,
            "branch": c.branch,
            "year_of_study": c.year_of_study,
            "stats": {"enrolled": 100, "graded": 50, "pending": 40, "in_queue": 10}
        })
    return result

@app.get("/api/courses/{course_id}")
def get_course_detail(course_id: int, db: Session = Depends(get_db)):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    experiments = []
    for exp in course.experiments:
        # Calculate graded count
        subs = db.query(models.StudentSubmission).filter(models.StudentSubmission.experiment_id == exp.id).all()
        graded_count = sum(1 for s in subs if s.status == "GRADED" or s.status == "DONE")
        total_count = len(subs)
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "deadline": exp.deadline,
            "graded_count": graded_count,
            "total_count": total_count,
            "has_manual": exp.lab_manual is not None
        })
        
    div_list = []
    for div in course.divisions:
        batch_list = []
        for batch in div.batches:
            student_list = []
            for stud in batch.students:
                student_list.append({
                    "id": stud.id,
                    "roll_number": stud.roll_number,
                    "name": stud.name,
                })
            batch_list.append({
                "id": batch.id,
                "name": batch.name,
                "students": student_list
            })
        div_list.append({
            "id": div.id,
            "name": div.name,
            "batches": batch_list
        })
        
    return {
        "id": course.id,
        "name": course.name,
        "branch": course.branch,
        "year_of_study": course.year_of_study,
        "total_marks": course.total_marks,
        "grading_components": course.grading_components,
        "experiments": experiments,
        "divisions": div_list
    }

@app.post("/api/courses/{course_id}/experiments")
async def add_experiment(
    course_id: int, 
    name: str = Form(...),
    short_code: str = Form(...),
    deadline: str = Form(...),
    max_marks: Optional[float] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    import os
    os.makedirs("backend/uploads/manuals", exist_ok=True)
    
    exp = models.Experiment(
        course_id=course_id,
        name=name,
        short_code=short_code,
        deadline=deadline,
        max_marks=max_marks
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    
    file_location = f"backend/uploads/manuals/{short_code}.pdf"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    manual = models.LabManual(
        experiment_id=exp.id,
        pdf_path=file_location,
        extracted_text="MOCK EXTRACTED TEXT FROM PDF"
    )
    db.add(manual)
    db.commit()
    return exp

@app.get("/api/experiments/{experiment_id}/submissions")
def list_experiment_submissions(experiment_id: int, db: Session = Depends(get_db)):
    subs = db.query(models.StudentSubmission).filter(models.StudentSubmission.experiment_id == experiment_id).all()
    return subs

# --- INGEST ---
@app.post("/api/ingest")
async def ingest_manual(experiment_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_location = f"backend/uploads/{file.filename}"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    manual = models.LabManual(
        experiment_id=experiment_id,
        pdf_path=file_location,
        extracted_text="MOCK EXTRACTED TEXT FROM PDF"
    )
    db.add(manual)
    db.commit()
    return {"status": "ingested"}

@app.post("/api/submissions/upload")
async def upload_submission(
    student_id: int = Form(...),
    experiment_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    file_location = f"backend/uploads/{student.roll_number}_{experiment_id}.pdf"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    sub = db.query(models.StudentSubmission).filter(
        models.StudentSubmission.student_id == student.id,
        models.StudentSubmission.experiment_id == experiment_id
    ).first()
    
    if not sub:
        sub = models.StudentSubmission(
            student_id=student.id,
            experiment_id=experiment_id,
            submission_timestamp=datetime.now().isoformat(),
            pdf_path=file_location,
            status="WAITING"
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
    else:
        sub.pdf_path = file_location
        sub.status = "WAITING"
        db.commit()
        
    # Queue job
    job = db.query(models.QueueJob).filter(models.QueueJob.submission_id == sub.id).first()
    if not job:
        job = models.QueueJob(submission_id=sub.id, status="WAITING")
        db.add(job)
    else:
        job.status = "WAITING"
        job.updated_at = datetime.utcnow().isoformat()
    db.commit()
    
    return {"status": "accepted", "submission_id": sub.id}

# --- SUBMIT ---
@app.post("/api/submit")
def submit_webhook(payload: Dict[Any, Any], db: Session = Depends(get_db)):
    parsed = parse_google_form_webhook(payload)
    student = db.query(models.Student).filter(models.Student.roll_number == parsed.roll_number).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    # Assume PDF is downloaded to local storage
    local_pdf_path = f"backend/uploads/{parsed.roll_number}_{parsed.experiment_id}.pdf"
    
    sub = models.StudentSubmission(
        student_id=student.id,
        experiment_id=int(parsed.experiment_id), # Assumes integer for now
        submission_timestamp=parsed.submission_timestamp,
        pdf_path=local_pdf_path,
        status="WAITING"
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    
    job = models.QueueJob(submission_id=sub.id, status="WAITING")
    db.add(job)
    db.commit()
    
    return {"status": "accepted", "submission_id": sub.id}

# --- PDF PAGE ---
@app.get("/api/submissions/{submission_id}/page/{page_num}")
def get_pdf_page(submission_id: int, page_num: int, db: Session = Depends(get_db)):
    sub = db.query(models.StudentSubmission).filter(models.StudentSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    img_bytes = get_pdf_page_image_bytes(sub.pdf_path, page_num)
    if not img_bytes:
        raise HTTPException(status_code=404, detail="Page not found or error rendering")
        
    return Response(content=img_bytes, media_type="image/png")

# --- QUEUE & WEBSOCKET ---
@app.get("/api/queue")
def get_queue(db: Session = Depends(get_db)):
    jobs = db.query(models.QueueJob).all()
    result = []
    for i, j in enumerate(jobs):
        sub = db.query(models.StudentSubmission).filter(models.StudentSubmission.id == j.submission_id).first()
        student = sub.student if sub else None
        exp = sub.experiment if sub else None
        
        result.append({
            "id": j.id,
            "submission_id": j.submission_id,
            "status": j.status,
            "position": i + 1,
            "student_name": student.name if student else "Unknown",
            "student_roll": student.roll_number if student else "Unknown",
            "experiment_name": exp.name if exp else "Unknown",
            "score": sub.final_score if (sub and (j.status == "DONE" or sub.status == "GRADED" or sub.status == "DONE")) else None
        })
    return result

@app.websocket("/ws/queue")
async def websocket_queue(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            db = models.SessionLocal()
            jobs = db.query(models.QueueJob).all()
            job_data = []
            for i, j in enumerate(jobs):
                sub = db.query(models.StudentSubmission).filter(models.StudentSubmission.id == j.submission_id).first()
                student = sub.student if sub else None
                exp = sub.experiment if sub else None
                job_data.append({
                    "id": j.id,
                    "submission_id": j.submission_id,
                    "status": j.status,
                    "position": i + 1,
                    "student_name": student.name if student else "Unknown",
                    "student_roll": student.roll_number if student else "Unknown",
                    "experiment_name": exp.name if exp else "Unknown",
                    "score": sub.final_score if (sub and (j.status == "DONE" or sub.status == "GRADED" or sub.status == "DONE")) else None
                })
            db.close()
            await websocket.send_json(job_data)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("Client disconnected from /ws/queue")

@app.post("/api/queue/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.QueueJob).filter(models.QueueJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job.status = "WAITING"
    job.updated_at = datetime.utcnow().isoformat()
    
    sub = db.query(models.StudentSubmission).filter(models.StudentSubmission.id == job.submission_id).first()
    if sub:
        sub.status = "WAITING"
        
    db.commit()
    return {"status": "retry_queued"}

# --- STUDENT SUBMISSIONS ---
@app.get("/api/students/{roll_number}/submission/{exp_id}")
def get_student_submission(roll_number: str, exp_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.roll_number == roll_number).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    sub = db.query(models.StudentSubmission).filter(
        models.StudentSubmission.student_id == student.id,
        models.StudentSubmission.experiment_id == exp_id
    ).first()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    page_count = get_pdf_page_count(sub.pdf_path)
    
    return {
        "id": sub.id,
        "student_id": sub.student_id,
        "experiment_id": sub.experiment_id,
        "submission_timestamp": sub.submission_timestamp,
        "pdf_path": sub.pdf_path,
        "status": sub.status,
        "signature_present": sub.signature_present,
        "days_late": sub.days_late,
        "raw_score": sub.raw_score,
        "late_penalty": sub.late_penalty,
        "final_score": sub.final_score,
        "scores_json": sub.scores_json,
        "flags": sub.flags,
        "instructor_note": sub.instructor_note,
        "page_count": page_count
    }

@app.patch("/api/students/{roll_number}/submission/{exp_id}")
def update_student_submission(roll_number: str, exp_id: int, payload: Dict[str, Any], db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.roll_number == roll_number).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    sub = db.query(models.StudentSubmission).filter(
        models.StudentSubmission.student_id == student.id,
        models.StudentSubmission.experiment_id == exp_id
    ).first()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    if "scores_json" in payload:
        sub.scores_json = payload["scores_json"]
    if "instructor_note" in payload:
        sub.instructor_note = payload["instructor_note"]
    
    db.commit()
    return sub

# --- SETTINGS ---
@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    settings = db.query(models.GlobalSettings).first()
    if not settings:
        settings = models.GlobalSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@app.patch("/api/settings")
def update_settings(payload: Dict[str, Any], db: Session = Depends(get_db)):
    settings = db.query(models.GlobalSettings).first()
    if not settings:
        settings = models.GlobalSettings()
        db.add(settings)
        
    for key, value in payload.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
            
    db.commit()
    return settings
