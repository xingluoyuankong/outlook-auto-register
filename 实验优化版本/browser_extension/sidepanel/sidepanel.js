const elements = {
  statusText: document.getElementById("statusText"),
  statusBadge: document.getElementById("statusBadge"),
  providerSelect: document.getElementById("providerSelect"),
  providerValue: document.getElementById("providerValue"),
  flowModeValue: document.getElementById("flowModeValue"),
  flowProviderTabs: document.getElementById("flowProviderTabs"),
  flowHintValue: document.getElementById("flowHintValue"),
  updatedValue: document.getElementById("updatedValue"),
  serviceGrid: document.getElementById("serviceGrid"),
  smsDiagStatusValue: document.getElementById("smsDiagStatusValue"),
  smsDiagList: document.getElementById("smsDiagList"),
  refreshSmsDiagBtn: document.getElementById("refreshSmsDiagBtn"),
  smsProviderSelect: document.getElementById("smsProviderSelect"),
  smsCountryInput: document.getElementById("smsCountryInput"),
  loadSmsNumbersBtn: document.getElementById("loadSmsNumbersBtn"),
  smsNumberSelect: document.getElementById("smsNumberSelect"),
  copySmsNumberBtn: document.getElementById("copySmsNumberBtn"),
  refreshSmsMessagesBtn: document.getElementById("refreshSmsMessagesBtn"),
  copySmsCodeBtn: document.getElementById("copySmsCodeBtn"),
  smsUseStatusValue: document.getElementById("smsUseStatusValue"),
  smsCodeValue: document.getElementById("smsCodeValue"),
  smsMessagesList: document.getElementById("smsMessagesList"),
  blockerValue: document.getElementById("blockerValue"),
  evidenceValue: document.getElementById("evidenceValue"),
  nextValue: document.getElementById("nextValue"),
  activeStepValue: document.getElementById("activeStepValue"),
  titleValue: document.getElementById("titleValue"),
  urlValue: document.getElementById("urlValue"),
  postStateValue: document.getElementById("postStateValue"),
  stepsList: document.getElementById("stepsList"),
  challengeList: document.getElementById("challengeList"),
  challengeEmpty: document.getElementById("challengeEmpty"),
  logsText: document.getElementById("logsText"),
  logCountValue: document.getElementById("logCountValue"),
  openWebUiBtn: document.getElementById("openWebUiBtn"),
  webUiBaseUrlInput: document.getElementById("webUiBaseUrlInput"),
  webUiHealthValue: document.getElementById("webUiHealthValue"),
  saveWebUiBaseUrlBtn: document.getElementById("saveWebUiBaseUrlBtn"),
  openBackendBtn: document.getElementById("openBackendBtn"),
  checkBackendBtn: document.getElementById("checkBackendBtn"),
  scanBtn: document.getElementById("scanBtn"),
  clearBtn: document.getElementById("clearBtn"),
  copyLogsBtn: document.getElementById("copyLogsBtn"),
  focusBtn: document.getElementById("focusBtn"),
  continueBtn: document.getElementById("continueBtn"),
  resumeBtn: document.getElementById("resumeBtn"),
  stopBtn: document.getElementById("stopBtn"),
  credentialDirInput: document.getElementById("credentialDirInput"),
  manualEmailInput: document.getElementById("manualEmailInput"),
  manualPasswordInput: document.getElementById("manualPasswordInput"),
  manualClientIdInput: document.getElementById("manualClientIdInput"),
  manualRefreshTokenInput: document.getElementById("manualRefreshTokenInput"),
  saveCredDirBtn: document.getElementById("saveCredDirBtn"),
  exportThreeCredBtn: document.getElementById("exportThreeCredBtn"),
  exportCredBtn: document.getElementById("exportCredBtn"),
  exportFourCredBtn: document.getElementById("exportFourCredBtn"),
  validateCredBtn: document.getElementById("validateCredBtn"),
  refreshCredBtn: document.getElementById("refreshCredBtn"),
  credStatusValue: document.getElementById("credStatusValue"),
  credInfoValue: document.getElementById("credInfoValue"),
  copyFourCredBtn: document.getElementById("copyFourCredBtn"),
  openCredentialDirBtn: document.getElementById("openCredentialDirBtn"),
  recoverLoginBtn: document.getElementById("recoverLoginBtn"),
  logModeSummaryBtn: document.getElementById("logModeSummaryBtn"),
  logModeRawBtn: document.getElementById("logModeRawBtn"),
  registrationCountInput: document.getElementById("registrationCountInput"),
  registrationProgressValue: document.getElementById("registrationProgressValue"),
  // ── 代理状态面板 ──
  proxyStatusPanel: document.getElementById("proxyStatusPanel"),
  proxyStatusIcon: document.getElementById("proxyStatusIcon"),
  proxyStatusTitle: document.getElementById("proxyStatusTitle"),
  proxyStatusDetails: document.getElementById("proxyStatusDetails"),
  // ── 代理管理 ──
  proxyPanel: document.querySelector(".proxy-panel"),
  proxyStatusValue: document.getElementById("proxyStatusValue"),
  proxyCountValue: document.getElementById("proxyCountValue"),
  proxyStableCountValue: document.getElementById("proxyStableCountValue"),
  proxyAutoCheckbox: document.getElementById("proxyAutoCheckbox"),
  proxyTextarea: document.getElementById("proxyTextarea"),
  proxyFileInput: document.getElementById("proxyFileInput"),
  proxyImportFileBtn: document.getElementById("proxyImportFileBtn"),
  proxyPasteBtn: document.getElementById("proxyPasteBtn"),
  proxyCardList: document.getElementById("proxyCardList"),
  proxyCardCount: document.getElementById("proxyCardCount"),
  proxyCardItems: document.getElementById("proxyCardItems"),
  proxyLoadBtn: document.getElementById("proxyLoadBtn"),
  proxySaveBtn: document.getElementById("proxySaveBtn"),
  proxyCheckBtn: document.getElementById("proxyCheckBtn"),
  proxyCheckLimitInput: document.getElementById("proxyCheckLimitInput"),
  proxyClearBtn: document.getElementById("proxyClearBtn"),
  proxyResultValue: document.getElementById("proxyResultValue")
};

const FLOW = globalThis.NinjemailFlow || {};
const DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e";
const DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR = "C:\\Users\\XZXyuan\\Downloads";
const CREDENTIAL_OUTPUT_DIR_STORAGE_KEY = "ninjemailCredentialOutputDir";
const WEB_UI_BASE_URL_STORAGE_KEY = "ninjemailWebUiBaseUrl";
const LOG_MODE = {
  raw: "raw",
  summary: "summary"
};
const uiState = {
  latest: null,
  logMode: LOG_MODE.raw
};

