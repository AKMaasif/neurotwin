// Shared dated report view. Every response is projected and authorized by the server.
async function loadWeeklyReports() {
  const epoch = (S.reportEpoch = (S.reportEpoch || 0) + 1);
  const pid = S.pid,
    user = S.user.id;
  const clinical = S.user.role === "clinician";
  const query = new URLSearchParams({
    timezone: S.reportZone || "Asia/Dubai",
    audience: clinical ? "clinical" : "family",
  });
  if (S.reportEnd) query.set("end_date", S.reportEnd);
  try {
    const [weekly, history, recipients] = await Promise.all([
      api(`/patients/${pid}/reports/weekly?${query}`),
      api(`/patients/${pid}/reports/snapshots`),
      clinical ? api(`/patients/${pid}/reports/recipients`) : Promise.resolve([]),
    ]);
    if (S.reportEpoch !== epoch || S.pid !== pid || S.user?.id !== user) return;
    S.weekly = weekly;
    S.reportHistory = history;
    S.reportRecipients = recipients;
    S.reportEnd = weekly.end;
    S.reportZone = weekly.timezone;
  } catch (error) {
    if (S.reportEpoch === epoch) {
      S.weekly = null;
      S.reportHistory = [];
    }
    throw error;
  }
}

function reportBars(rows, label) {
  const max = Math.max(1, ...rows.map((r) => r.denominator));
  return ntUi`<div class="report-bars" aria-label="${esc(label)}">${rows
    .map((r) => {
      const done = r.counts.completed,
        other = r.denominator - done;
      return ntUi`<div class="report-bar-row"><strong>${esc(r.date || r.start + " to " + r.end)}</strong><div class="report-bar" aria-hidden="true"><span class="report-confirmed" style="width:${(100 * done) / max}%"></span><span class="report-other" style="width:${(100 * other) / max}%"></span></div><span>${done} reported complete / ${r.denominator} recorded</span></div>`;
    })
    .join("")}</div>`;
}

function reportDetails(r, clinical) {
  if (!clinical && typeof renderMobileReportDetails === "function")
    return renderMobileReportDetails(r);
  return ntUi`<section class="card"><div class="eyebrow">${esc(r.start)} TO ${esc(r.end)} · ${esc(r.timezone)}</div><h2>${r.counts.completed} reported complete <span class="muted">of ${r.denominator} recorded activities</span></h2><p>Activity evidence is not a measure of memory or clinical stability.</p><div class="report-counts">${Object.entries(
    r.counts,
  )
    .filter(([key, value]) => clinical || value > 0 || key === "completed")
    .map(
      ([k, v]) =>
        ntUi`<div><strong>${v}</strong><span>${esc({ completed: ntTr("Reported complete"), deferred: ntTr("Postponed"), skipped: ntTr("Skipped"), help: ntTr("Asked for help"), pending: ntTr("Not yet confirmed"), unconfirmed: ntTr("No confirmation recorded"), unknown: ntTr("Status unavailable") }[k] || k)}</span></div>`,
    )
    .join(
      "",
    )}</div><p>${r.data_quality.dates_without_recorded_activities} dates have no recorded activities. Expected activity count is unavailable.</p><details><summary>How to read these counts</summary>${r.notes.map((n) => ntUi`<p>${esc(n)}</p>`).join("")}<p>${r.data_quality.invalid_activity_dates} activity records have unusable dates.</p></details></section><section class="card"><details ${clinical ? "open" : ""}><summary>Daily activity records</summary><p class="muted">Green: reported complete. Grey: other recorded states. No record is shown as an empty bar.</p>${reportBars(r.daily, "Daily activity counts")}</details></section><section class="card"><details ${clinical ? "open" : ""}><summary>Four-week comparison</summary><p class="muted">Each row has its own recorded denominator. This does not establish improvement or decline.</p>${reportBars(r.trend, "Four-week activity counts")}</details></section><section class="card"><details ${clinical ? "open" : ""}><summary>Recorded actions</summary><p class="muted">${r.timeline_total} actions in this week.${r.timeline_truncated ? ntTr(" Showing the latest 200.") : ""}</p>${
    r.timeline.length
      ? ntUi`<ol class="report-timeline">${[...r.timeline]
          .reverse()
          .map(
            (t) =>
              ntUi`<li><time>${esc(new Date(t.at).toLocaleString("en", { timeZone: r.timezone }))}</time><strong>${esc(t.action.replaceAll(".", " · "))}${t.response ? " · " + esc(t.response) : ""}</strong><span>${esc(t.title)}</span><small>Source: ${esc(t.source_id)}</small></li>`,
          )
          .join("")}</ol>`
      : ntUi("<p>No actions recorded in this interval.</p>")
  }</details></section>${clinical && r.clinical ? ntUi`<section class="card"><h2>Clinical review items</h2><p>${r.clinical.review_items.length} concerns awaiting review. ${r.clinical.plans_requiring_source_review.length} plans need source review.</p>${r.clinical.review_items.map((c) => ntUi`<div class="source"><strong>${esc(c.status)}</strong><p>${esc(c.concern)}</p><small>Source: ${esc(c.source_id)}</small></div>`).join("")}<h3>Research measurements</h3><p class="muted">Unvalidated research inputs, labelled with capture quality. These are not cognitive-health scores.</p>${r.clinical.research_measurements.map((m) => ntUi`<p>${esc(m.protocol || ntTr("Unspecified protocol"))} · ${esc(m.mode || ntTr("Unspecified mode"))} · ${esc(m.quality)} · recorded value ${esc(m.value ?? "unavailable")}<br><small>Source: ${esc(m.source_id)}</small></p>`).join("") || ntUi("<p>No research measurements recorded in this interval.</p>")}<h3>Source facts verified during this week</h3>${r.clinical.verified_source_facts.map((f) => ntUi`<blockquote><strong>${esc(f.label)}</strong><p>${esc(f.quote)}</p><small>${esc(f.source_id)} · v${f.version} · fact ${esc(f.fact_id)}</small></blockquote>`).join("") || ntUi("<p>No verified source facts recorded in this interval.</p>")}</section>` : ""}`;
}

