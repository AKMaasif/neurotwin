function companionStatus() {
  const labels = {
    idle: "Ready when you are. Nothing is listening in the background.",
    permission: "Waiting for microphone permission…",
    listening: "Listening. Select Finish recording when you are ready.",
    transcribing: "Checking your recording…",
    transcript_ready: "Please check the words below, then select Send.",
    thinking: "Working on your request…",
    speaking: "Reading aloud. You can stop at any time.",
    stopped: "Stopped. No new action was confirmed.",
    error: S.voiceError || "Something interrupted this request. You can type instead.",
  };
  return labels[S.voiceState] || labels.idle;
}
function renderCompanion() {
  const pending = S.pendingAction,
    guide = S.guide;
  return `<h1>Your companion</h1>${companionFigure()}<div class="voice-status ${S.voiceState === "error" ? "error" : ""}" role="status" aria-live="polite" aria-atomic="true"><span class="status-dot ${S.recording ? "listening" : ""}" aria-hidden="true"></span><span id="voiceStatusText">${esc(companionStatus())}</span></div><form id="chat"><label>How can I help?<input name="text" id="chatInput" placeholder="Open settings" maxlength="3000" required value="${esc(S.draftText || "")}"></label><div class="actions"><button class="primary" ${S.busy || S.recording ? "disabled" : ""}>Send</button><button type="button" id="voice" ${S.busy ? "disabled" : ""}>${S.recording ? "Finish recording" : "Speak"}</button><button type="button" id="stop">Stop</button>${S.retryText ? '<button type="button" id="retryCompanion">Retry request</button>' : ""}</div></form><div class="companion-shortcuts"><button data-say="what should I do">Guide my next activity</button><button data-say="read my plan">Read my plan</button><button data-say="help request status">Check family help</button></div>${S.chat
    .slice(-2)
    .map((c) => `<div class="chat ${c.role === "user" ? "user" : ""}">${esc(c.text)}</div>`)
    .join("")}${
    S.chat.length > 2
      ? `<details class="chat-history"><summary>Earlier messages</summary>${S.chat
          .slice(0, -2)
          .map((c) => `<div class="chat ${c.role === "user" ? "user" : ""}">${esc(c.text)}</div>`)
          .join("")}</details>`
      : ""
  }${guide ? `<section class="card step-guide"><span class="eyebrow">APPROVED ACTIVITY · STEP ${guide.step_index + 1} OF ${guide.steps.length}</span><h2>${esc(guide.task.title)}</h2><p>${esc(guide.steps[guide.step_index])}</p><div class="actions"><button data-say="repeat this step">Read again</button>${guide.step_index + 1 < guide.steps.length ? '<button class="primary" data-say="next step">Next step</button>' : '<button class="primary" data-say="I finished">I finished</button>'}<button data-say="do this later">Do this later</button></div></section>` : ""}${pending ? `<section class="card confirmation" aria-label="Confirm proposed change"><h2>Confirm this change</h2><p>${esc(pending.explanation)}</p><div class="actions"><button class="primary" id="confirmCompanion">Confirm</button><button id="cancelCompanion">Cancel change</button></div></section>` : ""}<p class="muted">A recording goes to the configured speech provider after you finish it. Review the transcript before sending. Companion recordings are not saved in the app.</p>${S.user.role === "participant" ? `<p class="memory-caption">${S.memory?.enabled ? "Memory on · up to 6 recent turns for 7 days" : "Memory off · this conversation is not saved between sessions"}. <button class="plain" data-tab="settings">Memory settings</button></p>` : ""}${renderCameraAssistance()}`;
}
function renderMemorySettings() {
  if (!S.memory) return "";
  return `<section class="card"><h2>Companion memory</h2><p>Choose what to remember. Family and clinician accounts cannot read this conversation memory.</p><form id="memorySettings"><label class="check-label"><input type="checkbox" name="enabled" ${S.memory.enabled ? "checked" : ""}> Remember my preferences and recent conversations</label><label>Name you prefer<input name="preferred_name" maxlength="60" value="${esc(S.memory.preferred_name)}"></label><label>Speaking pace<select name="speech_rate"><option value="normal">Comfortable</option><option value="slow" ${S.memory.speech_rate === "slow" ? "selected" : ""}>Slower</option></select></label><label class="check-label"><input type="checkbox" name="share_with_ai" ${S.memory.share_with_ai ? "checked" : ""}> Allow AI to use remembered messages to understand future requests</label><p class="muted">Off by default. At most 6 text exchanges are kept for 7 days; expired entries are removed when memory is next accessed. Raw audio is not saved. Current requests may use the configured AI even when memory is off.</p><button class="primary">Save memory choices</button></form><div class="actions"><button id="exportMemory">Download my companion memory</button><button id="forgetMemory">Forget conversations and preferences</button></div><p class="muted">The download contains retained companion text and preferences only. It may contain private information. Forgetting clears app memory, not previously downloaded files, care messages, audit records or provider retention.</p></section>`;
}
function setVoiceState(state, error = "") {
  S.voiceState = state;
  S.voiceError = error;
  const el = $("#voiceStatusText");
  if (el) el.textContent = companionStatus();
}
function stopCompanion(update = true) {
  S.voiceEpoch = (S.voiceEpoch || 0) + 1;
  S.voiceAbort?.abort();
  S.voiceAbort = null;
  S.cancelRecording = true;
  clearTimeout(S.recordTimer);
  if (S.recorder?.state === "recording") S.recorder.stop();
  S.micStream?.getTracks().forEach((track) => track.stop());
  S.micStream = null;
  window.speechSynthesis?.cancel();
  S.recording = false;
  S.busy = false;
  setVoiceState("stopped");
  if (update && S.data) render();
}
function speakReply(text, rate = "normal") {
  if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
    setVoiceState("idle");
    return;
  }
  const epoch = S.voiceEpoch;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = rate === "slow" ? 0.75 : 0.9;
  utterance.onstart = () => {
    if (epoch === S.voiceEpoch) setVoiceState("speaking");
  };
  utterance.onend = () => {
    if (epoch === S.voiceEpoch) setVoiceState("idle");
  };
  utterance.onerror = (e) => {
    if (epoch === S.voiceEpoch && !["canceled", "interrupted"].includes(e.error))
      setVoiceState("error", "Audio playback is unavailable. You can read the reply above.");
  };
  window.speechSynthesis.speak(utterance);
}
async function send(text, task = null) {
  text = text.trim();
  if (!text || S.busy || S.recording) return;
  stopCompanion(false);
  const epoch = S.voiceEpoch;
  S.busy = true;
  S.pendingAction = null;
  S.retryText = "";
  S.draftText = "";
  if (task) S.guide = null;
  S.chat = [...S.chat, { role: "user", text }].slice(-12);
  setVoiceState("thinking");
  render();
  const abort = new AbortController();
  S.voiceAbort = abort;
  const timer = setTimeout(() => abort.abort(), 35000);
  try {
    const guide = task || S.guide?.task;
    const body = {
      text,
      ...(guide
        ? { task_id: guide.id, task_version: guide.version, step_index: S.guide?.step_index || 0 }
        : {}),
    };
    const r = await api(`/patients/${S.pid}/companion`, "POST", body, abort.signal);
    if (epoch !== S.voiceEpoch) return;
    S.chat = [...S.chat, { role: "bot", text: r.explanation }].slice(-12);
    if (S.memory) S.memory.version = r.memory_version;
    if (r.intent === "stop") {
      S.pendingAction = null;
      S.guide = null;
      stopCompanion();
      return;
    }
    if (r.intent === "navigate" && r.screen !== "none") {
      if (r.screen === "messages") await loadCareMessages();
      if (r.screen === "weekly") await loadWeeklyReports();
      if (epoch !== S.voiceEpoch) return;
      S.tab = r.screen;
    }
    if (r.intent === "prepare_help") {
      S.helpDraft = text.slice(0, 1000);
      S.tab = "support";
    }
    if (r.intent === "coach_task" && r.steps.length) S.guide = r;
    if (["set_text_size", "task_response"].includes(r.intent))
      S.pendingAction = { ...r, command_id: crypto.randomUUID() };
    S.busy = false;
    setVoiceState("idle");
    render();
    speakReply(r.explanation, r.speech_rate);
  } catch (e) {
    if (epoch !== S.voiceEpoch) return;
    S.retryText = text;
    S.draftText = text;
    if (e.message.includes("review") || e.message.includes("changed")) S.guide = null;
    setVoiceState(
      "error",
      e.name === "AbortError"
        ? "The request took too long. Retry or type a shorter request."
        : e.message,
    );
    S.busy = false;
    render();
  } finally {
    clearTimeout(timer);
    if (epoch === S.voiceEpoch) {
      S.busy = false;
      S.voiceAbort = null;
    }
  }
}
async function confirmCompanion() {
  const action = S.pendingAction;
  if (!action || S.busy) return;
  S.busy = true;
  render();
  try {
    if (action.intent === "set_text_size")
      await api(`/patients/${S.pid}/preferences`, "POST", { text_size: action.text_size });
    else
      await api(`/patients/${S.pid}/tasks/${action.task.id}/response`, "POST", {
        command_id: action.command_id,
        expected_version: action.task.version,
        response: action.response,
      });
    S.pendingAction = null;
    S.guide = null;
    S.busy = false;
    await refresh();
    note("Your confirmed change was saved.");
  } catch (e) {
    S.busy = false;
    setVoiceState("error", e.message);
    render();
  }
}
async function recordVoice() {
  if (S.recorder?.state === "recording") {
    S.recorder.stop();
    return;
  }
  if (S.busy) return;
  stopCompanion(false);
  const epoch = S.voiceEpoch;
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    setVoiceState("error", "Recording is not supported here. Please type your request.");
    render();
    return;
  }
  S.busy = true;
  setVoiceState("permission");
  render();
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (epoch !== S.voiceEpoch) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    S.micStream = stream;
    S.cancelRecording = false;
    const rec = new MediaRecorder(stream),
      chunks = [];
    S.recorder = rec;
    rec.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data);
    };
    const fail = () => {
      if (epoch === S.voiceEpoch) {
        stopCompanion(false);
        setVoiceState("error", "Recording was interrupted. Please try again or type.");
        render();
      }
    };
    rec.onerror = fail;
    stream.getTracks().forEach((t) => (t.onended = fail));
    rec.onstop = async () => {
      if (S.recorder === rec) S.recorder = null;
      if (S.micStream === stream) S.micStream = null;
      clearTimeout(S.recordTimer);
      stream.getTracks().forEach((t) => t.stop());
      if (epoch !== S.voiceEpoch || S.cancelRecording) return;
      S.recording = false;
      S.busy = true;
      setVoiceState("transcribing");
      render();
      const abort = new AbortController();
      S.voiceAbort = abort;
      const timer = setTimeout(() => abort.abort(), 35000);
      try {
        const wav = await pcmWav(new Blob(chunks, { type: rec.mimeType }));
        if (epoch !== S.voiceEpoch) return;
        const form = new FormData();
        form.append("audio", wav, "recording.wav");
        const response = await fetch(`/api/patients/${S.pid}/voice/transcribe`, {
          method: "POST",
          headers: { "X-CSRF-Token": S.csrf },
          body: form,
          signal: abort.signal,
        });
        const d = await response.json();
        if (!response.ok)
          throw Error(
            typeof d.detail === "string"
              ? d.detail
              : "Voice unavailable. Please type your request.",
          );
        if (epoch !== S.voiceEpoch) return;
        S.draftText = d.text;
        setVoiceState("transcript_ready");
      } catch (e) {
        if (epoch === S.voiceEpoch)
          setVoiceState(
            "error",
            e.name === "AbortError"
              ? "Voice processing took too long. Please try again or type."
              : e instanceof TypeError
                ? "Connection interrupted. Please retry when you are connected."
                : e.message,
          );
      } finally {
        clearTimeout(timer);
        if (epoch === S.voiceEpoch) {
          S.busy = false;
          S.voiceAbort = null;
          render();
          $("#chatInput")?.focus();
        }
      }
    };
    rec.start();
    S.recording = true;
    S.busy = false;
    setVoiceState("listening");
    render();
    S.recordTimer = setTimeout(() => {
      if (rec.state === "recording") rec.stop();
    }, 20000);
  } catch {
    stream?.getTracks().forEach((t) => t.stop());
    if (epoch !== S.voiceEpoch) return;
    S.busy = false;
    setVoiceState(
      "error",
      "Microphone permission was denied or the device is unavailable. You can type instead.",
    );
    render();
  }
}
function bindCompanion() {
  if ($("#chat"))
    $("#chat").onsubmit = (e) => {
      e.preventDefault();
      send($("#chatInput").value);
    };
  if ($("#chatInput")) $("#chatInput").oninput = (e) => (S.draftText = e.target.value);
  document.querySelectorAll("[data-say]").forEach((b) => {
    b.disabled = S.busy || S.recording;
    b.onclick = () => send(b.dataset.say);
  });
  if ($("#voice")) $("#voice").onclick = recordVoice;
  if ($("#stop")) $("#stop").onclick = () => stopCompanion();
  if ($("#retryCompanion")) $("#retryCompanion").onclick = () => send(S.retryText);
  if ($("#confirmCompanion")) {
    $("#confirmCompanion").disabled = S.busy;
    $("#confirmCompanion").onclick = confirmCompanion;
  }
  if ($("#cancelCompanion"))
    $("#cancelCompanion").onclick = () => {
      S.pendingAction = null;
      stopCompanion();
    };
  if ($("#memorySettings"))
    $("#memorySettings").onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      if (f.has("share_with_ai") && !f.has("enabled")) {
        note("Turn on memory before sharing remembered context.");
        return;
      }
      guard(async () => {
        S.memory = await api(`/patients/${S.pid}/companion/memory`, "POST", {
          expected_version: S.memory.version,
          enabled: f.has("enabled"),
          share_with_ai: f.has("share_with_ai"),
          preferred_name: f.get("preferred_name"),
          speech_rate: f.get("speech_rate"),
        });
        if (!S.memory.enabled) S.chat = [];
        render();
        note("Your memory choices were saved.");
      });
    };
  if ($("#exportMemory"))
    $("#exportMemory").onclick = () =>
      guard(async () => {
        if (
          !confirm(
            "Download your private companion preferences and retained text to this device? Only continue on a device you trust.",
          )
        )
          return;
        const data = await api(`/patients/${S.pid}/companion/memory/export`, "POST");
        const url = URL.createObjectURL(
          new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = "neurotwin-companion-memory.json";
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        note("Companion memory download prepared. Keep the file private.");
      });
  if ($("#forgetMemory"))
    $("#forgetMemory").onclick = () =>
      guard(async () => {
        stopCompanion(false);
        S.memory = await api(`/patients/${S.pid}/companion/memory/forget`, "POST");
        S.chat = [];
        S.draftText = "";
        S.pendingAction = null;
        S.guide = null;
        render();
        note("Conversation memory and preferences were cleared.");
      });
}
window.addEventListener("pagehide", () => stopCompanion(false));
document.addEventListener("visibilitychange", () => {
  if (document.hidden && (S.recording || S.busy || S.voiceState === "speaking")) stopCompanion();
});