// ★ 代理冷却实时倒计时
let _cooldownDetails = []; // [{proxy, cooldownUntil}]
let _cooldownTimerId = null;

function formatCooldownSec(untilMs) {
  const sec = Math.max(0, Math.ceil((untilMs - Date.now()) / 1000));
  if (sec >= 60) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m${s}s`;
  }
  return `${sec}s`;
}

function buildCooldownText(details) {
  if (!details || !details.length) return "";
  const now = Date.now();
  const active = details.filter(d => d.cooldownUntil > now);
  if (!active.length) return "";
  const items = active.map(d => `${d.proxy}(${formatCooldownSec(d.cooldownUntil)})`);
  return ` [冷却${active.length}: ${items.join(", ")}]`;
}

function tickCooldownDisplay() {
  const now = Date.now();
  // 清除已过期的
  _cooldownDetails = _cooldownDetails.filter(d => d.cooldownUntil > now);
  const cdText = buildCooldownText(_cooldownDetails);
  // 更新代理引擎状态文本
  if (elements.proxyStatusValue && uiState.latest && uiState.latest.proxyEngine) {
    const pe = uiState.latest.proxyEngine;
    const healthy = pe.healthyCount || 0;
    const total = pe.count || 0;
    if (pe.currentProxy) {
      elements.proxyStatusValue.textContent = `轮询中: ${pe.currentProxy} (${healthy}/${total})${cdText}`;
    } else if (pe.enabled && total > 0) {
      elements.proxyStatusValue.textContent = `已启用 ${total} 个（可用:${healthy}${cdText}）`;
    }
  }
  // 更新代理状态面板（冷却信息实时刷新）
  if (elements.proxyStatusDetails && uiState.latest) {
    const ps = uiState.latest.proxyEngine || {};
    if (ps.activeStatus === "active") {
      const ipText = ps.exitIp || "";
      const countryText = ps.exitCountry ? ` (${ps.exitCountry})` : "";
      
      const details = [];
      if (ps.currentProxy) {
        details.push(`<strong>代理：</strong>${ps.currentProxy}`);
      }
      if (ipText) {
        details.push(`<strong>出口IP：</strong>${ipText}${countryText}`);
      }
      if (_cooldownDetails.length) {
        const items = _cooldownDetails.map(d => `${d.proxy} (${formatCooldownSec(d.cooldownUntil)})`);
        details.push(`<strong>冷却中 ${_cooldownDetails.length}：</strong>${items.join("，")}`);
      }
      elements.proxyStatusDetails.innerHTML = details.join("<br>");
    }
  }
  // 如果所有冷却都结束了，停止定时器
  if (!_cooldownDetails.length && _cooldownTimerId) {
    clearInterval(_cooldownTimerId);
    _cooldownTimerId = null;
  }
}

function startCooldownTimer() {
  if (_cooldownTimerId) return;
  _cooldownTimerId = setInterval(tickCooldownDisplay, 1000);
}

const PROVIDER_LABELS = {
  outlook: "Outlook 邮箱",
  hotmail: "Hotmail 邮箱",
  gmail: "Gmail 邮箱",
  yahoo: "Yahoo 邮箱",
  proton: "Proton Mail",
  gmx: "GMX Mail",
  aol: "AOL Mail",
  zoho: "Zoho Mail",
  yandex: "Yandex Mail",
  mailcom: "Mail.com",
  icloud: "iCloud Mail",
  mailru: "Mail.ru",
  naver: "Naver Mail",
  kakao: "Daum/Kakao Mail",
  netease163: "163 Mail",
  netease126: "126 Mail",
  neteaseyeah: "Yeah.net Mail",
  qq: "QQ Mail",
  sina: "Sina Mail",
  sohu: "Sohu Mail",
  tutanota: "Tutanota"
};

const PROVIDER_KEYS = Object.freeze(Object.keys(PROVIDER_LABELS));
const STATUS_LABELS = {
  idle: "待命",
  opening: "打开中",
  observing: "观察中",
  stopped: "已停止",
  manual_wait: "等待人工",
  blocked: "已阻塞",
  post_challenge: "验证后处理",
  done: "完成",
  ...(FLOW.STATUS_LABELS || {})
};

const STEP_STATUS_LABELS = {
  done: "✓",
  seen: "⊙",
  current: "→",
  blocked: "✗",
  pending: "○"
};

const CREDENTIAL_STEP = {
  id: "export_credentials",
  label: "获取四凭证",
  intent: "注册成功后获取并保存：账号----密码----客户端ID----刷新令牌。",
  status: "pending",
  evidence: "等待账号注册成功"
};

const PROVIDER_FLOW_HINTS = {
  outlook: "Outlook: 用户名 → 密码 → 姓名 → 生日 → 验证 → 四凭证",
  hotmail: "Hotmail: 保留 hotmail.com 域名，步骤同 Outlook",
  gmail: "Gmail: 姓名 → 生日/性别 → 用户名 → 密码 → 验证",
  yahoo: "Yahoo: 单页表单，姓名+用户名+密码+生日后提交"
};

for (const key of PROVIDER_KEYS) {
  if (!PROVIDER_FLOW_HINTS[key]) {
    PROVIDER_FLOW_HINTS[key] = `${PROVIDER_LABELS[key]} 独立流程`;
  }
}

function clearNode(node) {
  if (node) node.textContent = "";
}

function send(type, payload = {}) {
  chrome.runtime.sendMessage({ type, ...payload }, (response) => {
    if (chrome.runtime.lastError) {
      if (type === "NM_EXPORT_CREDENTIALS" || type === "NM_START_AUTOPILOT") {
        elements.credStatusValue.textContent = "发送失败";
        elements.credInfoValue.textContent = `后台未响应：${chrome.runtime.lastError.message || "unknown"}`;
      }
      return;
    }
    if (response) render(response);
    if (type === "NM_START_AUTOPILOT") {
      renderStartAckStatus(response && response.startAck ? response.startAck : {
        ok: false,
        stage: "background_empty_response",
        reason: "background_empty_response"
      });
    }
  });
}

function statusLabel(status, fallback = "") {
  return STATUS_LABELS[status] || fallback || status || "未知";
}

function badgeClass(status) {
  if (status === "blocked" || status === "manual_wait") return "badge blocked";
  if (status === "observing" || status === "post_challenge" || status === "done") return "badge ok";
  if (status === "stopped") return "badge stopped";
  return "badge";
}

function blockingChallenges(state = {}) {
  return (state.challengeFrames || []).filter((item) => item && item.blocking);
}

function nextAction(state) {
  if (state.status === "stopped") return "已停止；点[继续执行]可恢复";
  if (state.rootCause && state.rootCause.nextAction) return state.rootCause.nextAction;
  if (blockingChallenges(state).length) return "处理阻塞挑战后继续";
  if (!state.blocker) return state.postChallengeState ? "处理验证后页面" : "点[开始注册]";
  if (state.blocker.type === "hsprotect") return "手动完成按住验证";
  return "确认服务支持或手动处理";
}

function providerSteps(provider = "outlook") {
  return FLOW.stepsForProvider ? FLOW.stepsForProvider(provider) : [];
}

function ensureCredentialStep(steps = []) {
  const result = Array.isArray(steps) ? [...steps] : [];
  const hasStep = result.some((step) => step && step.id === "export_credentials");
  if (!hasStep) result.push({ ...CREDENTIAL_STEP });
  return result;
}

function defaultStepRows(provider = "outlook") {
  return ensureCredentialStep(providerSteps(provider)).map((step) => ({
    ...step,
    status: "pending",
    evidence: step.evidence || "本轮尚未观察到该步骤"
  }));
}

function stepStatusLabel(status) {
  return STEP_STATUS_LABELS[status] || status || "?";
}

function manualAccountFromInputs(includeDefaults = true) {
  return {
    email: elements.manualEmailInput.value.trim(),
    password: elements.manualPasswordInput.value,
    clientId: elements.manualClientIdInput.value.trim() || (includeDefaults ? DEFAULT_CLIENT_ID : ""),
    refreshToken: elements.manualRefreshTokenInput.value.trim()
  };
}

function manualAccountForStartRegistration() {
  const manual = manualAccountFromInputs(false);
  if (!manual.email && !manual.password && !manual.clientId && !manual.refreshToken) return null;
  return { ...manualAccountFromInputs(false), source: "user_input" };
}

function threeCredentialText(account = {}) {
  const email = String(account.email || "").trim();
  const password = String(account.password || "");
  const clientId = String(account.clientId || account.client_id || DEFAULT_CLIENT_ID).trim() || DEFAULT_CLIENT_ID;
  if (!email || !password) return "";
  return `${email}----${password}----${clientId}`;
}

function fourCredentialText(account = {}) {
  const base = threeCredentialText(account);
  const refreshToken = String(account.refreshToken || account.refresh_token || "").trim();
  return base && refreshToken ? `${base}----${refreshToken}` : "";
}

function copyTextToClipboard(text, button, okText = "已复制") {
  const value = String(text || "").trim();
  if (!value) return;
  navigator.clipboard.writeText(value).then(() => {
    if (!button) return;
    const previous = button.textContent;
    button.textContent = okText;
    setTimeout(() => {
      button.textContent = previous;
    }, 1200);
  }).catch(() => {
    const area = document.createElement("textarea");
    area.value = value;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  });
}

function renderStartAckStatus(ack = {}) {
  const stage = ack.stage || "unknown";
  const reason = ack.reason || "";
  const provider = ack.provider || elements.providerSelect.value || "";
  const tabId = ack.tabId ? ` | tab: ${ack.tabId}` : "";
  const runId = ack.runId ? ` | run: ${ack.runId}` : "";
  const url = ack.url ? ` | url: ${ack.url}` : "";
  if (ack.ok) {
    elements.credStatusValue.textContent = "页面 ACK 已收到";
    elements.credInfoValue.textContent = `正在执行 | ${provider}${tabId}${runId}${url}`;
    return;
  }
  if (stage === "waiting_for_content_ack") {
    elements.credStatusValue.textContent = "等待页面 ACK";
    elements.credInfoValue.textContent = `等待 content script 响应 | ${provider}${tabId}${runId}${url}`;
    return;
  }
  elements.credStatusValue.textContent = "启动失败";
  elements.credInfoValue.textContent = `未收到 ACK | ${provider} | ${stage} | ${reason || "unknown"}${tabId}${runId}${url}`;
}

function renderServices(services = {}) {
  clearNode(elements.serviceGrid);
  for (const [key, value] of Object.entries(services || {})) {
    const row = document.createElement("div");
    row.className = "service-item";
    const name = document.createElement("strong");
    name.textContent = key;
    const text = document.createElement("span");
    text.textContent = value && value.text ? value.text : statusLabel(value && value.status, "未知");
    row.append(name, text);
    elements.serviceGrid.append(row);
  }
}

function renderSmsDiagnostics(diag = {}) {
  elements.smsDiagStatusValue.textContent = diag.status || "未刷新";
  clearNode(elements.smsDiagList);
  for (const item of diag.providers || []) {
    const row = document.createElement("div");
    row.className = "sms-diag-row";
    row.textContent = `${item.provider}: ${item.status || ""} ${item.reason || ""}`.trim();
    elements.smsDiagList.append(row);
  }
}

function renderSmsUsage(state = {}) {
  elements.smsUseStatusValue.textContent = state.reason || state.status || "未加载号码";
  elements.smsCodeValue.textContent = `验证码：${state.code || "无"}`;
  clearNode(elements.smsMessagesList);
  clearNode(elements.smsNumberSelect);
  for (const item of state.numbers || []) {
    const option = document.createElement("option");
    const phone = typeof item === "string" ? item : (item.phone || item.number || "");
    option.value = phone;
    option.textContent = phone;
    if (state.selectedNumber === phone) option.selected = true;
    elements.smsNumberSelect.append(option);
  }
  for (const item of state.messages || []) {
    const row = document.createElement("div");
    row.className = "sms-message-row";
    row.textContent = typeof item === "string" ? item : JSON.stringify(item);
    elements.smsMessagesList.append(row);
  }
}

function renderFlowProviderTabs(provider = "outlook") {
  clearNode(elements.flowProviderTabs);
  for (const key of PROVIDER_KEYS) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.provider = key;
    button.textContent = PROVIDER_LABELS[key] || key;
    if (key === provider) button.classList.add("active");
    button.addEventListener("click", () => {
      elements.providerSelect.value = key;
      send("NM_SET_PROVIDER", { provider: key });
    });
    elements.flowProviderTabs.append(button);
  }
}

/* ── 步骤链路：每行一个卡片，卡片内文字横排 ── */
function renderSteps(steps = [], blocker = null, provider = "outlook") {
  clearNode(elements.stepsList);
  const rows = ensureCredentialStep(steps.length ? steps : defaultStepRows(provider));
  for (const step of rows) {
    const row = document.createElement("div");
    row.className = `step-row ${step.status || "pending"}`;
    row.dataset.stepId = step.id;

    // 圆点
    const dot = document.createElement("span");
    dot.className = `step-dot ${step.status === "current" ? "on" : step.status === "blocked" ? "blocked" : step.status === "done" ? "on" : ""}`;

    // 步骤名（横排文字）
    const text = document.createElement("span");
    text.className = "step-text";
    text.textContent = step.label || step.id;

    // 状态符号 ✓/✗/○/→
    const status = document.createElement("span");
    status.className = "step-status";
    status.textContent = stepStatusLabel(step.status);

    // 执行按钮
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "step-run-btn";
    btn.dataset.stepId = step.id;
    btn.textContent = "▶";

    row.append(dot, text, status, btn);

    if ((blocker && step.id === "challenge") || step.status === "blocked") {
      row.classList.add("blocked");
    }

    elements.stepsList.append(row);
  }
}

/* ── 挑战详情：修复展开后看不见 ── */
function renderChallenges(challenges = []) {
  clearNode(elements.challengeList);
  if (elements.challengeEmpty) {
    elements.challengeEmpty.style.display = challenges.length ? "none" : "";
  }
  for (const item of challenges) {
    const row = document.createElement("div");
    row.className = `challenge-row ${item.blocking ? "blocking" : "passive"}`;
    const title = document.createElement("div");
    title.className = "challenge-title";
    title.textContent = item.type || item.label || "challenge";
    const meta = document.createElement("div");
    meta.className = "challenge-meta";
    meta.textContent = item.blocking
      ? `阻塞 · ${item.evidence || ""}`
      : `附属 · ${item.evidence || ""}`;
    row.append(title, meta);
    elements.challengeList.append(row);
  }
}

function logLine(entry = {}) {
  const details = entry.details ? ` ${JSON.stringify(entry.details)}` : "";
  return `[${entry.level || "INFO"}] ${entry.at || ""} ${entry.message || ""}${details}`.trim();
}

function renderLogs(logs = []) {
  elements.logCountValue.textContent = `${logs.length} 条`;
  if (uiState.logMode === LOG_MODE.summary) {
    elements.logsText.value = logs.map((item) => item.message || "").join("\n");
  } else {
    elements.logsText.value = logs.map(logLine).join("\n");
  }
}

function renderCredentialSummary(state = {}) {
  const cred = state.credentialStatus || {};
  const last = state.lastCreatedAccount || state.lastGeneratedAccount || state.activeAccount || {};
  const three = threeCredentialText(last);
  const four = fourCredentialText(last);

  // 自动填入凭证到输入框
  const email = String(last.email || "").trim();
  const password = String(last.password || "").trim();
  const clientId = String(last.clientId || last.client_id || DEFAULT_CLIENT_ID).trim();
  const refreshToken = String(last.refreshToken || last.refresh_token || "").trim();

  if (email) elements.manualEmailInput.value = email;
  if (password) elements.manualPasswordInput.value = password;
  if (clientId) elements.manualClientIdInput.value = clientId;
  if (refreshToken) elements.manualRefreshTokenInput.value = refreshToken;

  if (four) {
    elements.credInfoValue.textContent = `四凭证: ${four}`;
  } else if (three) {
    elements.credInfoValue.textContent = `三凭证: ${three}`;
  } else if (cred.output_dir) {
    elements.credInfoValue.textContent = `保存目录: ${cred.output_dir}`;
  } else {
    elements.credInfoValue.textContent = "当前：无";
  }
}

function render(state = {}) {
  uiState.latest = state;
  const provider = state.provider || elements.providerSelect.value || "outlook";
  elements.statusText.textContent = statusLabel(state.status, "待命");
  elements.statusBadge.textContent = statusLabel(state.status, "待命");
  elements.statusBadge.className = badgeClass(state.status);
  elements.providerValue.textContent = state.providerLabel || PROVIDER_LABELS[provider] || provider;
  elements.updatedValue.textContent = state.updatedAt || "未更新";
  elements.providerSelect.value = provider;
  elements.flowHintValue.textContent = PROVIDER_FLOW_HINTS[provider] || "";
  elements.flowModeValue.textContent = `${PROVIDER_LABELS[provider] || provider} / ${providerSteps(provider).length || 0} 步`;
  elements.blockerValue.textContent = state.rootCause?.reason || (state.blocker ? `${state.blocker.label || state.blocker.type}:${state.blocker.action || ""}` : "无");
  elements.evidenceValue.textContent = state.rootCause?.evidence || (state.blocker ? state.blocker.evidence || "已检测" : "无");
  elements.nextValue.textContent = nextAction(state);
  elements.activeStepValue.textContent = state.activeStep ? (FLOW.stepLabel?.(state.activeStep, provider) || state.activeStep) : "无";
  elements.titleValue.textContent = state.title || "无标题";
  elements.urlValue.textContent = state.currentUrl || "无 URL";
  elements.postStateValue.textContent = `验证后：${state.postChallengeState || "无"} / 最终：${state.finalState || "无"}`;
  elements.credStatusValue.textContent = (state.credentialStatus && state.credentialStatus.status) || elements.credStatusValue.textContent || "未设置";
  renderCredentialSummary(state);
  renderServices(state.services || {});
  renderSmsDiagnostics(state.smsDiagnostics || {});
  renderSmsUsage(state.smsUsage || {});
  renderFlowProviderTabs(provider);
  renderSteps(state.steps || [], state.blocker || null, provider);
  renderChallenges(state.challengeFrames || []);
  renderLogs(state.logs || []);
  // 代理引擎状态同步
  if (state.proxyEngine) {
    const pe = state.proxyEngine;
    if (pe.count > 0 && !elements.proxyTextarea.value.trim()) {
      // 不覆盖用户手动输入，只在文本框为空时显示数量信息
      elements.proxyCountValue.textContent = String(pe.count);
    }
    elements.proxyStableCountValue.textContent = String(pe.healthyCount || 0);
    elements.proxyAutoCheckbox.checked = !!pe.enabled;
    const cooldown = pe.cooldownCount || 0;
    const healthy = pe.healthyCount || 0;
    const total = pe.count || 0;
    // 更新代理卡片高亮当前代理
    if (pe.currentProxy && elements.proxyCardItems.children.length) {
      elements.proxyCardItems.querySelectorAll(".proxy-chip").forEach(chip => {
        const lbl = chip.querySelector(".proxy-chip-label");
        chip.classList.toggle("active", lbl && lbl.title === pe.currentProxy);
      });
    }
    // ★ 存储冷却详情并启动实时倒计时
    if (pe.cooldownDetails && pe.cooldownDetails.length) {
      _cooldownDetails = pe.cooldownDetails.filter(d => d.cooldownUntil > Date.now());
      if (_cooldownDetails.length) startCooldownTimer();
    } else {
      _cooldownDetails = [];
    }
    const cooldownText = buildCooldownText(_cooldownDetails);
    if (pe.currentProxy) {
      let statusText = `轮询中: ${pe.currentProxy} (${healthy}/${total})`;
      statusText += cooldownText;
      elements.proxyStatusValue.textContent = statusText;
    } else if (pe.enabled && total > 0) {
      let statusText = `已启用 ${total} 个（可用:${healthy}`;
      statusText += cooldownText;
      statusText += "）";
      elements.proxyStatusValue.textContent = statusText;
    } else if (total > 0) {
      elements.proxyStatusValue.textContent = `${total} 个代理（未启用，可用:${healthy}${cooldownText}）`;
    }
  }
  if (state.startAck && (state.startAck.ok === false || state.startAck.stage === "waiting_for_content_ack")) {
    renderStartAckStatus(state.startAck);
  }
  // 注册进度更新
  if (state.registrationCount != null || state.registrationCompleted != null) {
    const total = state.registrationCount || parseInt(elements.registrationCountInput.value, 10) || 1;
    const completed = state.registrationCompleted || 0;
    elements.registrationProgressValue.textContent = `${completed}/${total}`;
  }

  // ── 代理状态面板（始终更新，醒目显示）──
  const proxyState = state.proxyEngine || {};
  const proxyStatus = proxyState.activeStatus || "none";
  console.log("[render] proxyStatus:", proxyStatus, "enabled:", proxyState.enabled, "count:", proxyState.count);
  const panel = elements.proxyStatusPanel;
  if (panel) {
    // 清除旧状态
    panel.className = "proxy-status-panel";
    
    if (proxyStatus === "active") {
      panel.classList.add("active");
      elements.proxyStatusIcon.textContent = "✅";
      elements.proxyStatusTitle.textContent = "正在使用代理";
      
      // 构建详细信息
      const details = [];
      if (proxyState.currentProxy) {
        details.push(`<strong>代理：</strong>${proxyState.currentProxy}`);
      }
      if (proxyState.exitIp) {
        const country = proxyState.exitCountry ? ` (${proxyState.exitCountry})` : "";
        details.push(`<strong>出口IP：</strong>${proxyState.exitIp}${country}`);
      }
      if (_cooldownDetails.length) {
        const items = _cooldownDetails.map(d => `${d.proxy} (${formatCooldownSec(d.cooldownUntil)})`);
        details.push(`<strong>冷却中 ${_cooldownDetails.length}：</strong>${items.join("，")}`);
      }
      elements.proxyStatusDetails.innerHTML = details.join("<br>");
      
    } else if (proxyStatus === "checking") {
      panel.classList.add("checking");
      elements.proxyStatusIcon.textContent = "🔄";
      elements.proxyStatusTitle.textContent = "正在检测代理...";
      if (proxyState.currentProxy) {
        elements.proxyStatusDetails.innerHTML = `<strong>测试代理：</strong>${proxyState.currentProxy}`;
      } else {
        elements.proxyStatusDetails.innerHTML = "验证代理连通性和出口IP";
      }
      
    } else if (proxyStatus === "failed") {
      panel.classList.add("failed");
      elements.proxyStatusIcon.textContent = "❌";
      elements.proxyStatusTitle.textContent = "代理未生效！";
      
      const details = [];
      if (proxyState.currentProxy) {
        details.push(`<strong>失败代理：</strong>${proxyState.currentProxy}`);
      }
      details.push(`<strong style="color:#c62828">⚠️ 警告：注册可能走直连，地址会显示中国！</strong>`);
      elements.proxyStatusDetails.innerHTML = details.join("<br>");
      
    } else if (proxyStatus === "direct") {
      panel.classList.add("direct");
      elements.proxyStatusIcon.textContent = "⚠️";
      elements.proxyStatusTitle.textContent = "无可用代理，使用直连";
      elements.proxyStatusDetails.innerHTML = `<strong style="color:#e65100">⚠️ 注册地址将显示中国IP</strong>`;
      
    } else if (proxyStatus === "ready") {
      // ★ 新状态：代理已导入且检测通过，就绪可用
      panel.classList.add("active");
      elements.proxyStatusIcon.textContent = "✅";
      const healthy = proxyState.healthyCount || 0;
      const total = proxyState.count || 0;
      elements.proxyStatusTitle.textContent = `代理已就绪（${healthy}/${total} 可用）`;
      const details = [];
      if (proxyState.currentProxy) {
        details.push(`<strong>当前代理：</strong>${proxyState.currentProxy}`);
      }
      if (proxyState.cooldownCount > 0) {
        details.push(`${proxyState.cooldownCount} 个冷却中`);
      }
      details.push(`点击“开始注册”即可使用代理`);
      elements.proxyStatusDetails.innerHTML = details.join("<br>");
      
    } else if (proxyStatus === "idle") {
      // ★ 新状态：代理已导入但未检测或全部不可用
      panel.classList.add("direct");
      elements.proxyStatusIcon.textContent = "⚠️";
      const total = proxyState.count || 0;
      elements.proxyStatusTitle.textContent = `${total} 个代理未检测`;
      elements.proxyStatusDetails.innerHTML = `请先检测代理可用性，然后开始注册`;
      
    } else {
      // none - 代理未启用或无代理列表
      elements.proxyStatusIcon.textContent = "⚪";
      if (!proxyState.enabled || proxyState.count === 0) {
        elements.proxyStatusTitle.textContent = "代理未启用";
        elements.proxyStatusDetails.innerHTML = "请在代理管理中导入代理列表";
      } else {
        elements.proxyStatusTitle.textContent = `${proxyState.count} 个代理待用`;
        const details = [];
        if (proxyState.cooldownCount > 0) {
          details.push(`${proxyState.cooldownCount} 个冷却中`);
        }
        if (proxyState.healthyCount > 0) {
          details.push(`${proxyState.healthyCount} 个可用`);
        }
        elements.proxyStatusDetails.innerHTML = details.length ? details.join("，") : "等待开始注册";
      }
    }
  }
}

function populateProviderSelect() {
  if (!elements.providerSelect) return;
  const selected = elements.providerSelect.value || "outlook";
  clearNode(elements.providerSelect);
  for (const key of PROVIDER_KEYS) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = PROVIDER_LABELS[key] || key;
    elements.providerSelect.append(option);
  }
  if (PROVIDER_LABELS[selected]) elements.providerSelect.value = selected;
}

function loadLocalSettings() {
  try {
    chrome.storage.local.get([
      CREDENTIAL_OUTPUT_DIR_STORAGE_KEY,
      WEB_UI_BASE_URL_STORAGE_KEY
    ], (stored) => {
      elements.credentialDirInput.value = stored[CREDENTIAL_OUTPUT_DIR_STORAGE_KEY] || "";
      elements.webUiBaseUrlInput.value = stored[WEB_UI_BASE_URL_STORAGE_KEY] || "";
    });
  } catch (_) {
    // Ignore extension reload races.
  }
}

populateProviderSelect();
loadLocalSettings();

elements.providerSelect.addEventListener("change", () => {
  send("NM_SET_PROVIDER", { provider: elements.providerSelect.value });
});

elements.refreshSmsDiagBtn.addEventListener("click", () => send("NM_REFRESH_SMS_DIAGNOSTICS"));
elements.loadSmsNumbersBtn.addEventListener("click", () => send("NM_SMS_LOAD_NUMBERS", {
  provider: elements.smsProviderSelect.value,
  country: elements.smsCountryInput.value.trim()
}));
elements.smsNumberSelect.addEventListener("change", () => send("NM_SMS_SELECT_NUMBER", {
  phone: elements.smsNumberSelect.value,
  provider: elements.smsProviderSelect.value
}));
elements.refreshSmsMessagesBtn.addEventListener("click", () => send("NM_SMS_REFRESH_MESSAGES", {
  phone: elements.smsNumberSelect.value,
  provider: elements.smsProviderSelect.value
}));
elements.copySmsNumberBtn.addEventListener("click", () => {
  copyTextToClipboard(elements.smsNumberSelect.value, elements.copySmsNumberBtn, "已复制");
});
elements.copySmsCodeBtn.addEventListener("click", () => {
  const text = (elements.smsCodeValue.textContent || "").replace(/^验证码：/, "").trim();
  if (text && text !== "无") copyTextToClipboard(text, elements.copySmsCodeBtn, "已复制");
});
elements.clearBtn.addEventListener("click", () => send("NM_CLEAR_LOGS"));
elements.copyLogsBtn.addEventListener("click", () => copyTextToClipboard(elements.logsText.value || "", elements.copyLogsBtn, "已复制"));
elements.focusBtn.addEventListener("click", () => send("NM_FOCUS_ACTIVE_STEP"));
elements.scanBtn.addEventListener("click", () => send("NM_SCAN_ACTIVE_TAB"));
elements.continueBtn.addEventListener("click", () => {
  // 每次点"开始注册"都清空手动输入框，确保生成全新随机账号
  elements.manualEmailInput.value = "";
  elements.manualPasswordInput.value = "";
  elements.manualClientIdInput.value = "";
  elements.manualRefreshTokenInput.value = "";

  const registrationCount = Math.max(1, parseInt(elements.registrationCountInput.value, 10) || 1);
  elements.registrationCountInput.value = registrationCount;
  elements.registrationProgressValue.textContent = `0/${registrationCount}`;

  const manualAccount = null; // 始终为null，让background端生成新账号
  elements.credStatusValue.textContent = "正在等待页面 ACK";
  elements.credInfoValue.textContent = "将打开注册页并自动生成账号";
  send("NM_START_AUTOPILOT", { manualAccount, provider: elements.providerSelect.value, registrationCount });
});
elements.resumeBtn.addEventListener("click", () => {
  elements.credStatusValue.textContent = "正在继续执行";
  send("NM_RESUME_AUTOPILOT");
});
elements.stopBtn.addEventListener("click", () => send("NM_STOP_AUTOPILOT"));
elements.saveCredDirBtn.addEventListener("click", () => {
  const outputDir = elements.credentialDirInput.value.trim();
  try {
    chrome.storage.local.set({ [CREDENTIAL_OUTPUT_DIR_STORAGE_KEY]: outputDir });
  } catch (_) {
    // Ignore extension reload races.
  }
  send("NM_SET_CREDENTIAL_OUTPUT_DIR", { outputDir });
});
elements.saveWebUiBaseUrlBtn.addEventListener("click", () => {
  const webUiBaseUrl = elements.webUiBaseUrlInput.value.trim();
  try {
    chrome.storage.local.set({ [WEB_UI_BASE_URL_STORAGE_KEY]: webUiBaseUrl });
  } catch (_) {
    // Ignore extension reload races.
  }
  send("NM_SET_WEB_UI_BASE_URL", { webUiBaseUrl });
});
elements.openBackendBtn.addEventListener("click", () => send("NM_OPEN_WEB_UI"));
elements.checkBackendBtn.addEventListener("click", () => send("NM_CHECK_WEB_UI_HEALTH"));
elements.openWebUiBtn.addEventListener("click", () => send("NM_OPEN_WEB_UI"));
elements.exportThreeCredBtn.addEventListener("click", () => {
  elements.credStatusValue.textContent = "正在导出";
  send("NM_EXPORT_THREE_CREDENTIALS", {
    reason: "sidepanel_three_button",
    manualAccount: manualAccountFromInputs(true),
    outputDir: elements.credentialDirInput.value.trim()
  });
});
elements.exportCredBtn.addEventListener("click", () => {
  elements.credStatusValue.textContent = "正在发送";
  send("NM_EXPORT_CREDENTIALS", {
    reason: "sidepanel_button",
    manualAccount: manualAccountFromInputs(true),
    outputDir: elements.credentialDirInput.value.trim()
  });
});
elements.exportFourCredBtn.addEventListener("click", () => {
  send("NM_EXPORT_CREDENTIALS_TO_DIR", {
    reason: "sidepanel_four_button",
    manualAccount: manualAccountFromInputs(true),
    outputDir: elements.credentialDirInput.value.trim() || DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR
  });
});
elements.validateCredBtn.addEventListener("click", () => {
  elements.credStatusValue.textContent = "正在校验";
  send("NM_VALIDATE_CREDENTIALS", {
    outputDir: elements.credentialDirInput.value.trim(),
    email: elements.manualEmailInput.value.trim()
  });
});
elements.refreshCredBtn.addEventListener("click", () => send("NM_GET_STATE"));
elements.copyFourCredBtn.addEventListener("click", () => {
  const manual = manualAccountFromInputs(true);
  const text = fourCredentialText(manual) || fourCredentialText(uiState.latest?.lastCreatedAccount || uiState.latest?.activeAccount || {});
  copyTextToClipboard(text, elements.copyFourCredBtn, "已复制");
});
elements.openCredentialDirBtn.addEventListener("click", () => {
  send("NM_EXPORT_CREDENTIALS_TO_DIR", {
    reason: "sidepanel_open_dir_button",
    manualAccount: manualAccountFromInputs(true),
    outputDir: elements.credentialDirInput.value.trim() || DEFAULT_BROWSER_DOWNLOAD_OUTPUT_DIR
  });
});
elements.recoverLoginBtn.addEventListener("click", () => {
  send("NM_RUN_MANUAL_STEP", { stepId: "open_signup" });
});
elements.logModeSummaryBtn.addEventListener("click", () => {
  uiState.logMode = LOG_MODE.summary;
  render(uiState.latest || {});
});
elements.logModeRawBtn.addEventListener("click", () => {
  uiState.logMode = LOG_MODE.raw;
  render(uiState.latest || {});
});
elements.stepsList.addEventListener("click", (event) => {
  const target = event.target;
  if (!target || !target.matches || !target.matches(".step-run-btn")) return;
  send("NM_RUN_MANUAL_STEP", { stepId: target.dataset.stepId || "", manualAccount: manualAccountFromInputs(true) });
});
document.querySelectorAll("[data-copy-input]").forEach((button) => {
  button.addEventListener("click", () => {
    const inputId = button.getAttribute("data-copy-input") || "";
    const input = document.getElementById(inputId);
    if (input) copyTextToClipboard(input.value || "", button, "已复制");
  });
});

// ── 代理管理功能 ──

function proxySetResult(text, type = "") {
  const el = elements.proxyResultValue;
  el.textContent = text;
  el.className = "proxy-result" + (type ? ` ${type}` : "");
}

function proxyUpdateCount() {
  const text = elements.proxyTextarea.value || "";
  const lines = text.split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
  elements.proxyCountValue.textContent = String(lines.length);
}

function proxyNormalize(text) {
  return (text || "")
    .split("\n")
    .map(l => l.trim())
    .filter(l => l && !l.startsWith("#"))
    .map(l => convertIpwebFormat(l))
    .filter(l => l)
    .join("\n");
}

/**
 * IPWEB 等代理商格式智能转换
 * 支持:
 *   host:port:user:pass → http://user:pass@host:port
 *   user:pass@host:port  → 原样返回
 *   http://...           → 原样返回
 *   socks5://...         → 原样返回
 */
function convertIpwebFormat(line) {
  if (!line) return "";
  // 已经是 URL 格式
  if (/^(https?|socks[45]?)?:\/\//i.test(line)) return line;
  // 已有 @ 认证
  if (line.includes("@") && line.includes(":")) return line;
  // 检查是否是 host:port:user:pass 格式（4 段，第 3 段非纯数字）
  const parts = line.split(":");
  if (parts.length === 4) {
    const port = parseInt(parts[1], 10);
    const maybeUser = parts[2].trim();
    const maybePass = parts[3].trim();
    if (port >= 1 && port <= 65535 && maybeUser && !/^\d+$/.test(maybeUser)) {
      return `http://${maybeUser}:${maybePass}@${parts[0].trim()}:${parts[1].trim()}`;
    }
  }
  // 普通 host:port 格式
  if (parts.length === 2) {
    const port = parseInt(parts[1], 10);
    if (port >= 1 && port <= 65535) return `http://${parts[0].trim()}:${parts[1].trim()}`;
  }
  return line;
}

