const MAX_LOGS = 1200;
const BUILTIN_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e";
const BACKGROUND_BUILD = "2026-05-25-live-runner-11";
const CREATED_ACCOUNTS_STORAGE_KEY = "ninjemailCreatedAccounts";
const CREDENTIAL_OUTPUT_DIR_STORAGE_KEY = "ninjemailCredentialOutputDir";
const WEB_UI_BASE_URL_STORAGE_KEY = "ninjemailWebUiBaseUrl";
const AUTORUN_ENABLED_STORAGE_KEY = "ninjemailAutoRunEnabled";
const AUTORUN_TAB_ID_STORAGE_KEY = "ninjemailAutoRunTabId";
const AUTORUN_STARTED_AT_STORAGE_KEY = "ninjemailAutoRunStartedAt";
const OAUTH_JOBS_STORAGE_KEY = "ninjemailOAuthJobs";
const OAUTH_ACTIVE_EMAIL_STORAGE_KEY = "ninjemailOAuthActiveEmail";
const OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY = "ninjemailOAuthActiveAccount";
const REGISTRATION_RUN_ID_STORAGE_KEY = "ninjemailRegistrationRunId";
const OAUTH_AUTHORIZE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize";
const OAUTH_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token";
const OAUTH_REDIRECT_URI = "http://localhost:8765";
const WEB_UI_BASE_URL = "http://127.0.0.1:7860";
const DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR = "C:\\Users\\XZXyuan\\Downloads";
const DEFAULT_CREDENTIAL_OUTPUT_DIR = "E:\\api获取（待跑通）\\20-邮箱服务\\ninjemail\\browser_extension\\邮箱凭证";
const AUTORUN_MAX_AGE_MS = 30 * 60 * 1000;
const START_ACK_TIMEOUT_MS = 5000;
const START_CONTENT_READY_TIMEOUT_MS = 18000;
const START_CONTENT_RETRY_DELAY_MS = 500;
const OAUTH_TOKEN_FETCH_TIMEOUT_MS = 15000;
const OAUTH_REDIRECT_WATCH_DELAY_MS = 18000;
const OAUTH_REDIRECT_RETRY_MAX = 2;
const WEB_UI_ACCOUNT_SAVE_TIMEOUT_MS = 12000;
const WEB_UI_CREDENTIAL_CHECK_TIMEOUT_MS = 8000;
const MICROSOFT_PROBLEM_AUTO_RETRY_MAX = 1;
const MICROSOFT_PROBLEM_AUTO_RETRY_DELAY_MS = 1400;
const CREDENTIAL_READY_FINAL_STATES = new Set(["account_home", "oauth_complete"]);
const OAUTH_SCOPES = [
  "offline_access",
  "openid",
  "profile",
  "https://graph.microsoft.com/User.Read",
  "https://graph.microsoft.com/Mail.Read"
];

const STATUS_TEXT = {
  idle: "待命",
  opening: "打开中",
  observing: "观察中",
  stopped: "已停止",
  manual_wait: "等待人工",
  blocked: "已阻塞",
  post_challenge: "验证后处理",
  done: "完成"
};
const DEFAULT_CLIENT_ID = BUILTIN_CLIENT_ID;

const PROVIDERS = {
  outlook: {
    key: "outlook",
    label: "Outlook 邮箱",
    domain: "outlook.com",
    url: "https://signup.live.com/signup?lic=1",
    hosts: ["signup.live.com", "login.live.com", "account.live.com", "account.microsoft.com"]
  },
  hotmail: {
    key: "hotmail",
    label: "Hotmail 邮箱",
    domain: "hotmail.com",
    url: "https://signup.live.com/signup?lic=1",
    hosts: ["signup.live.com", "login.live.com", "account.live.com", "account.microsoft.com"]
  },
  gmail: {
    key: "gmail",
    label: "Gmail 邮箱",
    domain: "gmail.com",
    url: "https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp",
    hosts: ["accounts.google.com"]
  },
  yahoo: {
    key: "yahoo",
    label: "Yahoo 邮箱",
    domain: "yahoo.com",
    url: "https://login.yahoo.com/account/create",
    hosts: ["login.yahoo.com"]
  },
  proton: { key: "proton", label: "Proton Mail", domain: "proton.me", url: "https://account.proton.me/mail/signup", hosts: ["account.proton.me", "signup.proton.me"] },
  gmx: { key: "gmx", label: "GMX Mail", domain: "gmx.com", url: "https://signup.gmx.com/", hosts: ["signup.gmx.com", "www.gmx.com"] },
  aol: { key: "aol", label: "AOL Mail", domain: "aol.com", url: "https://login.aol.com/account/create", hosts: ["login.aol.com", "signup.aol.com"] },
  zoho: { key: "zoho", label: "Zoho Mail", domain: "zohomail.com", url: "https://accounts.zoho.com/signup", hosts: ["accounts.zoho.com", "mail.zoho.com", "www.zoho.com"] },
  yandex: { key: "yandex", label: "Yandex Mail", domain: "yandex.com", url: "https://passport.yandex.com/registration/mail", hosts: ["passport.yandex.com", "passport.yandex.ru"] },
  mailcom: { key: "mailcom", label: "Mail.com", domain: "mail.com", url: "https://service.mail.com/registration.html", hosts: ["service.mail.com"] },
  icloud: { key: "icloud", label: "iCloud Mail", domain: "icloud.com", url: "https://appleid.apple.com/account", hosts: ["appleid.apple.com"] },
  mailru: { key: "mailru", label: "Mail.ru", domain: "mail.ru", url: "https://account.mail.ru/signup?rf=auth.mail.ru&from=main", hosts: ["account.mail.ru", "e.mail.ru"] },
  naver: { key: "naver", label: "Naver Mail", domain: "naver.com", url: "https://nid.naver.com/user2/join/agree", hosts: ["nid.naver.com"] },
  kakao: { key: "kakao", label: "Daum/Kakao Mail", domain: "daum.net", url: "https://accounts.kakao.com/weblogin/create_account", hosts: ["accounts.kakao.com"] },
  netease163: { key: "netease163", label: "163 Mail", domain: "163.com", url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=163mail", hosts: ["reg.email.163.com", "mail.163.com"] },
  netease126: { key: "netease126", label: "126 Mail", domain: "126.com", url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=126mail", hosts: ["reg.email.163.com", "mail.126.com"] },
  neteaseyeah: { key: "neteaseyeah", label: "Yeah.net Mail", domain: "yeah.net", url: "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=yeah", hosts: ["reg.email.163.com", "mail.yeah.net"] },
  qq: { key: "qq", label: "QQ Mail", domain: "qq.com", url: "https://ssl.zc.qq.com/v3/index-chs.html", hosts: ["ssl.zc.qq.com", "mail.qq.com"] },
  sina: { key: "sina", label: "Sina Mail", domain: "sina.com", url: "https://mail.sina.com.cn/register/regmail.php", hosts: ["mail.sina.com.cn"] },
  sohu: { key: "sohu", label: "Sohu Mail", domain: "sohu.com", url: "https://mail.sohu.com/reg/signup", hosts: ["mail.sohu.com"] },
  tutanota: { key: "tutanota", label: "Tutanota", domain: "tutanota.com", url: "https://app.tuta.com/signup", hosts: ["app.tuta.com", "app.tutanota.com"] }
};

const FREE_SMS_PROVIDER_CATALOG = [
  ["receive_sms_live", "https://receive-smss.live"],
  ["quackr", "https://quackr.io"],
  ["anonymsms", "https://anonymsms.com"],
  ["sms24_me", "https://sms24.me"],
  ["receive_sms_cc", "https://receive-sms.cc"],
  ["sms_receive_free", "https://www.free-sms-receive.com"],
  ["numtapper", "https://www.numtapper.com"],
  ["receivesms_it", "https://receivesms.it.com"],
  ["temporary_phone_number_io", "https://temporary-phone-number.io"],
  ["freephonenum", "https://freephonenum.com"],
  ["receive_sms_online_info", "https://receive-sms-online.info"],
  ["sms_online_co", "https://sms-online.co"],
  ["mytrashmobile", "https://www.mytrashmobile.com"],
  ["receive_sms_io", "https://receive-sms.io"],
  ["receive_sms_free_cc", "https://receive-sms-free.cc"],
  ["temporary_phone_number_com", "https://temporary-phone-number.com"],
  ["receivefreesms_net", "https://receivefreesms.net"],
  ["freeonlinephone_org", "https://www.freeonlinephone.org"],
  ["receivesms_net", "https://www.receivesms.net"],
  ["receivesmsonline_net", "https://www.receivesmsonline.net"],
  ["sms24_info", "https://sms24.info"]
];

function defaultSmsDiagnostics(
  status = "not_checked",
  reason = "waiting_for_web_ui_status",
  providerStatus = status,
  providerReason = reason
) {
  const providers = FREE_SMS_PROVIDER_CATALOG.map(([provider, url]) => ({
    provider,
    ok: false,
    status: providerStatus,
    reason: providerReason,
    url,
    route: "",
    latency_ms: "",
    numbers: "",
    requires_key: false,
    category: "free_temp_sms"
  }));
  return {
    status,
    source: "browser_extension_builtin",
    providers,
    diagnostic_primary: "",
    diagnostic_reason: reason,
    checked_at: "",
    ok_count: 0,
    total: providers.length,
    lastUpdatedAt: ""
  };
}

function defaultSmsUsage() {
  return {
    provider: "receive_sms_live",
    country: "USA",
    status: "idle",
    reason: "",
    numbers: [],
    selectedNumber: null,
    messages: [],
    codes: [],
    code: "",
    lastUpdatedAt: ""
  };
}

const state = {
  provider: "outlook",
  providerLabel: "Outlook 邮箱",
  status: "idle",
  statusText: STATUS_TEXT.idle,
  currentUrl: "",
  title: "",
  activeStep: "",
  blocker: null,
  rootCause: null,
  postChallengeState: "",
  finalState: "",
  steps: [],
  stepHistory: {},
  elements: {},
  frameReports: {},
  challengeFrames: [],
  services: {},
  smsDiagnostics: defaultSmsDiagnostics(),
  smsUsage: defaultSmsUsage(),
  logs: [],
  autoRunEnabled: false,
  autoRunTabId: null,
  autoRunStartedAt: 0,
  autoRunLastResumeSignature: "",
  autoRunLastCommandAt: 0,
  lastRegistrationTabId: null,
  autoRunControlVersion: 0,
  microsoftProblemAutoRetries: 0,
  microsoftProblemRestarting: false,
  startAck: null,
  credentialOutputDir: "",
  webUiBaseUrl: "",
  webUiHealth: {
    status: "unknown",
    ok: false,
    reason: "",
    checkedAt: "",
    url: WEB_UI_BASE_URL
  },
  credentialStatus: {},
  credentialValidation: {},
  auxiliaryMailbox: null,
  auxiliaryMailboxStatus: {},
  activeAccount: null,
  lastCreatedAccount: null,
  lastGeneratedAccount: null,
  registrationRunId: "",
  credentialLocks: {},
  oauthJobs: {},
  updatedAt: "",
  lastSignature: "",
  registrationCount: 0,
  registrationCompleted: 0,
  proxyExitIp: "",
  proxyExitCountry: "",
  proxyActiveStatus: "none" // none | checking | active | failed | direct
};
const activeWebUiControllers = new Set();

// ── 代理轮询引擎 ──
const proxyEngine = {
  proxies: [],                // 当前代理列表 ["http://ip:port", ...]
  health: {},                 // { url: { ok, failCount, cooldownUntil, latencyMs, lastCheck, successCount } }
  index: 0,                   // 轮询索引
  enabled: false,             // 是否启用代理轮询
  currentProxy: null,         // 当前正在使用的代理
  lastUsedProxy: null,        // 上一次注册使用的代理（避免连续重复）
  checkTimeoutMs: 3500,       // 快速预检超时（每条 URL）
  cooldownMs: 120000,         // 失败冷却 2 分钟（缩短，快速重试）
  maxFails: 2,                // 连续失败 2 次进入冷却
  maxRetries: 6,              // 每次注册最多尝试 6 个代理
  successCooldownMs: 300000,  // 注册成功后代理冷却 5 分钟
  _loadPromise: null,         // 防止并发加载
  _saveTimer: null,           // 健康状态持久化定时器
};

// ── 代理凭据存储（user:pass 认证）──
// Chrome proxy API 不支持 URL 内嵌认证，需要 webRequest.onAuthRequired 注入
const proxyCredentials = new Map(); // key: "host:port" → { username, password }

/**
 * 代理格式智能解析与标准化
 * 支持格式:
 *   host:port
 *   user:pass@host:port
 *   http://host:port
 *   socks5://host:port
 *   http://user:pass@host:port
 *   socks5://user:pass@host:port
 *   https://host:port
 *   socks4://host:port
 * 自动:
 *   - 去除 BOM、首尾空白、行内注释
 *   - 识别协议（无协议默认 http）
 *   - 提取 user:pass 认证信息
 *   - 校验 host 和 port 合法性
 *   - 输出标准化 URL: protocol://[user:pass@]host:port
 */
function normalizeProxyLine(raw) {
  if (!raw || typeof raw !== "string") return null;
  // 去 BOM + 首尾空白
  let line = raw.replace(/^\uFEFF/, "").trim();
  // 去行内注释 (# 或 // 但不能是 :// 协议分隔符)
  line = line.replace(/\s*(#.*)$/, "").replace(/(?<!:)\s*\/\/.*$/, "").trim();
  if (!line) return null;

  let protocol = "http";
  let auth = "";
  let hostPort = line;

  // 提取协议前缀
  const protoMatch = line.match(/^(https?|socks[45]?)\s*:\/\//i);
  if (protoMatch) {
    protocol = protoMatch[1].toLowerCase();
    // 标准化协议名
    if (protocol === "https") protocol = "http"; // HTTPS 代理仍然用 HTTP CONNECT
    hostPort = line.slice(protoMatch[0].length);
  }

  // 提取 user:pass@ 认证
  const authMatch = hostPort.match(/^([^@\s]+)@(.+)$/);
  if (authMatch) {
    auth = authMatch[1]; // user:pass
    hostPort = authMatch[2];
  }

  // ── IPWEB 等代理商格式: host:port:user:pass ──
  // 如果没有 user:pass@ 且 hostPort 有 4 段（以 : 分隔），
  // 且第 3、4 段不是纯数字（即不是 host:port 的一部分），
  // 则识别为 host:port:user:pass 格式
  if (!auth) {
    const colonParts = hostPort.split(":");
    if (colonParts.length === 4) {
      const maybePort = parseInt(colonParts[1], 10);\n      const maybeUser = colonParts[2].trim();
      const maybePass = colonParts[3].trim();
      // 第 2 段是端口号（1-65535），第 3 段非空且不是纯数字 → 确认为 host:port:user:pass
      if (maybePort >= 1 && maybePort <= 65535 && maybeUser && !/^\d+$/.test(maybeUser)) {
        hostPort = `${colonParts[0]}:${colonParts[1]}`;
        auth = `${maybeUser}:${maybePass}`;
      }
    }
  }

  // 解析 host:port
  // 支持 IPv6: [::1]:port 和常规 host:port
  let host, port;
  const ipv6Match = hostPort.match(/^\[([^\]]+)\]:(\d+)$/);
  if (ipv6Match) {
    host = ipv6Match[1];
    port = parseInt(ipv6Match[2], 10);
  } else {
    const parts = hostPort.split(":");
    if (parts.length !== 2) return null;
    host = parts[0].trim();
    port = parseInt(parts[1].trim(), 10);
  }

  // 校验
  if (!host || !port || port < 1 || port > 65535 || isNaN(port)) return null;
  // host 基本校验（IP 或域名）
  if (!/^[a-zA-Z0-9._\-:]+$/.test(host)) return null;
  // hostname 统一小写（避免重复匹配和凭据查找大小写不一致）
  host = host.toLowerCase();

  // 构建标准化 URL
  let normalized;
  if (auth) {
    normalized = `${protocol}://${auth}@${host}:${port}`;
    // 存储凭据供 onAuthRequired 使用
    proxyCredentials.set(`${host}:${port}`, (() => {
      const [username, ...passParts] = auth.split(":");
      return { username: decodeURIComponent(username), password: decodeURIComponent(passParts.join(":")) };
    })());
  } else {
    normalized = `${protocol}://${host}:${port}`;
  }

  return {
    normalized,
    protocol,
    host,
    port,
    username: auth ? decodeURIComponent(auth.split(":")[0]) : null,
    password: auth ? decodeURIComponent(auth.split(":").slice(1).join(":")) : null,
    original: raw.trim(),
  };
}

// ── 代理认证注入（webRequest.onAuthRequired）──
// 当代理返回 407 时自动注入 user:pass
try {
  chrome.webRequest.onAuthRequired.addListener(
    (details, callback) => {
      if (details.isProxy && proxyEngine.currentProxy) {
        const parsed = (() => {
          try { return new URL(proxyEngine.currentProxy); } catch (_) { return null; }
        })();
        if (parsed) {
          const cred = proxyCredentials.get(`${parsed.hostname}:${parsed.port}`);
          if (cred) {
            pushLog("OK", `[代理认证] 自动注入 ${cred.username}@${parsed.hostname}:${parsed.port}`);
            callback({ authCredentials: { username: cred.username, password: cred.password } });
            return;
          }
        }
      }
      callback({});
    },
    { urls: ["<all_urls>"] },
    ["asyncBlocking"]
  );
} catch (_) {
  // webRequest 权限不可用时静默跳过
}

// ── 健康状态持久化 ──
const PROXY_HEALTH_KEY = "proxyEngineHealth";
const PROXY_HEALTH_SAVE_INTERVAL = 30000; // 30 秒保存一次

function saveProxyHealth() {
  try {
    const compact = {};
    for (const [url, h] of Object.entries(proxyEngine.health)) {
      if (h && (h.failCount > 0 || h.successCount > 0)) {
        compact[url] = {
          ok: h.ok, failCount: h.failCount || 0, successCount: h.successCount || 0,
          cooldownUntil: h.cooldownUntil || 0, latencyMs: h.latencyMs || 0, lastCheck: h.lastCheck || 0,
        };
      }
    }
    chrome.storage.local.set({ [PROXY_HEALTH_KEY]: compact }).catch(() => {});
  } catch (_) {}
}

function loadProxyHealth() {
  try {
    chrome.storage.local.get(PROXY_HEALTH_KEY, (result) => {
      const saved = result[PROXY_HEALTH_KEY];
      if (saved && typeof saved === "object") {
        for (const [url, h] of Object.entries(saved)) {
          // 冷却已过期则自动恢复
          if (h.cooldownUntil && Date.now() >= h.cooldownUntil) {
            h.ok = true; h.failCount = 0; h.cooldownUntil = 0;
          }
          proxyEngine.health[url] = h;
        }
        pushLog("OK", `[代理] 已恢复 ${Object.keys(saved).length} 条健康记录`);
      }
    });
  } catch (_) {}
}

// 定期保存健康状态
function startHealthSaveTimer() {
  if (proxyEngine._saveTimer) clearInterval(proxyEngine._saveTimer);
  proxyEngine._saveTimer = setInterval(saveProxyHealth, PROXY_HEALTH_SAVE_INTERVAL);
}

function proxyIsAvailable(url) {
  const h = proxyEngine.health[url];
  if (!h) return true; // 未检测过的代理视为可用
  if (h.ok) return true;
  if (h.cooldownUntil && Date.now() >= h.cooldownUntil) {
    h.ok = true;
    h.failCount = 0;
    return true;
  }
  return false;
}

function proxyMarkFail(url, reason) {
  const h = proxyEngine.health[url] || { ok: true, failCount: 0, cooldownUntil: 0, latencyMs: 0, lastCheck: 0, successCount: 0 };
  h.failCount = (h.failCount || 0) + 1;
  h.lastCheck = Date.now();
  if (h.failCount >= proxyEngine.maxFails) {
    h.ok = false;
    h.cooldownUntil = Date.now() + proxyEngine.cooldownMs;
    pushLog("WARN", `[代理] ${urlShort(url)} 连续失败${h.failCount}次，冷却${proxyEngine.cooldownMs / 1000}秒`, { reason });
  }
  proxyEngine.health[url] = h;
}

function proxyMarkOk(url, latencyMs) {
  const h = proxyEngine.health[url] || { ok: true, failCount: 0, cooldownUntil: 0, latencyMs: 0, lastCheck: 0, successCount: 0 };
  h.ok = true;
  h.failCount = 0;
  h.cooldownUntil = 0;
  h.latencyMs = latencyMs || 0;
  h.lastCheck = Date.now();
  h.successCount = (h.successCount || 0) + 1;
  proxyEngine.health[url] = h;
}

// 注册成功后将代理置入冷却期，避免短期内重复使用
function proxyCooldownAfterSuccess(url) {
  if (!url) return;
  const h = proxyEngine.health[url] || { ok: true, failCount: 0, cooldownUntil: 0, latencyMs: 0, lastCheck: 0, successCount: 0 };
  h.ok = false;
  h.failCount = 0;
  h.cooldownUntil = Date.now() + proxyEngine.successCooldownMs;
  h.lastCheck = Date.now();
  proxyEngine.health[url] = h;
  pushLog("STEP", `[代理] ${urlShort(url)} 注册成功，进入冷却期 ${proxyEngine.successCooldownMs / 1000}s`, { cooldownMs: proxyEngine.successCooldownMs });
  saveProxyHealth();
}

function urlShort(url) {
  try {
    const u = new URL(url);
    return `${u.hostname}:${u.port}`;
  } catch (_) {
    return url;
  }
}

// ── 测试 URL 列表（备用，当前 quickCheckProxy 使用标签页预检） ──
const _CHECK_TEST_URLS = [
  "http://icanhazip.com",
  "http://httpbin.org/ip",
  "https://api.ipify.org?format=json",
];

async function quickCheckProxy(proxyUrl) {
  const start = Date.now();
  const h = proxyEngine.health[proxyUrl];

  // ── 快速信任路径 ──
  // 如果后端刚检测过（<5 分钟内通过），直接信任，跳过扩展端预检
  // 因为 MV3 service worker 的 fetch() 不一定走 chrome.proxy.settings
  // 在 service worker 里预检代理本身不可靠
  if (h && h.ok && h.lastCheck && (Date.now() - h.lastCheck < 300000)) {
    return { ok: true, latencyMs: h.latencyMs || 0, error: "", trusted: true };
  }

  // ── 临时标签页预检路径 ──
  // 创建一个隐藏的标签页，通过代理加载测试页面来验证代理是否真正可用
  // 这比 service worker fetch 可靠得多，因为标签页的网络请求一定会走 chrome.proxy.settings
  const parsed = parseProxyUrl(proxyUrl);
  let result;

  try {
    // 先设置代理
    await new Promise((resolve, reject) => {
      chrome.proxy.settings.set({
        value: {
          mode: "fixed_servers",
          rules: {
            singleProxy: parsed,
            bypassList: ["localhost", "127.0.0.1"]
          }
        }
      }, () => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve();
      });
    });

    // ★ 创建临时测试标签页（HTTP 即可验证代理连通性，HTTP 通则 HTTPS 也通）
    const testTab = await new Promise((resolve) => {
      chrome.tabs.create({ url: "http://icanhazip.com", active: false }, (tab) => resolve(tab));
    });

    if (!testTab || !testTab.id) {
      result = { ok: false, latencyMs: Date.now() - start, error: "failed_to_create_test_tab" };
    } else {
      // 等待标签页加载完成（最多 checkTimeoutMs）
      const loaded = await new Promise((resolve) => {
        let done = false;
        const listener = (tabId, changeInfo) => {
          if (tabId === testTab.id && changeInfo.status === "complete") {
            done = true;
            chrome.tabs.onUpdated.removeListener(listener);
            resolve(true);
          }
        };
        chrome.tabs.onUpdated.addListener(listener);
        setTimeout(() => {
          if (!done) {
            chrome.tabs.onUpdated.removeListener(listener);
            resolve(false);
          }
        }, proxyEngine.checkTimeoutMs);
      });

      const latencyMs = Date.now() - start;

      // 检查标签页是否成功加载
      if (loaded) {
        try {
          const finalTab = await new Promise((resolve) => {
            chrome.tabs.get(testTab.id, (t) => resolve(t));
          });
          // 如果 URL 包含错误页面标识，说明加载失败
          const tabUrl = (finalTab && finalTab.url) || "";
          if (tabUrl.includes("chrome-error") || tabUrl.includes("net::")) {
            result = { ok: false, latencyMs, error: "page_load_error" };
          } else {
            result = { ok: true, latencyMs, error: "" };
          }
        } catch (_) {
          result = { ok: true, latencyMs, error: "" };
        }
      } else {
        result = { ok: false, latencyMs, error: "timeout" };
      }

      // 关闭临时标签页
      try { chrome.tabs.remove(testTab.id, () => {}); } catch (_) {}
    }
  } catch (err) {
    result = { ok: false, latencyMs: Date.now() - start, error: String(err.message || err) };
  }

  // 恢复直连（清除代理设置，等待 applyProxy 重新设置）
  await clearProxy();

  return result;
}

function parseProxyUrl(proxyUrl) {
  try {
    const u = new URL(proxyUrl);
    const scheme = u.protocol.replace(":", "");
    return {
      scheme: (scheme === "socks5" || scheme === "socks4") ? scheme : "http",
      host: u.hostname,
      port: parseInt(u.port, 10)
    };
  } catch (_) {
    return { scheme: "http", host: "127.0.0.1", port: 8080 };
  }
}

async function clearProxy() {
  return new Promise((resolve) => {
    chrome.proxy.settings.clear({ scope: "regular" }, () => {
      if (chrome.runtime.lastError) {
        pushLog("WARN", `[代理] 清除代理设置失败: ${chrome.runtime.lastError.message}`);
      }
      resolve();
    });
  });
}

// ★ 根据当前代理引擎状态刷新 proxyActiveStatus（导入/检测后也要刷新，不仅仅在注册时）
function refreshProxyActiveStatus() {
  // 如果正在注册中（active/checking/failed/direct 由 startAutopilot 管理），不要覆盖
  const inFlight = ["active", "checking", "failed", "direct"];
  if (state.autoRunEnabled && inFlight.includes(state.proxyActiveStatus)) {
    console.log("[refreshProxyActiveStatus] SKIP: autoRun+inFlight", state.proxyActiveStatus);
    return;
  }
  
  console.log("[refreshProxyActiveStatus] enabled:", proxyEngine.enabled, "proxies:", proxyEngine.proxies.length, "health:", Object.keys(proxyEngine.health).length);
  
  if (!proxyEngine.enabled || proxyEngine.proxies.length === 0) {
    state.proxyActiveStatus = "none";
    console.log("[refreshProxyActiveStatus] → none");
    return;
  }
  
  const healthyCount = proxyEngine.proxies.filter(p => {
    const h = proxyEngine.health[p];
    return h && h.status === "healthy" && (!h.cooldownUntil || h.cooldownUntil < Date.now());
  }).length;
  
  if (healthyCount > 0) {
    state.proxyActiveStatus = "ready";
    console.log("[refreshProxyActiveStatus] → ready (healthy:", healthyCount, ")");
  } else {
    state.proxyActiveStatus = "idle";
    console.log("[refreshProxyActiveStatus] → idle (healthy:", healthyCount, ")");
  }
}

async function applyProxy(proxyUrl) {
  // 使用 PAC 模式（比 fixed_servers 在 MV3 中更可靠）
  // PAC 强制所有 HTTP/HTTPS 流量走代理
  const parsed = parseProxyUrl(proxyUrl);
  // ★ PAC 指令必须大写: PROXY / SOCKS5 / SOCKS / DIRECT
  const pacDirective = parsed.scheme === "http"
    ? "PROXY"
    : parsed.scheme === "socks5"
      ? "SOCKS5"
      : parsed.scheme === "socks4"
        ? "SOCKS"
        : parsed.scheme.toUpperCase();
  const pacEntry = `${pacDirective} ${parsed.host}:${parsed.port}`;
  const pacScript = `function FindProxyForURL(u,h){return "${pacEntry}";}`;

  // 第一步：设置代理
  await new Promise((resolve, reject) => {
    chrome.proxy.settings.set({
      value: { mode: "pac_script", pacScript },
    }, () => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        proxyEngine.currentProxy = proxyUrl;
        pushLog("OK", `[代理] PAC 模式已设置: ${pacEntry}`, { proxyUrl, pacDirective, scheme: parsed.scheme });
        resolve();
      }
    });
  });

  // 第二步：★ 等待短暂延迟让网络栈应用设置，然后验证
  await delay(200);
  try {
    const current = await new Promise((res) => {
      chrome.proxy.settings.get({ incognito: false }, (details) => res(details));
    });
    if (current && current.value) {
      const mode = current.value.mode;
      const actualScript = current.value.pacScript || "";
      if (mode === "pac_script" && actualScript.includes(pacEntry)) {
        pushLog("OK", `[代理] 设置已验证: mode=${mode}, PAC含 "${pacEntry}" ✅`, { levelOfControl: current.levelOfControl });
      } else {
        pushLog("WARN", `[代理] ⚠ 设置可能未生效! mode=${mode}, 期望pac_script含"${pacEntry}", levelOfControl=${current.levelOfControl}`, {
          mode, levelOfControl: current.levelOfControl, actualScriptPreview: actualScript.substring(0, 120)
        });
        // 如果 mode 是 system 或其他扩展覆盖了，尝试用 fixed_servers 回退
        if (mode !== "pac_script") {
          pushLog("WARN", `[代理] 检测到代理被覆盖 (mode=${mode})，尝试 fixed_servers 回退`);
          await new Promise((resolve, reject) => {
            chrome.proxy.settings.set({
              value: {
                mode: "fixed_servers",
                rules: {
                  singleProxy: parsed,
                  bypassList: ["localhost", "127.0.0.1"]
                }
              },
            }, () => {
              if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
              else resolve();
            });
          });
          pushLog("OK", `[代理] fixed_servers 回退已设置: ${parsed.scheme}://${parsed.host}:${parsed.port}`);
        }
      }
    }
  } catch (e) {
    pushLog("WARN", `[代理] 验证设置异常: ${e.message || e}`);
  }
}

async function verifyProxy(tabId) {
  // 在注册页加载后，通过 content script 验证出口 IP
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: async () => {
        try {
          const r = await fetch("https://ipapi.co/json/", { cache: "no-store" });
          const d = await r.json();
          return { ok: true, ip: d.ip || "", country: d.country_name || d.country_code || "" };
        } catch (e) {
          // fallback to ipify
          try {
            const r2 = await fetch("https://api.ipify.org?format=json", { cache: "no-store" });
            const d2 = await r2.json();
            return { ok: true, ip: d2.ip || "", country: "" };
          } catch (e2) {
            return { ok: false, error: String(e2.message || e2) };
          }
        }
      },
      world: "MAIN",
    });
    if (results && results[0] && results[0].result) {
      return results[0].result;
    }
  } catch (_) {}
  return { ok: false, error: "script_inject_failed" };
}

