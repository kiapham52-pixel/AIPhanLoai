const cameraVideo = document.getElementById("cameraVideo");
const cameraCanvas = document.getElementById("cameraCanvas");
const cameraStage = document.getElementById("cameraStage");
const cameraIdle = document.getElementById("cameraIdle");
const cameraError = document.getElementById("cameraError");
const cameraOverlay = document.getElementById("cameraOverlay");
const overlayClass = document.getElementById("overlayClass");
const overlayConfidence = document.getElementById("overlayConfidence");
const statusText = document.getElementById("statusText");
const countText = document.getElementById("countText");
const fpsText = document.getElementById("fpsText");
const startCameraBtn = document.getElementById("startCameraBtn");
const stopCameraBtn = document.getElementById("stopCameraBtn");
const objectList = document.getElementById("objectList");
const readingTitle = document.getElementById("readingTitle");
const readingMessage = document.getElementById("readingMessage");
const cameraProjects = document.getElementById("cameraProjects");
const cameraProjectList = document.getElementById("cameraProjectList");
const allProjectsLink = document.getElementById("allProjectsLink");
const cameraConfidence = document.getElementById("cameraConfidence");
const cameraImageSize = document.getElementById("cameraImageSize");
const cameraInterval = document.getElementById("cameraInterval");
const cameraConfidenceDisplay = document.getElementById("cameraConfidenceDisplay");
const cameraImageSizeDisplay = document.getElementById("cameraImageSizeDisplay");
const cameraIntervalDisplay = document.getElementById("cameraIntervalDisplay");

const CLASS_LABELS = {
    PLASTIC: "Nhựa",
    PAPER: "Giấy",
    GLASS: "Thủy tinh",
    METAL: "Kim loại",
    CARDBOARD: "Bìa carton",
    BIODEGRADABLE: "Rác hữu cơ",
    "UNKNOWN OBJECT": "Chưa chắc chắn",
};

let stream = null;
let cameraRunning = false;
let cameraStarting = false;
let isProcessing = false;
let fpsStart = performance.now();
let fpsFrames = 0;
let detectionTimer = null;
let requestController = null;
let cameraSession = 0;
let projectRequestMaterial = "";
const workCanvas = document.createElement("canvas");
const workContext = workCanvas.getContext("2d");

const formatClassLabel = (value) => CLASS_LABELS[(value || "").toUpperCase()] || value || "Chưa xác định";

const setStatus = (text, state = "scanning") => {
    statusText.textContent = text;
    cameraStage.dataset.state = state;
};

const updateCameraSettings = () => {
    cameraConfidenceDisplay.textContent = Number(cameraConfidence.value).toFixed(2);
    cameraImageSizeDisplay.textContent = cameraImageSize.value;
    cameraIntervalDisplay.textContent = `${cameraInterval.value}ms`;
};

const resetCanvas = () => {
    const ctx = cameraCanvas.getContext("2d");
    ctx.clearRect(0, 0, cameraCanvas.width, cameraCanvas.height);
};

const renderObjectList = (objects = []) => {
    objectList.replaceChildren();
    if (!objects.length) {
        const empty = document.createElement("p");
        empty.className = "camera-empty-result";
        empty.textContent = "Chưa có kết quả nhận diện.";
        objectList.appendChild(empty);
        return;
    }

    objects.forEach((item, index) => {
        const row = document.createElement("button");
        row.type = "button";
        const confidenceValue = Number(item.confidence) || 0;
        const uncertain = confidenceValue < 0.5;
        row.className = `mini-object-item${index === 0 ? " is-selected" : ""}${uncertain ? " is-uncertain" : ""}`;
        row.dataset.material = item.class;
        row.dataset.confidence = String(confidenceValue * 100);
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.style.backgroundColor = item.color;
        const label = document.createElement("span");
        label.className = "item-name";
        label.textContent = uncertain
            ? `Chưa chắc · ${formatClassLabel(item.display_class || item.class)}`
            : `Dự đoán · ${formatClassLabel(item.display_class || item.class)}`;
        const confidence = document.createElement("strong");
        confidence.textContent = `${Math.round(confidenceValue * 100)}%`;
        row.append(dot, label, confidence);
        objectList.appendChild(row);
    });
};

