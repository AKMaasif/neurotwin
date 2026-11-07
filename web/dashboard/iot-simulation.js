function renderIotSimulation() {
  if (
    !S.data.patient.synthetic ||
    !S.data.scopes.includes("assessment") ||
    !["participant", "clinician"].includes(S.user.role)
  )
    return "";
  return `<details class="card iot-panel"><summary>Device simulator · no physical hardware</summary><p>Software test events only. Not live monitoring, medical measurements or emergency dispatch.</p><button type="button" data-iot-load>Load device simulation</button><p data-iot-status role="status" aria-live="polite"></p><div data-iot-content></div></details>`;
}

function bindIotSimulation() {
  const panel = document.querySelector(".iot-panel");
  if (!panel) return;
  const pid = S.pid,
    actor = S.user.id,
    epoch = S.workspaceEpoch;
  const current = () =>
    panel.isConnected && S.pid === pid && S.user?.id === actor && S.workspaceEpoch === epoch;
  const path = `/patients/${encodeURIComponent(pid)}/iot-simulation`;
  const content = panel.querySelector("[data-iot-content]"),
    status = panel.querySelector("[data-iot-status]");
  let data,
    offset = 0,
    busy = false;
  const run = async (fn) => {
    if (!current() || busy) return;
    busy = true;
    S.iotBusy = true;
    panel.setAttribute("aria-busy", "true");
    panel.querySelectorAll("button").forEach((b) => (b.disabled = true));
    status.textContent = "Working…";
    try {
      await fn();
      if (current())
        status.textContent = "Saved simulation records loaded. Refresh to see later changes.";
    } catch (error) {
      if (current()) {
        if ([401, 403].includes(error.status)) content.replaceChildren();
        status.textContent = `${error.message}. Refresh before retrying an uncertain save.`;
      }
    } finally {
      busy = false;
      if (S.pid === pid && S.workspaceEpoch === epoch && S.user?.id === actor) S.iotBusy = false;
      if (current()) {
        panel.removeAttribute("aria-busy");
        panel.querySelectorAll("button").forEach((b) => (b.disabled = false));
      }
    }
  };
  const load = async () => {
    const response = await api(`${path}?offset=${offset}`);
    if (!current()) return;
    data = response;
    draw();
  };
  const write = (suffix, body) =>
    run(async () => {
      await api(path + suffix, "POST", { command_id: crypto.randomUUID(), ...body });
      offset = 0;
      if (current()) await load();
    });
  const labels = {
    connected: "Connection / recovery",
    disconnected: "Connection lost",
    reading: "Activity-count reading",
    missing_reading: "Missing reading",
    fault: "Device fault",
    review_signal: "Test signal for manual review",
  };
  function draw() {
    const state = data.state,
      active = state?.status === "enabled",
      clinician = S.user.role === "clinician";
    content.innerHTML = `<p><strong>Simulation permission:</strong> ${active ? "Enabled" : state ? "Withdrawn" : "Not granted"}</p><p><strong>Simulated connection:</strong> ${esc(state?.payload.connection || "unknown")} · last accepted sequence ${state?.payload.sequence || 0}</p>${
      !clinician
        ? active
          ? '<button type="button" data-iot-withdraw>Withdraw simulator permission</button>'
          : `<form data-iot-permission><p>${esc(data.consent_text)}</p><label class="research-choice"><input type="checkbox" required> I choose to allow these software-only test events.</label><button type="submit">Allow device simulation</button></form>`
        : active && S.data.scopes.includes("review")
          ? `<form data-iot-inject><label>Test event<select name="kind">${Object.entries(labels)
              .map(([kind, label]) => `<option value="${kind}">${label}</option>`)
              .join(
                "",
              )}</select></label><label>Activity count (reading only)<input name="value" type="number" min="0" max="1000000" step="1" disabled></label><label>Skip sequence numbers to simulate lost events<input name="gap" type="number" min="0" max="20" step="1" value="0" required></label><button type="submit">Inject labelled test event</button></form>`
          : "<p>Active participant permission and clinician review access are required to inject events.</p>"
    }<h3>Stored test events</h3><p>Showing ${data.events.length ? offset + 1 : 0}–${offset + data.events.length} of ${data.total}. Missing readings remain missing; reconnection does not invent replacement data.</p>${data.events.map((event) => `<article class="research-session" data-iot-event="${esc(event.id)}"><h4>${esc(labels[event.payload.kind])} · simulated</h4><p>Sequence ${event.payload.sequence} · gap ${event.payload.sequence_gap} · ${esc(new Date(event.payload.occurred_at).toLocaleString())}</p>${event.payload.value !== null ? `<p>Simulated activity count: ${event.payload.value} count</p>` : ""}<p>${esc(event.status.replaceAll("_", " "))}${event.payload.review ? " · " + esc(event.payload.review.decision) : ""}</p>${clinician && S.data.scopes.includes("review") && event.status === "awaiting_review" ? '<button type="button" data-iot-review="acknowledged">Acknowledge test signal</button><button type="button" data-iot-review="rejected">Reject test signal</button>' : ""}</article>`).join("") || "<p>No device test events recorded.</p>"}${offset ? '<button type="button" data-iot-page="newer">Newer events</button>' : ""}${offset + data.events.length < data.total ? '<button type="button" data-iot-page="older">Older events</button>' : ""}<p>Simulation reviews are recorded only here. They do not dispatch help, create a clinical concern, or update a treatment plan. Withdrawing permission stops injection and retains existing event and audit records.</p>`;
    const permission = content.querySelector("[data-iot-permission]");
    if (permission)
      permission.onsubmit = (e) => {
        e.preventDefault();
        if (permission.reportValidity())
          write("/permission", {
            expected_version: state?.version || 0,
            enabled: true,
            consent_version: data.consent_version,
          });
      };
    const withdraw = content.querySelector("[data-iot-withdraw]");
    if (withdraw)
      withdraw.onclick = () => {
        if (
          confirm(
            "Stop device simulation? Existing test events and audit records will be retained.",
          )
        )
          write("/permission", { expected_version: state.version, enabled: false });
      };
    const form = content.querySelector("[data-iot-inject]");
    if (form) {
      form.elements.kind.onchange = () => {
        form.elements.value.disabled = form.elements.kind.value !== "reading";
        form.elements.value.required = !form.elements.value.disabled;
      };
      form.onsubmit = (e) => {
        e.preventDefault();
        if (!form.reportValidity()) return;
        const fields = new FormData(form);
        write("/events", {
          expected_version: state.version,
          sequence: state.payload.sequence + Number(fields.get("gap")) + 1,
          occurred_at: new Date().toISOString(),
          kind: fields.get("kind"),
          ...(fields.get("kind") === "reading" ? { value: Number(fields.get("value")) } : {}),
        });
      };
    }
    content.querySelectorAll("[data-iot-review]").forEach(
      (b) =>
        (b.onclick = () => {
          const event = data.events.find(
            (row) => row.id === b.closest("[data-iot-event]").dataset.iotEvent,
          );
          write(`/events/${encodeURIComponent(event.id)}/review`, {
            expected_version: event.version,
            decision: b.dataset.iotReview,
          });
        }),
    );
    content.querySelectorAll("[data-iot-page]").forEach(
      (b) =>
        (b.onclick = () =>
          run(async () => {
            offset = Math.max(0, offset + (b.dataset.iotPage === "older" ? 50 : -50));
            await load();
          })),
    );
  }
  panel.querySelector("[data-iot-load]").onclick = () => run(load);
}
