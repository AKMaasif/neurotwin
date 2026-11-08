function renderCareExport() {
  if (
    S.user.role !== "participant" ||
    !S.data.patient.synthetic ||
    !S.data.scopes.includes("summary")
  )
    return "";
  return ntUi`<section class="card care-export"><h2>Download your care summary</h2><p>Save approved plans, linked tasks, help requests involving you and your text-size preference, within your current permissions.</p><p>Messages, attachments, documents, companion memory and private clinical records are excluded. The file lists its exact scope. Keep downloaded information private and share it deliberately.</p><button type="button" data-care-export>Download care summary (JSON)</button><p data-care-export-status role="status" aria-live="polite"></p></section>`;
}

function bindCareExport() {
  const panel = document.querySelector(".care-export");
  if (!panel) return;
  const pid = S.pid,
    actor = S.user.id,
    epoch = S.workspaceEpoch;
  const button = panel.querySelector("[data-care-export]"),
    status = panel.querySelector("[data-care-export-status]");
  const current = () =>
    panel.isConnected && S.pid === pid && S.user?.id === actor && S.workspaceEpoch === epoch;
  let busy = false;
  button.onclick = async () => {
    if (busy || !current()) return;
    if (
      !confirm(
        ntText`Download a care summary for ${S.data.patient.name}? It may contain private information. Keep the file secure; downloaded copies cannot be recalled.`,
      )
    )
      return;
    busy = true;
    S.careExportBusy = true;
    button.disabled = true;
    status.textContent = "Preparing your permitted care summary…";
    try {
      const data = await api(`/patients/${encodeURIComponent(pid)}/care-summary/export`, "POST");
      if (!current()) return;
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "neurotwin-care-summary.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      status.textContent =
        "Download requested. Check your browser downloads. Keep the file private.";
    } catch (error) {
      if (current()) status.textContent = error.message;
    } finally {
      busy = false;
      if (S.pid === pid && S.user?.id === actor && S.workspaceEpoch === epoch)
        S.careExportBusy = false;
      if (current()) button.disabled = false;
    }
  };
}
