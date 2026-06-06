const fs = require("fs");
const path = require("path");

const PLAYWRIGHT_ENTRY = "E:\\Openclaw\\runtime\\node\\node_modules\\playwright\\index.js";
const { chromium } = require(PLAYWRIGHT_ENTRY);

const ROOT = path.resolve(__dirname, "..");
const REPORT_ROOT = path.join(ROOT, "reports", "provider-real-probes");

const PROVIDERS = {
  proton: {
    label: "Proton Mail",
    url: "https://account.proton.me/mail/signup"
  },
  gmx: {
    label: "GMX Mail",
    url: "https://signup.gmx.com/"
  },
  aol: {
    label: "AOL Mail",
    url: "https://login.aol.com/account/create"
  },
  zoho: {
    label: "Zoho Mail",
    url: "https://accounts.zoho.com/signup"
  },
  yandex: {
    label: "Yandex Mail",
    url: "https://passport.yandex.com/registration/mail"
  },
  mailcom: {
    label: "Mail.com",
    url: "https://service.mail.com/registration.html"
  },
  icloud: {
    label: "iCloud Mail",
    url: "https://appleid.apple.com/account"
  },
  mailru: {
    label: "Mail.ru",
    url: "https://account.mail.ru/signup?rf=auth.mail.ru&from=main"
  },
  naver: {
    label: "Naver Mail",
    url: "https://nid.naver.com/user2/join/agree"
  },
  kakao: {
    label: "Daum/Kakao Mail",
    url: "https://accounts.kakao.com/weblogin/create_account"
  },
  netease163: {
    label: "NetEase 163 Mail",
    url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=163mail"
  },
  netease126: {
    label: "NetEase 126 Mail",
    url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=126mail"
  },
  neteaseyeah: {
    label: "NetEase Yeah Mail",
    url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=yeah"
  },
  qq: {
    label: "QQ Mail",
    url: "https://ssl.zc.qq.com/v3/index-chs.html"
  },
  sina: {
    label: "Sina Mail",
    url: "https://mail.sina.com.cn/register/regmail.php"
  },
  sohu: {
    label: "Sohu Mail",
    url: "https://mail.sohu.com/reg/signup"
  },
  tutanota: {
    label: "Tuta Mail",
    url: "https://app.tuta.com/signup"
  }
};

const BLOCKER_PATTERNS = [
  ["captcha", /\b(captcha|recaptcha|hcaptcha|arkose|turnstile|challenge|verify you are human|press and hold)\b/i],
  ["phone_sms", /\b(phone|mobile|sms|text message|verification code|call me|number)\b/i],
  ["email_otp", /\b(email verification|one-time code|otp|check your email|verification email)\b/i],
  ["terms", /\b(terms|privacy policy|agree|consent)\b/i],
  ["app_password_or_imap", /\b(imap|pop3|app password|application password)\b/i],
  ["region_or_language_gate", /\b(country|region|language|locale)\b/i],
  ["age_or_birthdate", /\b(birth|birthday|date of birth|age)\b/i]
];

function stamp() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    "_",
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds())
  ].join("");
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function cleanText(value, max = 180) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, max);
}

function safeName(value) {
  return String(value || "provider").replace(/[^a-z0-9_-]+/gi, "_");
}

function parseArgs(argv) {
  const args = argv.slice(2);
  const selected = [];
  let headed = false;
  let timeoutMs = 30000;
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--headed") {
      headed = true;
    } else if (arg === "--timeout-ms") {
      timeoutMs = Number(args[index + 1] || timeoutMs);
      index += 1;
    } else if (arg === "--all") {
      selected.push(...Object.keys(PROVIDERS));
    } else if (arg === "--foreign") {
      selected.push(...Object.keys(PROVIDERS));
    } else if (arg.startsWith("--")) {
      throw new Error(`Unknown argument: ${arg}`);
    } else {
      selected.push(arg);
    }
  }
  const providers = [...new Set(selected.length ? selected : ["proton", "gmx", "aol"])]
    .filter((key) => PROVIDERS[key]);
  return { providers, headed, timeoutMs };
}

async function dismissCommonBanners(page) {
  const textCandidates = [
    "Accept all",
    "Accept",
    "I agree",
    "Agree",
    "Continue",
    "Reject all",
    "Decline"
  ];
  for (const text of textCandidates) {
    try {
      const locator = page.getByRole("button", { name: new RegExp(`^${text}$`, "i") }).first();
      if (await locator.isVisible({ timeout: 900 })) {
        await locator.click({ timeout: 1200 });
        await page.waitForTimeout(800);
        return cleanText(text);
      }
    } catch (_) {
      // Cookie banners vary per provider; probing continues without blocking.
    }
  }
  return "";
}

