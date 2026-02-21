"""
MRZ (Machine Readable Zone) Parser
- Pasaport MRZ otomatik okuma
- TD1 (ID Card) ve TD3 (Passport) formatları
- Check digit doğrulama
- Veri çıkarımı
"""
import re
from datetime import datetime
from typing import Optional


# MRZ character to number mapping
MRZ_CHAR_MAP = {
    '<': 0, '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
    '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15,
    'G': 16, 'H': 17, 'I': 18, 'J': 19, 'K': 20, 'L': 21,
    'M': 22, 'N': 23, 'O': 24, 'P': 25, 'Q': 26, 'R': 27,
    'S': 28, 'T': 29, 'U': 30, 'V': 31, 'W': 32, 'X': 33,
    'Y': 34, 'Z': 35,
}

WEIGHTS = [7, 3, 1]


def compute_check_digit(data: str) -> int:
    """MRZ check digit hesapla"""
    total = 0
    for i, char in enumerate(data):
        val = MRZ_CHAR_MAP.get(char.upper(), 0)
        total += val * WEIGHTS[i % 3]
    return total % 10


def validate_check_digit(data: str, check_digit: str) -> bool:
    """Check digit doğrula"""
    try:
        expected = compute_check_digit(data)
        return expected == int(check_digit)
    except (ValueError, IndexError):
        return False


def parse_mrz_date(date_str: str) -> Optional[str]:
    """MRZ tarih formatını (YYMMDD) ISO formatına çevir"""
    try:
        if len(date_str) != 6:
            return None
        year = int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        
        # Y2K handling
        current_year = datetime.now().year % 100
        if year <= current_year + 10:
            year += 2000
        else:
            year += 1900
        
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, IndexError):
        return None


def clean_mrz_field(field: str) -> str:
    """MRZ alanından '<' karakterlerini temizle"""
    return field.replace('<', ' ').strip()


def extract_names(name_field: str) -> dict:
    """MRZ isim alanından ad ve soyad çıkar"""
    parts = name_field.split('<<')
    last_name = clean_mrz_field(parts[0]) if len(parts) > 0 else ""
    first_name = clean_mrz_field(parts[1]) if len(parts) > 1 else ""
    first_name = first_name.replace('<', ' ').strip()
    return {"first_name": first_name, "last_name": last_name}


def parse_td3_passport(lines: list) -> Optional[dict]:
    """TD3 format pasaport MRZ parse (2 satır x 44 karakter)"""
    if len(lines) != 2:
        return None
    
    line1 = lines[0].strip()
    line2 = lines[1].strip()
    
    if len(line1) != 44 or len(line2) != 44:
        return None
    
    if line1[0] != 'P':
        return None
    
    # Line 1
    doc_type = line1[0:2].replace('<', '')
    issuing_country = line1[2:5].replace('<', '')
    names_field = line1[5:44]
    names = extract_names(names_field)
    
    # Line 2
    passport_number = line2[0:9].replace('<', '')
    passport_check = line2[9]
    nationality = line2[10:13].replace('<', '')
    birth_date_raw = line2[13:19]
    birth_check = line2[19]
    gender = line2[20]
    expiry_date_raw = line2[21:27]
    expiry_check = line2[27]
    personal_number = line2[28:42].replace('<', '')
    personal_check = line2[42]
    final_check = line2[43]
    
    # Validate check digits
    checks = {
        "passport_number": validate_check_digit(line2[0:9], passport_check),
        "birth_date": validate_check_digit(birth_date_raw, birth_check),
        "expiry_date": validate_check_digit(expiry_date_raw, expiry_check),
    }
    
    # Parse dates
    birth_date = parse_mrz_date(birth_date_raw)
    expiry_date = parse_mrz_date(expiry_date_raw)
    
    # Gender mapping
    gender_map = {'M': 'M', 'F': 'F', '<': None}
    
    return {
        "mrz_type": "TD3",
        "document_type": "passport",
        "doc_subtype": doc_type,
        "issuing_country": issuing_country,
        "first_name": names["first_name"],
        "last_name": names["last_name"],
        "passport_number": passport_number,
        "nationality": nationality,
        "birth_date": birth_date,
        "gender": gender_map.get(gender, gender),
        "expiry_date": expiry_date,
        "personal_number": personal_number if personal_number else None,
        "check_digits_valid": checks,
        "all_checks_passed": all(checks.values()),
        "raw_mrz": lines,
    }


