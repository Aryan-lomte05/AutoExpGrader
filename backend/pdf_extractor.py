import fitz  # PyMuPDF
import base64
from typing import List, Dict, Any, Optional

def extract_all_pages_base64(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text and a base64 encoded image for ALL pages of the PDF.
    Used by the AI grader to read the whole document at once.
    """
    results = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            
            # Render page to an image
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")
            img_base64 = base64.b64encode(img_data).decode("utf-8")
            
            results.append({
                "page_num": page_num,
                "text": text,
                "image_base64": img_base64
            })
        doc.close()
    except Exception as e:
        print(f"Error extracting PDF {pdf_path}: {e}")
    return results

def get_pdf_page_image_bytes(pdf_path: str, page_num: int) -> Optional[bytes]:
    """
    Dynamically renders a specific PDF page to bytes.
    Used by the frontend endpoint to display individual pages.
    Note: page_num is 0-indexed internally.
    """
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            doc.close()
            return None
            
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        img_data = pix.tobytes("png")
        doc.close()
        return img_data
    except Exception as e:
        print(f"Error reading PDF page {pdf_path} (page {page_num}): {e}")
        return None

def get_pdf_page_count(pdf_path: str) -> int:
    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except:
        return 0
