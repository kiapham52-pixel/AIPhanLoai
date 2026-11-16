import logging
import threading
from pathlib import Path

from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_RELATIVE_PATH = Path("models/phan_loai_rac.pt")
MODEL_PATH = BASE_DIR / MODEL_RELATIVE_PATH

model: YOLO | None = None
try:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Không tìm thấy model: {MODEL_RELATIVE_PATH.as_posix()}")
    model = YOLO(str(MODEL_PATH))
    model.to("cpu")
except Exception:
    logging.getLogger(__name__).exception("Could not load YOLO model: %s", MODEL_RELATIVE_PATH.as_posix())
    model = None

INFERENCE_LOCK = threading.BoundedSemaphore(1)

CLASS_COLORS = {
    "BIODEGRADABLE": "#667d58",
    "CARDBOARD": "#a97858",
    "GLASS": "#4f8b87",
    "METAL": "#72786f",
    "PAPER": "#6f8b79",
    "PLASTIC": "#bd8050",
}
SUPPORTED_CLASSES = frozenset(CLASS_COLORS)

DISPLAY_CLASS_LABELS = {
    "BIODEGRADABLE": "Rác hữu cơ",
    "CARDBOARD": "Bìa carton",
    "GLASS": "Thủy tinh",
    "METAL": "Kim loại",
    "PAPER": "Giấy",
    "PLASTIC": "Nhựa",
    "UNKNOWN OBJECT": "Chưa đủ chắc chắn",
}


class ModelUnavailableError(RuntimeError):
    pass


def predict_once(source, confidence, image_size):
    if model is None:
        raise ModelUnavailableError(f"YOLO model is unavailable: {MODEL_RELATIVE_PATH.as_posix()}")
    if not INFERENCE_LOCK.acquire(blocking=False):
        return None
    try:
        results = model.predict(
            source=source,
            conf=confidence,
            imgsz=image_size,
            iou=0.45,
            device="cpu",
            verbose=False,
        )
        return results[0] if results else None
    finally:
        INFERENCE_LOCK.release()


def normalize_objects(result, conf_threshold=0.4):
    if model is None:
        raise ModelUnavailableError(f"YOLO model is unavailable: {MODEL_RELATIVE_PATH.as_posix()}")
    objects = []
    if result is None or result.boxes is None:
        return objects

    for box in result.boxes:
        confidence = float(box.conf.cpu().item())
        if confidence < conf_threshold:
            continue
        class_id = int(box.cls.cpu().item())
        class_name = model.names.get(class_id, str(class_id)).upper()
        if class_name not in SUPPORTED_CLASSES:
            continue
        x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].cpu().tolist()]
        objects.append({
            "class": class_name,
            "display_class": display_class_name(class_name),
            "confidence": round(confidence, 4),
            "confidence_pct": round(confidence * 100, 2),
            "box": [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))],
            "color": CLASS_COLORS.get(class_name, "#72786f"),
        })
    return sorted(objects, key=lambda item: item["confidence"], reverse=True)


def display_class_name(class_name):
    normalized = (class_name or "").upper()
    return DISPLAY_CLASS_LABELS.get(normalized, "Chưa đủ chắc chắn")


def get_confidence_state(confidence_pct):
    if confidence_pct >= 80:
        return "Độ tin cậy cao"
    if confidence_pct >= 50:
        return "Độ tin cậy trung bình"
    return "Độ tin cậy thấp"


def build_result_payload(objects, top_class=None, best_confidence=0.0, recycling=None, low_confidence=False):
    if low_confidence:
        top_class = "UNKNOWN OBJECT"
    return {
        "top_class": top_class,
        "display_class": display_class_name(top_class),
        "best_confidence": float(best_confidence),
        "low_confidence": bool(low_confidence),
        "confidence_state": get_confidence_state(float(best_confidence)),
        "recycling": recycling,
        "object_count": len(objects),
        "objects": objects,
    }