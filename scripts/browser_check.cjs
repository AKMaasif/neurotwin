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
    .find((s) => s.startsWith("DEMO_PASSWORD="))
    .slice("DEMO_PASSWORD=".length);
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const errors = [],
    steps = [];
  async function pageFor(role, mobile) {
    const context = await browser.newContext({
        viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
      }),
      page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("http://127.0.0.1:8140/" + (mobile ? "mobile/" : "dashboard/"));
    if (mobile) await page.locator("[name=username]").selectOption(role);
    else await page.locator("[name=username]").fill(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page
      .getByText("Synthetic development workspace", { exact: false })
      .or(page.getByText("synthetic data only", { exact: false }))
      .first()
      .waitFor();
    return page;
  }
  try {
    const mobile = await pageFor("participant", true);
    await mobile.screenshot({ path: path.join(out, "mobile-home.png"), fullPage: true });
    await mobile.getByRole("button", { name: "Done", exact: true }).first().click();
    await mobile.getByText("Your response was saved.", { exact: true }).waitFor();
    steps.push("participant task response persisted");
    await mobile.getByRole("button", { name: "Support", exact: true }).click();
    await mobile.getByRole("button", { name: "Confirm and save request", exact: true }).click();
    await mobile.getByText("Help request saved in app.", { exact: true }).waitFor();
    steps.push("help request saved");
    await mobile
      .locator("#concern textarea")
      .fill("Synthetic browser test: trouble organizing appointment details");
    await mobile.getByRole("button", { name: "Save for review", exact: true }).click();
    await mobile.getByText("Concern saved for clinician review.", { exact: true }).waitFor();
    steps.push("concern entered review queue");
    const family = await pageFor("family", true);
    await family.getByRole("button", { name: "Support", exact: true }).click();
    await family
      .getByRole("button", { name: "Accept responsibility", exact: true })
      .first()
      .click();
    await family.getByText("Responsibility accepted.", { exact: true }).waitFor();
    steps.push("independent family account accepted request");
    const dashboard = await pageFor("clinician", false);
    await dashboard.screenshot({ path: path.join(out, "dashboard-overview.png"), fullPage: true });
    await dashboard.getByRole("button", { name: "Work queue", exact: true }).click();
    await dashboard.getByRole("button", { name: "Review evidence", exact: true }).last().click();
    await dashboard
      .locator("[name=rationale]")
      .fill("Reviewed synthetic concern; arrange a supported preparation task.");
    await dashboard.getByRole("button", { name: "Confirm decision", exact: true }).click();
    await dashboard
      .getByText("Decision recorded with your authenticated identity.", { exact: true })
      .waitFor();
    steps.push("assigned clinician reviewed concern");
    await dashboard.getByRole("button", { name: "Patient workspace", exact: true }).click();
    await dashboard.locator("[name=title]").fill("Prepare your appointment details");
    await dashboard
      .locator("[name=instructions]")
      .fill("Check the date and time with your chosen helper.");
    await dashboard.getByRole("button", { name: "Save draft", exact: true }).click();
    await dashboard
      .getByText("Draft saved. It is not active until reviewed and approved.", { exact: true })
      .waitFor();
    dashboard.once("dialog", (d) => d.accept());
    await dashboard
      .getByRole("button", { name: "Review and approve this revision", exact: true })
      .last()
      .click();
    await dashboard
      .getByText(
        "Approved revision saved. Mobile can refresh the current plan. No EHR dispatch occurred.",
        { exact: true },
      )
      .waitFor();
    steps.push("plan approved as exact authenticated revision");
    await mobile.reload();
    await mobile
      .getByRole("heading", { name: "Prepare your appointment details", exact: true })
      .waitFor();
    steps.push("mobile received persisted approved plan on refresh");
    await mobile.getByRole("button", { name: "Companion", exact: true }).click();
    await mobile.locator("#chatInput").fill("Open settings");
    await mobile.getByRole("button", { name: "Send", exact: true }).click();
    await mobile.getByRole("heading", { name: "Settings", exact: true }).waitFor();
    steps.push("typed companion navigated through local allowlist");
    await dashboard.setViewportSize({ width: 1024, height: 768 });
    await dashboard.screenshot({ path: path.join(out, "dashboard-1024.png"), fullPage: true });
    if (errors.length) throw new Error(errors.join("; "));
    fs.writeFileSync(
      path.join(out, "browser-check.json"),
      JSON.stringify(
        { status: "passed", steps, errors, live_model_calls: false, clinical_validation: false },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } finally {
    await browser.close();
  }
})();