// ── 可用代理卡片渲染 ──
function proxyCardRender(proxies, currentProxy) {
  const list = elements.proxyCardList;
  const items = elements.proxyCardItems;
  const count = elements.proxyCardCount;
  if (!list || !items) return;
  if (!proxies || !proxies.length) {
    list.style.display = "none";
    return;
  }
  list.style.display = "";
  count.textContent = String(proxies.length);
  items.innerHTML = "";
  for (const url of proxies) {
    const chip = document.createElement("div");
    const isActive = url === currentProxy;
    chip.className = "proxy-chip" + (isActive ? " active" : "");
    // 当前使用标记
    if (isActive) {
      const badge = document.createElement("span");
      badge.className = "proxy-chip-badge";
      badge.textContent = "●";
      badge.title = "当前使用";
      chip.appendChild(badge);
    }
    // 显示标签
    const lbl = document.createElement("span");
    lbl.className = "proxy-chip-label";
    let label = url;
    try { const u = new URL(url); label = u.hostname + ":" + u.port; } catch (_) {}
    lbl.textContent = label;
    lbl.title = url;
    chip.appendChild(lbl);
    // 删除按钮
    const del = document.createElement("span");
    del.className = "proxy-chip-del";
    del.textContent = "×";
    del.onclick = (e) => {
      e.stopPropagation();
      proxyRemoveFromTextarea(url);
    };
    chip.appendChild(del);
    items.appendChild(chip);
  }
}

