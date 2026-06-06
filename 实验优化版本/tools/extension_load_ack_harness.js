const fs = require("fs");
const path = require("path");

const PLAYWRIGHT_ENTRY = "E:\\Openclaw\\runtime\\node\\node_modules\\playwright\\index.js";
const { chromium } = require(PLAYWRIGHT_ENTRY);

const ROOT = path.resolve(__dirname, "..");
const EXTENSION_ROOT = path.join(ROOT, "browser_extension");
const MANIFEST_PATH = path.join(EXTENSION_ROOT, "manifest.json");
const ACK_RUNS_DIR = path.join(ROOT, "reports", "extension-load-ack");
const PROTON_SIGNUP_URL = "https://account.proton.me/mail/signup";
const PROTON_ROUTE = "https://account.proton.me/**";

const MOCK_PROVIDER_PAGE_NOTE = "safe mocked/local provider page; no live account was created";
const VERIFICATION_LIMITATION = "CAPTCHA, SMS, OTP, real-name, QR, and provider anti-abuse checks are recorded as hard blockers and are not automated.";

function stamp() {
  const date = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    "_",
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds())
  ].join("");
}

function isoNow() {
  return new Date().toISOString();
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf-8");
}

function appendLine(filePath, value) {
  fs.appendFileSync(filePath, `${value}\n`, "utf-8");
}

function readManifest() {
  if (!fs.existsSync(MANIFEST_PATH)) {
    throw new Error(`manifest.json missing: ${MANIFEST_PATH}`);
  }
  return JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf-8"));
}

function mockProtonHtml() {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mock Proton Signup</title>
</head>
<body>
  <main>
    <h1>Create your Proton Mail account</h1>
    <form>
      <label>Username
        <input id="username" name="username" type="text" autocomplete="username">
      </label>
      <label>Password
        <input id="password" name="password" type="password" autocomplete="new-password">
      </label>
      <label>Repeat password
        <input id="password-repeat" name="repeat-password" type="password" autocomplete="new-password">
      </label>
      <button type="button" data-testid="submit">Create account</button>
    </form>
  </main>
</body>
</html>`;
}

function makeAccount(runId) {
  return {
    provider: "proton",
    username: "nxloadack",
    email: "nxloadack@proton.me",
    domain: "proton.me",
    password: "Aa1!bb22",
    firstName: "Nina",
    lastName: "Flow",
    birthMonth: "May",
    birthDay: "13",
    birthYear: "2005",
    recoveryEmail: "recovery@example.com",
    registrationRunId: runId
  };
}

async function waitForExtensionWorker(context, timeoutMs = 12000) {
  const existing = context.serviceWorkers().find((worker) => worker.url().startsWith("chrome-extension://"));
  if (existing) return existing;
  return context.waitForEvent("serviceworker", {
    timeout: timeoutMs,
    predicate: (worker) => worker.url().startsWith("chrome-extension://")
  });
}

async function sendRuntimeMessage(extensionPage, message) {
  return extensionPage.evaluate(async (payload) => new Promise((resolve) => {
    chrome.runtime.sendMessage(payload, (response) => {
      resolve({
        lastError: chrome.runtime.lastError ? chrome.runtime.lastError.message : null,
        response: response || null
      });
    });
  }), message);
}

async function fetchState(extensionPage) {
  const response = await sendRuntimeMessage(extensionPage, { type: "NM_GET_STATE" });
  return response && response.response ? response.response : null;
}

async function setSidepanelStartInputs(extensionPage, provider, account) {
  await extensionPage.selectOption("#providerSelect", provider);
  await extensionPage.fill("#manualEmailInput", account.email || "");
  await extensionPage.fill("#manualPasswordInput", account.password || "");
  await extensionPage.fill("#manualClientIdInput", account.clientId || "");
  await extensionPage.fill("#manualRefreshTokenInput", account.refreshToken || "");
}

async function clickContinueInSidepanel(extensionPage) {
  await extensionPage.locator("#continueBtn").click();
}

async function waitForStartAck(extensionPage, timeoutMs = 12000) {
  const deadline = Date.now() + timeoutMs;
  let lastState = null;
  while (Date.now() < deadline) {
    lastState = await fetchState(extensionPage);
    const ack = lastState && lastState.startAck ? lastState.startAck : null;
    if (ack && (ack.ok || ack.stage !== "waiting_for_content_ack")) {
      return { ack, state: lastState };
    }
    await extensionPage.waitForTimeout(250);
  }
  return {
    ack: lastState && lastState.startAck ? lastState.startAck : null,
    state: lastState
  };
}

async function sendTabMessage(extensionPage, urlPattern, message) {
  return extensionPage.evaluate(async ({ urlPattern, message }) => new Promise((resolve) => {
    chrome.tabs.query({ url: urlPattern }, (tabs) => {
      const tab = Array.isArray(tabs) && tabs.length ? tabs[0] : null;
      if (!tab || !tab.id) {
        resolve({ ok: false, reason: "provider_tab_not_found", tabId: null, response: null });
        return;
      }
      chrome.tabs.sendMessage(tab.id, message, { frameId: 0 }, (response) => {
        resolve({
          ok: !chrome.runtime.lastError,
          reason: chrome.runtime.lastError ? chrome.runtime.lastError.message : "content_response",
          tabId: tab.id,
          response: response || null
        });
      });
    });
  }), { urlPattern, message });
}

async function screenshot(page, screenshotsDir, label) {
  const filePath = path.join(screenshotsDir, `${label}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  return filePath;
}

