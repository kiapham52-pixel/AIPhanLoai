import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_PATH = BASE_DIR / "data" / "recycling_knowledge.json"

ALIASES = {
    "BIO": "BIODEGRADABLE",
    "BIODEGRADABLE": "BIODEGRADABLE",
    "CARD": "CARDBOARD",
    "CARDBOARD": "CARDBOARD",
    "GLASS": "GLASS",
    "METAL": "METAL",
    "PAPER": "PAPER",
    "PLASTIC": "PLASTIC",
}


def load_knowledge() -> Dict[str, Any]:
    if not KNOWLEDGE_PATH.exists():
        return {}
    with KNOWLEDGE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_material(material: Optional[str]) -> str:
    raw = (material or "").strip().upper().replace("-", "_").replace(" ", "_")
    if not raw:
        return "UNKNOWN"
    return ALIASES.get(raw, raw)


def find_material_profile(material: Optional[str]) -> Dict[str, Any]:
    key = normalize_material(material)
    data = load_knowledge()
    profile = data.get(key)
    if profile:
        return profile
    for name, profile in data.items():
        if profile.get("display_name", "").upper() == key.replace("_", " "):
            return profile
    return {}


def list_materials() -> List[str]:
    return list(load_knowledge().keys())


def get_recycling_profile(material: Optional[str]) -> Dict[str, Any]:
    profile = find_material_profile(material)
    if not profile:
        return {
            "name": "UNKNOWN",
            "display_name": "Vật liệu chưa xác định",
            "icon": "♻️",
            "color": "#6b7280",
            "description": "Mô hình chưa đủ dữ liệu để xác định chính xác vật liệu này.",
            "material_type": "unknown",
            "preparation": ["Đọc kỹ hướng dẫn và kiểm tra lại hình ảnh để tránh nhận diện sai."],
            "reuse_ideas": ["Tái sử dụng theo cách an toàn", "Đưa đến nơi thu gom phù hợp"],
            "diy_projects": [],
            "projects": [],
            "recycling_process": "Quy trình tái chế cần xác minh thêm.",
            "disposal_method": "Tiếp tục kiểm tra và nếu cần, liên hệ điểm thu gom phù hợp.",
            "warnings": ["Không tự bịa hướng dẫn hoặc xử lý vật liệu nguy hiểm khi chưa chắc chắn."],
        }
    return profile


def filter_projects(projects: Iterable[Dict[str, Any]], difficulty: Optional[str] = None, max_minutes: Optional[int] = None) -> List[Dict[str, Any]]:
    filtered = []
    for project in projects:
        if difficulty and str(project.get("difficulty", "")).lower() != str(difficulty).lower():
            continue
        if max_minutes is not None:
            time_text = str(project.get("time", "0-0")).lower()
            parsed = _extract_minutes(time_text)
            if parsed is not None and parsed > max_minutes:
                continue
        filtered.append(project)
    return filtered


def _extract_minutes(time_text: str) -> Optional[int]:
    if not time_text:
        return None
    text = time_text.lower().replace("phút", "").replace("minutes", "").replace("minute", "")
    parts = [part.strip() for part in text.split("-")]
    if len(parts) == 2:
        try:
            return int(parts[1])
        except ValueError:
            return None
    try:
        return int(text)
    except ValueError:
        return None


def get_material_projects(material: Optional[str], difficulty: Optional[str] = None, max_minutes: Optional[int] = None) -> List[Dict[str, Any]]:
    profile = get_recycling_profile(material)
    projects = list(profile.get("projects", []))
    return filter_projects(projects, difficulty=difficulty, max_minutes=max_minutes)


def search_knowledge(query: str) -> List[Dict[str, Any]]:
    text = _fold_text(query or "")
    if not text.strip():
        return []

    stop_words = {
        "the", "and", "for", "with", "from", "what", "how", "can", "could", "would", "should",
        "toi", "ban", "minh", "la", "gi", "co", "the", "lam", "nao", "voi", "cho", "mot", "nhung",
        "cai", "nay", "do", "duoc", "khong", "giup", "hay", "ve", "tu", "va", "de", "nen",
    }
    terms = {term for term in re.findall(r"[a-z0-9]+", text) if len(term) > 1 and term not in stop_words}
    if not terms:
        return []
    results = []
    for material_name, profile in load_knowledge().items():
        project_text = " ".join(
            " ".join([
                project.get("name", ""),
                project.get("category", ""),
                project.get("description", ""),
                project.get("final_product", ""),
                " ".join(project.get("materials", [])),
            ])
            for project in profile.get("projects", [])
        )
        haystack = _fold_text(" ".join([
            material_name,
            profile.get("display_name", ""),
            profile.get("description", ""),
            " ".join(profile.get("reuse_ideas", [])),
            project_text,
        ]))
        matched_terms = terms.intersection(re.findall(r"[a-z0-9]+", haystack))
        if matched_terms:
            results.append({
                "material": material_name,
                "display_name": profile.get("display_name"),
                "description": profile.get("description"),
                "icon": profile.get("icon"),
                "projects": profile.get("projects", [])[:3],
                "score": len(matched_terms),
            })
    return sorted(results, key=lambda item: item["score"], reverse=True)


def _fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d")
