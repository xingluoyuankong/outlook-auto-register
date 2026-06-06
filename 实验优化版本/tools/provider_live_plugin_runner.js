const fs = require("fs");
const path = require("path");

const PLAYWRIGHT_ENTRY = "E:\\Openclaw\\runtime\\node\\node_modules\\playwright\\index.js";
const { chromium } = require(PLAYWRIGHT_ENTRY);

const ROOT = path.resolve(__dirname, "..");
const EXTENSION_ROOT = path.join(ROOT, "browser_extension");
const REPORT_ROOT = path.join(ROOT, "reports", "extension-flow-runs");
const REQUIRED_PROVIDER_ARTIFACTS = [
  "run.json",
  "run.md",
  "steps.jsonl",
  "console.log",
  "screenshots",
  "blockers.json",
  "repair-notes.md"
];

const PROVIDERS = Object.freeze({
  proton: { label: "Proton Mail", url: "https://account.proton.me/mail/signup" },
  gmx: { label: "GMX Mail", url: "https://signup.gmx.com/" },
  aol: { label: "AOL Mail", url: "https://login.aol.com/account/create" },
  zoho: { label: "Zoho Mail", url: "https://accounts.zoho.com/signup" },
  yandex: { label: "Yandex Mail", url: "https://passport.yandex.com/registration/mail" },
  mailcom: { label: "Mail.com", url: "https://service.mail.com/registration.html" },
  icloud: { label: "iCloud Mail", url: "https://appleid.apple.com/account" },
  mailru: { label: "Mail.ru", url: "https://account.mail.ru/signup?rf=auth.mail.ru&from=main" },
  naver: { label: "Naver Mail", url: "https://nid.naver.com/user2/join/agree" },
  kakao: { label: "Daum/Kakao Mail", url: "https://accounts.kakao.com/weblogin/create_account" },
  netease163: { label: "NetEase 163 Mail", url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=163mail" },
  netease126: { label: "NetEase 126 Mail", url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=126mail" },
  neteaseyeah: { label: "NetEase Yeah Mail", url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=yeah" },
  qq: { label: "QQ Mail", url: "https://ssl.zc.qq.com/v3/index-chs.html" },
  sina: { label: "Sina Mail", url: "https://mail.sina.com.cn/register/regmail.php" },
  sohu: { label: "Sohu Mail", url: "https://mail.sohu.com/reg/signup" },
  tutanota: { label: "Tutanota", url: "https://app.tuta.com/signup" }
});

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

function safeName(value) {
  return String(value || "provider").replace(/[^a-z0-9_-]+/gi, "_");
}

function parseArgs(argv) {
  const args = argv.slice(2);
  const selected = [];
  let headed = true;
  let timeoutMs = 45000;
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--headed") {
      headed = true;
    } else if (arg === "--headless") {
      headed = false;
    } else if (arg === "--timeout-ms") {
      timeoutMs = Number(args[index + 1] || timeoutMs);
      index += 1;
    } else if (arg === "--all") {
      selected.push(...Object.keys(PROVIDERS));
    } else if (arg.startsWith("--")) {
      throw new Error(`Unknown argument: ${arg}`);
    } else {
      selected.push(arg);
    }
  }
  const providers = [...new Set(selected.length ? selected : ["gmx"])]
    .filter((key) => PROVIDERS[key]);
  return { providers, headed, timeoutMs };
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function appendLine(filePath, value) {
  fs.appendFileSync(filePath, `${value}\n`, "utf8");
}

function recordStep(paths, step, status, details = {}) {
  appendLine(paths.stepsJsonl, JSON.stringify({
    at: isoNow(),
    step,
    status,
    details
  }));
}

function relativePath(root, filePath) {
  return path.relative(root, filePath).replace(/\\/g, "/");
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

async function setProviderInSidepanel(extensionPage, provider) {
  await extensionPage.selectOption("#providerSelect", provider);
  await extensionPage.evaluate(() => {
    const email = document.querySelector("#manualEmailInput");
    const password = document.querySelector("#manualPasswordInput");
    const clientId = document.querySelector("#manualClientIdInput");
    const refresh = document.querySelector("#manualRefreshTokenInput");
    if (email) email.value = "";
    if (password) password.value = "";
    if (clientId) clientId.value = "";
    if (refresh) refresh.value = "";
  });
}

async function clickContinueInSidepanel(extensionPage) {
  const button = extensionPage.locator("#continueBtn");
  try {
    await button.click({ force: true });
  } catch (_) {
    await extensionPage.evaluate(() => {
      const node = document.querySelector("#continueBtn");
      if (node) node.click();
    });
  }
}

async function waitForStartAck(extensionPage, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastState = null;
  while (Date.now() < deadline) {
    lastState = await fetchState(extensionPage);
    const ack = lastState && lastState.startAck ? lastState.startAck : null;
    if (ack && (ack.ok || ack.stage !== "waiting_for_content_ack")) {
      return { ack, state: lastState };
    }
    await extensionPage.waitForTimeout(300);
  }
  return { ack: lastState && lastState.startAck ? lastState.startAck : null, state: lastState };
}

function terminalStateReached(state) {
  if (!state) return false;
  if (state.blocker || state.finalState) return true;
  return ["blocked", "manual_wait", "done", "stopped"].includes(String(state.status || ""));
}

async function waitForTerminalState(extensionPage, timeoutMs, onState) {
  const deadline = Date.now() + timeoutMs;
  let lastSignature = "";
  let lastState = null;
  while (Date.now() < deadline) {
    const state = await fetchState(extensionPage);
    lastState = state || lastState;
    const signature = JSON.stringify({
      status: state && state.status,
      activeStep: state && state.activeStep,
      blocker: state && state.blocker,
      postChallengeState: state && state.postChallengeState,
      finalState: state && state.finalState,
      currentUrl: state && state.currentUrl
    });
    if (signature !== lastSignature) {
      lastSignature = signature;
      if (state && onState) onState(state);
    }
    if (terminalStateReached(state)) return state;
    await extensionPage.waitForTimeout(500);
  }
  return lastState;
}

async function screenshot(page, screenshotsDir, label) {
  const filePath = path.join(screenshotsDir, `${label}.png`);
  await page.screenshot({ path: filePath, fullPage: true }).catch(() => {});
  return filePath;
}

function providerPaths(runRoot, provider) {
  const dir = ensureDir(path.join(runRoot, safeName(provider)));
  const result = {
    dir,
    screenshots: ensureDir(path.join(dir, "screenshots")),
    consoleLog: path.join(dir, "console.log"),
    stepsJsonl: path.join(dir, "steps.jsonl"),
    runJson: path.join(dir, "run.json"),
    runMd: path.join(dir, "run.md"),
    blockersJson: path.join(dir, "blockers.json"),
    repairNotes: path.join(dir, "repair-notes.md"),
    browserProfile: ensureDir(path.join(dir, "chromium-profile"))
  };
  if (!fs.existsSync(result.consoleLog)) fs.writeFileSync(result.consoleLog, "", "utf8");
  return result;
}

function markdownReport(result) {
  const blocker = result.blockerType || "none";
  const blockerEvidence = result.blockerEvidence || "none";
  const selectorMisses = result.selectorMisses.length ? result.selectorMisses.join("; ") : "none";
  const screenshots = result.screenshots.map((item) => `- ${item}`).join("\n") || "- none";
  return [
    `# ${result.provider} Live Plugin Run`,
    "",
    `- Run type: ${result.runType}`,
    `- Run id: ${result.runId}`,
    `- Browser/profile: ${result.browserProfile}`,
    `- Extension loaded status: ${JSON.stringify(result.extensionLoadedStatus)}`,
    `- Start button ACK status: ${JSON.stringify(result.startButtonAckStatus)}`,
    `- Current URL: ${result.currentUrl || ""}`,
    `- Final status: ${result.finalStatus}`,
    `- Completeness: ${result.completenessPercentage}%`,
    `- Blocker type: ${blocker}`,
    `- Blocker evidence: ${blockerEvidence}`,
    "",
    "## Completed Steps",
    ...result.completedSteps.map((item) => `- ${item}`),
    "",
    "## Failed Steps",
    ...(result.failedSteps.length ? result.failedSteps.map((item) => `- ${item}`) : ["- None"]),
    "",
    "## Selector Misses",
    `- ${selectorMisses}`,
    "",
    "## Screenshots",
    screenshots,
    "",
    "This run uses a real provider page and clicks the real sidepanel start button DOM. It does not bypass CAPTCHA, SMS, OTP, QR, real-name, or provider anti-abuse controls."
  ].join("\n");
}

function repairNotes(result) {
  const lines = [
    `# ${result.provider} repair notes`,
    "",
    `- runType: ${result.runType}`,
    `- finalStatus: ${result.finalStatus}`,
    `- currentUrl: ${result.currentUrl || ""}`,
    `- activeStep: ${result.activeStep || ""}`,
    `- blockerType: ${result.blockerType || ""}`,
    `- nextRepairRecommendation: ${result.nextRepairRecommendation || ""}`
  ];
  return `${lines.join("\n")}\n`;
}

function summarizeResult(result, runRoot) {
  return {
    runType: result.runType,
    provider: result.provider,
    runId: result.runId,
    finalStatus: result.finalStatus,
    completenessPercentage: result.completenessPercentage,
    startButtonAckStatus: result.startButtonAckStatus,
    blockerType: result.blockerType,
    blockerEvidence: result.blockerEvidence,
    activeStep: result.activeStep,
    currentUrl: result.currentUrl,
    reportDir: relativePath(runRoot, path.join(runRoot, safeName(result.provider)))
  };
}

async function runProvider(runRoot, runStamp, provider, headed, timeoutMs) {
  const meta = PROVIDERS[provider];
  const paths = providerPaths(runRoot, provider);
  const runId = `${runStamp}_${provider}`;
  const result = {
    runType: "live_plugin_run",
    provider,
    providerLabel: meta.label,
    runId,
    browserProfile: paths.browserProfile,
    extensionRoot: EXTENSION_ROOT,
    extensionLoadedStatus: null,
    startButtonAckStatus: null,
    currentUrl: meta.url,
    activeStep: "",
    blockerType: "",
    blockerEvidence: "",
    selectorMisses: [],
    screenshots: [],
    completedSteps: [],
    failedSteps: [],
    finalStatus: "not_started",
    completenessPercentage: 0,
    nextRepairRecommendation: "",
    logs: [],
    errors: []
  };

  let context = null;
  try {
    context = await chromium.launchPersistentContext(paths.browserProfile, {
      headless: !headed,
      ignoreHTTPSErrors: true,
      args: [
        `--disable-extensions-except=${EXTENSION_ROOT}`,
        `--load-extension=${EXTENSION_ROOT}`,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-dev-shm-usage"
      ]
    });

    const attachLogging = (page, tag) => {
      page.on("console", (message) => appendLine(paths.consoleLog, `[${isoNow()}] [${tag}:${message.type()}] ${message.text()}`));
      page.on("pageerror", (error) => appendLine(paths.consoleLog, `[${isoNow()}] [${tag}:pageerror] ${error && error.stack ? error.stack : error}`));
    };

    const worker = await waitForExtensionWorker(context, 15000);
    const workerUrl = worker.url();
    const extensionId = workerUrl.split("/")[2] || "";
    result.extensionLoadedStatus = {
      ok: Boolean(extensionId && workerUrl.includes("/background/background.js")),
      extensionId,
      workerUrl
    };

    const extensionPage = await context.newPage();
    attachLogging(extensionPage, "sidepanel");
    await extensionPage.goto(`chrome-extension://${extensionId}/sidepanel/sidepanel.html`, { waitUntil: "domcontentloaded" });
    await extensionPage.waitForSelector("#continueBtn", { timeout: 12000 });
    recordStep(paths, "sidepanel_ready", "completed", { extensionId });
    result.completedSteps.push("sidepanel_ready");
    result.screenshots.push(relativePath(runRoot, await screenshot(extensionPage, paths.screenshots, "01-sidepanel-ready")));

    const providerPage = await context.newPage();
    attachLogging(providerPage, "provider");
    await providerPage.goto(meta.url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
    await providerPage.waitForLoadState("load", { timeout: Math.min(timeoutMs, 12000) }).catch(() => {});
    await providerPage.waitForTimeout(1200);
    await providerPage.bringToFront();
    result.currentUrl = providerPage.url();
    recordStep(paths, "open_signup", "completed", { url: result.currentUrl });
    result.completedSteps.push("open_signup");
    result.screenshots.push(relativePath(runRoot, await screenshot(providerPage, paths.screenshots, "02-provider-open")));

    await setProviderInSidepanel(extensionPage, provider);
    recordStep(paths, "provider_selected", "completed", { provider });
    result.completedSteps.push("provider_selected");

    recordStep(paths, "start_button_ack", "started", { provider, action: "sidepanel_continue_btn" });
    await clickContinueInSidepanel(extensionPage);
    const ackResult = await waitForStartAck(extensionPage, Math.min(timeoutMs, 15000));
    const ack = ackResult.ack || null;
    result.startButtonAckStatus = ack || {
      ok: false,
      stage: "missing_start_ack",
      reason: "missing_start_ack"
    };
    if (ack && ack.ok && ack.response && ack.response.ack === "NM_START_AUTOPILOT_ACK") {
      recordStep(paths, "start_button_ack", "completed", ack);
      result.completedSteps.push("start_button_ack");
    } else {
      recordStep(paths, "start_button_ack", "failed", ack || {});
      result.failedSteps.push("start_button_ack");
    }
    result.screenshots.push(relativePath(runRoot, await screenshot(extensionPage, paths.screenshots, "03-sidepanel-after-start")));

    if (!(ack && ack.ok && ack.response && ack.response.ack === "NM_START_AUTOPILOT_ACK")) {
      result.finalStatus = "ack_failed";
      result.nextRepairRecommendation = "Fix sidepanel -> background -> content ACK before attempting provider-specific selector repair.";
    } else {
      const terminalState = await waitForTerminalState(extensionPage, timeoutMs, (state) => {
        recordStep(paths, "state_poll", "observed", {
          status: state.status || "",
          activeStep: state.activeStep || "",
          blocker: state.blocker || null,
          postChallengeState: state.postChallengeState || "",
          finalState: state.finalState || "",
          currentUrl: state.currentUrl || ""
        });
      });
      if (terminalState) {
        result.activeStep = terminalState.activeStep || "";
        result.currentUrl = terminalState.currentUrl || result.currentUrl;
        const visibleSteps = Array.isArray(terminalState.steps) ? terminalState.steps.filter((step) => step && step.status && step.status !== "pending") : [];
        result.completenessPercentage = Array.isArray(terminalState.steps) && terminalState.steps.length
          ? Math.round((visibleSteps.length / terminalState.steps.length) * 100)
          : 0;
        if (terminalState.blocker) {
          result.blockerType = terminalState.blocker.type || "";
          result.blockerEvidence = terminalState.blocker.evidence || terminalState.rootCause?.reason || "";
          result.finalStatus = "hard_blocker_recorded";
          result.nextRepairRecommendation = terminalState.rootCause?.nextAction || "Record the blocker and stop before anti-abuse verification.";
        } else if (terminalState.finalState) {
          result.finalStatus = "final_state_reached";
          result.nextRepairRecommendation = "Review final state and credential export readiness.";
        } else if (terminalState.status === "stopped") {
          result.finalStatus = "stopped";
          result.nextRepairRecommendation = terminalState.rootCause?.nextAction || "Review why the run stopped before a blocker or final state was recorded.";
        } else {
          result.finalStatus = "timeout";
          result.nextRepairRecommendation = "Review the final observed state; the provider did not reach a blocker or final state before timeout.";
        }
      } else {
        result.finalStatus = "timeout";
        result.nextRepairRecommendation = "No background state was available before timeout; inspect content script injection and page load timing.";
      }
    }

    result.screenshots.push(relativePath(runRoot, await screenshot(providerPage, paths.screenshots, "04-provider-final")));
    result.screenshots.push(relativePath(runRoot, await screenshot(extensionPage, paths.screenshots, "05-sidepanel-final")));
  } catch (error) {
    result.errors.push(error && error.stack ? error.stack : String(error));
    result.finalStatus = "runner_error";
    result.failedSteps.push("runner_error");
    result.nextRepairRecommendation = "Inspect the console log and stack trace before retrying the live plugin runner.";
    appendLine(paths.consoleLog, `[${isoNow()}] [runner:error] ${error && error.stack ? error.stack : error}`);
  } finally {
    if (context) {
      await context.close().catch(() => {});
    }
    writeJson(paths.blockersJson, {
      runType: result.runType,
      provider: result.provider,
      blockerType: result.blockerType,
      blockerEvidence: result.blockerEvidence,
      finalStatus: result.finalStatus
    });
    fs.writeFileSync(paths.repairNotes, repairNotes(result), "utf8");
    fs.writeFileSync(paths.runMd, markdownReport(result), "utf8");
    writeJson(paths.runJson, result);
  }

  return result;
}

function writeSummary(runRoot, results) {
  const summary = {
    runType: "live_plugin_run",
    checkedAt: isoNow(),
    runRoot,
    requiredProviderArtifacts: REQUIRED_PROVIDER_ARTIFACTS,
    totals: {
      providers: results.length,
      passed: results.filter((item) => item.finalStatus !== "ack_failed" && item.finalStatus !== "runner_error").length,
      failed: results.filter((item) => item.finalStatus === "ack_failed" || item.finalStatus === "runner_error").length
    },
    providers: results.map((item) => summarizeResult(item, runRoot))
  };
  writeJson(path.join(runRoot, "summary.json"), summary);
  const lines = [
    "# Live Plugin Run Summary",
    "",
    `Checked at: ${summary.checkedAt}`,
    `Run root: ${runRoot}`,
    "",
    "| Provider | ACK | Active step | Blocker | Status | Completeness |",
    "|---|---|---|---|---|---|"
  ];
  for (const item of results) {
    const ack = item.startButtonAckStatus && item.startButtonAckStatus.ok ? "ACK" : "NO ACK";
    lines.push(`| ${item.provider} | ${ack} | ${item.activeStep || "<none>"} | ${item.blockerType || "<none>"} | ${item.finalStatus} | ${item.completenessPercentage}% |`);
  }
  lines.push("");
  lines.push("These runs use real provider pages and the real sidepanel start button DOM. They do not bypass CAPTCHA, SMS, OTP, QR, real-name, or provider anti-abuse controls.");
  fs.writeFileSync(path.join(runRoot, "summary.md"), `${lines.join("\n")}\n`, "utf8");
}

async function main() {
  const { providers, headed, timeoutMs } = parseArgs(process.argv);
  const runStamp = stamp();
  const runRoot = ensureDir(path.join(REPORT_ROOT, runStamp));
  const results = [];
  for (const provider of providers) {
    results.push(await runProvider(runRoot, runStamp, provider, headed, timeoutMs));
  }
  writeSummary(runRoot, results);
  console.log(JSON.stringify({
    runType: "live_plugin_run",
    runRoot,
    providers: results.map((item) => ({
      provider: item.provider,
      finalStatus: item.finalStatus,
      startButtonAckStatus: Boolean(item.startButtonAckStatus && item.startButtonAckStatus.ok),
      blockerType: item.blockerType
    }))
  }, null, 2));
  if (results.some((item) => item.finalStatus === "ack_failed" || item.finalStatus === "runner_error")) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
