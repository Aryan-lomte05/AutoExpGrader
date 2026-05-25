from typing import Dict, Any, List

def detect_signature(images_base64: List[str]) -> Dict[str, Any]:
    """
    Stub for the CV model to detect signatures in a list of images.
    Eventually this will call Florence-2 or a custom YOLO model.
    """
    return {
        "signature_present": True,
        "confidence": 1.0,
        "note": "Stubbed detection"
    }
