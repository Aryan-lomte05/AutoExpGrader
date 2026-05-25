import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from config import get_current_model_config

# Using standard genai client
# Since the local Ollama provides an OpenAI-compatible API, we might use openai for prod.
# For simplicity in this scaffold, we'll configure a generic prompt builder.

def build_prompt(teacher_config: Dict[str, Any], lab_manual_text: str) -> str:
    return f"""
## ROLE
You are an expert academic lab submission grader for an undergraduate engineering course ({teacher_config.get('course_name')}, {teacher_config.get('branch')}). You assist the course instructor by evaluating student PDF submissions leniently but with academic integrity.

## TEACHER CONFIGURATION
Course: {teacher_config.get('course_name')}
Branch: {teacher_config.get('branch')}
Year of Study: {teacher_config.get('year_of_study')}
Division: {teacher_config.get('division')}
Batch: {teacher_config.get('batch')}
Total Marks: {teacher_config.get('total_marks', 15)}
Grading Components: {json.dumps(teacher_config.get('grading_components', dict()))}
Late Penalty Per Day: {teacher_config.get('late_penalty_per_day', 1)}

## CONTEXT
The lab manual context:
{lab_manual_text}

Evaluate based on the provided grading components.
Output ONLY valid JSON.
"""

def grade_submission(
    teacher_config: Dict[str, Any], 
    lab_manual_text: str,
    submission_data: Dict[str, Any],
    pdf_pages: List[Dict[str, Any]], 
    signature_present: bool
) -> Dict[str, Any]:
    """
    Grades the submission using the configured AI model.
    """
    config = get_current_model_config()
    prompt = build_prompt(teacher_config, lab_manual_text)
    
    # Example for Gemini API usage
    if config["provider"] == "google_aistudio":
        client = genai.Client(api_key=config["api_key"])
        
        # Build contents with text and images
        contents = [prompt, f"Submission Details: {json.dumps(submission_data)}", f"Signature detected: {signature_present}"]
        for page in pdf_pages:
            contents.append(f"Page {page['page_num']} Text: {page['text']}")
            # In a real scenario, we'd pass the image bytes here as well
            
        try:
            response = client.models.generate_content(
                model=config["text_model"],
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return {"error": str(e), "status": "FAILED"}
    else:
        # Local Ollama logic (OpenAI compatible client would go here)
        return {"status": "GRADED", "note": "Local Ollama logic placeholder"}
