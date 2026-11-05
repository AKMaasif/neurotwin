const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const b = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const p = await b.newPage({ viewport: { width: 1440, height: 1050 } }),
    steps = [];
  try {
    const password = fs
      .readFileSync(".env", "utf8")
      .split(/\r?\n/)
      .find((x) => x.startsWith("DEMO_PASSWORD="))
      .slice(14);
    await p.goto("http://127.0.0.1:8140/dashboard/");
    await p.locator("[name=password]").fill(password);
    await p.getByRole("button", { name: "Sign in", exact: true }).click();
    await p.getByRole("button", { name: "Source verification", exact: true }).click();
    await p.locator("#documentDrop").waitFor();
    await p.evaluate(() => {
      const transfer = new DataTransfer();
      transfer.items.add(
        new File(["Fictional drag-drop appointment support note."], "drop-check.txt", {
          type: "text/plain",
        }),
      );
      transfer.items.add(
        new File(["Fictional unsupported test."], "blocked.exe", {
          type: "application/octet-stream",
        }),
      );
      document
        .querySelector("#documentDrop")
        .dispatchEvent(
          new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer }),
        );
    });
    await p.locator("#documentUpload [name=synthetic_confirmation]").check();
    await p.getByRole("button", { name: "Upload documents", exact: true }).click();
    await p.waitForFunction(() => S.uploadOutcomes?.length === 2);
    const outcomes = await p.evaluate(() => S.uploadOutcomes);
    if (
      !outcomes.some((x) => x.filename === "blocked.exe" && x.status === "rejected") ||
      !outcomes.some((x) => x.filename === "drop-check.txt" && x.document_id)
    )
      throw Error("Per-file outcomes wrong");
    steps.push(
      "Drag-and-drop batch accepted valid text and rejected unsupported file individually",
    );
    await p.evaluate(async () => {
      S.dirty = false;
      const d = S.documents.find((x) => x.payload.filename === "appointment.png");
      await openDocument(d.id);
      S.sourceView = "visuals";
      render();
    });
    const checkbox = p.locator("[data-visual-asset]").first();
    await checkbox.check();
    const aid = await checkbox.getAttribute("data-visual-asset");
    if (!(await p.evaluate((id) => S.visualIds.length === 1 && S.visualIds[0] === id, aid)))
      throw Error("Selection not retained");
    steps.push("Individual visual source selection retained without automatic cloud inference");
    for (const width of [1440, 1024]) {
      await p.setViewportSize({ width, height: 900 });
      if (await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth))
        throw Error("Unexpected horizontal page overflow");
    }
    steps.push("Desktop and tablet document views have no horizontal page overflow");
    await p.screenshot({ path: "test-results/document-selected-visual.png" });
    fs.writeFileSync(
      "test-results/document-ui-checks.json",
      JSON.stringify({ status: "passed", steps }, null, 2),
    );
    console.log(JSON.stringify({ status: "passed", steps }));
  } finally {
    await b.close();
  }
})().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
