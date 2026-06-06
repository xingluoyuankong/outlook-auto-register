const fs = require("fs");
const path = require("path");

const PLAYWRIGHT_ENTRY = "E:\\Openclaw\\runtime\\node\\node_modules\\playwright\\index.js";
const { chromium } = require(PLAYWRIGHT_ENTRY);

const ROOT = path.resolve(__dirname, "..");
const EXTENSION_ROOT = path.join(ROOT, "browser_extension");
const FLOW_STATE_JS = path.join(EXTENSION_ROOT, "shared", "flow-state.js");
const CONTENT_JS = path.join(EXTENSION_ROOT, "content", "outlook-signup.js");
const DIAGNOSTICS_DIR = path.join(ROOT, "diagnostics_runs");
const FIXTURE_RUNS_DIR = path.join(ROOT, "reports", "extension-flow-fixtures");
const REQUIRED_PROVIDER_ARTIFACTS = [
  "run.json",
  "run.md",
  "steps.jsonl",
  "console.log",
  "screenshots",
  "blockers.json",
  "repair-notes.md"
];

const ACCOUNT = Object.freeze({
  username: "nxfixture",
  email: "nxfixture@example.com",
  password: "Aa1!bb22",
  firstName: "Nina",
  lastName: "Flow",
  birthMonth: "May",
  birthDay: "13",
  birthYear: "2005",
  gender: "Rather not say",
  recoveryEmail: "recovery@example.com"
});