async function verifyProxyWithGeo(tabId) {
  // 验证代理出口 IP 并获取国家信息
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: async () => {
        try {
          const r = await fetch("https://ipapi.co/json/", { cache: "no-store" });
          const d = await r.json();
          return { ok: true, ip: d.ip || "", country: d.country_name || "", countryCode: d.country_code || "", org: d.org || "" };
        } catch (e) {
          try {
            const r2 = await fetch("https://api.ipify.org?format=json", { cache: "no-store" });
            const d2 = await r2.json();
            return { ok: true, ip: d2.ip || "", country: "", countryCode: "" };
          } catch (e2) {
            return { ok: false, error: String(e2.message || e2) };
          }
        }
      },
      world: "MAIN",
    });
    if (results && results[0] && results[0].result) {
      return results[0].result;
    }
  } catch (_) {}
  return { ok: false, error: "script_inject_failed" };
}

function getNextHealthyProxy() {
  const total = proxyEngine.proxies.length;
  if (!total) return null;

  // 从当前 index 开始轮询，只对"找到可用代理"时递增 index
  let checked = 0;
  while (checked < total) {
    const idx = (proxyEngine.index + checked) % total;
    const url = proxyEngine.proxies[idx];
    if (proxyIsAvailable(url)) {
      // 只在找到可用代理时才推进 index，避免跳过冷却中的代理
      proxyEngine.index = (idx + 1) % total;
      return url;
    }
    checked++;
  }

  // 所有代理都在冷却，重置所有冷却状态并强制重试
  pushLog("WARN", "[代理] 所有代理都在冷却期，强制重置并重试");
  for (const url of proxyEngine.proxies) {
    proxyEngine.health[url] = { ok: true, failCount: 0, cooldownUntil: 0, latencyMs: 0, lastCheck: 0, successCount: (proxyEngine.health[url] || {}).successCount || 0 };
  }
  proxyEngine.index = 0;
  return proxyEngine.proxies[0] || null;
}

async function rotateProxyForRegistration(targetUrl) {
  if (!proxyEngine.enabled || !proxyEngine.proxies.length) {
    await clearProxy();
    proxyEngine.currentProxy = null;
    return { proxy: null, skipped: true };
  }

  // ★ 优先跳过上次使用的代理，确保每次注册用不同代理
  const skipProxy = proxyEngine.lastUsedProxy;
  const healthyCount = proxyEngine.proxies.filter(p => proxyIsAvailable(p)).length;

  // 循环尝试多个代理，最多 maxRetries 次
  const maxRetries = Math.min(proxyEngine.maxRetries, proxyEngine.proxies.length);
  const tried = new Set();

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    let proxy = getNextHealthyProxy();
    if (!proxy) {
      break;
    }

    // ★ 如果选到了上次用过的代理，且还有其他健康代理可用，再取下一个
    if (proxy === skipProxy && healthyCount > 1) {
      proxy = getNextHealthyProxy();
      if (!proxy) break;
    }

    // 避免重复尝试同一个代理
    if (tried.has(proxy)) {
      // 再往后找一个
      const altIdx = (proxyEngine.index) % proxyEngine.proxies.length;
      proxyEngine.index = (altIdx + 1) % proxyEngine.proxies.length;
      continue;
    }
    tried.add(proxy);

    pushLog("STEP", `[代理] 预检 ${urlShort(proxy)} (${attempt + 1}/${maxRetries})`, { proxy, targetUrl });
    const check = await quickCheckProxy(proxy);

    if (check.ok) {
      proxyMarkOk(proxy, check.latencyMs);
      await applyProxy(proxy);
      // ★ 记录本次使用的代理，供下次轮转时跳过
      proxyEngine.lastUsedProxy = proxy;
      pushLog("OK", `[代理] 已切换到 ${urlShort(proxy)} (延迟 ${check.latencyMs}ms)`, { proxy, latencyMs: check.latencyMs });
      return { proxy, latencyMs: check.latencyMs, attempt: attempt + 1 };
    }

    // 预检失败，标记并跳到下一个
    proxyMarkFail(proxy, check.error);
    pushLog("WARN", `[代理] ${urlShort(proxy)} 预检失败: ${check.error}，跳过`, { proxy, error: check.error });
  }

  // 所有尝试都失败，使用直连
  await clearProxy();
  proxyEngine.currentProxy = null;
  pushLog("BLOCK", `[代理] 尝试了 ${tried.size} 个代理均失败，回退直连`, { tried: [...tried].map(urlShort) });
  return { proxy: null, reason: "all_proxies_failed", tried: tried.size };
}

async function loadProxyEngine() {
  if (proxyEngine._loadPromise) return proxyEngine._loadPromise;
  proxyEngine._loadPromise = (async () => {
    try {
      // 先恢复持久化的健康状态
      loadProxyHealth();
      startHealthSaveTimer();

      // 从 chrome.storage.local 加载已保存的代理（不依赖外部后端）
      try {
        const result = await chrome.storage.local.get("savedProxyText");
        const content = (result.savedProxyText || "").trim();
        // ★ 启动时也做标准化
        const rawLines = content ? content.split(/[\r\n]+/) : [];
        const normalizedLines = [];
        const seen = new Set();
        for (const raw of rawLines) {
          const r = normalizeProxyLine(raw);
          if (r && !seen.has(r.normalized)) {
            seen.add(r.normalized);
            normalizedLines.push(r.normalized);
          }
        }
        if (normalizedLines.length > 0) {
          proxyEngine.proxies = normalizedLines;
          proxyEngine.enabled = true;
          // 回写标准化版本（如果不同）
          const normalizedText = normalizedLines.join("\n");
          if (normalizedText !== content) {
            await chrome.storage.local.set({ savedProxyText: normalizedText });
          }
          const authCount = normalizedLines.filter(l => { try { return !!new URL(l).username; } catch (_) { return false; } }).length;
          pushLog("OK", `[代理] 已加载 ${normalizedLines.length} 个代理（健康记录: ${Object.keys(proxyEngine.health).length} 条${authCount ? `，含认证${authCount}个` : ""}）`, { count: normalizedLines.length });
        } else {
          pushLog("WARN", "[代理] 无已保存的代理，请在侧边栏粘贴代理列表");
        }
      } catch (_) {
        pushLog("WARN", "[代理] 加载代理失败");
      }
    } catch (err) {
      pushLog("WARN", `[代理] 加载代理失败: ${err.message || err}`);
    }
    proxyEngine._loadPromise = null;
  })();
  return proxyEngine._loadPromise;
}

function abortBackgroundOperations() {
  for (const controller of activeWebUiControllers) {
    try {
      controller.__ninjemailStopAbort = true;
      controller.abort();
    } catch (error) {
      // Controllers are best-effort; stale ones are removed by postWebUiApi.
    }
  }
  activeWebUiControllers.clear();
}

function secureRandomBytes(length) {
  const source = globalThis.crypto || globalThis.msCrypto;
  if (!source || typeof source.getRandomValues !== "function") {
    throw new Error("secure_random_unavailable");
  }
  const values = new Uint8Array(length);
  source.getRandomValues(values);
  return values;
}

function secureRandomInt(min, max) {
  const low = Math.ceil(Number(min));
  const high = Math.floor(Number(max));
  const range = Math.max(1, high - low + 1);
  const maxUint32 = 0xffffffff;
  const limit = maxUint32 - (maxUint32 % range);
  const values = new Uint32Array(1);
  const source = globalThis.crypto || globalThis.msCrypto;
  if (!source || typeof source.getRandomValues !== "function") {
    throw new Error("secure_random_unavailable");
  }
  do {
    source.getRandomValues(values);
  } while (values[0] >= limit);
  return low + (values[0] % range);
}

function randomHex(length) {
  const values = secureRandomBytes(Math.ceil(length / 2));
  return Array.from(values, (value) => value.toString(16).padStart(2, "0")).join("").slice(0, length);
}

function randomBase64Url(byteLength = 32) {
  const values = secureRandomBytes(byteLength);
  return base64Url(values);
}

function base64Url(value) {
  const bytes = value instanceof ArrayBuffer ? new Uint8Array(value) : value;
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

async function sha256Base64Url(value) {
  const bytes = new TextEncoder().encode(String(value || ""));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return base64Url(digest);
}

function parseJwtPayload(token = "") {
  try {
    const part = String(token || "").split(".")[1] || "";
    const padded = part.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - part.length % 4) % 4);
    return JSON.parse(atob(padded));
  } catch (error) {
    return {};
  }
}

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December"
];

function randomInt(min, max) {
  return secureRandomInt(min, max);
}

const FIRST_NAMES = [
  "Aiden", "Amelia", "Andrew", "Avery", "Blake", "Brooke", "Caleb", "Carter",
  "Chloe", "Claire", "Connor", "Dylan", "Eleanor", "Elliot", "Emma", "Ethan",
  "Evan", "Grace", "Hannah", "Harper", "Hazel", "Henry", "Ian", "Iris",
  "Isaac", "Isla", "Jack", "Jade", "James", "Jenna", "Julian", "Kara",
  "Landon", "Leah", "Leo", "Lily", "Logan", "Lucas", "Mason", "Maya",
  "Mia", "Miles", "Naomi", "Nolan", "Nora", "Owen", "Parker", "Paige",
  "Quinn", "Reese", "Riley", "Rowan", "Ruby", "Ryan", "Sadie", "Samuel",
  "Sarah", "Sienna", "Sofia", "Theo", "Tyler", "Violet", "Wyatt", "Zoe"
];

const LAST_NAMES = [
  "Adams", "Allen", "Bailey", "Baker", "Bennett", "Brooks", "Carter", "Clark",
  "Coleman", "Collins", "Cooper", "Davis", "Diaz", "Edwards", "Evans", "Fisher",
  "Flores", "Foster", "Garcia", "Gray", "Green", "Hall", "Harris", "Hayes",
  "Henderson", "Hill", "Howard", "Hughes", "Jackson", "James", "Jenkins", "Johnson",
  "Kelly", "King", "Lewis", "Long", "Martin", "Mitchell", "Morgan", "Morris",
  "Murphy", "Nelson", "Parker", "Perez", "Phillips", "Price", "Reed", "Rivera",
  "Roberts", "Ross", "Russell", "Sanchez", "Scott", "Stewart", "Taylor", "Thomas",
  "Turner", "Walker", "Ward", "Watson", "White", "Williams", "Wilson", "Young"
];

function randomChoice(items) {
  return items[randomInt(0, items.length - 1)];
}

function randomChars(alphabet, length) {
  let text = "";
  for (let index = 0; index < length; index += 1) {
    text += alphabet[randomInt(0, alphabet.length - 1)];
  }
  return text;
}

function randomAccountUsername(name = {}) {
  const first = String(name.firstName || randomChoice(FIRST_NAMES)).toLowerCase().replace(/[^a-z]/g, "");
  const last = String(name.lastName || randomChoice(LAST_NAMES)).toLowerCase().replace(/[^a-z]/g, "");
  const style = randomInt(0, 4);
  const suffix = randomChars("abcdefghijklmnopqrstuvwxyz0123456789", randomInt(12, 16));
  const chunks = [
    `${first.slice(0, randomInt(3, Math.min(7, first.length)))}${last.slice(0, randomInt(2, Math.min(6, last.length)))}`,
    `${last.slice(0, randomInt(4, Math.min(8, last.length)))}${first.slice(0, randomInt(2, Math.min(5, first.length)))}`,
    `mx${randomChars("abcdefghijklmnopqrstuvwxyz", 2)}${randomChars("0123456789", 2)}`,
    `${first.charAt(0)}${last}${randomChars("abcdefghijklmnopqrstuvwxyz", 2)}`,
    `${first}${randomChars("0123456789", randomInt(2, 4))}`
  ];
  return `${chunks[style]}${suffix}`.slice(0, 30);
}

function randomPassword(length = 18) {
  const lower = "abcdefghijkmnopqrstuvwxyz";
  const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
  const digits = "23456789";
  const symbols = "!@#$%^&*_-+=";
  const alphabet = lower + upper + digits + symbols;
  const chars = [
    randomChars(upper, 1),
    randomChars(lower, 1),
    randomChars(digits, 1),
    randomChars(symbols, 1)
  ];
  while (chars.length < length) chars.push(randomChars(alphabet, 1));
  for (let index = chars.length - 1; index > 0; index -= 1) {
    const swap = randomInt(0, index);
    [chars[index], chars[swap]] = [chars[swap], chars[index]];
  }
  return chars.join("");
}

function randomAccountName() {
  return {
    firstName: randomChoice(FIRST_NAMES),
    lastName: randomChoice(LAST_NAMES)
  };
}

function randomAdultBirthday() {
  const now = new Date();
  const latestYear = now.getFullYear() - 19;
  const earliestYear = now.getFullYear() - 46;
  const year = randomInt(earliestYear, latestYear);
  const monthIndex = randomInt(0, 11);
  const maxDay = new Date(year, monthIndex + 1, 0).getDate();
  const day = randomInt(1, maxDay);
  return {
    birthMonth: MONTH_NAMES[monthIndex],
    birthDay: String(day),
    birthYear: String(year)
  };
}

function providerConfig(provider = state.provider) {
  return PROVIDERS[provider] || PROVIDERS.outlook;
}

function selectedProviderForUrl(url = "") {
  const host = (() => {
    try {
      return new URL(url).hostname;
    } catch (error) {
      return "";
    }
  })();
  const selected = providerConfig(state.provider);
  if ((selected.hosts || []).some((candidate) => host === candidate || host.endsWith(`.${candidate}`))) {
    return selected.key;
  }
  for (const item of Object.values(PROVIDERS)) {
    if (item.hosts.some((candidate) => host === candidate || host.endsWith(`.${candidate}`))) {
      if ((item.key === "hotmail" || item.key === "outlook") && state.provider === "hotmail") return "hotmail";
      if (item.key !== "hotmail") return item.key;
    }
  }
  return state.provider || "outlook";
}

function preserveMicrosoftDomainProvider(incomingProvider, url = "") {
  const incoming = String(incomingProvider || "").trim();
  if (incoming !== "outlook") return incoming;
  const lowerUrl = String(url || "").toLowerCase();
  const activeDomain = String(state.activeAccount?.domain || state.lastGeneratedAccount?.domain || "").toLowerCase();
  if (
    (state.provider === "hotmail" || activeDomain === "hotmail.com")
    && (lowerUrl.includes("live.com") || lowerUrl.includes("microsoft.com"))
  ) {
    return "hotmail";
  }
  return incoming;
}

function setSelectedProvider(provider) {
  const config = providerConfig(provider);
  state.provider = config.key;
  state.providerLabel = config.label;
  resetProviderRuntimeState("provider_switch");
  try {
    chrome.storage.local.set({ ninjemailProvider: config.key });
  } catch (error) {
    // Storage can be unavailable during extension reload.
  }
  pushDedupeLog("OK", `已选择注册方式：${config.label}`, {
    provider: config.key,
    domain: config.domain
  });
  setStatus("idle");
}

function resetProviderRuntimeState(reason = "provider_reset") {
  state.frameReports = {};
  state.challengeFrames = [];
  state.steps = [];
  state.stepHistory = {};
  state.blocker = null;
  state.rootCause = null;
  state.activeStep = "";
  state.postChallengeState = "";
  state.finalState = "";
  state.elements = {};
  state.startAck = null;
  state.autoRunLastResumeSignature = "";
  state.autoRunLastCommandAt = 0;
  if (reason === "start_autopilot") {
    state.currentUrl = "";
    state.title = "";
  }
}

function generatedOutlookAccount(provider = state.provider) {
  const config = providerConfig(provider);
  const birthday = randomAdultBirthday();
  const name = randomAccountName();
  const username = randomAccountUsername(name);
  return {
    username,
    provider: config.key,
    domain: config.domain,
    email: `${username}@${config.domain}`,
    password: randomPassword(),
    clientId: DEFAULT_CLIENT_ID,
    ...name,
    country: "United States",
    ...birthday
  };
}

function summarizeAccountForLog(account = {}) {
  const email = normalizeEmail(account.email);
  const password = String(account.password || "");
  const username = String(account.username || (email ? email.split("@", 1)[0] : ""));
  const provider = String(account.provider || state.provider || "outlook");
  const domain = String(account.domain || (email.includes("@") ? email.split("@")[1] : ""));
  const clientId = String(account.clientId || account.client_id || BUILTIN_CLIENT_ID);
  return {
    email,
    password,
    username,
    provider,
    domain,
    clientId
  };
}

function accountLogDetails(account = {}, extra = {}) {
  const summary = summarizeAccountForLog(account);
  const clientId = extra.client_id || extra.clientId || account.clientId || account.client_id || BUILTIN_CLIENT_ID;
  const refreshToken = extra.refresh_token || extra.refreshToken || account.refreshToken || account.refresh_token || "";
  const details = {
    ...extra,
    ...summary
  };
  if (summary.email && summary.password) {
    details.combo = `${summary.email}----${summary.password}`;
  }
  if (summary.email && summary.password && refreshToken) {
    details.client_id = clientId;
    details.refresh_token = refreshToken;
    details.combo = `${summary.email}----${summary.password}----${clientId}----${refreshToken}`;
  }
  return details;
}

function accountLogMessage(prefix, account = {}) {
  const summary = summarizeAccountForLog(account);
  return `${prefix} | 账号=${summary.email || "<empty>"} | 密码=${summary.password || "<empty>"} | 用户名=${summary.username || "<empty>"} | provider=${summary.provider} | domain=${summary.domain || "<empty>"}`;
}

function credentialLock(email = "") {
  return state.credentialLocks[normalizeEmail(email)] || null;
}

function setCredentialLock(email, patch = {}) {
  const key = normalizeEmail(email);
  if (!key) return null;
  const next = {
    ...(state.credentialLocks[key] || {}),
    ...patch,
    email: key,
    updatedAt: nowIso()
  };
  state.credentialLocks[key] = next;
  return next;
}

function isCredentialLocked(email, force = false) {
  if (force) return false;
  const lock = credentialLock(email);
  return Boolean(lock && ["token_pending", "saving", "done"].includes(lock.status));
}

function tokenAccountFromTokens(tokens = {}) {
  const claims = parseJwtPayload(tokens.id_token || "");
  for (const key of ["preferred_username", "email", "upn", "unique_name"]) {
    if (claims[key]) return normalizeEmail(claims[key]);
  }
  return "";
}

function isPersonalMicrosoftEmail(email = "") {
  return /@(outlook|hotmail|live|msn)\./i.test(String(email || ""));
}

function rememberGeneratedAccount(account = {}) {
  const email = normalizeEmail(account.email);
  if (!email || !account.password) return;
  const record = {
    provider: account.provider || state.provider || "outlook",
    domain: account.domain || "",
    username: account.username || email.split("@", 1)[0],
    email,
    password: account.password,
    clientId: account.clientId || account.client_id || DEFAULT_CLIENT_ID,
    registrationRunId: account.registrationRunId || state.registrationRunId || "",
    birthMonth: account.birthMonth || "",
    birthDay: account.birthDay || "",
    birthYear: account.birthYear || "",
    savedAt: nowIso()
  };
  state.lastGeneratedAccount = record;
  state.activeAccount = record;
  chrome.storage.local.set({ ninjemailGeneratedAccount: record, ninjemailActiveAccount: record }, () => {
    void chrome.runtime.lastError;
  });
  pushDedupeLog("STEP", "已缓存当前自动生成账号", {
    email: record.email,
    provider: record.provider
  });
  pushDedupeLog("ACCOUNT", accountLogMessage("自动生成账号已缓存", record), accountLogDetails(record, {
    stage: "generated_account_cached"
  }));
}

function setActiveAccount(account = {}, reason = "active_account") {
  const email = normalizeEmail(account.email);
  if (!email || !account.password) return null;
  const domain = account.domain || email.split("@")[1] || "";
  const record = {
    provider: account.provider || (domain.includes("hotmail") ? "hotmail" : "outlook"),
    domain,
    username: account.username || email.split("@", 1)[0],
    email,
    password: account.password,
    clientId: account.clientId || account.client_id || DEFAULT_CLIENT_ID,
    registrationRunId: account.registrationRunId || state.registrationRunId || "",
    birthMonth: account.birthMonth || "",
    birthDay: account.birthDay || "",
    birthYear: account.birthYear || "",
    savedAt: nowIso()
  };
  state.activeAccount = record;
  chrome.storage.local.set({ ninjemailActiveAccount: record }, () => {
    void chrome.runtime.lastError;
  });
  pushDedupeLog("ACCOUNT", accountLogMessage("当前账号已更新", record), accountLogDetails(record, { stage: reason }));
  return record;
}

function nowIso() {
  return new Date().toISOString();
}

function pushLog(level, message, details = {}) {
  state.logs.push({
    at: nowIso(),
    level,
    message,
    details
  });
  if (state.logs.length > MAX_LOGS) {
    state.logs.splice(0, state.logs.length - MAX_LOGS);
  }
  const entry = state.logs[state.logs.length - 1];
  try {
    const detailText = details && Object.keys(details).length
      ? " " + Object.entries(details).map(([key, value]) => `${key}=${typeof value === "string" ? value : JSON.stringify(value)}`).join(" ")
      : "";
    console.log(`[Ninjemail][${entry.level || "INFO"}] ${entry.at || ""} ${entry.message || ""}${detailText}`);
  } catch (error) {
    void error;
  }
}

function pushDedupeLog(level, message, details = {}) {
  const signature = JSON.stringify({ level, message, details });
  if (signature === state.lastSignature) return;
  state.lastSignature = signature;
  pushLog(level, message, details);
}

function cloneState() {
  // 代理引擎状态摘要
  const now = Date.now();
  const cooldownDetails = proxyEngine.proxies
    .map(p => {
      const h = proxyEngine.health[p];
      if (h && h.cooldownUntil && h.cooldownUntil > now) {
        return { proxy: urlShort(p), remainingSec: Math.ceil((h.cooldownUntil - now) / 1000), cooldownUntil: h.cooldownUntil };
      }
      return null;
    })
    .filter(Boolean);
  const proxyEngineSummary = {
    enabled: proxyEngine.enabled,
    count: proxyEngine.proxies.length,
    currentProxy: proxyEngine.currentProxy ? urlShort(proxyEngine.currentProxy) : null,
    currentProxyFull: proxyEngine.currentProxy || null,
    healthyCount: proxyEngine.proxies.filter(p => proxyIsAvailable(p)).length,
    cooldownCount: cooldownDetails.length,
    cooldownDetails,
    lastUsedProxy: proxyEngine.lastUsedProxy ? urlShort(proxyEngine.lastUsedProxy) : null,
    exitIp: state.proxyExitIp || "",
    exitCountry: state.proxyExitCountry || "",
    activeStatus: state.proxyActiveStatus || "none",
  };
  return JSON.parse(JSON.stringify({
    ...state,
    proxyEngine: proxyEngineSummary,
    defaultCredentialOutputDir: DEFAULT_CREDENTIAL_OUTPUT_DIR,
    effectiveCredentialOutputDir: state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
    defaultWebUiBaseUrl: WEB_UI_BASE_URL,
    effectiveWebUiBaseUrl: state.webUiBaseUrl || WEB_UI_BASE_URL
  }));
}

