// Shared multimedia composer and measured audio players. All files stay local until Send.
function mediaType(name, mime = "") {
  const ext = name.split(".").pop().toLowerCase();
  if (["jpg", "jpeg", "png", "webp"].includes(ext)) return "image";
  if (["mp4", "webm"].includes(ext) && !mime.startsWith("audio/")) return "video";
  if (["wav", "mp3", "m4a", "ogg", "webm"].includes(ext)) return "audio";
  if (["pdf", "docx", "xlsx", "txt", "csv"].includes(ext)) return "document";
  return null;
}
function bytesLabel(n) {
  return n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.ceil(n / 1024) + " KB";
}
function timeLabel(n) {
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n > 0 && n < 1) return "0:00." + Math.max(1, Math.round(n * 10));
  return Math.floor(n / 60) + ":" + String(Math.floor(n % 60)).padStart(2, "0");
}
function audioPlayer(url, metadata = {}, key = "preview", messageId = null) {
  const seconds = Number(metadata.duration_ms) / 1000;
  const peaks = metadata.waveform;
  const envelope = Array.isArray(peaks)
    ? `<span class="chat-wave" aria-hidden="true">${peaks.map((p) => `<i style="height:${Math.max(1, Math.min(30, Number(p) * 150))}px"></i>`).join("")}</span>`
    : '<span class="chat-wave-neutral" aria-hidden="true"></span>';
  return `<div class="chat-audio" data-player="${esc(key)}" data-message="${esc(messageId || "")}" data-duration="${Number.isFinite(seconds) ? seconds : 0}"><audio preload="none" src="${esc(url)}"></audio><button type="button" class="audio-play" aria-label="Play voice note">▶</button><div class="audio-middle">${envelope}<input type="range" class="audio-seek" min="0" max="${seconds > 0 ? seconds : 1}" step="0.1" value="0" aria-label="Seek audio" ${seconds > 0 ? "" : "disabled"}><span class="audio-clock"><span class="audio-position">0:00</span> / <span class="audio-total">${seconds > 0 ? timeLabel(seconds) : "Load audio"}</span></span></div><label class="audio-speed-label"><span class="sr-only">Playback speed</span><select class="audio-speed" aria-label="Playback speed"><option value="1">1×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label><span class="audio-feedback" role="status"></span><button type="button" class="audio-reload" hidden>Retry audio</button></div>`;
}
function wavEnvelope(blob) {
  return blob.arrayBuffer().then((buffer) => {
    const view = new DataView(buffer),
      count = Math.floor((buffer.byteLength - 44) / 2),
      step = Math.max(1, Math.ceil(count / 64));
    return Array.from({ length: 64 }, (_, i) => {
      let sum = 0,
        n = 0;
      for (let k = i * step; k < Math.min(count, (i + 1) * step); k++) {
        const x = view.getInt16(44 + 2 * k, true) / 32768;
        sum += x * x;
        n++;
      }
      return n ? Math.sqrt(sum / n) : 0;
    });
  });
}
function renderAttachment(item) {
  const url = item.url;
  const download = url + (url.includes("?") ? "&" : "?") + "download=true";
  const info = `${esc(item.filename)} · ${bytesLabel(item.size)}`;
  if (item.status !== "committed") return '<div class="chat-file">Attachment unavailable</div>';
  if (item.kind === "image")
    return `<div class="chat-image"><button type="button" class="chat-open-image" data-image-url="${esc(url)}" data-image-label="${esc(item.filename)}"><img loading="lazy" src="${esc(url)}?thumbnail=true" alt="${esc(item.filename)}"></button><small>${info}</small><a href="${esc(download)}" download>Download image</a></div>`;
  if (item.kind === "video")
    return `<div class="chat-video"><video controls preload="none" ${item.thumbnail ? `poster="${esc(url)}?thumbnail=true"` : ""} src="${esc(url)}" aria-label="${esc(item.filename)}"></video><small>${info} · ${timeLabel(item.duration_ms / 1000)}</small><a href="${esc(download)}" download>Download video</a><span class="media-error" role="status"></span></div>`;
  if (["voice", "audio"].includes(item.kind))
    return (
      audioPlayer(url, item, item.id, item.message_id) +
      `<small>${info}</small><a href="${esc(download)}" download>Download audio</a>`
    );
  return `<div class="chat-file"><span class="file-icon" aria-hidden="true">${item.content_type === "application/pdf" ? "PDF" : "FILE"}</span><div><strong>${esc(item.filename)}</strong><small>${bytesLabel(item.size)} · ${esc(item.content_type || "Document")}${item.pages ? ` · ${item.pages} pages` : ""}</small>${item.reconstruction ? "<small>Safety-processed copy. Formatting, formulas and digital signatures may change.</small>" : ""}<div class="actions">${item.thumbnail ? `<button type="button" class="chat-open-image" data-image-url="${esc(url)}?thumbnail=true" data-image-label="${esc(item.filename)}">Preview safe first page</button>` : ""}<a href="${esc(download)}" download>Download</a></div></div></div>`;
}
function chatMessageMedia(message) {
  if (message.withdrawn_at) return "";
  if (message.message_type === "voice" && message.voice)
    return audioPlayer(message.voice.url, message.voice, message.id, message.id);
  return (message.attachments || [])
    .map((a) => renderAttachment({ ...a, message_id: message.id }))
    .join("");
}
function renderFileDrafts() {
  const c = S.care,
    b = c.batch;
  const menu = c.attachMenu
    ? `<div class="attachment-menu"><button type="button" data-pick="image">Photos / gallery</button>${window.matchMedia("(pointer:coarse)").matches && "capture" in document.createElement("input") ? '<button type="button" data-pick="camera">Camera</button>' : ""}<button type="button" data-pick="video">Video</button><button type="button" data-pick="document">Document / PDF</button><button type="button" data-pick="audio">Audio file</button></div>`
    : "";
  const inputs = `<input type="file" id="care-file-picker" hidden multiple><input type="file" id="care-camera-picker" accept="image/jpeg,image/png" capture="environment" hidden>`;
  if (!b) return menu + inputs;
  const active = ["preparing", "uploading", "verifying", "sending"].includes(b.phase);
  const error = b.error ? `<p class="error" role="alert">${esc(b.error)}</p>` : "";
  return `${menu}${inputs}<section class="chat-prepared" aria-label="Attachments ready for review"><strong>${b.files.length} selected · ${esc(b.phase)}</strong>${b.files.map((f, i) => `<div class="prepared-file">${f.kind === "image" ? `<img src="${esc(f.url)}" alt="Selected ${esc(f.file.name)}">` : f.kind === "video" ? `<video controls preload="metadata" src="${esc(f.url)}"></video>` : '<span class="file-icon" aria-hidden="true">FILE</span>'}<div><strong>${esc(f.file.name)}</strong><small>${bytesLabel(f.file.size)} · ${esc(f.kind)} · limit ${bytesLabel(c.policy?.limits[f.kind] || 0)}</small><span id="file-phase-${f.id}">${esc(f.status || "Preview")}</span><progress id="file-progress-${f.id}" max="${f.file.size}" value="${f.offset || 0}" aria-label="Upload progress for ${esc(f.file.name)}"></progress></div><button type="button" data-remove-file="${i}" ${active ? "disabled" : ""} aria-label="Remove ${esc(f.file.name)}">Remove</button></div>`).join("")}${error}<div class="actions">${active ? '<button type="button" id="care-pause-files">Pause upload</button>' : b.approved ? '<button type="button" class="primary" id="care-resume-files">Resume send</button>' : ""}<button type="button" id="care-cancel-files">Cancel attachments</button></div><p class="muted">Files upload only after Send. ${c.policy?.scanner_configured ? "Antivirus verification configured." : "Development: antivirus unavailable; permitted synthetic files receive structural validation."}</p></section>`;
}
function discardFileDrafts() {
  const b = S.care?.batch;
  if (!b) return;
  b.cancelled = true;
  b.controller?.abort();
  for (const f of b.files) if (f.url) URL.revokeObjectURL(f.url);
  S.care.batch = null;
  delete S.care.resumeCommand;
}
async function pickChatFiles(files) {
  const c = S.care,
    peer = c.peer,
    patient = S.pid;
  if (!files.length) return;
  if (c.voice && !changeCareVoiceContact()) return;
  if (c.batch?.approved) {
    note("Finish or cancel the current send before choosing more files.");
    return;
  }
  const additions = [];
  try {
    c.policy ||= await api(`/patients/${S.pid}/messages/media-policy`);
    if (S.care !== c || c.peer !== peer || S.pid !== patient) return;
    const selected = c.batch?.files || [];
    if (selected.length + files.length > c.policy.max_files)
      throw Error(`Choose up to ${c.policy.max_files} files per message.`);
    for (const file of files) {
      const kind = mediaType(file.name, file.type);
      if (!kind || file.size === 0 || file.size > c.policy.limits[kind])
        throw Error("A selected file is empty, unsupported or above its type's limit.");
      additions.push({
        id: crypto.randomUUID(),
        file,
        kind,
        url: URL.createObjectURL(file),
        offset: 0,
        status: "Preview",
      });
    }
    if ([...selected, ...additions].reduce((n, f) => n + f.file.size, 0) > c.policy.total_bytes) {
      additions.forEach((f) => URL.revokeObjectURL(f.url));
      throw Error("Combined files exceed this application's message limit.");
    }
    c.batch ||= {
      peer: c.peer,
      patient: S.pid,
      command_id: crypto.randomUUID(),
      phase: "preview",
      files: [],
      approved: false,
    };
    if (c.resumeCommand) {
      const recovery = c.recoverable.filter((r) => r.client_message_id === c.resumeCommand);
      for (const file of additions) {
        const digest = await crypto.subtle.digest("SHA-256", await file.file.arrayBuffer());
        file.sha = [...new Uint8Array(digest)].map((x) => x.toString(16).padStart(2, "0")).join("");
        if (S.care !== c || c.peer !== peer || S.pid !== patient)
          throw Error("Contact changed; choose files again.");
        const old = recovery.find(
          (r) => r.sha256 === file.sha && r.expected_size === file.file.size,
        );
        if (!old || old.kind === "voice")
          throw Error("Select the original matching files for this unfinished attachment message.");
        file.id = old.client_attachment_id;
        file.upload_id = old.id;
        file.offset = old.offset;
      }
      c.batch.command_id = c.resumeCommand;
      c.batch.recoveryIds = recovery.map((r) => r.id);
    }
    c.batch.files.push(...additions);
    if (c.batch.recoveryIds?.every((id) => c.batch.files.some((f) => f.upload_id === id)))
      delete c.resumeCommand;
    c.attachMenu = false;
    render();
  } catch (error) {
    additions.forEach((f) => URL.revokeObjectURL(f.url));
    if (c.batch && !c.batch.files.length) c.batch = null;
    note(error.message);
  }
}
async function mediaRequest(path, method = "GET", body, signal) {
  const r = await fetch("/api" + path, {
    method,
    headers: {
      "X-CSRF-Token": S.csrf,
      ...(S.user ? { "X-Expected-Actor": S.user.id } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  const result = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (
      typeof result.detail === "string" &&
      (result.detail.startsWith("Session account changed") ||
        result.detail === "Invalid CSRF token")
    )
      careSessionChanged();
    const e = new Error(typeof result.detail === "string" ? result.detail : "Media request failed");
    e.status = r.status;
    e.retryAfter = Number(r.headers.get("retry-after")) || 0;
    throw e;
  }
  return result;
}
async function withMediaRetry(fn, signal) {
  for (let attempt = 0; ; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (
        signal?.aborted ||
        e.name === "AbortError" ||
        attempt >= 2 ||
        (e.status && e.status < 500 && ![408, 429].includes(e.status)) ||
        e.retryAfter > 30
      )
        throw e;
      await new Promise((resolve, reject) => {
        const timer = setTimeout(
          resolve,
          Math.max(e.retryAfter * 1000, 500 * 2 ** attempt + Math.random() * 250),
        );
        signal?.addEventListener(
          "abort",
          () => {
            clearTimeout(timer);
            reject(new DOMException("Aborted", "AbortError"));
          },
          { once: true },
        );
      });
    }
  }
}
function uploadChunk(path, blob, offset, progress, signal) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PATCH", "/api" + path);
    xhr.setRequestHeader("X-CSRF-Token", S.csrf);
    if (S.user) xhr.setRequestHeader("X-Expected-Actor", S.user.id);
    xhr.setRequestHeader("Content-Type", "application/offset+octet-stream");
    xhr.setRequestHeader("Upload-Offset", String(offset));
    xhr.timeout = 35000;
    const abort = () => xhr.abort();
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    signal?.addEventListener("abort", abort, { once: true });
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) progress(offset + e.loaded);
    };
    xhr.onload = () => {
      signal?.removeEventListener("abort", abort);
      let result = {};
      try {
        result = JSON.parse(xhr.responseText);
      } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(result);
      else {
        const e = new Error(
          typeof result.detail === "string" ? result.detail : "Upload chunk failed",
        );
        e.status = xhr.status;
        reject(e);
      }
    };
    xhr.onerror = () => reject(new TypeError("Connection interrupted"));
    xhr.ontimeout = () => reject(new Error("Upload timed out"));
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));
    xhr.send(blob);
  });
}
async function uploadChatFile(file, operation, update) {
  const c = S.care,
    signal = operation.controller?.signal || operation.abort?.signal;
  const valid = () => S.care === c && !operation.cancelled && !signal?.aborted;
  if (!file.sha) {
    update(0, "Preparing");
    const digest = await crypto.subtle.digest("SHA-256", await file.file.arrayBuffer());
    file.sha = [...new Uint8Array(digest)].map((x) => x.toString(16).padStart(2, "0")).join("");
  }
  if (!valid()) throw new DOMException("Aborted", "AbortError");
  let status;
  if (file.upload_id)
    status = await mediaRequest(
      `/patients/${operation.patient}/messages/uploads/${file.upload_id}`,
      "GET",
      null,
      signal,
    );
  else {
    status = await withMediaRetry(
      () =>
        mediaRequest(
          `/patients/${operation.patient}/messages/threads/${encodeURIComponent(operation.peer)}/uploads`,
          "POST",
          {
            client_message_id: operation.command_id,
            client_attachment_id: file.id,
            filename: file.file.name,
            content_type: file.file.type || "application/octet-stream",
            size: file.file.size,
            sha256: file.sha,
            kind: file.kind,
          },
          signal,
        ),
      signal,
    );
    file.upload_id = status.id;
  }
  if (status.status === "committed") return status;
  if (
    status.status === "quarantined" &&
    ["scanner_required", "scanner_unavailable"].includes(status.error)
  )
    status = await mediaRequest(
      `/patients/${operation.patient}/messages/uploads/${file.upload_id}/complete?retry_scan=true`,
      "POST",
      null,
      signal,
    );
  file.offset = status.offset;
  while (status.status === "uploading" && file.offset < file.file.size) {
    if (!valid()) throw new DOMException("Aborted", "AbortError");
    const offset = file.offset,
      part = file.file.slice(offset, offset + status.chunk_size);
    update(offset, "Uploading");
    try {
      status = await uploadChunk(
        `/patients/${operation.patient}/messages/uploads/${file.upload_id}`,
        part,
        offset,
        (n) => update(n, "Uploading"),
        signal,
      );
    } catch (error) {
      if (signal?.aborted) throw error;
      status = await withMediaRetry(
        () =>
          mediaRequest(
            `/patients/${operation.patient}/messages/uploads/${file.upload_id}`,
            "GET",
            null,
            signal,
          ),
        signal,
      );
      if (status.offset === offset) throw error;
    }
    file.offset = status.offset;
    update(file.offset, "Uploading");
  }
  for (let attempt = 0; !["ready", "committed"].includes(status.status); attempt++) {
    if (!valid()) throw new DOMException("Aborted", "AbortError");
    if (["rejected", "quarantined", "cancelled", "expired"].includes(status.status)) {
      const error = new Error(
        status.status === "quarantined"
          ? "File is quarantined and cannot be sent. Ask the care team to review scanning availability or choose another file."
          : "File was rejected by validation. Remove it or choose a supported file.",
      );
      error.status = 415;
      throw error;
    }
    if (attempt > 120)
      throw Error("Processing is taking longer than expected. Resume to check the same upload.");
    update(file.file.size, "Verifying");
    status = await withMediaRetry(
      () =>
        mediaRequest(
          `/patients/${operation.patient}/messages/uploads/${file.upload_id}/complete`,
          "POST",
          null,
          signal,
        ),
      signal,
    );
    if (status.status === "verifying") await new Promise((r) => setTimeout(r, 500));
  }
  update(file.file.size, "Ready");
  return status;
}
async function sendFileBatch() {
  const c = S.care,
    b = c.batch;
  if (!b || b.cancelled || ["uploading", "preparing", "verifying", "sending"].includes(b.phase))
    return;
  if (!b.approved) {
    if (b.recoveryIds?.some((id) => !b.files.some((f) => f.upload_id === id))) {
      note(
        "Reselect every original file before sending this recovered message, or cancel the unfinished uploads.",
      );
      return;
    }
    b.caption = c.drafts[b.peer] || "";
    b.reply_to_id = c.reply?.id || null;
    b.approved = true;
    c.drafts[b.peer] = "";
    c.reply = null;
  }
  b.controller = new AbortController();
  b.phase = navigator.onLine ? "preparing" : "waiting for network";
  b.error = "";
  render();
  if (!navigator.onLine) return;
  try {
    const existing = await mediaRequest(
      `/patients/${b.patient}/messages/threads/${b.peer}/command/${b.command_id}`,
    );
    if (!existing.message) {
      for (const file of b.files) {
        b.phase = "uploading";
        await uploadChatFile(file, b, (n, phase) => {
          file.status = phase;
          file.offset = Math.min(n, file.file.size);
          const progress = document.getElementById("file-progress-" + file.id);
          if (progress) progress.value = file.offset;
          const label = document.getElementById("file-phase-" + file.id);
          if (label)
            label.textContent =
              phase + " · " + Math.floor((100 * file.offset) / file.file.size) + "%";
        });
      }
      b.phase = "sending";
      await withMediaRetry(
        () =>
          mediaRequest(
            `/patients/${b.patient}/messages/threads/${b.peer}`,
            "POST",
            {
              command_id: b.command_id,
              body: b.caption,
              attachment_ids: b.files.map((f) => f.upload_id),
              reply_to_id: b.reply_to_id,
            },
            b.controller.signal,
          ),
        b.controller.signal,
      );
    }
    if (S.care !== c) return;
    discardFileDrafts();
    c.forceLatest = true;
    await loadCareInbox();
    await loadCareThread();
    render();
    note("Message saved in app.");
  } catch (error) {
    if (S.care !== c || b.cancelled) return;
    b.phase =
      b.phase === "paused"
        ? "paused"
        : !navigator.onLine
          ? "waiting for network"
          : error.status && error.status < 500
            ? "rejected"
            : "failed";
    b.error = error.message;
    render();
  }
}
async function cancelFileBatch() {
  const c = S.care,
    b = c.batch;
  if (!b) return;
  b.controller?.abort();
  b.cancelled = true;
  try {
    const existing = await mediaRequest(
      `/patients/${b.patient}/messages/threads/${b.peer}/command/${b.command_id}`,
    );
    if (existing.message)
      note("This message was already saved. You can withdraw it from the timeline.");
    else
      for (const f of b.files)
        if (f.upload_id)
          await mediaRequest(`/patients/${b.patient}/messages/uploads/${f.upload_id}`, "DELETE");
  } catch {
    note(
      "Local upload stopped. Uncommitted server uploads expire; a saved message remains in history.",
    );
  }
  if (S.care === c) {
    discardFileDrafts();
    await loadCareMessages();
    render();
  }
}
function bindFileComposer() {
  const c = S.care;
  if (document.querySelector("#care-attach"))
    $("#care-attach").onclick = () => {
      c.attachMenu = !c.attachMenu;
      render();
    };
  const filters = {
    image: ".jpg,.jpeg,.png,.webp",
    video: ".mp4,.webm",
    document: ".pdf,.docx,.xlsx,.txt,.csv",
    audio: ".wav,.mp3,.m4a,.ogg,.webm",
  };
  document.querySelectorAll("[data-pick]").forEach(
    (b) =>
      (b.onclick = () => {
        const input = document.querySelector(
          b.dataset.pick === "camera" ? "#care-camera-picker" : "#care-file-picker",
        );
        if (b.dataset.pick !== "camera") input.accept = filters[b.dataset.pick];
        input.click();
      }),
  );
  document
    .querySelectorAll("#care-file-picker,#care-camera-picker")
    .forEach((input) => (input.onchange = () => pickChatFiles([...input.files])));
  document.querySelectorAll("[data-remove-file]").forEach(
    (b) =>
      (b.onclick = async () => {
        const batch = c.batch,
          index = Number(b.dataset.removeFile),
          file = batch.files[index];
        if (file.upload_id) {
          try {
            await mediaRequest(
              `/patients/${batch.patient}/messages/uploads/${file.upload_id}`,
              "DELETE",
            );
          } catch {
            note("This file is already committed or access changed. Refresh the conversation.");
            return;
          }
        }
        URL.revokeObjectURL(file.url);
        batch.files.splice(index, 1);
        if (!batch.files.length) discardFileDrafts();
        else {
          for (const f of batch.files) {
            if (f.upload_id) {
              try {
                await mediaRequest(
                  `/patients/${batch.patient}/messages/uploads/${f.upload_id}`,
                  "DELETE",
                );
              } catch {
                note("An unfinished upload will expire automatically.");
              }
            }
          }
          c.drafts[batch.peer] ||= batch.caption || "";
          batch.phase = "preview";
          batch.approved = false;
          batch.command_id = crypto.randomUUID();
          for (const f of batch.files) {
            f.id = crypto.randomUUID();
            delete f.upload_id;
            f.offset = 0;
          }
        }
        render();
      }),
  );
  if ($("#care-pause-files"))
    $("#care-pause-files").onclick = () => {
      c.batch.phase = "paused";
      c.batch.controller.abort();
      render();
    };
  if ($("#care-resume-files")) $("#care-resume-files").onclick = sendFileBatch;
  if ($("#care-cancel-files")) $("#care-cancel-files").onclick = cancelFileBatch;
  document.querySelectorAll(".chat-open-image").forEach(
    (b) =>
      (b.onclick = () => {
        const dialog = document.createElement("dialog");
        dialog.className = "chat-viewer";
        dialog.innerHTML = `<button type="button" aria-label="Close media viewer">Close</button><p>${esc(b.dataset.imageLabel)}</p><img src="${esc(b.dataset.imageUrl)}" alt="${esc(b.dataset.imageLabel)}">`;
        dialog.querySelector("button").onclick = () => dialog.close();
        dialog.onclose = () => dialog.remove();
        document.body.append(dialog);
        dialog.showModal();
      }),
  );
  document.querySelectorAll(".chat-video video").forEach((v) =>
    v.addEventListener("error", () => {
      v.parentElement.querySelector(".media-error").textContent =
        "Video is unavailable or unsupported on this device. Use an authorized download or ask your contact.";
    }),
  );
}
async function reportCareReceipt(ids, event) {
  const c = S.care;
  if (!ids.length || !c?.peer) return;
  try {
    await api(`/patients/${S.pid}/messages/threads/${c.peer}/receipts`, "POST", {
      message_ids: ids,
      event,
    });
  } catch {
    c.pendingReceipts ||= [];
    if (
      !c.pendingReceipts.some(
        (r) =>
          r.event === event && r.peer === c.peer && JSON.stringify(r.ids) === JSON.stringify(ids),
      )
    )
      c.pendingReceipts.push({ ids, event, peer: c.peer });
    c.pendingReceipts = c.pendingReceipts.slice(-100);
  }
}
async function flushCareReceipts() {
  const c = S.care;
  if (!c?.pendingReceipts?.length || c.flushingReceipts) return;
  c.flushingReceipts = true;
  try {
    while (S.care === c && c.pendingReceipts.length) {
      const r = c.pendingReceipts[0];
      await api(`/patients/${S.pid}/messages/threads/${r.peer}/receipts`, "POST", {
        message_ids: r.ids,
        event: r.event,
      });
      c.pendingReceipts.shift();
    }
  } catch {
  } finally {
    c.flushingReceipts = false;
  }
}
function closeCareViewers() {
  document.querySelectorAll(".chat-viewer").forEach((dialog) => dialog.remove());
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
}
function bindAudioPlayers() {
  const c = S.care;
  if (!c) return;
  c.playback ||= {};
  document.querySelectorAll(".chat-audio").forEach((root) => {
    const audio = root.querySelector("audio"),
      button = root.querySelector(".audio-play"),
      seek = root.querySelector(".audio-seek"),
      clock = root.querySelector(".audio-position"),
      total = root.querySelector(".audio-total"),
      feedback = root.querySelector(".audio-feedback"),
      retry = root.querySelector(".audio-reload"),
      speed = root.querySelector(".audio-speed");
    const key = root.dataset.player,
      record = c.playback[key] || { position: 0, speed: 1 };
    audio.playbackRate = record.speed;
    speed.value = String(record.speed);
    const save = () => {
      if (S.care === c)
        c.playback[key] = { position: audio.currentTime || 0, speed: audio.playbackRate };
    };
    const messageId = root.dataset.message;
    const incoming =
      messageId &&
      c.thread?.messages.some((m) => m.id === messageId && m.recipient_id === S.user.id);
    audio.addEventListener("loadedmetadata", () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        seek.max = audio.duration;
        seek.disabled = false;
        total.textContent = timeLabel(audio.duration);
        if (record.position < audio.duration) audio.currentTime = record.position;
      }
      feedback.textContent = "";
    });
    audio.addEventListener("timeupdate", () => {
      seek.value = audio.currentTime;
      clock.textContent = timeLabel(audio.currentTime);
      save();
    });
    audio.addEventListener("playing", () => {
      button.textContent = "❚❚";
      button.setAttribute("aria-label", "Pause voice note");
      feedback.textContent = "";
      if (incoming) reportCareReceipt([messageId], "playback_started");
    });
    audio.addEventListener("pause", () => {
      button.textContent = "▶";
      button.setAttribute("aria-label", "Play voice note");
      save();
    });
    audio.addEventListener("ended", () => {
      if (incoming) reportCareReceipt([messageId], "playback_completed");
      c.playback[key] = { position: 0, speed: audio.playbackRate };
      button.textContent = "▶";
    });
    audio.addEventListener("error", () => {
      feedback.textContent =
        "Audio unavailable. Check your connection or access; ask your contact if it continues.";
      retry.hidden = false;
      button.disabled = true;
    });
    button.onclick = async () => {
      if (!audio.paused) {
        audio.pause();
        return;
      }
      pauseCareAudio();
      feedback.textContent = "Loading audio…";
      try {
        await audio.play();
      } catch {
        feedback.textContent = "Playback unavailable on this device or access changed.";
        retry.hidden = false;
      }
    };
    seek.oninput = () => {
      if (audio.readyState > 0) {
        audio.currentTime = Number(seek.value);
        save();
      }
    };
    speed.onchange = () => {
      audio.playbackRate = Number(speed.value);
      save();
    };
    retry.onclick = () => {
      button.disabled = false;
      retry.hidden = true;
      feedback.textContent = "Reloading audio…";
      audio.load();
    };
  });
}