const CASES = [
  {
    provider: "proton",
    host: "account.proton.me",
    url: "https://account.proton.me/signup",
    fields: "plan-username-password",
    expectedActiveStep: "fill_proton_username",
    expectedBlockerStep: "proton_email_otp",
    blockerHtml: "<main><h1>Email verification</h1><p>Check your email for a one-time code.</p></main>"
  },
  {
    provider: "gmx",
    host: "www.gmx.com",
    url: "https://www.gmx.com/consent-management/signup",
    fields: "name-username-password-birthdate-recovery",
    expectedActiveStep: "fill_gmx_profile_birthdate",
    expectedBlockerStep: "gmx_imap_enablement",
    blockerHtml: "<main><h1>Enable IMAP</h1><p>Create an app password before mail client access.</p></main>"
  },
  {
    provider: "aol",
    host: "login.aol.com",
    url: "https://login.aol.com/account/create",
    fields: "name-username-password-birthdate",
    expectedActiveStep: "fill_aol_account_form",
    expectedBlockerStep: "aol_phone",
    blockerHtml: "<main><label>Phone number<input type='tel' name='phone'></label><p>SMS verification code required.</p></main>"
  },
  {
    provider: "zoho",
    host: "accounts.zoho.com",
    url: "https://accounts.zoho.com/signup",
    fields: "name-username-password",
    expectedActiveStep: "fill_zoho_name",
    expectedBlockerStep: "zoho_phone_or_otp",
    blockerHtml: "<main><label>Mobile number<input type='tel' name='mobile'></label><p>OTP verification code required.</p></main>"
  },
  {
    provider: "yandex",
    host: "passport.yandex.com",
    url: "https://passport.yandex.com/registration",
    fields: "name-username-password",
    expectedActiveStep: "fill_yandex_name",
    expectedBlockerStep: "yandex_phone_or_captcha",
    blockerHtml: "<main><div class='g-recaptcha'>recaptcha</div><p>Phone number SMS code required.</p></main>"
  },
  {
    provider: "mailcom",
    host: "service.mail.com",
    url: "https://service.mail.com/registration.html",
    fields: "name-username-password-birthdate-recovery",
    expectedActiveStep: "fill_mailcom_name",
    expectedBlockerStep: "mailcom_challenge",
    blockerHtml: "<main><h1>Security challenge</h1><p>Verification code required before continuing.</p></main>"
  },
  {
    provider: "icloud",
    host: "appleid.apple.com",
    url: "https://appleid.apple.com/account",
    fields: "name-username-password-birthdate",
    expectedActiveStep: "fill_icloud_name",
    expectedBlockerStep: "icloud_email_otp",
    blockerHtml: "<main><h1>Email verification</h1><p>Enter the one-time code sent by email.</p></main>"
  },
  {
    provider: "mailru",
    host: "account.mail.ru",
    url: "https://account.mail.ru/signup",
    fields: "name-username-password-birthdate-recovery",
    expectedActiveStep: "fill_mailru_name",
    expectedBlockerStep: "mailru_phone_or_captcha",
    blockerHtml: "<main><div class='hcaptcha'>hcaptcha</div><label>Phone number<input type='tel' name='phone'></label></main>"
  },
  {
    provider: "naver",
    host: "nid.naver.com",
    url: "https://nid.naver.com/user2/join",
    fields: "username-password-name-birthdate-gender",
    expectedActiveStep: "fill_naver_name",
    expectedBlockerStep: "naver_phone_sms",
    blockerHtml: "<main><label>Mobile number<input type='tel' name='phone'></label><p>SMS text message verification code</p></main>"
  },
  {
    provider: "kakao",
    host: "accounts.kakao.com",
    url: "https://accounts.kakao.com/weblogin/create_account",
    fields: "terms-username-password-name",
    expectedActiveStep: "fill_kakao_name",
    expectedBlockerStep: "kakao_phone_or_email_otp",
    blockerHtml: "<main><h1>Email verification</h1><p>OTP one-time code or phone number is required.</p></main>"
  },
  {
    provider: "netease163",
    host: "reg.email.163.com",
    url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=163mail",
    fields: "username-password",
    expectedActiveStep: "fill_netease_username",
    expectedBlockerStep: "netease_sms_or_resume",
    blockerHtml: "<main><label>Phone<input type='tel' name='phone'></label><p>SMS verification code required.</p></main>"
  },
  {
    provider: "netease126",
    host: "reg.email.163.com",
    url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=126mail",
    fields: "username-password",
    expectedActiveStep: "fill_netease_username",
    expectedBlockerStep: "netease_sms_or_resume",
    blockerHtml: "<main><label>Phone<input type='tel' name='phone'></label><p>SMS verification code required.</p></main>"
  },
  {
    provider: "neteaseyeah",
    host: "reg.email.163.com",
    url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=yeah",
    fields: "username-password",
    expectedActiveStep: "fill_netease_username",
    expectedBlockerStep: "netease_sms_or_resume",
    blockerHtml: "<main><label>Phone<input type='tel' name='phone'></label><p>SMS verification code required.</p></main>"
  },
  {
    provider: "qq",
    host: "ssl.zc.qq.com",
    url: "https://ssl.zc.qq.com/v3/index-chs.html",
    fields: "username-password",
    expectedActiveStep: "fill_qq_username",
    expectedBlockerStep: "qq_phone_sms",
    blockerHtml: "<main><label>Phone<input type='tel' name='phone'></label><p>SMS verification code required.</p></main>"
  },
  {
    provider: "sina",
    host: "mail.sina.com.cn",
    url: "https://mail.sina.com.cn/register/regmail.php",
    fields: "phone-password",
    expectedActiveStep: "sina_phone_account",
    expectedBlockerStep: "sina_phone_account",
    blockerHtml: "<main><label>Mobile<input type='tel' name='phone'></label><p>Manual phone account gate.</p></main>"
  },
  {
    provider: "sohu",
    host: "mail.sohu.com",
    url: "https://mail.sohu.com/reg/signup",
    fields: "username-password",
    expectedActiveStep: "fill_sohu_username",
    expectedBlockerStep: "sohu_phone_sms",
    blockerHtml: "<main><label>Phone<input type='tel' name='phone'></label><p>SMS verification code required.</p></main>"
  },
  {
    provider: "tutanota",
    host: "app.tuta.com",
    url: "https://app.tuta.com/signup",
    fields: "username-password-terms",
    expectedActiveStep: "fill_tutanota_username",
    expectedBlockerStep: "tutanota_email_otp",
    blockerHtml: "<main><h1>Email verification</h1><p>Check your email for a one-time code.</p></main>"
  }
];

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

function providerDirName(provider) {
  return String(provider || "provider").replace(/[^a-z0-9_-]+/gi, "_");
}

function makeAccount(provider, runId) {
  const account = { ...ACCOUNT, provider, registrationRunId: runId };
  account.domain = `${provider}.example`;
  account.email = `${account.username}@${account.domain}`;
  return account;
}