function broadcastState() {
  const cloned = cloneState();
  console.log("[broadcastState] proxyEngine:", JSON.stringify(cloned.proxyEngine));
  chrome.runtime.sendMessage({ type: "NM_STATE_UPDATED", payload: cloned }, () => {
    void chrome.runtime.lastError;
  });
}

function setStatus(status) {
  state.status = status;
  state.statusText = STATUS_TEXT[status] || status;
  state.updatedAt = nowIso();
}

function isAutoRunLeaseFresh(startedAt = state.autoRunStartedAt) {
  const started = Number(startedAt || 0);
  return Number.isFinite(started) && started > 0 && Date.now() - started <= AUTORUN_MAX_AGE_MS;
}

async function clearAutoRunLease() {
  state.autoRunEnabled = false;
  state.autoRunTabId = null;
  state.autoRunStartedAt = 0;
  state.autoRunLastResumeSignature = "";
  state.autoRunLastCommandAt = 0;
  await storageSet({
    [AUTORUN_ENABLED_STORAGE_KEY]: false,
    [AUTORUN_TAB_ID_STORAGE_KEY]: null,
    [AUTORUN_STARTED_AT_STORAGE_KEY]: 0
  });
}

async function hydrateStoredState() {
  const stored = await storageGet([
    AUTORUN_ENABLED_STORAGE_KEY,
    AUTORUN_TAB_ID_STORAGE_KEY,
    AUTORUN_STARTED_AT_STORAGE_KEY,
    CREDENTIAL_OUTPUT_DIR_STORAGE_KEY,
    WEB_UI_BASE_URL_STORAGE_KEY,
    "ninjemailActiveAccount",
    "ninjemailLastCreatedAccount",
    "ninjemailGeneratedAccount",
    CREATED_ACCOUNTS_STORAGE_KEY,
    OAUTH_JOBS_STORAGE_KEY,
    REGISTRATION_RUN_ID_STORAGE_KEY
  ]);
  state.autoRunStartedAt = Number(stored[AUTORUN_STARTED_AT_STORAGE_KEY] || 0) || 0;
  state.autoRunTabId = stored[AUTORUN_TAB_ID_STORAGE_KEY] || null;
  state.autoRunEnabled = Boolean(stored[AUTORUN_ENABLED_STORAGE_KEY]) && isAutoRunLeaseFresh(state.autoRunStartedAt) && Boolean(state.autoRunTabId);
  if (stored[AUTORUN_ENABLED_STORAGE_KEY] && !state.autoRunEnabled) {
    await clearAutoRunLease();
  }
  state.credentialOutputDir = stored[CREDENTIAL_OUTPUT_DIR_STORAGE_KEY] || "";
  state.webUiBaseUrl = stored[WEB_UI_BASE_URL_STORAGE_KEY] || "";
  state.activeAccount = stored.ninjemailActiveAccount || null;
  state.lastCreatedAccount = stored.ninjemailLastCreatedAccount || null;
  state.lastGeneratedAccount = stored.ninjemailGeneratedAccount || null;
  state.registrationRunId = String(stored[REGISTRATION_RUN_ID_STORAGE_KEY] || "");
  state.oauthJobs = stored[OAUTH_JOBS_STORAGE_KEY] && typeof stored[OAUTH_JOBS_STORAGE_KEY] === "object"
    ? stored[OAUTH_JOBS_STORAGE_KEY]
    : {};
  if (state.activeAccount) {
    state.credentialStatus = {
      email: state.activeAccount.email || "",
      combo_path: state.activeAccount.comboPath || "",
      token_job: state.activeAccount.tokenJobStatus || "",
      web_ui_saved: Boolean(state.activeAccount.webUiOk),
      status: state.credentialStatus.status || "active_account"
    };
  } else if (state.lastCreatedAccount) {
    state.credentialStatus = {
      email: state.lastCreatedAccount.email || "",
      combo_path: state.lastCreatedAccount.comboPath || "",
      token_job: state.lastCreatedAccount.tokenJobStatus || "",
      web_ui_saved: Boolean(state.lastCreatedAccount.webUiOk)
    };
  }
}

function storageGet(keys) {
  return new Promise((resolve) => {
    chrome.storage.local.get(keys, (result) => resolve(result || {}));
  });
}

function storageSet(values) {
  return new Promise((resolve) => {
    chrome.storage.local.set(values, () => resolve());
  });
}

async function persistOAuthJobs() {
  await storageSet({ [OAUTH_JOBS_STORAGE_KEY]: state.oauthJobs });
}

async function oauthJobByState(oauthState) {
  const key = String(oauthState || "");
  if (!key) return null;
  if (state.oauthJobs[key]) return state.oauthJobs[key];
  const stored = await storageGet([OAUTH_JOBS_STORAGE_KEY]);
  state.oauthJobs = stored[OAUTH_JOBS_STORAGE_KEY] && typeof stored[OAUTH_JOBS_STORAGE_KEY] === "object"
    ? stored[OAUTH_JOBS_STORAGE_KEY]
    : {};
  return state.oauthJobs[key] || null;
}

async function removeOAuthJob(oauthState) {
  const key = String(oauthState || "");
  if (!key) return;
  delete state.oauthJobs[key];
  await persistOAuthJobs();
}

function normalizeEmail(value = "") {
  return String(value || "").trim().toLowerCase();
}

function comboLineFor(record) {
  return `${normalizeEmail(record.email)}----${record.password || ""}----${record.clientId || BUILTIN_CLIENT_ID}----${record.refreshToken || ""}`;
}

function threeCredentialLineFor(record) {
  return `${normalizeEmail(record.email)}----${record.password || ""}----${record.clientId || BUILTIN_CLIENT_ID}`;
}

function credentialFilenameFor(email = "") {
  const safe = normalizeEmail(email).replace(/[<>:"/\\|?*]+/g, "_").replace(/^\.+|\.+$/g, "") || "outlook";
  return `${safe}.txt`;
}

function threeCredentialFilenameFor(email = "") {
  return credentialFilenameFor(email).replace(/\.txt$/i, ".triple.txt");
}

function credentialPathMatchesEmail(email = "", path = "") {
  const expected = credentialFilenameFor(email).toLowerCase();
  const normalizedPath = String(path || "").replace(/\\/g, "/").toLowerCase();
  const basename = normalizedPath.split("/").filter(Boolean).pop() || "";
  const expectedBase = expected.replace(/\.txt$/i, "");
  return basename === expected || (basename.startsWith(`${expectedBase}__`) && basename.endsWith(".txt"));
}

function threeCredentialPathMatchesEmail(email = "", path = "") {
  const expected = threeCredentialFilenameFor(email).toLowerCase();
  const normalizedPath = String(path || "").replace(/\\/g, "/").toLowerCase();
  const basename = normalizedPath.split("/").filter(Boolean).pop() || "";
  return basename === expected;
}

function credentialDownloadFilenameFor(record = {}) {
  const filename = credentialFilenameFor(record.email);
  const outputDir = String(record.outputDir || state.credentialOutputDir || "").trim().replace(/\\/g, "/");
  const marker = "/downloads/";
  const markerIndex = outputDir.toLowerCase().lastIndexOf(marker);
  if (markerIndex < 0) return filename;
  const relativeDir = outputDir.slice(markerIndex + marker.length)
    .split("/")
    .map((segment) => segment.trim().replace(/[<>:"\\|?*]+/g, "_").replace(/^\.+|\.+$/g, ""))
    .filter(Boolean)
    .join("/");
  return relativeDir ? `${relativeDir}/${filename}` : filename;
}

function threeCredentialDownloadFilenameFor(record = {}) {
  const filename = threeCredentialFilenameFor(record.email || "");
  const outputDir = String(record.outputDir || state.credentialOutputDir || "").trim().replace(/\\/g, "/");
  const marker = "/downloads/";
  const markerIndex = outputDir.toLowerCase().lastIndexOf(marker);
  if (markerIndex < 0) return filename;
  const relativeDir = outputDir.slice(markerIndex + marker.length)
    .split("/")
    .map((segment) => segment.trim().replace(/[<>:"\\|?*]+/g, "_").replace(/^\.+|\.+$/g, ""))
    .filter(Boolean)
    .join("/");
  return relativeDir ? `${relativeDir}/${filename}` : filename;
}

function isAbsoluteFilesystemPath(value = "") {
  const text = String(value || "").trim();
  return /^[a-zA-Z]:[\\/]/.test(text) || text.startsWith("\\\\") || text.startsWith("/");
}

function outputDirSupportsBrowserDownload(outputDir = "") {
  const text = String(outputDir || "").trim();
  if (!text) return true;
  if (!isAbsoluteFilesystemPath(text)) return true;
  const normalized = text.replace(/\\/g, "/").toLowerCase();
  return normalized.endsWith("/downloads") || normalized.includes("/downloads/");
}

function normalizeCredentialSaveFailureReason(reason = "", outputDir = "") {
  const text = String(reason || "").trim();
  if (
    isAbsoluteFilesystemPath(outputDir)
    && !outputDirSupportsBrowserDownload(outputDir)
    && ["Failed to fetch", "web_ui_timeout"].includes(text)
  ) {
    return "local_writer_unreachable_for_absolute_output_dir";
  }
  return text || "credential_save_failed";
}

function effectiveWebUiBaseUrl() {
  const raw = String(state.webUiBaseUrl || "").trim();
  if (!raw) return WEB_UI_BASE_URL;
  return raw.replace(/\/+$/g, "");
}

function webUiApiUrl(apiName = "") {
  const base = effectiveWebUiBaseUrl();
  if (!apiName) return `${base}/`;
  return `${base}/gradio_api/api/${apiName}`;
}

async function downloadCredentialFile(record) {
  if (!chrome.downloads || !chrome.downloads.download) {
    return { ok: false, reason: "downloads_permission_missing" };
  }
  if (!record || !record.email || !record.password || !record.refreshToken) {
    return { ok: false, reason: "missing_complete_credentials" };
  }
  const body = `${comboLineFor(record)}\n`;
  const url = `data:text/plain;charset=utf-8,${encodeURIComponent(body)}`;
  const filename = credentialDownloadFilenameFor(record);
  return new Promise((resolve) => {
    chrome.downloads.download({
      url,
      filename,
      conflictAction: "uniquify",
      saveAs: false
    }, (downloadId) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, reason: chrome.runtime.lastError.message || "download_failed" });
        return;
      }
      if (chrome.downloads.search) {
        chrome.downloads.search({ id: downloadId }, (items) => {
          const item = Array.isArray(items) ? items[0] : null;
          resolve({ ok: true, downloadId, filename, finalFilename: item?.filename || filename });
        });
        return;
      }
      resolve({ ok: true, downloadId, filename, finalFilename: filename });
    });
  });
}

async function downloadThreeCredentialFile(record) {
  if (!chrome.downloads || !chrome.downloads.download) {
    return { ok: false, reason: "downloads_permission_missing" };
  }
  if (!record || !record.email || !record.password) {
    return { ok: false, reason: "missing_email_or_password" };
  }
  const body = `${threeCredentialLineFor(record)}\n`;
  const url = `data:text/plain;charset=utf-8,${encodeURIComponent(body)}`;
  const filename = threeCredentialDownloadFilenameFor(record);
  return new Promise((resolve) => {
    chrome.downloads.download({
      url,
      filename,
      conflictAction: "uniquify",
      saveAs: false
    }, (downloadId) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, reason: chrome.runtime.lastError.message || "download_failed" });
        return;
      }
      if (chrome.downloads.search) {
        chrome.downloads.search({ id: downloadId }, (items) => {
          const item = Array.isArray(items) ? items[0] : null;
          resolve({ ok: true, downloadId, filename, finalFilename: item?.filename || filename });
        });
        return;
      }
      resolve({ ok: true, downloadId, filename, finalFilename: filename });
    });
  });
}

async function postAccountToWebUi(record) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), WEB_UI_ACCOUNT_SAVE_TIMEOUT_MS);
  const payload = {
    email: record.email,
    password: record.password,
    provider: record.provider || "outlook",
    domain: record.domain || "",
    client_id: record.clientId || BUILTIN_CLIENT_ID,
    access_token: record.accessToken || record.access_token || "",
    refresh_token: record.refreshToken || "",
    expires_in: record.expiresIn || record.expires_in || "",
    token_type: record.tokenType || record.token_type || "",
    scope: record.scope || "",
    final_state: record.finalState || "",
    url: record.url || "",
    output_dir: record.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
    start_token_export: false,
    source: "browser_extension"
  };
  try {
    const response = await fetch(webUiApiUrl("ninjemail_account_created"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: [payload] }),
      signal: controller.signal
    });
    const raw = await response.json().catch(() => ({}));
    const data = Array.isArray(raw.data) ? (raw.data[0] || {}) : raw;
    return { ok: response.ok && data.ok !== false, status: response.status, data };
  } catch (error) {
    return { ok: false, reason: error && error.name === "AbortError" ? "web_ui_timeout" : String(error && error.message || error) };
  } finally {
    clearTimeout(timer);
  }
}

async function checkLocalWriterAvailability(timeoutMs = 3000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(webUiApiUrl(), {
      method: "GET",
      signal: controller.signal
    });
    return Boolean(response && response.ok);
  } catch (error) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function probeWebUiHealth(timeoutMs = 3000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(webUiApiUrl(), {
      method: "GET",
      signal: controller.signal
    });
    const ok = Boolean(response && response.ok);
    return {
      ok,
      status: ok ? "running" : "failed",
      reason: ok ? "" : `http_${response.status}`,
      checkedAt: nowIso(),
      url: effectiveWebUiBaseUrl()
    };
  } catch (error) {
    return {
      ok: false,
      status: "failed",
      reason: error && error.name === "AbortError" ? "timeout" : String(error && error.message || error),
      checkedAt: nowIso(),
      url: effectiveWebUiBaseUrl()
    };
  } finally {
    clearTimeout(timer);
  }
}

async function checkSavedCredentialViaWebUi(record = {}) {
  const email = normalizeEmail(record.email || "");
  const outputDir = String(record.outputDir || record.output_dir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR).trim()
    || DEFAULT_CREDENTIAL_OUTPUT_DIR;
  if (!email || !email.includes("@")) {
    return { ok: false, reason: "missing_email", data: { email, output_dir: outputDir } };
  }
  const result = await postWebUiApi("ninjemail_credential_status", {
    email,
    output_dir: outputDir,
    source: "browser_extension"
  }, WEB_UI_CREDENTIAL_CHECK_TIMEOUT_MS);
  const data = result.data || {};
  const refreshToken = String(data.refresh_token || "").trim();
  return {
    ok: Boolean(result.ok && data.exists && data.has_refresh_token && refreshToken),
    reason: data.reason || result.reason || (data.exists ? "missing_refresh_token" : "credential_not_found"),
    data: {
      ...data,
      email,
      refresh_token: refreshToken,
      credential_path: String(data.credential_path || ""),
      combo_path: String(data.combo_path || data.credential_path || ""),
      output_dir: outputDir
    }
  };
}

async function persistRecoveredCredentialRecord(record = {}, recovered = {}, reason = "recovered_saved_credential") {
  const email = normalizeEmail(record.email || recovered.email || "");
  const refreshToken = String(record.refreshToken || record.refresh_token || recovered.refresh_token || "").trim();
  if (!email || !email.includes("@") || !refreshToken) {
    return { ok: false, reason: "missing_email_or_refresh_token" };
  }
  const outputDir = String(record.outputDir || record.output_dir || recovered.output_dir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR).trim()
    || DEFAULT_CREDENTIAL_OUTPUT_DIR;
  const normalized = {
    ...record,
    provider: record.provider || state.provider || "outlook",
    domain: record.domain || (email.split("@")[1] || ""),
    username: record.username || email.split("@", 1)[0],
    email,
    password: record.password || "",
    clientId: record.clientId || record.client_id || BUILTIN_CLIENT_ID,
    refreshToken,
    accessToken: record.accessToken || record.access_token || "",
    registrationRunId: record.registrationRunId || state.registrationRunId || "",
    expiresIn: record.expiresIn || record.expires_in || "",
    tokenType: record.tokenType || record.token_type || "",
    scope: record.scope || "",
    finalState: record.finalState || record.final_state || "",
    url: record.url || "",
    title: record.title || "",
    outputDir,
    savedAt: nowIso(),
    webUiOk: true,
    browserDownloadOk: false,
    tokenJobStatus: "saved",
    credentialPath: String(recovered.credential_path || recovered.combo_path || record.credentialPath || record.comboPath || ""),
    comboPath: String(recovered.combo_path || recovered.credential_path || record.comboPath || record.credentialPath || "")
  };
  const stored = await storageGet([CREATED_ACCOUNTS_STORAGE_KEY]);
  const existing = Array.isArray(stored[CREATED_ACCOUNTS_STORAGE_KEY]) ? stored[CREATED_ACCOUNTS_STORAGE_KEY] : [];
  const next = existing.filter((item) => normalizeEmail(item && item.email) !== email);
  next.push(normalized);
  await storageSet({
    [CREATED_ACCOUNTS_STORAGE_KEY]: next,
    ninjemailActiveAccount: normalized,
    ninjemailLastCreatedAccount: normalized
  });
  state.activeAccount = normalized;
  state.lastCreatedAccount = normalized;
  state.credentialStatus = {
    status: "saved_or_token_started",
    email,
    credential_path: normalized.credentialPath || normalized.comboPath || "",
    combo_path: normalized.comboPath || normalized.credentialPath || "",
    token_job: "saved",
    web_ui_saved: true,
    browser_download_saved: false,
    output_dir: outputDir,
    reason: reason || ""
  };
  setCredentialLock(email, { status: "done", finalState: normalized.finalState || "", stage: reason, tokenJobStatus: "saved" });
  pushDedupeLog("OK", "检测到已保存的四凭证，已恢复插件状态", {
    email,
    credential_path: normalized.credentialPath || normalized.comboPath || "",
    output_dir: outputDir,
    reason
  });
  return { ok: true, record: normalized };
}

async function postClearCredentialsToWebUi(emails = [], reason = "start_autopilot") {
  const uniqueEmails = Array.from(new Set((emails || []).map(normalizeEmail).filter(Boolean)));
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3500);
  const payload = {
    emails: uniqueEmails,
    output_dir: state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
    reason,
    source: "browser_extension"
  };
  try {
    const response = await fetch(webUiApiUrl("ninjemail_clear_previous_credentials"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: [payload] }),
      signal: controller.signal
    });
    const raw = await response.json().catch(() => ({}));
    const data = Array.isArray(raw.data) ? (raw.data[0] || {}) : raw;
    return { ok: response.ok && data.ok !== false, status: response.status, data };
  } catch (error) {
    return { ok: false, reason: error && error.name === "AbortError" ? "web_ui_timeout" : String(error && error.message || error) };
  } finally {
    clearTimeout(timer);
  }
}

async function postThreeCredentialsToWebUi(record) {
  return postWebUiApi("ninjemail_export_three_credentials", {
    email: record.email,
    password: record.password,
    client_id: record.clientId || BUILTIN_CLIENT_ID,
    provider: record.provider || "outlook",
    domain: record.domain || "",
    output_dir: record.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
    source: "browser_extension"
  }, 12000);
}

async function openCredentialOutputDir(payload = {}) {
  const record = state.activeAccount || state.lastCreatedAccount || {};
  const outputDir = String(payload.outputDir || payload.output_dir || state.credentialOutputDir || record.outputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR).trim()
    || DEFAULT_CREDENTIAL_OUTPUT_DIR;
  const credentialPath = String(payload.credentialPath || payload.credential_path || state.credentialStatus?.credential_path || record.credentialPath || record.comboPath || "").trim();
  if (record.downloadId && chrome.downloads && chrome.downloads.show) {
    return new Promise((resolve) => {
      chrome.downloads.show(record.downloadId);
      resolve({ ok: true, method: "downloads_show", downloadId: record.downloadId, output_dir: outputDir });
    });
  }
  if (outputDirSupportsBrowserDownload(outputDir) && chrome.downloads && chrome.downloads.showDefaultFolder) {
    return new Promise((resolve) => {
      chrome.downloads.showDefaultFolder();
      resolve({ ok: true, method: "show_default_folder", output_dir: outputDir });
    });
  }
  return postWebUiApi("ninjemail_open_credential_output_dir", {
    output_dir: outputDir,
    credential_path: credentialPath,
    source: "browser_extension"
  }, 10000);
}

async function postWebUiApi(apiName, payload = {}, timeoutMs = 25000) {
  const controller = new AbortController();
  activeWebUiControllers.add(controller);
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(webUiApiUrl(apiName), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: [payload] }),
      signal: controller.signal
    });
    const raw = await response.json().catch(() => ({}));
    const data = Array.isArray(raw.data) ? (raw.data[0] || {}) : raw;
    return {
      ok: response.ok && data.ok !== false,
      status: response.status,
      data,
      reason: data.reason || (response.ok ? "" : `HTTP ${response.status}`)
    };
  } catch (error) {
    return {
      ok: false,
      reason: error && error.name === "AbortError"
        ? (controller.__ninjemailStopAbort ? "background_operation_stopped" : "web_ui_timeout")
        : String(error && error.message || error)
    };
  } finally {
    activeWebUiControllers.delete(controller);
    clearTimeout(timer);
  }
}

async function refreshSmsDiagnostics(reason = "manual_refresh") {
  const controller = new AbortController();
  const shouldProbe = ["sidepanel_button", "manual_refresh", "force_probe"].includes(reason);
  const timer = setTimeout(() => controller.abort(), shouldProbe ? 70000 : 4500);
  if (!state.smsDiagnostics || !Array.isArray(state.smsDiagnostics.providers) || !state.smsDiagnostics.providers.length) {
    state.smsDiagnostics = defaultSmsDiagnostics();
  }
  const payload = {
    source: "browser_extension",
    reason,
    provider: state.provider || "outlook",
    probe: shouldProbe
  };
  try {
    const response = await fetch(webUiApiUrl("ninjemail_sms_diagnostics"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: [payload] }),
      signal: controller.signal
    });
    const raw = await response.json().catch(() => ({}));
    const data = Array.isArray(raw.data) ? (raw.data[0] || {}) : raw;
    const apiReason = data.reason || `HTTP ${response.status}`;
    const fallback = defaultSmsDiagnostics(
      response.ok ? "not_checked" : "web_ui_unavailable",
      apiReason,
      "not_checked",
      response.ok ? "等待实测结果" : "Web UI 诊断接口不可用，服务未实测"
    );
    const providers = Array.isArray(data.providers) && data.providers.length ? data.providers : fallback.providers;
    state.smsDiagnostics = {
      status: response.ok && data.ok !== false ? (data.diagnostic_status || "ok") : "web_ui_unavailable",
      source: data.source || fallback.source,
      providers,
      diagnostic_primary: data.diagnostic_primary || "",
      diagnostic_reason: data.diagnostic_reason || data.reason || fallback.diagnostic_reason,
      real_provider: data.real_provider || "",
      country: data.country || "",
      checked_at: data.checked_at || "",
      ok_count: Number(data.ok_count || providers.filter((item) => item && item.ok).length || 0),
      total: Number(data.total || providers.length || 0),
      lastUpdatedAt: nowIso()
    };
    pushDedupeLog(response.ok ? "OK" : "BLOCK", response.ok ? "免费接码服务状态已刷新" : "免费接码服务状态刷新失败", {
      status: state.smsDiagnostics.status,
      primary: state.smsDiagnostics.diagnostic_primary || "",
      ok_count: state.smsDiagnostics.ok_count,
      total: state.smsDiagnostics.total
    });
    return { ok: response.ok && data.ok !== false, data: state.smsDiagnostics };
  } catch (error) {
    const fallback = defaultSmsDiagnostics(
      "web_ui_unavailable",
      error && error.name === "AbortError" ? "web_ui_timeout" : String(error && error.message || error),
      "not_checked",
      "Web UI 诊断接口不可用，服务未实测"
    );
    state.smsDiagnostics = {
      ...fallback,
      status: "web_ui_unavailable",
      diagnostic_reason: fallback.diagnostic_reason,
      lastUpdatedAt: nowIso()
    };
    pushDedupeLog("BLOCK", "免费接码服务状态刷新失败", {
      reason: state.smsDiagnostics.diagnostic_reason
    });
    return { ok: false, reason: state.smsDiagnostics.diagnostic_reason };
  } finally {
    clearTimeout(timer);
  }
}

async function validateCredentialFiles(payload = {}) {
  const controlVersion = state.autoRunControlVersion;
  state.credentialValidation = {
    status: "running",
    checked: 0,
    valid: 0,
    failed: 0,
    reason: "",
    credential_dir: state.credentialOutputDir || ""
  };
  broadcastState();
  const result = await postWebUiApi("ninjemail_validate_credentials", {
    output_dir: payload.outputDir || payload.output_dir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
    email: payload.email || "",
    source: "browser_extension"
  }, 90000);
  if (controlVersion !== state.autoRunControlVersion && state.status === "stopped") {
    state.credentialValidation = {
      status: "stopped",
      checked: 0,
      valid: 0,
      failed: 0,
      reason: "background_operation_stopped",
      credential_dir: state.credentialOutputDir || ""
    };
    broadcastState();
    return state.credentialValidation;
  }
  const data = result.data || {};
  state.credentialValidation = {
    status: result.ok ? "done" : "failed",
    checked: data.checked || 0,
    valid: data.valid || 0,
    failed: data.failed || 0,
    reason: data.reason || result.reason || "",
    credential_dir: data.credential_dir || state.credentialOutputDir || "",
    results: Array.isArray(data.results) ? data.results.slice(0, 20) : []
  };
  pushDedupeLog(result.ok ? "OK" : "BLOCK", result.ok ? "邮箱凭证校验完成" : "邮箱凭证校验失败", {
    checked: state.credentialValidation.checked,
    valid: state.credentialValidation.valid,
    failed: state.credentialValidation.failed,
    credential_dir: state.credentialValidation.credential_dir,
    reason: state.credentialValidation.reason
  });
  broadcastState();
  return state.credentialValidation;
}