const renderProjects = async (material, confidence) => {
    if (!material || confidence < 50 || material === "UNKNOWN OBJECT") {
        cameraProjects.hidden = true;
        projectRequestMaterial = "";
        return;
    }
    if (projectRequestMaterial === material) return;
    projectRequestMaterial = material;
    try {
        const response = await fetch(`/api/projects?material=${encodeURIComponent(material)}`);
        const payload = await response.json();
        if (!response.ok || !payload.success || projectRequestMaterial !== material) return;
        cameraProjectList.replaceChildren();
        payload.projects.slice(0, 2).forEach((project) => {
            const link = document.createElement("a");
            link.className = "camera-project-link";
            link.href = `/projects/${encodeURIComponent(project.id)}`;
            const image = document.createElement("img");
            image.src = project.image;
            image.alt = "";
            image.loading = "lazy";
            const text = document.createElement("span");
            text.append(document.createTextNode(project.title));
            const meta = document.createElement("small");
            meta.textContent = `${project.difficulty} · ${project.time}`;
            text.appendChild(meta);
            link.append(image, text);
            cameraProjectList.appendChild(link);
        });
        allProjectsLink.href = `/explore?material=${encodeURIComponent(material)}`;
        cameraProjects.hidden = payload.projects.length === 0;
    } catch {
        cameraProjects.hidden = true;
    }
};

const drawDetectionOverlay = (objects = []) => {
    const ctx = cameraCanvas.getContext("2d");
    const videoWidth = cameraVideo.videoWidth || 640;
    const videoHeight = cameraVideo.videoHeight || 480;
    cameraCanvas.width = videoWidth;
    cameraCanvas.height = videoHeight;
    ctx.clearRect(0, 0, videoWidth, videoHeight);
    if (!objects.length) return;

    const frameWidth = workCanvas.width;
    const frameHeight = workCanvas.height;
    const scaleX = videoWidth / frameWidth;
    const scaleY = videoHeight / frameHeight;

    objects.forEach((item) => {
        const [x1, y1, x2, y2] = item.box;
        const sx1 = x1 * scaleX;
        const sy1 = y1 * scaleY;
        const sx2 = (x2 - x1) * scaleX;
        const sy2 = (y2 - y1) * scaleY;
        const confidence = Number(item.confidence) || 0;
        const label = `${confidence < 0.5 ? "Chưa chắc · " : "Dự đoán · "}${formatClassLabel(item.display_class || item.class)} ${Math.round(confidence * 100)}%`;
        ctx.strokeStyle = item.color;
        ctx.lineWidth = 3;
        ctx.strokeRect(sx1, sy1, sx2, sy2);
        ctx.font = "14px Arial, sans-serif";
        const labelWidth = Math.min(videoWidth, ctx.measureText(label).width + 16);
        const labelX = Math.min(Math.max(0, sx1), videoWidth - labelWidth);
        const labelTop = sy1 >= 30 ? sy1 - 27 : Math.min(videoHeight - 25, sy1 + sy2);
        ctx.fillStyle = item.color;
        ctx.fillRect(labelX, labelTop, labelWidth, 25);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(label, labelX + 8, labelTop + 17);
    });
};

const updateFps = () => {
    fpsFrames += 1;
    const elapsed = performance.now() - fpsStart;
    if (elapsed >= 1000) {
        const fps = (fpsFrames * 1000) / elapsed;
        fpsText.textContent = fps.toFixed(1);
        fpsStart = performance.now();
        fpsFrames = 0;
    }
};

const cameraErrorMessage = (error) => {
    if (error.name === "NotAllowedError" || error.name === "SecurityError") return "Bạn chưa cấp quyền camera";
    if (error.name === "NotFoundError" || error.name === "OverconstrainedError") return "Không tìm thấy camera";
    if (error.name === "NotReadableError" || error.name === "TrackStartError") return "Camera đang được dùng bởi ứng dụng khác";
    if (error.name === "TypeError") return "Trình duyệt không hỗ trợ camera";
    return "Không thể truy cập camera";
};

