import io
import json
import sqlite3
import uuid
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

import app as app_module
from services import chat_service
from services import config_service
from services import detection_service
from app import app


def create_https_test_client():
    client = app.test_client()
    client.environ_base["wsgi.url_scheme"] = "https"
    return client


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "waste_ai_test.db")
    upload_folder = tmp_path / "uploads"
    results_folder = tmp_path / "results"
    upload_folder.mkdir()
    results_folder.mkdir()
    monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload_folder)
    monkeypatch.setattr(app_module, "RESULTS_FOLDER", results_folder)
    app_module.init_db()
    app.config["TESTING"] = True
    with create_https_test_client() as client:
        yield client


def test_session_cookie_is_secure_http_only_and_same_site_lax(client, monkeypatch):
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", True)
    response = client.get("/api/health")

    assert app.config["SESSION_COOKIE_SECURE"] is True
    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


@pytest.mark.parametrize(
    ("environment", "secure_override", "expected"),
    [
        ("development", "", False),
        ("production", "", True),
    ],
)
def test_session_cookie_policy_by_environment(monkeypatch, environment, secure_override, expected):
    settings = {"APP_ENV": environment, "SESSION_COOKIE_SECURE": secure_override}
    monkeypatch.setattr(
        config_service,
        "get_setting",
        lambda name, default="": settings.get(name, default),
    )

    assert config_service.get_session_cookie_secure() is expected


def test_production_session_cookie_cannot_be_configured_insecure(monkeypatch):
    settings = {"APP_ENV": "production", "SESSION_COOKIE_SECURE": "false"}
    monkeypatch.setattr(
        config_service,
        "get_setting",
        lambda name, default="": settings.get(name, default),
    )

    with pytest.raises(ValueError, match="cannot be false in production"):
        config_service.get_session_cookie_secure()


def test_development_cookie_is_not_secure_over_local_http(client, monkeypatch):
    settings = {"APP_ENV": "development"}
    monkeypatch.setattr(
        config_service,
        "get_setting",
        lambda name, default="": settings.get(name, default),
    )
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", config_service.get_session_cookie_secure())
    client.environ_base["wsgi.url_scheme"] = "http"

    response = client.get("/api/health")

    assert "Secure" not in response.headers["Set-Cookie"]
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]


def test_sqlite_connections_enforce_declared_foreign_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "waste_ai_test.db")
    app_module.init_db()
    conn = app_module.sqlite3_connect()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                ("missing-session", "user", "test", "2026-01-01 00:00:00"),
            )
    finally:
        conn.close()