function pageHtml(fieldSet) {
  const fields = new Set(String(fieldSet || "").split("-").filter(Boolean));
  const controls = [];
  if (fields.has("terms")) {
    controls.push("<label for='terms'>Terms of service</label><input id='terms' type='checkbox' name='terms'>");
  }
  if (fields.has("plan")) {
    controls.push(`
      <section class="plans">
        <label class="plan-card">
          <strong>Free</strong>
          <input id="plan-free" type="radio" name="plan" value="free">
          <span>¥0 forever, 1 GB mailbox</span>
        </label>
        <label class="plan-card selected">
          <strong>Proton Unlimited</strong>
          <input id="plan-paid" type="radio" name="plan" value="paid" checked>
          <span>Paid VPN Pass Drive plan</span>
        </label>
      </section>`);
  }
  if (fields.has("name")) {
    controls.push("<label>First name<input name='firstName' autocomplete='given-name'></label>");
    controls.push("<label>Last name<input name='lastName' autocomplete='family-name'></label>");
  }
  if (fields.has("username")) {
    if (fields.has("plan")) {
      controls.push("<label>Email username<span class='username-row'><input data-testid='input-input-element'><button type='button'>@proton.me</button></span></label>");
    } else {
      controls.push("<label>Email username<input name='username' autocomplete='username'></label>");
    }
  }
  if (fields.has("password")) {
    controls.push("<label>Password<input name='password' type='password' autocomplete='new-password'></label>");
    controls.push("<label>Confirm password<input name='confirmPassword' type='password' autocomplete='new-password'></label>");
  }
  if (fields.has("birthdate")) {
    controls.push("<label>Birth month<input name='birthMonth' aria-label='Birth month'></label>");
    controls.push("<label>Birth day<input name='birthDay' aria-label='Birth day'></label>");
    controls.push("<label>Birth year<input name='birthYear' aria-label='Birth year'></label>");
  }
  if (fields.has("gender")) {
    controls.push("<label>Gender<select name='gender'><option>Rather not say</option><option>Female</option></select></label>");
  }
  if (fields.has("recovery")) {
    controls.push("<label>Recovery email<input name='recoveryEmail' type='email'></label>");
  }
  if (fields.has("phone")) {
    controls.push("<label>Mobile<input name='phone' type='tel'></label>");
  }
  controls.push("<button type='button'>Next</button>");
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Ninjemail provider fixture</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 24px; }
    label { display: block; margin: 10px 0; }
    .plans { display: flex; gap: 12px; }
    .plan-card { width: 180px; min-height: 110px; border: 1px solid #cabdff; padding: 12px; }
    .username-row { display: flex; align-items: center; gap: 4px; }
    .username-row input { width: 220px; }
    .username-row button { width: 80px; }
    input, select, button { display: block; width: 280px; height: 32px; margin-top: 4px; }
    button { width: 120px; }
  </style>
</head>
<body>
  <main>
    <h1>Provider registration</h1>
    ${controls.join("\n    ")}
  </main>
</body>
</html>`;
}

function providerPaths(runRoot, provider) {
  const providerDir = path.join(runRoot, providerDirName(provider));
  const screenshotsDir = path.join(providerDir, "screenshots");
  fs.mkdirSync(screenshotsDir, { recursive: true });
  const paths = {
    provider,
    dir: providerDir,
    screenshotsDir,
    runJson: path.join(providerDir, "run.json"),
    runMd: path.join(providerDir, "run.md"),
    stepsJsonl: path.join(providerDir, "steps.jsonl"),
    consoleLog: path.join(providerDir, "console.log"),
    blockersJson: path.join(providerDir, "blockers.json"),
    repairNotes: path.join(providerDir, "repair-notes.md")
  };
  fs.writeFileSync(paths.stepsJsonl, "", "utf8");
  fs.writeFileSync(paths.consoleLog, "", "utf8");
  return paths;
}

function appendJsonl(filePath, payload) {
  fs.appendFileSync(filePath, `${JSON.stringify({ at: isoNow(), ...payload })}\n`, "utf8");
}

function appendConsole(paths, line) {
  fs.appendFileSync(paths.consoleLog, `[${isoNow()}] ${line}\n`, "utf8");
}

function recordStep(paths, result, step, status, details = {}) {
  const entry = {
    runId: result.runId,
    provider: result.provider,
    step,
    status,
    currentUrl: result.currentUrl || "",
    details
  };
  appendJsonl(paths.stepsJsonl, entry);
  if (status === "completed" && !result.completedSteps.includes(step)) result.completedSteps.push(step);
  if (status === "failed") result.failedSteps.push({ step, details });
}

async function captureScreenshot(page, paths, result, label) {
  const filename = `${String(result.screenshots.length + 1).padStart(2, "0")}-${label}.png`;
  const fullPath = path.join(paths.screenshotsDir, filename);
  try {
    await page.screenshot({ path: fullPath, fullPage: true });
    result.screenshots.push(path.relative(paths.dir, fullPath).replace(/\\/g, "/"));
    recordStep(paths, result, `screenshot:${label}`, "completed", { file: filename });
  } catch (error) {
    recordStep(paths, result, `screenshot:${label}`, "failed", {
      error: error && error.message ? error.message : String(error)
    });
  }
}

async function installChromeMock(page, provider, runId) {
  const account = makeAccount(provider, runId);
  await page.addInitScript(({ provider, account }) => {
    const listeners = [];
    const storage = {
      ninjemailProvider: provider,
      ninjemailActiveAccount: account,
      ninjemailGeneratedAccount: account,
      ninjemailAutoRunEnabled: false
    };
    window.__ninjemailMessages = [];
    window.__ninjemailStorage = storage;
    window.__ninjemailDispatch = async (message) => {
      let response;
      for (const listener of listeners) {
        await new Promise((resolve) => {
          const sendResponse = (value) => {
            response = value;
            resolve();
          };
          const returned = listener(message, {}, sendResponse);
          if (returned !== true) resolve();
        });
      }
      return response;
    };
    window.chrome = {
      runtime: {
        lastError: null,
        sendMessage(message, callback) {
          window.__ninjemailMessages.push(message);
          if (typeof callback === "function") callback({ ok: true });
        },
        onMessage: {
          addListener(listener) {
            listeners.push(listener);
          }
        }
      },
      storage: {
        local: {
          get(keys, callback) {
            if (Array.isArray(keys)) {
              callback(Object.fromEntries(keys.map((key) => [key, storage[key]])));
              return;
            }
            if (typeof keys === "string") {
              callback({ [keys]: storage[keys] });
              return;
            }
            callback({ ...storage });
          },
          set(values, callback) {
            Object.assign(storage, values || {});
            if (typeof callback === "function") callback();
          }
        },
        onChanged: {
          addListener() {}
        }
      }
    };
  }, { provider, account });
}

async function loadFixture(page, testCase, html, runId) {
  await page.route("**/*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "text/html; charset=utf-8",
      body: html
    });
  });
  await installChromeMock(page, testCase.provider, runId);
  await page.goto(testCase.url, { waitUntil: "domcontentloaded" });
  await page.addScriptTag({ path: FLOW_STATE_JS });
  await page.addScriptTag({ path: CONTENT_JS });
  await page.waitForFunction(() => Array.isArray(window.__ninjemailMessages)
    && window.__ninjemailMessages.some((item) => item.type === "NM_CONTENT_STATUS"), null, { timeout: 5000 });
  return page.evaluate(() => ({
    chromeMockLoaded: Boolean(window.chrome && window.chrome.runtime && window.chrome.runtime.onMessage),
    flowStateLoaded: Boolean(window.NinjemailFlow && window.NinjemailFlow.FLOW_STEPS_BY_PROVIDER),
    contentScriptInjected: Array.isArray(window.__ninjemailMessages)
      && window.__ninjemailMessages.some((item) => item.type === "NM_CONTENT_STATUS"),
    provider: window.__ninjemailStorage && window.__ninjemailStorage.ninjemailProvider
  }));
}

async function scan(page) {
  await page.evaluate(() => window.__ninjemailDispatch({ type: "NM_SCAN" }));
  await page.waitForTimeout(120);
  return page.evaluate(() => {
    const statuses = window.__ninjemailMessages
      .filter((item) => item.type === "NM_CONTENT_STATUS")
      .map((item) => item.payload);
    return statuses[statuses.length - 1] || null;
  });
}

async function runStep(page, stepId, provider) {
  const account = makeAccount(provider, "");
  const outcome = await page.evaluate(async ({ stepId, account }) => {
    const before = Array.isArray(window.__ninjemailMessages) ? window.__ninjemailMessages.length : 0;
    const response = await window.__ninjemailDispatch({
      type: "NM_STEP_ACTION",
      action: "run_step",
      stepId,
      account
    });
    const after = Array.isArray(window.__ninjemailMessages)
      ? window.__ninjemailMessages.slice(before)
      : [];
    const result = after
      .filter((item) => item.type === "NM_ACTION_RESULT")
      .map((item) => item.payload)
      .find((payload) => payload && payload.action === "run_step" && payload.stepId === stepId) || null;
    return { before, response, result };
  }, { stepId, account });
  if (outcome.result) return outcome.result;
  await page.waitForTimeout(180);
  return page.evaluate(({ stepId, before, response }) => {
    const after = Array.isArray(window.__ninjemailMessages)
      ? window.__ninjemailMessages.slice(before)
      : [];
    const result = after
      .filter((item) => item.type === "NM_ACTION_RESULT")
      .map((item) => item.payload)
      .find((payload) => payload && payload.action === "run_step" && payload.stepId === stepId);
    return result || response || null;
  }, { stepId, before: outcome.before, response: outcome.response });
}

async function startAutoRunAck(page, provider, runId) {
  const account = makeAccount(provider, runId);
  const response = await page.evaluate(({ account, runId }) => window.__ninjemailDispatch({
    type: "NM_STEP_ACTION",
    action: "auto_run",
    account,
    runId
  }), { account, runId });
  await page.evaluate(() => window.__ninjemailDispatch({
    type: "NM_STEP_ACTION",
    action: "stop_auto"
  }));
  await page.waitForTimeout(120);
  return response || null;
}

async function values(page) {
  return page.evaluate(() => {
    const result = {};
    for (const node of Array.from(document.querySelectorAll("input, select"))) {
      const key = node.name || node.id || node.type;
      if (node.type === "radio") {
        if (node.checked || !(key in result)) result[key] = node.checked ? node.value : "";
      } else if (node.type === "checkbox") {
        result[key] = node.checked;
      } else {
        result[key] = node.value;
      }
    }
    return result;
  });
}

function expectedFilledValues(stepId) {
  const expected = [];
  const step = String(stepId || "");
  if (step.includes("_username") || step.includes("_domain")) expected.push(ACCOUNT.username);
  if (step.includes("_name") || step.includes("_profile")) {
    expected.push(ACCOUNT.firstName, `${ACCOUNT.firstName} ${ACCOUNT.lastName}`);
  }
  if (step.includes("_password")) expected.push(ACCOUNT.password);
  if (step.includes("_recovery") || step.includes("_reserve_email")) expected.push(ACCOUNT.recoveryEmail);
  if (step.includes("_birthdate")) expected.push(ACCOUNT.birthMonth, ACCOUNT.birthDay, ACCOUNT.birthYear);
  return expected;
}

async function waitForExpectedFilledValue(page, stepId) {
  const expected = expectedFilledValues(stepId);
  if (!expected.length) {
    return { ok: true, skipped: true, expected, values: await values(page) };
  }
  try {
    await page.waitForFunction((expectedValues) => {
      const currentValues = Array.from(document.querySelectorAll("input, select"))
        .map((node) => node.type === "checkbox" ? String(node.checked) : String(node.value || ""));
      return expectedValues.some((expectedValue) => currentValues.includes(String(expectedValue)));
    }, expected, { timeout: 12000, polling: 100 });
    return { ok: true, expected, values: await values(page) };
  } catch (error) {
    return {
      ok: false,
      expected,
      values: await values(page),
      error: error && error.message ? error.message : String(error)
    };
  }
}

function assertResult(result, ok, detail) {
  if (!ok) {
    result.errors.push(detail);
  }
}

function writeProviderReports(paths, result) {
  const blockers = [];
  if (result.blockerType || result.observedBlockerStep) {
    blockers.push({
      provider: result.provider,
      blockerType: result.blockerType || "provider_challenge",
      step: result.observedBlockerStep || result.expectedBlockerStep,
      evidence: result.blockerEvidence || "",
      hardBlocker: true,
      action: result.blockerAction || null
    });
  }

  result.requiredArtifacts = REQUIRED_PROVIDER_ARTIFACTS;
  result.artifacts = {
    runJson: "run.json",
    runMd: "run.md",
    stepsJsonl: "steps.jsonl",
    consoleLog: "console.log",
    screenshots: "screenshots/",
    blockersJson: "blockers.json",
    repairNotes: "repair-notes.md"
  };
  fs.writeFileSync(paths.runJson, JSON.stringify(result, null, 2), "utf8");
  fs.writeFileSync(paths.blockersJson, JSON.stringify(blockers, null, 2), "utf8");

  const md = [
    `# ${result.provider} Extension Flow Run`,
    "",
    `- Run id: ${result.runId}`,
    `- Browser/profile: ${result.browserProfile}`,
    `- Extension loaded status: ${JSON.stringify(result.extensionLoadedStatus)}`,
    `- Start button ACK status: ${JSON.stringify(result.startButtonAckStatus)}`,
    `- Current URL: ${result.currentUrl || ""}`,
    `- Final status: ${result.finalStatus}`,
    `- Completeness: ${result.completenessPercentage}%`,
    `- Blocker type: ${result.blockerType || "-"}`,
    `- Blocker evidence: ${result.blockerEvidence || "-"}`,
    "",
    "## Completed Steps",
    ...result.completedSteps.map((item) => `- ${item}`),
    "",
    "## Failed Steps",
    ...(result.failedSteps.length ? result.failedSteps.map((item) => `- ${item.step}: ${JSON.stringify(item.details)}`) : ["- None"]),
    "",
    "## Selector Misses",
    ...(result.selectorMisses.length ? result.selectorMisses.map((item) => `- ${item}`) : ["- None"]),
    "",
    "## Screenshots",
    ...(result.screenshots.length ? result.screenshots.map((item) => `- ${item}`) : ["- None"]),
    "",
    "This run uses mocked provider pages and stops at real verification blockers. It does not create accounts or bypass CAPTCHA/SMS/OTP."
  ];
  fs.writeFileSync(paths.runMd, md.join("\n"), "utf8");

  const notes = [
    `# ${result.provider} Repair Notes`,
    "",
    result.nextRepairRecommendation || "No immediate selector repair needed in the mocked provider fixture.",
    "",
    result.ok
      ? "Hard verification blockers are recorded as expected and should be handled by manual/provider adapters outside this fixture."
      : "Review failed steps and selector misses before running this provider against a live page."
  ];
  fs.writeFileSync(paths.repairNotes, notes.join("\n"), "utf8");
}