async function startCamera() {
    if (cameraRunning || cameraStarting) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setStatus("Trình duyệt không hỗ trợ camera", "error");
        return;
    }
    if (!window.isSecureContext) {
        setStatus("Camera cần chạy trên localhost hoặc HTTPS", "error");
        return;
    }

    cameraStarting = true;
    startCameraBtn.disabled = true;
    stopCameraBtn.disabled = false;
    cameraError.hidden = true;
    setStatus("Đang mở camera...", "opening");
    const session = ++cameraSession;
    let cameraStream = null;

    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: { ideal: "environment" }, frameRate: { ideal: 30, max: 30 } },
            audio: false,
        });

        if (session !== cameraSession) {
            cameraStream.getTracks().forEach((track) => track.stop());
            return;
        }

        stream = cameraStream;
        cameraVideo.srcObject = stream;
        await cameraVideo.play();

        if (session !== cameraSession) {
            cameraStream.getTracks().forEach((track) => track.stop());
            if (cameraVideo.srcObject === cameraStream) cameraVideo.srcObject = null;
            return;
        }

        cameraRunning = true;
        cameraStage.classList.add("is-live");
        setStatus("Đang quét...", "scanning");
        fpsStart = performance.now();
        fpsFrames = 0;
        scheduleNextCapture(0);
    } catch (error) {
        if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
        if (session === cameraSession) {
            if (stream === cameraStream) stream = null;
            cameraVideo.srcObject = null;
            cameraStage.classList.remove("is-live");
            stopCameraBtn.disabled = true;
            cameraError.hidden = false;
            cameraError.textContent = cameraErrorMessage(error);
            setStatus("Không thể mở camera", "error");
        }
    } finally {
        if (session === cameraSession) {
            cameraStarting = false;
            startCameraBtn.disabled = false;
        }
    }
}

function stopCamera() {
    cameraSession += 1;
    cameraRunning = false;
    cameraStarting = false;
    startCameraBtn.disabled = false;
    stopCameraBtn.disabled = true;

    if (detectionTimer !== null) {
        clearTimeout(detectionTimer);
        detectionTimer = null;
    }
    if (requestController) requestController.abort();
    if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        stream = null;
    }

    if (cameraVideo) cameraVideo.srcObject = null;
    cameraStage?.classList.remove("is-live");
    resetCanvas();
    cameraOverlay.classList.add("hidden");
    renderObjectList([]);
    cameraProjects.hidden = true;
    readingTitle.textContent = "Khung hình\nđang chờ bạn.";
    readingTitle.classList.remove("is-uncertain");
    readingMessage.textContent = "Khi nhận diện được vật thể, thông tin và hướng dẫn phù hợp sẽ xuất hiện ở đây.";
    countText.textContent = "0";
    fpsText.textContent = "0";
    if (cameraError) cameraError.hidden = true;
    setStatus("Camera đang tắt", "off");
}

function toBlobFromCanvas(canvas) {
    return new Promise((resolve) => {
        canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.65);
    });
}