async function pickAuxiliaryMailbox(payload = {}) {
  const controlVersion = state.autoRunControlVersion;
  const result = await postWebUiApi("ninjemail_auxiliary_mailbox_pick", {
    auxiliary_dir: payload.auxiliaryDir || payload.auxiliary_dir || "",
    seed: `${Date.now()}:${Array.from(secureRandomBytes(8)).map((item) => item.toString(16).padStart(2, "0")).join("")}`,
    source: "browser_extension"
  }, 30000);
  if (controlVersion !== state.autoRunControlVersion && state.status === "stopped") {
    state.auxiliaryMailboxStatus = {
      status: "stopped",
      reason: "background_operation_stopped"
    };
    broadcastState();
    return { ok: false, reason: "background_operation_stopped", status: state.auxiliaryMailboxStatus };
  }
  const data = result.data || {};
  if (result.ok && data.ok !== false && data.email) {
    state.auxiliaryMailbox = {
      email: data.email,
      clientId: data.client_id || data.clientId || "",
      sourcePath: data.source_path || data.sourcePath || "",
      pickedAt: nowIso()
    };
    state.auxiliaryMailboxStatus = {
      status: "selected",
      email: data.email,
      source_path: state.auxiliaryMailbox.sourcePath,
      auxiliary_dir: data.auxiliary_dir || "",
      count: data.count || 0
    };
    pushDedupeLog("STEP", "已选择辅助邮箱", state.auxiliaryMailboxStatus);
  } else {
    state.auxiliaryMailboxStatus = {
      status: "failed",
      reason: data.reason || result.reason || "auxiliary_mailbox_pick_failed",
      auxiliary_dir: data.auxiliary_dir || ""
    };
    pushDedupeLog("BLOCK", "辅助邮箱选择失败", state.auxiliaryMailboxStatus);
  }
  broadcastState();
  return { ok: Boolean(state.auxiliaryMailbox && state.auxiliaryMailbox.email), mailbox: state.auxiliaryMailbox, status: state.auxiliaryMailboxStatus };
}

async function pollAuxiliaryMailboxCode(payload = {}) {
  const controlVersion = state.autoRunControlVersion;
  if (!state.auxiliaryMailbox || !state.auxiliaryMailbox.email) {
    await pickAuxiliaryMailbox(payload);
  }
  if (!state.auxiliaryMailbox || !state.auxiliaryMailbox.email) {
    return { ok: false, reason: "missing_auxiliary_mailbox", status: state.auxiliaryMailboxStatus };
  }
  state.auxiliaryMailboxStatus = {
    ...state.auxiliaryMailboxStatus,
    status: "polling_code",
    email: state.auxiliaryMailbox.email
  };
  broadcastState();
  const result = await postWebUiApi("ninjemail_auxiliary_mailbox_code", {
    email: state.auxiliaryMailbox.email,
    source_path: state.auxiliaryMailbox.sourcePath,
    timeout_seconds: payload.timeoutSeconds || payload.timeout_seconds || 70,
    interval_seconds: payload.intervalSeconds || payload.interval_seconds || 5,
    source: "browser_extension"
  }, 90000);
  if (controlVersion !== state.autoRunControlVersion && state.status === "stopped") {
    state.auxiliaryMailboxStatus = {
      status: "stopped",
      email: state.auxiliaryMailbox.email,
      reason: "background_operation_stopped",
      source_path: state.auxiliaryMailbox.sourcePath
    };
    broadcastState();
    return { ok: false, ...state.auxiliaryMailboxStatus };
  }
  const data = result.data || {};
  state.auxiliaryMailboxStatus = {
    status: result.ok && data.ok !== false && data.code ? "code_ready" : "code_failed",
    email: state.auxiliaryMailbox.email,
    code: data.code || "",
    reason: data.reason || result.reason || "",
    subject: data.subject || "",
    source_path: state.auxiliaryMailbox.sourcePath
  };
  pushDedupeLog(state.auxiliaryMailboxStatus.code ? "OK" : "BLOCK", state.auxiliaryMailboxStatus.code ? "已获取辅助邮箱验证码" : "辅助邮箱验证码获取失败", {
    email: state.auxiliaryMailbox.email,
    code: state.auxiliaryMailboxStatus.code || "",
    reason: state.auxiliaryMailboxStatus.reason || ""
  });
  broadcastState();
  return { ok: Boolean(state.auxiliaryMailboxStatus.code), ...state.auxiliaryMailboxStatus };
}

function preferredSmsProvider(provider = "") {
  const requested = String(provider || "").trim();
  if (requested) return requested;
  if (state.smsUsage && state.smsUsage.provider) return state.smsUsage.provider;
  if (state.smsDiagnostics && state.smsDiagnostics.diagnostic_primary) return state.smsDiagnostics.diagnostic_primary;
  const okItem = (state.smsDiagnostics.providers || []).find((item) => item && item.ok && !item.requires_key);
  return okItem?.provider || "receive_sms_live";
}

async function loadSmsNumbers(payload = {}) {
  const provider = preferredSmsProvider(payload.provider);
  const country = String(payload.country || state.smsUsage?.country || "USA").trim() || "USA";
  state.smsUsage = {
    ...defaultSmsUsage(),
    ...state.smsUsage,
    provider,
    country,
    status: "loading_numbers",
    reason: "loading",
    lastUpdatedAt: nowIso()
  };
  const result = await postWebUiApi("ninjemail_sms_numbers", {
    source: "browser_extension",
    provider,
    country,
    limit: Number(payload.limit || 30)
  }, 35000);
  const data = result.data || {};
  state.smsUsage = {
    ...state.smsUsage,
    provider: data.provider || provider,
    country: data.country || country,
    status: result.ok ? "numbers_loaded" : "numbers_failed",
    reason: data.reason || result.reason || "",
    numbers: Array.isArray(data.numbers) ? data.numbers : [],
    selectedNumber: null,
    messages: [],
    codes: [],
    code: "",
    url: data.url || "",
    route: data.route || "",
    latency_ms: data.latency_ms || "",
    lastUpdatedAt: nowIso()
  };
  if (state.smsUsage.numbers.length) {
    state.smsUsage.selectedNumber = state.smsUsage.numbers[0];
  }
  pushDedupeLog(result.ok ? "OK" : "BLOCK", result.ok ? "免费接码号码已加载" : "免费接码号码加载失败", {
    provider: state.smsUsage.provider,
    count: state.smsUsage.numbers.length,
    reason: state.smsUsage.reason || ""
  });
  return state.smsUsage;
}

function selectSmsNumber(payload = {}) {
  const phone = String(payload.phone || "").trim();
  const messageUrl = String(payload.message_url || payload.messageUrl || "").trim();
  const provider = preferredSmsProvider(payload.provider);
  const match = (state.smsUsage.numbers || []).find((item) => {
    const itemPhone = String(item.phone || "").trim();
    const itemUrl = String(item.message_url || item.messageUrl || "").trim();
    return (phone && itemPhone === phone) || (messageUrl && itemUrl === messageUrl);
  });
  state.smsUsage = {
    ...state.smsUsage,
    provider,
    selectedNumber: match || {
      provider,
      phone,
      message_url: messageUrl,
      source_url: String(payload.source_url || payload.sourceUrl || "").trim()
    },
    messages: [],
    codes: [],
    code: "",
    status: "number_selected",
    reason: "",
    lastUpdatedAt: nowIso()
  };
  return state.smsUsage;
}

async function refreshSmsMessages(payload = {}) {
  if (payload.phone || payload.message_url || payload.messageUrl) {
    selectSmsNumber(payload);
  }
  const selected = state.smsUsage.selectedNumber || {};
  const provider = preferredSmsProvider(payload.provider || selected.provider);
  const country = String(payload.country || state.smsUsage.country || "USA").trim() || "USA";
  const phone = String(payload.phone || selected.phone || "").trim();
  const messageUrl = String(payload.message_url || payload.messageUrl || selected.message_url || selected.messageUrl || "").trim();
  state.smsUsage = {
    ...state.smsUsage,
    provider,
    country,
    status: "loading_messages",
    reason: "loading",
    lastUpdatedAt: nowIso()
  };
  const result = await postWebUiApi("ninjemail_sms_messages", {
    source: "browser_extension",
    provider,
    country,
    phone,
    message_url: messageUrl,
    limit: Number(payload.limit || 30)
  }, 35000);
  const data = result.data || {};
  state.smsUsage = {
    ...state.smsUsage,
    provider: data.provider || provider,
    country: data.country || country,
    status: result.ok ? "messages_loaded" : "messages_failed",
    reason: data.reason || result.reason || "",
    selectedNumber: data.selected_number || state.smsUsage.selectedNumber || selected,
    messages: Array.isArray(data.messages) ? data.messages : [],
    codes: Array.isArray(data.codes) ? data.codes : [],
    code: data.code || "",
    message_url: data.message_url || messageUrl,
    route: data.route || "",
    latency_ms: data.latency_ms || "",
    lastUpdatedAt: nowIso()
  };
  pushDedupeLog(result.ok ? "OK" : "BLOCK", result.ok ? "免费接码短信已刷新" : "免费接码短信刷新失败", {
    provider: state.smsUsage.provider,
    phone: phone || "",
    code: state.smsUsage.code || "",
    messages: state.smsUsage.messages.length,
    reason: state.smsUsage.reason || ""
  });
  return state.smsUsage;
}

async function removeDownloadedCredentialFiles(emails = []) {
  if (!chrome.downloads || !chrome.downloads.search || !chrome.downloads.removeFile) {
    return { ok: false, reason: "downloads_permission_missing", removed: 0 };
  }
  const targets = Array.from(new Set((emails || []).map((email) => credentialFilenameFor(email).toLowerCase())));
  if (!targets.length) return { ok: true, removed: 0 };
  let removed = 0;
  for (const target of targets) {
    const items = await new Promise((resolve) => {
      chrome.downloads.search({ query: [target] }, (results) => {
        resolve(Array.isArray(results) ? results : []);
      });
    });
    for (const item of items) {
      const filename = String(item.filename || "").replace(/\\/g, "/").toLowerCase();
      if (!filename.endsWith(`/${target}`) && filename !== target) continue;
      await new Promise((resolve) => {
        chrome.downloads.removeFile(item.id, () => {
          void chrome.runtime.lastError;
          resolve();
        });
      });
      if (chrome.downloads.erase) {
        chrome.downloads.erase({ id: item.id }, () => {
          void chrome.runtime.lastError;
        });
      }
      removed += 1;
    }
  }
  return { ok: true, removed };
}

async function clearPreviousCredentialArtifacts(reason = "start_autopilot") {
  const stored = await storageGet([
    "ninjemailActiveAccount",
    "ninjemailLastCreatedAccount",
    "ninjemailGeneratedAccount",
    CREATED_ACCOUNTS_STORAGE_KEY,
    OAUTH_JOBS_STORAGE_KEY,
    OAUTH_ACTIVE_EMAIL_STORAGE_KEY,
    OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY,
    REGISTRATION_RUN_ID_STORAGE_KEY
  ]);
  const accounts = [
    state.activeAccount,
    state.lastCreatedAccount,
    state.lastGeneratedAccount,
    stored.ninjemailActiveAccount,
    stored.ninjemailLastCreatedAccount,
    stored.ninjemailGeneratedAccount,
    ...(Array.isArray(stored[CREATED_ACCOUNTS_STORAGE_KEY]) ? stored[CREATED_ACCOUNTS_STORAGE_KEY] : [])
  ];
  const emails = Array.from(new Set(accounts.map((item) => normalizeEmail(item && item.email)).filter(Boolean)));
  const storedOAuthJobs = stored[OAUTH_JOBS_STORAGE_KEY] && typeof stored[OAUTH_JOBS_STORAGE_KEY] === "object"
    ? stored[OAUTH_JOBS_STORAGE_KEY]
    : {};
  const oauthJobs = [
    ...Object.values(state.oauthJobs || {}),
    ...Object.values(storedOAuthJobs)
  ];
  const oauthTabIds = Array.from(new Set(oauthJobs
    .map((job) => Number(job && job.tabId))
    .filter((id) => Number.isFinite(id) && id > 0)));
  const webUi = { ok: true, reason: "history_preserved", data: { deleted_paths: [], preserved: true } };
  const downloads = { ok: true, reason: "history_preserved", removed: 0 };
  for (const tabId of oauthTabIds) {
    if (chrome.tabs && chrome.tabs.remove) {
      chrome.tabs.remove(tabId, () => {
        void chrome.runtime.lastError;
      });
    }
  }
  state.oauthJobs = {};
  state.credentialLocks = {};
  state.activeAccount = null;
  state.lastCreatedAccount = null;
  state.lastGeneratedAccount = null;
  state.registrationRunId = "";
  state.credentialStatus = { status: "new_registration", email: "", output_dir: state.credentialOutputDir || "<browser_downloads>" };
  await storageSet({
    [CREATED_ACCOUNTS_STORAGE_KEY]: [],
    ninjemailActiveAccount: null,
    ninjemailLastCreatedAccount: null,
    ninjemailGeneratedAccount: null,
    [OAUTH_JOBS_STORAGE_KEY]: {},
    [OAUTH_ACTIVE_EMAIL_STORAGE_KEY]: "",
    [OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY]: null,
    [REGISTRATION_RUN_ID_STORAGE_KEY]: ""
  });
  pushDedupeLog("STEP", "已重置当前注册缓存，历史四凭证已保留", {
    reason,
    emails,
    web_ui_ok: Boolean(webUi && webUi.ok),
    web_ui_deleted: webUi?.data?.deleted_paths || [],
    browser_download_removed: downloads?.removed || 0,
    oauth_tabs_closed: oauthTabIds
  });
}

function backupGeneratedAccount(account = {}, reason = "generated_account") {
  rememberGeneratedAccount(account);
  pushDedupeLog("ACCOUNT", accountLogMessage("当前注册账号已锁定", account), accountLogDetails(account, {
    reason,
    stage: "generated_account_locked"
  }));
  broadcastState();
}

async function buildOAuthAuthorizeUrl(record, oauthState, codeChallenge) {
  const params = new URLSearchParams({
    client_id: record.clientId || BUILTIN_CLIENT_ID,
    response_type: "code",
    redirect_uri: OAUTH_REDIRECT_URI,
    response_mode: "query",
    scope: OAUTH_SCOPES.join(" "),
    state: oauthState,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
    prompt: "login"
  });
  if (record.email) {
    params.set("login_hint", record.email);
  }
  if (isPersonalMicrosoftEmail(record.email)) {
    params.set("domain_hint", "consumers");
  }
  return `${OAUTH_AUTHORIZE_URL}?${params.toString()}`;
}

async function fetchOAuthTokensDirect(job, code) {
  const body = new URLSearchParams({
    client_id: job.clientId || BUILTIN_CLIENT_ID,
    grant_type: "authorization_code",
    code,
    redirect_uri: OAUTH_REDIRECT_URI,
    scope: OAUTH_SCOPES.join(" "),
    code_verifier: job.codeVerifier
  });
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), OAUTH_TOKEN_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(OAUTH_TOKEN_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body,
      signal: controller.signal
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const reason = data.error_description || data.error || `token_http_${response.status}`;
      throw new Error(reason);
    }
    if (!data.refresh_token) {
      throw new Error("missing_refresh_token_in_direct_response");
    }
    return data;
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("token_fetch_timeout");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function exchangeOAuthCodeForTokens(job, code) {
  try {
    const directFirst = await fetchOAuthTokensDirect(job, code);
    pushDedupeLog("OK", "扩展直连已换取刷新令牌", {
      email: job.email || "",
      output_dir: job.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    });
    return directFirst;
  } catch (error) {
    pushDedupeLog("STEP", "扩展直连换取刷新令牌失败，正在切换本地 Web UI 兜底", {
      email: job.email || "",
      reason: String(error && error.message || error || "token_fetch_failed"),
      output_dir: job.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    });
  }
  const webUiFirst = await postWebUiApi("ninjemail_oauth_code_exchange", {
    email: job.email || "",
    client_id: job.clientId || BUILTIN_CLIENT_ID,
    code,
    redirect_uri: OAUTH_REDIRECT_URI,
    scope: OAUTH_SCOPES.join(" "),
    code_verifier: job.codeVerifier || "",
    tenant: "consumers",
    source: "browser_extension"
  }, 40000);
  if (webUiFirst.ok && webUiFirst.data && webUiFirst.data.refresh_token) {
    pushDedupeLog("OK", "本地 Web UI 已换取刷新令牌", {
      email: job.email || "",
      route: webUiFirst.data.route || "",
      output_dir: job.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    });
    return webUiFirst.data;
  }
  const body = new URLSearchParams({
    client_id: job.clientId || BUILTIN_CLIENT_ID,
    grant_type: "authorization_code",
    code,
    redirect_uri: OAUTH_REDIRECT_URI,
    scope: OAUTH_SCOPES.join(" "),
    code_verifier: job.codeVerifier
  });
  try {
    const response = await fetch(OAUTH_TOKEN_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const reason = data.error_description || data.error || `token_http_${response.status}`;
      throw new Error(reason);
    }
    return data;
  } catch (error) {
    const directReason = String(error && error.message || error || "token_fetch_failed");
    pushDedupeLog("STEP", "扩展直连换取刷新令牌失败，正在切换本地 Web UI 兜底", {
      email: job.email || "",
      reason: directReason,
      output_dir: job.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    });
    const fallback = await postWebUiApi("ninjemail_oauth_code_exchange", {
      email: job.email || "",
      client_id: job.clientId || BUILTIN_CLIENT_ID,
      code,
      redirect_uri: OAUTH_REDIRECT_URI,
      scope: OAUTH_SCOPES.join(" "),
      code_verifier: job.codeVerifier || "",
      tenant: "consumers",
      source: "browser_extension"
    }, 40000);
    if (fallback.ok && fallback.data && fallback.data.refresh_token) {
      return fallback.data;
    }
    const fallbackReason = fallback.data?.reason || fallback.reason || directReason;
    throw new Error(`token_exchange_failed: ${directReason}; fallback: ${fallbackReason}`);
  }
}

async function completeOAuthTokenJob(job, tokens, tabId = null) {
  const email = normalizeEmail(job.email || tokenAccountFromTokens(tokens) || "");
  if (!email || !tokens.refresh_token) {
    throw new Error("missing_refresh_token");
  }
  if (job.expectedEmail && normalizeEmail(job.expectedEmail) && normalizeEmail(job.expectedEmail) !== email) {
    throw new Error(`account_mismatch:${email}`);
  }
  const record = {
    ...(job.account || {}),
    provider: job.provider || (job.account && job.account.provider) || state.provider || "outlook",
    domain: (job.account && job.account.domain) || "",
    username: (job.account && job.account.username) || email.split("@", 1)[0],
    email,
    password: (job.account && job.account.password) || job.password || "",
    clientId: job.clientId || BUILTIN_CLIENT_ID,
    accessToken: tokens.access_token || "",
    refreshToken: tokens.refresh_token,
    registrationRunId: job.registrationRunId || (job.account && job.account.registrationRunId) || state.registrationRunId || "",
    expiresIn: tokens.expires_in || "",
    tokenType: tokens.token_type || "",
    scope: tokens.scope || "",
    finalState: job.finalState || "",
    url: job.url || "",
    title: job.title || "",
    outputDir: job.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
    stableDelayMs: 0
  };
  if (!record.password) {
    throw new Error("missing_password_for_refresh_token");
  }
  setCredentialLock(email, { status: "saving", finalState: record.finalState || "", stage: "token_received" });
  state.credentialStatus = {
    status: "saving",
    email,
    output_dir: record.outputDir || "<browser_downloads>"
  };
  broadcastState();
  const result = await rememberCreatedAccount({
    account: record,
    refreshToken: tokens.refresh_token,
    clientId: record.clientId,
    output_dir: record.outputDir || "",
    finalState: record.finalState || "",
    url: record.url || "",
    title: record.title || "",
    stableDelayMs: 0,
    force: true,
    reason: "oauth_token_export"
  });
    if (!result.ok) {
      throw new Error(result.reason || "credential_save_failed");
    }
  const credentialPath = result.record?.credentialPath
    || result.record?.comboPath
    || result.webUi?.data?.credential_path
    || result.webUi?.data?.combo_path
    || "";
  pushDedupeLog("ACCOUNT", "四凭证完整输出", {
    email: record.email,
    password: record.password,
    client_id: record.clientId,
    refresh_token: record.refreshToken,
    combo: comboLineFor(record),
    credential_path: credentialPath,
    output_dir: record.outputDir || "<browser_downloads>"
  });
  setCredentialLock(email, { status: "done", finalState: record.finalState || "", tokenJobStatus: result.record?.tokenJobStatus || "saved" });
  state.credentialStatus = {
    status: "saved_or_token_started",
    email,
    credential_path: credentialPath,
    combo_path: credentialPath,
    token_job: result.record?.tokenJobStatus || "saved",
    web_ui_saved: Boolean(result.webUi && result.webUi.ok),
    browser_download_saved: Boolean(result.download && result.download.ok),
    output_dir: record.outputDir || "<browser_downloads>",
    reason: ""
  };
  broadcastState();
  if (tabId !== null && chrome.tabs && chrome.tabs.remove) {
    chrome.tabs.remove(tabId, () => {
      void chrome.runtime.lastError;
    });
  }
  storageSet({ [OAUTH_ACTIVE_EMAIL_STORAGE_KEY]: "", [OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY]: null }).finally(() => {});
  // OAuth 凭证保存完成，触发下一轮注册
  state.registrationCompleted = (state.registrationCompleted || 0) + 1;
  maybeStartNextRegistration(email);
  return { ok: true, record: result.record, tokens, result };
}

async function startBrowserOAuthTokenExport(account = {}, context = {}) {
  const email = normalizeEmail(account.email);
  if (!email || !account.password) {
    return { ok: false, reason: "missing_email_or_password" };
  }
  if (isCredentialLocked(email, context.force)) {
    const lock = credentialLock(email);
    return { ok: true, reason: lock?.status || "duplicate", duplicate: true, status: lock?.status || "" };
  }
  const codeVerifier = randomBase64Url(64);
  const codeChallenge = await sha256Base64Url(codeVerifier);
  const oauthState = randomBase64Url(18);
  const job = {
    state: oauthState,
    codeVerifier,
    codeChallenge,
    clientId: account.clientId || BUILTIN_CLIENT_ID,
    account: { ...account, email },
    email,
    expectedEmail: email,
    password: account.password || "",
    registrationRunId: account.registrationRunId || context.registrationRunId || state.registrationRunId || "",
    provider: account.provider || state.provider || "outlook",
    finalState: context.finalState || "",
    url: context.url || "",
    title: context.title || "",
    outputDir: context.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
    createdAt: nowIso(),
    status: "waiting_redirect",
    retryCount: 0
  };
  state.oauthJobs[oauthState] = job;
  await persistOAuthJobs();
  await storageSet({ [OAUTH_ACTIVE_EMAIL_STORAGE_KEY]: email });
  await storageSet({ [OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY]: job.account });
  setCredentialLock(email, { status: "token_pending", oauthState, finalState: job.finalState, stage: "oauth_started" });
  state.credentialStatus = {
    status: "token_pending",
    email,
    output_dir: job.outputDir || "<browser_downloads>",
    reason: "oauth_browser_pending"
  };
  broadcastState();
  const authUrl = await buildOAuthAuthorizeUrl(job, oauthState, codeChallenge);
  const createOptions = { url: authUrl, active: true };
  const windowId = Number(context.windowId || 0);
  if (Number.isFinite(windowId) && windowId > 0) {
    createOptions.windowId = windowId;
  }
  const openResult = await new Promise((resolve) => {
    chrome.tabs.create(createOptions, (tab) => {
      if (chrome.runtime.lastError || !tab || !tab.id) {
        resolve({ ok: false, reason: chrome.runtime.lastError?.message || "open_auth_failed" });
        return;
      }
      job.tabId = tab.id;
      state.oauthJobs[oauthState] = job;
      persistOAuthJobs().finally(() => {});
      resolve({ ok: true, tabId: tab.id });
    });
  });
  if (!openResult.ok) {
    delete state.oauthJobs[oauthState];
    await persistOAuthJobs();
    await storageSet({ [OAUTH_ACTIVE_EMAIL_STORAGE_KEY]: "" });
    await storageSet({ [OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY]: null });
    setCredentialLock(email, { status: "failed", reason: openResult.reason });
    state.credentialStatus = {
      status: "save_failed",
      email,
      reason: openResult.reason,
      output_dir: job.outputDir || "<browser_downloads>"
    };
    broadcastState();
    return { ok: false, reason: openResult.reason };
  }
  scheduleOAuthTabProbe(openResult.tabId, 900, "oauth_opened");
  scheduleOAuthTabProbe(openResult.tabId, 2600, "oauth_followup");
  scheduleOAuthRedirectWatch(oauthState, OAUTH_REDIRECT_WATCH_DELAY_MS);
  pushDedupeLog("STEP", "已打开 OAuth 授权页，等待刷新令牌回填", {
    email,
    tabId: openResult.tabId,
    output_dir: job.outputDir || "<browser_downloads>"
  });
  return { ok: true, oauthState, tabId: openResult.tabId };
}

async function startOAuthTokenExport(account = {}, context = {}) {
  return startBrowserOAuthTokenExport(account, context);
}

