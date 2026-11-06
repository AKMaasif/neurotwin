// Shared care inbox. Unsent message text remains in session memory only.
function resetCareMessages() {
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
    (Object.values(S.care.drafts).some((t) => t.trim()) || Object.keys(S.care.pending).length > 0)
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
  try {
    const result = await api(
      `/patients/${pid}/messages/threads/${encodeURIComponent(peer)}?${params}`,
    );
    if (S.care !== c || S.pid !== pid || c.peer !== peer || c.epoch !== epoch) return;
    c.thread = result;
    c.before = before;
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
  const c = S.care;
  if (!c) return '<h1>Messages</h1><section class="card">Loading your care circle…</section>';
  const history = document.querySelector(".care-history");
  if (
    !c.forceLatest &&
    history?.dataset.peer === c.peer &&
    history.dataset.page === (c.before || "")
  ) {
    c.scroll = {
      peer: c.peer,
      page: c.before || "",
      top: history.scrollTop,
      bottom: history.scrollHeight - history.clientHeight - history.scrollTop < 60,
    };
  }
  const contact = c.inbox?.contacts.find((p) => p.id === c.peer);
  const messages = c.thread?.messages || [];
  const pending = c.pending[c.peer];
  const unopened = messages.filter((m) => m.recipient_id === S.user.id && !m.opened_at);
  return `<h1>Care-circle messages</h1><p>Speak with the people connected to this patient. Each conversation is private to its two participants.</p><p class="care-notice">This inbox is not monitored for emergencies. For urgent help, use your locally approved assistance route.</p>${c.error ? `<p class="error" role="alert">${esc(c.error)}</p>` : ""}<div class="care-layout ${contact ? "care-selected" : ""}"><section class="card care-contacts"><h2>Your contacts</h2>${c.inbox?.contacts.map((p) => `<button class="care-contact ${p.id === c.peer ? "selected" : ""}" data-care-contact="${esc(p.id)}" aria-pressed="${p.id === c.peer}" ${c.busy ? "disabled" : ""}><strong>${esc(p.name)}</strong><span>${esc(careRole(p.role))}${p.unopened ? ` · ${p.unopened} not opened` : ""}</span></button>`).join("") || "<p>No messaging contacts are currently available.</p>"}<button id="care-refresh" ${c.busy ? "disabled" : ""}>Refresh inbox</button></section><section class="card care-conversation">${contact ? `<button id="care-back" class="care-back" ${c.busy ? "disabled" : ""}>All contacts</button><h2>${esc(contact.name)}</h2><p class="muted">${esc(careRole(contact.role))} · Times use this device’s timezone.</p><div class="actions"><button id="care-latest" ${c.busy ? "disabled" : ""}>Latest messages</button>${c.thread?.next_before ? `<button id="care-older" ${c.busy ? "disabled" : ""}>Older messages</button>` : ""}</div>${c.before ? '<p class="muted">Viewing an older page. New messages are available from Latest messages.</p>' : ""}<ol class="care-history" data-peer="${esc(c.peer)}" data-page="${esc(c.before || "")}" aria-label="Conversation history" tabindex="0">${messages.map((m) => `<li class="care-message ${m.sender_id === S.user.id ? "outgoing" : "incoming"}"><strong>${esc(m.sender_id === S.user.id ? "You" : contact.name)}</strong><p class="care-body">${esc(m.body)}</p><small>${esc(new Date(m.created_at).toLocaleString())}<br>${m.opened_at ? `Opened in app ${esc(new Date(m.opened_at).toLocaleString())}` : "Saved in app · not acknowledged as opened"}</small></li>`).join("") || '<li class="muted">No messages on this page. Write a message below.</li>'}</ol>${unopened.length ? `<button id="care-opened" ${c.busy ? "disabled" : ""}>Confirm messages opened (${unopened.length})</button><p class="muted">This sends an opening acknowledgement, not a claim that you understood or acted on the message.</p>` : ""}<form id="care-compose"><label>Your message<textarea name="body" maxlength="2000" rows="4" required ${pending || c.busy ? "disabled" : ""}>${esc(pending?.body ?? c.drafts[c.peer] ?? "")}</textarea></label><p class="muted">${pending ? "Saving is unconfirmed. Retry sends the same message ID, so a lost response does not create a duplicate." : "Draft text stays in this session until sent. It is not saved for offline delivery."}</p><button class="primary" ${c.busy ? "disabled" : ""}>${pending ? "Retry saving this message" : "Send message"}</button></form><p class="muted">Messages do not change the approved care plan. No SMS, email, call or push notification is sent.</p>` : "<h2>Choose a contact</h2><p>Select a person to open your direct conversation.</p>"}</section></div>`;
}
function bindCareMessages() {
  if (!careActive() || !S.care) return;
  const c = S.care;
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
          c.peer = b.dataset.careContact;
          c.thread = null;
          c.before = null;
          await loadCareThread();
        })),
  );
  if ($("#care-back"))
    $("#care-back").onclick = () => {
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
      const target = c.peer;
      const body = c.pending[target] || {
        command_id: crypto.randomUUID(),
        body: textarea.value.trim(),
      };
      if (!body.body || body.body.length > 2000) {
        note("Write a message of 1 to 2,000 characters before sending.");
        return;
      }
      c.pending[target] = body;
      c.drafts[target] = body.body;
      run(async () => {
        try {
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
        .filter((m) => m.recipient_id === S.user.id && !m.opened_at)
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
}
let carePolling = false;
setInterval(async () => {
  if (
    !S.user ||
    !S.pid ||
    !careActive() ||
    !S.care ||
    S.care.busy ||
    carePolling ||
    document.hidden ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
  )
    return;
  carePolling = true;
  const c = S.care;
  try {
    const changed = await loadCareInbox();
    if (changed && S.care === c) {
      if (c.peer && !c.before) await loadCareThread();
      if (careActive()) render();
    }
  } catch (error) {
    if (S.care === c) {
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
