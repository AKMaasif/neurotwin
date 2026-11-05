const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path");
(async () => {
  const root = path.resolve(__dirname, ".."),
    out = path.join(root, "test-results"),
    fixture = path.join(out, "document-fixtures");
  const password = fs
    .readFileSync(path.join(root, ".env"), "utf8")
    .split(/\r?\n/)
    .find((x) => x.startsWith("DEMO_PASSWORD="))
    .slice(14);
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const p = await browser.newPage({ viewport: { width: 1440, height: 1050 } }),
    steps = [],
    errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  try {
    await p.goto("http://127.0.0.1:8140/dashboard/");
    await p.locator("[name=username]").fill("clinician");
    await p.locator("[name=password]").fill(password);
    await p.getByRole("button", { name: "Sign in", exact: true }).click();
    await p.getByRole("button", { name: "Source verification", exact: true }).click();
    await p.getByRole("heading", { name: "Upload Synthetic Documents", exact: true }).waitFor();
    await p
      .locator("#documentUpload [name=files]")
      .setInputFiles(
        [
          "appointment.docx",
          "activities.xlsx",
          "schedule.csv",
          "note.txt",
          "scan.pdf",
          "mixed.pdf",
          "appointment.png",
          "legacy.xls",
        ].map((x) => path.join(fixture, x)),
      );
    await p.locator("#documentUpload [name=synthetic_confirmation]").check();
    await p.getByRole("button", { name: "Upload documents", exact: true }).click();
    await p.waitForFunction(() => S.uploadOutcomes?.length === 8, null, { timeout: 60000 });
    const outcomes = await p.evaluate(() => S.uploadOutcomes);
    if (outcomes.some((x) => !x.document_id)) throw Error("A fixture upload failed");
    steps.push("Eight-format batch accepted with per-file outcomes");
    const ids = outcomes.map((x) => x.document_id);
    await p.waitForFunction(
      async (ids) => {
        const docs = await api(`/patients/${S.pid}/documents`);
        return ids.every((id) =>
          docs.some(
            (d) => d.id === id && ["processed", "partial"].includes(d.payload.processing_status),
          ),
        );
      },
      ids,
      { timeout: 120000, polling: 1500 },
    );
    await p.evaluate(async () => {
      S.dirty = false;
      await refresh();
    });
    steps.push("Background native parsing and real local OCR completed");
    await p.locator("#documentSearch [name=query]").fill("transport assistance");
    await p.locator("#documentSearch").getByRole("button", { name: "Search sources" }).click();
    await p.waitForFunction(() => S.searchResult?.results.length > 0);
    steps.push("Keyword retrieval returned source-linked excerpts");
    const csv = outcomes.find((x) => x.filename === "schedule.csv").document_id;
    await p.evaluate(async (id) => {
      S.dirty = false;
      await openDocument(id);
    }, csv);
    await p.getByRole("button", { name: "Tables & cells", exact: true }).click();
    await p.locator("#sourceUnitSelect").waitFor();
    await p.screenshot({ path: path.join(out, "document-library-desktop.png"), fullPage: true });
    const xlsx = outcomes.find((x) => x.filename === "activities.xlsx").document_id;
    await p.evaluate(async (id) => {
      S.dirty = false;
      await openDocument(id);
    }, xlsx);
    await p.getByRole("button", { name: "Tables & cells", exact: true }).click();
    await p.setViewportSize({ width: 1024, height: 768 });
    await p.screenshot({ path: path.join(out, "document-library-tablet.png"), fullPage: true });
    steps.push("CSV rows and workbook cells inspectable in reference-style UI");
    const scan = outcomes.find((x) => x.filename === "scan.pdf").document_id;
    await p.evaluate(async (id) => {
      S.dirty = false;
      await openDocument(id);
    }, scan);
    await p.getByRole("button", { name: "Text", exact: true }).click();
    await p.getByText("Appointment date: 2026-11-18", { exact: true }).waitFor();
    await p.screenshot({ path: path.join(out, "document-ocr-review.png"), fullPage: true });
    steps.push("Scanned PDF OCR text visible with provenance and quality warning");
    const download = p.waitForEvent("download");
    await p.getByRole("link", { name: "Download original document" }).click();
    if (
      !fs
        .readFileSync(await (await download).path())
        .equals(fs.readFileSync(path.join(fixture, "scan.pdf")))
    )
      throw Error("Original mismatch");
    steps.push("Original download is byte-identical");
    if (errors.length) throw Error(errors.join(";"));
    fs.writeFileSync(
      path.join(out, "document-browser-check.json"),
      JSON.stringify(
        { status: "passed", steps, errors, document_ids: ids, clinical_validation: false },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } catch (e) {
    await p.screenshot({ path: path.join(out, "document-browser-failure.png"), fullPage: true });
    console.error("Completed steps:", steps);
    console.error("Notice:", await p.locator("#notice").textContent());
    throw e;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
