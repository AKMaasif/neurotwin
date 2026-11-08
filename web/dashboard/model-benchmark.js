function renderModelBenchmark() {
  if (S.user.role !== "clinician" || !S.data.scopes.includes("review")) return "";
  return ntUi`<section class="card model-benchmark"><h2>Source-study ML benchmark</h2><p>This report evaluates original research participants. It does not analyze this patient or validate the mobile adaptation.</p><button type="button" data-model-evaluation>Load evaluated research model</button><p data-model-status role="status"></p><div data-model-content></div></section>`;
}
function bindModelBenchmark() {
  const panel = document.querySelector(".model-benchmark");
  if (!panel) return;
  const pid = S.pid,
    actor = S.user.id,
    epoch = S.workspaceEpoch;
  const current = () =>
    panel.isConnected && S.pid === pid && S.user?.id === actor && S.workspaceEpoch === epoch;
  const button = panel.querySelector("button"),
    status = panel.querySelector("[data-model-status]"),
    content = panel.querySelector("[data-model-content]");
  button.onclick = async () => {
    button.disabled = true;
    try {
      const r = await api(`/patients/${encodeURIComponent(pid)}/research-model`);
      if (!current()) return;
      status.textContent = ntTr("Original-cohort evaluation loaded. Clinical release is blocked.");
      const rows = Object.entries(r.metrics)
        .map(
          ([name, m]) =>
            ntUi`<tr><th scope="row">${esc(name)}</th><td>${m.participants}</td><td>${m.roc_auc.toFixed(3)}</td><td>${m.brier.toFixed(3)}</td><td>${m.balanced_accuracy.toFixed(3)}</td></tr>`,
        )
        .join("");
      content.innerHTML = ntUi`<p><strong>No patient prediction is enabled.</strong></p><p>Training participants: ${r.partitions.train.participants} · Calibration participants: ${r.partitions.validation.participants} · Test participants: ${r.partitions.test.participants}</p><p>Linked patient-partner groups remain in the same partition. Most negative labels are presumed normal, not independently clinically rated.</p><div style="overflow:auto" tabindex="0" role="region" aria-label="Research model comparison"><table><thead><tr><th>Model</th><th>Test participants</th><th>ROC AUC</th><th>Brier score</th><th>Balanced accuracy</th></tr></thead><tbody>${rows}</tbody></table></div><p>Calibration did not improve the held-out Brier score. This small study cannot establish clinical reliability.</p><p>These are cross-sectional English source-study results, not longitudinal decline predictions or Arabic/Gulf validation.</p><p>${esc(r.version)}</p>`;
    } catch (e) {
      if (current()) {
        content.replaceChildren();
        status.textContent = ntTr(e.message);
      }
    } finally {
      if (current()) button.disabled = false;
    }
  };
}