// 从 textarea 实时删除一个代理
function proxyRemoveFromTextarea(url) {
  const text = elements.proxyTextarea.value || "";
  const lines = text.split("\n").map(l => l.trim()).filter(l => l && l !== url);
  elements.proxyTextarea.value = lines.join("\n");
  proxyUpdateCount();
  // 同步删除到 background 的代理引擎
  send("NM_PROXY_REMOVE", { url });
}

// 检测中实时删除不可用代理
function proxyRealtimeRemove(url) {
  const text = elements.proxyTextarea.value || "";
  const lines = text.split("\n").map(l => l.trim()).filter(l => l && l !== url);
  elements.proxyTextarea.value = lines.join("\n");
  proxyUpdateCount();
}

// 导入文件
elements.proxyImportFileBtn.addEventListener("click", () => {
  elements.proxyFileInput.click();
});

elements.proxyFileInput.addEventListener("change", (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target && e.target.result ? String(e.target.result) : "";
    const normalized = proxyNormalize(text);
    if (normalized) {
      const existing = elements.proxyTextarea.value.trim();
      elements.proxyTextarea.value = existing ? existing + "\n" + normalized : normalized;
      proxyUpdateCount();
      proxySetResult(`✅ 已导入 ${normalized.split("\n").length} 个代理 (${file.name})`, "ok");
    } else {
      proxySetResult("⚠ 文件为空或格式不正确", "error");
    }
  };
  reader.onerror = () => proxySetResult("❌ 读取文件失败", "error");
  reader.readAsText(file);
  event.target.value = "";
});

