"""
Biyometrik Yüz Eşleştirme Modülü
- Belge fotoğrafı ile canlı yüz karşılaştırma
- Liveness detection (spoofing önleme)
- Eşleştirme güven skoru
- Işık ve açı toleransı
"""
from datetime import datetime, timezone
from typing import Optional
import uuid
import json
import os
import random

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# Liveness challenges
LIVENESS_CHALLENGES = [
    {"challenge_id": "turn_right", "instruction": "Lütfen yüzünüzü sağa çevirin", "instruction_en": "Please turn your face to the right"},
    {"challenge_id": "turn_left", "instruction": "Lütfen yüzünüzü sola çevirin", "instruction_en": "Please turn your face to the left"},
    {"challenge_id": "look_up", "instruction": "Lütfen yukarı bakın", "instruction_en": "Please look up"},
    {"challenge_id": "smile", "instruction": "Lütfen gülümseyin", "instruction_en": "Please smile"},
    {"challenge_id": "blink", "instruction": "Lütfen gözlerinizi kırpın", "instruction_en": "Please blink your eyes"},
    {"challenge_id": "open_mouth", "instruction": "Lütfen ağzınızı açın", "instruction_en": "Please open your mouth"},
]


def get_liveness_challenge() -> dict:
    """Rastgele bir canlılık testi sorusu döndür"""
    challenge = random.choice(LIVENESS_CHALLENGES)
    return {
        "session_id": str(uuid.uuid4()),
        "challenge": challenge,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_in_seconds": 30,
    }


FACE_COMPARISON_PROMPT = """You are a biometric face matching expert for a hotel check-in verification system.

You will receive TWO images:
1. First image: A photo from an identity document (ID card, passport, etc.)
2. Second image: A live selfie/photo of a person

Your task is to compare the faces and determine if they are the SAME person.

ANALYSIS CRITERIA:
1. Facial structure similarity (jawline, cheekbones, forehead shape)
2. Eye shape and spacing
3. Nose shape and size
4. Mouth and lip shape
5. Overall proportions
6. Consider aging differences (document photo may be older)
7. Consider lighting and angle differences
8. Consider that document photos are often more formal/different quality

IMPORTANT RULES:
- Return ONLY valid JSON, no markdown, no extra text
- Be lenient with lighting/angle differences
- Consider natural aging (up to 10 years difference)
- Document photos are usually more formal/staged

Return this exact JSON structure:
{
    "match": true or false,
    "confidence_score": 0 to 100 (integer),
    "confidence_level": "high" (80-100) or "medium" (50-79) or "low" (0-49),
    "analysis": {
        "facial_structure": "match" or "partial" or "mismatch",
        "eyes": "match" or "partial" or "mismatch",
        "nose": "match" or "partial" or "mismatch",
        "mouth": "match" or "partial" or "mismatch",
        "overall_proportions": "match" or "partial" or "mismatch"
    },
    "notes": "Brief explanation of the comparison result",
    "warnings": ["list of any issues detected"],
    "image_quality": {
        "document_photo": "good" or "acceptable" or "poor",
        "selfie_photo": "good" or "acceptable" or "poor"
    }
}"""

LIVENESS_CHECK_PROMPT = """You are a liveness detection expert. Analyze the provided image to determine if this is a REAL live person or a SPOOF attempt (photo of a photo, video playback, mask, etc.).

The person was asked to perform this specific action: "{challenge_instruction}"

ANALYSIS CRITERIA:
1. Does the image appear to be a live capture (not a photo of a screen/photo)?
2. Is the person performing the requested action?
3. Look for signs of spoofing: screen edges, moiré patterns, flat appearance, printed paper edges
4. Check for natural skin texture, 3D depth cues, natural lighting on face
5. Check for proper head/face positioning indicating a live person

Return ONLY valid JSON:
{{
    "is_live": true or false,
    "challenge_completed": true or false,
    "confidence_score": 0 to 100,
    "spoof_indicators": ["list any detected spoof signs"],
    "analysis": {{
        "natural_lighting": true or false,
        "3d_depth_cues": true or false,
        "skin_texture": "natural" or "flat" or "pixelated",
        "screen_artifacts": false or true,
        "paper_edges": false or true
    }},
    "notes": "Brief explanation"
}}"""


async def compare_faces(document_image_b64: str, selfie_image_b64: str) -> dict:
    """İki yüzü karşılaştır: belge fotoğrafı vs canlı fotoğraf"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"face-match-{uuid.uuid4().hex[:8]}",
        system_message=FACE_COMPARISON_PROMPT
    )
    chat.with_model("openai", "gpt-4o")
    
    # Clean base64
    if "," in document_image_b64:
        document_image_b64 = document_image_b64.split(",")[1]
    if "," in selfie_image_b64:
        selfie_image_b64 = selfie_image_b64.split(",")[1]
    
    doc_image = ImageContent(image_base64=document_image_b64)
    selfie_image = ImageContent(image_base64=selfie_image_b64)
    
    user_message = UserMessage(
        text="Compare the faces in these two images. First image is from an identity document, second is a live selfie. Determine if they are the same person. Return ONLY JSON.",
        file_contents=[doc_image, selfie_image]
    )
    
    response = await chat.send_message(user_message)
    json_str = response.strip()
    
    # Clean markdown if present
    if json_str.startswith("```"):
        lines = json_str.split("\n")
        json_str = "\n".join(lines[1:-1]) if len(lines) > 2 else json_str[3:-3]
        json_str = json_str.strip()
    
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(json_str[start:end])
        else:
            result = {
                "match": False,
                "confidence_score": 0,
                "confidence_level": "low",
                "notes": "Yüz karşılaştırma analizi başarısız",
                "warnings": ["AI yanıtı ayrıştırılamadı"],
            }
    
    return result


async def check_liveness(image_b64: str, challenge_id: str) -> dict:
    """Canlılık testi: fotoğraf/video spoofing kontrolü"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    
    # Find challenge instruction
    challenge_instruction = "Yüzünüzü kameraya gösterin"
    for c in LIVENESS_CHALLENGES:
        if c["challenge_id"] == challenge_id:
            challenge_instruction = c["instruction"]
            break
    
    prompt = LIVENESS_CHECK_PROMPT.format(challenge_instruction=challenge_instruction)
    
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"liveness-{uuid.uuid4().hex[:8]}",
        system_message=prompt
    )
    chat.with_model("openai", "gpt-4o")
    
    if "," in image_b64:
        image_b64 = image_b64.split(",")[1]
    
    image = ImageContent(image_base64=image_b64)
    user_message = UserMessage(
        text=f"Check if this is a live person performing the action: '{challenge_instruction}'. Detect any spoofing attempts. Return ONLY JSON.",
        file_contents=[image]
    )
    
    response = await chat.send_message(user_message)
    json_str = response.strip()
    
    if json_str.startswith("```"):
        lines = json_str.split("\n")
        json_str = "\n".join(lines[1:-1]) if len(lines) > 2 else json_str[3:-3]
        json_str = json_str.strip()
    
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(json_str[start:end])
        else:
            result = {
                "is_live": False,
                "challenge_completed": False,
                "confidence_score": 0,
                "notes": "Canlılık analizi başarısız",
                "spoof_indicators": ["AI yanıtı ayrıştırılamadı"],
            }
    
    return result