function renderWeeklyReports() {
  const clinical = S.user.role === "clinician";
  const selected = (S.reportHistory || []).find((r) => r.id === S.reportId);
  return ntUi`<h1>${clinical ? ntTr("Weekly evidence & review") : ntTr("Weekly summary")}</h1><p>${clinical ? ntTr("Review dated records and share an approved snapshot with one authorized relative.") : ntTr("A simple view of recorded activities and shared support.")}</p><section class="card"><form id="report-period"><label>Week ending<input name="end_date" type="date" value="${esc(S.reportEnd || "")}" required></label><label>Reporting timezone<select name="timezone">${["Asia/Dubai", "Asia/Colombo", "Europe/London", "America/New_York", "UTC"].map((z) => ntUi`<option ${z === (S.reportZone || "Asia/Dubai") ? "selected" : ""}>${z}</option>`).join("")}</select></label><button ${S.reportBusy ? "disabled" : ""}>Load week</button></form></section>${S.weekly ? ntUi`<p class="muted">Live records updated ${esc(new Date(S.weekly.as_of).toLocaleString(ntIntlLocale()))}.</p>` + reportDetails(S.weekly, clinical) : ntUi('<section class="card"><p>No weekly report loaded.</p><button id="report-retry">Load weekly report</button></section>')}${clinical && S.weekly ? ntUi`<section class="card"><h2>Save a review snapshot</h2><p>Family snapshots contain that relative’s permitted activity and support evidence. Clinical notes, measurements and documents stay in the clinical view.</p><form id="report-create"><label>Audience<select name="target"><option value="">Clinical review only</option>${(S.reportRecipients || []).map((r) => ntUi`<option value="${esc(r.id)}">Family · ${esc(r.name)}</option>`).join("")}</select></label><button ${S.reportBusy ? "disabled" : ""}>Create factual draft</button></form></section>` : ""}<section class="card"><h2>${clinical ? ntTr("Saved snapshots") : ntTr("Care-team shared reports")}</h2><p class="muted">Frozen evidence as recorded at generation time. Later activity may differ. Showing up to 12 recent reports.</p><div class="actions">${(S.reportHistory || []).map((r) => ntUi`<button data-report="${esc(r.id)}" aria-pressed="${r.id === S.reportId}">${esc(r.snapshot.end)} · ${esc(r.status)}<small>${esc(clinical ? ((S.reportRecipients || []).find((p) => p.id === r.snapshot.recipient_id)?.name || ntTr("Clinical review")) + " · " : "")}Saved ${esc(new Date(r.generated_at).toLocaleString(ntIntlLocale()))}</small></button>`).join("") || ntUi("<p>No reports shared yet.</p>")}</div></section>${selected ? ntUi`<section class="card"><h2>Saved ${esc(selected.snapshot.audience)} report · ${esc(selected.status)}</h2><p>Generated ${esc(new Date(selected.generated_at).toLocaleString(ntIntlLocale()))}. ${selected.approved_at ? "Approved " + esc(new Date(selected.approved_at).toLocaleString(ntIntlLocale())) + "." : ntTr("Not shared with family until approved.")}</p><p class="muted">Producer: ${esc(selected.producer)}</p>${selected.summary ? ntUi`<h3>Evidence-selected summary</h3>${selected.summary.observations.map((q) => ntUi`<blockquote>${esc(q.quote)}<br><small>${esc(q.source_id)}</small></blockquote>`).join("")}` : ntUi("<p>Factual snapshot; no AI summary generated.</p>")}${clinical && ["draft", "awaiting_review"].includes(selected.status) ? ntUi`<button id="report-ai" ${S.reportBusy ? "disabled" : ""}>Select summary facts with AI</button><p class="muted">Optional. Only computed facts are sent; every returned quote must match exactly.</p><form id="report-review"><label>Private review note<textarea name="note" maxlength="2000">${esc(S.reportNotes?.[selected.id] ?? selected.review_note ?? "")}</textarea></label><label>Decision<select name="decision"><option value="approve">Approve frozen report</option><option value="reject">Reject report</option></select></label><button class="primary" ${S.reportBusy ? "disabled" : ""}>Confirm review</button></form>` : ""}</section><details class="report-snapshot"><summary>View saved evidence</summary>${reportDetails(selected.snapshot, clinical)}</details>` : ""}`;
}