// 粘贴代理
elements.proxyPasteBtn.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    const normalized = proxyNormalize(text);
    if (normalized) {
      const existing = elements.proxyTextarea.value.trim();
      elements.proxyTextarea.value = existing ? existing + "\n" + normalized : normalized;
      proxyUpdateCount();
      proxySetResult(`✅ 已粘贴 ${normalized.split("\n").length} 个代理`, "ok");
    } else {
      proxySetResult("⚠ 剪贴板为空或格式不正确", "error");
    }
  } catch (_) {
    proxySetResult("❌ 读取剪贴板失败，请手动粘贴到文本框", "error");
  }
});

// 从后端加载
elements.proxyLoadBtn.addEventListener("click", () => {
  proxySetResult("正在加载...", "loading");
  send("NM_PROXY_LOAD");
});

// 保存到后端
elements.proxySaveBtn.addEventListener("click", () => {
  const text = proxyNormalize(elements.proxyTextarea.value);
  if (!text) {
    proxySetResult("⚠ 代理列表为空", "error");
    return;
  }
  proxySetResult("正在检测并保存...", "loading");
  send("NM_PROXY_SAVE", { proxyText: text });
});

// 检测代理（PAC 并发 + 标签页精确验证，自动剔除不可用）
elements.proxyCheckBtn.addEventListener("click", () => {
  const text = proxyNormalize(elements.proxyTextarea.value);
  if (!text) {
    proxySetResult("⚠ 代理列表为空", "error");
    return;
  }
  const rawLimit = parseInt(elements.proxyCheckLimitInput.value, 10);
  const checkLimit = Number.isFinite(rawLimit) && rawLimit >= 1 ? Math.min(rawLimit, 500) : 20;
  elements.proxyCheckLimitInput.value = checkLimit;
  const lines = text.split("\n").filter(l => l.trim());
  const n = Math.min(lines.length, checkLimit);
  proxySetResult(`正在检测 ${n} 个代理（10 并发 + 精确验证）...`, "loading");
  send("NM_PROXY_CHECK", { proxyText: text, checkLimit });
});