function markdownReport(result) {
  const blockers = result.blockers.length ? result.blockers.join("; ") : "none";
  const limitations = result.limitations.length ? result.limitations.join("; ") : "none";
  return [
    "# Extension Load ACK Harness",
    "",
    `- runId: ${result.runId}`,
    `- provider: ${result.provider}`,
    `- finalStatus: ${result.finalStatus}`,
    `- extensionLoadedStatus: ${result.extensionLoadedStatus}`,
    `- backgroundServiceWorkerStatus: ${result.backgroundServiceWorkerStatus}`,
    `- contentScriptInjected: ${result.contentScriptInjected}`,
    `- startButtonAckStatus: ${result.startButtonAckStatus.ok ? "ok" : "failed"}`,
    `- currentURL: ${result.currentUrl || ""}`,
    `- safeValidation: ${result.safeValidation}`,
    `- evidence: ${MOCK_PROVIDER_PAGE_NOTE}`,
    `- verificationControlsNotAutomated: ${result.verificationControlsNotAutomated}`,
    `- blockers: ${blockers}`,
    `- limitations: ${limitations}`,
    ""
  ].join("\n");
}

async function main() {
  const runStamp = stamp();
  const runId = `extension-load-ack-${runStamp}`;
  const runRoot = ensureDir(path.join(ACK_RUNS_DIR, runStamp));
  const screenshotsDir = ensureDir(path.join(runRoot, "screenshots"));
  const consoleLogPath = path.join(runRoot, "console.log");
  const userDataDir = ensureDir(path.join(runRoot, "chromium-profile"));
  const result = {
    runType: "mocked_ack",
    provider: "proton",
    runId,
    browserProfile: userDataDir,
    extensionRoot: EXTENSION_ROOT,
    manifestPath: MANIFEST_PATH,
    extensionLoadedStatus: false,
    backgroundServiceWorkerStatus: "missing",
    contentScriptInjected: false,
    startButtonAckStatus: {
      ok: false,
      stage: "not_started",
      reason: "not_started",
      ack: null
    },
    currentUrl: "",
    safeValidation: true,
    verificationControlsNotAutomated: true,
    validationMode: MOCK_PROVIDER_PAGE_NOTE,
    blockers: [],
    limitations: [
      VERIFICATION_LIMITATION,
      "Playwright opens sidepanel HTML as an extension page and clicks the real sidepanel button DOM; it does not claim a native Chrome toolbar side-panel gesture."
    ],
    screenshots: [],
    finalStatus: "failed",
    startedAt: isoNow(),
    finishedAt: ""
  };

  let context = null;
  try {
    const manifest = readManifest();
    result.manifestVersion = manifest.manifest_version;
    result.extensionName = manifest.name;

    context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        `--disable-extensions-except=${EXTENSION_ROOT}`,
        `--load-extension=${EXTENSION_ROOT}`,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-dev-shm-usage"
      ]
    });

    context.on("page", (page) => {
      page.on("console", (message) => appendLine(consoleLogPath, `[${isoNow()}] [page:${message.type()}] ${message.text()}`));
      page.on("pageerror", (error) => appendLine(consoleLogPath, `[${isoNow()}] [pageerror] ${error.message}`));
    });

    await context.route(PROTON_ROUTE, (route) => route.fulfill({
      status: 200,
      contentType: "text/html; charset=utf-8",
      body: mockProtonHtml()
    }));

    const worker = await waitForExtensionWorker(context);
    const workerUrl = worker.url();
    const extensionId = workerUrl.split("/")[2] || "";
    result.backgroundServiceWorkerUrl = workerUrl;
    result.backgroundServiceWorkerStatus = workerUrl.includes("/background/background.js") ? "ready" : "unexpected_url";
    result.extensionId = extensionId;
    result.extensionLoadedStatus = Boolean(extensionId && workerUrl.startsWith("chrome-extension://"));

    const extensionPage = await context.newPage();
    await extensionPage.goto(`chrome-extension://${extensionId}/sidepanel/sidepanel.html`, { waitUntil: "domcontentloaded" });
    await extensionPage.waitForSelector("#continueBtn", { timeout: 8000 });
    result.sidepanelLoaded = true;

    const providerPage = await context.newPage();
    providerPage.on("console", (message) => appendLine(consoleLogPath, `[${isoNow()}] [provider:${message.type()}] ${message.text()}`));
    await providerPage.goto(PROTON_SIGNUP_URL, { waitUntil: "domcontentloaded" });
    await providerPage.waitForLoadState("load", { timeout: 8000 }).catch(() => {});
    await providerPage.waitForTimeout(800);
    await providerPage.bringToFront();
    result.currentUrl = providerPage.url();
    result.screenshots.push(path.relative(runRoot, await screenshot(providerPage, screenshotsDir, "01-mocked-proton-signup")).replace(/\\/g, "/"));

    let scanResult = null;
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      scanResult = await sendTabMessage(extensionPage, "https://account.proton.me/*", { type: "NM_SCAN" });
      if (scanResult && scanResult.ok && scanResult.response && scanResult.response.ok) break;
      await providerPage.waitForTimeout(500);
    }
    result.contentScan = scanResult;
    result.contentScriptInjected = Boolean(scanResult && scanResult.ok && scanResult.response && scanResult.response.ok);

    await providerPage.bringToFront();
    const manualAccount = makeAccount(runId);
    await setSidepanelStartInputs(extensionPage, "proton", manualAccount);
    await clickContinueInSidepanel(extensionPage);
    const startAckResult = await waitForStartAck(extensionPage, 12000);
    const startAck = startAckResult && startAckResult.ack ? startAckResult.ack : null;
    result.startRuntimeResponse = startAckResult && startAckResult.state ? startAckResult.state : null;
    result.startButtonAckStatus = {
      ok: Boolean(startAck && startAck.ok && startAck.response && startAck.response.ack === "NM_START_AUTOPILOT_ACK"),
      stage: startAck && startAck.stage ? startAck.stage : "missing_start_ack",
      reason: startAck && startAck.reason ? startAck.reason : "missing_start_ack",
      ack: startAck || null
    };
    result.contentScriptInjected = result.contentScriptInjected || result.startButtonAckStatus.ok;

    await providerPage.waitForTimeout(500);
    result.currentUrl = providerPage.url();
    result.screenshots.push(path.relative(runRoot, await screenshot(providerPage, screenshotsDir, "02-after-start-ack")).replace(/\\/g, "/"));

    if (!result.extensionLoadedStatus) result.blockers.push("extension_not_loaded");
    if (result.backgroundServiceWorkerStatus !== "ready") result.blockers.push("background_service_worker_not_ready");
    if (!result.contentScriptInjected) result.blockers.push("content_script_not_injected");
    if (!result.startButtonAckStatus.ok) result.blockers.push(result.startButtonAckStatus.reason || "start_ack_failed");

    result.finalStatus = result.blockers.length ? "blocked" : "passed";
  } catch (error) {
    result.blockers.push(error && error.message ? error.message : String(error));
    result.finalStatus = "error";
    appendLine(consoleLogPath, `[${isoNow()}] [harness-error] ${error && error.stack ? error.stack : error}`);
  } finally {
    result.finishedAt = isoNow();
    writeJson(path.join(runRoot, "run.json"), result);
    fs.writeFileSync(path.join(runRoot, "run.md"), markdownReport(result), "utf-8");
    if (context) await context.close();
  }

  console.log(JSON.stringify({
    finalStatus: result.finalStatus,
    runRoot,
    extensionLoadedStatus: result.extensionLoadedStatus,
    backgroundServiceWorkerStatus: result.backgroundServiceWorkerStatus,
    contentScriptInjected: result.contentScriptInjected,
    startButtonAckStatus: result.startButtonAckStatus.ok,
    blockers: result.blockers
  }, null, 2));

  if (result.finalStatus !== "passed") {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
