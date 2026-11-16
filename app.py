from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, session
from werkzeug.utils import secure_filename

from services.chat_service import get_chat_backend, generate_fallback_chat_reply, generate_llm_reply
from services.config_service import get_flask_secret_key, get_session_cookie_secure
from services.detection_service import (
    ModelUnavailableError,
    build_result_payload,
    display_class_name,
    get_confidence_state,
    model,
    normalize_objects,
    predict_once,
)
from services.recycling_service import (
    get_material_projects,
    get_recycling_profile,
    list_materials,
    search_knowledge,
)
from services.recommendation_service import get_project_by_id, list_projects
from services.project_art_service import render_project_art

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
RESULTS_FOLDER = BASE_DIR / "static" / "results"
DATABASE_PATH = BASE_DIR / "waste_ai.db"
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
MAX_STORED_FILES = 100
MAX_CHAT_REQUESTS_PER_MINUTE = 20

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = get_flask_secret_key()
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["RESULTS_FOLDER"] = str(RESULTS_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = get_session_cookie_secure()


@app.before_request
def establish_anonymous_session():
    if not session.get("eco_vision_session_id"):
        session["eco_vision_session_id"] = uuid.uuid4().hex


def browser_session_id():
    return session["eco_vision_session_id"]


@app.context_processor
def inject_browser_session():
    return {"browser_session_id": browser_session_id()}



def init_db():
    conn = sqlite3_connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT,
            detected_class TEXT,
            confidence REAL,
            object_count INTEGER,
            created_at DATETIME,
            browser_session_id TEXT NOT NULL DEFAULT ''
        )
        """
    )
    detection_columns = {row[1] for row in conn.execute("PRAGMA table_info(detections)")}
    if "browser_session_id" not in detection_columns:
        conn.execute("ALTER TABLE detections ADD COLUMN browser_session_id TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_request_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            requested_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_request_log_window ON chat_request_log(session_id, requested_at)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_projects (
            session_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            saved_at DATETIME NOT NULL,
            PRIMARY KEY (session_id, project_id)
        )
        """
    )
    conn.commit()
    conn.close()


def sqlite3_connect():
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def reserve_chat_request(session_id, max_requests, window_seconds=60):
    now = time.time()
    cutoff = now - window_seconds
    conn = sqlite3_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM chat_request_log WHERE requested_at < ?", (cutoff,))
        count = conn.execute(
            "SELECT COUNT(*) FROM chat_request_log WHERE session_id = ? AND requested_at >= ?",
            (session_id, cutoff),
        ).fetchone()[0]
        if count >= max_requests:
            conn.rollback()
            return False
        conn.execute(
            "INSERT INTO chat_request_log (session_id, requested_at) VALUES (?, ?)",
            (session_id, now),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_chat_history(session_id, limit=12):
    conn = sqlite3_connect()
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [{"role": role, "content": content} for role, content in reversed(rows)]

def get_saved_projects(session_id):
    conn = sqlite3_connect()
    rows = conn.execute(
        "SELECT project_id FROM saved_projects WHERE session_id = ? ORDER BY saved_at DESC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [project for (project_id,) in rows if (project := get_project_by_id(project_id))]


def save_chat_message(session_id, role, content):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3_connect()
    conn.execute(
        "INSERT OR IGNORE INTO chat_sessions (session_id, created_at, updated_at) VALUES (?, ?, ?)",
        (session_id, now, now),
    )
    conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content[:2000], now),
    )
    conn.execute(
        "DELETE FROM chat_messages WHERE session_id = ? AND id NOT IN "
        "(SELECT id FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 12)",
        (session_id, session_id),
    )
    conn.commit()
    conn.close()


def save_detection_record(image_path, detected_class, confidence, object_count, browser_id=""):
    conn = sqlite3_connect()
    conn.execute(
        "INSERT INTO detections (image_path, detected_class, confidence, object_count, created_at, browser_session_id) VALUES (?, ?, ?, ?, ?, ?)",
        (image_path, detected_class, float(confidence), int(object_count), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), browser_id),
    )
    conn.commit()
    conn.close()