// 清空列表
elements.proxyClearBtn.addEventListener("click", () => {
  elements.proxyTextarea.value = "";
  proxyUpdateCount();
  proxySetResult("已清空", "");
});

// textarea 输入时更新计数
elements.proxyTextarea.addEventListener("input", proxyUpdateCount);

// 自动代理开关
elements.proxyAutoCheckbox.addEventListener("change", () => {
  const enabled = elements.proxyAutoCheckbox.checked;
  send("NM_PROXY_TOGGLE", { enabled });
  proxySetResult(enabled ? "正在启用轮询引擎..." : "正在禁用轮询引擎...", "loading");
});

// 处理代理相关的 background 回复
function handleProxyResponse(message) {
  if (!message) return false;
  const type = message.type;
  const data = message.payload || message;

  if (type === "NM_PROXY_LOAD_RESULT") {
    if (data.ok) {
      elements.proxyTextarea.value = data.proxy_text || (data.proxies || []).join("\n");
      elements.proxyCountValue.textContent = String(data.count || 0);
      elements.proxyStableCountValue.textContent = String(data.stable_count || 0);
      if (data.auto_proxy != null) elements.proxyAutoCheckbox.checked = !!data.auto_proxy;
      elements.proxyStatusValue.textContent = `${data.count || 0} 个代理`;
      proxySetResult(`✅ 已加载 ${data.count || 0} 个代理（all=${data.all_count || 0} stable=${data.stable_count || 0}）`, "ok");
    } else {
      proxySetResult(`❌ 加载失败: ${data.reason || "未知错误"}`, "error");
    }
    return true;
  }

  if (type === "NM_PROXY_SAVE_RESULT") {
    if (data.ok) {
      // ★ 用合并后的实际代理列表更新 textarea
      if (data.proxies && data.proxies.length) {
        elements.proxyTextarea.value = data.proxies.join("\n");
      } else if (data.proxy_text) {
        elements.proxyTextarea.value = data.proxy_text;
      }
      elements.proxyCountValue.textContent = String(data.count || 0);
      elements.proxyStatusValue.textContent = `${data.count || 0} 个代理`;
      proxyCardRender(data.proxies || [], null);
      // ★ 显示标准化 + 合并详情
      let resultMsg = data.reason || `✅ ${data.count || 0} 个代理已保存`;
      proxySetResult(resultMsg, data.invalid > 0 ? "warn" : "ok");
    } else {
      proxySetResult(data.reason || "❌ 保存失败", "error");
    }
    return true;
  }

  if (type === "NM_PROXY_CHECK_PROGRESS") {
    const { completed, total, working, failed, current, failedUrl, workingProxies } = data;
    if (failedUrl) proxyRealtimeRemove(failedUrl);
    // 实时更新可用代理卡片
    if (workingProxies && workingProxies.length) proxyCardRender(workingProxies, null);
    proxySetResult(`检测中: ${completed}/${total} (✅${working} ❌${failed}) ${current || ""}`, "loading");
    return true;
  }

  if (type === "NM_PROXY_CHECK_RESULT") {
    if (data.ok) {
      if (data.proxy_text) {
        elements.proxyTextarea.value = data.proxy_text;
      }
      proxyUpdateCount();
      const working = data.count || 0;
      const total = data.total || working;
      const failed = data.failed_count || (total - working);
      const skipped = data.skipped || 0;
      elements.proxyStableCountValue.textContent = String(working);
      // 更新代理卡片
      proxyCardRender(data.proxies || [], null);
      const skippedMsg = skipped > 0 ? `（${skipped} 个未检测已丢弃）` : "";
      proxySetResult(
        data.reason || `✅ ${working}/${total} 个代理可用` + (failed > 0 ? `（${failed} 个已剔除）` : "") + skippedMsg,
        working > 0 ? "ok" : "error"
      );
    } else {
      proxySetResult(data.reason || "❌ 检测失败", "error");
    }
    return true;
  }

  return false;
}

// 监听 background 主动推送的状态更新
chrome.runtime.onMessage.addListener((message) => {
  if (!message) return;
  if (message.type === "NM_STATE_UPDATED" && message.payload) {
    console.log("[sidepanel] NM_STATE_UPDATED proxyEngine:", JSON.stringify(message.payload.proxyEngine));
    render(message.payload);
  }
  handleProxyResponse(message);
});

send("NM_GET_STATE");