async function handleOAuthRedirect(tabId, url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch (error) {
    return false;
  }
  const callbackHost = String(parsed.hostname || "").replace(/^\[|\]$/g, "").toLowerCase();
  if (!["localhost", "127.0.0.1", "::1"].includes(callbackHost)) return false;
  if (String(parsed.port || "") !== "8765") return false;
  const code = parsed.searchParams.get("code") || "";
  const oauthState = parsed.searchParams.get("state") || "";
  const error = parsed.searchParams.get("error") || "";
  if (!code && !error) return false;
  const job = await oauthJobByState(oauthState);
  if (!job) return false;
  if (job.registrationRunId && state.registrationRunId && job.registrationRunId !== state.registrationRunId) {
    await removeOAuthJob(oauthState);
    pushDedupeLog("STEP", "已忽略上一轮 OAuth 回调", {
      email: job.email || "",
      job_run_id: job.registrationRunId,
      current_run_id: state.registrationRunId
    });
    return true;
  }
  if (job.tabId && tabId !== job.tabId) return false;
  if (["exchanging", "done"].includes(job.status || "")) return true;
  if (code && chrome.tabs && chrome.tabs.update) {
    chrome.tabs.update(tabId, { url: "about:blank" }, () => {
      void chrome.runtime.lastError;
    });
  }
  if (error) {
    delete state.oauthJobs[oauthState];
    await persistOAuthJobs();
    await storageSet({ [OAUTH_ACTIVE_EMAIL_STORAGE_KEY]: "" });
    await storageSet({ [OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY]: null });
    setCredentialLock(job.email, { status: "failed", reason: error, stage: "oauth_error" });
    state.credentialStatus = {
      status: "save_failed",
      email: job.email,
      reason: error,
      output_dir: job.outputDir || "<browser_downloads>"
    };
    broadcastState();
    pushDedupeLog("BLOCK", "OAuth 授权失败", { email: job.email, reason: error });
    return true;
  }
  try {
    job.status = "exchanging";
    state.oauthJobs[oauthState] = job;
    await persistOAuthJobs();
    pushDedupeLog("STEP", "已收到 OAuth 回调，正在交换刷新令牌", {
      email: job.email,
      tabId,
      output_dir: job.outputDir || "<browser_downloads>"
    });
    const tokens = await exchangeOAuthCodeForTokens(job, code);
    const actualEmail = tokenAccountFromTokens(tokens) || job.email;
    if (actualEmail && normalizeEmail(actualEmail) !== normalizeEmail(job.email)) {
      throw new Error(`account_mismatch:${actualEmail}`);
    }
    await completeOAuthTokenJob(job, tokens, tabId);
    delete state.oauthJobs[oauthState];
    await persistOAuthJobs();
    await storageSet({ [OAUTH_ACTIVE_EMAIL_STORAGE_KEY]: "" });
    await storageSet({ [OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY]: null });
    pushDedupeLog("OK", "刷新令牌已获取并保存四凭证", {
      email: job.email,
      output_dir: job.outputDir || "<browser_downloads>",
      credential_file: credentialFilenameFor(job.email)
    });
  } catch (error) {
    delete state.oauthJobs[oauthState];
    await persistOAuthJobs();
    await storageSet({ [OAUTH_ACTIVE_EMAIL_STORAGE_KEY]: "" });
    await storageSet({ [OAUTH_ACTIVE_ACCOUNT_STORAGE_KEY]: null });
    const detailedReason = String(error && error.message || error);
    setCredentialLock(job.email, { status: "failed", reason: detailedReason, stage: "oauth_exchange_failed" });
    state.credentialStatus = {
      status: "save_failed",
      email: job.email,
      reason: detailedReason,
      output_dir: job.outputDir || "<browser_downloads>"
    };
    broadcastState();
    pushDedupeLog("BLOCK", "刷新令牌交换失败", {
      email: job.email,
      reason: detailedReason,
      build: BACKGROUND_BUILD
    });
  }
  return true;
}

async function rememberCreatedAccount(payload = {}) {
  const account = payload.account || {};
  if (payload.manualAccount && payload.manualAccount.email && payload.manualAccount.password) {
    account.email = payload.manualAccount.email;
    account.password = payload.manualAccount.password;
    account.clientId = payload.manualAccount.clientId || payload.manualAccount.client_id || account.clientId;
  }
  const email = normalizeEmail(account.email);
  if (!email || !email.includes("@") || !account.password) {
    return { ok: false, reason: "missing_email_or_password" };
  }
  const requestedOutputDir = String(payload.output_dir || payload.outputDir || state.credentialOutputDir || "").trim();
  const outputDir = requestedOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR;
  if (requestedOutputDir) {
    state.credentialOutputDir = outputDir;
    await storageSet({ [CREDENTIAL_OUTPUT_DIR_STORAGE_KEY]: outputDir });
  }

  const record = {
    provider: account.provider || payload.provider || state.provider || "outlook",
    domain: account.domain || "",
    username: account.username || email.split("@", 1)[0],
    email,
    password: account.password,
    clientId: payload.clientId || payload.client_id || account.clientId || account.client_id || BUILTIN_CLIENT_ID,
    accessToken: payload.accessToken || payload.access_token || account.accessToken || account.access_token || "",
    refreshToken: payload.refreshToken || payload.refresh_token || "",
    registrationRunId: payload.registrationRunId || payload.registration_run_id || account.registrationRunId || state.registrationRunId || "",
    expiresIn: payload.expiresIn || payload.expires_in || account.expiresIn || account.expires_in || "",
    tokenType: payload.tokenType || payload.token_type || account.tokenType || account.token_type || "",
    scope: payload.scope || account.scope || "",
    finalState: payload.finalState || payload.final_state || "",
    url: payload.url || "",
    title: payload.title || "",
    outputDir,
    stableDelayMs: Number(payload.stableDelayMs || payload.stable_delay_ms || 0) || 0,
    savedAt: nowIso()
  };
  if (!record.refreshToken && !payload.allowIncompleteSave) {
    state.credentialStatus = {
      status: "save_failed",
      reason: "missing_refresh_token",
      email,
      output_dir: outputDir || "<browser_downloads>"
    };
    return { ok: false, reason: "missing_refresh_token", record };
  }

  const stored = await storageGet([CREATED_ACCOUNTS_STORAGE_KEY]);
  const existing = Array.isArray(stored[CREATED_ACCOUNTS_STORAGE_KEY]) ? stored[CREATED_ACCOUNTS_STORAGE_KEY] : [];
  const previous = existing.find((item) => normalizeEmail(item && item.email) === email);
  const previousAt = Date.parse(previous && previous.savedAt || "");
  const previousAgeMs = Number.isFinite(previousAt) ? Date.now() - previousAt : Number.POSITIVE_INFINITY;
  const shouldPostWebUi = (
    Boolean(payload.force || payload.force_export)
    || !previous
    || previous.webUiOk === false
    || previousAgeMs > 5 * 60 * 1000
  );
  const next = existing.filter((item) => normalizeEmail(item && item.email) !== email);
  let download = { ok: false, reason: "not_needed" };
  let webUi = { ok: false, reason: "web_ui_not_requested", data: { token_job: { status: "not_requested" } } };
  const delayMs = Math.max(0, Math.min(120000, record.stableDelayMs || 0));
  if (delayMs > 0) {
    state.credentialStatus = {
      status: "waiting_page_stable",
      email,
      delay_ms: delayMs,
      output_dir: outputDir || "<browser_downloads>"
    };
    setStatus("observing");
    pushDedupeLog("STEP", "账号已进入稳定等待，稍后自动补齐四凭证", {
      email,
      delay_ms: delayMs,
      output_dir: outputDir || "<browser_downloads>"
    });
    pushDedupeLog("ACCOUNT", accountLogMessage("账号进入稳定等待", record), accountLogDetails(record, {
      delay_ms: delayMs,
      output_dir: outputDir || "<browser_downloads>",
      stage: "waiting_page_stable"
    }));
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  state.credentialStatus = {
    status: "running",
    email,
    output_dir: outputDir || "<browser_downloads>"
  };
  broadcastState();
  const canBrowserDownloadFallback = outputDirSupportsBrowserDownload(outputDir);
  const preferBrowserDownload = Boolean(record.refreshToken && canBrowserDownloadFallback);
  if (preferBrowserDownload) {
    download = await downloadCredentialFile(record);
  }
  webUi = (!preferBrowserDownload && shouldPostWebUi)
    ? await postAccountToWebUi(record)
    : { ok: false, reason: "web_ui_not_requested", data: { token_job: { status: "not_requested" } } };
  let webUiCredentialPath = String(webUi?.data?.credential_path || webUi?.data?.combo_path || "");
  let webUiPathValid = !webUi || !webUi.ok || !webUiCredentialPath || credentialPathMatchesEmail(email, webUiCredentialPath);
  if (webUi && webUi.ok && webUiCredentialPath && !webUiPathValid) {
    webUi = {
      ...webUi,
      ok: false,
      reason: "unexpected_credential_filename",
      data: {
        ...(webUi.data || {}),
        ok: false,
        reason: "unexpected_credential_filename"
      }
    };
  }
  if (record.refreshToken && (!webUi?.ok || !webUiCredentialPath || !webUiPathValid)) {
    const recovered = await checkSavedCredentialViaWebUi(record);
    if (recovered.ok) {
      webUi = {
        ok: true,
        reason: "verified_saved_credential",
        data: {
          ...(webUi?.data || {}),
          ...recovered.data,
          ok: true,
          reason: "verified_saved_credential"
        }
      };
      webUiCredentialPath = String(recovered.data.credential_path || recovered.data.combo_path || webUiCredentialPath || "");
      webUiPathValid = !webUiCredentialPath || credentialPathMatchesEmail(email, webUiCredentialPath);
      record.refreshToken = String(recovered.data.refresh_token || record.refreshToken || "").trim();
    }
  }
  if (record.refreshToken && canBrowserDownloadFallback && !download.ok && (!shouldPostWebUi || !webUi || !webUi.ok)) {
    pushDedupeLog("STEP", "Web UI 保存失败，正在回退到浏览器下载落盘四凭证", {
      email,
      output_dir: outputDir || "<browser_downloads>",
      web_ui_reason: webUi?.reason || webUi?.data?.reason || ""
    });
    download = await downloadCredentialFile(record);
  }
  const credentialPath = (webUi?.ok && credentialPathMatchesEmail(email, webUiCredentialPath))
    ? webUiCredentialPath
    : (download.ok ? (download.finalFilename || download.filename || credentialDownloadFilenameFor(record)) : "");
  record.webUiOk = Boolean(webUi && webUi.ok);
  record.browserDownloadOk = Boolean(download && download.ok);
  record.downloadId = download?.downloadId || record.downloadId || null;
  record.tokenJobStatus = record.refreshToken
    ? "saved"
    : (webUi?.data?.token_job?.status || "not_requested");
  record.credentialPath = credentialPath;
  record.comboPath = credentialPath;
  if (record.refreshToken && !record.webUiOk && !record.browserDownloadOk) {
    const reason = normalizeCredentialSaveFailureReason(
      webUi?.reason || webUi?.data?.reason || download?.reason || "credential_save_failed",
      outputDir
    );
    state.credentialStatus = {
      status: "save_failed",
      email,
      reason,
      output_dir: outputDir || "<browser_downloads>"
    };
    return { ok: false, reason, record, download, webUi };
  }
  next.push(record);
  await storageSet({
    [CREATED_ACCOUNTS_STORAGE_KEY]: next,
    ninjemailActiveAccount: record,
    ninjemailLastCreatedAccount: record
  });
  state.activeAccount = record;
  state.lastCreatedAccount = record;
  state.credentialStatus = {
    status: (record.webUiOk || record.browserDownloadOk) ? "saved_or_token_started" : "save_failed",
    email,
    credential_path: credentialPath,
    combo_path: credentialPath,
    token_job: record.tokenJobStatus,
    web_ui_saved: record.webUiOk,
    browser_download_saved: record.browserDownloadOk,
    output_dir: outputDir || "<browser_downloads>",
    reason: webUi?.reason || webUi?.data?.reason || ""
  };
  pushDedupeLog("ACCOUNT", accountLogMessage("四凭证保存/补齐完成", record), accountLogDetails(record, {
    credential_path: state.credentialStatus.credential_path || "",
    web_ui_saved: record.webUiOk,
    browser_download_saved: Boolean(download && download.ok),
    token_job: record.tokenJobStatus,
    output_dir: outputDir || "<browser_downloads>",
    reason: webUi?.reason || webUi?.data?.reason || "",
    stage: "created_account_saved"
  }));
  return { ok: true, record, download, webUi };
}

function frameKey(payload = {}) {
  if (payload.isTopFrame || payload.frame === "top") return "top";
  const host = payload.host || "child";
  const url = String(payload.url || "").slice(0, 180);
  return `child:${host}:${url}`;
}

function reportList() {
  return Object.values(state.frameReports || {});
}

function topReport() {
  return state.frameReports.top || null;
}

function isActionableTopReport(report) {
  if (!report || report.blocker) return false;
  return [
    "fill_username",
    "fill_password",
    "fill_profile",
    "fill_birthdate",
    "fill_gmail_profile",
    "fill_gmail_birthdate",
    "fill_gmail_username",
    "fill_gmail_password",
    "fill_yahoo_account_form",
    "post_challenge",
    "final_state"
  ].includes(report.activeStep || "");
}

function summarizeServices() {
  const now = Date.now();
  for (const [key, item] of Object.entries(state.frameReports || {})) {
    const received = Date.parse(item.receivedAt || item.checkedAt || "");
    if (Number.isFinite(received) && now - received > 15000) {
      delete state.frameReports[key];
    }
  }
  const reports = reportList();
  const top = topReport();
  const topActionable = isActionableTopReport(top);
  const challengeFrames = reports.filter((item) => item.blocker);
  state.challengeFrames = challengeFrames.map((item) => ({
    type: item.blocker?.type || "",
    label: item.blocker?.label || item.blocker?.type || "",
    action: item.blocker?.action || "",
    evidence: item.blocker?.evidence || "",
    url: item.url || "",
    host: item.host || "",
    frame: item.frame || "child",
    checkedAt: item.checkedAt || "",
    blocking: item.frame === "top" || !topActionable
  }));
  const blockingChallenges = state.challengeFrames.filter((item) => item.blocking);
  state.services = {
    extension: { status: "ok", text: "插件已加载" },
    pageProbe: {
      status: top ? "ok" : "waiting",
      text: top ? "主页面已连接" : "等待主页面上报"
    },
    challengeProbe: {
      status: blockingChallenges.length ? "warn" : "ok",
      text: blockingChallenges.length
        ? `检测到 ${blockingChallenges.length} 个阻塞挑战 frame`
        : (challengeFrames.length ? "发现挑战 frame，但主页面可继续" : "未检测到挑战 frame")
    },
    logs: { status: "ok", text: `${state.logs.length} 条日志` }
  };
}

function mergePrimaryReport(primary) {
  if (state.status === "stopped") {
    return;
  }
  if (!primary) {
    summarizeServices();
    setStatus(state.challengeFrames.some((item) => item.blocking) ? "manual_wait" : "idle");
    return;
  }

  state.currentUrl = primary.url || "";
  state.title = primary.title || "";
  state.activeStep = primary.activeStep || "";
  state.rootCause = primary.rootCause || null;
  state.postChallengeState = primary.postChallengeState || "";
  state.finalState = primary.finalState || "";
  state.steps = applyCredentialStep(applyStepHistory(primary.steps || []));
  state.elements = primary.elements || {};
  const credentialBusy = ["waiting_page_stable", "token_pending", "running", "saving"].includes(String(state.credentialStatus?.status || ""));
  if (credentialBusy) {
    state.activeStep = "export_credentials";
  }

  if (primary.blocker) {
    state.blocker = primary.blocker;
    setStatus(primary.blocker.type === "hsprotect" ? "manual_wait" : "blocked");
    return;
  }

  state.blocker = null;
  if (credentialBusy) {
    setStatus("observing");
  } else if (primary.finalState) {
    setStatus("done");
  } else if (primary.postChallengeState) {
    setStatus("post_challenge");
  } else {
    setStatus("observing");
  }
}

function rememberObservedSteps(payload = {}) {
  const observed = Array.isArray(payload.observedSteps) ? payload.observedSteps : [];
  for (const item of observed) {
    if (!item || !item.id) continue;
    state.stepHistory[item.id] = {
      status: item.status || "seen",
      evidence: item.evidence || "",
      at: payload.checkedAt || nowIso(),
      url: payload.url || ""
    };
  }
}

function applyStepHistory(steps = []) {
  return steps.map((step) => {
    const history = state.stepHistory[step.id];
    if (!history) return step;
    if (step.status === "pending") {
      return {
        ...step,
        status: "seen",
        evidence: history.evidence ? `历史观察：${history.evidence}` : step.evidence
      };
    }
    return step;
  });
}

function applyCredentialStep(steps = []) {
  const result = Array.isArray(steps) ? [...steps] : [];
  const hasStep = result.some((step) => step && step.id === "export_credentials");
  if (!hasStep) {
    result.push({
      id: "export_credentials",
      label: "获取四凭证",
      intent: "注册成功后获取并保存：账号----密码----客户端ID----刷新令牌。",
      status: "pending",
      evidence: "等待账号注册成功"
    });
  }
  const index = result.findIndex((step) => step && step.id === "export_credentials");
  if (index < 0) return result;
  const cred = state.credentialStatus || {};
  const finalObserved = Boolean(state.finalState || state.postChallengeState === "account_home" || state.postChallengeState === "login_live_success" || state.postChallengeState === "oauth_complete");
  let status = result[index].status || "pending";
  let evidence = result[index].evidence || "等待账号注册成功";
  if (cred.status === "waiting_page_stable") {
    status = "current";
    evidence = `等待页面稳定 ${cred.delay_ms || ""}ms 后获取刷新令牌`;
  } else if (cred.status === "token_pending") {
    status = "current";
    evidence = `正在通过浏览器 OAuth 获取刷新令牌：${cred.email || ""}`;
  } else if (cred.status === "running") {
    status = "current";
    evidence = `正在获取/保存四凭证：${cred.email || ""}`;
  } else if (cred.status === "saved_or_token_started") {
    status = "done";
    evidence = `已保存四凭证：${cred.credential_path || cred.combo_path || cred.output_dir || ""}`;
  } else if (cred.status === "save_failed") {
    status = "blocked";
    evidence = `四凭证保存失败：${cred.reason || "unknown"}`;
  } else if (finalObserved) {
    status = "current";
    evidence = "账号已注册成功，等待获取刷新令牌后保存四凭证";
  }
  result[index] = {
    ...result[index],
    status,
    evidence
  };
  return result;
}

function recomputeStateFromFrames() {
  summarizeServices();
  const top = topReport();
  const topActionable = isActionableTopReport(top);
  const fallback = top || reportList()[0] || null;
  mergePrimaryReport(fallback);
  const blockingChallenges = state.challengeFrames.filter((item) => item.blocking);
  if (!state.blocker && blockingChallenges.length && !state.postChallengeState && !state.finalState && !topActionable) {
    state.rootCause = {
      blocker: "child_challenge_frame",
      reason: "子 frame 检测到人机验证",
      evidence: blockingChallenges.map((item) => `${item.label || item.type}: ${item.evidence}`).join("; "),
      nextAction: "查看挑战详情；如果页面显示挑战，手动完成后点击扫描"
    };
    setStatus("manual_wait");
  }
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs && tabs.length ? tabs[0] : null;
}

function createTab(url) {
  return new Promise((resolve) => {
    chrome.tabs.create({ url }, (tab) => {
      resolve(tab && tab.id ? tab : null);
    });
  });
}

function waitForTabLoad(tabId, timeoutMs = 18000) {
  return new Promise((resolve) => {
    if (!tabId || !chrome.tabs || !chrome.tabs.onUpdated) {
      resolve(false);
      return;
    }
    let done = false;
    const finish = (ok) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve(ok);
    };
    const listener = (updatedTabId, changeInfo) => {
      if (updatedTabId === tabId && changeInfo.status === "complete") finish(true);
    };
    const timer = setTimeout(() => finish(false), timeoutMs);
    chrome.tabs.onUpdated.addListener(listener);
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms || 0))));
}

function getTabById(tabId) {
  return new Promise((resolve) => {
    const id = Number(tabId || 0);
    if (!id || !chrome.tabs || !chrome.tabs.get) {
      resolve(null);
      return;
    }
    chrome.tabs.get(id, (tab) => {
      if (chrome.runtime.lastError || !tab || !tab.id) {
        resolve(null);
        return;
      }
      resolve(tab);
    });
  });
}

function isSupportedContentUrl(url = "") {
  const supportedHosts = [
    ...Object.values(PROVIDERS).flatMap((provider) => provider.hosts || []),
    "login.microsoftonline.com",
    "hsprotect.net"
  ];
  return supportedHosts.some((host) => String(url || "").includes(host));
}

async function ensureContentScript(tab) {
  if (!tab || !tab.id || !isSupportedContentUrl(tab.url || "")) return false;
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true },
      files: ["shared/flow-state.js", "content/outlook-signup.js"]
    });
    return true;
  } catch (error) {
    pushDedupeLog("BLOCK", "页面探针注入失败", {
      url: tab.url || "",
      reason: error && error.message ? error.message : String(error)
    });
    return false;
  }
}

function scheduleOAuthTabProbe(tabId, delayMs = 900, reason = "oauth_tab_probe") {
  if (!tabId || !chrome.tabs || !chrome.tabs.get) return;
  setTimeout(() => {
    chrome.tabs.get(tabId, async (tab) => {
      if (chrome.runtime.lastError || !tab || !tab.id) return;
      const injected = await ensureContentScript(tab);
      if (!injected || !chrome.tabs || !chrome.tabs.sendMessage) return;
      chrome.tabs.sendMessage(tab.id, { type: "NM_SCAN" }, { frameId: 0 }, () => {
        void chrome.runtime.lastError;
      });
      pushDedupeLog("STEP", "已检查 OAuth 授权页自动化探针", {
        tabId: tab.id,
        reason,
        url: tab.url || ""
      });
    });
  }, delayMs);
}

function scheduleOAuthRedirectWatch(oauthState, delayMs = OAUTH_REDIRECT_WATCH_DELAY_MS) {
  if (!oauthState) return;
  setTimeout(async () => {
    const job = await oauthJobByState(oauthState);
    if (!job || job.status !== "waiting_redirect") return;
    const retryCount = Number(job.retryCount || 0);
    if (retryCount >= OAUTH_REDIRECT_RETRY_MAX) {
      pushDedupeLog("BLOCK", "OAuth 回调超时，已达到重试上限", {
        email: job.email || "",
        retry_count: retryCount,
        output_dir: job.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
      });
      return;
    }
    const authUrl = await buildOAuthAuthorizeUrl(job.account || job, oauthState, job.codeChallenge || "");
    job.retryCount = retryCount + 1;
    state.oauthJobs[oauthState] = job;
    await persistOAuthJobs();
    const updated = await new Promise((resolve) => {
      if (job.tabId && chrome.tabs && chrome.tabs.update) {
        chrome.tabs.update(job.tabId, { url: authUrl, active: true }, (tab) => {
          resolve(Boolean(tab && !chrome.runtime.lastError));
        });
        return;
      }
      if (chrome.tabs && chrome.tabs.create) {
        chrome.tabs.create({ url: authUrl, active: true }, (tab) => {
          if (tab && tab.id) {
            job.tabId = tab.id;
            state.oauthJobs[oauthState] = job;
            persistOAuthJobs().finally(() => {});
          }
          resolve(Boolean(tab && tab.id && !chrome.runtime.lastError));
        });
        return;
      }
      resolve(false);
    });
    if (!updated) {
      pushDedupeLog("BLOCK", "OAuth 回调超时重试失败", {
        email: job.email || "",
        retry_count: job.retryCount,
        output_dir: job.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
      });
      return;
    }
    pushDedupeLog("STEP", "OAuth 回调超时，正在重试授权页", {
      email: job.email || "",
      retry_count: job.retryCount,
      tabId: job.tabId || "",
      output_dir: job.outputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    });
    if (job.tabId) {
      scheduleOAuthTabProbe(job.tabId, 1200, "oauth_retry");
    }
    scheduleOAuthRedirectWatch(oauthState, delayMs);
  }, delayMs);
}

async function scanActiveTab() {
  const tab = await getActiveTab();
  if (!tab || !tab.id) {
    pushLog("BLOCK", "没有可扫描的当前标签页");
    broadcastState();
    return;
  }
  await ensureContentScript(tab);
  chrome.tabs.sendMessage(tab.id, { type: "NM_SCAN" }, () => {
    if (chrome.runtime.lastError) {
      pushLog("BLOCK", "当前页面探针未就绪", { reason: chrome.runtime.lastError.message });
      broadcastState();
    } else {
      pushLog("STEP", "已请求扫描当前页面", { tabId: tab.id });
      broadcastState();
    }
  });
}

async function sendStepAction(action, extra = {}) {
  if (state.status === "stopped" && !state.autoRunEnabled && action !== "stop_auto") {
    pushLog("BLOCK", "自动执行已停止，页面操作被锁定；请先点“继续执行”", {
      action,
      stepId: extra.stepId || ""
    });
    broadcastState();
    return { ok: false, reason: "autopilot_stopped" };
  }
  const tab = await getActiveTab();
  if (!tab || !tab.id) {
    pushLog("BLOCK", "没有可操作的当前标签页");
    broadcastState();
    return { ok: false, reason: "no_active_tab" };
  }
  const injected = await ensureContentScript(tab);
  if (!injected) {
    pushLog("BLOCK", "步骤操作发送失败", {
      action,
      reason: "content_script_injection_failed",
      url: tab.url || ""
    });
    broadcastState();
    return { ok: false, reason: "content_script_injection_failed", url: tab.url || "" };
  }
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tab.id, { type: "NM_STEP_ACTION", action, ...extra }, { frameId: 0 }, (response) => {
      if (chrome.runtime.lastError) {
        const reason = chrome.runtime.lastError.message || "send_message_failed";
        pushLog("BLOCK", "步骤操作发送失败", { action, reason, url: tab.url || "" });
        broadcastState();
        resolve({ ok: false, reason, url: tab.url || "" });
      } else {
        pushLog("STEP", "步骤操作已发送", { action, tabId: tab.id, stepId: extra.stepId || "" });
        broadcastState();
        resolve({ ok: true, response, tabId: tab.id });
      }
    });
  });
}

function rememberStartAck(ack) {
  state.startAck = {
    type: "NM_START_AUTOPILOT_ACK",
    ok: false,
    provider: state.provider || "outlook",
    tabId: state.autoRunTabId || null,
    runId: state.registrationRunId || "",
    stage: "unknown",
    reason: "",
    at: nowIso(),
    ...(ack || {})
  };
  return state.startAck;
}

function startFailureAck(reason, extra = {}) {
  return rememberStartAck({
    ok: false,
    stage: extra.stage || "start_failed",
    reason: reason || "unknown",
    provider: extra.provider || state.provider || "outlook",
    tabId: extra.tabId || state.autoRunTabId || null,
    runId: extra.runId || state.registrationRunId || "",
    url: extra.url || state.currentUrl || "",
    response: extra.response || null
  });
}

async function failAutopilotStart(reason, extra = {}) {
  await clearAutoRunLease();
  setStatus("blocked");
  const ack = startFailureAck(reason, extra);
  pushLog("BLOCK", "自动执行启动失败：未收到页面 ACK", {
    provider: ack.provider,
    tabId: ack.tabId,
    runId: ack.runId,
    stage: ack.stage,
    reason: ack.reason,
    url: ack.url || ""
  });
  broadcastState();
  return ack;
}

async function prepareAccountRegenerationAfterMicrosoftProblem(payload = {}) {
  const email = normalizeEmail(
    payload.email
      || state.activeAccount?.email
      || state.lastGeneratedAccount?.email
      || state.lastCreatedAccount?.email
      || ""
  );
  if (email) {
    setCredentialLock(email, {
      status: "failed",
      finalState: "microsoft_problem",
      reason: payload.reason || "microsoft_problem"
    });
  }
  state.activeAccount = null;
  state.lastGeneratedAccount = null;
  state.credentialStatus = {
    status: "regenerate_required",
    email,
    reason: "microsoft_problem",
    output_dir: state.credentialOutputDir || "<browser_downloads>"
  };
  await clearAutoRunLease();
  await storageSet({
    ninjemailActiveAccount: null,
    ninjemailGeneratedAccount: null
  });
  pushDedupeLog("BLOCK", "Microsoft 问题页：已丢弃当前生成账号，下一次开始注册会重新生成", {
    email,
    activeStep: payload.activeStep || "",
    postChallengeState: payload.postChallengeState || "microsoft_problem",
    reason: payload.reason || "microsoft_problem",
    url: payload.evidence || payload.url || state.currentUrl || ""
  });
}

