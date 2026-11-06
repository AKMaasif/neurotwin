// Shared care inbox. Unsent message text remains in session memory only.
function resetCareMessages() {
  closeCareViewers();
  closeCareFeed();
  pauseCareAudio();
  disposeCareVoice();
  discardFileDrafts();
  document.body.classList.remove("care-chat-page");
  S.care = {
    inbox: null,
    peer: null,
    thread: null,
    before: null,
    busy: false,
    drafts: {},
    pending: {},
    error: "",
    epoch: 0,
  };
}
function careActive() {
  return S.tab === "messages";
}
function hasCareDrafts() {
  return (
    !!S.care &&
    (Boolean(S.care.voice) ||
      Boolean(S.care.batch) ||
      Object.values(S.care.drafts).some((t) => t.trim()) ||
      Object.keys(S.care.pending).length > 0)
  );
}
async function loadCareInbox() {
  const c = S.care,
    pid = S.pid;
  const result = await api(`/patients/${pid}/messages/inbox`);
  if (S.care !== c || S.pid !== pid || !S.user) return false;
  const changed = result.revision !== c.inbox?.revision;
  c.inbox = result;
  if (c.peer && !result.contacts.some((p) => p.id === c.peer)) {
    closeCareViewers();
    pauseCareAudio();
    disposeCareVoice();
    closeCareFeed();
    discardFileDrafts();
    c.thread = null;
    c.peer = null;
    c.before = null;
    c.error = "Contact access changed. That conversation is no longer available.";
    c.epoch++;
  }
  return changed;
}
async function loadCareThread(before = null) {
  const c = S.care,
    pid = S.pid,
    peer = c.peer,
    epoch = ++c.epoch;
  if (!peer) return;
  const params = new URLSearchParams({ limit: "40" });
  if (before) params.set("before", before);
  if (c.query) params.set("q", c.query);
  if (c.kind) params.set("kind", c.kind);
  try {
    const result = await api(
      `/patients/${pid}/messages/threads/${encodeURIComponent(peer)}?${params}`,
    );
    if (S.care !== c || S.pid !== pid || c.peer !== peer || c.epoch !== epoch) return;
    c.thread = result;
    c.before = before;
    if (c.recoveryPeer !== peer) {
      c.recoverable = await api(`/patients/${pid}/messages/threads/${peer}/uploads`);
      if (S.care !== c || c.peer !== peer || c.epoch !== epoch) return;
      c.recoveryPeer = peer;
    }
    const delivered = result.messages
      .filter((m) => m.recipient_id === S.user.id && !m.withdrawn_at && !m.receipt?.delivered_at)
      .map((m) => m.id);
    if (careActive() && !document.hidden && delivered.length)
      await reportCareReceipt(delivered, "delivered");
    startCareFeed(result.conversation.sequence);
    if (
      c.voice?.phase === "unconfirmed" &&
      result.messages.some((m) => m.command_id === c.voice.command_id)
    )
      disposeCareVoice();
    const pending = c.pending[peer];
    if (pending && result.messages.some((m) => m.command_id === pending.command_id)) {
      delete c.pending[peer];
      c.drafts[peer] = "";
    }
  } catch (error) {
    if (S.care === c && c.epoch === epoch) {
      c.thread = null;
      c.error = error.message;
    }
    throw error;
  }
}
async function loadCareMessages() {
  if (!S.care) resetCareMessages();
  const c = S.care;
  c.error = "";
  try {
    await loadCareInbox();
    if (S.care === c) await loadCareThread(c.before);
    if (S.care === c && c.peer)
      c.recoverable = await api(`/patients/${S.pid}/messages/threads/${c.peer}/uploads`);
  } catch (error) {
    if (S.care === c) {
      c.inbox = null;
      c.thread = null;
      c.error = error.message;
    }
  }
}
const careRole = (role) =>
  ({ participant: "Patient", family: "Family", clinician: "Clinician" })[role] || role;