function bindWeeklyReports() {
  document.querySelectorAll("#report-review, #report-period, #report-create").forEach((f) =>
    f.addEventListener("input", () => {
      S.dirty = true;
    }),
  );
  if ($("#report-review textarea"))
    $("#report-review textarea").addEventListener("input", (e) => {
      S.reportNotes ||= {};
      S.reportNotes[S.reportId] = e.target.value;
    });
  const active = () => S.tab === "report" || S.tab === "weekly";
  const run = async (fn) => {
    if (S.reportBusy) return;
    S.reportBusy = true;
    const user = S.user.id;
    try {
      await fn();
      S.dirty = Boolean(S.reportNotes?.[S.reportId]);
    } catch (e) {
      note(e.message);
    } finally {
      S.reportBusy = false;
      if (S.user?.id === user && active()) render();
    }
  };
  const reload = () => run(loadWeeklyReports);
  if ($("#report-retry")) $("#report-retry").onclick = reload;
  if ($("#report-period"))
    $("#report-period").onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      S.reportEnd = f.get("end_date");
      S.reportZone = f.get("timezone");
      S.reportId = null;
      reload();
    };
  document.querySelectorAll("[data-report]").forEach(
    (b) =>
      (b.onclick = () => {
        if (S.dirty && !confirm("Discard unsaved review note?")) return;
        S.dirty = false;
        S.reportId = b.dataset.report;
        render();
      }),
  );
  if ($("#report-create"))
    $("#report-create").onsubmit = (e) => {
      e.preventDefault();
      const target = new FormData(e.target).get("target");
      run(async () => {
        const r = await api(`/patients/${S.pid}/reports/snapshots`, "POST", {
          end_date: S.reportEnd,
          timezone: S.reportZone,
          audience: target ? "family" : "clinical",
          recipient_id: target || null,
        });
        S.reportId = r.id;
        await loadWeeklyReports();
        note(ntTr("Snapshot saved for review."));
      });
    };
  const current = () => (S.reportHistory || []).find((r) => r.id === S.reportId);
  if ($("#report-ai"))
    $("#report-ai").onclick = () =>
      run(async () => {
        const r = current();
        await api(`/patients/${S.pid}/reports/snapshots/${r.id}/summarize`, "POST", {
          expected_version: r.version,
        });
        await loadWeeklyReports();
        note(ntTr("Summary facts validated. Human approval is still required."));
      });
  if ($("#report-review"))
    $("#report-review").onsubmit = (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target));
      const r = current();
      run(async () => {
        await api(`/patients/${S.pid}/reports/snapshots/${r.id}/review`, "POST", {
          ...body,
          expected_version: r.version,
        });
        if (S.reportNotes) delete S.reportNotes[r.id];
        await loadWeeklyReports();
        note(ntTr("Report review saved."));
      });
    };
}