function renderVoiceDraft(v) {
  if (!v) return "";
  const capture = ["permission", "recording", "paused", "processing"].includes(v.phase);
  const status = {
    permission: "Waiting for microphone permission…",
    recording: 'Recording · <span id="care-voice-time">0</span> seconds',
    paused:
      'Recording paused · <span id="care-voice-time">' +
      Math.floor((v.activeMs || 0) / 1000) +
      "</span> seconds",
    processing: "Preparing the completed recording…",
    preview: "Preview ready. Nothing has been sent.",
    sending: "Uploading and saving…",
    unconfirmed: "Saving unconfirmed. Retry keeps the same note ID.",
  }[v.phase];
  const metadata = { duration_ms: v.blob ? (v.blob.size - 44) / 48 : 0, waveform: v.waveform };
  return `<section id="care-voice" class="care-voice"><h3>Your voice note</h3><p role="status" aria-live="polite">${status || "Microphone off"}</p>${v.error ? `<p class="error" role="alert">${esc(v.error)}</p>` : ""}${capture ? `${v.levelAnalyser ? '<label>Audio level<progress id="care-record-level" max="1" value="0"></progress></label>' : ""}<div class="actions">${["recording", "paused"].includes(v.phase) ? `<button type="button" class="primary" id="care-voice-finish">Finish recording</button><button type="button" id="care-record-pause">${v.phase === "paused" ? "Resume recording" : "Pause recording"}</button>` : ""}<button type="button" id="care-voice-discard">Cancel recording</button></div>` : `${audioPlayer(v.url, metadata, "draft-" + v.command_id)}<form id="care-voice-form"><label>Optional text for your contact<textarea name="caption" maxlength="2000" rows="2" ${["sending", "unconfirmed"].includes(v.phase) ? "disabled" : ""}>${esc(v.caption || "")}</textarea></label><div class="actions"><button class="primary" ${v.phase === "sending" ? "disabled" : ""}>${v.phase === "unconfirmed" ? "Retry saving voice note" : "Send voice note"}</button>${v.phase === "sending" ? '<button type="button" id="care-voice-upload-pause">Pause upload</button>' : `<button type="button" id="care-voice-discard">Discard voice note</button>`}</div></form>${v.phase === "sending" || v.uploadFile ? `<progress id="voice-upload-progress" max="${v.uploadFile?.file.size || 1}" value="${v.uploaded || 0}"></progress><span id="voice-upload-status">${esc(v.uploadStage || "Preparing")}</span>` : ""}`}<small>Record up to 20 seconds. Preview and Send are separate actions. Sent notes are stored privately; no speech or AI provider receives them.</small></section>`;
}
function pauseFileSend() {
  const batch = S.care?.batch;
  if (batch && ["preparing", "uploading", "verifying", "sending"].includes(batch.phase)) {
    batch.phase = "paused";
    batch.controller?.abort();
  }
}