function updateTabUrl(tabId, url) {
  return new Promise((resolve) => {
    const id = Number(tabId || 0);
    if (!id || !chrome.tabs || !chrome.tabs.update) {
      resolve({ ok: false, reason: "missing_tab" });
      return;
    }
    chrome.tabs.update(id, { url, active: true }, (tab) => {
      if (chrome.runtime.lastError || !tab || !tab.id) {
        resolve({ ok: false, reason: chrome.runtime.lastError?.message || "tab_update_failed" });
        return;
      }
      resolve({ ok: true, tab });
    });
  });
}

function createRegistrationTab(url) {
  return new Promise((resolve) => {
    if (!chrome.tabs || !chrome.tabs.create) {
      resolve({ ok: false, reason: "tabs_create_unavailable" });
      return;
    }
    chrome.tabs.create({ url, active: true }, (tab) => {
      if (chrome.runtime.lastError || !tab || !tab.id) {
        resolve({ ok: false, reason: chrome.runtime.lastError?.message || "tab_create_failed" });
        return;
      }
      resolve({ ok: true, tab });
    });
  });
}

async function restartAfterMicrosoftProblem(payload = {}, senderTab = null) {
  const wantsNewAccount = payload.requestNewAccount
    || payload.postChallengeState === "microsoft_problem"
    || payload.blocker === "microsoft_problem";
  if (!wantsNewAccount || state.microsoftProblemRestarting) return false;
  if (state.microsoftProblemAutoRetries >= MICROSOFT_PROBLEM_AUTO_RETRY_MAX) {
    pushDedupeLog("BLOCK", "Microsoft 问题页自动重开已达上限，等待手动开始注册", {
      retries: state.microsoftProblemAutoRetries,
      max: MICROSOFT_PROBLEM_AUTO_RETRY_MAX
    });
    broadcastState();
    return false;
  }
  const config = providerConfig(state.provider || payload.provider || "outlook");
  const tabId = senderTab?.id || state.autoRunTabId || 0;
  state.microsoftProblemRestarting = true;
  state.microsoftProblemAutoRetries += 1;
  pushDedupeLog("STEP", "Microsoft 问题页：正在自动重开注册页并生成新账号", {
    retry: state.microsoftProblemAutoRetries,
    max: MICROSOFT_PROBLEM_AUTO_RETRY_MAX,
    provider: config.key,
    tabId,
    url: config.url
  });
  broadcastState();
  let openResult = await updateTabUrl(tabId, config.url);
  if (!openResult.ok) {
    openResult = await createRegistrationTab(config.url);
  }
  if (!openResult.ok) {
    state.microsoftProblemRestarting = false;
    pushDedupeLog("BLOCK", "Microsoft 问题页自动重开注册页失败", {
      reason: openResult.reason,
      tabId,
      url: config.url
    });
    broadcastState();
    return false;
  }
  setStatus("opening");
  await new Promise((resolve) => setTimeout(resolve, MICROSOFT_PROBLEM_AUTO_RETRY_DELAY_MS));
  state.microsoftProblemRestarting = false;
  const ack = await startAutopilot(null, { tabId: openResult.tab.id, autoRetry: true });
  summarizeServices();
  broadcastState();
  return Boolean(ack && ack.ok);
}

function sendAutoRunWithAck(tab, account, timeoutMs = START_ACK_TIMEOUT_MS) {
  return new Promise((resolve) => {
    if (!tab || !tab.id) {
      resolve(startFailureAck("no_active_tab", { stage: "preflight" }));
      return;
    }
    let settled = false;
    const finish = (ack) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolve(rememberStartAck(ack));
    };
    const timeout = setTimeout(() => {
      finish({
        ok: false,
        provider: account?.provider || state.provider || "outlook",
        tabId: tab.id,
        runId: account?.registrationRunId || state.registrationRunId || "",
        stage: "content_ack_timeout",
        reason: "start_autopilot_ack_timeout",
        url: tab.url || ""
      });
    }, timeoutMs);
    chrome.tabs.sendMessage(
      tab.id,
      {
        type: "NM_STEP_ACTION",
        action: "auto_run",
        account,
        expectAck: true,
        runId: account?.registrationRunId || state.registrationRunId || ""
      },
      { frameId: 0 },
      (response) => {
        if (chrome.runtime.lastError) {
          finish({
            ok: false,
            provider: account?.provider || state.provider || "outlook",
            tabId: tab.id,
            runId: account?.registrationRunId || state.registrationRunId || "",
            stage: "send_message_failed",
            reason: chrome.runtime.lastError.message || "send_message_failed",
            url: tab.url || ""
          });
          return;
        }
        if (!response) {
          finish({
            ok: false,
            provider: account?.provider || state.provider || "outlook",
            tabId: tab.id,
            runId: account?.registrationRunId || state.registrationRunId || "",
            stage: "empty_content_response",
            reason: "empty_content_response",
            url: tab.url || ""
          });
          return;
        }
        finish({
          ok: response.ok !== false,
          provider: account?.provider || state.provider || "outlook",
          tabId: tab.id,
          runId: account?.registrationRunId || state.registrationRunId || "",
          stage: response.ok === false ? "content_rejected" : "content_ack",
          reason: response.reason || (response.ok === false ? "content_rejected" : "content_ack"),
          url: tab.url || "",
          response
        });
      }
    );
  });
}

async function waitForAutoRunAck(tab, account, controlVersion, totalTimeoutMs = START_CONTENT_READY_TIMEOUT_MS) {
  const deadline = Date.now() + Math.max(START_ACK_TIMEOUT_MS, Number(totalTimeoutMs || START_CONTENT_READY_TIMEOUT_MS));
  let lastAck = null;
  let attempts = 0;
  while (Date.now() < deadline) {
    if (controlVersion !== state.autoRunControlVersion || !state.autoRunEnabled) {
      return rememberStartAck(startFailureAck("autopilot_stopped_before_content_ack", {
        stage: "stopped",
        provider: account?.provider || state.provider || "outlook",
        tabId: tab?.id || null,
        runId: account?.registrationRunId || state.registrationRunId || "",
        url: tab?.url || state.currentUrl || ""
      }));
    }
    const freshTab = await getTabById(tab.id) || tab;
    const injected = await ensureContentScript(freshTab);
    attempts += 1;
    const ack = await sendAutoRunWithAck(freshTab, account, Math.min(3500, Math.max(1200, deadline - Date.now())));
    lastAck = ack;
    if (ack && ack.ok) {
      return ack;
    }
    const retryable = !injected
      || ["send_message_failed", "content_ack_timeout", "empty_content_response"].includes(ack?.stage || "")
      || /receiving end|could not establish connection|context invalidated|frame/i.test(String(ack?.reason || ""));
    if (!retryable) return ack;
    pushDedupeLog("STEP", "页面探针尚未就绪，正在重试自动执行 ACK", {
      provider: account?.provider || state.provider || "outlook",
      tabId: freshTab.id,
      runId: account?.registrationRunId || state.registrationRunId || "",
      attempt: attempts,
      stage: ack?.stage || (injected ? "unknown" : "content_injection_pending"),
      reason: ack?.reason || ""
    });
    await delay(START_CONTENT_RETRY_DELAY_MS);
  }
  return rememberStartAck({
    ok: false,
    provider: account?.provider || state.provider || "outlook",
    tabId: tab.id,
    runId: account?.registrationRunId || state.registrationRunId || "",
    stage: lastAck?.stage || "content_ack_timeout",
    reason: lastAck?.reason || "start_autopilot_ack_timeout",
    url: tab.url || state.currentUrl || "",
    response: lastAck?.response || null
  });
}

async function maybeResumeAutoRunForContent(sender, payload = {}) {
  const tabId = sender && sender.tab && sender.tab.id;
  if (!payload.isTopFrame || !state.autoRunEnabled || !tabId) return;
  if (!isAutoRunLeaseFresh()) {
    await clearAutoRunLease();
    return;
  }
  if (state.autoRunTabId && tabId !== state.autoRunTabId) return;
  if (payload.finalState || payload.blocker) return;
  // CRITICAL: do NOT resume auto-run if any blocking challenge exists
  const blockingChallenges = (state.challengeFrames || []).filter((item) => item.blocking);
  if (blockingChallenges.length) {
    pushDedupeLog("BLOCK", "存在阻塞的人机验证 frame，停止自动恢复", {
      challenges: blockingChallenges.map((c) => `${c.type}:${c.evidence}`).join("; "),
      activeStep: payload.activeStep || ""
    });
    await clearAutoRunLease();
    if (tabId) {
      chrome.tabs.sendMessage(tabId, { type: "NM_STEP_ACTION", action: "stop_auto" }, () => { void chrome.runtime.lastError; });
    }
    summarizeServices();
    broadcastState();
    return;
  }
  if (Date.now() - Number(state.autoRunLastCommandAt || 0) < 500) return;
  const signature = `${tabId}:${payload.url || ""}:${payload.activeStep || ""}:${payload.postChallengeState || ""}`;
  if (state.autoRunLastResumeSignature === signature) return;
  state.autoRunLastResumeSignature = signature;
  const account = state.lastGeneratedAccount || await activeOrLastAccount();
  if (!account || !account.email || !account.password) return;
  state.autoRunLastCommandAt = Date.now();
  chrome.tabs.sendMessage(tabId, { type: "NM_STEP_ACTION", action: "auto_run", account }, { frameId: 0 }, () => {
    void chrome.runtime.lastError;
  });
}

async function startAutopilotLegacy() {
  const tab = await getActiveTab();
  if (!tab || !tab.id) {
    pushLog("BLOCK", "没有可执行的当前标签页");
    broadcastState();
    return;
  }
  const url = String(tab.url || "");
  if (!url.includes("signup.live.com")) {
    pushLog("BLOCK", "当前标签页不是 Outlook/Hotmail 注册页", { url });
    broadcastState();
    return;
  }
  const account = generatedOutlookAccount();
  state.autoRunEnabled = true;
  state.autoRunTabId = tab.id;
  state.autoRunStartedAt = Date.now();
  state.autoRunLastResumeSignature = "";
  pushDedupeLog("ACCOUNT", accountLogMessage("Outlook 自动执行账号已生成", account), accountLogDetails(account, {
    tabId: tab.id,
    mode: "stop_at_real_challenge",
    stage: "start_autopilot_legacy"
  }));
  state.autoRunLastCommandAt = Date.now();
  chrome.storage.local.set({
    ninjemailActiveAccount: account,
    [AUTORUN_ENABLED_STORAGE_KEY]: true,
    [AUTORUN_TAB_ID_STORAGE_KEY]: tab.id,
    [AUTORUN_STARTED_AT_STORAGE_KEY]: state.autoRunStartedAt
  }, () => {
  chrome.tabs.sendMessage(tab.id, { type: "NM_STEP_ACTION", action: "auto_run", account }, () => {
    if (chrome.runtime.lastError) {
      pushLog("BLOCK", "自动执行启动失败", { reason: chrome.runtime.lastError.message });
      broadcastState();
    } else {
      pushLog("STEP", "已启动 Outlook 普通步骤自动执行", {
        tabId: tab.id,
        username: account.username,
        mode: "stop_at_real_challenge"
      });
      broadcastState();
    }
  });
  });
}

async function openSelectedRegistration(provider = state.provider) {
  const config = providerConfig(provider);
  setSelectedProvider(config.key);
  state.autoRunEnabled = false;
  await clearAutoRunLease();
  state.activeAccount = null;
  state.lastGeneratedAccount = null;
  state.credentialStatus = { status: "new_registration", email: "", output_dir: state.credentialOutputDir || "<browser_downloads>" };
  await storageSet({
    ninjemailActiveAccount: null,
    ninjemailGeneratedAccount: null
  });
  chrome.tabs.create({ url: config.url });
  setStatus("opening");
  pushLog("STEP", `已打开 ${config.label} 注册页`, {
    provider: config.key,
    url: config.url,
    auto_run: false
  });
  broadcastState();
}

async function maybeStartNextRegistration(completedEmail) {
  const total = state.registrationCount || 1;
  const completed = state.registrationCompleted || 0;
  if (completed >= total) {
    pushDedupeLog("OK", `全部注册任务完成 (${completed}/${total})`, {
      registration_count: total,
      registration_completed: completed
    });
    // ★ 最后一个注册也用冷却，避免下次批量任务重复使用
    if (proxyEngine.lastUsedProxy) {
      proxyCooldownAfterSuccess(proxyEngine.lastUsedProxy);
    }
    // ★ 关闭注册标签页（clearAutoRunLease已清空autoRunTabId，用之前保存的lastRegistrationTabId）
    const regTabId = state.lastRegistrationTabId || state.autoRunTabId;
    state.lastRegistrationTabId = null;
    if (regTabId && chrome.tabs && chrome.tabs.remove) {
      chrome.tabs.remove(regTabId, () => { void chrome.runtime.lastError; });
    }
    // ★ 关闭残留的 OAuth 标签页
    const oauthJobs = Object.values(state.oauthJobs || {});
    for (const job of oauthJobs) {
      const oauthTab = Number(job && job.tabId);
      if (Number.isFinite(oauthTab) && oauthTab > 0 && chrome.tabs && chrome.tabs.remove) {
        chrome.tabs.remove(oauthTab, () => { void chrome.runtime.lastError; });
      }
    }
    state.oauthJobs = {};
    // ★ 停止自动执行
    await clearAutoRunLease();
    setStatus("done");
    state.autoRunEnabled = false;
    broadcastState();
    return;
  }
  // ★ 将本次使用的代理置入 5 分钟冷却，确保下次注册用不同代理
  if (proxyEngine.lastUsedProxy) {
    proxyCooldownAfterSuccess(proxyEngine.lastUsedProxy);
  }
  pushDedupeLog("STEP", `注册进度 ${completed}/${total}，正在启动第 ${completed + 1} 个注册`, {
    registration_count: total,
    registration_completed: completed,
    last_completed_email: completedEmail
  });
  broadcastState();
  // 等待短暂间隔后启动下一轮
  await delay(2000);
  // 检查是否还有 OAuth 任务在进行中
  const hasActiveOAuth = Object.values(state.oauthJobs || {}).some(j => j.status === "exchanging" || j.status === "pending");
  if (hasActiveOAuth) {
    pushDedupeLog("STEP", "上一轮 OAuth 令牌交换仍在进行，等待完成后再启动下一轮", {
      registration_completed: completed
    });
    // OAuth 完成后会再次调用 maybeStartNextRegistration
    return;
  }
  // 重新开始注册（生成新账号、打开新页面）
  try {
    const ack = await startAutopilot(null, {
      provider: state.provider,
      isNextRegistration: true
    });
    if (!ack || !ack.ok) {
      pushDedupeLog("BLOCK", `第 ${completed + 1} 个注册启动失败`, {
        reason: ack?.reason || "unknown",
        stage: ack?.stage || "unknown"
      });
    }
  } catch (error) {
    pushDedupeLog("BLOCK", `第 ${completed + 1} 个注册启动异常`, {
      reason: String(error && error.message || error)
    });
  }
  summarizeServices();
  broadcastState();
}

async function startAutopilot(manualAccount = null, options = {}) {
  const controlVersion = state.autoRunControlVersion + 1;
  state.autoRunControlVersion = controlVersion;
  if (!options.autoRetry) {
    state.microsoftProblemAutoRetries = 0;
    state.microsoftProblemRestarting = false;
  }
  // 下一轮注册（非重试）也重置 microsoft problem 状态
  if (options.isNextRegistration) {
    state.microsoftProblemAutoRetries = 0;
    state.microsoftProblemRestarting = false;
  }
  const requestedConfig = providerConfig(options.provider || state.provider);
  setSelectedProvider(requestedConfig.key);

  // ── 代理轮询：每次注册前切换代理 ──
  state.proxyExitIp = "";
  state.proxyExitCountry = "";
  state.proxyActiveStatus = "none";
  if (proxyEngine.enabled && proxyEngine.proxies.length) {
    state.proxyActiveStatus = "checking";
    broadcastState();
    const proxyResult = await rotateProxyForRegistration(requestedConfig.url);
    if (proxyResult.proxy) {
      state.proxyActiveStatus = "active";
      pushLog("OK", `[自动注册] 使用代理 ${urlShort(proxyResult.proxy)}`, { proxy: proxyResult.proxy });
    } else {
      state.proxyActiveStatus = "direct";
      pushLog("WARN", `[自动注册] 无可用代理或已回退直连`, { reason: proxyResult.reason || "no_proxy" });
    }
  } else {
    state.proxyActiveStatus = "none";
  }

  // 总是新开标签页，不复用当前页面
  const tab = await createTab(requestedConfig.url);
  if (!tab || !tab.id) {
    return failAutopilotStart("open_registration_tab_failed", {
      stage: "open_signup",
      provider: requestedConfig.key,
      url: requestedConfig.url
    });
  }
  state.currentUrl = requestedConfig.url;
  setStatus("opening");
  pushLog("STEP", `已打开 ${requestedConfig.label} 注册页`, {
    provider: requestedConfig.key,
    tabId: tab.id,
    url: requestedConfig.url,
    auto_run: true
  });
  broadcastState();
  await waitForTabLoad(tab.id);
  // 等待页面完全加载后再注入验证脚本（MAIN world 需要页面就绪）
  await delay(800);

  // ── 验证代理是否真正生效（含国家检测）──
  if (proxyEngine.currentProxy) {
    const ipResult = await verifyProxyWithGeo(tab.id);
    if (ipResult.ok && ipResult.ip) {
      state.proxyExitIp = ipResult.ip;
      state.proxyExitCountry = ipResult.country || "";
      state.proxyActiveStatus = "active";
      pushLog("OK", `[代理验证] 出口 IP: ${ipResult.ip} | 国家: ${ipResult.country || "未知"} ✅ 代理已生效`, { exitIp: ipResult.ip, country: ipResult.country, proxy: proxyEngine.currentProxy });
    } else {
      state.proxyActiveStatus = "failed";
      pushLog("WARN", `[代理验证] 无法确认出口 IP（${ipResult.error || "未知"}），代理可能未生效！`, { proxy: proxyEngine.currentProxy });
    }
    broadcastState();
  }

  const loadedTab = await getTabById(tab.id) || tab;
  let url = String(loadedTab.url || requestedConfig.url || "");
  const config = requestedConfig;
  if (!(config.hosts || []).some((host) => url.includes(host))) {
    return failAutopilotStart("selected_provider_url_mismatch", {
      stage: "preflight",
      provider: config.key,
      tabId: tab.id,
      url
    });
  }
  setSelectedProvider(config.key);
  resetProviderRuntimeState("start_autopilot");
  const manual = normalizedManualAccount(manualAccount || {});
  if (manual && manual.invalid) {
    pushDedupeLog("BLOCK", "手动账号不完整，不能开始注册", {
      email: manual.email || "",
      has_password: manual.hasPassword
    });
    return failAutopilotStart("manual_account_incomplete", {
      stage: "preflight",
      provider: config.key,
      tabId: tab.id,
      url
    });
  }
  await clearPreviousCredentialArtifacts("start_autopilot");
  const registrationRunId = randomBase64Url(12);
  state.registrationRunId = registrationRunId;
  await storageSet({ [REGISTRATION_RUN_ID_STORAGE_KEY]: registrationRunId });
  const account = {
    ...(manual || generatedOutlookAccount(config.key)),
    clientId: (manual && manual.clientId) || DEFAULT_CLIENT_ID,
    registrationRunId
  };
  if (manual) {
    setActiveAccount(account, "start_autopilot_manual");
  } else {
    backupGeneratedAccount(account, "start_autopilot");
  }
  state.autoRunEnabled = true;
  state.autoRunTabId = tab.id;
  state.autoRunStartedAt = Date.now();
  state.autoRunLastResumeSignature = "";
  state.autoRunLastCommandAt = Date.now();
  rememberStartAck({
    ok: false,
    provider: config.key,
    tabId: tab.id,
    runId: registrationRunId,
    stage: "waiting_for_content_ack",
    reason: "waiting_for_content_ack",
    url
  });
  pushLog("STEP", "正在等待页面 ACK 后启动自动执行", {
    provider: config.key,
    tabId: tab.id,
    runId: registrationRunId,
    url
  });
  await storageSet({
    ninjemailProvider: config.key,
    ninjemailActiveAccount: account,
    ninjemailGeneratedAccount: account,
    [REGISTRATION_RUN_ID_STORAGE_KEY]: registrationRunId,
    [AUTORUN_ENABLED_STORAGE_KEY]: true,
    [AUTORUN_TAB_ID_STORAGE_KEY]: tab.id,
    [AUTORUN_STARTED_AT_STORAGE_KEY]: state.autoRunStartedAt
  });
  const ack = await waitForAutoRunAck(tab, account, controlVersion, START_CONTENT_READY_TIMEOUT_MS);
  if (controlVersion !== state.autoRunControlVersion || !state.autoRunEnabled) {
    return rememberStartAck(startFailureAck("autopilot_stopped_after_content_ack", {
      stage: "stopped",
      provider: config.key,
      tabId: tab.id,
      runId: registrationRunId,
      url
    }));
  }
  if (!ack.ok) {
    return failAutopilotStart(ack.reason || "content_ack_failed", {
      ...ack,
      stage: ack.stage || "content_ack_failed"
    });
  }
  setStatus("observing");
  pushLog("STEP", "已启动注册普通步骤自动执行并收到页面 ACK", {
    provider: config.key,
    tabId: tab.id,
    runId: registrationRunId,
    username: account.username,
    domain: account.domain,
    activeStep: ack.response?.activeStep || "",
    mode: "stop_at_real_challenge"
  });
  broadcastState();
  return rememberStartAck({
    ...ack,
    ok: true,
    stage: "content_ack",
    reason: ack.reason || "content_ack"
  });
}

async function stopAutopilot() {
  const tab = await getActiveTab();
  state.autoRunControlVersion += 1;
  abortBackgroundOperations();
  setStatus("stopped");
  // 用户主动停止，重置注册计数
  state.registrationCount = 0;
  state.registrationCompleted = 0;
  await clearAutoRunLease();
  state.startAck = {
    ok: true,
    ack: "NM_STOP_AUTOPILOT_ACK",
    stage: "stopped",
    reason: "user_stop",
    tabId: tab?.id || null,
    at: nowIso()
  };
  pushLog("OK", "自动执行已停止，后续步骤操作已锁定，点“继续执行”才会恢复");
  if (!tab || !tab.id) {
    broadcastState();
    return;
  }
  await ensureContentScript(tab);
  chrome.tabs.sendMessage(tab.id, { type: "NM_STEP_ACTION", action: "stop_auto" }, () => {
    void chrome.runtime.lastError;
    broadcastState();
  });
}

async function resumeAutopilot() {
  const tab = await getActiveTab();
  if (!tab || !tab.id) {
    pushLog("BLOCK", "没有可继续执行的当前标签页");
    broadcastState();
    return { ok: false, reason: "missing_active_tab" };
  }
  const account = await activeOrLastAccount();
  if (!account || !account.email || !account.password) {
    pushLog("BLOCK", "没有可继续执行的当前账号缓存");
    broadcastState();
    return { ok: false, reason: "missing_active_account" };
  }
  state.autoRunControlVersion += 1;
  state.autoRunEnabled = true;
  state.autoRunTabId = tab.id;
  state.autoRunStartedAt = Date.now();
  state.autoRunLastResumeSignature = "";
  state.autoRunLastCommandAt = Date.now();
  setStatus("observing");
  await storageSet({
    ninjemailActiveAccount: account,
    [AUTORUN_ENABLED_STORAGE_KEY]: true,
    [AUTORUN_TAB_ID_STORAGE_KEY]: tab.id,
    [AUTORUN_STARTED_AT_STORAGE_KEY]: state.autoRunStartedAt
  });
  await ensureContentScript(tab);
  chrome.tabs.sendMessage(tab.id, { type: "NM_STEP_ACTION", action: "auto_run", account }, { frameId: 0 }, () => {
    void chrome.runtime.lastError;
    broadcastState();
  });
  pushLog("STEP", "已继续执行当前注册流程", {
    provider: account.provider || state.provider,
    tabId: tab.id,
    username: account.username || "",
    email: account.email
  });
  broadcastState();
  return { ok: true };
}

async function runManualStep(stepId) {
  const id = String(stepId || "").trim();
  if (state.status === "stopped" && !state.autoRunEnabled) {
    pushLog("BLOCK", "自动执行已停止，步骤操作被锁定；请先点“继续执行”");
    broadcastState();
    return;
  }
  if (!id) {
    pushLog("BLOCK", "未指定要手动执行的步骤");
    broadcastState();
    return;
  }
  if (id === "open_signup") {
    await openSelectedRegistration(state.provider);
    return;
  }
  if (id === "plugin_ready") {
    await scanActiveTab();
    return;
  }
  if (id === "final_state" || id === "export_credentials") {
    await exportCurrentAccountCredentials(`manual_step_${id}`);
    return;
  }
  await sendStepAction("run_step", { stepId: id });
}

function normalizedManualAccount(manualAccount = {}) {
  const email = normalizeEmail(manualAccount.email);
  const password = String(manualAccount.password || "");
  if (!email && !password) return null;
  if (!email || !email.includes("@") || !password) {
    return { invalid: true, email, hasPassword: Boolean(password) };
  }
  const domain = email.split("@")[1] || "";
  const provider = Object.values(PROVIDERS).find((item) => item.domain === domain)?.key
    || (domain.includes("hotmail") ? "hotmail" : (domain.includes("outlook") ? "outlook" : state.provider || "outlook"));
  return {
    provider,
    domain,
    username: email.split("@", 1)[0],
    email,
    password,
    clientId: manualAccount.clientId || manualAccount.client_id || DEFAULT_CLIENT_ID,
    refreshToken: manualAccount.refreshToken || manualAccount.refresh_token || ""
  };
}

function usableCredentialAccount(account = {}) {
  if (!account || typeof account !== "object") return null;
  const email = normalizeEmail(account.email);
  const password = String(account.password || "");
  if (!email || !email.includes("@") || !password) return null;
  return {
    ...account,
    email,
    password,
    provider: account.provider || state.provider || "outlook",
    domain: account.domain || (email.split("@")[1] || ""),
    username: account.username || email.split("@", 1)[0],
    clientId: account.clientId || account.client_id || BUILTIN_CLIENT_ID,
    refreshToken: account.refreshToken || account.refresh_token || ""
  };
}

function candidateAccountList(stored = {}) {
  return [
    stored.ninjemailActiveAccount,
    state.activeAccount,
    stored.ninjemailGeneratedAccount,
    state.lastGeneratedAccount,
    stored.ninjemailLastCreatedAccount,
    state.lastCreatedAccount
  ].map((item) => usableCredentialAccount(item)).filter(Boolean);
}