def cleanup_old_files(folder, keep=MAX_STORED_FILES):
    files = [path for path in folder.iterdir() if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for old_file in files[keep:]:
        try:
            old_file.unlink()
        except OSError:
            app.logger.warning("Could not remove old file: %s", old_file)


def normalize_history_item(row):
    image_path = str(row[0] or "").replace("\\", "/")
    uploads_marker = "/uploads/"
    if uploads_marker in image_path:
        image_path = f"uploads/{image_path.rsplit(uploads_marker, 1)[1]}"
    elif not image_path.startswith("uploads/"):
        image_path = ""

    confidence = float(row[2] or 0)
    if 0 < confidence <= 1:
        confidence *= 100

    detected_class = str(row[1] or "UNKNOWN OBJECT").upper()
    return {
        "image_path": image_path,
        "detected_class": detected_class,
        "display_class": display_class_name(detected_class),
        "confidence": confidence,
        "object_count": int(row[3] or 0),
        "created_at": row[4],
        "projects": list_projects(material=detected_class)[:3] if confidence >= 50 and detected_class in list_materials() else [],
    }


def parse_prediction_settings(default_image_size=320):
    try:
        confidence = float(request.form.get("confidence", "0.4"))
        image_size = int(request.form.get("image_size", str(default_image_size)))
    except (TypeError, ValueError) as error:
        raise ValueError("Thông số nhận diện không hợp lệ") from error

    if not 0 <= confidence <= 1:
        raise ValueError("Confidence phải nằm trong khoảng 0 đến 1")
    return confidence, max(320, min(image_size, 640))


def get_recycling_meta(class_name):
    profile = get_recycling_profile(class_name)
    return {
        "icon": profile.get("icon", "♻️"),
        "color": profile.get("color", "#4b5563"),
        "title": profile.get("display_name", "Vật liệu tái chế"),
        "description": profile.get("description", "Vật liệu này có thể được tái sử dụng hoặc đưa đến cơ sở tái chế phù hợp."),
        "easy": [
            {"icon": "♻️", "name": project.get("name", "Dự án tái chế"), "description": project.get("final_product", "")}
            for project in (profile.get("projects", [])[:2])
        ],
        "medium": [
            {"icon": "♻️", "name": project.get("name", "Dự án tái chế"), "description": project.get("final_product", "")}
            for project in (profile.get("projects", [])[2:4])
        ],
        "advanced": [{"icon": "♻️", "name": "Tái chế chuyên sâu", "description": profile.get("recycling_process", "Đưa đến điểm thu gom phù hợp.")}],
        "steps": profile.get("steps", ["Làm sạch", "Phân loại", "Đưa đến điểm thu gom phù hợp."]),
    }


def save_annotated_result(result, file_name):
    try:
        annotated = result.plot()
        if isinstance(annotated, np.ndarray):
            output_path = RESULTS_FOLDER / file_name
            if cv2.imwrite(str(output_path), annotated):
                cleanup_old_files(RESULTS_FOLDER)
                return f"/static/results/{file_name}"
    except Exception:
        app.logger.exception("Could not save annotated prediction image")
    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return render_template("index.html", message="Không có ảnh để phân tích.")

    image_file = request.files["image"]
    if not image_file.filename:
        return render_template("index.html", message="Vui lòng chọn ảnh trước khi phân tích.")

    safe_name = secure_filename(image_file.filename)
    if not safe_name:
        safe_name = "upload.jpg"
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    extension = Path(safe_name).suffix.lower()
    if extension not in allowed_extensions:
        return render_template("index.html", message="Định dạng ảnh không được hỗ trợ."), 400
    safe_name = f"{Path(safe_name).stem[:100]}{extension}"
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    image_path = UPLOAD_FOLDER / unique_name
    file_bytes = image_file.read()
    image_array = np.frombuffer(file_bytes, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR) if file_bytes else None
    if frame is None:
        return render_template("index.html", message="Tệp đã chọn không phải ảnh hợp lệ."), 400

    try:
        conf_threshold, image_size = parse_prediction_settings()
    except ValueError as error:
        return render_template("index.html", message=str(error)), 400

    image_path.write_bytes(file_bytes)
    cleanup_old_files(UPLOAD_FOLDER)
    try:
        result = predict_once(frame, conf_threshold, image_size)
    except ModelUnavailableError as error:
        app.logger.error("Upload prediction unavailable: %s", error)
        return render_template("index.html", message="Mô hình AI hiện không khả dụng."), 503
    except Exception:
        app.logger.exception("Upload image inference failed")
        return render_template("index.html", message="AI đang gặp lỗi khi phân tích ảnh."), 500
    if result is None:
        return render_template("index.html", message="AI đang bận, vui lòng thử lại sau."), 429

    try:
        objects = normalize_objects(result, conf_threshold)
    except Exception:
        app.logger.exception("Could not process upload detection results")
        return render_template("index.html", message="AI đang gặp lỗi khi xử lý kết quả."), 500

    if not objects:
        return render_template(
            "index.html",
            result_image=f"/uploads/{unique_name}",
            top_class="UNKNOWN OBJECT",
            top_class_label=display_class_name("UNKNOWN OBJECT"),
            best_confidence=0,
            object_count=0,
            objects=[],
            recycling=None,
            projects=[],
            message="AI chưa đủ chắc chắn để xác định vật thể. Vật thể có thể nằm ngoài phạm vi dữ liệu mà hệ thống được huấn luyện.",
            low_confidence=True,
            chat_context={},
        )

    best = objects[0]
    best_confidence = float(best["confidence_pct"])
    low_confidence = best_confidence < 50
    top_class = "UNKNOWN OBJECT" if low_confidence else best["class"]
    result_image_path = save_annotated_result(result, f"result_{uuid.uuid4().hex}.jpg")
    recycling = None if low_confidence else get_recycling_meta(best["class"])
    projects = list_projects(material=best["class"])[:3] if not low_confidence else []
    message = "AI chưa đủ chắc chắn để xác định vật thể. Vật thể này có thể nằm ngoài phạm vi dữ liệu huấn luyện." if low_confidence else "AI đã phân loại thành công và có thể sử dụng để định hướng tái chế phù hợp."
    save_detection_record(
        f"uploads/{unique_name}",
        top_class,
        best_confidence,
        len(objects),
        browser_session_id(),
    )

    return render_template(
        "index.html",
        result_image=result_image_path,
        objects=objects,
        top_class=top_class,
        top_class_label=display_class_name(top_class),
        best_confidence=best_confidence,
        object_count=len(objects),
        recycling=recycling,
        projects=projects,
        low_confidence=low_confidence,
        message=message,
        chat_context={
            "last_detection": best["class"] if not low_confidence else "",
            "display_name": display_class_name(best["class"]) if not low_confidence else "",
            "confidence": best["confidence"],
            "object_count": len(objects),
        },
    )


@app.route("/camera")
def camera():
    return render_template("camera.html")


@app.route("/explore")
def explore_page():
    projects = list_projects()
    categories = sorted({project.get("category", "") for project in projects if project.get("category")})
    return render_template(
        "explore.html",
        projects=projects,
        categories=categories,
        active_material=request.args.get("material", "").upper(),
        search_query=request.args.get("q", ""),
    )


@app.route("/projects/<project_id>")
def project_detail_page(project_id):
    project = get_project_by_id(project_id)
    if not project:
        return render_template("project_detail.html", project=None), 404
    profile = get_recycling_profile(project.get("material"))
    return render_template("project_detail.html", project=project, profile=profile)


@app.route("/project-art/<project_id>.svg")
def project_art(project_id):
    project = get_project_by_id(project_id)
    if not project:
        return "Project illustration not found", 404
    return Response(render_project_art(project), mimetype="image/svg+xml")


@app.route("/api/health")
def api_health():
    model_status = "ok" if model is not None else "unavailable"
    try:
        conn = sqlite3_connect()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        database_status = "ok"
    except sqlite3.Error:
        database_status = "unavailable"
    try:
        chat_status = "llm" if get_chat_backend()[0] else "knowledge_fallback"
    except ValueError:
        chat_status = "misconfigured"
    return jsonify({
        "server": "ok",
        "database": database_status,
        "model": model_status,
        "chat": chat_status,
    })


@app.route("/api/recycling", methods=["GET"])
@app.route("/api/recycling/", methods=["GET"])
@app.route("/api/recycling/<material>", methods=["GET"])
def api_recycling(material=None):
    if material is None:
        return jsonify({"success": True, "materials": list_materials()})

    profile = get_recycling_profile(material)
    if not profile.get("display_name"):
        return jsonify({"success": False, "message": "Vật liệu không tồn tại."}), 404

    projects = get_material_projects(material)
    response = {
        "success": True,
        "material": str(material).upper(),
        "display_name": profile.get("display_name"),
        "icon": profile.get("icon"),
        "color": profile.get("color"),
        "description": profile.get("description"),
        "material_type": profile.get("material_type"),
        "preparation": profile.get("preparation", []),
        "reuse_ideas": profile.get("reuse_ideas", []),
        "diy_projects": profile.get("diy_projects", []),
        "projects": projects,
        "recycling_process": profile.get("recycling_process"),
        "disposal_method": profile.get("disposal_method"),
        "warnings": profile.get("warnings", []),
    }
    return jsonify(response)


@app.route("/api/projects", methods=["GET"])
@app.route("/api/projects/", methods=["GET"])
def api_projects():
    material = request.args.get("material")
    difficulty = request.args.get("difficulty")
    max_minutes = request.args.get("max_minutes", type=int)
    category = request.args.get("category")
    projects = list_projects(
        material=material,
        difficulty=difficulty,
        max_minutes=max_minutes,
        category=category,
    )
    return jsonify({"success": True, "projects": projects})

@app.route("/api/projects/<project_id>", methods=["GET"])
def api_project_detail(project_id):
    project = get_project_by_id(project_id)
    if not project:
        return jsonify({"success": False, "message": "Không tìm thấy hướng dẫn này."}), 404
    return jsonify({"success": True, "project": project})


@app.route("/api/favorites", methods=["GET", "POST"])
def api_favorites():
    session_id = browser_session_id()
    if request.method == "GET":
        conn = sqlite3_connect()
        rows = conn.execute(
            "SELECT project_id FROM saved_projects WHERE session_id = ? ORDER BY saved_at DESC",
            (session_id,),
        ).fetchall()
        conn.close()
        projects = [project for (project_id,) in rows if (project := get_project_by_id(project_id))]
        return jsonify({"success": True, "projects": projects})

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "Nội dung gửi chưa đúng định dạng."}), 400
    project_id = str(payload.get("project_id") or "").strip()[:100]
    action = payload.get("action", "save")
    if action not in {"save", "remove"}:
        return jsonify({"success": False, "message": "Thông tin lưu chưa hợp lệ."}), 400
    if not get_project_by_id(project_id):
        return jsonify({"success": False, "message": "Không tìm thấy hướng dẫn này."}), 404

    conn = sqlite3_connect()
    if action == "save":
        conn.execute(
            "INSERT OR IGNORE INTO saved_projects (session_id, project_id, saved_at) VALUES (?, ?, ?)",
            (session_id, project_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    else:
        conn.execute("DELETE FROM saved_projects WHERE session_id = ? AND project_id = ?", (session_id, project_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "saved": action == "save"})


@app.route("/api/search", methods=["GET"])
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"success": False, "message": "Bạn chưa nhập từ khóa tìm kiếm."}), 400
    return jsonify({"success": True, "results": search_knowledge(query)})


