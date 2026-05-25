from typing import Dict, Any
from pydantic import BaseModel

class WebhookPayload(BaseModel):
    roll_number: str
    name: str
    experiment_id: str
    submission_timestamp: str
    pdf_url: str  # Assuming Google Forms provides a link to the PDF

def parse_google_form_webhook(payload: Dict[Any, Any]) -> WebhookPayload:
    """
    Parses a Google Forms POST payload into a structured format.
    The actual implementation will depend on how the Google Apps Script is formatted.
    """
    return WebhookPayload(
        roll_number=payload.get("roll_number", "UNKNOWN"),
        name=payload.get("name", "Unknown Student"),
        experiment_id=payload.get("experiment_id", "EXP_0"),
        submission_timestamp=payload.get("submission_timestamp", "1970-01-01T00:00:00"),
        pdf_url=payload.get("pdf_url", "")
    )