function pickAccountByEmail(candidates = [], email = "") {
  const wanted = normalizeEmail(email);
  if (wanted) {
    const matched = candidates.find((item) => normalizeEmail(item.email) === wanted);
    if (matched) return matched;
    return null;
  }
  return candidates[0] || null;
}

async function activeOrLastAccount(manualAccount = null) {
  const manual = normalizedManualAccount(manualAccount || {});
  if (manual && !manual.invalid) return manual;
  const stored = await storageGet(["ninjemailActiveAccount", "ninjemailLastCreatedAccount", "ninjemailGeneratedAccount"]);
  const candidates = candidateAccountList(stored);
  if (manual && manual.email) {
    return pickAccountByEmail(candidates, manual.email);
  }
  return candidates[0] || null;
}

async function activeRegistrationAccount() {
  const stored = await storageGet(["ninjemailActiveAccount", "ninjemailGeneratedAccount", "ninjemailLastCreatedAccount"]);
  const candidates = candidateAccountList(stored);
  return candidates[0] || null;
}

function finalStateFromPayload(payload = {}) {
  const finalState = String(payload.finalState || payload.final_state || "").trim();
  if (CREDENTIAL_READY_FINAL_STATES.has(finalState)) return finalState;
  if (String(payload.activeStep || "").trim() === "final_state") {
    const postChallengeState = String(payload.postChallengeState || payload.post_challenge_state || "").trim();
    if (CREDENTIAL_READY_FINAL_STATES.has(postChallengeState)) {
      return postChallengeState;
    }
  }
  return "";
}

async function maybeStartTokenExportFromFinalStatus(sender, payload = {}) {
  const tabId = sender && sender.tab && sender.tab.id;
  if (!payload.isTopFrame || !tabId) return false;
  const finalState = finalStateFromPayload(payload);
  if (!finalState) return false;
  if (state.status === "stopped" && !state.autoRunEnabled) return false;
  if (state.autoRunEnabled && isAutoRunLeaseFresh() && state.autoRunTabId && tabId !== state.autoRunTabId) return false;

  const account = await activeRegistrationAccount();
  if (!account || !account.email || !account.password) {
    pushDedupeLog("BLOCK", "注册已到最终态，但当前账号/密码缓存缺失，未启动刷新令牌获取", {
      final_state: finalState,
      url: payload.url || state.currentUrl || "",
      tabId
    });
    return false;
  }
  if (isCredentialLocked(account.email, false)) return true;
  const resolvedOutputDir = DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR;

  setActiveAccount(account, "final_state_observed");
  setCredentialLock(account.email, {
    status: "token_pending",
    finalState,
    stage: "final_state_observed"
  });
  state.credentialStatus = {
    status: "waiting_page_stable",
    email: account.email,
    delay_ms: 2500,
    output_dir: resolvedOutputDir
  };
  setStatus("observing");
  await clearAutoRunLease();
  broadcastState();
  pushDedupeLog("ACCOUNT", accountLogMessage("注册最终态已确认，准备自动获取四凭证", account), accountLogDetails(account, {
    final_state: finalState,
    url: payload.url || state.currentUrl || "",
    output_dir: resolvedOutputDir,
    stage: "final_state_observed"
  }));

  setTimeout(() => {
    startOAuthTokenExport(account, {
      finalState,
      url: payload.url || state.currentUrl || "",
      title: payload.title || state.title || "",
      outputDir: resolvedOutputDir,
      windowId: sender?.tab?.windowId || 0,
      force: true
    }).then((result) => {
      summarizeServices();
      broadcastState();
      if (result.ok) {
        pushDedupeLog("STEP", "已启动刷新令牌获取流程", {
          email: account.email,
          output_dir: resolvedOutputDir,
          final_state: finalState,
          oauth_tab: result.tabId || ""
        });
      } else {
        pushDedupeLog("BLOCK", "刷新令牌获取流程启动失败", {
          email: account.email,
          reason: result.reason || "unknown"
        });
      }
    }).catch((error) => {
      const reason = String(error && error.message || error);
      setCredentialLock(account.email, { status: "failed", finalState, reason });
      state.credentialStatus = {
        status: "save_failed",
        email: account.email,
        reason,
        output_dir: state.credentialOutputDir || "<browser_downloads>"
      };
      summarizeServices();
      broadcastState();
      pushDedupeLog("BLOCK", "刷新令牌获取流程启动异常", {
        email: account.email,
        reason
      });
    });
  }, 2500);

  return true;
}

async function exportCurrentAccountCredentials(reason = "manual_export", manualAccount = null, outputDirOverride = DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR) {
  const requestedOutputDir = String(outputDirOverride || DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR).trim() || DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR;
  pushDedupeLog("STEP", "正在获取四凭证", {
    reason,
    output_dir: requestedOutputDir || "<browser_downloads>"
  });
  state.credentialStatus = {
    status: "running",
    email: "",
    output_dir: requestedOutputDir || "<browser_downloads>"
  };
  summarizeServices();
  broadcastState();
  const manual = normalizedManualAccount(manualAccount || {});
  const account = await activeOrLastAccount(manualAccount);
  if (manual && manual.invalid && !account) {
      state.credentialStatus = {
        status: "save_failed",
        reason: "manual_account_incomplete",
        email: manual.email || "",
        output_dir: requestedOutputDir || "<browser_downloads>"
      };
    pushDedupeLog("BLOCK", "手动账号不完整，无法获取四凭证", {
      email: manual.email || "",
      has_password: manual.hasPassword
    });
    summarizeServices();
    broadcastState();
    return { ok: false, reason: "manual_account_incomplete" };
  }
  if (manual && manual.invalid && account) {
    pushDedupeLog("STEP", "手动输入不完整，已按当前缓存账号获取四凭证", {
      requested_email: manual.email || "",
      resolved_email: account.email,
      has_password: Boolean(account.password)
    });
  }
  if (!account || !account.email || !account.password) {
    pushLog("STEP", "本地没有账号缓存，已请求当前页面提交注册成功账号", { reason });
    const sent = await sendStepAction("run_step", { stepId: "export_credentials" });
    if (!sent.ok) {
      state.credentialStatus = {
        status: "save_failed",
        reason: `missing_cached_account; ${sent.reason || "current_page_unavailable"}`,
        email: "",
        output_dir: requestedOutputDir || "<browser_downloads>"
      };
      pushDedupeLog("BLOCK", "获取四凭证失败：没有账号缓存，且当前页面无法提交账号", {
        reason: sent.reason || "current_page_unavailable",
        url: sent.url || state.currentUrl || ""
      });
      summarizeServices();
      broadcastState();
      return { ok: false, reason: "missing_cached_account_and_page_unavailable", detail: sent.reason || "" };
    }
    state.credentialStatus = {
      status: "waiting_page_account",
      email: "",
      output_dir: requestedOutputDir || "<browser_downloads>"
    };
    broadcastState();
    return { ok: true, reason: "requested_content_export_credentials" };
  }
  const tab = await getActiveTab();
  pushDedupeLog("ACCOUNT", accountLogMessage("准备获取四凭证", account), accountLogDetails(account, {
    reason,
    output_dir: requestedOutputDir || "<browser_downloads>",
    stage: "export_credentials_target"
  }));
  const refreshToken = String(account.refreshToken || account.refresh_token || "").trim();
  const baseRecord = {
    ...account,
    finalState: "manual_export",
    url: tab?.url || state.currentUrl || "",
    title: tab?.title || state.title || "",
    output_dir: requestedOutputDir,
    stableDelayMs: 0,
    reason
  };
  if (isAbsoluteFilesystemPath(baseRecord.output_dir) && !outputDirSupportsBrowserDownload(baseRecord.output_dir)) {
    const localWriterReady = await checkLocalWriterAvailability();
    if (!localWriterReady) {
      state.credentialStatus = {
        status: "save_failed",
        email: account.email,
        reason: "local_writer_unreachable_for_absolute_output_dir",
        output_dir: baseRecord.output_dir || "<browser_downloads>"
      };
      pushDedupeLog("BLOCK", "绝对路径导出需要本地写盘服务，但当前本地写盘 API 不可用", {
        email: account.email,
        output_dir: baseRecord.output_dir || "<browser_downloads>",
        web_ui_base_url: effectiveWebUiBaseUrl()
      });
      summarizeServices();
      broadcastState();
      return { ok: false, reason: "local_writer_unreachable_for_absolute_output_dir" };
    }
  }
  let result;
  if (!refreshToken) {
    const recovered = await checkSavedCredentialViaWebUi(baseRecord);
    if (recovered.ok) {
      result = await persistRecoveredCredentialRecord(baseRecord, recovered.data, "manual_export_recovered_saved_credential");
      if (result.ok) {
        setStatus("done");
        pushDedupeLog("OK", "检测到已保存的四凭证，直接恢复并完成导出", {
          email: account.email,
          output_dir: state.credentialOutputDir || "<browser_downloads>",
          credential_path: result.record?.credentialPath || result.record?.comboPath || ""
        });
        summarizeServices();
        broadcastState();
        return { ok: true, reason: "recovered_saved_credential", record: result.record, webUi: { ok: true, data: recovered.data } };
      }
    }
    result = await startOAuthTokenExport(baseRecord, {
      finalState: "manual_export",
      url: baseRecord.url,
      title: baseRecord.title,
      outputDir: baseRecord.output_dir,
      windowId: tab?.windowId || 0,
      force: true
    });
    if (result.ok) {
      setStatus("observing");
      pushDedupeLog("STEP", "已启动刷新令牌获取流程", {
        email: account.email,
        output_dir: state.credentialOutputDir || "<browser_downloads>",
        reason
      });
    } else {
      pushDedupeLog("BLOCK", "刷新令牌获取流程启动失败", { reason: result.reason || "unknown" });
    }
  } else {
    result = await rememberCreatedAccount({
      account: baseRecord,
      refreshToken,
      finalState: "manual_export",
      url: baseRecord.url,
      title: baseRecord.title,
      output_dir: state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
      stableDelayMs: 0,
      force: true,
      reason
    });
    if (result.ok) {
      setStatus("done");
      pushDedupeLog("OK", "四凭证保存/补齐任务已启动", {
        email: account.email,
        output_dir: state.credentialOutputDir || "<browser_downloads>",
        web_ui_saved: Boolean(result.webUi && result.webUi.ok),
        token_job: result.webUi?.data?.token_job?.status || "unknown",
        credential_path: result.record?.credentialPath || result.record?.comboPath || result.webUi?.data?.credential_path || result.webUi?.data?.combo_path || ""
      });
    } else {
      pushDedupeLog("BLOCK", "四凭证保存/补齐任务启动失败", { reason: result.reason || "unknown" });
    }
  }
  summarizeServices();
  broadcastState();
  return result;
}

async function exportCurrentAccountThreeCredentials(reason = "manual_export_three", manualAccount = null) {
  pushDedupeLog("STEP", "正在导出三凭证", {
    reason,
    output_dir: state.credentialOutputDir || "<browser_downloads>"
  });
  const manual = normalizedManualAccount(manualAccount || {});
  const account = await activeOrLastAccount(manualAccount);
  if (manual && manual.invalid && !account) {
    state.credentialStatus = {
      status: "save_failed",
      reason: "manual_account_incomplete",
      email: manual.email || "",
      output_dir: DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR
    };
    summarizeServices();
    broadcastState();
    return { ok: false, reason: "manual_account_incomplete" };
  }
  if (!account || !account.email || !account.password) {
    const sent = await sendStepAction("run_step", { stepId: "export_credentials" });
    if (!sent.ok) {
      state.credentialStatus = {
        status: "save_failed",
        reason: `missing_cached_account; ${sent.reason || "current_page_unavailable"}`,
        email: "",
        output_dir: state.credentialOutputDir || "<browser_downloads>"
      };
      summarizeServices();
      broadcastState();
      return { ok: false, reason: "missing_cached_account_and_page_unavailable", detail: sent.reason || "" };
    }
    state.credentialStatus = {
      status: "waiting_page_account",
      email: "",
      output_dir: state.credentialOutputDir || "<browser_downloads>"
    };
    broadcastState();
    return { ok: true, reason: "requested_content_export_credentials" };
  }
  const tab = await getActiveTab();
  const record = {
    ...account,
    clientId: account.clientId || account.client_id || BUILTIN_CLIENT_ID,
    outputDir: state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR,
    url: tab?.url || state.currentUrl || "",
    title: tab?.title || state.title || ""
  };
  if (isAbsoluteFilesystemPath(record.outputDir) && !outputDirSupportsBrowserDownload(record.outputDir)) {
    const localWriterReady = await checkLocalWriterAvailability();
    if (!localWriterReady) {
      state.credentialStatus = {
        status: "save_failed",
        email: record.email,
        reason: "local_writer_unreachable_for_absolute_output_dir",
        output_dir: record.outputDir || "<browser_downloads>"
      };
      summarizeServices();
      broadcastState();
      return { ok: false, reason: "local_writer_unreachable_for_absolute_output_dir" };
    }
  }
  let download = { ok: false, reason: "not_needed" };
  const preferBrowserDownload = outputDirSupportsBrowserDownload(record.outputDir);
  if (preferBrowserDownload) {
    download = await downloadThreeCredentialFile(record);
  }
  let webUi = { ok: false, reason: "web_ui_not_requested", data: {} };
  if (!download.ok && isAbsoluteFilesystemPath(record.outputDir)) {
    webUi = await postThreeCredentialsToWebUi(record);
  }
  const savedPath = (webUi?.ok && threeCredentialPathMatchesEmail(record.email, webUi?.data?.credential_path || ""))
    ? String(webUi.data.credential_path || "")
    : (download.ok ? String(download.finalFilename || download.filename || threeCredentialDownloadFilenameFor(record)) : "");
  if (!(webUi?.ok || download.ok)) {
    const reason = webUi?.data?.reason || webUi?.reason || download?.reason || "three_credential_save_failed";
    state.credentialStatus = {
      status: "save_failed",
      email: record.email,
      reason,
      output_dir: record.outputDir || "<browser_downloads>"
    };
    summarizeServices();
    broadcastState();
    return { ok: false, reason };
  }
  state.credentialStatus = {
    ...state.credentialStatus,
    status: "three_credentials_saved",
    email: record.email,
    three_credential_path: savedPath,
    output_dir: record.outputDir || "<browser_downloads>",
    reason: ""
  };
  pushDedupeLog("OK", "三凭证已导出", {
    email: record.email,
    client_id: record.clientId,
    three_credential_path: savedPath,
    output_dir: record.outputDir || "<browser_downloads>"
  });
  summarizeServices();
  broadcastState();
  return { ok: true, record, webUi, download, threeCredentialPath: savedPath };
}

if (chrome.runtime && chrome.runtime.onInstalled) chrome.runtime.onInstalled.addListener(() => {
  setStatus("idle");
  clearAutoRunLease().finally(() => {});
  pushLog("OK", `Ninjemail 浏览器插件已安装/重载 | build=${BACKGROUND_BUILD}`);
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  }
});

if (chrome.runtime.onStartup) {
  chrome.runtime.onStartup.addListener(() => {
    clearAutoRunLease().finally(() => {});
  });
}

if (chrome.action && chrome.action.onClicked) chrome.action.onClicked.addListener((tab) => {
  if (chrome.sidePanel && chrome.sidePanel.open && tab && tab.windowId) {
    chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});
  }
});

if (chrome.tabs && chrome.tabs.onUpdated) chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const url = changeInfo.url || tab?.url || "";
  if (!url) return;
  handleOAuthRedirect(tabId, url).catch((error) => {
    pushDedupeLog("BLOCK", "OAuth 回调处理失败", {
      reason: String(error && error.message || error)
    });
  });
});

