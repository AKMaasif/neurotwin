const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path");
(async () => {
  const root = path.resolve(__dirname, ".."),
    out = path.join(root, "test-results");
  fs.mkdirSync(out, { recursive: true });
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
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } }),
    errors = [],
    steps = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await page.goto("http://127.0.0.1:8140/dashboard/");
    await page.locator("[name=username]").fill("clinician");
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: "Source verification", exact: true }).click();
    if (!(await page.locator("#sourceIntake [name=title]").isVisible()))
      await page.getByText("Or add a fictional text note", { exact: true }).click();
    await page
      .locator("#sourceIntake [name=title]")
      .fill("Synthetic appointment source " + Date.now());
    await page.locator("#sourceIntake [name=source_date]").fill("2026-11-05");
    await page
      .locator("#sourceIntake [name=text]")
      .fill("Appointment date: 2026-11-18.\nSupport requested: transport assistance.");
    await page.getByRole("button", { name: "Save source", exact: true }).click();
    await page.getByText("Source saved. It has not been verified.", { exact: true }).waitFor();
    steps.push("source text saved with provenance");
    await page.getByRole("button", { name: "Extract candidate facts", exact: true }).click();
    await page.locator("[data-fact]").first().waitFor({ timeout: 45000 });
    steps.push("live Gemini extraction passed source quote/value QA");
    const ids = await page.evaluate(() =>
      S.documents.find((d) => d.id === S.documentId).payload.candidates.map((f) => f.id),
    );
    if (ids.length < 1) throw new Error("Expected at least one synthetic candidate");
    for (const id of ids) {
      const form = page.locator(`[data-fact="${id}"]`);
      await form
        .locator("[name=reason]")
        .fill("Compared with the original fictional appointment note.");
      await form.getByRole("button", { name: "Verify unchanged", exact: true }).click();
      await page
        .getByText("Attributed fact review saved. Linked plan changes still require approval.", {
          exact: true,
        })
        .waitFor();
      await page.waitForFunction(
        (id) =>
          S.documents.find((d) => d.id === S.documentId).payload.candidates.find((f) => f.id === id)
            .status === "verified",
        id,
      );
    }
    steps.push("all extracted candidates verified by authenticated clinician");
    await page.screenshot({ path: path.join(out, "source-verifier-desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.screenshot({ path: path.join(out, "source-verifier-1024.png"), fullPage: true });
    await page.evaluate(async () => {
      const c = await api(`/patients/${S.pid}/concerns`, "POST", {
        command_id: crypto.randomUUID(),
        text: "Synthetic concern: help arranging transport for an appointment.",
      });
      S.caseId = c.id;
      S.tab = "case";
      await refresh();
    });
    await page.getByRole("button", { name: "Prepare source-linked draft", exact: true }).click();
    await page
      .getByText("Draft saved for human review. It has not changed the plan.", { exact: true })
      .waitFor({ timeout: 45000 });
    steps.push("live Muse Spark source-linked draft persisted as awaiting human review");
    await page.screenshot({ path: path.join(out, "evidence-draft-review.png"), fullPage: true });
    if (errors.length) throw new Error(errors.join("; "));
    fs.writeFileSync(
      path.join(out, "source-browser-check.json"),
      JSON.stringify(
        { status: "passed", steps, errors, live_synthetic_calls: 2, clinical_validation: false },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } finally {
    await browser.close();
  }
})();
