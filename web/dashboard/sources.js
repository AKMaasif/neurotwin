function sourceLabel(source) {
  return Object.entries(source || {})
    .map(
      ([k, v]) =>
        k.replaceAll("_", " ") +
        " " +
        (Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : v),
    )
    .join(" · ");
}
function processingLabel(d) {
  return (d.payload.processing_status || "processed").replaceAll("_", " ");
}
function uploadPanel() {
  return `<section class="card upload-card"><div class="section-heading"><div><span class="eyebrow">DOCUMENT LIBRARY</span><h2>Upload Synthetic Documents</h2><p>Keep original files, source structure and review history together.</p></div><span class="badge">Synthetic only</span></div><form id="documentUpload"><label class="drop-zone" id="documentDrop"><span class="upload-symbol" aria-hidden="true">↑</span><strong>Drop documents here or choose files</strong><span>PDF, DOCX, DOC, XLSX, XLS, CSV, TXT, JPG, PNG, TIFF</span><span class="muted">Up to 8 files · 10 MB each · 40 MB per batch</span><input name="files" type="file" multiple accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.txt,.jpg,.jpeg,.png,.tif,.tiff" aria-label="Choose synthetic documents"></label><div id="selectedFiles" class="selected-files">${(S.uploadFiles || []).map((f) => `<span>${esc(f.name)} · ${(f.size / 1024).toFixed(1)} KB</span>`).join("")}</div><div class="upload-options"><label>Source date<input name="source_date" type="date" required value="${new Date().toISOString().slice(0, 10)}"></label><label class="consent-line"><input name="synthetic_confirmation" type="checkbox" value="true" required> These files are fictional and contain no real patient information.</label></div><div class="actions"><button class="primary" ${S.pdfBusy ? "disabled" : ""}>${S.pdfBusy ? "Uploading…" : "Upload documents"}</button><span id="uploadProgress" role="status" class="muted"></span></div><p class="muted">Native parsing and OCR run locally in the background. Cloud extraction, visual descriptions and semantic indexing run only when requested.</p></form>${S.uploadOutcomes?.length ? `<details class="upload-outcomes"><summary>Batch results · ${S.uploadOutcomes.length} files${S.uploadOutcomes.some((x) => x.status === "rejected") ? " · review rejected files" : ""}</summary><div role="status">${S.uploadOutcomes.map((x) => `<p><strong>${esc(x.filename)}</strong> <span class="badge ${x.status === "rejected" ? "hold" : ""}">${esc(x.status)}</span> ${esc(x.error?.replaceAll("_", " ") || "")}</p>`).join("")}</div></details>` : ""}<details class="manual-source"><summary>Or add a fictional text note</summary><form id="sourceIntake"><label>Document title<input name="title" maxlength="150" required></label><label>Source date<input name="source_date" type="date" required></label><label>Original source text<textarea name="text" maxlength="24000" rows="5" required></textarea></label><button>Save source</button></form></details></section>`;
}
function libraryPanel(docs) {
  return `<section class="card"><div class="section-heading"><h2>Your documents <span class="muted">${docs.length}</span></h2><span class="muted">Processing status is separate from fact verification</span></div><div class="table-scroll document-library-scroll" tabindex="0" aria-label="Document library"><table class="document-list"><thead><tr><th>Document</th><th>Format</th><th>Uploaded</th><th>Processing</th><th></th></tr></thead><tbody>${docs.map((d) => `<tr class="${d.id === S.documentId ? "selected-row" : ""}"><td><strong>${esc(d.payload.filename || d.payload.title)}</strong><div class="muted">${esc(d.payload.file_size ? (d.payload.file_size / 1024).toFixed(1) + " KB" : "Text note")}</div></td><td>${esc((d.payload.format || "pdf").toUpperCase())}</td><td>${esc(new Date(d.created_at).toLocaleDateString())}</td><td><span class="badge ${["partial", "failed"].includes(d.payload.processing_status) ? "hold" : ""}">${esc(processingLabel(d))}</span>${d.payload.stage && ["queued", "processing"].includes(d.payload.processing_status) ? `<div class="muted">${esc(d.payload.stage)}</div>` : ""}</td><td><button data-open-document="${d.id}">Review</button></td></tr>`).join("") || '<tr><td colspan="5">Upload a fictional document to start building the source library.</td></tr>'}</tbody></table></div></section>`;
}
function searchPanel() {
  return `<section class="card"><h2>Find information in documents</h2><p class="muted">Results are source excerpts and unverified interpretations, not medical advice.</p><form id="documentSearch" class="search-form"><label>Question or keywords<input name="query" required minlength="2" maxlength="500" placeholder="For example: transport appointment" value="${esc(S.searchQuery || "")}"></label><label>Search in<select name="document_id"><option value="">All documents</option>${(S.documents || []).map((d) => `<option value="${d.id}">${esc(d.payload.title)}</option>`).join("")}</select></label><label class="consent-line"><input type="checkbox" name="semantic" value="true"> Include semantic search (cloud query embedding; requires an indexed document)</label><button>Search sources</button></form>${S.searchResult ? `<p class="muted">${esc(S.searchResult.mode)} · ${S.searchResult.results.length} results${S.searchResult.warning ? " · " + esc(S.searchResult.warning) : ""}</p>${S.searchResult.results.map((x) => `<article class="search-result"><button class="source-link" data-open-document="${x.document_id}">${esc(x.document_title)}</button><span class="badge ${x.interpretation ? "hold" : ""}">${x.interpretation ? "AI interpretation" : esc(x.kind)}</span><p class="muted">${esc(sourceLabel(x.source))} · revision ${x.document_version}</p><pre>${esc(x.text)}</pre>${x.warnings.length ? '<span class="muted">Source has extraction warnings; inspect before use.</span>' : ""}</article>`).join("") || "<p>No matching excerpts. Try another phrase or inspect a source directly.</p>"}` : ""}</section>`;
}
function unitPreview(doc) {
  const detail = S.documentDetails;
  if (!detail || detail.document.id !== doc.id || !detail.units.length)
    return `<pre>${esc(doc.payload.text || "Processing has not produced readable text yet.")}</pre>`;
  const view = S.sourceView || "text",
    units = detail.units.filter((x) =>
      view === "tables"
        ? ["table", "row"].includes(x.kind)
        : view === "visuals"
          ? ["visual_description", "chart"].includes(x.kind)
          : !["table", "row", "visual_description", "chart"].includes(x.kind),
    );
  return `<div class="source-tabs" role="group" aria-label="Document detail view">${[
    ["text", "Text"],
    ["tables", "Tables & cells"],
    ["visuals", "Images & diagrams"],
    ["logs", "Processing log"],
  ]
    .map(
      ([k, n]) =>
        `<button data-source-view="${k}" class="${view === k ? "primary" : ""}">${n}</button>`,
    )
    .join(
      "",
    )}</div>${view === "logs" ? detail.jobs.map((j) => `<section class="source"><strong>${esc(j.status)} · attempt ${j.attempts}</strong>${j.history.map((h) => `<p>${esc(h.stage)} · ${esc(new Date(h.at).toLocaleTimeString())}</p>`).join("")}${j.error ? `<p class="source-warning">${esc(j.error.replaceAll("_", " "))}</p>` : ""}</section>`).join("") || "<p>No background job for this source.</p>" : `${units.length ? `<label>Source unit<select id="sourceUnitSelect">${units.map((x) => `<option value="${x.id}" ${S.unitId === x.id ? "selected" : ""}>${esc(x.kind + " · " + sourceLabel(x.source))}</option>`).join("")}</select></label>${renderUnit(units.find((x) => x.id === S.unitId) || units[0])}` : '<p class="muted">No extracted units in this view.</p>'}${view === "visuals" ? `<div class="source-assets">${detail.assets.map((a) => `<figure><img loading="lazy" src="/api/patients/${S.pid}/documents/${doc.id}/assets/${a.id}" alt="Original visual source ${esc(sourceLabel(a.source))}"><figcaption class="muted">${esc(sourceLabel(a.source))}</figcaption><label class="consent-line"><input type="checkbox" data-visual-asset="${a.id}" ${S.visualIds?.includes(a.id) ? "checked" : ""}> Select for visual description</label></figure>`).join("")}</div>` : ""}`}`;
}
function renderUnit(u) {
  const d = u.detail;
  return `<p class="muted">${esc(sourceLabel(u.source))} · ${esc(d.method || "native extraction")}${d.recognition_score != null ? " · OCR recognition " + (d.recognition_score * 100).toFixed(1) + "% (not clinical confidence)" : ""}</p>${d.interpretation ? '<p class="source-warning">AI interpretation — not a verified source fact.</p>' : ""}${d.rows ? `<div class="table-scroll"><table>${d.rows.map((row) => `<tr>${row.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</table></div>` : d.values ? `<div class="table-scroll"><table><thead><tr>${d.values.map((_, i) => `<th>${esc(d.cell_references?.[i] || d.headers?.[i] || "Column " + (i + 1))}</th>`).join("")}</tr></thead><tbody><tr>${d.values.map((v) => `<td>${esc(v || "—")}</td>`).join("")}</tr></tbody></table></div>` : `<pre>${esc(u.text)}</pre>`}${d.formulas && Object.keys(d.formulas).length ? `<details><summary>Formulas and cached results</summary><pre>${esc(JSON.stringify(d.formulas, null, 2))}</pre></details>` : ""}${d.merged_ranges?.length ? `<p class="muted">Merged ranges: ${esc(JSON.stringify(d.merged_ranges))}</p>` : ""}`;
}
function candidatePanel(doc) {
  return `<section class="card"><div class="section-heading"><h2>Candidate facts</h2><span class="badge">${doc.payload.candidates.length} candidates</span></div>${doc.payload.candidates.map((f) => `<article class="candidate"><div class="section-heading"><h3>${esc(f.label)}</h3><span class="badge ${f.status === "unverified" ? "hold" : ""}">${esc(f.status)}</span></div><p><strong>${esc(f.value)}</strong> ${esc(f.unit)}</p><blockquote>${esc(f.quote)}</blockquote><p class="muted">${esc(f.source_references?.length ? f.source_references.map(sourceLabel).join("; ") : f.page_numbers?.length ? "PDF page(s): " + f.page_numbers.join(", ") : "Manual text source")}</p><p class="muted">${f.reviewed_by ? "Reviewed by " + esc(f.reviewed_by) : "AI extraction — awaiting human verification"}</p><form data-fact="${f.id}"><div class="fact-fields"><label>Value<input name="value" value="${esc(f.value)}" maxlength="300" required></label><label>Unit<input name="unit" value="${esc(f.unit)}" maxlength="40"></label></div><label>Review reason<input name="reason" minlength="3" maxlength="1000" required></label><div class="actions"><button name="decision" value="verify" class="primary">Verify unchanged</button><button name="decision" value="correct">Save correction</button><button name="decision" value="reject">Reject</button></div></form></article>`).join("") || `<p>No candidate facts yet. Extraction uses a bounded source excerpt and never verifies a fact automatically.</p><button id="extractSource" class="primary" ${S.sourceBusy || !doc.payload.text || ["queued", "processing", "failed"].includes(doc.payload.processing_status) || doc.status === "ocr_required" ? "disabled" : ""}>${S.sourceBusy ? "Extracting…" : "Extract candidate facts"}</button>`}${doc.payload.extraction_scope_limited ? '<p class="source-warning">Candidate extraction covered a bounded excerpt. Search the remaining source units for additional information.</p>' : ""}<p class="muted">Verification does not activate a care plan. Corrections retain attribution and flag linked plans for review.</p></section>`;
}
function renderSourcePage() {
  const docs = S.documents || [],
    doc = docs.find((d) => d.id === S.documentId) || docs[0];
  if (doc) S.documentId = doc.id;
  return `<h1>Source document verification</h1><p>A searchable document library with traceable extraction and human review.</p>${uploadPanel()}${libraryPanel(docs)}${searchPanel()}${doc ? `<section class="patient-context" id="documentDetails"><div><span class="eyebrow">SOURCE RECORD</span><h2>${esc(doc.payload.title)}</h2><span class="muted">Source date ${esc(doc.payload.source_date)} · revision ${doc.version}</span></div><span class="badge hold">${esc(doc.status.replaceAll("_", " "))}</span></section><div class="grid verifier-grid"><section class="card"><div class="section-heading"><h2>Document details</h2><span class="badge">${esc(processingLabel(doc))}</span></div><div class="actions">${doc.payload.has_original_file ? `<a class="button" href="/api/patients/${S.pid}/documents/${doc.id}/file">Download original document</a><button id="reprocessDocument">Retry / reprocess</button>` : ""}<button id="removeDocument">Remove document</button></div>${doc.payload.error ? `<p class="source-warning">${esc(doc.payload.error.replaceAll("_", " "))}. Inspect the original and retry after resolving the issue.</p>` : ""}${(doc.payload.warnings || []).length ? `<details open class="extraction-warnings"><summary>Extraction warnings (${doc.payload.warnings.length})</summary><ul>${doc.payload.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></details>` : ""}<div class="document-paper"><span class="eyebrow">SYNTHETIC SOURCE · NOT A CLINICAL RECORD</span>${unitPreview(doc)}</div><details><summary>Integrity and metadata</summary><p class="muted hash">Original SHA-256 ${esc(doc.payload.file_sha256 || "Text-only source")}</p><p class="muted">${doc.payload.unit_count || S.documentDetails?.units.length || 0} units · ${doc.payload.asset_count || 0} visual assets · ${S.documentDetails?.chunks || 0} searchable chunks. Hashes identify bytes, not clinical correctness.</p></details><div class="actions">${doc.payload.asset_count ? '<button id="describeVisuals">Describe next visuals with AI</button>' : ""}${doc.payload.generation && doc.payload.text ? '<button id="indexEmbeddings">Enable semantic index</button>' : ""}</div><p class="muted">Visual descriptions and embeddings use Gemini with synthetic content. Visual descriptions remain unverified and excluded from clinical fact extraction.</p></section>${candidatePanel(doc)}</div>` : ""}`;
}
async function openDocument(id) {
  if (S.dirty && !confirm("Discard unsaved source edits?")) return;
  S.dirty = false;
  S.documentId = id;
  S.unitId = null;
  S.visualIds = [];
  S.documentDetails = await api(`/patients/${S.pid}/documents/${id}/details`);
  render();
  $("#documentDetails")?.scrollIntoView({ block: "start", behavior: "instant" });
}
function bindSourcePage() {
  const form = $("#documentUpload"),
    input = form?.querySelector("[name=files]"),
    drop = $("#documentDrop");
  const choose = (files) => {
    const a = Array.from(files);
    if (
      a.length > 8 ||
      a.some((f) => f.size > 10 * 1024 * 1024) ||
      a.reduce((n, f) => n + f.size, 0) > 40 * 1024 * 1024
    ) {
      note("Choose up to 8 files, 10 MB each and 40 MB total.");
      return;
    }
    S.uploadFiles = a;
    $("#selectedFiles").innerHTML = a
      .map((f) => `<span>${esc(f.name)} · ${(f.size / 1024).toFixed(1)} KB</span>`)
      .join("");
  };
  if (input) input.onchange = (e) => choose(e.target.files);
  if (drop) {
    drop.ondragover = (e) => {
      e.preventDefault();
      drop.classList.add("dragging");
    };
    drop.ondragleave = () => drop.classList.remove("dragging");
    drop.ondrop = (e) => {
      e.preventDefault();
      drop.classList.remove("dragging");
      choose(e.dataTransfer.files);
      S.dirty = true;
    };
  }
  if (form)
    form.onsubmit = (e) => {
      e.preventDefault();
      if (!S.uploadFiles?.length) {
        note("Choose at least one synthetic document.");
        return;
      }
      const data = new FormData(form);
      data.delete("files");
      S.uploadFiles.forEach((f) => data.append("files", f));
      guard(async () => {
        S.pdfBusy = true;
        form.querySelector("button").disabled = true;
        try {
          const result = await new Promise((resolve, reject) => {
            const x = new XMLHttpRequest();
            x.open("POST", `/api/patients/${S.pid}/documents/upload`);
            x.setRequestHeader("X-CSRF-Token", S.csrf);
            x.upload.onprogress = (e) => {
              if (e.lengthComputable)
                $("#uploadProgress").textContent =
                  `Uploading ${Math.round((e.loaded / e.total) * 100)}%`;
            };
            x.onload = () => {
              let d;
              try {
                d = JSON.parse(x.responseText);
              } catch {
                return reject(Error("Upload response unavailable"));
              }
              if (x.status >= 400)
                return reject(Error(typeof d.detail === "string" ? d.detail : "Upload rejected"));
              resolve(d);
            };
            x.onerror = () =>
              reject(Error("Upload interrupted; check the document list before retrying."));
            x.send(data);
          });
          S.uploadOutcomes = result.outcomes;
          S.documentId = result.outcomes.find((x) => x.document_id)?.document_id || S.documentId;
          S.uploadFiles = [];
          S.dirty = false;
          await refresh();
          note("Batch received. Accepted files are queued for background processing.");
        } finally {
          S.pdfBusy = false;
          render();
        }
      });
    };
  if ($("#sourceIntake"))
    $("#sourceIntake").onsubmit = (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target));
      guard(async () => {
        const d = await api(`/patients/${S.pid}/documents`, "POST", { ...body, synthetic: true });
        S.documentId = d.id;
        S.dirty = false;
        await refresh();
        note("Source saved. It has not been verified.");
      });
    };
  document
    .querySelectorAll("[data-open-document]")
    .forEach((b) => (b.onclick = () => guard(() => openDocument(b.dataset.openDocument))));
  document.querySelectorAll("[data-source-view]").forEach(
    (b) =>
      (b.onclick = () => {
        if (S.dirty && !confirm("Discard unsaved edits before changing the source view?")) return;
        S.dirty = false;
        S.sourceView = b.dataset.sourceView;
        S.unitId = null;
        render();
      }),
  );
  if ($("#sourceUnitSelect"))
    $("#sourceUnitSelect").onchange = (e) => {
      if (S.dirty && !confirm("Discard unsaved edits before changing the source unit?")) {
        render();
        return;
      }
      S.dirty = false;
      S.unitId = e.target.value;
      render();
    };
  if ($("#documentSearch"))
    $("#documentSearch").onsubmit = (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(e.target));
      guard(async () => {
        S.searchQuery = data.query;
        S.searchResult = await api(`/patients/${S.pid}/documents/search`, "POST", {
          query: data.query,
          document_id: data.document_id || null,
          semantic: data.semantic === "true",
        });
        S.dirty = false;
        render();
      });
    };
  document.querySelectorAll("[data-visual-asset]").forEach(
    (el) =>
      (el.onchange = () => {
        const ids = Array.from(document.querySelectorAll("[data-visual-asset]:checked")).map(
          (x) => x.dataset.visualAsset,
        );
        if (ids.length > 3) {
          el.checked = false;
          note("Select up to 3 visuals per request.");
          return;
        }
        S.visualIds = ids;
      }),
  );
  const current = () => S.documents.find((d) => d.id === S.documentId);
  for (const [id, route, question] of [
    [
      "reprocessDocument",
      "reprocess",
      "Reprocess the original? Existing extracted candidates and search indexes will be replaced; linked plans will require review.",
    ],
    [
      "removeDocument",
      "remove",
      "Remove the original file, extracted content and indexes? Linked plans will require review.",
    ],
    [
      "describeVisuals",
      "visuals",
      "Send up to 3 synthetic visual assets to Gemini? Descriptions will remain unverified interpretations.",
    ],
    [
      "indexEmbeddings",
      "embeddings",
      "Send synthetic source chunks to Gemini to enable semantic search? Keyword search is already available.",
    ],
  ])
    if ($("#" + id))
      $("#" + id).onclick = () => {
        if (!confirm(question)) return;
        guard(async () => {
          S.sourceBusy = true;
          const d = current(),
            body = { expected_version: d.version };
          if (route === "visuals" && S.visualIds?.length) body.asset_ids = S.visualIds;
          render();
          try {
            await api(`/patients/${S.pid}/documents/${d.id}/${route}`, "POST", body);
            S.visualIds = [];
            S.dirty = false;
            S.searchResult = null;
            await refresh();
            note(
              route === "remove"
                ? "Document removed."
                : route === "reprocess"
                  ? "Reprocessing queued."
                  : "Document enrichment saved.",
            );
          } finally {
            S.sourceBusy = false;
            render();
          }
        });
      };
  if ($("#extractSource"))
    $("#extractSource").onclick = () =>
      guard(async () => {
        const d = current();
        S.sourceBusy = true;
        render();
        try {
          await api(`/patients/${S.pid}/documents/${d.id}/extract`, "POST", {
            expected_version: d.version,
          });
          await refresh();
          note("Candidates extracted. Review each against the source.");
        } finally {
          S.sourceBusy = false;
          render();
        }
      });
  document.querySelectorAll("[data-fact]").forEach(
    (form) =>
      (form.onsubmit = (e) => {
        e.preventDefault();
        const values = Object.fromEntries(new FormData(form)),
          decision = e.submitter.value,
          d = current(),
          f = d.payload.candidates.find((x) => x.id === form.dataset.fact);
        if (decision === "verify" && (values.value !== f.value || values.unit !== f.unit)) {
          note("Choose Save correction when changing a value or unit.");
          return;
        }
        guard(async () => {
          await api(`/patients/${S.pid}/documents/${d.id}/candidates/${f.id}/review`, "POST", {
            expected_version: d.version,
            decision,
            value: decision === "correct" ? values.value : null,
            unit: decision === "correct" ? values.unit : null,
            reason: values.reason,
          });
          S.dirty = false;
          await refresh();
          note("Attributed fact review saved. Linked plan changes still require approval.");
        });
      }),
  );
}

function renderEvidenceDrafts(caseId) {
  const drafts = rows("draft").filter((d) => d.payload.case_id === caseId);
  return `<section class="card"><div class="section-heading"><div><h2>Evidence preparation</h2><p class="muted">Muse Spark drafts; source checks run before saving. Clinical meaning still needs your review.</p></div><button id="generateDraft" ${S.draftBusy ? "disabled" : ""}>${S.draftBusy ? "Preparing draft…" : "Prepare source-linked draft"}</button></div>${drafts.map((d) => `<article class="candidate"><span class="badge hold">${esc(d.status.replaceAll("_", " "))}</span><p class="muted">Producer ${esc(d.payload.producer)} · ${esc(d.payload.model)}</p>${d.payload.draft.items.map((i) => `<p>${esc(i.observation)}<br>${renderDraftSource(i.source_id)}</p>`).join("")}${d.payload.source_review_required ? '<p class="source-warning">A linked source changed. This draft is historical and requires renewed review.</p>' : ""}<h3>Missing information</h3><ul>${d.payload.draft.missing_information.map((x) => `<li>${esc(x)}</li>`).join("") || "<li>No additional item identified by the model.</li>"}</ul><p class="muted">${esc(d.payload.qa)}</p></article>`).join("") || "<p>No AI draft saved. The original evidence can be reviewed directly.</p>"}</section>`;
}

function bindEvidenceDraft() {
  document.querySelectorAll("[data-source]").forEach(
    (b) =>
      (b.onclick = () => {
        if (S.dirty && !confirm("Discard unsaved review edits?")) return;
        S.dirty = false;
        S.documentId = b.dataset.source;
        S.tab = "sources";
        render();
      }),
  );
  if ($("#generateDraft"))
    $("#generateDraft").onclick = () => {
      if (S.dirty && !confirm("Discard unsaved review edits before preparing a draft?")) return;
      S.dirty = false;
      guard(async () => {
        S.draftBusy = true;
        render();
        try {
          await api(`/patients/${S.pid}/cases/${S.caseId}/evidence-draft`, "POST");
          await refresh();
          note("Draft saved for human review. It has not changed the plan.");
        } finally {
          S.draftBusy = false;
          render();
        }
      });
    };
}

function renderDraftSource(id) {
  const doc = (S.documents || []).find((d) => d.id === id.split(":")[0]);
  return doc
    ? `<button class="source-link" data-source="${doc.id}">Source: ${esc(doc.payload.title)}</button>`
    : '<span class="muted">Source: attributed concern above</span>';
}
