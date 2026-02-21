"""
Görüntü Kalite Kontrolü Modülü
- Bulanıklık tespiti (Laplacian variance)
- Karanlık/aşırı parlak görüntü tespiti
- Çözünürlük kontrolü
- Kullanıcıya uyarı mesajları
"""
import base64
import io
from typing import Optional

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def decode_base64_image(image_base64: str) -> Optional[np.ndarray]:
    """Base64 görüntüyü numpy array'e çevir"""
    if not CV2_AVAILABLE:
        return None
    try:
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        img_bytes = base64.b64decode(image_base64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def check_blur(img: np.ndarray, threshold: float = 100.0) -> dict:
    """Bulanıklık kontrolü - Laplacian variance yöntemi"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_blurry = laplacian_var < threshold
    
    if laplacian_var < 50:
        level = "very_blurry"
        message = "Görüntü çok bulanık. Lütfen kamerayı sabit tutun ve odaklanmasını bekleyin."
    elif laplacian_var < 100:
        level = "blurry"
        message = "Görüntü bulanık. Daha net bir fotoğraf çekmeyi deneyin."
    elif laplacian_var < 200:
        level = "acceptable"
        message = "Görüntü kalitesi kabul edilebilir."
    else:
        level = "sharp"
        message = "Görüntü netliği iyi."
    
    return {
        "is_blurry": is_blurry,
        "blur_score": round(laplacian_var, 2),
        "blur_level": level,
        "message": message,
    }


def check_brightness(img: np.ndarray) -> dict:
    """Aydınlatma kontrolü"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    
    if mean_brightness < 50:
        level = "very_dark"
        message = "Görüntü çok karanlık. Lütfen daha aydınlık bir ortamda çekin veya flaş kullanın."
        is_ok = False
    elif mean_brightness < 80:
        level = "dark"
        message = "Görüntü karanlık. Aydınlatmayı artırmayı deneyin."
        is_ok = False
    elif mean_brightness > 220:
        level = "overexposed"
        message = "Görüntü aşırı parlak. Flaşı kapatın veya ışık kaynağından uzaklaşın."
        is_ok = False
    elif mean_brightness > 200:
        level = "bright"
        message = "Görüntü biraz parlak ama kabul edilebilir."
        is_ok = True
    else:
        level = "good"
        message = "Aydınlatma uygun."
        is_ok = True
    
    return {
        "brightness_ok": is_ok,
        "brightness_score": round(float(mean_brightness), 2),
        "brightness_level": level,
        "message": message,
    }


def check_resolution(img: np.ndarray, min_width: int = 640, min_height: int = 480) -> dict:
    """Çözünürlük kontrolü"""
    height, width = img.shape[:2]
    is_ok = width >= min_width and height >= min_height
    
    if not is_ok:
        message = f"Görüntü çözünürlüğü düşük ({width}x{height}). En az {min_width}x{min_height} olmalı."
    else:
        message = f"Çözünürlük yeterli ({width}x{height})."
    
    return {
        "resolution_ok": is_ok,
        "width": width,
        "height": height,
        "message": message,
    }


def check_contrast(img: np.ndarray) -> dict:
    """Kontrast kontrolü"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    contrast = float(np.std(gray))
    
    if contrast < 30:
        level = "low"
        message = "Görüntü kontrastı düşük. Belge ve arka plan arasında yeterli kontrast yok."
        is_ok = False
    elif contrast < 50:
        level = "acceptable"
        message = "Kontrast kabul edilebilir."
        is_ok = True
    else:
        level = "good"
        message = "Kontrast iyi."
        is_ok = True
    
    return {
        "contrast_ok": is_ok,
        "contrast_score": round(contrast, 2),
        "contrast_level": level,
        "message": message,
    }


def assess_image_quality(image_base64: str) -> dict:
    """Tam görüntü kalite değerlendirmesi"""
    if not CV2_AVAILABLE:
        return {
            "quality_checked": False,
            "overall_quality": "unknown",
            "overall_score": 0,
            "warnings": ["OpenCV yüklü değil, görüntü kalite kontrolü yapılamadı."],
            "checks": {},
        }
    
    img = decode_base64_image(image_base64)
    if img is None:
        return {
            "quality_checked": False,
            "overall_quality": "invalid",
            "overall_score": 0,
            "warnings": ["Görüntü dosyası okunamadı. Lütfen geçerli bir fotoğraf gönderin."],
            "checks": {},
        }
    
    blur = check_blur(img)
    brightness = check_brightness(img)
    resolution = check_resolution(img)
    contrast = check_contrast(img)
    
    warnings = []
    score = 100
    
    if blur["is_blurry"]:
        warnings.append(blur["message"])
        score -= 30 if blur["blur_level"] == "very_blurry" else 15
    
    if not brightness["brightness_ok"]:
        warnings.append(brightness["message"])
        score -= 25 if brightness["brightness_level"] in ("very_dark", "overexposed") else 10
    
    if not resolution["resolution_ok"]:
        warnings.append(resolution["message"])
        score -= 20
    
    if not contrast["contrast_ok"]:
        warnings.append(contrast["message"])
        score -= 15
    
    score = max(0, score)
    
    if score >= 80:
        overall = "good"
    elif score >= 50:
        overall = "acceptable"
    else:
        overall = "poor"
    
    return {
        "quality_checked": True,
        "overall_quality": overall,
        "overall_score": score,
        "pass": score >= 50,
        "warnings": warnings,
        "checks": {
            "blur": blur,
            "brightness": brightness,
            "resolution": resolution,
            "contrast": contrast,
        },
    }