async function runCase(browser, testCase, runRoot, runStamp) {
  const runId = `${runStamp}_${testCase.provider}`;
  const paths = providerPaths(runRoot, testCase.provider);
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  const result = {
    runType: "mocked_fixture",
    provider: testCase.provider,
    runId,
    browserProfile: "playwright-chromium-headless-mocked-extension-content",
    url: testCase.url,
    browserProfileEvidence: PLAYWRIGHT_ENTRY,
    extensionLoadedStatus: null,
    startButtonAckStatus: null,
    currentUrl: "",
    expectedActiveStep: testCase.expectedActiveStep,
    observedActiveStep: "",
    expectedBlockerStep: testCase.expectedBlockerStep,
    observedBlockerStep: "",
    fillAction: null,
    blockerAction: null,
    filledValues: {},
    completedSteps: [],
    failedSteps: [],
    blockerType: "",
    blockerEvidence: "",
    selectorMisses: [],
    screenshots: [],
    finalStatus: "not_started",
    completenessPercentage: 0,
    nextRepairRecommendation: "",
    errors: []
  };
  page.on("console", (message) => appendConsole(paths, `${message.type()} ${message.text()}`));
  page.on("pageerror", (error) => appendConsole(paths, `pageerror ${error && error.stack ? error.stack : error}`));
  try {
    recordStep(paths, result, "fixture_load", "started", { url: testCase.url, fields: testCase.fields });
    result.extensionLoadedStatus = await loadFixture(page, testCase, pageHtml(testCase.fields), runId);
    result.currentUrl = page.url();
    recordStep(paths, result, "plugin_ready", "completed", result.extensionLoadedStatus);
    recordStep(paths, result, "open_signup", "completed", { url: result.currentUrl });
    await captureScreenshot(page, paths, result, "fixture-loaded");

    recordStep(paths, result, "start_button_ack", "started", { action: "auto_run" });
    result.startButtonAckStatus = await startAutoRunAck(page, testCase.provider, runId);
    const ackOk = Boolean(result.startButtonAckStatus
      && result.startButtonAckStatus.ok
      && result.startButtonAckStatus.ack === "NM_START_AUTOPILOT_ACK");
    assertResult(result, ackOk, `expected NM_START_AUTOPILOT_ACK, got ${JSON.stringify(result.startButtonAckStatus)}`);
    recordStep(paths, result, "start_button_ack", ackOk ? "completed" : "failed", result.startButtonAckStatus || {});

    const firstScan = await scan(page);
    result.observedActiveStep = firstScan && firstScan.activeStep;
    assertResult(result, result.observedActiveStep === testCase.expectedActiveStep,
      `expected activeStep ${testCase.expectedActiveStep}, got ${result.observedActiveStep}`);
    assertResult(result, firstScan && firstScan.provider === testCase.provider,
      `expected payload provider ${testCase.provider}, got ${firstScan && firstScan.provider}`);
    recordStep(paths, result, "scan_initial", result.observedActiveStep === testCase.expectedActiveStep ? "completed" : "failed", {
      expectedActiveStep: testCase.expectedActiveStep,
      observedActiveStep: result.observedActiveStep,
      provider: firstScan && firstScan.provider
    });

    result.fillAction = await runStep(page, testCase.expectedActiveStep, testCase.provider);
    result.fillWait = await waitForExpectedFilledValue(page, testCase.expectedActiveStep);
    result.filledValues = result.fillWait.values || await values(page);
    recordStep(paths, result, `run_step:${testCase.expectedActiveStep}`, result.fillAction && result.fillAction.ok === false && result.fillAction.blocker
      ? "blocked"
      : "completed", {
      action: result.fillAction,
      wait: result.fillWait,
      values: result.filledValues
    });
    assertResult(result, result.fillWait && result.fillWait.ok,
      `step ${testCase.expectedActiveStep} did not settle expected values ${JSON.stringify(result.fillWait && result.fillWait.expected)}`);
    if (testCase.expectedActiveStep.includes("_username")) {
      assertResult(result, Object.values(result.filledValues).includes(ACCOUNT.username),
        "username step did not fill the generated username");
    }
    if (testCase.provider === "proton") {
      result.protonPasswordAction = await runStep(page, "fill_proton_password", testCase.provider);
      result.protonPasswordWait = await waitForExpectedFilledValue(page, "fill_proton_password");
      result.filledValues = await values(page);
      result.protonPlanSelection = await page.evaluate(() => ({
        free: Boolean(document.querySelector("#plan-free")?.checked),
        paid: Boolean(document.querySelector("#plan-paid")?.checked)
      }));
      assertResult(result, result.protonPlanSelection.free && !result.protonPlanSelection.paid,
        `Proton Free plan was not selected: ${JSON.stringify(result.protonPlanSelection)}`);
      assertResult(result, result.protonPasswordWait && result.protonPasswordWait.ok && Object.values(result.filledValues).includes(ACCOUNT.password),
        "Proton password fields were not filled after selecting the Free plan");
    }
    if (testCase.expectedActiveStep.includes("_name")) {
      assertResult(result, Object.values(result.filledValues).includes(ACCOUNT.firstName)
        || Object.values(result.filledValues).includes(`${ACCOUNT.firstName} ${ACCOUNT.lastName}`),
        "name step did not fill the generated name");
    }
    if (result.fillAction && result.fillAction.ok === false && result.fillAction.blocker) {
      result.blockerType = result.fillAction.blocker;
      result.blockerEvidence = result.fillAction.reason || testCase.expectedActiveStep;
    }
    await captureScreenshot(page, paths, result, "after-fill-step");

    recordStep(paths, result, "blocker_fixture_load", "started", { expectedBlockerStep: testCase.expectedBlockerStep });
    await page.setContent(testCase.blockerHtml, { waitUntil: "domcontentloaded" });
    const blockerScan = await scan(page);
    result.observedBlockerStep = blockerScan && blockerScan.activeStep;
    assertResult(result, result.observedBlockerStep === testCase.expectedBlockerStep,
      `expected blocker ${testCase.expectedBlockerStep}, got ${result.observedBlockerStep}`);
    recordStep(paths, result, "scan_blocker", result.observedBlockerStep === testCase.expectedBlockerStep ? "completed" : "failed", {
      expectedBlockerStep: testCase.expectedBlockerStep,
      observedBlockerStep: result.observedBlockerStep
    });
    await captureScreenshot(page, paths, result, "blocker-page");
    const blockerAction = await runStep(page, testCase.expectedBlockerStep, testCase.provider);
    result.blockerAction = blockerAction;
    assertResult(result, blockerAction && blockerAction.ok === false && blockerAction.blocker === "provider_challenge",
      "blocker step did not stop safely before real verification");
    result.blockerType = blockerAction && blockerAction.blocker ? blockerAction.blocker : result.blockerType;
    result.blockerEvidence = blockerAction && blockerAction.reason ? blockerAction.reason : result.blockerEvidence;
    recordStep(paths, result, `blocker_action:${testCase.expectedBlockerStep}`, blockerAction && blockerAction.ok === false && blockerAction.blocker === "provider_challenge"
      ? "blocked"
      : "failed", blockerAction || {});
  } catch (error) {
    result.errors.push(error && error.stack ? error.stack : String(error));
    recordStep(paths, result, "exception", "failed", {
      error: error && error.stack ? error.stack : String(error)
    });
  } finally {
    result.currentUrl = page.url();
    result.ok = result.errors.length === 0;
    result.finalStatus = result.ok ? "hard_blocker_recorded" : "fixture_failed";
    result.completenessPercentage = Math.round((result.completedSteps.length / 8) * 100);
    if (result.completenessPercentage > 100) result.completenessPercentage = 100;
    if (!result.ok) {
      result.nextRepairRecommendation = `Repair ${result.provider} selectors or expected step mapping: ${result.errors.join("; ")}`;
      result.selectorMisses = result.errors.filter((item) => /expected|not found|did not fill/i.test(item));
    } else {
      result.nextRepairRecommendation = "Fixture reached the configured verification boundary; live runs should stop here and record the provider blocker.";
    }
    await context.close();
    writeProviderReports(paths, result);
  }
  return result;
}

