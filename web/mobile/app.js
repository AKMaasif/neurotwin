const S = {
  user: null,
  csrf: "",
  pid: null,
  data: null,
  tab: "home",
  chat: [],
  recording: false,
  busy: false,
};
const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
async function api(path, method = "GET", body) {
  const r = await fetch("/api" + path, {
    method,
    headers: { ...(body ? { "Content-Type": "application/json" } : {}), "X-CSRF-Token": S.csrf },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(typeof e.detail === "string" ? e.detail : "Request unavailable");
  }
  return r.json();
}
function note(t) {
  $("#notice").textContent = t;
  $("#notice").style.display = "block";
  clearTimeout(note.timer);
  note.timer = setTimeout(() => ($("#notice").style.display = "none"), 6000);
}
function records(kind) {
  return S.data.records.filter((r) => r.kind === kind);
}
async function refresh() {
  S.data = await api(`/patients/${S.pid}/workspace`);
  const pref = records("preference")[0];
  document.documentElement.classList.toggle("large", pref?.payload.text_size === "large");
  render();
}
function icon(k) {
  const paths = {
    home: "M3 10 12 3l9 7v11H3z M9 21v-8h6v8",
    check: "M9 3h6v3h5v15H4V6h5z M8 13l3 3 5-6",
    companion: "M5 5h14v12H9l-4 4z M8 10h1m6 0h1",
    plan: "M5 3h14v18H5z M8 8h8m-8 5h8m-8 5h5",
    support: "M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M2 21v-3a6 6 0 0 1 12 0v3m4-12v8m-4-4h8",
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="${paths[k] || paths.home}"/></svg>`;
}
function login() {
  $("#app").innerHTML =
    `<main class="login"><div class="eyebrow">NEUROTWIN</div><h1>A little support for your day</h1><p>Sign in to your own workspace.</p><form id="login"><label>Account<select name="username"><option value="participant">Participant (synthetic)</option><option value="family">Family (synthetic)</option></select></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button class="primary">Sign in</button><p class="muted">Local development accounts. Password is stored in the server .env file.</p><p id="error" role="alert"></p></form></main>`;
  $("#login").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const f = new FormData(e.target);
      S.user = await api("/login", "POST", Object.fromEntries(f));
      S.csrf = S.user.csrf;
      await start();
    } catch (x) {
      $("#error").textContent = x.message;
    }
  };
}
function taskCard(t, hero = false) {
  const reviewHold = records("plan").some(
    (p) => p.id === t.payload.plan_id && p.payload.source_review_required,
  );
  return `<section class="card ${hero ? "hero" : ""}"><div class="eyebrow">${esc(t.payload.period)} · ${esc(t.payload.time)}</div><h2>${esc(t.payload.title)}</h2><p class="muted">${t.status === "completed" ? "Confirmed by participant" : esc(t.status === "pending" ? "Not yet confirmed" : t.status)}</p><div class="actions">${reviewHold ? '<p class="error">This task is waiting for source review. Please ask your care team for help.</p>' : ""}${S.data.scopes.includes("respond") && !reviewHold ? `<button class="primary" data-response="completed" data-id="${t.id}">Done</button><button data-response="deferred" data-id="${t.id}">Later</button>` : ""}<button data-coach="${t.id}">Step guide</button></div></section>`;
}
function render() {
  const family = S.user.role === "family";
  const tasks = records("task").filter((t) => t.status !== "superseded");
  const plan = records("plan").find((p) => p.status === "approved");
  let body = "";
  if (S.tab === "home") {
    body = `<h1>${family ? "Care circle overview" : "Hello, " + esc(S.user.name)}</h1><p>${esc(new Intl.DateTimeFormat("en", { dateStyle: "full" }).format(new Date()))}</p>${family ? `<section class="card"><h2>Shared support</h2><p>Task responses are participant reports. No clinical stability estimate is available.</p><button data-tab="support">Open help requests</button></section>` : tasks[0] ? taskCard(tasks.find((t) => t.status === "pending") || tasks[0], true) : '<section class="card">No active task. Your care team can review your plan.</section>'}<section class="card"><h2>Your current plan</h2><p>${esc(plan?.payload.instructions || "No approved plan available.")}</p><p class="muted">Synthetic support plan · ${esc(plan?.payload.signed_by || "Not signed")}</p>${plan?.payload.source_review_required ? '<p class="error">A source was corrected. Your care team needs to review this plan. Please ask for help before acting on affected instructions.</p>' : ""}</section><section class="card"><h2>One thing at a time</h2><div class="actions"><button data-tab="plan">My plan</button><button data-tab="support">Ask for help</button></div></section>`;
  }
  if (S.tab === "plan")
    body = `<h1>${family ? "Shared tasks" : "My plan"}</h1><p>Follow the current approved instructions. Ask for help when you need it.</p>${tasks.map((t) => taskCard(t)).join("")}`;
  if (S.tab === "check")
    body = `<h1>My check</h1><section class="card"><h2>No assessment assigned</h2><p>Research measurements need an approved protocol and suitable device capture. This build does not diagnose cognitive impairment.</p><button data-tab="support">Report a concern</button></section>`;
  if (S.tab === "companion")
    body = `<h1>Your companion</h1><div class="avatar" aria-hidden="true"><div class="face">• •</div></div><p class="muted">${S.recording ? "Recording — select Stop to finish." : "Ready when you are. Nothing is listening in the background."}</p>${S.chat.map((c) => `<div class="chat ${c.role === "user" ? "user" : ""}">${esc(c.text)}</div>`).join("")}<form id="chat"><label>How can I help?<input name="text" id="chatInput" placeholder="Open settings" maxlength="3000" required></label><div class="actions"><button class="primary">Send</button><button type="button" id="voice">${S.recording ? "Stop recording" : "Speak"}</button><button type="button" id="stop">Stop audio</button></div></form>`;
  if (S.tab === "support")
    body = `<h1>Support</h1><section class="card"><h2>Ask for practical help</h2><p>No emergency service is monitored or contacted by this app.</p><form id="help"><label>Recipient<select name="recipient_id"><option value="${family ? "participant" : "family"}">${family ? "Mansoor" : "Fatima"} (granted contact)</option></select></label><label>Your request<textarea name="text" maxlength="1000" required>Please help me prepare transport for my appointment.</textarea></label><button class="primary">Confirm and save request</button></form></section>${records(
      "help",
    )
      .map(
        (h) =>
          `<section class="card"><h2>${esc(h.status)}</h2><p>${esc(h.payload.text)}</p>${h.payload.recipient_id === S.user.id && h.status === "requested" ? `<button data-accept="${h.id}">Accept responsibility</button>` : ""}<p class="muted">Saved in app. Push/SMS is not connected.</p></section>`,
      )
      .join(
        "",
      )}<section class="card"><h2>Tell your care team</h2><form id="concern"><label>Your concern<textarea name="text" maxlength="1500" required></textarea></label><label><input type="checkbox" name="urgent" style="width:auto"> I am reporting a sudden concerning change</label><button>Save for review</button></form><p class="muted">For urgent help, do not wait for an app reply. Use your locally approved assistance route.</p></section>`;
  if (S.tab === "settings")
    body = `<h1>Settings</h1><section class="card"><h2>Reading comfort</h2><button id="size">${document.documentElement.classList.contains("large") ? "Use normal text" : "Use larger text"}</button><button id="contrast">Toggle contrast</button></section><section class="card"><h2>Your session</h2><p>Signed in as ${esc(S.user.name)}. Family access requires its own account.</p><button id="logout">Sign out</button></section>`;
  $("#app").innerHTML =
    `<header><strong>NeuroCompanion</strong><button class="plain" data-tab="settings">Settings</button></header><div class="scope">${esc(S.data.patient.name)} · ${esc(family ? "Authorized relative" : "Participant")}<br><span class="muted">Synthetic development workspace · ${navigator.onLine ? "Server-connected" : "Offline"}</span></div><main>${body}</main><nav aria-label="Main navigation">${[
      ["home", "Home"],
      ["check", "My Check"],
      ["companion", "Companion"],
      ["plan", "My Plan"],
      ["support", "Support"],
    ]
      .map(
        ([key, label]) =>
          `<button data-tab="${key}" class="${S.tab === key ? "active" : ""}" aria-current="${S.tab === key ? "page" : "false"}">${icon(key)}${label}</button>`,
      )
      .join("")}</nav>`;
  bind();
}
function bind() {
  document.querySelectorAll("[data-tab]").forEach(
    (b) =>
      (b.onclick = () => {
        S.tab = b.dataset.tab;
        render();
        window.scrollTo(0, 0);
      }),
  );
  document.querySelectorAll("[data-response]").forEach(
    (b) =>
      (b.onclick = () =>
        guard(async () => {
          const t = records("task").find((t) => t.id === b.dataset.id);
          await api(`/patients/${S.pid}/tasks/${t.id}/response`, "POST", {
            command_id: crypto.randomUUID(),
            expected_version: t.version,
            response: b.dataset.response,
          });
          await refresh();
          note("Your response was saved.");
        })),
  );
  document.querySelectorAll("[data-coach]").forEach(
    (b) =>
      (b.onclick = () => {
        const t = records("task").find((t) => t.id === b.dataset.coach);
        note(t.payload.steps.join(" "));
      }),
  );
  document.querySelectorAll("[data-accept]").forEach(
    (b) =>
      (b.onclick = () =>
        guard(async () => {
          const h = records("help").find((h) => h.id === b.dataset.accept);
          await api(`/patients/${S.pid}/help/${h.id}/accept`, "POST", {
            command_id: crypto.randomUUID(),
            expected_version: h.version,
          });
          await refresh();
          note("Responsibility accepted.");
        })),
  );
  if ($("#help"))
    $("#help").onsubmit = (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target));
      guard(async () => {
        await api(`/patients/${S.pid}/help`, "POST", { ...body, command_id: crypto.randomUUID() });
        await refresh();
        note("Help request saved in app.");
      });
    };
  if ($("#concern"))
    $("#concern").onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      guard(async () => {
        await api(`/patients/${S.pid}/concerns`, "POST", {
          command_id: crypto.randomUUID(),
          text: f.get("text"),
          urgent_reported: f.has("urgent"),
        });
        await refresh();
        note(
          f.has("urgent")
            ? "Concern recorded. Do not wait for this app for urgent assistance."
            : "Concern saved for clinician review.",
        );
      });
    };
  if ($("#chat"))
    $("#chat").onsubmit = (e) => {
      e.preventDefault();
      send($("#chatInput").value);
    };
  if ($("#size"))
    $("#size").onclick = () =>
      guard(async () => {
        await api(`/patients/${S.pid}/preferences`, "POST", {
          text_size: document.documentElement.classList.contains("large") ? "normal" : "large",
        });
        await refresh();
      });
  if ($("#contrast"))
    $("#contrast").onclick = () => document.body.classList.toggle("high-contrast");
  if ($("#logout"))
    $("#logout").onclick = () =>
      guard(async () => {
        await api("/logout", "POST");
        S.user = null;
        S.data = null;
        S.chat = [];
        login();
      });
  if ($("#voice")) $("#voice").onclick = recordVoice;
  if ($("#stop"))
    $("#stop").onclick = () => {
      speechSynthesis.cancel();
      if (S.recorder?.state === "recording") {
        S.cancelRecording = true;
        S.recorder.stop();
      }
    };
}
async function guard(fn) {
  try {
    await fn();
  } catch (e) {
    note(e.message);
  }
}
async function send(text) {
  if (S.busy) return;
  S.busy = true;
  S.chat.push({ role: "user", text });
  render();
  try {
    const r = await api(`/patients/${S.pid}/companion`, "POST", { text });
    S.chat.push({ role: "bot", text: r.explanation });
    if (r.intent === "navigate") {
      if (r.screen !== "none") S.tab = r.screen;
    }
    if (r.intent === "set_text_size") {
      await api(`/patients/${S.pid}/preferences`, "POST", { text_size: r.text_size });
      await refresh();
    }
    if (r.intent === "prepare_help") S.tab = "support";
    render();
    const u = new SpeechSynthesisUtterance(r.explanation);
    u.rate = 0.9;
    speechSynthesis.speak(u);
  } catch (e) {
    note(e.message);
  } finally {
    S.busy = false;
  }
}
async function recordVoice() {
  if (S.recorder?.state === "recording") {
    S.recorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    S.cancelRecording = false;
    const rec = new MediaRecorder(stream),
      chunks = [];
    S.recorder = rec;
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = async () => {
      clearTimeout(S.recordTimer);
      stream.getTracks().forEach((t) => t.stop());
      S.recording = false;
      render();
      if (S.cancelRecording) return;
      const form = new FormData();
      form.append("audio", await pcmWav(new Blob(chunks, { type: rec.mimeType })), "recording.wav");
      await guard(async () => {
        const r = await fetch(`/api/patients/${S.pid}/voice/transcribe`, {
          method: "POST",
          headers: { "X-CSRF-Token": S.csrf },
          body: form,
        });
        if (!r.ok) throw new Error("Voice unavailable. Please type your request.");
        const d = await r.json();
        $("#chatInput").value = d.text;
        note("Check the transcript, then select Send.");
      });
    };
    rec.start();
    S.recording = true;
    render();
    S.recordTimer = setTimeout(() => {
      if (rec.state === "recording") rec.stop();
    }, 20000);
  } catch {
    note("Microphone unavailable. You can type instead.");
  }
}
async function start() {
  const ps = await api("/patients");
  S.pid = ps[0]?.id;
  if (!S.pid) throw new Error("No active workspace grant");
  await refresh();
}
(async () => {
  try {
    S.user = await api("/session");
    S.csrf = S.user.csrf;
    if (S.user.role === "clinician") {
      location.href = "/dashboard/";
      return;
    }
    await start();
  } catch {
    login();
  }
})();

async function pcmWav(blob) {
  const ctx = new AudioContext();
  let decoded;
  try {
    decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
  } finally {
    await ctx.close();
  }
  const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * 24000), 24000),
    src = offline.createBufferSource();
  src.buffer = decoded;
  src.connect(offline.destination);
  src.start();
  const rendered = await offline.startRendering(),
    samples = rendered.getChannelData(0),
    buf = new ArrayBuffer(44 + samples.length * 2),
    v = new DataView(buf);
  const str = (o, s) => {
    for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i));
  };
  str(0, "RIFF");
  v.setUint32(4, 36 + samples.length * 2, true);
  str(8, "WAVE");
  str(12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, 24000, true);
  v.setUint32(28, 48000, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  str(36, "data");
  v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const x = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, x < 0 ? x * 32768 : x * 32767, true);
  }
  return new Blob([buf], { type: "audio/wav" });
}

let revision = null,
  syncing = false;
setInterval(async () => {
  if (
    !S.user ||
    !S.pid ||
    syncing ||
    document.hidden ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
  )
    return;
  syncing = true;
  try {
    const d = await api(`/patients/${S.pid}/changes`);
    if (revision && revision !== d.revision) await refresh();
    revision = d.revision;
  } catch (e) {
    if (e.message === "Sign in required" || e.message === "Access not granted") {
      S.data = null;
      S.user = null;
      login();
      note("Access expired or changed. Sign in again.");
    }
  } finally {
    syncing = false;
  }
}, 5000);