async function collectPageSnapshot(page) {
  return page.evaluate(() => {
    const clean = (value, max = 180) => String(value || "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, max);
    const visible = (node) => {
      if (!node || !node.getBoundingClientRect) return false;
      const style = window.getComputedStyle(node);
      if (!style || style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
      const rect = node.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    };
    const attrs = (node) => ({
      tag: node.tagName ? node.tagName.toLowerCase() : "",
      type: clean(node.getAttribute("type")),
      id: clean(node.getAttribute("id")),
      name: clean(node.getAttribute("name")),
      autocomplete: clean(node.getAttribute("autocomplete")),
      placeholder: clean(node.getAttribute("placeholder")),
      ariaLabel: clean(node.getAttribute("aria-label")),
      role: clean(node.getAttribute("role")),
      text: clean(node.innerText || node.value || node.getAttribute("value"))
    });
    const controls = Array.from(document.querySelectorAll("input, select, textarea, [role='combobox'], [role='checkbox']"))
      .filter(visible)
      .slice(0, 80)
      .map(attrs);
    const buttons = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit'], a[role='button'], a"))
      .filter(visible)
      .map((node) => ({
        tag: node.tagName ? node.tagName.toLowerCase() : "",
        type: clean(node.getAttribute("type")),
        id: clean(node.getAttribute("id")),
        name: clean(node.getAttribute("name")),
        href: clean(node.getAttribute("href"), 260),
        text: clean(node.innerText || node.value || node.getAttribute("aria-label"))
      }))
      .filter((item) => item.text || item.href)
      .slice(0, 100);
    const frames = Array.from(document.querySelectorAll("iframe"))
      .map((node) => ({
        src: clean(node.getAttribute("src"), 260),
        title: clean(node.getAttribute("title")),
        id: clean(node.getAttribute("id")),
        visible: visible(node)
      }))
      .slice(0, 50);
    const headings = Array.from(document.querySelectorAll("h1,h2,h3,[role='heading']"))
      .filter(visible)
      .map((node) => clean(node.innerText))
      .filter(Boolean)
      .slice(0, 40);
    return {
      title: document.title,
      url: location.href,
      headings,
      controls,
      buttons,
      frames,
      bodySample: clean(document.body ? document.body.innerText : "", 5000)
    };
  });
}

function classifyControl(control) {
  const haystack = [
    control.type,
    control.id,
    control.name,
    control.autocomplete,
    control.placeholder,
    control.ariaLabel,
    control.role,
    control.text
  ].join(" ").toLowerCase();
  if (/first|given|fname/.test(haystack)) return "first_name";
  if (/last|family|lname|surname/.test(haystack)) return "last_name";
  if (/full.?name|display.?name|real.?name/.test(haystack)) return "name";
  if (/user|login|mail|email|account|id/.test(haystack) && !/recovery|reserve|alternate/.test(haystack)) return "username";
  if (/password|passwd|pwd/.test(haystack)) return "password";
  if (/birth|birthday|dob|year|month|day|age/.test(haystack)) return "birthdate";
  if (/gender|sex/.test(haystack)) return "gender";
  if (/phone|mobile|tel/.test(haystack)) return "phone";
  if (/recovery|reserve|alternate/.test(haystack)) return "recovery";
  if (/check|agree|terms|privacy|consent/.test(haystack)) return "terms";
  return "unknown";
}

function summarize(provider, meta, snapshot, dismissedBanner, error) {
  const text = [
    snapshot && snapshot.url,
    snapshot && snapshot.title,
    snapshot && snapshot.headings && snapshot.headings.join(" "),
    snapshot && snapshot.bodySample,
    snapshot && snapshot.frames && snapshot.frames.map((item) => item.src).join(" ")
  ].filter(Boolean).join("\n");
  const blockers = BLOCKER_PATTERNS
    .filter(([, pattern]) => pattern.test(text))
    .map(([type]) => type);
  const controls = (snapshot && snapshot.controls ? snapshot.controls : []).map((control) => ({
    ...control,
    class: classifyControl(control)
  }));
  const classes = [...new Set(controls.map((item) => item.class).filter((item) => item !== "unknown"))];
  return {
    runType: "live_probe",
    provider,
    label: meta.label,
    sourceUrl: meta.url,
    finalUrl: snapshot ? snapshot.url : "",
    title: snapshot ? snapshot.title : "",
    probedAt: new Date().toISOString(),
    status: error ? "error" : "ok",
    error: error ? String(error.message || error) : "",
    dismissedBanner,
    observedClasses: classes,
    blockers,
    headings: snapshot ? snapshot.headings : [],
    controls,
    buttons: snapshot ? snapshot.buttons : [],
    frames: snapshot ? snapshot.frames : [],
    bodySample: snapshot ? snapshot.bodySample : ""
  };
}

function writeMarkdown(reportPath, records) {
  const lines = [
    "# Provider Real Signup Probe",
    "",
    `Generated: ${new Date().toISOString()}`,
    "",
    "| Provider | Status | Observed controls | Blockers | Final URL |",
    "| --- | --- | --- | --- | --- |"
  ];
  for (const record of records) {
    lines.push(`| ${record.provider} | ${record.status} | ${record.observedClasses.join(", ") || "-"} | ${record.blockers.join(", ") || "-"} | ${record.finalUrl || record.sourceUrl} |`);
  }
  for (const record of records) {
    lines.push("");
    lines.push(`## ${record.provider} - ${record.label}`);
    lines.push("");
    lines.push(`- Source: ${record.sourceUrl}`);
    lines.push(`- Final: ${record.finalUrl || ""}`);
    lines.push(`- Status: ${record.status}${record.error ? ` (${record.error})` : ""}`);
    lines.push(`- Dismissed banner: ${record.dismissedBanner || "-"}`);
    lines.push(`- Headings: ${record.headings.join(" | ") || "-"}`);
    lines.push(`- Observed control classes: ${record.observedClasses.join(", ") || "-"}`);
    lines.push(`- Blockers/signals: ${record.blockers.join(", ") || "-"}`);
    lines.push("");
    lines.push("Visible controls:");
    for (const control of record.controls.slice(0, 30)) {
      lines.push(`- ${control.class}: tag=${control.tag} type=${control.type || "-"} id=${control.id || "-"} name=${control.name || "-"} autocomplete=${control.autocomplete || "-"} label=${control.ariaLabel || control.placeholder || control.text || "-"}`);
    }
    lines.push("");
    lines.push("Visible buttons/links:");
    for (const button of record.buttons.slice(0, 30)) {
      lines.push(`- ${button.text || button.href}`);
    }
    if (record.frames.length) {
      lines.push("");
      lines.push("Frames:");
      for (const frame of record.frames) lines.push(`- ${frame.visible ? "visible" : "hidden"} ${frame.src || frame.title || frame.id}`);
    }
  }
  fs.writeFileSync(reportPath, `${lines.join("\n")}\n`, "utf8");
}

async function probeProvider(browser, runDir, provider, timeoutMs) {
  const meta = PROVIDERS[provider];
  const page = await browser.newPage({
    viewport: { width: 1365, height: 900 },
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
  });
  page.setDefaultTimeout(timeoutMs);
  let snapshot = null;
  let dismissedBanner = "";
  let error = null;
  try {
    await page.goto(meta.url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
    await page.waitForLoadState("networkidle", { timeout: Math.min(timeoutMs, 12000) }).catch(() => {});
    await page.waitForTimeout(1600);
    dismissedBanner = await dismissCommonBanners(page);
    snapshot = await collectPageSnapshot(page);
    const screenshotPath = path.join(runDir, `${safeName(provider)}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});
  } catch (caught) {
    error = caught;
    try {
      snapshot = await collectPageSnapshot(page);
    } catch (_) {
      snapshot = null;
    }
  } finally {
    await page.close().catch(() => {});
  }
  return summarize(provider, meta, snapshot, dismissedBanner, error);
}

async function main() {
  const { providers, headed, timeoutMs } = parseArgs(process.argv);
  ensureDir(REPORT_ROOT);
  const runId = stamp();
  const runDir = path.join(REPORT_ROOT, runId);
  ensureDir(runDir);

  const browser = await chromium.launch({ headless: !headed });
  const records = [];
  try {
    for (const provider of providers) {
      console.log(`[probe] ${provider}`);
      records.push(await probeProvider(browser, runDir, provider, timeoutMs));
    }
  } finally {
    await browser.close().catch(() => {});
  }

  const jsonPath = path.join(runDir, "summary.json");
  const mdPath = path.join(runDir, "summary.md");
  fs.writeFileSync(jsonPath, JSON.stringify({ runType: "live_probe", runId, providers, records }, null, 2), "utf8");
  writeMarkdown(mdPath, records);
  console.log(JSON.stringify({ runId, runDir, jsonPath, mdPath, count: records.length }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
