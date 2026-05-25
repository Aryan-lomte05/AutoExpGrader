import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from datetime import datetime

import models
from pdf_extractor import extract_all_pages_base64
from signature_detector import detect_signature
from grader import grade_submission

# Create the scheduler
scheduler = AsyncIOScheduler()

def process_single_job(job_id: int):
    """Synchronous function to process a single job, run in thread pool if needed."""
    db = models.SessionLocal()
    try:
        job = db.query(models.QueueJob).filter(models.QueueJob.id == job_id).first()
        if not job or job.status != "PROCESSING":
            return

        submission = db.query(models.StudentSubmission).filter(models.StudentSubmission.id == job.submission_id).first()
        if not submission:
            job.status = "FAILED"
            db.commit()
            return
            
        experiment = db.query(models.Experiment).filter(models.Experiment.id == submission.experiment_id).first()
        course = db.query(models.Course).filter(models.Course.id == experiment.course_id).first()
        lab_manual = db.query(models.LabManual).filter(models.LabManual.experiment_id == experiment.id).first()
        settings = db.query(models.GlobalSettings).first()

        # 1. Extract PDF pages
        pdf_pages = extract_all_pages_base64(submission.pdf_path)
        
        # 2. Detect Signature (using stub for now)
        images = [p["image_base64"] for p in pdf_pages]
        sig_result = detect_signature(images)
        submission.signature_present = sig_result["signature_present"]
        
        # 3. Grade AI
        lab_manual_text = lab_manual.extracted_text if lab_manual else "No manual available."
        submission_data = {
            "roll_number": submission.student.roll_number,
            "submission_timestamp": submission.submission_timestamp,
        }
        
        grading_result = grade_submission(
            course.__dict__, lab_manual_text, submission_data, pdf_pages, sig_result["signature_present"]
        )
        
        submission.status = grading_result.get("status", "GRADED")
        submission.scores_json = grading_result
        if "final_score" in grading_result:
            submission.final_score = grading_result["final_score"]
            
        job.status = "DONE"
        job.updated_at = datetime.utcnow().isoformat()
        db.commit()
    except Exception as e:
        print(f"Worker Error on Job {job_id}: {e}")
        job.status = "FAILED"
        job.updated_at = datetime.utcnow().isoformat()
        db.commit()
    finally:
        db.close()

async def poll_queue():
    """Polls the queue every 3 seconds for WAITING jobs."""
    db = models.SessionLocal()
    try:
        # Find one WAITING job
        job = db.query(models.QueueJob).filter(models.QueueJob.status == "WAITING").first()
        if job:
            job.status = "PROCESSING"
            job.updated_at = datetime.utcnow().isoformat()
            db.commit()
            
            # Offload heavy synchronous processing to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, process_single_job, job.id)
            
    except Exception as e:
        print(f"Queue Poller Error: {e}")
    finally:
        db.close()

def start_worker():
    scheduler.add_job(poll_queue, 'interval', seconds=3)
    scheduler.start()
