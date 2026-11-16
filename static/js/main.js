const header = document.getElementById("siteHeader");
const navToggle = document.querySelector("[data-nav-toggle]");
const primaryNav = document.getElementById("primaryNav");
if (window.location.pathname === "/predict") {
    document.getElementById("scan-panel")?.scrollIntoView({ block: "start" });
}
const setHeaderState = () => header?.classList.toggle("is-scrolled", window.scrollY > 12);
window.addEventListener("scroll", setHeaderState, { passive: true });
setHeaderState();

navToggle?.addEventListener("click", () => {
    const isOpen = primaryNav?.classList.toggle("is-open") || false;
    navToggle.setAttribute("aria-expanded", String(isOpen));
    navToggle.setAttribute("aria-label", isOpen ? "Đóng menu" : "Mở menu");
});

const fileInput = document.getElementById("imageInput");
const dropZone = document.getElementById("dropZone");
const previewImage = document.getElementById("previewImage");
const previewEmpty = document.getElementById("previewEmpty");
const previewLoading = document.getElementById("previewLoading");
const selectedFile = document.getElementById("selectedFile");
const uploadForm = document.getElementById("uploadForm");
const scanSubmit = document.getElementById("scanSubmit");
let previewUrl = null;

const acceptImage = (file) => {
    if (!file) return;
    const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"];
    if (!allowedTypes.includes(file.type)) {
        if (selectedFile) selectedFile.textContent = "Định dạng này chưa được hỗ trợ.";
        if (scanSubmit) scanSubmit.disabled = true;
        return;
    }
    if (file.size > 16 * 1024 * 1024) {
        if (selectedFile) selectedFile.textContent = "Ảnh vượt quá giới hạn 16 MB.";
        if (scanSubmit) scanSubmit.disabled = true;
        return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    if (previewImage) {
        previewImage.src = previewUrl;
        previewImage.classList.remove("is-empty");
        previewImage.alt = `Ảnh xem trước: ${file.name}`;
    }
    if (previewEmpty) previewEmpty.hidden = true;
    if (selectedFile) selectedFile.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    if (scanSubmit) scanSubmit.disabled = false;
};

dropZone?.addEventListener("click", () => fileInput?.click());
fileInput?.addEventListener("change", () => acceptImage(fileInput.files?.[0]));
if (dropZone) {
    ["dragenter", "dragover"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add("dragover");
    }));
    ["dragleave", "drop"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.remove("dragover");
    }));
    dropZone.addEventListener("drop", (event) => {
        const file = event.dataTransfer?.files?.[0];
        if (!file || !fileInput) return;
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
        acceptImage(file);
    });
}
uploadForm?.addEventListener("submit", (event) => {
    if (!fileInput?.files?.length) {
        event.preventDefault();
        return;
    }
    if (previewLoading) previewLoading.hidden = false;
    if (scanSubmit) {
        scanSubmit.disabled = true;
        scanSubmit.textContent = "Đang phân tích...";
    }
});

const filters = ["projectSearch", "materialFilter", "difficultyFilter", "timeFilter", "categoryFilter"]
    .map((id) => document.getElementById(id));
const cards = [...document.querySelectorAll("[data-project-card]")];
const projectCount = document.getElementById("projectCount");
const filterEmpty = document.getElementById("filterEmpty");
const filterProjects = () => {
    if (!cards.length) return;
    const [searchInput, materialInput, difficultyInput, timeInput, categoryInput] = filters;
    const query = searchInput?.value.trim().toLocaleLowerCase("vi") || "";
    const queryTerms = query.split(/\s+/).filter(Boolean);
    const material = materialInput?.value || "";
    const difficulty = difficultyInput?.value || "";
    const category = categoryInput?.value || "";
    const timeRange = timeInput?.value || "";
    let visible = 0;
    cards.forEach((card) => {
        const values = (card.dataset.minutes || "").match(/\d+/g)?.map(Number) || [];
        const estimated = values.length ? Math.max(...values) : 0;
        const timeMatches = !timeRange
            || (timeRange === "15" && estimated <= 15)
            || (timeRange === "30" && estimated > 15 && estimated <= 30)
            || (timeRange === "60" && estimated > 30 && estimated <= 60)
            || (timeRange === "61" && estimated > 60);
        const matches = (!query || queryTerms.every((term) => card.dataset.search?.includes(term)))
            && (!material || card.dataset.material === material)
            && (!difficulty || card.dataset.difficulty === difficulty)
            && (!category || card.dataset.category === category)
            && timeMatches;
        card.hidden = !matches;
        if (matches) visible += 1;
    });
    if (projectCount) projectCount.textContent = `${visible} hướng dẫn`;
    if (filterEmpty) filterEmpty.hidden = visible > 0;
};
filters.forEach((filter) => filter?.addEventListener(filter?.type === "search" ? "input" : "change", filterProjects));
filterProjects();

