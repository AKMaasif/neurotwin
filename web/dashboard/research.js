// Shared secondary panel; it never turns synthetic workflow metadata into a score.
function renderResearchPanel() {
  if (
    !S.data.patient.synthetic ||
    !S.data.scopes.includes("assessment") ||
    !["participant", "clinician"].includes(S.user.role)
  )
    return "";
  return `<details class="card research-panel"><summary>Research workflow · synthetic only</summary><p>This optional software workflow is separate from a medical assessment. No sensor recording or health score is collected.</p><button type="button" data-research-load>Load research sessions</button><p data-research-status role="status" aria-live="polite"></p><div data-research-content></div></details>`;
}

function bindResearchSessions() {
  const panel = document.querySelector(".research-panel");
  if (!panel) return;
  const pid = S.pid,
    actor = S.user.id,
    epoch = S.workspaceEpoch;
  const current = () =>
    panel.isConnected && S.pid === pid && S.user?.id === actor && S.workspaceEpoch === epoch;
  const path = `/patients/${encodeURIComponent(pid)}/research/sessions`;
  const status = panel.querySelector("[data-research-status]");
  const content = panel.querySelector("[data-research-content]");
  const button = panel.querySelector("[data-research-load]");
  let data = null,
    pending = false;
  const run = async (operation) => {
    if (!current() || pending) return;
    pending = true;
    S.researchBusy = true;
    panel.setAttribute("aria-busy", "true");
    panel.querySelectorAll("button").forEach((b) => (b.disabled = true));
    status.textContent = "Working…";
    try {
      await operation();
      if (current()) status.textContent = "Saved records are up to date.";
    } catch (error) {
      if (current()) {
        if ([401, 403].includes(error.status)) {
          data = null;
          content.replaceChildren();
        }
        status.textContent = `${error.message}. Refresh sessions before retrying an uncertain save.`;
      }
    } finally {
      pending = false;
      if (S.pid === pid && S.workspaceEpoch === epoch && S.user?.id === actor)
        S.researchBusy = false;
      if (current()) {
        panel.removeAttribute("aria-busy");
        panel.querySelectorAll("button").forEach((b) => (b.disabled = false));
      }
    }
  };
  const load = async () => {
    const result = await api(path);
    if (!current()) return;
    data = result;
    draw();
  };
  const action = (row, type, extra = {}) =>
    run(async () => {
      await api(`${path}/${encodeURIComponent(row.id)}/transition`, "POST", {
        command_id: crypto.randomUUID(),
        expected_version: row.version,
        action: type,
        ...extra,
      });
      if (current()) await load();
    });
  function draw() {
    const clinician = S.user.role === "clinician";
    button.textContent = "Refresh research sessions";
    const labels = {
      awaiting_consent: "Awaiting your choice",
      active: "Consented · workflow active",
      completed: "Workflow completed",
      interrupted: "Stopped before completion",
      cancelled: "Cancelled",
      withdrawn: "Consent withdrawn",
    };
    content.innerHTML = `${clinician && S.data.scopes.includes("review") ? '<button type="button" data-research-assign>Assign synthetic workflow</button><p>Assignment does not start an assessment or provide consent on the participant’s behalf.</p>' : ""}${data.sessions.length ? data.sessions.map((row) => `<article class="research-session" data-research-session="${esc(row.id)}"><h3>${esc(labels[row.status] || row.status)}</h3><p>Recorded ${esc(new Date(row.created_at).toLocaleString())} · revision ${row.version}</p><p>Protocol ${esc(row.payload.protocol.id)} · version ${esc(row.payload.protocol.version)}</p>${!clinician && row.status === "awaiting_consent" ? `<p>${esc(row.payload.protocol.consent_text)}</p><form data-research-consent><label class="research-choice"><input type="checkbox" name="agree" required> I have read this and choose to take part in the synthetic software workflow.</label><button type="submit">Agree and start workflow</button></form>` : ""}${!clinician && row.status === "active" ? `<form data-research-complete><p>Record workflow quality only. These choices are self-reported and do not measure memory or health.</p><label>Workflow quality<select name="quality" required><option value="">Choose quality</option><option value="usable">Usable software workflow</option><option value="poor">Poor quality</option></select></label><label>How you took part<select name="mode" required><option value="">Choose mode</option><option value="self">By myself</option><option value="assisted">With assistance</option><option value="video">During a video session</option></select></label><label>Device category<select name="device_class" required><option value="">Choose device</option><option value="phone">Phone</option><option value="tablet">Tablet</option><option value="desktop">Computer</option><option value="unknown">Not sure</option></select></label><button type="submit">Save workflow completion</button></form><button type="button" data-research-action="interrupt">Stop before completion</button>` : ""}${!clinician && ["awaiting_consent", "active"].includes(row.status) ? '<button type="button" data-research-action="cancel">Cancel workflow</button>' : ""}${!clinician && ["active", "completed", "interrupted"].includes(row.status) ? '<button type="button" data-research-action="withdraw">Withdraw consent</button>' : ""}${row.payload.capture ? `<p>Declared quality: ${esc(row.payload.capture.quality)} · mode: ${esc(row.payload.capture.mode)} · device: ${esc(row.payload.capture.device_class)}</p>` : ""}${row.status === "withdrawn" ? "<p>No further capture is allowed. Existing metadata and audit records are retained; withdrawal is not deletion.</p>" : ""}<details><summary>Workflow history</summary><ul>${row.payload.events.map((event) => `<li>${esc(event.action)} · ${esc(new Date(event.at).toLocaleString())}</li>`).join("") || "<li>No participant action recorded.</li>"}</ul></details></article>`).join("") : "<p>No synthetic research workflow has been assigned.</p>"}`;
    const assign = content.querySelector("[data-research-assign]");
    if (assign)
      assign.onclick = () =>
        run(async () => {
          await api(path, "POST", {
            command_id: crypto.randomUUID(),
            protocol_id: data.protocol.id,
            protocol_version: data.protocol.version,
          });
          if (current()) await load();
        });
    content.querySelectorAll("[data-research-session]").forEach((article) => {
      const row = data.sessions.find((item) => item.id === article.dataset.researchSession);
      const consent = article.querySelector("[data-research-consent]");
      if (consent)
        consent.onsubmit = (event) => {
          event.preventDefault();
          if (consent.reportValidity())
            action(row, "consent", { consent_version: row.payload.protocol.consent_version });
        };
      const complete = article.querySelector("[data-research-complete]");
      if (complete)
        complete.onsubmit = (event) => {
          event.preventDefault();
          if (complete.reportValidity())
            action(row, "complete", Object.fromEntries(new FormData(complete)));
        };
      article.querySelectorAll("[data-research-action]").forEach(
        (b) =>
          (b.onclick = () => {
            const type = b.dataset.researchAction;
            if (
              type === "withdraw" &&
              !confirm(
                "Withdraw consent? Further capture stops. Existing metadata and audit records will be retained.",
              )
            )
              return;
            action(row, type);
          }),
      );
    });
  }
  button.onclick = () => run(load);
}
