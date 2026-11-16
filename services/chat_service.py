import json
from typing import Any, Dict, List, Optional
from urllib import request as urllib_request
from urllib.parse import quote

from services.config_service import get_setting
from services.recycling_service import (
    get_recycling_profile,
    list_materials,
    normalize_material,
    search_knowledge,
)

SYSTEM_PROMPT = (
    "Bạn là trợ lý AI đa năng của ECO VISION AI. Trả lời tự nhiên bằng ngôn ngữ người dùng sử dụng, "
    "có thể hỗ trợ câu hỏi phổ thông cũng như AI, computer vision, YOLO, môi trường, phân loại vật liệu, "
    "tái sử dụng và DIY. Dùng tri thức cấu trúc được cung cấp làm nguồn đáng tin cậy cho hướng dẫn tái chế. "
    "Chỉ dùng kết quả nhận diện khi backend cung cấp vật liệu đã biết với confidence từ 50% trở lên. "
    "Không bịa kết quả nhận diện, thành phần vật liệu, quy định địa phương hoặc hướng dẫn an toàn; nếu chưa chắc, "
    "nói rõ giới hạn và đề nghị xác minh. Trả lời súc tích, hữu ích, không ép mọi câu hỏi vào chủ đề rác."
)


def build_chat_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = context if isinstance(context, dict) else {}
    detection = raw.get("last_detection") or raw.get("material") or ""
    if isinstance(detection, dict):
        detection = detection.get("material") or detection.get("class") or ""
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence > 1:
        confidence /= 100
    try:
        object_count = max(0, int(raw.get("object_count") or 0))
    except (TypeError, ValueError):
        object_count = 0
    material = normalize_material(str(detection)) if detection else ""
    if material not in list_materials() or confidence < 0.5:
        material = ""
    return {
        "last_detection": material,
        "display_name": str(raw.get("display_name") or "").strip(),
        "confidence": min(max(confidence, 0.0), 1.0),
        "object_count": object_count,
        "uncertain_detection": bool(detection) and confidence < 0.5,
    }


def build_system_instruction(context: Optional[Dict[str, Any]], message: str = "") -> str:
    normalized = build_chat_context(context)
    instruction = SYSTEM_PROMPT
    if normalized["last_detection"]:
        material = normalized["last_detection"]
        profile = get_recycling_profile(material)
        instruction += (
            f"\nNgữ cảnh nhận diện gần nhất do website cung cấp: {profile.get('display_name', material)}, "
            f"độ tin cậy {normalized['confidence']:.0%}, {normalized['object_count']} vật thể. Đây là dự đoán hình ảnh, "
            "không phải xác minh thành phần vật liệu. Hướng dẫn chuẩn bị: "
            f"{'; '.join(profile.get('preparation', [])[:3])}. Quy trình tham khảo: "
            f"{profile.get('recycling_process', '')}"
        )
    elif normalized["uncertain_detection"]:
        instruction += "\nNhận diện gần nhất dưới 50% nên không thể dùng để kết luận loại vật liệu; hãy hỏi thêm thay vì đoán."
    if normalized["object_count"]:
        instruction += f"\nSố vật thể được trả về trong lần quét gần nhất: {normalized['object_count']}."

    matches = search_knowledge(message)[:2]
    if matches:
        knowledge = []
        for match in matches:
            project_names = ", ".join(project.get("name", "") for project in match.get("projects", [])[:3])
            knowledge.append(
                f"{match.get('display_name')}: {match.get('description')} "
                f"Dự án trong kho: {project_names}."
            )
        instruction += "\nTri thức có cấu trúc liên quan:\n" + "\n".join(knowledge)
    return instruction