function writeReports(results, runRoot, runStamp) {
  fs.mkdirSync(runRoot, { recursive: true });
  const summaryJsonPath = path.join(runRoot, "summary.json");
  const summaryMdPath = path.join(runRoot, "summary.md");
  const summary = {
    runType: "mocked_fixture",
    checkedAt: isoNow(),
    runRoot,
    contentScript: CONTENT_JS,
    flowState: FLOW_STATE_JS,
    requiredProviderArtifacts: REQUIRED_PROVIDER_ARTIFACTS,
    totals: {
      providers: results.length,
      passed: results.filter((item) => item.ok).length,
      failed: results.filter((item) => !item.ok).length
    },
    providers: results.map((result) => ({
      provider: result.provider,
      runId: result.runId,
      finalStatus: result.finalStatus,
      completenessPercentage: result.completenessPercentage,
      startButtonAckStatus: result.startButtonAckStatus,
      blockerType: result.blockerType,
      observedActiveStep: result.observedActiveStep,
      observedBlockerStep: result.observedBlockerStep,
      errors: result.errors,
      reportDir: providerDirName(result.provider)
    }))
  };
  fs.writeFileSync(summaryJsonPath, JSON.stringify(summary, null, 2), "utf8");

  const summaryLines = [
    "# Extension Flow Run Summary",
    "",
    `Checked at: ${summary.checkedAt}`,
    `Run root: ${runRoot}`,
    "",
    "| Provider | ACK | Normal step | Blocker step | Status | Completeness |",
    "|---|---|---|---|---|---|"
  ];
  for (const result of results) {
    const ack = result.startButtonAckStatus && result.startButtonAckStatus.ack === "NM_START_AUTOPILOT_ACK" ? "ACK" : "NO ACK";
    summaryLines.push([
      result.provider,
      ack,
      `${result.observedActiveStep || "<none>"} / expected ${result.expectedActiveStep}`,
      `${result.observedBlockerStep || "<none>"} / expected ${result.expectedBlockerStep}`,
      result.ok ? "PASS" : "FAIL",
      `${result.completenessPercentage}%`
    ].join(" | ").replace(/^/, "| ").replace(/$/, " |"));
  }
  summaryLines.push("");
  summaryLines.push("This fixture uses mocked HTTPS pages and stops at real verification blockers. It does not create accounts or bypass CAPTCHA/SMS/OTP.");
  fs.writeFileSync(summaryMdPath, summaryLines.join("\n"), "utf8");

  fs.mkdirSync(DIAGNOSTICS_DIR, { recursive: true });
  const id = `foreign_provider_flow_fixture_${runStamp}`;
  const jsonPath = path.join(DIAGNOSTICS_DIR, `${id}.json`);
  const mdPath = path.join(DIAGNOSTICS_DIR, `${id}.md`);
  fs.writeFileSync(jsonPath, JSON.stringify({
    runType: "mocked_fixture",
    checkedAt: isoNow(),
    reportRoot: runRoot,
    contentScript: CONTENT_JS,
    flowState: FLOW_STATE_JS,
    totals: {
      providers: results.length,
      passed: results.filter((item) => item.ok).length,
      failed: results.filter((item) => !item.ok).length
    },
    results
  }, null, 2), "utf8");

  const lines = [
    "# Foreign Provider Flow Fixture",
    "",
    `Checked at: ${isoNow()}`,
    `Report root: ${runRoot}`,
    "",
    "| Provider | Normal step | Blocker step | Result | Notes |",
    "|---|---|---|---|---|"
  ];
  for (const result of results) {
    lines.push([
      result.provider,
      `${result.observedActiveStep || "<none>"} / expected ${result.expectedActiveStep}`,
      `${result.observedBlockerStep || "<none>"} / expected ${result.expectedBlockerStep}`,
      result.ok ? "PASS" : "FAIL",
      result.errors.join("; ").replace(/\|/g, "\\|") || "-"
    ].join(" | ").replace(/^/, "| ").replace(/$/, " |"));
  }
  lines.push("");
  lines.push("This fixture uses mocked HTTPS pages and stops at real verification blockers. It does not create accounts or bypass CAPTCHA/SMS/OTP.");
  fs.writeFileSync(mdPath, lines.join("\n"), "utf8");
  return { jsonPath, mdPath, runRoot, summaryJsonPath, summaryMdPath };
}

async function closeBrowserWithTimeout(browser) {
  try {
    await Promise.race([
      browser.close(),
      new Promise((resolve) => setTimeout(resolve, 5000))
    ]);
  } catch (error) {
    // The report has already been written; do not let Playwright cleanup mask the flow result.
  }
}

(async () => {
  const runStamp = stamp();
  const runRoot = path.join(FIXTURE_RUNS_DIR, runStamp);
  fs.mkdirSync(runRoot, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  let exitCode = 1;
  try {
    const results = [];
    for (const testCase of CASES) {
      // Run sequentially so any provider-specific failure is easy to read in the generated log.
      results.push(await runCase(browser, testCase, runRoot, runStamp));
    }
    const reports = writeReports(results, runRoot, runStamp);
    const failed = results.filter((item) => !item.ok);
    console.log(JSON.stringify({ ok: failed.length === 0, reports, failed }, null, 2));
    exitCode = failed.length ? 1 : 0;
  } finally {
    await closeBrowserWithTimeout(browser);
  }
  process.exit(exitCode);
})().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
