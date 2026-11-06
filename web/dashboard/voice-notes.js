// Explicit, recipient-bound voice-note recording and upload. No speech provider.
function pauseCareAudio() {
  document
    .querySelectorAll(".care-history audio, #care-voice audio, .care-conversation video")
    .forEach((a) => a.pause());
}
function careAudioPlaying() {
  return [
    ...document.querySelectorAll(
      ".care-history audio, #care-voice audio, .care-conversation video",
    ),
  ].some((a) => !a.paused && !a.ended);
}
function careVoiceBusy() {
  return ["permission", "recording", "paused", "processing", "sending"].includes(
    S.care?.voice?.phase,
  );
}
function disposeCareVoice() {
  const v = S.care?.voice;
  if (!v) return;
  v.cancelled = true;
  clearTimeout(v.limit);
  clearInterval(v.timer);
  v.abort?.abort();
  if (v.rec && v.rec.state !== "inactive") v.rec.stop();
  v.stream?.getTracks().forEach((t) => t.stop());
  v.levelContext?.close().catch(() => {});
  clearInterval(v.levelTimer);
  if (v.url) URL.revokeObjectURL(v.url);
  pauseCareAudio();
  S.care.voice = null;
}
function stopCareCapture() {
  const v = S.care?.voice;
  pauseCareAudio();
  closeCareFeed();
  pauseFileSend();
  if (v && ["permission", "recording", "paused", "processing"].includes(v.phase))
    disposeCareVoice();
  if (v?.phase === "sending") {
    v.phase = "unconfirmed";
    v.abort?.abort();
  }
}
function changeCareVoiceContact() {
  const v = S.care?.voice;
  if (!v) return true;
  if (
    !confirm(
      v.phase === "unconfirmed"
        ? "Saving is unconfirmed and the note may already be saved. Discard this local copy before changing contact?"
        : "Discard this unsent voice note before changing contact?",
    )
  )
    return false;
  disposeCareVoice();
  return true;
}
function voiceMessage(m) {
  return m.message_type === "voice"
    ? `<div class="voice-message"><p>Voice note · ${(m.voice.duration_ms / 1000).toFixed(1)} seconds</p><audio controls preload="none" src="${esc(m.voice.url)}" aria-label="Play voice note"></audio><p class="voice-playback-error" role="status"></p></div>`
    : "";
}
function renderCareVoice() {
  return renderVoiceDraft(S.care.voice);
}
async function startCareVoice() {
  const c = S.care;
  if (c.busy || c.voice || !c.peer) return;
  pauseCareAudio();
  if (typeof stopCompanion === "function") stopCompanion(false);
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    c.error = "Recording is unavailable here. You can send a text message.";
    render();
    return;
  }
  const v = {
    phase: "permission",
    peer: c.peer,
    patient: S.pid,
    caption: "",
    command_id: crypto.randomUUID(),
  };
  c.voice = v;
  c.error = "";
  render();
  const current = () =>
    S.care === c && c.voice === v && !v.cancelled && c.peer === v.peer && S.pid === v.patient;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (!current()) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    v.stream = stream;
    const preferred = [
      "audio/webm;codecs=opus",
      "audio/ogg;codecs=opus",
      "audio/mp4",
      "audio/webm",
    ].find((type) => MediaRecorder.isTypeSupported?.(type));
    v.rec = new MediaRecorder(stream, preferred ? { mimeType: preferred } : undefined);
    try {
      v.levelContext = new AudioContext();
      v.levelAnalyser = v.levelContext.createAnalyser();
      v.levelAnalyser.fftSize = 256;
      v.levelContext.createMediaStreamSource(stream).connect(v.levelAnalyser);
      v.levelTimer = setInterval(() => {
        const meter = document.querySelector("#care-record-level");
        if (current() && meter) {
          const data = new Float32Array(256);
          v.levelAnalyser.getFloatTimeDomainData(data);
          meter.value =
            v.phase === "paused" ? 0 : Math.sqrt(data.reduce((n, x) => n + x * x, 0) / data.length);
        }
      }, 100);
    } catch {}

    const chunks = [];
    let bytes = 0;
    const fail = () => {
      if (current()) {
        disposeCareVoice();
        c.error = "Recording was interrupted. Try again or use text.";
        if (careActive()) render();
      }
    };
    v.rec.onerror = fail;
    stream.getTracks().forEach((t) => {
      t.onended = fail;
    });
    v.rec.ondataavailable = (e) => {
      if (e.data.size && current()) {
        chunks.push(e.data);
        bytes += e.data.size;
        if (bytes > 2 * 1024 * 1024) fail();
      }
    };
    v.rec.onstop = async () => {
      clearTimeout(v.limit);
      clearInterval(v.timer);
      stream.getTracks().forEach((t) => t.stop());
      clearInterval(v.levelTimer);
      v.levelContext?.close().catch(() => {});
      if (!current()) return;
      v.phase = "processing";
      render();
      try {
        v.sourceBlob = new Blob(chunks, {
          type: v.rec.mimeType || chunks[0]?.type || "application/octet-stream",
        });
        const blob = await pcmWav(v.sourceBlob);
        if (!current()) return;
        v.blob = blob;
        v.url = URL.createObjectURL(blob);
        v.waveform = await wavEnvelope(blob);
        if (!current()) {
          URL.revokeObjectURL(v.url);
          return;
        }
        v.phase = "preview";
        render();
      } catch {
        fail();
      }
    };
    v.rec.start(250);
    v.phase = "recording";
    v.started = Date.now();
    v.activeMs = 0;
    render();
    v.timer = setInterval(() => {
      const el = document.querySelector("#care-voice-time");
      if (current() && el)
        el.textContent = Math.floor(
          (v.activeMs + (v.phase === "recording" ? Date.now() - v.started : 0)) / 1000,
        );
    }, 1000);
    v.limit = setTimeout(() => {
      if (current() && v.rec.state === "recording") v.rec.stop();
    }, 20000);
  } catch {
    if (current()) {
      disposeCareVoice();
      c.error = "Microphone permission was denied or the device is unavailable. You can use text.";
      if (careActive()) render();
    }
  }
}
async function sendCareVoice() {
  const c = S.care,
    v = c.voice;
  if (
    !v?.blob ||
    c.busy ||
    !["preview", "unconfirmed"].includes(v.phase) ||
    c.peer !== v.peer ||
    S.pid !== v.patient
  )
    return;
  pauseCareAudio();
  c.busy = true;
  c.error = "";
  v.phase = "sending";
  v.abort = new AbortController();
  const timer = setTimeout(() => v.abort.abort(), 35000);
  render();
  try {
    const form = new FormData();
    const sourceType = v.sourceBlob?.type || "audio/wav";
    const extension = sourceType.includes("webm")
      ? "webm"
      : sourceType.includes("ogg")
        ? "ogg"
        : sourceType.includes("mp4")
          ? "m4a"
          : "wav";
    v.uploadFile ||= {
      id: crypto.randomUUID(),
      file: new File([extension === "wav" ? v.blob : v.sourceBlob], "voice-note." + extension, {
        type: extension === "wav" ? "audio/wav" : sourceType,
      }),
      kind: "voice",
      offset: 0,
    };
    await uploadChatFile(v.uploadFile, v, (n, phase) => {
      v.uploadStage = phase;
      v.uploaded = n;
      const progress = document.querySelector("#voice-upload-progress");
      if (progress) {
        progress.max = v.uploadFile.file.size;
        progress.value = n;
      }
      const text = document.querySelector("#voice-upload-status");
      if (text)
        text.textContent = phase + " · " + Math.floor((100 * n) / v.uploadFile.file.size) + "%";
    });
    form.append("upload_id", v.uploadFile.upload_id);
    form.append("command_id", v.command_id);
    form.append("caption", v.caption);
    const r = await fetch(
      `/api/patients/${v.patient}/messages/threads/${encodeURIComponent(v.peer)}/voice`,
      {
        method: "POST",
        headers: { "X-CSRF-Token": S.csrf, "X-Expected-Actor": S.user.id },
        body: form,
        signal: v.abort.signal,
      },
    );
    const result = await r.json().catch(() => ({}));
    if (S.care !== c || c.voice !== v || v.cancelled) return;
    if (!r.ok) {
      v.phase = [413, 415, 422].includes(r.status) ? "preview" : "unconfirmed";
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : "Saving is unconfirmed. Check the conversation or retry.",
      );
    }
    disposeCareVoice();
    c.forceLatest = true;
    await loadCareInbox();
    await loadCareThread();
    note("Voice note saved in app.");
  } catch (error) {
    if (S.care === c && c.voice === v && !v.cancelled) {
      if (v.phase === "sending")
        v.phase = [413, 415, 422].includes(error.status) ? "preview" : "unconfirmed";
      c.error = error.message;
      v.error = error.message;
    }
  } finally {
    clearTimeout(timer);
    c.busy = false;
    if (S.care === c && careActive()) render();
  }
}
function bindCareVoice() {
  document.querySelectorAll(".voice-message audio").forEach((a) =>
    a.addEventListener("error", () => {
      a.closest(".voice-message").querySelector(".voice-playback-error").textContent =
        "Audio is unavailable. Refresh the conversation or ask your contact.";
    }),
  );
  if (document.querySelector("#care-voice-record"))
    $("#care-voice-record").onclick = startCareVoice;
  if (document.querySelector("#care-voice-finish"))
    $("#care-voice-finish").onclick = () => {
      const v = S.care.voice;
      if (v?.rec && ["recording", "paused"].includes(v.rec.state)) v.rec.stop();
    };
  if (document.querySelector("#care-record-pause"))
    $("#care-record-pause").onclick = () => {
      const v = S.care.voice;
      if (!v?.rec) return;
      if (v.rec.state === "recording") {
        v.activeMs += Date.now() - v.started;
        v.rec.pause();
        v.stream.getTracks().forEach((t) => (t.enabled = false));
        v.phase = "paused";
        clearTimeout(v.limit);
      } else if (v.rec.state === "paused") {
        v.stream.getTracks().forEach((t) => (t.enabled = true));
        v.rec.resume();
        v.started = Date.now();
        v.phase = "recording";
        v.limit = setTimeout(
          () => {
            if (v.rec.state === "recording") v.rec.stop();
          },
          Math.max(0, 20000 - v.activeMs),
        );
      }
      render();
    };
  if (document.querySelector("#care-voice-upload-pause"))
    $("#care-voice-upload-pause").onclick = () => {
      const v = S.care.voice;
      v.phase = "unconfirmed";
      v.abort?.abort();
      render();
    };
  if (document.querySelector("#care-voice-discard"))
    $("#care-voice-discard").onclick = async () => {
      if (
        S.care.voice?.phase === "unconfirmed" &&
        !confirm(
          "The note may already be saved. Discard this local copy? Check the conversation before recording it again.",
        )
      )
        return;
      const v = S.care.voice;
      if (v?.uploadFile?.upload_id) {
        try {
          await mediaRequest(
            `/patients/${v.patient}/messages/uploads/${v.uploadFile.upload_id}`,
            "DELETE",
          );
        } catch {
          note(
            "A saved note remains in the conversation; unfinished uploads expire automatically.",
          );
        }
      }
      disposeCareVoice();
      render();
    };
  if (document.querySelector("#care-voice-form")) {
    $("#care-voice-form textarea").oninput = (e) => {
      S.care.voice.caption = e.target.value;
    };
    $("#care-voice-form").onsubmit = (e) => {
      e.preventDefault();
      sendCareVoice();
    };
  }
}
window.addEventListener("pagehide", stopCareCapture);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopCareCapture();
    if (careActive() && S.user) render();
  }
});