def test_health_endpoint_returns_system_status(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["server"] == "ok"
    assert payload["model"] in {"ok", "unavailable"}


def test_health_endpoint_remains_available_when_model_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(app_module, "model", None)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["model"] == "unavailable"


def test_loaded_model_keeps_the_six_class_order_and_cpu_device():
    model = detection_service.model
    assert model is not None
    assert model.names == {
        0: "BIODEGRADABLE",
        1: "CARDBOARD",
        2: "GLASS",
        3: "METAL",
        4: "PAPER",
        5: "PLASTIC",
    }
    assert next(model.model.parameters()).device.type == "cpu"


def test_camera_api_returns_503_when_model_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(detection_service, "model", None)
    success, encoded = app_module.cv2.imencode(".jpg", app_module.np.zeros((32, 32, 3), dtype="uint8"))
    assert success

    response = client.post(
        "/camera/predict",
        data={"image": (io.BytesIO(encoded.tobytes()), "camera.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert response.get_json()["success"] is False
    assert "không khả dụng" in response.get_json()["message"]


def test_upload_returns_503_when_model_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(detection_service, "model", None)
    success, encoded = app_module.cv2.imencode(".jpg", app_module.np.zeros((32, 32, 3), dtype="uint8"))
    assert success

    response = client.post(
        "/predict",
        data={"image": (io.BytesIO(encoded.tobytes()), "upload.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert "Mô hình AI hiện không khả dụng." in response.get_data(as_text=True)


def test_recycling_endpoint_returns_structured_material_data(client):
    response = client.get("/api/recycling/PLASTIC")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["material"] == "PLASTIC"
    assert "projects" in payload
    assert len(payload["projects"]) >= 3


def test_project_detail_endpoint_returns_a_knowledge_base_project(client):
    response = client.get("/api/projects/plastic-planter")
    assert response.status_code == 200
    project = response.get_json()["project"]
    assert project["material"] == "PLASTIC"
    assert project["display_name"] == "Nhựa"
    assert project["steps"]


def test_project_detail_endpoint_returns_404_for_unknown_project(client):
    response = client.get("/api/projects/not-a-project")
    assert response.status_code == 404


def test_every_project_has_a_unique_local_illustration_and_practical_details(client):
    projects = client.get("/api/projects").get_json()["projects"]
    assert len(projects) == 22
    illustrations = []
    for project in projects:
        assert project["image"] == f"/project-art/{project['id']}.svg"
        assert project["materials"]
        assert project["tools"]
        assert project["time"]
        assert project["difficulty"]
        assert project["steps"]
        response = client.get(project["image"])
        assert response.status_code == 200
        assert response.mimetype == "image/svg+xml"
        ElementTree.fromstring(response.data)
        illustrations.append(response.get_data())
    assert len(set(illustrations)) == len(projects)


def test_favorites_are_persisted_per_session(client):
    session_id = f"test-{uuid.uuid4().hex}"
    save_response = client.post(
        "/api/favorites",
        json={"session_id": session_id, "project_id": "plastic-planter", "action": "save"},
    )
    assert save_response.status_code == 200
    saved = client.get("/api/favorites", query_string={"session_id": session_id}).get_json()
    assert [project["id"] for project in saved["projects"]] == ["plastic-planter"]

    client.post(
        "/api/favorites",
        json={"session_id": session_id, "project_id": "plastic-planter", "action": "remove"},
    )
    removed = client.get("/api/favorites", query_string={"session_id": session_id}).get_json()
    assert removed["projects"] == []


def test_favorites_are_isolated_by_signed_browser_session(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "waste_ai_test.db")
    app_module.init_db()
    first_browser = create_https_test_client()
    second_browser = create_https_test_client()
    first_browser.post(
        "/api/favorites",
        json={"session_id": "forged-shared-session", "project_id": "plastic-planter", "action": "save"},
    )

    first_projects = first_browser.get("/api/favorites?session_id=forged-shared-session").get_json()["projects"]
    second_projects = second_browser.get("/api/favorites?session_id=forged-shared-session").get_json()["projects"]
    assert [project["id"] for project in first_projects] == ["plastic-planter"]
    assert second_projects == []


def test_upload_with_no_detections_renders_uncertain_state(client, monkeypatch):
    monkeypatch.setattr(app_module, "predict_once", lambda *_args: SimpleNamespace(boxes=None))
    success, encoded = app_module.cv2.imencode(".jpg", app_module.np.zeros((32, 32, 3), dtype="uint8"))
    assert success

    response = client.post(
        "/predict",
        data={"image": (io.BytesIO(encoded.tobytes()), "unrecognized.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert "AI chưa đủ chắc chắn" in response.get_data(as_text=True)


def test_upload_rejects_invalid_image_contents(client):
    response = client.post(
        "/predict",
        data={"image": (io.BytesIO(b"not an image"), "invalid.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "Tệp đã chọn không phải ảnh hợp lệ." in response.get_data(as_text=True)


def test_camera_api_rejects_invalid_image_contents(client):
    response = client.post(
        "/camera/predict",
        data={"image": (io.BytesIO(b"not an image"), "camera.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_detection_service_rejects_classes_outside_the_six_trained_labels(monkeypatch):
    class FakeValue:
        def __init__(self, value):
            self.value = value

        def cpu(self):
            return self

        def item(self):
            return self.value

        def tolist(self):
            return self.value

    class FakeBox:
        def __init__(self, class_id, confidence):
            self.cls = FakeValue(class_id)
            self.conf = FakeValue(confidence)
            self.xyxy = [FakeValue([1, 2, 20, 30])]

    monkeypatch.setattr(
        detection_service,
        "model",
        SimpleNamespace(names={0: "SHIRT", 1: "PAPER", 2: "PLASTIC"}),
    )

    objects = detection_service.normalize_objects(
        SimpleNamespace(boxes=[FakeBox(0, 0.99), FakeBox(1, 0.42), FakeBox(2, 0.83)]),
        conf_threshold=0.25,
    )

    assert [item["class"] for item in objects] == ["PLASTIC", "PAPER"]
    assert [item["confidence_pct"] for item in objects] == [83.0, 42.0]


def test_camera_api_reports_low_confidence_as_uncertain(client, monkeypatch):
    monkeypatch.setattr(app_module, "predict_once", lambda *_args: object())
    monkeypatch.setattr(
        app_module,
        "normalize_objects",
        lambda *_args: [{
            "class": "PAPER",
            "display_class": "Giấy",
            "confidence": 0.42,
            "confidence_pct": 42.0,
            "box": [1, 2, 20, 30],
            "color": "#6f8b79",
        }],
    )
    success, encoded = app_module.cv2.imencode(".jpg", app_module.np.zeros((32, 32, 3), dtype="uint8"))
    assert success

    response = client.post(
        "/camera/predict",
        data={"image": (io.BytesIO(encoded.tobytes()), "camera.jpg")},
        content_type="multipart/form-data",
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["detection_status"] == "uncertain"
    assert payload["low_confidence"] is True
    assert payload["top_class"] == "UNKNOWN OBJECT"
    assert payload["message"].startswith("Dự đoán chưa đủ tin cậy")


def test_camera_api_distinguishes_no_detection_from_uncertain(client, monkeypatch):
    monkeypatch.setattr(app_module, "predict_once", lambda *_args: SimpleNamespace(boxes=None))
    success, encoded = app_module.cv2.imencode(".jpg", app_module.np.zeros((32, 32, 3), dtype="uint8"))
    assert success

    response = client.post(
        "/camera/predict",
        data={"image": (io.BytesIO(encoded.tobytes()), "camera.jpg")},
        content_type="multipart/form-data",
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["detection_status"] == "not_detected"
    assert payload["object_count"] == 0
    assert payload["low_confidence"] is False


def test_chat_api_returns_relevant_reply(client):
    response = client.post(
        "/api/chat",
        json={
            "message": "Chai nhựa có thể làm gì?",
            "context": {"last_detection": "PLASTIC", "confidence": 0.94, "object_count": 1},
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "nhựa" in payload["reply"].lower()
    assert "nhựa nhựa" not in payload["reply"].lower()


def test_chat_api_resolves_first_project_follow_up(client, monkeypatch):
    monkeypatch.setattr(app_module, "generate_llm_reply", lambda *_args: None)
    first = client.post("/api/chat", json={"message": "Chai nhựa có thể làm gì?"})
    follow_up = client.post("/api/chat", json={"message": "Cái đầu tiên làm thế nào?"})

    assert first.get_json()["mode"] == "knowledge_fallback"
    assert "Chậu cây mini" in follow_up.get_json()["reply"]
    assert "/projects/plastic-planter" in follow_up.get_json()["reply"]
    assert "thành phẩm là một chậu cây mini" in follow_up.get_json()["reply"].lower()


def test_llm_request_includes_history_and_confident_detection_context(monkeypatch):
    settings = {
        "CHAT_PROVIDER": "openai",
        "OPENAI_API_KEY": "test_key",
        "OPENAI_MODEL": "gpt-test",
    }
    monkeypatch.setattr(chat_service, "get_setting", lambda name, default="": settings.get(name, default))
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        body = {"choices": [{"message": {"content": "Here is the first project."}}]}
        return io.BytesIO(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(chat_service.urllib_request, "urlopen", fake_urlopen)
    reply = chat_service.generate_llm_reply(
        "How do I make the first one?",
        {"last_detection": "PLASTIC", "confidence": 0.94, "object_count": 1},
        [{"role": "user", "content": "What can I make from a plastic bottle?"}],
    )

    request_body = json.loads(captured["request"].data)
    assert reply == "Here is the first project."
    assert request_body["messages"][-2]["content"] == "What can I make from a plastic bottle?"
    assert "Nhựa" in request_body["messages"][0]["content"]
    assert captured["request"].get_header("Authorization") == "Bearer " + "test" + "_key"
    assert captured["timeout"] <= 20


def test_gemini_request_includes_history_and_uses_server_side_key(monkeypatch):
    settings = {
        "CHAT_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test_key",
        "GEMINI_MODEL": "gemini-test",
    }
    monkeypatch.setattr(chat_service, "get_setting", lambda name, default="": settings.get(name, default))
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        payload = {"candidates": [{"content": {"parts": [{"text": "A general answer."}]}}]}
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(chat_service.urllib_request, "urlopen", fake_urlopen)
    reply = chat_service.generate_llm_reply(
        "Explain recursion",
        conversation_history=[{"role": "user", "content": "What is a function?"}],
    )

    body = json.loads(captured["request"].data)
    assert reply == "A general answer."
    assert captured["request"].full_url.endswith("/models/gemini-test:generateContent")
    assert captured["request"].get_header("X-goog-api-key") == "test_key"
    assert body["contents"][0]["parts"][0]["text"] == "What is a function?"
    assert body["contents"][-1]["parts"][0]["text"] == "Explain recursion"
    assert captured["timeout"] <= 20


def test_generic_chat_without_api_key_explains_backend_configuration(client, monkeypatch):
    monkeypatch.setattr(chat_service, "get_setting", lambda name, default="": default)

    response = client.post("/api/chat", json={"message": "How do I reverse a linked list in Python?"})
    payload = response.get_json()

    assert response.status_code == 503
    assert payload["success"] is False
    assert payload["setup_required"] is True
    assert "OPENAI_API_KEY" in payload["reply"]
    assert "GEMINI_API_KEY" in payload["reply"]
    assert "your_openai_api_key" in payload["reply"]


def test_chat_rate_limit_returns_429_after_session_limit(client, monkeypatch):
    monkeypatch.setattr(app_module, "MAX_CHAT_REQUESTS_PER_MINUTE", 20)
    monkeypatch.setattr(app_module, "generate_llm_reply", lambda *_args: None)

    responses = [
        client.post("/api/chat", json={"message": f"Câu hỏi số {index}"})
        for index in range(20)
    ]
    twenty_first = client.post("/api/chat", json={"message": "Câu hỏi vượt giới hạn"})

    assert all(response.status_code == 200 for response in responses)
    assert twenty_first.status_code == 429
    assert twenty_first.headers["Retry-After"] == "60"
