// Presentation and live reconciliation on top of the compatible care-message controller.
const careRoleLabel = (role) =>
  ({ participant: "Patient", family: "Family", clinician: "Clinician" })[role] || role;
function chatReceiptLabel(m) {
  if (m.withdrawn_at) return "Withdrawn";
  if (m.receipt?.playback_completed_at) return "Playback ended · client reported";
  if (m.receipt?.playback_started_at) return "Playback started · client reported";
  if (m.opened_at) return "Opened in app";
  if (m.receipt?.delivered_at) return "Delivered to recipient session";
  return "Sent · saved in app";
}
function chatText(text) {
  return String(text)
    .split(/(https?:\/\/[^\s<>]+)/g)
    .map((p) => {
      if (!/^https?:\/\//.test(p)) return esc(p);
      try {
        const url = new URL(p);
        return ["http:", "https:"].includes(url.protocol)
          ? `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">${esc(p)}</a>`
          : esc(p);
      } catch {
        return esc(p);
      }
    })
    .join("");
}
function chatTimeline(rows, contact) {
  let date = "",
    divider = false;
  return rows
    .map((m) => {
      const day = new Date(m.created_at).toLocaleDateString(undefined, { dateStyle: "medium" }),
        separator = day !== date ? `<li class="chat-date"><span>${esc(day)}</span></li>` : "";
      date = day;
      const fresh = !divider && m.recipient_id === S.user.id && !m.opened_at && !m.withdrawn_at;
      if (fresh) divider = true;
      const own = m.sender_id === S.user.id,
        withdraw =
          own && !m.withdrawn_at && Date.now() - new Date(m.created_at).getTime() < 86400000;
      return `${separator}${fresh ? '<li class="chat-unread">Not opened</li>' : ""}<li class="care-message ${own ? "outgoing" : "incoming"} ${m.withdrawn_at ? "withdrawn" : ""}" data-message-id="${esc(m.id)}"><strong class="message-author">${esc(own ? "You" : contact.name)}</strong>${m.reply_to ? `<blockquote class="chat-quote"><span>Reply</span>${esc(m.reply_to.body)}</blockquote>` : ""}${m.body ? `<p class="care-body">${chatText(m.body)}</p>` : ""}${chatMessageMedia(m)}<div class="message-footer"><time title="${esc(new Date(m.created_at).toLocaleString())}">${esc(new Date(m.created_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }))}</time><small>${esc(chatReceiptLabel(m))}</small></div>${!m.withdrawn_at ? `<details class="message-actions"><summary aria-label="Message actions">•••</summary><button type="button" data-reply="${esc(m.id)}">Reply</button>${m.body ? `<button type="button" data-copy="${esc(m.id)}">Copy text</button>` : ""}${withdraw ? `<button type="button" data-withdraw="${esc(m.id)}">Withdraw</button>` : ""}</details>` : ""}</li>`;
    })
    .join("");
}
function renderModernCare() {
  const c = S.care;
  if (!c)
    return '<h1>Care-circle messages</h1><section class="card">Loading your care circle…</section>';
  const history = document.querySelector(".care-history");
  if (
    !c.forceLatest &&
    history?.dataset.peer === c.peer &&
    history.dataset.page === (c.before || "")
  )
    c.scroll = {
      peer: c.peer,
      page: c.before || "",
      top: history.scrollTop,
      bottom: history.scrollHeight - history.clientHeight - history.scrollTop < 60,
    };
  const contact = c.inbox?.contacts.find((p) => p.id === c.peer),
    rows = c.thread?.messages || [],
    pending = c.pending[c.peer],
    draft = pending?.body ?? c.drafts[c.peer] ?? "";
  const unopened = rows.filter(
      (m) => m.recipient_id === S.user.id && !m.opened_at && !m.withdrawn_at,
    ),
    batch = c.batch && !c.batch.approved;
  return `<h1>Care-circle messages</h1><p class="care-intro">Private conversations for ${esc(S.data.patient.name)}.</p><p class="care-notice">Unmonitored inbox. For urgent help, use your locally approved assistance route.</p>${c.error ? `<p class="error" role="alert">${esc(c.error)}</p>` : ""}<div class="care-layout ${contact ? "care-selected" : ""}"><section class="card care-contacts"><div class="chat-list-heading"><h2>Your contacts</h2><button type="button" id="care-refresh">Refresh inbox</button></div>${c.inbox?.contacts.map((p) => `<button class="care-contact ${p.id === c.peer ? "selected" : ""}" data-care-contact="${esc(p.id)}" aria-pressed="${p.id === c.peer}"><span class="contact-initial" aria-hidden="true">${esc(p.name.slice(0, 1))}</span><span class="contact-details"><strong>${esc(p.name)} <small>${esc(careRoleLabel(p.role))}</small></strong><span class="contact-preview">${esc(p.last_message?.preview || "Start a conversation")}</span>${p.last_message ? `<small>${esc(new Date(p.last_message.created_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }))}${p.last_message.outgoing ? ` · ${p.last_message.opened ? "Opened" : "Sent"}` : ""}</small>` : ""}</span>${p.unopened ? `<span class="unopened-count" aria-label="${p.unopened} not opened">${p.unopened}</span>` : ""}</button>`).join("") || "<p>No messaging contacts are currently available.</p>"}</section><section class="card care-conversation">${contact ? `<div class="chat-header"><button type="button" id="care-back" class="care-back">All contacts</button><div><h2>${esc(contact.name)}</h2><small>${esc(careRoleLabel(contact.role))} · ${esc(S.data.patient.name)}</small></div><span class="chat-connection" id="care-connection">${esc(c.connection || "Connecting")}</span></div><form id="care-search" class="chat-search"><label><span class="sr-only">Search conversation</span><input name="q" value="${esc(c.query || "")}" placeholder="Search conversation" maxlength="120"></label><label><span class="sr-only">Message type</span><select name="kind"><option value="">All types</option>${["text", "voice", "audio", "image", "video", "document"].map((t) => `<option value="${t}" ${c.kind === t ? "selected" : ""}>${t[0].toUpperCase() + t.slice(1)}</option>`).join("")}</select></label><button>Search</button><button type="button" id="care-latest">Latest messages</button></form><div class="chat-history-controls">${c.thread?.next_before ? '<button type="button" id="care-older">Older messages</button>' : ""}<button type="button" id="care-new-updates" ${c.needsLatest ? "" : "hidden"}>New messages · show latest</button>${c.before ? "<small>Older page</small>" : ""}</div><ol class="care-history" data-peer="${esc(c.peer)}" data-page="${esc(c.before || "")}" aria-label="Conversation history" tabindex="0">${chatTimeline(rows, contact) || '<li class="chat-empty"><strong>A little connection starts here.</strong><p>Write a message, attach a file, or record a voice note.</p></li>'}</ol>${unopened.length ? `<div class="chat-open-bar"><button type="button" id="care-opened">Confirm messages opened (${unopened.length})</button><small>Explicit acknowledgement, not evidence of understanding or action.</small></div>` : ""}${pending ? `<div class="chat-pending" role="status"><span>${esc(pending.body)}</span><small>${c.busy ? "Sending…" : "Saving unconfirmed · retry uses the same message ID"}</small></div>` : ""}${c.reply ? `<div class="composer-reply">Reply: ${esc(c.reply.body || "Attachment")}<button type="button" id="care-clear-reply">Cancel reply</button></div>` : ""}<div class="chat-composer"><form id="care-compose"><label class="composer-text"><span class="sr-only">Your message</span><textarea name="body" maxlength="2000" rows="1" ${!batch ? "required" : ""} ${pending || c.busy ? "disabled" : ""} placeholder="Write a message">${esc(draft)}</textarea></label><div class="composer-buttons"><button type="button" id="care-attach" aria-label="Attach a file" ${c.voice ? "disabled" : ""}>＋ Attach</button><button class="primary" id="care-send" ${c.busy ? "disabled" : ""} ${!draft.trim() && !batch && !pending ? "hidden" : ""}>${pending ? "Retry saving this message" : batch ? "Send attachments" : "Send message"}</button>${!c.voice ? `<button type="button" id="care-voice-record" ${c.busy || pending || c.batch ? "disabled" : ""} ${draft.trim() || c.batch ? "hidden" : ""}>Record voice note</button>` : ""}</div></form>${renderFileDrafts()}${renderCareVoice()}${!c.batch && c.recoverable?.length ? `<details class="chat-recovery"><summary>${c.recoverable.length} unfinished server uploads</summary><p>Reselect matching files to resume. Local file data and draft captions are not retained after refresh.</p>${[...new Set(c.recoverable.map((r) => r.client_message_id))].map((key) => `<button type="button" data-recover-command="${esc(key)}">Resume ${esc(c.recoverable.find((r) => r.client_message_id === key).filename)}</button>`).join("")}</details>` : ""}<small class="composer-policy">Session-only drafts. No offline/background delivery. Messages do not change the approved care plan. No SMS, email, call or push notification is sent.</small></div>` : '<div class="chat-empty"><h2>Choose a contact</h2><p>Your direct conversation is visible only to its two authorized participants.</p></div>'}</section></div>`;
}
function closeCareFeed() {
  S.care?.source?.close();
  if (S.care) S.care.source = null;
}
function startCareFeed(sequence) {
  const c = S.care;
  if (!careActive() || !c?.peer || !window.EventSource) return;
  if (c.source && c.sourcePeer === c.peer) return;
  closeCareFeed();
  c.sourcePeer = c.peer;
  c.lastEvent = sequence;
  c.connection = "Connecting";
  const source = new EventSource(
    `/api/patients/${S.pid}/messages/threads/${encodeURIComponent(c.peer)}/events?after=${sequence}`,
  );
  c.source = source;
  const label = (text) => {
    if (S.care !== c) return;
    c.connection = text;
    const el = document.getElementById("care-connection");
    if (el) el.textContent = text;
  };
  source.onopen = () => {
    label("Live connection");
    flushCareReceipts();
  };
  source.onerror = () => label(navigator.onLine ? "Reconnecting" : "Offline");
  source.addEventListener("care", (event) => {
    if (S.care !== c || c.source !== source || !careActive()) return;
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }
    if (data.sequence <= c.lastEvent) return;
    c.lastEvent = data.sequence;
    c.needsSync = true;
    if (data.type === "message.created") {
      c.needsLatest = true;
      const button = document.getElementById("care-new-updates");
      if (button) button.hidden = false;
    }
    syncCareEvents();
  });
  source.addEventListener("reset", () => {
    if (S.care === c) {
      closeCareFeed();
      c.needsSync = true;
      syncCareEvents();
    }
  });
  source.addEventListener("revoked", () => {
    if (S.care !== c) return;
    closeCareFeed();
    closeCareViewers();
    pauseCareAudio();
    disposeCareVoice();
    discardFileDrafts();
    c.thread = null;
    c.inbox = null;
    c.peer = null;
    c.drafts = {};
    c.pending = {};
    c.playback = {};
    c.recoverable = [];
    c.reply = null;
    c.error = "Messaging access expired or changed. Sign in again or ask your care team.";
    if (careActive()) render();
  });
}
async function syncCareEvents() {
  const c = S.care;
  if (
    !c?.needsSync ||
    carePolling ||
    c.busy ||
    careVoiceBusy() ||
    careAudioPlaying() ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName) ||
    document.hidden ||
    !careActive()
  )
    return;
  carePolling = true;
  c.needsSync = false;
  try {
    await loadCareInbox();
    if (c.peer && !c.before) {
      await loadCareThread();
      c.needsLatest = false;
    }
    if (S.care === c && careActive()) render();
  } catch (error) {
    c.error = error.message;
  } finally {
    carePolling = false;
  }
}
function bindChatFeatures() {
  const c = S.care;
  if (!c || !careActive()) return;
  bindFileComposer();
  bindAudioPlayers();
  const run = async (fn) => {
    try {
      await fn();
      if (S.care === c && careActive()) render();
    } catch (error) {
      note(error.message);
    }
  };
  if ($("#care-search"))
    $("#care-search").onsubmit = (e) => {
      e.preventDefault();
      const data = new FormData(e.target);
      c.query = data.get("q");
      c.kind = data.get("kind");
      run(() => loadCareThread());
    };
  if ($("#care-new-updates")) $("#care-new-updates").onclick = () => $("#care-latest").click();
  if ($("#care-clear-reply"))
    $("#care-clear-reply").onclick = () => {
      c.reply = null;
      render();
    };
  document.querySelectorAll("[data-reply]").forEach(
    (b) =>
      (b.onclick = () => {
        c.reply = c.thread.messages.find((m) => m.id === b.dataset.reply);
        render();
        $("#care-compose textarea")?.focus();
      }),
  );
  document.querySelectorAll("[data-copy]").forEach(
    (b) =>
      (b.onclick = async () => {
        try {
          await navigator.clipboard.writeText(
            c.thread.messages.find((m) => m.id === b.dataset.copy).body,
          );
          note("Text copied.");
        } catch {
          note("Copy is unavailable on this device.");
        }
      }),
  );
  document.querySelectorAll("[data-withdraw]").forEach(
    (b) =>
      (b.onclick = () => {
        if (
          !confirm("Withdraw this message? Original evidence remains under the retention policy.")
        )
          return;
        run(async () => {
          await api(
            `/patients/${S.pid}/messages/threads/${c.peer}/messages/${b.dataset.withdraw}/withdraw`,
            "POST",
          );
          await loadCareInbox();
          await loadCareThread(c.before);
        });
      }),
  );
  document.querySelectorAll("[data-care-contact],#care-back").forEach((button) => {
    const original = button.onclick;
    button.onclick = async (event) => {
      if (c.batch) {
        if (!confirm("Cancel unsent attachments before changing contact?")) return;
        await cancelFileBatch();
      }
      original?.(event);
    };
  });
  if ($("#care-compose textarea")) {
    const input = $("#care-compose textarea"),
      original = input.oninput;
    const resize = () => {
      input.style.height = "auto";
      input.style.height = Math.min(128, Math.max(44, input.scrollHeight)) + "px";
    };
    resize();
    input.addEventListener("input", () => {
      original?.({ target: input });
      const send = $("#care-send"),
        record = $("#care-voice-record");
      if (send)
        send.hidden = !input.value.trim() && (!c.batch || c.batch.approved) && !c.pending[c.peer];
      if (record) record.hidden = !!input.value.trim() || !!c.batch;
      resize();
    });
    input.onkeydown = (e) => {
      if (
        e.key === "Enter" &&
        !e.shiftKey &&
        !e.isComposing &&
        !window.matchMedia("(pointer:coarse)").matches
      ) {
        e.preventDefault();
        if (input.value.trim()) $("#care-compose").requestSubmit();
      }
    };
  }
  document.querySelectorAll("[data-recover-command]").forEach(
    (button) =>
      (button.onclick = () => {
        const rows = c.recoverable.filter(
          (r) => r.client_message_id === button.dataset.recoverCommand,
        );
        if (rows.some((r) => r.kind === "voice")) {
          recoverCareVoice(rows[0]);
          return;
        }
        c.resumeCommand = button.dataset.recoverCommand;
        c.attachMenu = true;
        render();
        note("Select the same files to resume this send.");
      }),
  );
}