const stateReady = hydrateStoredState().then(() => {
  summarizeServices();
  // ★ 启动时自动加载代理列表到轮询引擎，加载完再发状态
  return loadProxyEngine().then(() => {
    refreshProxyActiveStatus();
    broadcastState();
  }).catch(() => {
    broadcastState();
  });
}).catch(() => {});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const type = message && message.type;
  if (type === "NM_GET_STATE") {
    stateReady.finally(() => {
      summarizeServices();
      const s = cloneState();
      console.log("[NM_GET_STATE] proxyEngine:", JSON.stringify(s.proxyEngine));
      sendResponse(s);
    });
    return true;
  }

  if (type === "NM_REFRESH_SMS_DIAGNOSTICS") {
    refreshSmsDiagnostics(message.reason || message.payload?.reason || "sidepanel_refresh").finally(() => {
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_SMS_LOAD_NUMBERS") {
    loadSmsNumbers(message.payload || message).finally(() => {
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_SMS_SELECT_NUMBER") {
    selectSmsNumber(message.payload || message);
    summarizeServices();
    broadcastState();
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_SMS_REFRESH_MESSAGES") {
    refreshSmsMessages(message.payload || message).finally(() => {
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_SET_PROVIDER") {
    setSelectedProvider(message.provider || message.payload?.provider || state.provider);
    summarizeServices();
    broadcastState();
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_SET_CREDENTIAL_OUTPUT_DIR") {
    const outputDir = String(message.outputDir || message.payload?.outputDir || "").trim();
    state.credentialOutputDir = outputDir;
    chrome.storage.local.set({ [CREDENTIAL_OUTPUT_DIR_STORAGE_KEY]: outputDir }, () => {
      pushDedupeLog("OK", "四凭证保存路径已更新", {
        output_dir: outputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
      });
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_SET_WEB_UI_BASE_URL") {
    const webUiBaseUrl = String(message.webUiBaseUrl || message.payload?.webUiBaseUrl || "").trim();
    state.webUiBaseUrl = webUiBaseUrl;
    state.webUiHealth = {
      ...state.webUiHealth,
      status: "unknown",
      ok: false,
      reason: "",
      checkedAt: "",
      url: webUiBaseUrl || WEB_UI_BASE_URL
    };
    chrome.storage.local.set({ [WEB_UI_BASE_URL_STORAGE_KEY]: webUiBaseUrl }, () => {
      pushDedupeLog("OK", "本地写盘 API 地址已更新", {
        web_ui_base_url: webUiBaseUrl || WEB_UI_BASE_URL
      });
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_CHECK_WEB_UI_HEALTH") {
    probeWebUiHealth().then((health) => {
      state.webUiHealth = health;
      pushDedupeLog(health.ok ? "OK" : "BLOCK", health.ok ? "本地写盘后台可用" : "本地写盘后台不可用", {
        web_ui_base_url: health.url,
        reason: health.reason || ""
      });
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_CLEAR_LOGS") {
    state.logs = [];
    state.lastSignature = "";
    pushLog("OK", "日志已清空");
    summarizeServices();
    broadcastState();
    sendResponse(cloneState());
    return false;
  }

  // ── 代理管理 ──

  if (type === "NM_PROXY_TOGGLE") {
    const enabled = !!message.enabled;
    proxyEngine.enabled = enabled;
    pushLog("STEP", `[代理] 轮询引擎${enabled ? "已启用" : "已禁用"} (${proxyEngine.proxies.length} 个代理)`);
    if (!enabled) {
      // 禁用时保存健康状态并清除代理
      saveProxyHealth();
      clearProxy().then(() => {
        proxyEngine.currentProxy = null;
        refreshProxyActiveStatus();
        broadcastState();
        sendResponse(cloneState());
      });
    } else {
      loadProxyEngine().then(() => {
        refreshProxyActiveStatus();
        broadcastState();
        sendResponse(cloneState());
      });
    }
    return true;
  }

  if (type === "NM_PROXY_LOAD") {
    // 从 chrome.storage.local 加载代理（插件内部持久化，不依赖后端）
    (async () => {
      try {
        const result = await chrome.storage.local.get("savedProxyText");
        const content = (result.savedProxyText || "").trim();
        // ★ 加载时也做标准化（兼容旧格式数据）
        const rawLines = content ? content.split(/[\r\n]+/) : [];
        const normalizedLines = [];
        const seen = new Set();
        for (const raw of rawLines) {
          const r = normalizeProxyLine(raw);
          if (r && !seen.has(r.normalized)) {
            seen.add(r.normalized);
            normalizedLines.push(r.normalized);
          }
        }
        const normalizedText = normalizedLines.join("\n");
        // 如果标准化后与原始不同，回写标准化版本
        if (normalizedText !== content && normalizedLines.length > 0) {
          await chrome.storage.local.set({ savedProxyText: normalizedText });
          pushLog("OK", `[代理] 加载时标准化：${rawLines.length}行 → ${normalizedLines.length}个有效代理（已回写）`);
        }
        // ★ 同步内存中的 proxyEngine 状态
        if (normalizedLines.length > 0) {
          proxyEngine.proxies = normalizedLines;
          proxyEngine.enabled = true;
        }
        refreshProxyActiveStatus();
        const payload = {
          ok: normalizedLines.length > 0,
          count: normalizedLines.length,
          all_count: normalizedLines.length,
          stable_count: normalizedLines.length,
          proxy_text: normalizedText,
          proxies: normalizedLines,
          auto_proxy: normalizedLines.length > 0,
        };
        pushLog(payload.ok ? "OK" : "BLOCK", payload.ok
          ? `已加载 ${payload.count} 个代理`
          : "无已保存的代理");
        chrome.runtime.sendMessage({ type: "NM_PROXY_LOAD_RESULT", payload }).catch(() => {});
      } catch (err) {
        pushLog("BLOCK", `加载代理异常: ${err.message || err}`);
        chrome.runtime.sendMessage({ type: "NM_PROXY_LOAD_RESULT", payload: { ok: false, reason: String(err.message || err) } }).catch(() => {});
      }
      broadcastState();
      sendResponse(cloneState());
    })();
    return true;
  }

  if (type === "NM_PROXY_SAVE") {
    const proxyText = String(message.proxyText || message.payload?.proxyText || "").trim();
    if (!proxyText) {
      sendResponse({ ok: false, reason: "proxy_text_empty" });
      return false;
    }
    (async () => {
      // ★ 智能解析 + 标准化每条代理
      const rawLines = proxyText.split(/[\r\n]+/); // 兼容 \r\n 和 \n
      const normalized = []; // 标准化后的代理列表
      const normalizedTexts = []; // 标准化后的文本行
      let invalidCount = 0;
      let authCount = 0;
      const invalidSamples = [];

      for (const raw of rawLines) {
        const result = normalizeProxyLine(raw);
        if (result) {
          // 去重
          if (!normalized.includes(result.normalized)) {
            normalized.push(result.normalized);
            normalizedTexts.push(result.normalized);
            if (result.username) authCount++;
          }
        } else if (raw.trim()) {
          invalidCount++;
          if (invalidSamples.length < 3) invalidSamples.push(raw.trim().substring(0, 60));
        }
      }

      if (!normalized.length) {
        const payload = { ok: false, reason: `无有效代理地址（${rawLines.length} 行全部无法解析）` };
        chrome.runtime.sendMessage({ type: "NM_PROXY_SAVE_RESULT", payload }).catch(() => {});
        sendResponse({ ok: false, reason: payload.reason });
        return;
      }

      const normalizedText = normalizedTexts.join("\n");
      pushLog("STEP", `[代理] 导入 ${normalized.length} 个代理（标准化完成，无效${invalidCount}行，含认证${authCount}个）`);
      if (invalidSamples.length) {
        pushLog("WARN", `[代理] 无效行示例: ${invalidSamples.join(" | ")}`);
      }

      try {
        // 保存标准化后的文本到 chrome.storage.local
        await chrome.storage.local.set({ savedProxyText: normalizedText });

        // ★ 增量合并：保留现有代理的健康/冷却状态，追加新代理
        const existingSet = new Set(proxyEngine.proxies);
        const newProxies = normalized.filter(l => !existingSet.has(l));
        const removedProxies = proxyEngine.proxies.filter(p => !normalized.includes(p));

        if (newProxies.length === 0 && removedProxies.length === 0) {
          pushLog("OK", `[代理] ${normalized.length} 个代理无变化，保持当前轮询位置`);
        } else {
          const kept = proxyEngine.proxies.filter(p => normalized.includes(p));
          proxyEngine.proxies = [...kept, ...newProxies];

          for (const removed of removedProxies) {
            delete proxyEngine.health[removed];
            // 清理凭据
            try {
              const u = new URL(removed);
              proxyCredentials.delete(`${u.hostname}:${u.port}`);
            } catch (_) {}
          }

          if (proxyEngine.index >= proxyEngine.proxies.length) {
            proxyEngine.index = 0;
          }

          pushLog("OK", `[代理] 合并完成：保留${kept.length}个 + 新增${newProxies.length}个 - 移除${removedProxies.length}个 = ${proxyEngine.proxies.length}个`);
        }

        proxyEngine.enabled = proxyEngine.proxies.length > 0;
        startHealthSaveTimer();
        refreshProxyActiveStatus();

        // 构建结果消息
        const parts = [];
        if (newProxies.length || removedProxies.length) {
          parts.push(`+${newProxies.length}新增 -${removedProxies.length}移除`);
        }
        parts.push(`共${proxyEngine.proxies.length}个`);
        if (authCount) parts.push(`认证${authCount}个`);
        if (invalidCount) parts.push(`⚠️无效${invalidCount}行`);

        const payload = {
          ok: true,
          count: proxyEngine.proxies.length,
          added: newProxies.length,
          removed: removedProxies.length,
          invalid: invalidCount,
          authCount,
          proxy_text: normalizedText,
          proxies: proxyEngine.proxies,
          reason: `✅ ${parts.join("，")}`,
        };

        chrome.runtime.sendMessage({ type: "NM_PROXY_SAVE_RESULT", payload }).catch(() => {});
      } catch (err) {
        pushLog("BLOCK", `保存代理异常: ${err.message || err}`);
        chrome.runtime.sendMessage({ type: "NM_PROXY_SAVE_RESULT", payload: { ok: false, reason: String(err.message || err) } }).catch(() => {});
      }
      broadcastState();
      sendResponse(cloneState());
    })();
    return true;
  }

  if (type === "NM_PROXY_CHECK") {
    const proxyText = String(message.proxyText || message.payload?.proxyText || "").trim();
    if (!proxyText) {
      sendResponse({ ok: false, reason: "proxy_text_empty" });
      return false;
    }
    (async () => {
      const allLines = proxyText.split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#") && l.includes(":"));
      const reqLimit = parseInt(message.checkLimit || message.payload?.checkLimit, 10);
      const CHECK_LIMIT = Number.isFinite(reqLimit) && reqLimit >= 1 ? Math.min(reqLimit, 500) : 20;
      const toCheck = allLines.slice(0, CHECK_LIMIT);
      const skipped = allLines.length - toCheck.length;

      pushLog("STEP", `[代理] 并发检测 ${toCheck.length} 个代理` + (skipped > 0 ? `（跳过 ${skipped} 个）` : ""));

      // ── PAC 轮询并发检测 ──
      // 所有代理排进 PAC 脚本，每次请求自动轮换到下一个
      // 同时发 10 个 fetch → 每个走不同代理 → 约 3 秒完成一轮
      const CONCURRENT = 10;
      const ROUNDS = Math.ceil(toCheck.length / CONCURRENT);
      const TEST_URL = "http://icanhazip.com";

      // 构建 PAC 轮询脚本（★ PAC 指令必须大写）
      const pacEntries = [];
      for (const url of toCheck) {
        try {
          const u = new URL(url);
          let directive;
          if (u.protocol === "socks5:") directive = "SOCKS5";
          else if (u.protocol === "socks4:") directive = "SOCKS";
          else directive = "PROXY";
          pacEntries.push(`${directive} ${u.hostname}:${u.port}`);
        } catch (_) {}
      }

      if (!pacEntries.length) {
        chrome.runtime.sendMessage({ type: "NM_PROXY_CHECK_RESULT", payload: { ok: false, reason: "无有效代理地址" } }).catch(() => {});
        broadcastState();
        sendResponse(cloneState());
        return;
      }

      // PAC 脚本：轮询代理列表
      const proxyArrStr = '"' + pacEntries.join('","') + '"';
      const pacScript = "var _px=[" + proxyArrStr + "];var _pi=0;function FindProxyForURL(u,h){if(u.indexOf('http')!==0)return 'DIRECT';var p=_px[_pi%_px.length];_pi++;return p;}";

      let pacOk = false;
      try {
        await new Promise((resolve, reject) => {
          chrome.proxy.settings.set({ value: { mode: "pac_script", pacScript } }, () => {
            if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
            else resolve();
          });
        });
        pacOk = true;
      } catch (e) {
        pushLog("WARN", `[代理] PAC 设置失败: ${e.message}，回退串行检测`);
      }

      let successRate = 0;
      let totalOk = 0;

      if (pacOk) {
        // PAC 模式并发检测
        await new Promise(r => setTimeout(r, 200));

        for (let round = 0; round < ROUNDS; round++) {
          const batchSize = Math.min(CONCURRENT, toCheck.length - round * CONCURRENT);
          const fetches = [];
          for (let j = 0; j < batchSize; j++) {
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), 4000);
            fetches.push(
              fetch(TEST_URL + "?_r=" + round + "_" + j, { cache: "no-store", signal: ctrl.signal })
                .then(r => { clearTimeout(timer); return r.ok ? 1 : 0; })
                .catch(() => { clearTimeout(timer); return 0; })
            );
          }
          const results = await Promise.all(fetches);
          const roundOk = results.reduce((a, b) => a + b, 0);
          totalOk += roundOk;

          pushLog("STEP", `[代理] 轮次 ${round + 1}/${ROUNDS}: ${roundOk}/${batchSize} 成功`);
          chrome.runtime.sendMessage({
            type: "NM_PROXY_CHECK_PROGRESS",
            payload: { completed: (round + 1) * CONCURRENT, total: toCheck.length, working: totalOk, failed: (round + 1) * CONCURRENT - totalOk, current: `轮次 ${round + 1}/${ROUNDS}` }
          }).catch(() => {});
        }

        await clearProxy();
        successRate = totalOk / toCheck.length;
        pushLog("OK", `[代理] 并发检测完成: ${totalOk}/${toCheck.length} 成功 (${Math.round(successRate * 100)}%)`);
      }

      // ── 精确验证（标签页方式） ──
      // PAC 并发通过率高 → 只精确验证前 10 个确认可用性
      // PAC 并发通过率低或 PAC 失败 → 精确验证全部
      const working = [];
      const failed = [];
      let verifyLimit;
      if (!pacOk) {
        verifyLimit = toCheck.length; // PAC 失败，全部串行验证
      } else if (successRate >= 0.5) {
        verifyLimit = Math.min(10, toCheck.length); // 通过率高，只验证 10 个
      } else {
        verifyLimit = Math.min(30, toCheck.length); // 通过率低，验证 30 个
      }

      pushLog("STEP", `[代理] 精确验证 ${verifyLimit} 个代理（标签页方式）...`);

      for (let i = 0; i < verifyLimit; i++) {
        const url = toCheck[i];
        let isFailed = false;
        try {
          const result = await quickCheckProxy(url);
          if (result.ok) {
            working.push(url);
            proxyMarkOk(url, result.latencyMs);
          } else {
            failed.push(url);
            isFailed = true;
          }
        } catch (_) {
          failed.push(url);
          isFailed = true;
        }
        // 实时进度：带可用代理列表 + 失败代理 URL
        chrome.runtime.sendMessage({
          type: "NM_PROXY_CHECK_PROGRESS",
          payload: { completed: i + 1, total: verifyLimit, working: working.length, failed: failed.length, current: urlShort(url), failedUrl: isFailed ? url : null, workingProxies: working.slice() }
        }).catch(() => {});
      }

      await clearProxy();

      // 未精确验证的代理：PAC 通过率 ≥50% 则保留（仅从已检测的前100个中）
      const unverified = toCheck.slice(verifyLimit);
      if (pacOk && successRate >= 0.5) {
        working.push(...unverified);
        for (const url of unverified) proxyMarkOk(url, 0);
      }

      // ★ 修复：不再把超过 CHECK_LIMIT 未检测的代理加入可用列表
      // 只有经过检测（精确验证或 PAC 高通过率保留）的才算可用
      const finalWorking = working.slice();

      // ★ 修复：结果文本准确反映检测范围
      const totalChecked = toCheck.length;
      const totalAll = allLines.length;
      const payload = {
        ok: finalWorking.length > 0,
        count: finalWorking.length,
        total: totalChecked,
        total_all: totalAll,
        skipped,
        failed_count: failed.length,
        proxy_text: finalWorking.join("\n"),
        proxies: finalWorking,
        reason: finalWorking.length > 0
          ? `✅ ${working.length}/${totalChecked} 个代理可用（${failed.length} 个已剔除${skipped > 0 ? `，${skipped} 个未检测已丢弃` : ''}）${!pacOk ? '（串行模式）' : ''}`
          : `❌ ${totalChecked} 个代理全部不可用`,
      };

      pushLog(payload.ok ? "OK" : "BLOCK", payload.reason);
      chrome.runtime.sendMessage({ type: "NM_PROXY_CHECK_RESULT", payload }).catch(() => {});
      refreshProxyActiveStatus();
      broadcastState();
      sendResponse(cloneState());
    })();
    return true;
  }

  if (type === "NM_PROXY_REMOVE") {
    const url = String(message.url || message.payload?.url || "").trim();
    if (url) {
      proxyEngine.proxies = proxyEngine.proxies.filter(p => p !== url);
      delete proxyEngine.health[url];
      pushLog("OK", `[代理] 已移除 ${urlShort(url)}（剩余 ${proxyEngine.proxies.length} 个）`);
      saveProxyHealth();
      broadcastState();
    }
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_OPEN_WEB_UI") {
    chrome.tabs.create({ url: webUiApiUrl() });
    pushLog("STEP", "已打开 Ninjemail Web UI");
    broadcastState();
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_OPEN_CREDENTIAL_OUTPUT_DIR") {
    openCredentialOutputDir(message.payload || message || {})
      .then((result) => sendResponse({ ...cloneState(), openCredentialDir: result }))
      .catch((error) => sendResponse({ ...cloneState(), openCredentialDir: { ok: false, reason: String(error && error.message || error) } }));
    return true;
  }

  if (type === "NM_RECOVER_LOGIN_FLOW") {
    sendStepAction("click_continue")
      .then(async (result) => {
        await scanActiveTab();
        sendResponse({ ...cloneState(), recoverLogin: result });
      })
      .catch((error) => sendResponse({ ...cloneState(), recoverLogin: { ok: false, reason: String(error && error.message || error) } }));
    return true;
  }

  if (type === "NM_OPEN_REGISTER") {
    openSelectedRegistration(message.provider || message.payload?.provider || state.provider);
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_RUN_MANUAL_STEP") {
    runManualStep(message.stepId || message.payload?.stepId || "").then(() => {
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_EXPORT_CREDENTIALS") {
    const requestedOutputDir = String(message.outputDir || message.payload?.outputDir || "").trim();
    if (requestedOutputDir) {
      state.credentialOutputDir = requestedOutputDir;
      chrome.storage.local.set({ [CREDENTIAL_OUTPUT_DIR_STORAGE_KEY]: requestedOutputDir });
    }
    pushLog("STEP", "收到获取四凭证按钮请求", {
      reason: message.reason || message.payload?.reason || "manual_button",
      output_dir: state.credentialOutputDir || "<browser_downloads>"
    });
    exportCurrentAccountCredentials(
      message.reason || message.payload?.reason || "manual_button",
      message.manualAccount || message.payload?.manualAccount || null,
      DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR
    ).then((result) => {
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  /*
  if (type === "NM_EXPORT_CREDENTIALS_TO_DIR") {
    const requestedOutputDir = String(message.outputDir || message.payload?.outputDir || "").trim();
    if (requestedOutputDir) {
      state.credentialOutputDir = requestedOutputDir;
      chrome.storage.local.set({ [CREDENTIAL_OUTPUT_DIR_STORAGE_KEY]: requestedOutputDir });
    }
    pushLog("STEP", "鏀跺埌瀵煎嚭鍥涘嚟璇佹寜閽姹?, {
      reason: message.reason || message.payload?.reason || "manual_export_button",
      output_dir: requestedOutputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    });
    exportCurrentAccountCredentials(
      message.reason || message.payload?.reason || "manual_export_button",
      message.manualAccount || message.payload?.manualAccount || null,
      requestedOutputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    ).then(() => {
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }
  */

  if (type === "NM_EXPORT_CREDENTIALS_TO_DIR") {
    const requestedOutputDir = String(message.outputDir || message.payload?.outputDir || "").trim();
    if (requestedOutputDir) {
      state.credentialOutputDir = requestedOutputDir;
      chrome.storage.local.set({ [CREDENTIAL_OUTPUT_DIR_STORAGE_KEY]: requestedOutputDir });
    }
    pushLog("STEP", "Received export-four-credentials request", {
      reason: message.reason || message.payload?.reason || "manual_export_button",
      output_dir: requestedOutputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    });
    exportCurrentAccountCredentials(
      message.reason || message.payload?.reason || "manual_export_button",
      message.manualAccount || message.payload?.manualAccount || null,
      requestedOutputDir || state.credentialOutputDir || DEFAULT_CREDENTIAL_OUTPUT_DIR
    ).then(() => {
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_EXPORT_THREE_CREDENTIALS") {
    const requestedOutputDir = String(message.outputDir || message.payload?.outputDir || "").trim();
    if (requestedOutputDir) {
      state.credentialOutputDir = requestedOutputDir;
      chrome.storage.local.set({ [CREDENTIAL_OUTPUT_DIR_STORAGE_KEY]: requestedOutputDir });
    }
    pushLog("STEP", "收到导出三凭证按钮请求", {
      reason: message.reason || message.payload?.reason || "manual_button",
      output_dir: state.credentialOutputDir || "<browser_downloads>"
    });
    exportCurrentAccountThreeCredentials(
      message.reason || message.payload?.reason || "manual_three_button",
      message.manualAccount || message.payload?.manualAccount || null
    ).then(() => {
      summarizeServices();
      broadcastState();
      sendResponse(cloneState());
    });
    return true;
  }

  if (type === "NM_VALIDATE_CREDENTIALS") {
    validateCredentialFiles(message.payload || message || {})
      .then((result) => sendResponse({ ...cloneState(), credentialValidation: result }))
      .catch((error) => {
        const reason = String(error && error.message || error);
        pushDedupeLog("BLOCK", "邮箱凭证校验失败", { reason });
        sendResponse({ ...cloneState(), credentialValidation: { status: "failed", reason } });
      });
    return true;
  }

  if (type === "NM_AUXILIARY_MAILBOX_PICK") {
    pickAuxiliaryMailbox(message.payload || message || {})
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ ok: false, reason: String(error && error.message || error) }));
    return true;
  }

  if (type === "NM_AUXILIARY_MAILBOX_CODE") {
    pollAuxiliaryMailboxCode(message.payload || message || {})
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ ok: false, reason: String(error && error.message || error) }));
    return true;
  }

  if (type === "NM_GENERATED_ACCOUNT") {
    const payload = message.payload || message;
    const incoming = payload.account || {};
    const incomingEmail = normalizeEmail(incoming.email);
    const activeEmail = normalizeEmail(state.activeAccount && state.activeAccount.email);
    if (activeEmail && incomingEmail && incomingEmail !== activeEmail) {
      pushDedupeLog("STEP", "已忽略 content 端候选账号，继续使用后台锁定的当前账号", {
        active_email: activeEmail,
        ignored_email: incomingEmail,
        reason: payload.reason || "content_generated_account"
      });
    } else {
      backupGeneratedAccount(incoming, payload.reason || "content_generated_account");
    }
    summarizeServices();
    broadcastState();
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_OPEN_OUTLOOK") {
    clearAutoRunLease().finally(() => {});
    chrome.tabs.create({ url: "https://signup.live.com/signup" });
    setStatus("opening");
    pushLog("STEP", "已打开 Outlook/Hotmail 注册页");
    broadcastState();
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_SCAN_ACTIVE_TAB") {
    scanActiveTab();
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_FOCUS_ACTIVE_STEP") {
    sendStepAction("focus_active");
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_CLICK_CONTINUE") {
    sendStepAction("click_continue");
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_START_AUTOPILOT") {
    // 设置注册个数
    const requestedCount = Math.max(1, parseInt(message.registrationCount || message.payload?.registrationCount, 10) || 1);
    state.registrationCount = requestedCount;
    state.registrationCompleted = 0;

    startAutopilot(message.manualAccount || message.payload?.manualAccount || null, {
      provider: message.provider || message.payload?.provider || state.provider
    })
      .then((ack) => {
        summarizeServices();
        broadcastState();
        sendResponse({
          ...cloneState(),
          startAck: ack || state.startAck || null
        });
      })
      .catch((error) => {
        const ack = startFailureAck(String((error && error.message) || error || "background_exception"), {
          stage: "background_exception"
        });
        summarizeServices();
        broadcastState();
        sendResponse({
          ...cloneState(),
          startAck: ack
        });
      });
    return true;
  }

  if (type === "NM_RESUME_AUTOPILOT") {
    resumeAutopilot()
      .then((result) => {
        summarizeServices();
        broadcastState();
        sendResponse({ ...cloneState(), resume: result });
      })
      .catch((error) => {
        pushLog("BLOCK", "继续执行失败", {
          reason: String((error && error.message) || error || "background_exception")
        });
        summarizeServices();
        broadcastState();
        sendResponse({ ...cloneState(), resume: { ok: false, reason: "background_exception" } });
      });
    return true;
  }

  if (type === "NM_STOP_AUTOPILOT") {
    stopAutopilot();
    sendResponse(cloneState());
    return false;
  }

  if (type === "NM_ACCOUNT_CREATED") {
    const payload = message.payload || message;
    const account = payload.account || {};
    const email = normalizeEmail(account.email);
    const observedFinalState = payload.finalState || payload.final_state || "";
    const finalState = CREDENTIAL_READY_FINAL_STATES.has(observedFinalState) ? observedFinalState : "";
    const refreshToken = String(account.refreshToken || account.refresh_token || payload.refreshToken || payload.refresh_token || "").trim();
    if (!email || !account.password) {
      pushDedupeLog("BLOCK", "注册成功账号保存失败", {
        reason: "missing_email_or_password"
      });
      sendResponse({ ok: false, reason: "missing_email_or_password" });
      return false;
    }
    if (!finalState) {
      pushDedupeLog("STEP", "已观察到登录跳转，等待账号主页稳定后再获取刷新令牌", {
        email,
        observed_final_state: observedFinalState || "",
        url: payload.url || state.currentUrl || ""
      });
      sendResponse({ ok: true, waiting: true, reason: "waiting_for_account_home" });
      return false;
    }
    if (isCredentialLocked(email, false)) {
      const lock = credentialLock(email);
      pushDedupeLog("STEP", "重复最终态已忽略，四凭证流程已经在处理", {
        email,
        status: lock?.status || "",
        final_state: finalState
      });
      sendResponse({ ok: true, duplicate: true, status: lock?.status || "" });
      return false;
    }
    setCredentialLock(email, {
      status: refreshToken ? "saving" : "token_pending",
      finalState,
      stage: "registration_final_observed"
    });
    // ★ 保存注册标签页 ID，以便全部完成后关闭
    state.lastRegistrationTabId = sender?.tab?.id || state.autoRunTabId || null;
    clearAutoRunLease().finally(() => {});
    const delayed = Math.max(0, Math.min(120000, Number(payload.stableDelayMs || payload.stable_delay_ms || 0) || 0));
    const run = () => {
      const action = refreshToken
        ? rememberCreatedAccount({ ...payload, output_dir: DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR, refreshToken, refresh_token: refreshToken, stableDelayMs: 0, stable_delay_ms: 0, force: true })
        : startOAuthTokenExport(account, {
            finalState,
            url: payload.url || state.currentUrl || "",
            title: payload.title || state.title || "",
            outputDir: DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR,
            windowId: sender?.tab?.windowId || 0,
            force: true
          });
      action.then((result) => {
      if (result.ok) {
        if (refreshToken) {
          // 一个注册流程完成
          state.registrationCompleted = (state.registrationCompleted || 0) + 1;
          setStatus("done");
          const savedEmail = result.record.email;
          setCredentialLock(savedEmail, { status: "done", finalState, stage: "saved_with_refresh_token" });
          pushDedupeLog("OK", "注册成功账号已保存，四凭证完整", {
            email: savedEmail,
            credential_path: result.record?.credentialPath || result.record?.comboPath || result.webUi?.data?.credential_path || result.webUi?.data?.combo_path || credentialFilenameFor(savedEmail),
            output_dir: state.credentialOutputDir || "<browser_downloads>",
            web_ui_saved: Boolean(result.webUi && result.webUi.ok),
            token_job: result.webUi?.data?.token_job?.status || "saved",
            registration_completed: state.registrationCompleted,
            registration_count: state.registrationCount
          });
          // 如果还有注册任务，自动启动下一轮
          maybeStartNextRegistration(savedEmail);
        } else {
          setStatus("observing");
          pushDedupeLog("STEP", "注册成功，已启动刷新令牌获取流程", {
            email,
            output_dir: state.credentialOutputDir || "<browser_downloads>",
            oauth_tab: result.tabId || ""
          });
        }
      } else {
        setCredentialLock(email, { status: "failed", finalState, reason: result.reason || "unknown" });
        pushDedupeLog("BLOCK", "注册成功账号保存失败", {
          reason: result.reason || "unknown"
        });
      }
      summarizeServices();
      broadcastState();
      sendResponse({ ok: result.ok, result });
      }).catch((error) => {
        const reason = String(error && error.message || error);
        setCredentialLock(email, { status: "failed", finalState, reason });
        state.credentialStatus = {
          status: "save_failed",
          email,
          reason,
          output_dir: state.credentialOutputDir || "<browser_downloads>"
        };
        pushDedupeLog("BLOCK", "注册成功账号保存失败", { email, reason });
        summarizeServices();
        broadcastState();
        sendResponse({ ok: false, reason });
      });
    };
    if (delayed > 0) {
      pushDedupeLog("STEP", "注册成功，等待页面稳定后获取刷新令牌", {
        email,
        delay_ms: delayed,
        output_dir: state.credentialOutputDir || "<browser_downloads>"
      });
      setTimeout(run, delayed);
    } else {
      run();
    }
    return true;
  }

  if (type === "NM_ACTION_RESULT") {
    const payload = message.payload || {};
    if (String(payload.action || "").startsWith("auto_")) {
      state.autoRunLastCommandAt = Date.now();
    }
    if (payload.action === "auto_stop") {
      setStatus("stopped");
      pushDedupeLog("OK", "自动执行已停止", payload);
      broadcastState();
      sendResponse({ ok: true });
      return false;
    }
    if (payload.action === "auto_start") {
      pushDedupeLog(payload.ok ? "OK" : "BLOCK", payload.ok ? "自动执行已自动启动" : "自动执行启动失败", payload);
      broadcastState();
      sendResponse({ ok: true });
      return false;
    }
    const messageText = payload.action === "auto_click_continue"
      ? (payload.ok ? "自动点击继续/同意完成" : "自动点击继续/同意受阻")
      : (payload.ok ? "页面操作完成" : "页面操作受阻");
    if (payload.ok === false && (payload.blocker || payload.hardBlocker || payload.postChallengeState === "microsoft_problem")) {
      const rawBlocker = payload.blocker;
      const blockerType = String(
        rawBlocker && typeof rawBlocker === "object"
          ? (rawBlocker.type || rawBlocker.label || "")
          : (rawBlocker || payload.postChallengeState || "action_blocked")
      );
      const blockerEvidence = (rawBlocker && typeof rawBlocker === "object" ? rawBlocker.evidence : "")
        || payload.evidence
        || payload.reason
        || payload.url
        || "";
      state.blocker = {
        type: blockerType,
        label: (rawBlocker && typeof rawBlocker === "object" && rawBlocker.label) || blockerType,
        action: (rawBlocker && typeof rawBlocker === "object" && rawBlocker.action) || (payload.hardBlocker ? "manual_required" : "provider_or_manual_required"),
        evidence: blockerEvidence,
        source: "action_result"
      };
      state.rootCause = {
        blocker: blockerType,
        reason: payload.reason || "页面操作受阻",
        evidence: blockerEvidence,
        activeStep: payload.activeStep || state.activeStep || "",
        postChallengeState: payload.postChallengeState || state.postChallengeState || "",
        finalState: payload.finalState || state.finalState || "",
        nextAction: blockerType === "native_passkey_dialog"
          ? "手动取消系统通行密钥弹窗后，点“开始注册”继续普通步骤"
          : (blockerType === "microsoft_problem"
            ? "当前账号已标记为不可继续；下一次开始注册会重新生成账号、密码和 ID"
            : "记录阻碍点；不要绕过验证，处理完成后再继续")
      };
      state.activeStep = payload.activeStep || state.activeStep || "";
      state.postChallengeState = payload.postChallengeState || state.postChallengeState || "";
      state.finalState = payload.finalState || state.finalState || "";
      if (blockerType === "native_passkey_dialog") {
        setStatus("manual_wait");
      } else {
        setStatus("blocked");
      }
      if (blockerType === "microsoft_problem") {
        prepareAccountRegenerationAfterMicrosoftProblem(payload).then(() => {
          return restartAfterMicrosoftProblem(payload, sender.tab);
        }).then(() => {
          summarizeServices();
          broadcastState();
        }).catch((error) => {
          pushDedupeLog("BLOCK", "Microsoft 问题页账号重置失败", {
            reason: String(error && error.message || error)
          });
          broadcastState();
        });
      }
    }
    pushDedupeLog(payload.ok ? "OK" : "BLOCK", messageText, payload);
    broadcastState();
    sendResponse({ ok: true });
    return false;
  }

  if (type === "NM_CONTENT_STATUS") {
    const payload = message.payload || {};
    const effectiveProvider = preserveMicrosoftDomainProvider(payload.provider, payload.url);
    if (effectiveProvider && PROVIDERS[effectiveProvider]) {
      state.provider = effectiveProvider;
      state.providerLabel = providerConfig(effectiveProvider).label;
      payload.provider = effectiveProvider;
    }
    const key = frameKey(payload);
    state.frameReports[key] = {
      ...payload,
      receivedAt: nowIso()
    };
    if (payload.isTopFrame) {
      rememberObservedSteps(payload);
    }
    recomputeStateFromFrames();
    const payloadBlockerType = payload.blocker && typeof payload.blocker === "object"
      ? payload.blocker.type
      : String(payload.blocker || "");
    if (payload.isTopFrame && payloadBlockerType === "microsoft_problem") {
      const problemPayload = {
        ...payload,
        evidence: payload.blocker?.evidence || payload.url || "",
        reason: payload.rootCause?.reason || "microsoft_problem"
      };
      prepareAccountRegenerationAfterMicrosoftProblem(problemPayload).then(() => {
        return restartAfterMicrosoftProblem(problemPayload, sender.tab);
      }).then(() => {
        summarizeServices();
        broadcastState();
      }).catch((error) => {
        pushDedupeLog("BLOCK", "Microsoft 问题页账号重置失败", {
          reason: String(error && error.message || error)
        });
      });
    }
    // When any child frame reports a blocker, proactively stop the top-frame auto-run
    const blockingChallenges = (state.challengeFrames || []).filter((item) => item.blocking);
    if (blockingChallenges.length && !payload.isTopFrame && payload.blocker) {
      const tabId = sender?.tab?.id;
      if (tabId && state.autoRunEnabled && state.autoRunTabId === tabId) {
        pushDedupeLog("BLOCK", "子 frame 检测到人机验证，主动停止顶层自动执行", {
          challenge: payload.blocker?.type || "",
          evidence: payload.blocker?.evidence || "",
          frame: payload.frame || "child"
        });
        clearAutoRunLease().then(() => {
          chrome.tabs.sendMessage(tabId, { type: "NM_STEP_ACTION", action: "stop_auto" }, () => { void chrome.runtime.lastError; });
        });
      }
    }
    maybeResumeAutoRunForContent(sender, payload).catch((error) => {
      pushDedupeLog("BLOCK", "自动注册恢复失败", {
        reason: String(error && error.message || error)
      });
    });
    maybeStartTokenExportFromFinalStatus(sender, payload).catch((error) => {
      pushDedupeLog("BLOCK", "最终态自动获取刷新令牌失败", {
        reason: String(error && error.message || error)
      });
    });
    const top = topReport();
    const topActionable = isActionableTopReport(top);

    if (payload.blocker) {
      const logLevel = payload.isTopFrame || !topActionable ? "BLOCK" : "STEP";
      const logMessage = payload.isTopFrame
        ? "主页面检测到人机验证"
        : (topActionable ? "子 frame 检测到挑战，但主页面可继续" : "子 frame 检测到人机验证");
      const blocking = payload.isTopFrame || !topActionable;
      if (blocking) {
        pushDedupeLog(logLevel, logMessage, {
          challenge: payload.blocker.type,
          evidence: payload.blocker.evidence,
          activeStep: payload.activeStep,
          frame: payload.frame,
          url: payload.url,
          blocking
        });
      }
    } else if (payload.isTopFrame) {
      pushDedupeLog("STEP", `当前步骤：${payload.activeStep || "未知"}`, {
        reason: payload.reason,
        postChallengeState: payload.postChallengeState || "",
        finalState: payload.finalState || "",
        url: payload.url,
        captchaCheck: payload.captchaCheck || "NONE",
        frameDebug: payload.frameDebug || [],
        frameCount: (payload.frameSources || []).length
      });
    }

    broadcastState();
    sendResponse({ ok: true });
    return false;
  }

  return false;
});
