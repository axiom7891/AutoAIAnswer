(function () {
  const sessionId = window.SESSION_ID && window.SESSION_ID !== "__SESSION_ID__"
    ? window.SESSION_ID
    : new URLSearchParams(location.search).get("session_id");
  const statusEl = document.getElementById("status");
  const selectionEl = document.getElementById("selection-status");
  const selectionMessageEl = document.getElementById("selection-message");
  const fullscreenButton = document.getElementById("fullscreen-button");
  const chatCaptureButton = document.getElementById("chat-capture-button");
  const questionInput = document.getElementById("question-input");
  const askButton = document.getElementById("ask-button");
  const clearChatButton = document.getElementById("clear-chat-button");
  const chatList = document.getElementById("chat-list");
  const previewList = document.getElementById("preview-list");
  const previewCount = document.getElementById("preview-count");
  const saveAlbumButton = document.getElementById("save-album-button");
  const selectAllAlbumButton = document.getElementById("select-all-album");
  const albumSheet = document.getElementById("album-sheet");
  const albumSheetImages = document.getElementById("album-sheet-images");
  const albumSheetClose = document.getElementById("album-sheet-close");
  const outputEl = document.getElementById("output");
  const outputPrev = document.getElementById("output-prev");
  const outputNext = document.getElementById("output-next");
  const outputPage = document.getElementById("output-page");
  const outputAutoEnabled = document.getElementById("output-auto-enabled");
  const outputAutoSeconds = document.getElementById("output-auto-seconds");
  const outputExpand = document.getElementById("output-expand");
  const chunkSizeInput = document.getElementById("chunk-size");
  const chunkCopyButton = document.getElementById("chunk-copy-button");
  const chunkResetButton = document.getElementById("chunk-reset");
  const chunkProgress = document.getElementById("chunk-progress");
  const chunkSizeKey = "answerChunk:size";
  let chunkIndex = 0;
  let chunkSourceText = "";
  const codeWrapToggle = document.getElementById("code-wrap");
  const codeFontSelect = document.getElementById("code-font");
  const codePanToggle = document.getElementById("code-autopan");
  const CODE_VIEW_KEY = "codeView:settings";
  let codeViewSettings = { wrap: true, font: "13", pan: true };
  let panTimer = null;
  let panPauseUntil = 0;
  let panDirection = 1;
  let panXDirection = 1;
  const modelHint = document.getElementById("model-hint");
  const modelRoute = document.getElementById("model-route");
  const cursorKey = `lastEventId:${sessionId || "missing"}`;
  const modelTierKey = `modelTier:${sessionId || "missing"}`;
  const autoPageKey = `outputAuto:${sessionId || "missing"}`;
  let autoPageConfig = {};
  try {
    autoPageConfig = JSON.parse(localStorage.getItem(autoPageKey) || "{}") || {};
  } catch (_) {
    autoPageConfig = {};
  }
  if (outputAutoEnabled) {
    outputAutoEnabled.checked = autoPageConfig.enabled === true;
  }
  if (outputAutoSeconds) {
    outputAutoSeconds.value = String(autoPageConfig.seconds || 10);
  }
  let lastEventId = Number(localStorage.getItem(cursorKey) || 0);
  let reconnectMs = 1000;
  let buffer = "";
  let socket = null;
  let activeChatRequestId = null;
  let activeAssistantBubble = null;
  let activeAssistantText = "";
  let activeDirectRequestId = null;
  let latestChatRequestId = null;
  let latestDirectRequestId = null;
  let renderScheduled = false;
  let albumItems = [];
  let nextAlbumId = 1;
  let requestCounter = 0;
  let autoPageTimer = null;
  const renderedChatRequests = new Set();
  const routeAliases = {
    "openrouter-qwen-32b": "openrouter-qwen-27b",
    "openrouter-qwen-8b": "openrouter-qwen-flash",
    "openrouter-deepseek-flash": "openrouter-qwen-plus",
    "deepseek/deepseek-v4.1-flash": "openrouter-qwen-plus",
    good: "openrouter-qwen-235b",
    high: "openrouter-qwen-235b",
    best: "openrouter-qwen-235b",
    "好": "openrouter-qwen-235b",
    medium: "openrouter-qwen-27b",
    mid: "openrouter-qwen-27b",
    "中等": "openrouter-qwen-27b",
    simple: "deepseek-flash",
    low: "deepseek-flash",
    easy: "deepseek-flash",
    "简单": "deepseek-flash",
    doubao: "doubao-seed-2-1-turbo",
    "豆包": "doubao-seed-2-1-turbo",
    "doubao-seed-vision": "doubao-seed-2-1-turbo",
    "doubao-seed-1-6-vision": "doubao-seed-2-1-turbo",
    "doubao-seed-1-6-vision-250815": "doubao-seed-2-1-turbo",
    "doubao-seed-2-0-mini-260428": "doubao-seed-2-0-mini",
    "doubao-seed-2-0-lite-260428": "doubao-seed-2-0-lite",
    "doubao-seed-2-1-turbo-260628": "doubao-seed-2-1-turbo",
    "doubao-seed-2-1-pro-260915": "doubao-seed-2-1-pro",
    "qwen/qwen3.6-plus": "openrouter-qwen-plus",
    "openrouter-deepseek": "openrouter-qwen-plus"
  };
  const knownRoutes = {
    "doubao-seed-2-0-mini": "豆包 Mini / doubao-seed-2-0-mini-260428（最快 / 准确一般）",
    "doubao-seed-2-0-lite": "豆包 Lite / doubao-seed-2-0-lite-260428（较快 / 准确中等）",
    "doubao-seed-2-1-turbo": "豆包 Turbo / doubao-seed-2-1-turbo-260628（快 / 准确较好）",
    "doubao-seed-2-1-pro": "豆包 Pro / doubao-seed-2-1-pro-260915（最准 / 较慢）",
    "openrouter-qwen-235b": "OpenRouter / qwen/qwen3-vl-235b-a22b-instruct（图像理解 / 本次首字约9秒）",
    "openrouter-qwen-27b": "OpenRouter / qwen/qwen3.8-27b（图文理解 / 本次首字约3.4秒）",
    "openrouter-qwen-flash": "OpenRouter / qwen/qwen3.8-flash（通用视觉 / 本次首字约4.7秒）",
    "openrouter-qwen-plus": "OpenRouter Qwen Plus / qwen/qwen3.6-plus（图文问答 / 本次首字约2.8秒）",
    "openrouter-glm": "OpenRouter GLM / z-ai/glm-4.6v（视觉问答 / 本次首字约3.1秒）",
    "openrouter-minimax": "OpenRouter MiniMax / minimax/minimax-m3（多模态 / 本次首字约3.2秒）",
    "deepseek-flash": "DeepSeek 官方 / deepseek-flash（快 / 准确一般）"
  };
  let currentTier = normalizeRoute(localStorage.getItem(modelTierKey) || "openrouter-qwen-235b");
  const maxScreenshots = 5;
  const maxAlbumItems = 12;
  const maxChatMessages = 40;
  const maxRenderChars = 40000;

  function normalizeRoute(value) {
    const key = String(value || "").trim();
    if (knownRoutes[key]) {
      return key;
    }
    if (routeAliases[key]) {
      return routeAliases[key];
    }
    const lowered = key.toLowerCase();
    if (knownRoutes[lowered]) {
      return lowered;
    }
    return routeAliases[lowered] || "openrouter-qwen-235b";
  }

  function nextRequestId(prefix) {
    requestCounter += 1;
    return `${prefix}-${Date.now()}-${requestCounter}`;
  }

  function extensionForMime(mime) {
    if (mime === "image/jpeg") {
      return "jpg";
    }
    if (mime === "image/webp") {
      return "webp";
    }
    return "png";
  }

  function isAppleMobile() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent)
      || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function screenshotFileName(mime) {
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    return `QQMusic-${stamp}.${extensionForMime(mime)}`;
  }

  function dataUrlToBlob(dataUrl) {
    const match = String(dataUrl || "").match(/^data:([^;]+);base64,(.+)$/);
    if (!match) {
      throw new Error("截图数据无效");
    }
    const mime = match[1];
    const binary = atob(match[2]);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return { blob: new Blob([bytes], { type: mime }), mime: mime };
  }

  function dataUrlToJpegFile(dataUrl, filename) {
    const parsed = dataUrlToBlob(dataUrl);
    if (parsed.mime === "image/jpeg") {
      return Promise.resolve(new File([parsed.blob], filename, { type: "image/jpeg" }));
    }
    return new Promise(function (resolve, reject) {
      const image = new Image();
      image.onload = function () {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(image, 0, 0);
        canvas.toBlob(function (blob) {
          if (!blob) {
            reject(new Error("转码失败"));
            return;
          }
          resolve(new File([blob], filename, { type: "image/jpeg" }));
        }, "image/jpeg", 0.92);
      };
      image.onerror = function () {
        reject(new Error("截图无法打开"));
      };
      image.src = dataUrl;
    });
  }

  function shareFilesToAlbum(files) {
    return navigator.share({
      files: files,
      title: "保存到相册"
    }).then(function () {
      return "shared";
    });
  }

  function showAlbumLongPressSheet(dataUrls) {
    if (!albumSheet || !albumSheetImages) {
      return;
    }
    albumSheetImages.textContent = "";
    dataUrls.forEach(function (dataUrl, index) {
      const image = document.createElement("img");
      image.src = dataUrl;
      image.alt = `待存入相册的截图 ${index + 1}`;
      albumSheetImages.appendChild(image);
    });
    albumSheet.hidden = false;
  }

  function hideAlbumLongPressSheet() {
    if (albumSheet) {
      albumSheet.hidden = true;
    }
    if (albumSheetImages) {
      albumSheetImages.textContent = "";
    }
  }

  function saveImagesToAlbum(dataUrls) {
    const names = dataUrls.map(function () {
      return screenshotFileName("image/jpeg");
    });
    return dataUrls.reduce(function (chain, dataUrl, index) {
      return chain.then(function (files) {
        return dataUrlToJpegFile(dataUrl, names[index]).then(function (file) {
          files.push(file);
          return files;
        });
      });
    }, Promise.resolve([])).then(function (files) {
      const shareAttempt = navigator.share
        ? shareFilesToAlbum(files).catch(function (error) {
          if (error && error.name === "AbortError") {
            throw error;
          }
          if (files.length <= 1) {
            throw error;
          }
          return files.reduce(function (next, file) {
            return next.then(function () {
              return shareFilesToAlbum([file]);
            });
          }, Promise.resolve("shared"));
        })
        : Promise.reject(new Error("当前浏览器不能分享到相册"));
      return shareAttempt.catch(function (error) {
        if (error && error.name === "AbortError") {
          throw error;
        }
        if (isAppleMobile()) {
          showAlbumLongPressSheet(dataUrls);
          return "longpress";
        }
        throw error;
      });
    });
  }

  function chatScreenshots() {
    return albumItems.filter(function (item) {
      return item.forChat;
    });
  }

  function removeSentChatScreenshots(sentItems) {
    const sentIds = {};
    sentItems.forEach(function (item) {
      sentIds[item.id] = true;
    });
    albumItems = albumItems.filter(function (item) {
      return !sentIds[item.id];
    });
  }

  function selectedAlbumItems() {
    return albumItems.filter(function (item) {
      return item.selected;
    });
  }

  function updateSaveAlbumButton() {
    const selected = selectedAlbumItems().length;
    if (saveAlbumButton) {
      saveAlbumButton.disabled = selected === 0;
      saveAlbumButton.textContent = selected > 1 ? `保存到相册（${selected}）` : "保存到相册";
    }
    if (selectAllAlbumButton) {
      const allSelected = albumItems.length > 0 && selected === albumItems.length;
      selectAllAlbumButton.textContent = allSelected ? "取消全选" : "全选";
      selectAllAlbumButton.disabled = albumItems.length === 0;
    }
  }

  function addAlbumItem(image, size, forChat, screenshotId) {
    albumItems.push({
      id: nextAlbumId,
      image: image,
      size: size || 0,
      selected: true,
      forChat: Boolean(forChat),
      screenshotId: screenshotId || ""
    });
    nextAlbumId += 1;
    if (forChat) {
      const extra = chatScreenshots().length - maxScreenshots;
      let remaining = extra;
      albumItems.forEach(function (item) {
        if (remaining > 0 && item.forChat) {
          item.forChat = false;
          remaining -= 1;
        }
      });
    }
    if (albumItems.length > maxAlbumItems) {
      albumItems = albumItems.slice(albumItems.length - maxAlbumItems);
    }
  }

  function saveSelectedToAlbum() {
    const selected = selectedAlbumItems();
    if (!selected.length) {
      return;
    }
    saveImagesToAlbum(selected.map(function (item) {
      return item.image;
    })).then(function (method) {
      if (method === "shared") {
        setSelectionStatus("completed", "请在菜单中点「存储图像 / 添加到照片」，不要选存储到文件");
      } else if (method === "longpress") {
        setSelectionStatus("completed", "请长按图片存入相册，不要选存储到文件");
      }
    }).catch(function (error) {
      if (error && error.name === "AbortError") {
        return;
      }
      showAlbumLongPressSheet(selected.map(function (item) {
        return item.image;
      }));
      setSelectionStatus("error", "无法直接写入相册，请长按图片选择添加到照片");
    });
  }

  function capText(text) {
    const value = text || "";
    if (value.length <= maxRenderChars) {
      return value;
    }
    return `内容较长，仅显示最后 ${maxRenderChars} 个字符。\n\n` + value.slice(-maxRenderChars);
  }

  function appendTextBlock(container, text) {
    if (!text) {
      return;
    }
    const block = document.createElement("div");
    block.className = "text-block";
    block.textContent = text;
    container.appendChild(block);
  }

  function renderFormattedText(container, text) {
    container.answerText = String(text || "");
    const value = capText(text);
    container.textContent = "";
    const codePattern = /```([a-zA-Z0-9_+-]*)\s*\n?([\s\S]*?)```/g;
    let lastIndex = 0;
    let match = codePattern.exec(value);
    while (match) {
      appendTextBlock(container, value.slice(lastIndex, match.index));
      const pre = document.createElement("pre");
      pre.className = "code-block";
      const code = document.createElement("code");
      if (match[1]) {
        code.dataset.language = match[1].toLowerCase();
      }
      code.textContent = match[2].trimEnd();

      const shell = document.createElement("div");
      shell.className = "code-shell";
      const toolbar = document.createElement("div");
      toolbar.className = "code-toolbar";
      if (match[1]) {
        const lang = document.createElement("span");
        lang.className = "code-lang";
        lang.textContent = match[1].toLowerCase();
        toolbar.appendChild(lang);
      }
      const copyButton = document.createElement("button");
      copyButton.type = "button";
      copyButton.className = "code-copy";
      copyButton.textContent = "复制代码";
      copyButton.addEventListener("click", function () {
        copyAnswer(code.textContent, copyButton, "复制代码");
      });
      toolbar.appendChild(copyButton);
      shell.appendChild(toolbar);
      pre.appendChild(code);
      shell.appendChild(pre);
      container.appendChild(shell);
      lastIndex = codePattern.lastIndex;
      match = codePattern.exec(value);
    }
    appendTextBlock(container, value.slice(lastIndex));
  }

  function outputPageStep() {
    return Math.max(120, (outputEl.clientHeight || 240) - 28);
  }

  function updateOutputPager() {
    if (!outputPage || !outputPrev || !outputNext) {
      return;
    }
    const step = outputPageStep();
    const maxScroll = Math.max(0, outputEl.scrollHeight - outputEl.clientHeight);
    const pages = maxScroll > 8
      ? Math.max(2, Math.ceil(outputEl.scrollHeight / step))
      : 1;
    const current = maxScroll <= 8
      ? 1
      : Math.min(pages, Math.floor((outputEl.scrollTop + 8) / step) + 1);
    outputPage.textContent = `${current} / ${pages}`;
    outputPrev.disabled = outputEl.scrollTop <= 2;
    outputNext.disabled = outputEl.scrollTop >= maxScroll - 2;
  }

  function scrollOutputPage(direction) {
    const step = outputPageStep();
    const maxScroll = Math.max(0, outputEl.scrollHeight - outputEl.clientHeight);
    const target = Math.max(0, Math.min(maxScroll, outputEl.scrollTop + direction * step));
    outputEl.scrollTo({ top: target, behavior: "smooth" });
    setTimeout(updateOutputPager, 350);
  }

  function stopAutoPaging() {
    if (autoPageTimer !== null) {
      clearInterval(autoPageTimer);
      autoPageTimer = null;
    }
  }

  function scrollableCodeBlock() {
    const blocks = Array.prototype.slice.call(outputEl.querySelectorAll("pre.code-block"));
    if (!blocks.length) {
      return null;
    }
    const view = outputEl.getBoundingClientRect();
    const middle = view.top + view.height / 2;
    let best = null;
    let bestDistance = Infinity;
    blocks.forEach(function (block) {
      const rect = block.getBoundingClientRect();
      if (rect.bottom < view.top || rect.top > view.bottom) {
        return;
      }
      if (block.scrollWidth <= block.clientWidth + 2) {
        return;
      }
      const distance = Math.abs(rect.top + rect.height / 2 - middle);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = block;
      }
    });
    return best;
  }

  function scrollOutputHorizontal(direction) {
    const block = scrollableCodeBlock();
    if (block) {
      const step = Math.max(48, Math.round(block.clientWidth * 0.6));
      block.scrollTo({ left: block.scrollLeft + direction * step, behavior: "smooth" });
      return true;
    }
    const maxLeft = Math.max(0, outputEl.scrollWidth - outputEl.clientWidth);
    if (maxLeft <= 2) {
      return false;
    }
    const step = Math.max(48, Math.round(outputEl.clientWidth * 0.6));
    const target = Math.max(0, Math.min(maxLeft, outputEl.scrollLeft + direction * step));
    outputEl.scrollTo({ left: target, behavior: "smooth" });
    return true;
  }

  function answerShortcutName(event) {
    const code = String(event.code || "");
    if (/^Key[WASD]$/.test(code)) {
      return code.slice(3).toLowerCase();
    }
    const key = String(event.key || "").toLowerCase();
    return ["w", "a", "s", "d"].indexOf(key) >= 0 ? key : "";
  }

  function handleAnswerShortcut(event) {
    if (!event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) {
      return;
    }
    const target = event.target;
    if (target) {
      const tag = String(target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable) {
        return;
      }
    }
    const name = answerShortcutName(event);
    if (!name) {
      return;
    }
    if (name === "w" || name === "s") {
      scrollOutputPage(name === "w" ? -1 : 1);
    } else {
      scrollOutputHorizontal(name === "a" ? -1 : 1);
    }
    stopAutoPaging();
    event.preventDefault();
  }

  function autoPageIntervalMs() {
    let seconds = Number(outputAutoSeconds && outputAutoSeconds.value) || 10;
    seconds = Math.max(3, Math.min(120, Math.round(seconds)));
    if (outputAutoSeconds && String(outputAutoSeconds.value) !== String(seconds)) {
      outputAutoSeconds.value = String(seconds);
    }
    return seconds * 1000;
  }

  function saveAutoPageConfig() {
    autoPageConfig = {
      enabled: Boolean(outputAutoEnabled && outputAutoEnabled.checked),
      seconds: Math.round(autoPageIntervalMs() / 1000)
    };
    localStorage.setItem(autoPageKey, JSON.stringify(autoPageConfig));
  }

  function startAutoPaging() {
    stopAutoPaging();
    if (!outputAutoEnabled || !outputAutoEnabled.checked) {
      return;
    }
    const maxScroll = Math.max(0, outputEl.scrollHeight - outputEl.clientHeight);
    if (maxScroll <= 8) {
      return;
    }
    outputEl.scrollTop = 0;
    updateOutputPager();
    autoPageTimer = setInterval(function () {
      const latestMax = Math.max(0, outputEl.scrollHeight - outputEl.clientHeight);
      if (outputEl.scrollTop >= latestMax - 2) {
        stopAutoPaging();
        return;
      }
      scrollOutputPage(1);
    }, autoPageIntervalMs());
  }

  function setOutput(text) {
    const previousTop = outputEl.scrollTop;
    const nextText = String(text || "");
    renderFormattedText(outputEl, nextText);
    outputEl.scrollTop = previousTop;
    updateOutputPager();
    if (!nextText.startsWith(chunkSourceText)) {
      chunkIndex = 0;
    }
    chunkSourceText = nextText;
    updateChunkStatus();
  }

  function trimChatMessages() {
    const messages = chatList.querySelectorAll(".chat-message");
    const extra = messages.length - maxChatMessages;
    for (let index = 0; index < extra; index += 1) {
      messages[index].remove();
    }
  }

  function setConnectionStatus(value, online) {
    statusEl.textContent = value;
    statusEl.classList.toggle("online", Boolean(online));
    fullscreenButton.disabled = !online;
    chatCaptureButton.disabled = !online;
    clearChatButton.disabled = !online;
    updateAskButton();
  }

  function updateAskButton() {
    const online = socket && socket.readyState === WebSocket.OPEN;
    askButton.disabled = !online || (chatScreenshots().length === 0 && !questionInput.value.trim());
  }

  function setSelectionStatus(state, message) {
    selectionEl.className = `selection-status ${state || "waiting"}`;
    selectionMessageEl.textContent = message || "等待操作";
  }

  function applyDevicePresence(payload) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    const mobiles = Number(payload.mobiles || 0);
    const desktop = Boolean(payload.desktop);
    statusEl.textContent = desktop
      ? `电脑已连接${mobiles > 1 ? ` · ${mobiles} 台手机` : ""}`
      : `等待电脑连接${mobiles > 1 ? ` · ${mobiles} 台手机` : ""}`;
    statusEl.classList.toggle("online", desktop);
  }

  function appendUserMessageOnce(requestId, text, imageCount) {
    if (!requestId || renderedChatRequests.has(requestId)) {
      return;
    }
    renderedChatRequests.add(requestId);
    appendMessage("user", String(text || "").trim() || "请根据截图作答", Number(imageCount || 0));
  }

  function clearChatScreenshots() {
    if (!albumItems.some(function (item) { return item.forChat; })) {
      return;
    }
    albumItems = albumItems.filter(function (item) {
      return !item.forChat;
    });
    renderPreviewList();
    updateAskButton();
  }

  function removeChatScreenshotsByIds(screenshotIds) {
    const wanted = new Set(screenshotIds || []);
    if (!wanted.size) {
      return false;
    }
    const before = albumItems.length;
    albumItems = albumItems.filter(function (item) {
      return !(item.forChat && wanted.has(item.screenshotId));
    });
    if (albumItems.length !== before) {
      renderPreviewList();
      updateAskButton();
    }
    return true;
  }

  function resetChatUi() {
    activeChatRequestId = null;
    activeAssistantBubble = null;
    activeAssistantText = "";
    latestChatRequestId = null;
    renderedChatRequests.clear();
    albumItems = [];
    hideAlbumLongPressSheet();
    renderPreviewList();
    chatList.textContent = "";
    const empty = document.createElement("div");
    empty.className = "empty-chat";
    empty.textContent = "可以只截图不输入文字；多张截图会和可选文字一起发送给 AI。";
    chatList.appendChild(empty);
    updateAskButton();
  }

  function setActiveTier(tier, persist) {
    const next = normalizeRoute(tier);
    currentTier = next;
    if (modelRoute && modelRoute.value !== next) {
      modelRoute.value = next;
    }
    if (modelHint) {
      modelHint.textContent = knownRoutes[next] || next;
    }
    if (persist !== false) {
      localStorage.setItem(modelTierKey, next);
    }
  }

  function applyModelAvailability(availableRoutes) {
    if (!modelRoute || !Array.isArray(availableRoutes)) {
      return;
    }
    const available = new Set(availableRoutes);
    Array.from(modelRoute.options).forEach(function (option) {
      if (!option.dataset.baseLabel) {
        option.dataset.baseLabel = option.textContent;
      }
      const enabled = available.has(option.value);
      option.disabled = !enabled;
      option.textContent = option.dataset.baseLabel + (enabled ? "" : "（你还没有连接模型喔）");
    });
  }

  function sendModelTier(tier) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    const route = normalizeRoute(tier);
    socket.send(JSON.stringify({
      type: "command.set_model_tier",
      payload: { tier: route, route: route }
    }));
  }

  function clearEmptyChat() {
    const empty = chatList.querySelector(".empty-chat");
    if (empty) {
      empty.remove();
    }
  }

  function renderPreviewList() {
    const selected = selectedAlbumItems().length;
    previewCount.textContent = albumItems.length
      ? `已截图：${albumItems.length}张，已选 ${selected} 张`
      : "已截图：0张";
    previewList.textContent = "";
    albumItems.forEach(function (screenshot, index) {
      const item = document.createElement("div");
      item.className = "preview-item" + (screenshot.selected ? " selected" : "");
      const image = document.createElement("img");
      image.src = screenshot.image;
      image.alt = `截图 ${index + 1}`;
      const check = document.createElement("input");
      check.type = "checkbox";
      check.className = "preview-check";
      check.checked = screenshot.selected;
      check.setAttribute("aria-label", `选择截图 ${index + 1} 保存到相册`);
      check.addEventListener("click", function (event) {
        event.stopPropagation();
      });
      check.addEventListener("change", function () {
        screenshot.selected = check.checked;
        renderPreviewList();
      });
      const remove = document.createElement("button");
      remove.className = "preview-remove";
      remove.type = "button";
      remove.setAttribute("aria-label", `删除截图 ${index + 1}`);
      remove.textContent = "×";
      remove.addEventListener("click", function (event) {
        event.stopPropagation();
        albumItems = albumItems.filter(function (entry) {
          return entry.id !== screenshot.id;
        });
        renderPreviewList();
        updateAskButton();
      });
      item.addEventListener("click", function () {
        screenshot.selected = !screenshot.selected;
        renderPreviewList();
      });
      item.appendChild(image);
      item.appendChild(check);
      item.appendChild(remove);
      previewList.appendChild(item);
    });
    updateSaveAlbumButton();
  }

  function appendMessage(role, text, imageCount) {
    clearEmptyChat();
    const item = document.createElement("div");
    item.className = `chat-message ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    if (imageCount) {
      const attachment = document.createElement("div");
      attachment.className = "attachment-chip";
      attachment.textContent = `已附带 ${imageCount} 张截图`;
      bubble.appendChild(attachment);
    }
    const content = document.createElement("div");
    content.className = "chat-content";
    if (role === "assistant") {
      const actions = document.createElement("div");
      actions.className = "answer-actions";
      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "clear-chat copy-answer";
      copy.textContent = "复制答案";
      copy.addEventListener("click", function () { copyAnswer(content.answerText, copy); });
      actions.appendChild(copy);
      bubble.appendChild(actions);
    }
    renderFormattedText(content, text);
    bubble.appendChild(content);
    item.appendChild(bubble);
    chatList.appendChild(item);
    trimChatMessages();
    chatList.scrollTop = chatList.scrollHeight;
    return content;
  }

  function startAssistantMessage(requestId) {
    activeChatRequestId = requestId;
    activeAssistantText = "";
    activeAssistantBubble = appendMessage("assistant", "分析中…", 0);
  }

  function scheduleAssistantRender() {
    if (renderScheduled) {
      return;
    }
    renderScheduled = true;
    requestAnimationFrame(function () {
      renderScheduled = false;
      if (activeAssistantBubble) {
        renderFormattedText(activeAssistantBubble, activeAssistantText || "分析中…");
        chatList.scrollTop = chatList.scrollHeight;
      }
    });
  }

  function appendAssistantDelta(requestId, delta) {
    if (!activeAssistantBubble || requestId !== activeChatRequestId) {
      return false;
    }
    activeAssistantText += delta || "";
    scheduleAssistantRender();
    return true;
  }

  function completeAssistantMessage(requestId, text) {
    if (!activeAssistantBubble || requestId !== activeChatRequestId) {
      return false;
    }
    activeAssistantText = text || activeAssistantText || "分析完成";
    renderFormattedText(activeAssistantBubble, activeAssistantText);
    activeChatRequestId = null;
    activeAssistantBubble = null;
    activeAssistantText = "";
    chatList.scrollTop = chatList.scrollHeight;
    return true;
  }

  function failAssistantMessage(message) {
    if (activeAssistantBubble) {
      renderFormattedText(activeAssistantBubble, `错误：${message || "模型调用失败"}`);
      activeChatRequestId = null;
      activeAssistantBubble = null;
      activeAssistantText = "";
      chatList.scrollTop = chatList.scrollHeight;
    }
  }

  function stopActiveAssistantMessage() {
    if (!activeAssistantBubble) {
      return;
    }
    const stopped = activeAssistantText
      ? `${activeAssistantText}\n\n（已停止）`
      : "（已停止）";
    renderFormattedText(activeAssistantBubble, stopped);
    activeChatRequestId = null;
    activeAssistantBubble = null;
    activeAssistantText = "";
  }

  function isOutdatedAnswerEvent(event) {
    const requestId = String(event.request_id || "");
    if (requestId.startsWith("fullscreen-")) {
      return requestId !== latestDirectRequestId;
    }
    if (requestId.startsWith("chat-")) {
      return requestId !== latestChatRequestId;
    }
    return false;
  }

  function handleEvent(event) {
    const payload = event.payload || {};
    if (event.type === "prompt.current" || event.type === "prompt.saved") {
      return;
    }
    if (event.type === "selection.status") {
      setSelectionStatus(payload.state, payload.message);
    } else if (event.type === "answer.started") {
      const fromBank = payload.source === "bank";
      if (payload.chat) {
        latestChatRequestId = event.request_id;
        appendUserMessageOnce(event.request_id, payload.user_text, payload.image_count);
        if (activeAssistantBubble && activeChatRequestId === event.request_id) {
          activeAssistantText = "";
          renderFormattedText(activeAssistantBubble, "分析中…");
        } else {
          if (activeAssistantBubble) {
            stopActiveAssistantMessage();
          }
          startAssistantMessage(event.request_id);
        }
        const sentIds = Array.isArray(payload.screenshot_ids) ? payload.screenshot_ids : [];
        if (sentIds.length) {
          removeChatScreenshotsByIds(sentIds);
        } else if (Number(payload.image_count || 0) > 0) {
          clearChatScreenshots();
        }
        setSelectionStatus("analyzing", fromBank ? "题库命中，正在返回答案" : "AI 正在分析，请稍候");
      } else {
        latestDirectRequestId = event.request_id;
        activeDirectRequestId = event.request_id;
        buffer = "";
        stopAutoPaging();
        setOutput(fromBank ? "题库命中，正在返回答案…" : "分析中…");
        outputEl.scrollTop = 0;
        setSelectionStatus("analyzing", fromBank ? "题库命中，正在返回答案" : "AI 正在分析，请稍候");
      }
    } else if (event.type === "answer.delta") {
      if (isOutdatedAnswerEvent(event)) {
        return;
      }
      if (String(event.request_id).startsWith("chat-")) {
        appendAssistantDelta(event.request_id, payload.delta || "");
      } else {
        buffer += payload.delta || "";
        setOutput(buffer || "分析中…");
      }
    } else if (event.type === "answer.completed") {
      if (isOutdatedAnswerEvent(event)) {
        return;
      }
      const result = payload.result || {};
      if (String(event.request_id).startsWith("chat-")) {
        completeAssistantMessage(event.request_id, result.text || activeAssistantText || "分析完成");
      } else {
        buffer = result.text || buffer || "分析完成";
        setOutput(buffer);
        startAutoPaging();
      }
      if (event.request_id === activeDirectRequestId) {
        activeDirectRequestId = null;
      }
      setSelectionStatus(
        "completed",
        result.source === "bank" ? "题库命中，已返回题库答案" : "答案已生成，可以继续框选或全屏截题"
      );
    } else if (event.type === "screenshot.captured") {
      if (payload.image) {
        const forChat = payload.add_to_buffer !== false;
        if (forChat) {
          addAlbumItem(payload.image, payload.size || 0, true, payload.screenshot_id);
          renderPreviewList();
          updateAskButton();
          const selected = selectedAlbumItems().length;
          setSelectionStatus("completed", `已添加截图，已选 ${selected} 张，可勾选后保存到相册或发送`);
        } else {
          setSelectionStatus("completed", "全屏截图已完成，不加入截图对话附件");
        }
      }
    } else if (event.type === "answer.error") {
      if (isOutdatedAnswerEvent(event)) {
        return;
      }
      if (String(event.request_id).startsWith("chat-")) {
        failAssistantMessage(payload.message);
      } else {
        buffer = "";
        setOutput(`错误：${payload.message || "模型调用失败"}`);
      }
      if (event.request_id === activeDirectRequestId) {
        activeDirectRequestId = null;
      }
      setSelectionStatus("error", "分析失败，可以重新框选或全屏截题");
    } else if (event.type === "conversation.cleared") {
      resetChatUi();
    } else if (event.type === "direct.cleared") {
      latestDirectRequestId = "__cleared__";
      activeDirectRequestId = null;
      buffer = "";
      stopAutoPaging();
      setOutput("等待电脑端发送题目…");
      setSelectionStatus("waiting", "等待操作");
    } else if (event.type === "device.presence") {
      applyDevicePresence(payload);
    } else if (event.type === "model.changed") {
      applyModelAvailability(payload.available_routes);
      setActiveTier(payload.route || payload.tier || currentTier, true);
      if (modelRoute && modelRoute.selectedOptions[0] && modelRoute.selectedOptions[0].disabled) {
        const fallback = Array.from(modelRoute.options).find(function (option) { return !option.disabled; });
        if (fallback) {
          setActiveTier(fallback.value, true);
          sendModelTier(fallback.value);
        }
      }
      if (payload.display_name && modelHint) {
        modelHint.textContent = payload.display_name;
      }
    } else if (event.type === "answer.scroll") {
      applyRemoteScroll(payload);
    } else if (event.type === "answer.autopan") {
      applyRemoteAutoPan(payload);
    }
  }

  function applyRemoteScroll(payload) {
    const data = payload || {};
    const direction = String(data.direction || "").toLowerCase();
    const steps = Math.max(1, Math.min(20, Number(data.steps) || 1));
    pauseCodePan();
    stopAutoPaging();
    if (direction === "up") {
      scrollOutputBy(-1, steps);
    } else if (direction === "down") {
      scrollOutputBy(1, steps);
    } else if (direction === "left") {
      scrollHorizontalBy(-1, steps);
    } else if (direction === "right") {
      scrollHorizontalBy(1, steps);
    } else if (direction === "top") {
      outputEl.scrollTo({ top: 0, behavior: "smooth" });
      setTimeout(updateOutputPager, 350);
    } else if (direction === "bottom") {
      outputEl.scrollTo({ top: outputEl.scrollHeight, behavior: "smooth" });
      setTimeout(updateOutputPager, 350);
    }
  }

  function applyRemoteAutoPan(payload) {
    const enabled = payload && typeof payload.enabled === "boolean"
      ? payload.enabled
      : !codeViewSettings.pan;
    codeViewSettings.pan = enabled;
    panPauseUntil = 0;
    saveCodeViewSettings();
    applyCodeViewSettings();
    if (enabled) {
      startCodePan();
    } else {
      stopCodePan();
    }
  }

  function connect() {
    if (!sessionId) {
      setConnectionStatus("缺少配对会话", false);
      return;
    }
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}/ws/mobile/${sessionId}?last_event_id=${lastEventId}`);
    socket.onopen = function () {
      reconnectMs = 1000;
      setConnectionStatus("电脑已连接", true);
      socket.send(JSON.stringify({ type: "command.get_model" }));
    };
    socket.onmessage = function (message) {
      const event = JSON.parse(message.data);
      if (event.event_id && event.event_id > lastEventId) {
        lastEventId = event.event_id;
        localStorage.setItem(cursorKey, String(lastEventId));
      }
      handleEvent(event);
    };
    socket.onclose = function () {
      socket = null;
      setConnectionStatus("正在重连", false);
      setTimeout(connect, reconnectMs);
      reconnectMs = Math.min(Math.floor(reconnectMs * 2), 30000);
    };
  }

  async function copyAnswer(text, button, label) {
    if (!text) return false;
    const restoreLabel = label || "复制答案";
    let copied = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        copied = true;
      }
    } catch (_) { /* Fall back for local HTTP and denied clipboard access. */ }
    if (!copied) {
      const previous = document.activeElement;
      const field = document.createElement("textarea");
      field.value = text;
      field.readOnly = true;
      field.style.cssText = "position:fixed;left:0;top:0;opacity:0;pointer-events:none";
      document.body.appendChild(field);
      field.focus();
      field.select();
      field.setSelectionRange(0, text.length);
      try { copied = document.execCommand("copy"); } catch (_) { copied = false; }
      field.remove();
      if (previous) previous.focus({preventScroll: true});
    }
    if (button) {
      button.textContent = copied ? "已复制" : "复制失败";
      setTimeout(function () { button.textContent = restoreLabel; }, 1500);
    }
    return copied;
  }

  function chunkSizeValue() {
    let size = Number(chunkSizeInput && chunkSizeInput.value) || 200;
    size = Math.max(20, Math.min(2000, Math.round(size)));
    if (chunkSizeInput && String(chunkSizeInput.value) !== String(size)) {
      chunkSizeInput.value = String(size);
    }
    return size;
  }

  function answerChunks() {
    const text = String(chunkSourceText || "");
    const size = chunkSizeValue();
    const chunks = [];
    for (let start = 0; start < text.length; start += size) {
      chunks.push(text.slice(start, start + size));
    }
    return chunks;
  }

  function updateChunkStatus() {
    const chunks = answerChunks();
    if (chunkCopyButton) {
      chunkCopyButton.disabled = chunks.length === 0 || chunkIndex >= chunks.length;
    }
    if (chunkProgress) {
      if (!chunks.length) {
        chunkProgress.textContent = "0 / 0 段";
      } else {
        const current = Math.min(chunkIndex + (chunkIndex < chunks.length ? 1 : 0), chunks.length);
        chunkProgress.textContent = `${current} / ${chunks.length} 段`;
      }
    }
    if (chunkResetButton) {
      chunkResetButton.disabled = chunks.length === 0;
    }
  }

  function resetChunks() {
    chunkIndex = 0;
    updateChunkStatus();
  }

  function copyNextChunk() {
    const chunks = answerChunks();
    if (chunkIndex >= chunks.length) {
      if (chunkCopyButton) {
        chunkCopyButton.textContent = "已到末尾";
        setTimeout(function () { chunkCopyButton.textContent = "复制下一段"; }, 1500);
      }
      return;
    }
    const text = chunks[chunkIndex];
    chunkIndex += 1;
    copyAnswer(text, chunkCopyButton, "复制下一段").then(function (copied) {
      if (copied) {
        updateChunkStatus();
      } else {
        chunkIndex -= 1;
        updateChunkStatus();
      }
    });
  }

  if (chunkSizeInput) {
    const savedSize = Number(localStorage.getItem(chunkSizeKey));
    if (savedSize >= 20 && savedSize <= 2000) {
      chunkSizeInput.value = String(Math.round(savedSize));
    }
    chunkSizeInput.addEventListener("change", function () {
      localStorage.setItem(chunkSizeKey, String(chunkSizeValue()));
      resetChunks();
    });
  }
  if (chunkCopyButton) {
    chunkCopyButton.addEventListener("click", copyNextChunk);
  }
  if (chunkResetButton) {
    chunkResetButton.addEventListener("click", resetChunks);
  }

  function loadCodeViewSettings() {
    try {
      const raw = JSON.parse(localStorage.getItem(CODE_VIEW_KEY) || "{}") || {};
      if (typeof raw.wrap === "boolean") {
        codeViewSettings.wrap = raw.wrap;
      }
      if (["11", "13", "16"].indexOf(String(raw.font)) >= 0) {
        codeViewSettings.font = String(raw.font);
      }
      if (typeof raw.pan === "boolean") {
        codeViewSettings.pan = raw.pan;
      }
    } catch (_) { /* 保留默认值 */ }
  }

  function saveCodeViewSettings() {
    localStorage.setItem(CODE_VIEW_KEY, JSON.stringify(codeViewSettings));
  }

  function applyCodeViewSettings() {
    document.body.classList.toggle("code-wrap", codeViewSettings.wrap);
    document.documentElement.style.setProperty("--code-font-size", `${codeViewSettings.font}px`);
    if (codeWrapToggle) {
      codeWrapToggle.checked = codeViewSettings.wrap;
    }
    if (codeFontSelect) {
      codeFontSelect.value = codeViewSettings.font;
    }
    if (codePanToggle) {
      codePanToggle.checked = codeViewSettings.pan;
    }
  }

  function pauseCodePan() {
    panPauseUntil = performance.now() + 6000;
  }

  function scrollOutputBy(direction, steps) {
    const step = outputPageStep() * Math.max(1, steps);
    const maxScroll = Math.max(0, outputEl.scrollHeight - outputEl.clientHeight);
    const target = Math.max(0, Math.min(maxScroll, outputEl.scrollTop + direction * step));
    outputEl.scrollTo({ top: target, behavior: "smooth" });
    setTimeout(updateOutputPager, 350);
  }

  function scrollHorizontalBy(direction, steps) {
    const block = scrollableCodeBlock();
    const count = Math.max(1, steps);
    if (block) {
      const step = Math.max(48, Math.round(block.clientWidth * 0.6)) * count;
      const maxLeft = Math.max(0, block.scrollWidth - block.clientWidth);
      const target = Math.max(0, Math.min(maxLeft, block.scrollLeft + direction * step));
      block.scrollTo({ left: target, behavior: "smooth" });
      return;
    }
    const maxLeft = Math.max(0, outputEl.scrollWidth - outputEl.clientWidth);
    if (maxLeft <= 2) {
      return;
    }
    const step = Math.max(48, Math.round(outputEl.clientWidth * 0.6)) * count;
    outputEl.scrollTo({ left: Math.max(0, Math.min(maxLeft, outputEl.scrollLeft + direction * step)), behavior: "smooth" });
  }

  // 慢速巡览：每 50ms 走一步，答案框约 14px/s、代码块约 10px/s，触底/触边反向
  function panStep() {
    if (!codeViewSettings.pan || performance.now() < panPauseUntil) {
      return;
    }
    const maxScroll = Math.max(0, outputEl.scrollHeight - outputEl.clientHeight);
    if (maxScroll > 4) {
      let next = outputEl.scrollTop + panDirection * 0.7;
      if (next >= maxScroll - 1) {
        next = maxScroll;
        panDirection = -1;
        panPauseUntil = performance.now() + 1200;
      } else if (next <= 1) {
        next = 0;
        panDirection = 1;
        panPauseUntil = performance.now() + 1200;
      }
      outputEl.scrollTop = Math.round(next);
      updateOutputPager();
    }
    const block = scrollableCodeBlock();
    if (block) {
      const maxLeft = Math.max(0, block.scrollWidth - block.clientWidth);
      let nextLeft = block.scrollLeft + panXDirection * 0.5;
      if (nextLeft >= maxLeft - 1) {
        nextLeft = maxLeft;
        panXDirection = -1;
      } else if (nextLeft <= 1) {
        nextLeft = 0;
        panXDirection = 1;
      }
      block.scrollLeft = Math.round(nextLeft);
    }
  }

  function startCodePan() {
    if (!codeViewSettings.pan) {
      return;
    }
    stopAutoPaging();
    if (panTimer === null) {
      panTimer = setInterval(panStep, 50);
    }
  }

  function stopCodePan() {
    if (panTimer !== null) {
      clearInterval(panTimer);
      panTimer = null;
    }
  }

  if (codeWrapToggle) {
    codeWrapToggle.addEventListener("change", function () {
      codeViewSettings.wrap = codeWrapToggle.checked;
      saveCodeViewSettings();
      applyCodeViewSettings();
    });
  }
  if (codeFontSelect) {
    codeFontSelect.addEventListener("change", function () {
      codeViewSettings.font = codeFontSelect.value;
      saveCodeViewSettings();
      applyCodeViewSettings();
    });
  }
  if (codePanToggle) {
    codePanToggle.addEventListener("change", function () {
      codeViewSettings.pan = codePanToggle.checked;
      saveCodeViewSettings();
      if (codeViewSettings.pan) {
        startCodePan();
      } else {
        stopCodePan();
      }
    });
  }
  loadCodeViewSettings();
  applyCodeViewSettings();
  startCodePan();


  document.getElementById("copy-direct").addEventListener("click", function () {
    copyAnswer(buffer, this);
  });

  fullscreenButton.addEventListener("click", function () {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    activeDirectRequestId = nextRequestId("fullscreen");
    latestDirectRequestId = activeDirectRequestId;
    buffer = "";
    setOutput("分析中…");
    setSelectionStatus("capturing", "已请求电脑截取全屏");
    socket.send(JSON.stringify({
      type: "command.fullscreen",
      payload: { client_request_id: activeDirectRequestId }
    }));
  });

  document.getElementById("clear-direct").addEventListener("click", function () {
    latestDirectRequestId = nextRequestId("cleared");
    activeDirectRequestId = null;
    buffer = "";
    setOutput("等待电脑端发送题目…");
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({type: "command.clear_direct"}));
    }
  });

  chatCaptureButton.addEventListener("click", function () {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    chatCaptureButton.disabled = true;
    setSelectionStatus("capturing", "已请求电脑截全屏并添加到对话缓冲区");
    socket.send(JSON.stringify({ type: "command.capture_fullscreen" }));
    setTimeout(function () {
      if (socket && socket.readyState === WebSocket.OPEN) {
        chatCaptureButton.disabled = false;
      }
    }, 1500);
  });

  questionInput.addEventListener("input", updateAskButton);

  if (modelRoute) {
    modelRoute.addEventListener("change", function () {
      const route = modelRoute.value || "openrouter-qwen-235b";
      setActiveTier(route, true);
      sendModelTier(route);
    });
  }

  if (saveAlbumButton) {
    saveAlbumButton.addEventListener("click", saveSelectedToAlbum);
  }
  if (selectAllAlbumButton) {
    selectAllAlbumButton.addEventListener("click", function () {
      const selectAll = selectedAlbumItems().length !== albumItems.length;
      albumItems.forEach(function (item) {
        item.selected = selectAll;
      });
      renderPreviewList();
    });
  }
  if (albumSheetClose) {
    albumSheetClose.addEventListener("click", hideAlbumLongPressSheet);
  }
  if (albumSheet) {
    albumSheet.addEventListener("click", function (event) {
      if (event.target === albumSheet) {
        hideAlbumLongPressSheet();
      }
    });
  }

  clearChatButton.addEventListener("click", function () {
    resetChatUi();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    socket.send(JSON.stringify({ type: "command.clear_conversation" }));
  });

  askButton.addEventListener("click", function () {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    const chatImages = chatScreenshots();
    const text = questionInput.value.trim();
    if (chatImages.length === 0 && !text) {
      updateAskButton();
      return;
    }
    const images = chatImages.map(function (screenshot) { return screenshot.image; });
    const requestId = nextRequestId("chat");
    stopActiveAssistantMessage();
    latestChatRequestId = requestId;
    activeChatRequestId = requestId;
    activeAssistantBubble = null;
    activeAssistantText = "";
    appendUserMessageOnce(requestId, text || "请根据截图作答", images.length);
    askButton.disabled = true;
    setSelectionStatus("analyzing", images.length ? `正在发送 ${images.length} 张截图给 AI` : "正在发送追问给 AI");
    socket.send(JSON.stringify({
      type: "command.submit_screenshots",
      payload: {
        text,
        images,
        screenshot_ids: chatImages.map(function (screenshot) { return screenshot.screenshotId; }).filter(Boolean),
        conversation: true,
        chat: true,
        client_request_id: requestId
      }
    }));
    questionInput.value = "";
    removeSentChatScreenshots(chatImages);
    renderPreviewList();
    setTimeout(function () {
      if (socket && socket.readyState === WebSocket.OPEN) {
        updateAskButton();
      }
    }, 1500);
  });

  if (outputPrev) {
    outputPrev.addEventListener("click", function () {
      stopAutoPaging();
      scrollOutputPage(-1);
    });
  }
  if (outputNext) {
    outputNext.addEventListener("click", function () {
      stopAutoPaging();
      scrollOutputPage(1);
    });
  }
  if (outputAutoEnabled) {
    outputAutoEnabled.addEventListener("change", function () {
      saveAutoPageConfig();
      if (outputAutoEnabled.checked) {
        stopCodePan();
        startAutoPaging();
      } else {
        stopAutoPaging();
      }
    });
  }
  if (outputAutoSeconds) {
    outputAutoSeconds.addEventListener("change", function () {
      saveAutoPageConfig();
      if (autoPageTimer !== null) {
        startAutoPaging();
      }
    });
  }
  if (outputExpand) {
    outputExpand.addEventListener("click", function () {
      const expanded = outputEl.classList.toggle("expanded");
      outputExpand.textContent = expanded ? "还原" : "放大";
      setTimeout(updateOutputPager, 80);
    });
  }
  outputEl.addEventListener("scroll", updateOutputPager, { passive: true });
  outputEl.addEventListener("wheel", stopAutoPaging, { passive: true });
  outputEl.addEventListener("touchstart", stopAutoPaging, { passive: true });
  outputEl.addEventListener("pointerdown", stopAutoPaging);
  outputEl.addEventListener("wheel", pauseCodePan, { passive: true });
  outputEl.addEventListener("touchstart", pauseCodePan, { passive: true });
  outputEl.addEventListener("pointerdown", pauseCodePan);
  document.addEventListener("keydown", pauseCodePan);
  document.addEventListener("keydown", handleAnswerShortcut);
  window.addEventListener("resize", updateOutputPager);

  renderPreviewList();
  updateOutputPager();
  setActiveTier(currentTier, false);
  connect();
})();