const classLabels = {
    PLASTIC: "Nhựa", PAPER: "Giấy", GLASS: "Thủy tinh", METAL: "Kim loại",
    CARDBOARD: "Bìa carton", BIODEGRADABLE: "Rác hữu cơ", "UNKNOWN OBJECT": "Chưa chắc chắn",
};
const chatToggle = document.getElementById("assistantToggle");
const chatPanel = document.getElementById("assistantPanel");
const chatClose = document.getElementById("assistantClose");
const chatForm = document.getElementById("assistantForm");
const chatInput = document.getElementById("assistantInput");
const chatMessages = document.getElementById("assistantMessages");
const getSession = () => {
    if (window.ECO_SESSION_ID) return window.ECO_SESSION_ID;
    try {
        let id = sessionStorage.getItem("ecoVisionSession");
        if (!id) {
            id = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
            sessionStorage.setItem("ecoVisionSession", id);
        }
        return id;
    } catch {
        return "browser-session";
    }
};
const chatSession = getSession();
let conversation = [];
try { conversation = JSON.parse(sessionStorage.getItem(`ecoVisionChat:${chatSession}`) || "[]"); } catch { conversation = []; }

document.querySelectorAll("[data-favorite-button]").forEach(async (button) => {
    const projectId = button.dataset.projectId;
    if (!projectId) return;
    try {
        const response = await fetch("/api/favorites");
        const payload = await response.json();
        const isSaved = response.ok && payload.projects?.some((project) => project.id === projectId);
        button.setAttribute("aria-pressed", String(Boolean(isSaved)));
        button.innerHTML = isSaved ? "Đã lưu <span aria-hidden=\"true\">✓</span>" : "Lưu ý tưởng <span aria-hidden=\"true\">＋</span>";
    } catch { /* Saving remains available even if the initial state cannot load. */ }
    button.addEventListener("click", async () => {
        const shouldSave = button.getAttribute("aria-pressed") !== "true";
        button.disabled = true;
        try {
            const response = await fetch("/api/favorites", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ project_id: projectId, action: shouldSave ? "save" : "remove" }),
            });
            const payload = await response.json();
            if (!response.ok || !payload.success) throw new Error("Could not save project");
            button.setAttribute("aria-pressed", String(shouldSave));
            button.innerHTML = shouldSave ? "Đã lưu <span aria-hidden=\"true\">✓</span>" : "Lưu ý tưởng <span aria-hidden=\"true\">＋</span>";
            if (!shouldSave && window.location.pathname === "/favorites") {
                button.closest(".saved-project-entry")?.remove();
            }
        } catch {
            button.textContent = "Chưa thể lưu, thử lại";
        } finally {
            button.disabled = false;
        }
    });
});

const openChat = () => {
    chatPanel?.classList.add("is-open");
    chatPanel?.setAttribute("aria-hidden", "false");
    chatToggle?.setAttribute("aria-expanded", "true");
    chatInput?.focus();
};
const closeChat = () => {
    chatPanel?.classList.remove("is-open");
    chatPanel?.setAttribute("aria-hidden", "true");
    chatToggle?.setAttribute("aria-expanded", "false");
    chatToggle?.focus();
};
chatToggle?.addEventListener("click", () => chatPanel?.classList.contains("is-open") ? closeChat() : openChat());
chatClose?.addEventListener("click", closeChat);
document.querySelectorAll("[data-assistant-open]").forEach((button) => button.addEventListener("click", openChat));
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && chatPanel?.classList.contains("is-open")) closeChat();
});

const appendChatMessage = (role, text, persist = true) => {
    if (!chatMessages) return;
    const row = document.createElement("div");
    row.className = `message ${role === "user" ? "user-message" : "ai-message"}`;
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    row.appendChild(paragraph);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    if (persist) {
        conversation.push({ role, content: text });
        conversation = conversation.slice(-12);
        try { sessionStorage.setItem(`ecoVisionChat:${chatSession}`, JSON.stringify(conversation)); } catch { /* Storage is optional. */ }
    }
};
conversation.forEach((item) => appendChatMessage(item.role, item.content, false));

chatForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = chatInput?.value.trim();
    if (!message || !chatInput || !chatMessages) return;
    appendChatMessage("user", message);
    chatInput.value = "";
    const submitButton = chatForm.querySelector("button[type='submit']");
    if (submitButton) submitButton.disabled = true;
    const typing = document.createElement("div");
    typing.className = "message ai-message";
    typing.setAttribute("role", "status");
    const typingText = document.createElement("p");
    typingText.textContent = "Đang soạn câu trả lời...";
    typing.appendChild(typingText);
    chatMessages.appendChild(typing);
    try {
        const context = window.WASTE_CHAT_CONTEXT || {};
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                conversation_history: conversation.slice(0, -1),
                context: {
                    ...context,
                    last_detection: context.last_detection || context.material || "",
                    display_name: context.display_name || classLabels[context.last_detection] || "",
                },
            }),
        });
        const payload = await response.json();
        typing.remove();
        appendChatMessage("assistant", response.ok && payload.success
            ? payload.reply
            : (payload.reply || "Trợ lý AI hiện chưa thể trả lời. Bạn có thể thử lại sau."));
    } catch {
        typing.remove();
        appendChatMessage("assistant", "Trợ lý AI hiện chưa thể trả lời. Bạn có thể thử lại sau.");
    } finally {
        if (submitButton) submitButton.disabled = false;
        chatInput.focus();
    }
});

const selectedObjects = document.getElementById("detectedObjects");
selectedObjects?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-material]");
    if (!button) return;
    selectedObjects.querySelectorAll(".detected-object").forEach((item) => item.classList.toggle("is-selected", item === button));
    const material = button.dataset.material;
    const confidence = Number(button.dataset.confidence || 0);
    window.WASTE_CHAT_CONTEXT = {
        last_detection: material,
        display_name: classLabels[material] || material,
        confidence: confidence / 100,
        object_count: selectedObjects.querySelectorAll(".detected-object").length,
    };
    const analysisTitle = document.querySelector(".analysis-title");
    const confidenceValue = document.querySelector(".confidence-line strong");
    const confidenceExplanation = document.querySelector(".confidence-explanation");
    if (analysisTitle) analysisTitle.textContent = classLabels[material] || material;
    if (confidenceValue) confidenceValue.textContent = `${Math.round(confidence)}%`;
    if (confidenceExplanation) {
        confidenceExplanation.textContent = confidence >= 80
            ? "AI khá chắc chắn về nhận diện này."
            : confidence >= 50 ? "AI nhận diện với độ tin cậy trung bình. Hãy kiểm tra vật liệu trước khi xử lý."
                : "AI chưa đủ chắc chắn. Vật thể có thể nằm ngoài phạm vi dữ liệu mà hệ thống được huấn luyện.";
    }
    if (confidence < 50) return;
    try {
        const response = await fetch(`/api/projects?material=${encodeURIComponent(material)}`);
        const payload = await response.json();
        const gallery = document.querySelector(".project-gallery-featured");
        if (!response.ok || !payload.success || !gallery) return;
        gallery.replaceChildren();
        payload.projects.slice(0, 3).forEach((project, index) => {
            const link = document.createElement("a");
            link.className = `project-tile${index === 0 ? " project-tile-featured" : ""}`;
            link.href = `/projects/${encodeURIComponent(project.id)}`;
            const imageWrap = document.createElement("div");
            imageWrap.className = "project-image";
            const image = document.createElement("img");
            image.src = project.image;
            image.alt = project.title;
            image.loading = "lazy";
            imageWrap.appendChild(image);
            const meta = document.createElement("div");
            meta.className = "project-meta";
            meta.textContent = `${project.display_name} · ${project.difficulty} · ${project.time}`;
            const title = document.createElement("h4");
            title.textContent = project.title;
            const description = document.createElement("p");
            description.textContent = project.description;
            link.append(imageWrap, meta, title, description);
            gallery.appendChild(link);
        });
        const recommendationTitle = document.getElementById("recommendationTitle");
        if (recommendationTitle) recommendationTitle.textContent = `Bạn có thể biến ${classLabels[material] || "vật liệu này"} thành...`;
    } catch { /* The server-rendered recommendations remain available. */ }
});