function renderCareMessages() {
  return renderModernCare();
}
function bindCareMessages() {
  if (!careActive() || !S.care) return;
  const c = S.care;
  bindCareVoice();
  const history = document.querySelector(".care-history");
  if (history) {
    const previous = c.scroll;
    history.scrollTop = c.forceLatest
      ? history.scrollHeight
      : previous?.peer === c.peer && previous.page === (c.before || "") && !previous.bottom
        ? previous.top
        : c.before
          ? 0
          : history.scrollHeight;
    c.forceLatest = false;
  }
  const run = async (fn) => {
    if (c.busy) return;
    c.busy = true;
    c.error = "";
    render();
    try {
      await fn();
    } catch (error) {
      if (S.care === c) c.error = error.message;
    } finally {
      c.busy = false;
      if (S.care === c && careActive()) render();
    }
  };
  document.querySelectorAll("[data-care-contact]").forEach(
    (b) =>
      (b.onclick = () =>
        run(async () => {
          if (b.dataset.careContact !== c.peer && !changeCareVoiceContact()) return;
          c.peer = b.dataset.careContact;
          c.thread = null;
          c.before = null;
          await loadCareThread();
        })),
  );
  if ($("#care-back"))
    $("#care-back").onclick = () => {
      if (!changeCareVoiceContact()) return;
      c.peer = null;
      c.thread = null;
      c.before = null;
      c.epoch++;
      render();
    };
  if ($("#care-refresh")) $("#care-refresh").onclick = () => run(loadCareMessages);
  if ($("#care-latest"))
    $("#care-latest").onclick = () =>
      run(async () => {
        c.forceLatest = true;
        c.query = "";
        c.kind = "";
        c.needsLatest = false;
        await loadCareInbox();
        await loadCareThread();
      });
  if ($("#care-older"))
    $("#care-older").onclick = () => run(() => loadCareThread(c.thread.next_before));
  if ($("#care-compose")) {
    const textarea = $("#care-compose textarea");
    textarea.addEventListener("input", () => {
      c.drafts[c.peer] = textarea.value;
    });
    $("#care-compose").onsubmit = (e) => {
      e.preventDefault();
      if (c.batch && !c.batch.approved) {
        sendFileBatch();
        return;
      }
      const target = c.peer;
      const body = c.pending[target] || {
        command_id: crypto.randomUUID(),
        body: textarea.value.trim(),
        reply_to_id: c.reply?.id || null,
      };
      if (!body.body || body.body.length > 2000) {
        note("Write a message of 1 to 2,000 characters before sending.");
        return;
      }
      c.pending[target] = body;
      c.drafts[target] = body.body;
      run(async () => {
        try {
          const prior = await api(
            `/patients/${S.pid}/messages/threads/${encodeURIComponent(target)}/command/${body.command_id}`,
          );
          if (!prior.message)
            await api(
              `/patients/${S.pid}/messages/threads/${encodeURIComponent(target)}`,
              "POST",
              body,
            );
        } catch (error) {
          if (error.status === 422 && S.care === c) delete c.pending[target];
          throw error;
        }
        if (S.care !== c) return;
        delete c.pending[target];
        c.drafts[target] = "";
        c.reply = null;
        c.forceLatest = true;
        await loadCareInbox();
        await loadCareThread();
        note("Message saved in app.");
      });
    };
  }
  if ($("#care-opened"))
    $("#care-opened").onclick = () => {
      const ids = c.thread.messages
        .filter((m) => m.recipient_id === S.user.id && !m.opened_at && !m.withdrawn_at)
        .map((m) => m.id);
      run(async () => {
        await api(
          `/patients/${S.pid}/messages/threads/${encodeURIComponent(c.peer)}/opened`,
          "POST",
          { message_ids: ids },
        );
        await loadCareInbox();
        await loadCareThread(c.before);
        note("Opening acknowledgement saved.");
      });
    };
  bindChatFeatures();
}
let carePolling = false;
setInterval(async () => {
  if (
    !S.user ||
    !S.pid ||
    !careActive() ||
    !S.care ||
    S.care.busy ||
    careVoiceBusy() ||
    careAudioPlaying() ||
    carePolling ||
    document.hidden ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
  )
    return;
  carePolling = true;
  const c = S.care;
  try {
    await flushCareReceipts();
    const changed = await loadCareInbox();
    if ((changed || c.needsSync || (!c.source && c.peer)) && S.care === c) {
      c.needsSync = false;
      if (c.peer && !c.before) await loadCareThread();
      if (careActive()) render();
    }
  } catch (error) {
    if (S.care === c) {
      closeCareFeed();
      c.thread = null;
      c.inbox = null;
      c.error = error.message;
      if (careActive()) render();
    }
  } finally {
    carePolling = false;
  }
}, 5000);
window.addEventListener("beforeunload", (e) => {
  if (hasCareDrafts()) {
    e.preventDefault();
    e.returnValue = "";
  }
});