async function captureAndSend() {
    if (!cameraRunning || !cameraVideo || cameraVideo.readyState < 2) return;
    if (isProcessing) {
        scheduleNextCapture(120);
        return;
    }

    isProcessing = true;
    const session = cameraSession;
    const interval = Math.max(250, Number(cameraInterval.value) || 400);
    const targetWidth = Number(cameraImageSize.value) || 320;
    const controller = new AbortController();
    requestController = controller;
    setStatus("Đang phân tích...", "analyzing");
    workCanvas.width = targetWidth;
    workCanvas.height = Math.round((cameraVideo.videoHeight / cameraVideo.videoWidth) * targetWidth);

    try {
        workContext.drawImage(cameraVideo, 0, 0, targetWidth, workCanvas.height);
        const blob = await toBlobFromCanvas(workCanvas);
        if (!blob || !cameraRunning || session !== cameraSession) return;

        const formData = new FormData();
        formData.append("image", blob, "camera_frame.jpg");
        formData.append("confidence", cameraConfidence.value);
        formData.append("image_size", String(targetWidth));

        const response = await fetch("/camera/predict", { method: "POST", body: formData, signal: controller.signal });
        if (!cameraRunning || session !== cameraSession) return;

        if (!response.ok) {
            if (response.status === 429) {
                setStatus("AI đang bận, vui lòng chờ trong giây lát", "error");
                return;
            }
            throw new Error(`Camera API returned ${response.status}`);
        }

        const payload = await response.json();
        if (!cameraRunning || session !== cameraSession) return;

        if (!payload.success) {
            setStatus(payload.message || "Đã xảy ra lỗi khi nhận diện", "error");
            return;
        }

        if (!payload.objects || !payload.objects.length) {
            cameraOverlay.classList.add("hidden");
            renderObjectList([]);
            countText.textContent = "Không nhận diện được vật thể";
            resetCanvas();
            cameraProjects.hidden = true;
            readingTitle.textContent = "Không nhận diện được.";
            readingTitle.classList.remove("is-uncertain");
            readingMessage.textContent = "Chưa tìm thấy vật thể thuộc 6 lớp hỗ trợ. Hãy căn giữa vật thể, chọn nền đơn giản và đủ sáng.";
            window.WASTE_CHAT_CONTEXT = {};
            setStatus("Không nhận diện được", "not-detected");
        } else {
            const objects = payload.objects.map((item) => ({
                ...item,
                confidence: Number(item.confidence) || 0,
                color: item.color || "#4a90e2",
            }));

            countText.textContent = `${payload.object_count ?? objects.length} đối tượng được phát hiện`;
            renderObjectList(objects);
            drawDetectionOverlay(objects);
            cameraOverlay.classList.remove("hidden");
            const best = objects[0];
            const confidencePct = Number(payload.best_confidence) || 0;
            const uncertain = Boolean(payload.low_confidence) || confidencePct < 50;
            const bestLabel = uncertain ? "Chưa đủ chắc chắn" : formatClassLabel(best.display_class || best.class);
            readingTitle.classList.toggle("is-uncertain", uncertain);
            overlayClass.textContent = bestLabel;
            overlayConfidence.textContent = `Dự đoán ${Math.round(confidencePct)}%`;
            readingTitle.textContent = bestLabel;
            readingMessage.textContent = uncertain
                ? "AI chưa đủ chắc chắn. Vật thể có thể nằm ngoài phạm vi dữ liệu mà hệ thống được huấn luyện. Hãy kiểm tra lại trước khi xử lý."
                : confidencePct >= 80
                    ? "AI khá chắc chắn về nhận diện này. Bạn có thể khám phá cách tái sử dụng phù hợp."
                    : "AI nhận diện với độ tin cậy trung bình. Hãy kiểm tra vật liệu trước khi xử lý.";
            window.WASTE_CHAT_CONTEXT = {
                last_detection: uncertain ? "" : best.class,
                display_name: uncertain ? "" : formatClassLabel(best.display_class || best.class),
                confidence: confidencePct / 100,
                object_count: objects.length,
            };
            await renderProjects(uncertain ? "" : best.class, confidencePct);
            setStatus(
                uncertain ? "Kết quả chưa đủ tin cậy" : "Đã nhận diện",
                uncertain ? "uncertain" : "recognized",
            );
        }

        updateFps();
    } catch (error) {
        if (error.name !== "AbortError") {
            if (cameraRunning && session === cameraSession) {
                setStatus("Đang gặp sự cố", "error");
                cameraError.hidden = false;
                cameraError.textContent = "Có vẻ hệ thống đang gặp chút trục trặc. Hãy thử lại trong giây lát.";
            }
        }
    } finally {
        isProcessing = false;
        if (requestController === controller) requestController = null;
        if (cameraRunning && session === cameraSession) scheduleNextCapture(interval);
    }
}

function scheduleNextCapture(delay) {
    if (!cameraRunning || detectionTimer !== null) return;
    detectionTimer = window.setTimeout(() => {
        detectionTimer = null;
        captureAndSend();
    }, delay);
}

objectList.addEventListener("click", async (event) => {
    const row = event.target.closest("[data-material]");
    if (!row) return;
    objectList.querySelectorAll(".mini-object-item").forEach((item) => item.classList.toggle("is-selected", item === row));
    const material = row.dataset.material;
    const confidence = Number(row.dataset.confidence || 0);
    const known = confidence >= 50 && material !== "UNKNOWN OBJECT";
    window.WASTE_CHAT_CONTEXT = {
        last_detection: known ? material : "",
        display_name: known ? formatClassLabel(material) : "",
        confidence: confidence / 100,
        object_count: objectList.querySelectorAll("[data-material]").length,
    };
    readingTitle.textContent = known ? formatClassLabel(material) : "Chưa đủ chắc chắn";
    readingMessage.textContent = !known
        ? "AI chưa đủ chắc chắn. Vật thể có thể nằm ngoài phạm vi dữ liệu mà hệ thống được huấn luyện."
        : confidence >= 80 ? "AI khá chắc chắn về nhận diện này." : "AI nhận diện với độ tin cậy trung bình. Hãy kiểm tra vật liệu trước khi xử lý.";
    await renderProjects(known ? material : "", confidence);
});

cameraConfidence.addEventListener("input", updateCameraSettings);
cameraImageSize.addEventListener("input", updateCameraSettings);
cameraInterval.addEventListener("input", updateCameraSettings);
startCameraBtn.addEventListener("click", startCamera);
stopCameraBtn.addEventListener("click", stopCamera);
updateCameraSettings();
