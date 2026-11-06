function renderClinicalRoutines() {
  const data = S.routineData || { routines: [], occurrences: [] };
  const templates = rows("task").filter(
    (t) =>
      !t.payload.occurrence_id &&
      rows("plan").some(
        (p) =>
          p.id === t.payload.plan_id &&
          p.status === "approved" &&
          !p.payload.source_review_required,
      ),
  );
  const today = new Date().toISOString().slice(0, 10),
    end = new Date();
  end.setDate(end.getDate() + 30);
  return `<h1>Daily routines and follow-up</h1><p>Propose timing for approved activities. Participants must confirm clinician proposals and choose their own family-sharing rules.</p><section class="card"><h2>Propose a routine</h2><form id="clinicalRoutine"><label>Approved activity<select name="template_id" required>${templates
    .filter((t) => !data.routines.some((r) => r.template_id === t.id))
    .map((t) => `<option value="${t.id}">${esc(t.payload.title)}</option>`)
    .join(
      "",
    )}</select></label><div class="grid"><label>Time zone<input name="timezone" value="Asia/Dubai" required></label><label>Local time<input name="local_time" type="time" value="09:00" required></label><label>Start date<input name="start_date" type="date" value="${today}" required></label><label>End date<input name="end_date" type="date" value="${end.toISOString().slice(0, 10)}" required></label></div><p class="muted">Runs daily across this date range. Quiet hours default to 21:00–07:00 in the selected zone. Family follow-up is off until the participant explicitly allows it.</p><button class="primary" ${templates.some((t) => !data.routines.some((r) => r.template_id === t.id)) ? "" : "disabled"}>Save for participant confirmation</button></form></section><section class="card"><h2>Routine status</h2><div class="table-scroll"><table><thead><tr><th>Activity</th><th>Local time</th><th>Time zone</th><th>State</th><th>Family follow-up</th></tr></thead><tbody>${data.routines.map((r) => `<tr><td>${esc(r.payload.title)}</td><td>${esc(r.payload.local_time)}</td><td>${esc(r.payload.timezone)}</td><td>${esc(r.status.replaceAll("_", " "))}</td><td>${r.payload.family_followup ? "Allowed after " + r.payload.grace_minutes + " min" : "Off"}</td></tr>`).join("") || '<tr><td colspan="5">No routine proposed.</td></tr>'}</tbody></table></div></section><section class="card"><h2>Dated activities</h2><p class="muted">Unconfirmed is not the same as missed. Reminder acknowledgement and accepted family responsibility are separate evidence. A browser request does not prove device display.</p><div class="table-scroll"><table><thead><tr><th>Activity</th><th>Local date</th><th>Scheduled UTC</th><th>Participant state</th><th>Help request</th><th>Reminder evidence</th></tr></thead><tbody>${
    data.occurrences
      .slice(0, 30)
      .map(
        (o) =>
          `<tr><td>${esc(o.task.title)}</td><td>${esc(o.local_date)}</td><td>${esc(new Date(o.scheduled_at).toISOString())}</td><td>${esc(o.status)}</td><td>${esc(o.help_status || "None")}</td><td>${(o.reminder_evidence || []).map((e) => esc(e.kind + ": " + e.state + (e.device_states.length ? " · browser " + e.device_states.join(", ") : ""))).join("<br>") || "Not available in app yet"}</td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="6">The reminder worker has not created dated activities yet.</td></tr>'
  }</tbody></table></div></section>`;
}
function bindClinicalRoutines() {
  if ($("#clinicalRoutine"))
    $("#clinicalRoutine").onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(e.target),
        task = rows("task").find((t) => t.id === f.get("template_id"));
      guard(async () => {
        await api(`/patients/${S.pid}/routines`, "POST", {
          template_id: task.id,
          template_version: task.version,
          timezone: f.get("timezone"),
          local_time: f.get("local_time"),
          start_date: f.get("start_date"),
          end_date: f.get("end_date"),
          weekdays: [0, 1, 2, 3, 4, 5, 6],
        });
        S.dirty = false;
        await refresh();
        note("Proposal saved. The participant must confirm before it runs.");
      });
    };
}