def get_chat_backend() -> tuple[Optional[str], Optional[str]]:
    provider = get_setting("CHAT_PROVIDER", "auto").lower()
    if provider not in {"auto", "openai", "gemini"}:
        raise ValueError("CHAT_PROVIDER must be auto, openai, or gemini")

    openai_key = get_setting("OPENAI_API_KEY")
    gemini_key = get_setting("GEMINI_API_KEY")
    if provider == "openai":
        return ("openai", openai_key) if openai_key else (None, None)
    if provider == "gemini":
        return ("gemini", gemini_key) if gemini_key else (None, None)
    if openai_key:
        return "openai", openai_key
    if gemini_key:
        return "gemini", gemini_key
    return None, None


def _generate_gemini_reply(
    message: str,
    api_key: str,
    instruction: str,
    conversation_history: Optional[List[Dict[str, str]]],
) -> str:
    contents = []
    for item in (conversation_history or [])[-12:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()[:2000]
        if content:
            contents.append({
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": content}],
            })
    contents.append({"role": "user", "parts": [{"text": message[:2000]}]})

    request_body = {
        "systemInstruction": {"parts": [{"text": instruction}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 700},
    }
    model_name = quote(get_setting("GEMINI_MODEL", "gemini-2.5-flash"), safe="-")
    req = urllib_request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    candidates = payload.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
    answer = "\n".join(str(part.get("text") or "") for part in parts).strip()
    if not answer:
        raise RuntimeError("Gemini returned no text response")
    return answer


def generate_llm_reply(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Optional[str]:
    provider, api_key = get_chat_backend()
    if not provider or not api_key:
        return None

    instruction = build_system_instruction(context, message)
    if provider == "gemini":
        return _generate_gemini_reply(message, api_key, instruction, conversation_history)

    messages = [{"role": "system", "content": instruction}]
    for item in (conversation_history or [])[-12:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()[:2000]
        if content:
            messages.append({"role": item["role"], "content": content})
    messages.append({"role": "user", "content": message[:2000]})

    request_body = {
        "model": get_setting("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 500,
    }
    req = urllib_request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {api_key}")
    with urllib_request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI returned no text response")
    answer = str((choices[0].get("message") or {}).get("content") or "").strip()
    if not answer:
        raise RuntimeError("OpenAI returned no text response")
    return answer


def generate_fallback_chat_reply(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    normalized = build_chat_context(context)
    lower_message = message.casefold()
    references_first = any(phrase in lower_message for phrase in ("cái đầu tiên", "ý tưởng đầu tiên", "thứ nhất", "first one", "the first"))
    if references_first:
        matches = []
        for item in reversed(conversation_history or []):
            if item.get("role") != "user":
                continue
            matches = search_knowledge(str(item.get("content") or ""))
            if matches:
                break
        if matches:
            profile = get_recycling_profile(matches[0]["material"])
            project = (profile.get("projects") or [None])[0]
            if project:
                materials = ", ".join(project.get("materials", [])[:4])
                final_product = str(project.get("final_product") or "").strip().rstrip(".")
                if final_product.casefold() == str(project.get("name") or "").casefold():
                    final_product = f"một {final_product.lower()} làm từ vật liệu đã qua sử dụng"
                return (
                    f"Ý tưởng đầu tiên cho {profile.get('display_name')} là {project.get('name')}. "
                    f"Thành phẩm là {final_product}. Bạn cần {materials}. "
                    f"Mở hướng dẫn chi tiết tại /projects/{project.get('id')}."
                )

    matches = search_knowledge(message)
    if matches:
        match = matches[0]
        profile = get_recycling_profile(match["material"])
        projects = profile.get("projects", [])[:3]
        project_names = ", ".join(project.get("name", "") for project in projects)
        description = str(profile.get("description") or "").strip()
        answer = f"Theo dữ liệu hiện có: {description}"
        if project_names:
            answer += f" Một vài hướng dẫn phù hợp: {project_names}."
        answer += " Mở từng hướng dẫn để xem nguyên liệu, dụng cụ, các bước và lưu ý an toàn."
        return answer

    if normalized["last_detection"]:
        return "Câu hỏi này cần trợ lý ngôn ngữ được kết nối để trả lời chính xác."

    return "Câu hỏi này cần trợ lý ngôn ngữ được kết nối để trả lời chính xác."