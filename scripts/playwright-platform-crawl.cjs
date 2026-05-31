const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");

const repoRoot = path.resolve(__dirname, "..");
const outDir = path.join(
  repoRoot,
  "frontend-next",
  "research-next",
  "output",
  "playwright",
  "platform-stabilization",
);

const surfaces = [
  {
    name: "research",
    base: "http://localhost:3010",
    routes: ["/", "/signals"],
  },
  {
    name: "livepnl",
    base: "http://localhost:3020",
    routes: ["/", "/trades"],
  },
  {
    name: "admin",
    base: "http://localhost:3030",
    routes: [
      "/war-room",
      "/core-engine",
      "/agents",
      "/positions",
      "/market-watch",
      "/data-pipeline",
      "/compliance",
      "/memory",
      "/settings",
    ],
  },
];

function routeName(surface, route) {
  return `${surface}${route === "/" ? "-home" : route.replaceAll("/", "-")}`.replace(
    /[^a-z0-9-]/gi,
    "_",
  );
}

async function collectRoute(page, surface, route) {
  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];
  const badResponses = [];

  const onConsole = (msg) => {
    if (["error", "warning"].includes(msg.type())) {
      if (msg.type() === "warning" && msg.text().includes("was preloaded using link preload")) {
        return;
      }
      consoleMessages.push({ type: msg.type(), text: msg.text() });
    }
  };
  const onPageError = (error) => pageErrors.push(error.message);
  const onRequestFailed = (request) =>
    {
      const failure = request.failure()?.errorText || "";
      if (failure === "net::ERR_ABORTED" && request.url().includes("_rsc=")) {
        return;
      }
      failedRequests.push({
        url: request.url(),
        method: request.method(),
        failure,
      });
    };
  const onResponse = (response) => {
    const status = response.status();
    const url = response.url();
    if (status >= 400 && !url.includes("/_next/static/webpack/")) {
      badResponses.push({ url, status });
    }
  };

  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  page.on("requestfailed", onRequestFailed);
  page.on("response", onResponse);

  const url = `${surface.base}${route}`;
  const entry = {
    surface: surface.name,
    route,
    url,
    status: null,
    title: "",
    h1: "",
    links: [],
    buttons: [],
    inputs: [],
    consoleMessages,
    pageErrors,
    failedRequests,
    badResponses,
    screenshot: "",
  };

  try {
    const response = await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
    entry.status = response?.status() || null;
    entry.title = await page.title();
    entry.h1 = await page.locator("h1").first().textContent({ timeout: 2000 }).catch(() => "");
    entry.links = await page.locator("a").evaluateAll((nodes) =>
      nodes
        .map((node) => ({ text: (node.textContent || "").trim(), href: node.href }))
        .filter((item) => item.text || item.href)
        .slice(0, 80),
    );
    entry.buttons = await page
      .locator("button")
      .evaluateAll((nodes) =>
        nodes.map((node) => (node.textContent || "").trim()).filter(Boolean).slice(0, 80),
      );
    entry.inputs = await page.locator("input, select, textarea").evaluateAll((nodes) =>
      nodes
        .map((node) => ({
          tag: node.tagName.toLowerCase(),
          name: node.getAttribute("name") || "",
          type: node.getAttribute("type") || "",
          value: node.value || "",
        }))
        .slice(0, 80),
    );

    const screenshot = path.join(outDir, `${routeName(surface.name, route)}.png`);
    await page.screenshot({ path: screenshot, fullPage: true });
    entry.screenshot = screenshot;

    if (surface.name === "research" && route === "/") {
      const search = page.locator('input[name="q"]');
      if (await search.count()) {
        await search.fill("NVDA");
        await page.locator('button[type="submit"]').first().click();
        await page.waitForLoadState("networkidle");
      }
    }

    if (surface.name === "livepnl" && route === "/") {
      await page
        .getByText("Stream: connected")
        .waitFor({ timeout: 5000 })
        .catch(() => {
          entry.pageErrors.push("Live PnL websocket did not reach connected state.");
        });

      for (const label of ["1W", "1M", "3M", "All"]) {
        const button = page.getByRole("button", { name: label });
        if (await button.count()) await button.first().click();
      }
      const details = page.locator("details summary").first();
      if (await details.count()) {
        await details.click();
        await details.click();
      }
    }

    if (surface.name === "livepnl" && route === "/trades") {
      for (const name of ["symbol", "side", "status"]) {
        const select = page.locator(`select[name="${name}"]`);
        if ((await select.count()) && (await select.locator("option").count()) > 1) {
          const value = await select.locator("option").nth(1).getAttribute("value");
          if (value) await select.selectOption(value);
        }
      }
      const apply = page.getByRole("button", { name: "Apply Filters" });
      if (await apply.count()) {
        await apply.first().click();
        await page.waitForLoadState("networkidle");
      }
    }

    if (surface.name === "admin" && route === "/settings") {
      const functionalVerify = page.getByRole("button", { name: "Functional Verify" });
      if (await functionalVerify.count()) {
        await functionalVerify.first().click();
        await page.waitForLoadState("networkidle");
      }
    }
  } catch (error) {
    entry.pageErrors.push(error instanceof Error ? error.message : String(error));
  } finally {
    page.off("console", onConsole);
    page.off("pageerror", onPageError);
    page.off("requestfailed", onRequestFailed);
    page.off("response", onResponse);
  }

  return entry;
}

function hasFailure(entry) {
  return (
    (entry.status && entry.status >= 400) ||
    entry.consoleMessages.length > 0 ||
    entry.pageErrors.length > 0 ||
    entry.failedRequests.length > 0 ||
    entry.badResponses.length > 0
  );
}

async function main() {
  await fs.mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = [];

  try {
    for (const surface of surfaces) {
      for (const route of surface.routes) {
        const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
        const page = await context.newPage();
        results.push(await collectRoute(page, surface, route));
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }

  const summaryPath = path.join(outDir, "crawl-summary.json");
  await fs.writeFile(summaryPath, JSON.stringify(results, null, 2));
  const failures = results.filter(hasFailure);

  console.log(JSON.stringify({ summaryPath, checked: results.length, failures }, null, 2));

  if (failures.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