async function recoverCareVoice(row) {
  const c = S.care,
    peer = c.peer,
    patient = S.pid;
  if (c.voice || c.batch) return;
  if (row.status !== "ready") {
    if (
      confirm(
        "This recording was not fully verified before the page closed. Its local audio is unavailable. Cancel the unfinished upload and record again?",
      )
    ) {
      try {
        await mediaRequest(`/patients/${S.pid}/messages/uploads/${row.id}`, "DELETE");
        await loadCareMessages();
        render();
      } catch (error) {
        note(error.message);
      }
    }
    return;
  }
  try {
    const response = await fetch(`/api/patients/${S.pid}/messages/uploads/${row.id}/preview`, {
      headers: { "X-Expected-Actor": S.user.id },
    });
    if (!response.ok) throw Error("Verified recording is unavailable. Refresh or record again.");
    const blob = await response.blob();
    if (S.care !== c || c.peer !== peer || S.pid !== patient) return;
    c.voice = {
      phase: "preview",
      peer: c.peer,
      patient: S.pid,
      caption: "",
      command_id: row.client_message_id,
      blob,
      url: URL.createObjectURL(blob),
      waveform: row.detail.waveform,
      uploadFile: {
        id: row.client_attachment_id,
        upload_id: row.id,
        sha: row.sha256,
        file: new File([blob], "voice-note.wav", { type: "audio/wav" }),
        kind: "voice",
        offset: row.offset,
      },
    };
    render();
    note(
      "Recording recovered for review. Choose Send explicitly; the earlier caption was not retained.",
    );
  } catch (error) {
    note(error.message);
  }
}

function careSessionChanged() {
  if (typeof stopCompanion === "function") stopCompanion(false);
  resetCareMessages();
  S.user = null;
  S.data = null;
  S.chat = [];
  S.memory = null;
  S.pendingAction = null;
  S.guide = null;
  S.routineData = null;
  S.offlineActions = [];
  S.report = null;
  S.weekly = null;
  S.reportHistory = [];
  S.reportNotes = {};
  S.reportId = null;
  S.reportEpoch = (S.reportEpoch || 0) + 1;
  S.documents = [];
  S.documentDetails = null;
  S.documentId = null;
  S.contacts = [];
  S.draftText = "";
  S.helpDraft = "";
  login();
  note("Session account changed. Sign in again.");
}
const careSessionChannel = window.BroadcastChannel
  ? new BroadcastChannel("neurotwin-session")
  : null;
function announceCareSessionChange() {
  careSessionChannel?.postMessage({ type: "changed" });
}
if (careSessionChannel)
  careSessionChannel.onmessage = (e) => {
    if (e.data?.type === "changed" && S.user) careSessionChanged();
  };