def parse_td1_id_card(lines: list) -> Optional[dict]:
    """TD1 format kimlik kartı MRZ parse (3 satır x 30 karakter)"""
    if len(lines) != 3:
        return None
    
    line1 = lines[0].strip()
    line2 = lines[1].strip()
    line3 = lines[2].strip()
    
    if len(line1) != 30 or len(line2) != 30 or len(line3) != 30:
        return None
    
    # Line 1
    doc_type = line1[0:2].replace('<', '')
    issuing_country = line1[2:5].replace('<', '')
    doc_number = line1[5:14].replace('<', '')
    doc_check = line1[14]
    optional1 = line1[15:30].replace('<', '')
    
    # Line 2
    birth_date_raw = line2[0:6]
    birth_check = line2[6]
    gender = line2[7]
    expiry_date_raw = line2[8:14]
    expiry_check = line2[14]
    nationality = line2[15:18].replace('<', '')
    optional2 = line2[18:29].replace('<', '')
    final_check = line2[29]
    
    # Line 3 - Names
    names = extract_names(line3)
    
    checks = {
        "document_number": validate_check_digit(line1[5:14], doc_check),
        "birth_date": validate_check_digit(birth_date_raw, birth_check),
        "expiry_date": validate_check_digit(expiry_date_raw, expiry_check),
    }
    
    birth_date = parse_mrz_date(birth_date_raw)
    expiry_date = parse_mrz_date(expiry_date_raw)
    gender_map = {'M': 'M', 'F': 'F', '<': None}
    
    return {
        "mrz_type": "TD1",
        "document_type": "id_card",
        "doc_subtype": doc_type,
        "issuing_country": issuing_country,
        "first_name": names["first_name"],
        "last_name": names["last_name"],
        "document_number": doc_number,
        "nationality": nationality,
        "birth_date": birth_date,
        "gender": gender_map.get(gender, gender),
        "expiry_date": expiry_date,
        "personal_number": optional1 if optional1 else None,
        "check_digits_valid": checks,
        "all_checks_passed": all(checks.values()),
        "raw_mrz": lines,
    }


def detect_and_parse_mrz(text: str) -> Optional[dict]:
    """Metin içinden MRZ bölgesini tespit et ve parse et"""
    if not text:
        return None
    
    # Clean and split lines
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    # Filter MRZ-like lines (only uppercase letters, digits, and '<')
    mrz_pattern = re.compile(r'^[A-Z0-9<]{28,44}$')
    mrz_lines = [line for line in lines if mrz_pattern.match(line.replace(' ', ''))]
    
    if not mrz_lines:
        return None
    
    # Clean spaces from MRZ lines
    mrz_lines = [line.replace(' ', '') for line in mrz_lines]
    
    # Try TD3 (passport - 2 lines x 44 chars)
    if len(mrz_lines) >= 2:
        td3_lines = [l for l in mrz_lines if len(l) == 44]
        if len(td3_lines) >= 2:
            result = parse_td3_passport(td3_lines[:2])
            if result:
                return result
    
    # Try TD1 (ID card - 3 lines x 30 chars)
    if len(mrz_lines) >= 3:
        td1_lines = [l for l in mrz_lines if len(l) == 30]
        if len(td1_lines) >= 3:
            result = parse_td1_id_card(td1_lines[:3])
            if result:
                return result
    
    return None


def parse_mrz_from_text(raw_text: str) -> dict:
    """Ham metinden MRZ parse et ve sonuç döndür"""
    result = detect_and_parse_mrz(raw_text)
    
    if result:
        return {
            "mrz_detected": True,
            "mrz_data": result,
            "message": f"MRZ başarıyla okundu ({result['mrz_type']} format)",
        }
    
    return {
        "mrz_detected": False,
        "mrz_data": None,
        "message": "MRZ bölgesi tespit edilemedi",
    }
