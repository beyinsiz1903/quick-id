"""
Offline OCR Fallback (Tesseract)
- İnternet kesintisinde lokal OCR
- Tesseract ile metin çıkarımı
- Basit veri yapılandırma
- MRZ okuma desteği
"""
import base64
import io
import re
from typing import Optional
from datetime import datetime, timezone

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from mrz_parser import detect_and_parse_mrz


def is_tesseract_available() -> bool:
    """Tesseract'ın kurulu olup olmadığını kontrol et"""
    if not TESSERACT_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_extract_text(image_base64: str, lang: str = "tur+eng") -> str:
    """Base64 görüntüden metin çıkar"""
    if not TESSERACT_AVAILABLE:
        raise RuntimeError("Tesseract OCR kurulu değil")
    
    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]
    
    img_bytes = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(img_bytes))
    
    # OCR with Turkish and English
    text = pytesseract.image_to_string(img, lang=lang, config='--psm 6')
    return text.strip()


def extract_structured_data(raw_text: str) -> dict:
    """Ham OCR metninden yapılandırılmış veri çıkar"""
    data = {
        "first_name": None,
        "last_name": None,
        "id_number": None,
        "birth_date": None,
        "gender": None,
        "nationality": None,
        "document_type": None,
        "document_number": None,
        "expiry_date": None,
        "raw_text": raw_text,
    }
    
    lines = raw_text.split('\n')
    text_upper = raw_text.upper()
    
    # TC Kimlik No detection (11 digit number)
    tc_pattern = re.compile(r'\b[1-9]\d{10}\b')
    tc_matches = tc_pattern.findall(raw_text)
    if tc_matches:
        data["id_number"] = tc_matches[0]
        data["document_type"] = "tc_kimlik"
    
    # Passport number detection
    passport_pattern = re.compile(r'\b[A-Z]{1,2}\d{6,8}\b')
    passport_matches = passport_pattern.findall(raw_text.upper())
    if passport_matches and not data["id_number"]:
        data["document_number"] = passport_matches[0]
        data["document_type"] = "passport"
    
    # Date detection (DD.MM.YYYY or DD/MM/YYYY or YYYY-MM-DD)
    date_pattern = re.compile(r'\b(\d{2})[./](\d{2})[./](\d{4})\b')
    date_matches = date_pattern.findall(raw_text)
    if date_matches:
        # First date usually birth date
        day, month, year = date_matches[0]
        data["birth_date"] = f"{year}-{month}-{day}"
        if len(date_matches) > 1:
            day2, month2, year2 = date_matches[1]
            data["expiry_date"] = f"{year2}-{month2}-{day2}"
    
    # Gender detection
    if 'ERKEK' in text_upper or '/M/' in text_upper or ' M ' in text_upper:
        data["gender"] = "M"
    elif 'KADIN' in text_upper or '/F/' in text_upper or ' F ' in text_upper:
        data["gender"] = "F"
    
    # Nationality detection
    if 'T.C.' in text_upper or 'TÜRKİYE' in text_upper or 'TURKEY' in text_upper or 'TURKISH' in text_upper:
        data["nationality"] = "TR"
    
    # Try to extract name fields from common patterns
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        
        # "ADI" or "AD" pattern
        if re.match(r'^(ADI?|NAME|GIVEN NAME|PRENOM)\s*[:/]?\s*(.+)', line_clean, re.IGNORECASE):
            match = re.match(r'^(ADI?|NAME|GIVEN NAME|PRENOM)\s*[:/]?\s*(.+)', line_clean, re.IGNORECASE)
            if match:
                data["first_name"] = match.group(2).strip()
        
        # "SOYADI" or "SOYAD" pattern
        if re.match(r'^(SOYADI?|SURNAME|NOM)\s*[:/]?\s*(.+)', line_clean, re.IGNORECASE):
            match = re.match(r'^(SOYADI?|SURNAME|NOM)\s*[:/]?\s*(.+)', line_clean, re.IGNORECASE)
            if match:
                data["last_name"] = match.group(2).strip()
    
    # Try MRZ parsing
    mrz_result = detect_and_parse_mrz(raw_text)
    if mrz_result:
        mrz_data = mrz_result
        if mrz_data.get("first_name"):
            data["first_name"] = data["first_name"] or mrz_data["first_name"]
        if mrz_data.get("last_name"):
            data["last_name"] = data["last_name"] or mrz_data["last_name"]
        if mrz_data.get("birth_date"):
            data["birth_date"] = data["birth_date"] or mrz_data["birth_date"]
        if mrz_data.get("gender"):
            data["gender"] = data["gender"] or mrz_data["gender"]
        if mrz_data.get("nationality"):
            data["nationality"] = data["nationality"] or mrz_data["nationality"]
        if mrz_data.get("expiry_date"):
            data["expiry_date"] = data["expiry_date"] or mrz_data["expiry_date"]
        if mrz_data.get("passport_number"):
            data["document_number"] = data["document_number"] or mrz_data["passport_number"]
        if mrz_data.get("document_number"):
            data["document_number"] = data["document_number"] or mrz_data["document_number"]
        data["mrz_data"] = mrz_data
    
    return data


def ocr_scan_document(image_base64: str) -> dict:
    """Tam OCR tarama: metin çıkarım + yapılandırma"""
    if not is_tesseract_available():
        return {
            "success": False,
            "error": "Tesseract OCR sistemi kurulu değil",
            "documents": [],
        }
    
    try:
        raw_text = ocr_extract_text(image_base64)
        
        if not raw_text or len(raw_text.strip()) < 10:
            return {
                "success": False,
                "error": "Görüntüden yeterli metin çıkarılamadı",
                "raw_text": raw_text,
                "documents": [],
            }
        
        structured = extract_structured_data(raw_text)
        
        # Determine validity
        has_name = bool(structured.get("first_name") or structured.get("last_name"))
        has_id = bool(structured.get("id_number") or structured.get("document_number"))
        is_valid = has_name or has_id
        
        document = {
            "is_valid": is_valid,
            "document_type": structured.get("document_type", "other"),
            "first_name": structured.get("first_name"),
            "last_name": structured.get("last_name"),
            "id_number": structured.get("id_number"),
            "birth_date": structured.get("birth_date"),
            "gender": structured.get("gender"),
            "nationality": structured.get("nationality"),
            "document_number": structured.get("document_number"),
            "expiry_date": structured.get("expiry_date"),
            "raw_extracted_text": raw_text,
            "warnings": [
                "Offline OCR (Tesseract) ile tarandı - doğruluk düşük olabilir",
                "Lütfen çıkarılan bilgileri kontrol edin",
            ],
            "mrz_data": structured.get("mrz_data"),
        }
        
        return {
            "success": True,
            "source": "tesseract_ocr",
            "document_count": 1,
            "documents": [document],
            "raw_text": raw_text,
            "confidence_note": "Offline OCR taraması - AI taramaya göre daha düşük doğruluk",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"OCR hatası: {str(e)}",
            "documents": [],
        }