@app.route("/uploads/<path:filename>")
def uploaded_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/camera/predict", methods=["POST"])
def camera_predict():
    if "image" not in request.files:
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": "Không có ảnh camera"}), 400

    image_file = request.files["image"]
    file_bytes = image_file.read()
    if not file_bytes:
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": "Không có dữ liệu ảnh"}), 400

    image_array = np.frombuffer(file_bytes, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": "Không đọc được ảnh"}), 400

    try:
        conf_threshold, image_size = parse_prediction_settings()
        result = predict_once(frame, conf_threshold, image_size)
    except ValueError as error:
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": str(error)}), 400
    except ModelUnavailableError as error:
        app.logger.error("Camera prediction unavailable: %s", error)
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": "Mô hình AI hiện không khả dụng"}), 503
    except Exception:
        app.logger.exception("Camera inference failed")
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": "AI đang gặp lỗi"}), 500

    if result is None:
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": "AI đang bận, vui lòng thử lại sau"}), 429

    try:
        objects = normalize_objects(result, conf_threshold)
        best = objects[0] if objects else None
        best_confidence = float(best["confidence_pct"]) if best else 0.0
        low_confidence = bool(best) and best_confidence < 50
        top_class = "UNKNOWN OBJECT" if low_confidence else (best["class"] if best else None)
        detection_status = (
            "not_detected" if not objects else "uncertain" if low_confidence else "recognized"
        )
        payload = build_result_payload(
            [
                {
                    "class": item["class"],
                    "display_class": item.get("display_class", display_class_name(item["class"])),
                    "confidence": item["confidence"],
                    "box": item["box"],
                    "color": item["color"],
                }
                for item in objects
            ],
            top_class=top_class,
            best_confidence=best_confidence,
            recycling=get_recycling_meta(best["class"]) if best and not low_confidence else None,
            low_confidence=low_confidence,
        )
        payload.update({
            "success": True,
            "detected": bool(objects),
            "detection_status": detection_status,
            "message": (
                "Không tìm thấy vật thể thuộc 6 lớp được hỗ trợ."
                if not objects else
                "Dự đoán chưa đủ tin cậy; hãy kiểm tra lại hoặc chụp khung hình khác."
                if low_confidence else
                "AI đã nhận diện vật thể trong một trong 6 lớp được hỗ trợ."
            ),
        })
        return jsonify(payload)
    except Exception:
        app.logger.exception("Could not format camera detection response")
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": "AI đang gặp lỗi"}), 500



@app.route("/favorites")
def favorites_page():
    return render_template("favorites.html", projects=get_saved_projects(browser_session_id()))


@app.route("/history")
def history_page():
    conn = sqlite3_connect()
    rows = conn.execute(
        "SELECT image_path, detected_class, confidence, object_count, created_at FROM detections "
        "WHERE browser_session_id = ? ORDER BY id DESC LIMIT 20",
        (browser_session_id(),),
    ).fetchall()
    conn.close()

    history = [normalize_history_item(row) for row in rows]
    return render_template("history.html", history=history)


@app.route("/api/history")
def history_api():
    conn = sqlite3_connect()
    rows = conn.execute(
        "SELECT image_path, detected_class, confidence, object_count, created_at FROM detections "
        "WHERE browser_session_id = ? ORDER BY id DESC LIMIT 20",
        (browser_session_id(),),
    ).fetchall()
    conn.close()

    data = [normalize_history_item(row) for row in rows]
    return jsonify({"success": True, "history": data})


@app.route("/guide")
def guide_page():
    return render_template("guide.html")


@app.route("/about")
def about_page():
    return render_template("about.html")


@app.route("/api/chat", methods=["POST"])
def chat_api():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "reply": "Nội dung gửi chưa đúng định dạng."}), 400
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"success": False, "reply": "Bạn chưa nhập câu hỏi."}), 400
    if len(message) > 2000:
        return jsonify({"success": False, "reply": "Câu hỏi quá dài. Vui lòng rút gọn còn tối đa 2.000 ký tự."}), 400

    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    session_id = browser_session_id()
    if not reserve_chat_request(session_id, MAX_CHAT_REQUESTS_PER_MINUTE):
        return jsonify({
            "success": False,
            "reply": "Bạn đã gửi 20 câu hỏi trong một phút. Hãy thử lại sau ít phút.",
            "retry_after": 60,
        }), 429, {"Retry-After": "60"}
    supplied_history = payload.get("conversation_history")
    conversation_history = get_chat_history(session_id)
    if not conversation_history and isinstance(supplied_history, list):
        conversation_history = [
            {"role": item["role"], "content": str(item.get("content") or "")[:2000]}
            for item in supplied_history[-12:]
            if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and item.get("content")
        ]

    try:
        llm_reply = generate_llm_reply(message, context, conversation_history)
    except Exception:
        app.logger.exception("LLM chat failed")
        return jsonify({
            "success": False,
            "reply": "Không thể kết nối dịch vụ AI lúc này. Kiểm tra cấu hình API và thử lại.",
            "mode": "provider_error",
        }), 502

    if llm_reply:
        save_chat_message(session_id, "user", message)
        save_chat_message(session_id, "assistant", llm_reply)
        return jsonify({"success": True, "reply": llm_reply, "mode": "llm"})

    reply = generate_fallback_chat_reply(message, context, conversation_history)
    if reply == "Câu hỏi này cần trợ lý ngôn ngữ được kết nối để trả lời chính xác.":
        return jsonify({
            "success": False,
            "reply": (
                "Trợ lý AI đa năng chưa được kết nối. Tạo tệp .env ở thư mục gốc, điền một trong hai cấu hình "
                "sau rồi khởi động lại ứng dụng (có thể sao chép .env.example thành .env):\n\n"
                "OpenAI:\nCHAT_PROVIDER=openai\nOPENAI_API_KEY=your_openai_api_key\n"
                "OPENAI_MODEL=gpt-4o-mini\n\n"
                "Gemini:\nCHAT_PROVIDER=gemini\nGEMINI_API_KEY=your_gemini_api_key\n"
                "GEMINI_MODEL=gemini-2.5-flash\n\n"
                "Không gửi API key trong tin nhắn hoặc mã frontend."
            ),
            "mode": "unavailable",
            "setup_required": True,
        }), 503
    reply = (
        "Chưa cấu hình API AI; câu trả lời sau đây chỉ tra cứu thư viện tái chế có sẵn, không phải nội dung "
        "do mô hình ngôn ngữ tạo. Hãy xem cấu hình API trong thư mục gốc để bật trợ lý đa năng.\n\n"
        + reply
    )
    try:
        save_chat_message(session_id, "user", message)
        save_chat_message(session_id, "assistant", reply)
    except sqlite3.Error:
        app.logger.exception("Could not persist chat history")
    return jsonify({"success": True, "reply": reply, "mode": "knowledge_fallback"})


def generate_llm_reply(message, context, conversation_history=None):
    from services.chat_service import generate_llm_reply as service_generate_llm_reply

    return service_generate_llm_reply(message, context, conversation_history)


def generate_fallback_chat_reply(message, context, conversation_history=None):
    from services.chat_service import generate_fallback_chat_reply as service_generate_fallback_chat_reply

    return service_generate_fallback_chat_reply(message, context, conversation_history)


@app.errorhandler(413)
def request_too_large(_error):
    message = "Tệp quá lớn (tối đa 16 MB)"
    if request.path.startswith("/camera/"):
        return jsonify({"success": False, "detected": False, "object_count": 0, "objects": [], "message": message}), 413
    return render_template("index.html", message=message), 413


@app.errorhandler(500)
def internal_error(_error):
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"success": False, "message": "Có vẻ hệ thống đang gặp chút trục trặc. Hãy thử lại sau."}), 500
    return render_template("error.html"), 500


def init_app():
    init_db()


init_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)