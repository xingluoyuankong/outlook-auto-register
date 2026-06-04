import json
import re
from pathlib import Path

from ..browser_extension import (
    DEFAULT_NINJEMAIL_EXTENSION_PATH,
    PROJECT_ROOT,
    build_ninjemail_extension_paths,
    check_ninjemail_extension,
    resolve_ninjemail_extension_dir,
)


REQUESTED_PROVIDER_FIXTURE_ORDER = [
    "proton",
    "gmx",
    "aol",
    "zoho",
    "yandex",
    "mailcom",
    "icloud",
    "mailru",
    "naver",
    "kakao",
    "netease163",
    "netease126",
    "neteaseyeah",
    "qq",
    "sina",
    "sohu",
    "tutanota",
]


def provider_fixture_source():
    return (Path(PROJECT_ROOT) / "tools" / "provider_flow_fixture_test.js").read_text(encoding="utf-8")


def extension_harness_source():
    return (Path(PROJECT_ROOT) / "tools" / "extension_load_ack_harness.js").read_text(encoding="utf-8")


def live_runner_source():
    return (Path(PROJECT_ROOT) / "tools" / "provider_live_plugin_runner.js").read_text(encoding="utf-8")


def test_default_ninjemail_extension_is_valid():
    result = check_ninjemail_extension()
    assert result.ok, result.reason
    assert result.path == str(DEFAULT_NINJEMAIL_EXTENSION_PATH.resolve())
    assert result.manifest_version == 3
    assert result.details["has_background"] is True
    assert result.details["has_side_panel"] is True
    assert result.details["content_script_count"] >= 1


def test_check_ninjemail_extension_rejects_missing_manifest(tmp_path):
    result = check_ninjemail_extension(tmp_path)
    assert not result.ok
    assert result.reason == "manifest_json_missing"


def test_project_root_resolves_to_internal_browser_extension():
    assert resolve_ninjemail_extension_dir(PROJECT_ROOT) == DEFAULT_NINJEMAIL_EXTENSION_PATH.resolve()


def test_check_ninjemail_extension_rejects_non_ninjemail_name(tmp_path):
    manifest = {
        "manifest_version": 3,
        "name": "Other Extension",
        "version": "1.0.0",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = check_ninjemail_extension(tmp_path)
    assert not result.ok
    assert result.reason == "ninjemail_extension_name_required"


def test_build_ninjemail_extension_paths_disabled():
    assert build_ninjemail_extension_paths(False) == []


def test_manifest_json_is_parseable():
    manifest_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["manifest_version"] == 3


def test_outlook_step_registry_contains_expected_order():
    shared_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "shared" / "flow-state.js"
    content = shared_path.read_text(encoding="utf-8")
    outlook_section = content.split("const OUTLOOK_STEPS", 1)[1].split("function baseStep", 1)[0]
    step_ids = re.findall(r'id: "([^"]+)"', outlook_section)
    assert step_ids == [
        "plugin_ready",
        "open_signup",
        "fill_username",
        "fill_password",
        "fill_profile",
        "fill_birthdate",
        "challenge",
        "post_challenge",
        "final_state",
        "export_credentials",
    ]


def test_content_script_reports_rich_step_payload():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    content = content_path.read_text(encoding="utf-8")
    for token in [
        "activeStep",
        "rootCause",
        "finalState",
        "NM_STEP_ACTION",
        "clickSafeContinue",
        "focus_active",
        "observedSteps",
        "maybeAutoContinue",
        "auto_click_continue",
        "fillCurrentStep",
        "auto_run",
        "ensureAutoPilotStarted",
        "generatedLocalAccount",
        "switchToNewEmailIfNeeded",
        "auto_start",
        "humanClick",
        "jitter",
        "selectCustomOption",
        "ensureBirthYear",
        "lastControlAction",
    ]:
        assert token in content


def test_content_script_uses_strict_challenge_and_step_precedence():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    content = content_path.read_text(encoding="utf-8")
    assert "includeFrameSources: !isTopFrame" in content
    assert "includeFrameSources: false" in content
    assert "个人数据导出许可" in content
    assert "strongPrivacyText" in content
    assert content.index('if (elements.username) return "fill_username";') < content.index('if (challenge) return "challenge";')


def test_background_does_not_block_on_child_challenge_when_top_is_actionable():
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content = background_path.read_text(encoding="utf-8")
    assert "isActionableTopReport" in content
    assert "发现挑战 frame，但主页面可继续" in content
    assert "子 frame 检测到挑战，但主页面可继续" in content
    assert 'state.challengeFrames.some((item) => item.blocking)' in content
    assert "NM_START_AUTOPILOT" in content
    assert "generatedOutlookAccount" in content


def test_sidepanel_treats_passive_challenges_as_auxiliary():
    sidepanel_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "sidepanel" / "sidepanel.js"
    content = sidepanel_path.read_text(encoding="utf-8")
    assert "blockingChallenges" in content
    assert "附属观察，不阻塞" in content
    assert "查看阻塞挑战详情" in content

    css_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "sidepanel" / "sidepanel.css"
    css = css_path.read_text(encoding="utf-8")
    assert ".challenge-row.passive" in css


def test_sidepanel_has_step_action_buttons():
    sidepanel_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "sidepanel" / "sidepanel.html"
    content = sidepanel_path.read_text(encoding="utf-8")
    assert 'id="focusBtn"' in content
    assert 'id="continueBtn"' in content
    assert 'id="resumeBtn"' in content
    assert 'id="providerSelect"' in content
    assert 'value="outlook"' in content
    assert 'value="hotmail"' in content
    assert 'value="gmail"' in content
    assert 'value="yahoo"' in content
    assert 'id="openRegisterBtn"' not in content
    assert "开始注册" in content
    assert "继续执行" in content
    assert 'id="stopBtn"' in content
    assert "停止执行" in content
    assert 'id="activeStepValue"' in content
    assert 'id="copyLogsBtn"' in content
    assert 'id="logsText"' in content
    assert 'id="credentialDirInput"' in content
    assert 'id="manualEmailInput"' in content
    assert 'id="manualPasswordInput"' in content
    assert 'id="manualClientIdInput"' in content
    assert 'id="manualRefreshTokenInput"' in content
    assert 'data-copy-input="manualEmailInput"' in content
    assert 'data-copy-input="manualRefreshTokenInput"' in content
    assert 'id="exportCredBtn"' in content
    assert 'id="saveCredDirBtn"' in content
    assert 'id="manualPasswordInput" type="text"' in content


def test_extension_stop_button_wires_to_content_script():
    sidepanel_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "sidepanel" / "sidepanel.js"
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    sidepanel = sidepanel_path.read_text(encoding="utf-8")
    background = background_path.read_text(encoding="utf-8")
    content = content_path.read_text(encoding="utf-8")
    assert "NM_STOP_AUTOPILOT" in sidepanel
    assert "NM_STOP_AUTOPILOT" in background
    assert "stop_auto" in background
    assert "stopAutoPilot" in content
    assert "clearPendingTimers" in content
    assert "自动执行已停止" in content
    assert 'stopped: "已停止"' in background
    assert "NM_RESUME_AUTOPILOT" in sidepanel
    assert "NM_RESUME_AUTOPILOT" in background
    assert "resumeAutopilot" in background
    assert "autopilot_stopped" in background
    assert "页面操作被锁定" in background
    assert "stopGeneration" in content
    assert "typingSignature = \"\"" in content
    assert "abortBackgroundOperations" in background
    assert "background_operation_stopped" in background


def test_start_registration_uses_manual_account_when_provided_and_generates_when_blank():
    sidepanel_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "sidepanel" / "sidepanel.js"
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    sidepanel = sidepanel_path.read_text(encoding="utf-8")
    background = background_path.read_text(encoding="utf-8")

    assert "manualAccountFromInputs(false)" in sidepanel
    assert "manualAccountFromInputs(true)" in sidepanel
    assert "startAutopilot(message.manualAccount" in background
    assert "normalizedManualAccount(manualAccount || {})" in background
    assert 'setActiveAccount(account, "start_autopilot_manual")' in background
    assert "generatedOutlookAccount(config.key)" in background
    assert "clearPreviousCredentialArtifacts" in background


def test_sidepanel_and_background_support_manual_step_and_credential_export():
    sidepanel_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "sidepanel" / "sidepanel.js"
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    sidepanel = sidepanel_path.read_text(encoding="utf-8")
    background = background_path.read_text(encoding="utf-8")
    content = content_path.read_text(encoding="utf-8")

    assert "NM_RUN_MANUAL_STEP" in sidepanel
    assert "NM_RUN_MANUAL_STEP" in background
    assert "runRequestedStep" in content
    assert 'message.action === "run_step"' in content
    assert "NM_SET_CREDENTIAL_OUTPUT_DIR" in sidepanel
    assert "NM_SET_CREDENTIAL_OUTPUT_DIR" in background
    assert "NM_EXPORT_CREDENTIALS" in sidepanel
    assert "NM_EXPORT_CREDENTIALS" in background
    assert "manualAccount" in sidepanel
    assert "manual_account_incomplete" in background
    assert "ninjemailGeneratedAccount" in background
    assert "当前注册账号已锁定" in background
    assert "{ frameId: 0 }" in background
    assert "sendResponse(response)" in content
    assert "ninjemail_account_created" in background
    assert "stableDelayMs: 8000" in content
    assert "applyCredentialStep" in background
    assert "ensureCredentialStep" in sidepanel
    assert 'id === "final_state" || id === "export_credentials"' in background
    assert "missing_cached_account_and_page_unavailable" in background
    assert "获取四凭证" in background
    assert "export_credentials" in content


def test_extension_supports_credential_validation_and_auxiliary_mailboxes():
    extension_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH)
    background = (extension_path / "background" / "background.js").read_text(encoding="utf-8")
    sidepanel_html = (extension_path / "sidepanel" / "sidepanel.html").read_text(encoding="utf-8")
    sidepanel_js = (extension_path / "sidepanel" / "sidepanel.js").read_text(encoding="utf-8")
    content = (extension_path / "content" / "outlook-signup.js").read_text(encoding="utf-8")
    web_ui = (Path(PROJECT_ROOT) / "web_ui.py").read_text(encoding="utf-8")

    assert 'id="webUiBaseUrlInput"' in sidepanel_html
    assert 'id="webUiHealthValue"' in sidepanel_html
    assert 'id="saveWebUiBaseUrlBtn"' in sidepanel_html
    assert 'id="openBackendBtn"' in sidepanel_html
    assert 'id="checkBackendBtn"' in sidepanel_html
    assert 'id="validateCredBtn"' in sidepanel_html
    assert 'id="exportThreeCredBtn"' in sidepanel_html
    assert 'id="exportFourCredBtn"' in sidepanel_html
    assert "NM_SET_WEB_UI_BASE_URL" in sidepanel_js
    assert "NM_CHECK_WEB_UI_HEALTH" in sidepanel_js
    assert "openBackendBtn" in sidepanel_js
    assert "checkBackendBtn" in sidepanel_js
    assert "WEB_UI_BASE_URL_STORAGE_KEY" in sidepanel_js
    assert "NM_SET_WEB_UI_BASE_URL" in background
    assert "NM_CHECK_WEB_UI_HEALTH" in background
    assert "probeWebUiHealth" in background
    assert "effectiveWebUiBaseUrl" in background
    assert "webUiApiUrl" in background
    assert "NM_EXPORT_THREE_CREDENTIALS" in sidepanel_js
    assert "threeCredentialText" in sidepanel_js
    assert "四凭证:" in sidepanel_js
    assert "NM_EXPORT_THREE_CREDENTIALS" in background
    assert "NM_EXPORT_CREDENTIALS_TO_DIR" in background
    assert "exportCurrentAccountThreeCredentials" in background
    assert "ninjemail_export_three_credentials" in background
    assert "ninjemail_export_three_credentials" in web_ui
    assert "NM_VALIDATE_CREDENTIALS" in sidepanel_js
    assert "NM_VALIDATE_CREDENTIALS" in background
    assert "validateCredentialFiles" in background
    assert "ninjemail_validate_credentials" in background
    assert "ninjemail_validate_credentials" in web_ui

    assert "NM_AUXILIARY_MAILBOX_PICK" in background
    assert "NM_AUXILIARY_MAILBOX_CODE" in background
    assert "ninjemail_auxiliary_mailbox_pick" in background
    assert "ninjemail_auxiliary_mailbox_code" in background
    assert "ninjemail_auxiliary_mailbox_pick" in web_ui
    assert "ninjemail_auxiliary_mailbox_code" in web_ui

    for token in [
        "looksLikeAuxiliaryMailboxPrompt",
        "findAuxiliaryEmailInput",
        "findVerificationCodeInput",
        "maybeHandleAuxiliaryMailbox",
        "auxiliaryBusy",
        "auxiliaryLastActionSignature",
    ]:
        assert token in content

    scan_section = content.split("function scan(reason)", 1)[1].split("chrome.runtime.onMessage", 1)[0]
    assert scan_section.index("ensureAutoPilotStarted") < scan_section.index("maybeHandleAuxiliaryMailbox")
    assert scan_section.index("maybeHandleAuxiliaryMailbox") < scan_section.index("maybeAutoContinue")
    assert (extension_path / "邮箱凭证").is_dir()
    assert (extension_path / "辅助邮箱").is_dir()


def test_birthdate_flow_requires_year_month_and_day_before_next():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    content = content_path.read_text(encoding="utf-8")
    assert "出生年份，等待页面确认" in content
    assert "出生月份，等待页面确认" in content
    assert "出生日期，等待页面确认" in content
    assert "生日三项已填完整" in content
    birthdate_section = content.split('if (stepState.activeStep === "fill_birthdate")', 1)[1]
    assert birthdate_section.index("const yearState = ensureBirthYear") < birthdate_section.index('const monthState = selectCustomOption(month, "month"')
    assert birthdate_section.index('const monthState = selectCustomOption(month, "month"') < birthdate_section.index('const dayState = selectCustomOption(day, "day"')
    assert birthdate_section.index('const dayState = selectCustomOption(day, "day"') < birthdate_section.index("if (clickNextButton())")


def test_day_picker_does_not_accept_month_text_as_day():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    content = content_path.read_text(encoding="utf-8")
    assert "containsMonthMarker" in content
    assert 'if (kind === "day" && containsMonthMarker(text)) return false;' in content
    assert 'if (anchorNode?.getAttribute?.("aria-expanded") !== "true") return [];' in content
    assert "ensureHumanText" in content
    assert "正在逐字输入用户名" in content
    assert "正在逐字输入密码" in content


def test_birthdate_generation_is_random_adult_in_extension_and_background():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content = content_path.read_text(encoding="utf-8")
    background = background_path.read_text(encoding="utf-8")

    assert "function randomAdultBirthday" in content
    assert "function randomAdultBirthday" in background
    local_section = content.split("function generatedLocalAccount()", 1)[1].split("function ensureAutoPilotAccount", 1)[0]
    background_section = background.split("function generatedOutlookAccount", 1)[1].split("function nowIso", 1)[0]
    assert 'birthYear: "2000"' not in local_section
    assert 'birthDay: "1"' not in local_section
    assert 'birthYear: "2000"' not in background_section
    assert 'birthDay: "1"' not in background_section
    assert "const minAge = 19;" in content
    assert "const maxAge = 46;" in content


def test_name_generation_uses_random_name_pools_in_extension_and_background():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content = content_path.read_text(encoding="utf-8")
    background = background_path.read_text(encoding="utf-8")

    for source in [content, background]:
        assert "const FIRST_NAMES = [" in source
        assert "const LAST_NAMES = [" in source
        assert "function randomAccountName" in source
        assert "randomChoice(FIRST_NAMES)" in source
        assert "randomChoice(LAST_NAMES)" in source

    local_section = content.split("function generatedLocalAccount()", 1)[1].split("function accountConsoleSummary", 1)[0]
    background_section = background.split("function generatedOutlookAccount", 1)[1].split("function summarizeAccountForLog", 1)[0]
    assert 'firstName: "Alex"' not in local_section
    assert "lastName: `Lin" not in local_section
    assert 'firstName: "Alex"' not in background_section
    assert "lastName: `Lin" not in background_section
    assert 'account.firstName || "Alex"' not in content
    assert 'account.lastName || "Lin"' not in content


def test_account_generation_uses_crypto_randomness_in_extension_and_background():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content = content_path.read_text(encoding="utf-8")
    background = background_path.read_text(encoding="utf-8")

    for source in [content, background]:
        assert "function secureRandomInt" in source
        assert "secure_random_unavailable" in source
        assert "getRandomValues" in source
        assert "Math.random" not in source
        assert "Date.now().toString(36)" not in source


def test_post_challenge_terminal_states_do_not_auto_block():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content = content_path.read_text(encoding="utf-8")
    background = background_path.read_text(encoding="utf-8")

    actionable = content.split("const AUTO_ACTIONABLE_STEPS", 1)[1].split("const SAFE_AUTO_CONTINUE_STATES", 1)[0]
    assert '"post_challenge"' not in actionable
    assert "FINAL_POST_CHALLENGE_STATES" in content
    assert "notifyAccountCreated" in content
    assert "if (final) return \"final_state\";" in content
    assert content.index('if (final) return "final_state";') < content.index('if (postChallengeState) return "post_challenge";')
    assert 'href.includes("privacynotice.account.microsoft.com")' in content
    assert 'if (includesAny(pageText, ["stay signed in", "保持登录", "保持登录状态"])) return "";' in content
    assert "passkey_prompt" in content
    assert "login_live_success" in content
    assert "NM_ACCOUNT_CREATED" in content
    assert "NM_ACCOUNT_CREATED" in background
    assert "注册成功账号已保存" in background
    assert "CREDENTIAL_READY_FINAL_STATES" in content
    assert "CREDENTIAL_READY_FINAL_STATES" in background
    assert "maybeStartTokenExportFromFinalStatus" in background


def test_passkey_prompt_prefers_cancel_and_stay_signed_in_prefers_yes():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    content = content_path.read_text(encoding="utf-8")
    assert "priorityByState" in content
    assert "passkey_prompt" in content
    assert '"取消"' in content
    assert '"cancel"' in content
    assert 'stay_signed_in: ["是", "yes"' in content
    assert "native_passkey_dialog" in content
    assert "hardBlocker: true" in content
    assert "已后退退出通行密钥提示" not in content
    assert "SAFE_CONTINUE_CONTROL_SELECTOR" in content
    assert '"#idSIButton9"' in content
    assert '"#idBtn_Back"' in content
    assert '"[role=\'button\']"' in content
    assert "function controlMatchesToken" in content
    assert "humanClick(match)" in content


def test_post_challenge_is_not_treated_as_provider_blocker():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    content = content_path.read_text(encoding="utf-8")
    blocker_fn = content.split("function isGenericProviderBlockerStep", 1)[1].split("const GENERIC_ACTION_STEPS", 1)[0]

    assert 'if (stepId === "post_challenge" || stepId === "challenge") return false;' in blocker_fn
    assert 'if (stepId.endsWith("_challenge")) return true;' in blocker_fn


def test_microsoft_next_button_has_text_fallback():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    content = content_path.read_text(encoding="utf-8")

    assert "function microsoftPrimaryButton" in content
    assert 'const button = queryAny(FIELD_SELECTORS.submit) || microsoftPrimaryButton();' in content
    assert '"下一步"' in content
    assert '"next"' in content
    assert 'testId.includes("primary")' in content


def test_registration_autorun_is_explicit_and_tab_scoped():
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    background = background_path.read_text(encoding="utf-8")
    content = content_path.read_text(encoding="utf-8")

    assert "function shouldAutoStart" in content
    assert re.search(r"function shouldAutoStart\([^)]*\)\s*\{\s*return false;", content)
    assert "maybeResumeAutoRunForContent" in background
    assert "ninjemailAutoRunTabId" in background
    assert "tabId !== state.autoRunTabId" in background
    assert "clearAutoRunLease" in background
    assert "autoPilot.enabled = enabled;" not in content


def test_start_registration_waits_for_content_ack_and_returns_it_to_sidepanel():
    extension_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH)
    background = (extension_path / "background" / "background.js").read_text(encoding="utf-8")
    sidepanel = (extension_path / "sidepanel" / "sidepanel.js").read_text(encoding="utf-8")
    content = (extension_path / "content" / "outlook-signup.js").read_text(encoding="utf-8")

    assert "const START_ACK_TIMEOUT_MS = 8000;" in background
    assert "function sendAutoRunWithAck" in background
    assert 'type: "NM_STEP_ACTION"' in background
    assert 'action: "auto_run"' in background
    assert "expectAck: true" in background
    assert "{ frameId: 0 }" in background
    assert "content_ack_timeout" in background
    assert "start_autopilot_ack_timeout" in background
    assert "NM_START_AUTOPILOT_ACK" in background
    assert "startAutopilot(message.manualAccount" in background
    assert "function createTab" in background
    assert "await createTab(requestedConfig.url)" in background
    assert "open_registration_tab_failed" in background
    assert "START_CONTENT_READY_TIMEOUT_MS" in background
    assert "function waitForAutoRunAck" in background
    assert "页面探针尚未就绪，正在重试自动执行 ACK" in background
    assert ".then((ack)" in background
    assert "startAck: ack || state.startAck || null" in background
    assert "background_exception" in background

    assert "function renderStartAckStatus" in sidepanel
    assert 'type === "NM_START_AUTOPILOT"' in sidepanel
    assert "background_empty_response" in sidepanel
    assert "provider: elements.providerSelect.value" in sidepanel
    assert "openRegisterBtn" not in sidepanel
    assert "页面 ACK 已收到" in sidepanel
    assert "等待页面 ACK" in sidepanel
    assert "未收到页面 ACK" in sidepanel
    assert "后台未响应" in sidepanel

    assert 'ack: "NM_START_AUTOPILOT_ACK"' in content
    assert "provider: flowProvider()" in content
    assert "runId: message.runId || nextAccount.registrationRunId || \"\"" in content


def test_provider_runtime_state_is_reset_between_provider_runs():
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    background = background_path.read_text(encoding="utf-8")
    reset_section = background.split("function resetProviderRuntimeState", 1)[1].split("function generatedOutlookAccount", 1)[0]

    assert 'resetProviderRuntimeState("provider_switch")' in background
    assert 'resetProviderRuntimeState("start_autopilot")' in background
    for token in [
        "state.frameReports = {};",
        "state.challengeFrames = [];",
        "state.steps = [];",
        "state.stepHistory = {};",
        "state.blocker = null;",
        "state.rootCause = null;",
        'state.activeStep = "";',
        'state.postChallengeState = "";',
        'state.finalState = "";',
        "state.elements = {};",
        "state.startAck = null;",
    ]:
        assert token in reset_section


def test_outlook_oauth_flow_uses_live_pages_and_requires_refresh_token():
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    background = background_path.read_text(encoding="utf-8")
    content = content_path.read_text(encoding="utf-8")

    assert 'prompt: "login"' in background
    assert 'params.set("domain_hint", "consumers")' in background
    assert "ninjemailOAuthActiveAccount" in background
    assert "ninjemailOAuthActiveAccount" in content
    assert 'host.includes("login.live.com")' in content
    assert 'host.includes("account.live.com")' in content
    assert "已填写 OAuth 登录密码" in content
    assert "已接受 Microsoft Graph 授权" in content
    assert "scheduleOAuthRescan" in content
    assert "#idBtn_Accept" in content
    assert "Detected blocked Microsoft request page and returned to login flow" in content
    assert "missing_refresh_token" in background
    assert "四凭证完整输出" in background
    assert "accessToken" in background
    assert "credential_path" in background
    assert "start_token_export: false" in background
    assert "startTokenToolExport" not in background
    assert "scheduleTokenToolCredentialPoll" not in background
    assert "ninjemail_credential_status" in background
    assert "checkSavedCredentialViaWebUi" in background
    assert "persistRecoveredCredentialRecord" in background
    assert "recovered_saved_credential" in background
    assert "outlook-token-tool" not in background
    assert "chrome.tabs.create(createOptions" in background
    assert 'chrome.tabs.update(tabId, { url: "about:blank" }' in background
    assert "downloadCredentialFile(record)" in background
    assert "outputDirSupportsBrowserDownload" in background
    assert "checkLocalWriterAvailability" in background
    assert "local_writer_unreachable_for_absolute_output_dir" in background
    assert "Web UI 保存失败，正在回退到浏览器下载落盘四凭证" in background
    assert "OAuth 回调超时，正在重试授权页" in background
    assert "credentialPathMatchesEmail" in background
    assert "unexpected_credential_filename" in background
    assert "credentialDownloadFilenameFor(record)" in background
    assert "token_json_path" not in background
    assert "token_env_path" not in background
    assert "token_combo_path" not in background


def test_content_script_does_not_generate_second_account_during_autorun():
    content_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js"
    content = content_path.read_text(encoding="utf-8")
    assert "没有后台下发的当前账号，已拒绝在 content 端重新生成账号" in content
    assert "message.account || autoPilot.account || generatedLocalAccount()" not in content
    ensure_section = content.split("function ensureAutoPilotAccount()", 1)[1].split("function setProvider", 1)[0]
    assert "autoPilot.account = generatedLocalAccount()" not in ensure_section
    assert "ninjemail_clear_previous_credentials" in Path(DEFAULT_NINJEMAIL_EXTENSION_PATH.parent / "web_ui.py").read_text(encoding="utf-8")


def test_manifest_loads_shared_state_before_content_script():
    manifest_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scripts = manifest["content_scripts"][0]["js"]
    assert scripts.index("shared/flow-state.js") < scripts.index("content/outlook-signup.js")


def test_requested_mail_providers_are_registered_across_extension_surfaces():
    extension_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH)
    background = (extension_path / "background" / "background.js").read_text(encoding="utf-8")
    shared = (extension_path / "shared" / "flow-state.js").read_text(encoding="utf-8")
    sidepanel = (extension_path / "sidepanel" / "sidepanel.js").read_text(encoding="utf-8")
    content = (extension_path / "content" / "outlook-signup.js").read_text(encoding="utf-8")

    provider_keys = [
        "proton",
        "gmx",
        "aol",
        "zoho",
        "yandex",
        "mailcom",
        "icloud",
        "mailru",
        "naver",
        "kakao",
        "netease163",
        "netease126",
        "neteaseyeah",
        "qq",
        "sina",
        "sohu",
        "tutanota",
    ]
    for provider in provider_keys:
        assert re.search(rf"\b{provider}:\s*\{{", background), provider
        assert re.search(rf"\b{provider}:\s*[A-Z_]+_STEPS", shared), provider
        assert re.search(rf"\b{provider}:\s*\"", sidepanel), provider
        assert f'"{provider}"' in content, provider


def test_requested_mail_provider_manifest_hosts_are_loaded_for_permissions_and_content():
    manifest_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    host_permissions = set(manifest["host_permissions"])
    content_matches = set(manifest["content_scripts"][0]["matches"])
    expected_matches = [
        "https://account.proton.me/*",
        "https://signup.proton.me/*",
        "https://signup.gmx.com/*",
        "https://www.gmx.com/*",
        "https://login.aol.com/*",
        "https://signup.aol.com/*",
        "https://accounts.zoho.com/*",
        "https://mail.zoho.com/*",
        "https://www.zoho.com/*",
        "https://passport.yandex.com/*",
        "https://passport.yandex.ru/*",
        "https://service.mail.com/*",
        "https://appleid.apple.com/*",
        "https://account.mail.ru/*",
        "https://e.mail.ru/*",
        "https://nid.naver.com/*",
        "https://accounts.kakao.com/*",
        "http://reg.email.163.com/*",
        "https://reg.email.163.com/*",
        "https://mail.163.com/*",
        "https://mail.126.com/*",
        "https://mail.yeah.net/*",
        "https://ssl.zc.qq.com/*",
        "https://mail.qq.com/*",
        "https://mail.sina.com.cn/*",
        "https://mail.sohu.com/*",
        "https://app.tuta.com/*",
        "https://app.tutanota.com/*",
    ]
    for match in expected_matches:
        assert match in host_permissions
        assert match in content_matches


def test_generic_provider_blocker_steps_match_configured_flow_steps():
    extension_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH)
    content = (extension_path / "content" / "outlook-signup.js").read_text(encoding="utf-8")
    shared = (extension_path / "shared" / "flow-state.js").read_text(encoding="utf-8")

    expected_blockers = {
        "proton_email_otp": ("proton", "email_otp"),
        "gmx_imap_enablement": ("gmx", "imap_enablement"),
        "aol_phone": ("aol", "phone"),
        "zoho_phone_or_otp": ("zoho", "phone_or_otp"),
        "yandex_phone_or_captcha": ("yandex", "phone_or_captcha"),
        "yandex_imap_enablement": ("yandex", "imap_enablement"),
        "icloud_email_otp": ("icloud", "email_otp"),
        "mailru_phone_or_captcha": ("mailru", "phone_or_captcha"),
        "naver_phone_sms": ("naver", "phone_sms"),
        "kakao_phone_or_email_otp": ("kakao", "phone_or_email_otp"),
        "netease_sms_or_resume": ("netease", "sms_or_resume"),
        "netease_captcha": ("netease", "captcha"),
        "qq_phone_sms": ("qq", "phone_sms"),
        "qq_captcha": ("qq", "captcha"),
        "sina_phone_account": ("sina", "phone_account"),
        "sina_sms_code": ("sina", "sms_code"),
        "sina_captcha": ("sina", "captcha"),
        "sohu_phone_sms": ("sohu", "phone_sms"),
        "sohu_captcha": ("sohu", "captcha"),
        "tutanota_email_otp": ("tutanota", "email_otp"),
    }
    custom_provider_steps = {"proton", "gmx", "aol"}
    for step_id, (provider_key, field_name) in expected_blockers.items():
        assert f'"{step_id}"' in content, step_id
        if provider_key in custom_provider_steps:
            assert f'id: "{step_id}"' in shared, step_id
        else:
            assert f'providerSignupSteps("{provider_key}"' in shared, step_id
        assert f'"{field_name}"' in shared, step_id

    assert "function genericProviderChallengeStep" in content
    assert "function isGenericProviderBlockerStep" in content
    assert "isGenericProviderBlockerStep(activeStep)" in content
    assert "fillGenericGender(account, activeStep)" in content
    assert "activeStep === `fill_${prefix}_gender`" in content


def test_provider_fixture_includes_all_requested_provider_cases_in_order():
    source = provider_fixture_source()
    cases_section = source.split("const CASES = [", 1)[1].split("];", 1)[0]
    providers = re.findall(r'\bprovider:\s*"([^"]+)"', cases_section)
    assert providers == REQUESTED_PROVIDER_FIXTURE_ORDER


def test_provider_fixture_writes_extension_flow_run_reports():
    source = provider_fixture_source()
    assert 'const FIXTURE_RUNS_DIR = path.join(ROOT, "reports", "extension-flow-fixtures");' in source
    assert 'runType: "mocked_fixture"' in source
    assert "const runRoot = path.join(FIXTURE_RUNS_DIR, runStamp);" in source
    assert "summary.json" in source
    assert "summary.md" in source


def test_provider_fixture_names_required_provider_artifacts():
    source = provider_fixture_source()
    for artifact in [
        "run.json",
        "run.md",
        "steps.jsonl",
        "console.log",
        "screenshots",
        "blockers.json",
        "repair-notes.md",
    ]:
        assert f'"{artifact}"' in source, artifact
    assert "REQUIRED_PROVIDER_ARTIFACTS" in source
    assert "requiredProviderArtifacts" in source


def test_provider_fixture_validates_start_autopilot_ack():
    source = provider_fixture_source()
    assert "function startAutoRunAck" in source
    assert 'action: "auto_run"' in source
    assert 'ack === "NM_START_AUTOPILOT_ACK"' in source
    assert "expected NM_START_AUTOPILOT_ACK" in source
    assert "startButtonAckStatus" in source


def test_provider_fixture_keeps_netease_shared_host_flows_isolated():
    source = provider_fixture_source()
    content = (Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "content" / "outlook-signup.js").read_text(encoding="utf-8")
    background = (Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js").read_text(encoding="utf-8")

    for token in ["from=126mail", "from=yeah", "netease126", "neteaseyeah"]:
        assert token in source
        assert token in content or token in background


def test_extension_load_ack_harness_exists():
    harness_path = Path(PROJECT_ROOT) / "tools" / "extension_load_ack_harness.js"
    assert harness_path.exists()


def test_extension_load_ack_harness_loads_unpacked_extension():
    source = extension_harness_source()
    assert "--load-extension" in source
    assert "--disable-extensions-except" in source
    assert "launchPersistentContext" in source
    assert "EXTENSION_ROOT" in source


def test_extension_load_ack_harness_checks_background_worker_and_ack():
    source = extension_harness_source()
    assert "serviceWorkers()" in source
    assert "waitForExtensionWorker" in source
    assert "background/background.js" in source
    assert "chrome.runtime.sendMessage" in source
    assert "clickContinueInSidepanel" in source
    assert 'selectOption("#providerSelect", provider)' in source
    assert 'locator("#continueBtn")' in source
    assert "NM_START_AUTOPILOT_ACK" in source


def test_extension_load_ack_harness_writes_extension_flow_run_report():
    source = extension_harness_source()
    assert 'const ACK_RUNS_DIR = path.join(ROOT, "reports", "extension-load-ack");' in source
    assert 'runType: "mocked_ack"' in source
    assert '"run.json"' in source
    assert '"run.md"' in source
    assert '"console.log"' in source
    assert '"screenshots"' in source


def test_extension_load_ack_harness_uses_safe_mocked_provider_page():
    source = extension_harness_source()
    assert "safe mocked/local provider page" in source
    assert "no live account was created" in source
    assert "safeValidation" in source
    assert "verificationControlsNotAutomated" in source
    assert "mockProtonHtml" in source
    assert "context.route(PROTON_ROUTE" in source


def test_extension_load_ack_harness_has_no_verification_solver_language():
    source = extension_harness_source().lower()
    compact = re.sub(r"[^a-z0-9]+", "", source)
    for forbidden in [
        "solvecaptcha",
        "bypasscaptcha",
        "captchasolver",
        "captchasolverextension",
        "2captcha",
        "anticaptcha",
        "smscodegrabber",
        "smssolver",
        "otpsolver",
        "realnamebypass",
        "qrbypass",
    ]:
        assert forbidden not in compact


def test_live_plugin_runner_exists_and_uses_sidepanel_start_button():
    source = live_runner_source()
    assert 'const REPORT_ROOT = path.join(ROOT, "reports", "extension-flow-runs");' in source
    assert 'runType: "live_plugin_run"' in source
    assert 'selectOption("#providerSelect", provider)' in source
    assert 'locator("#continueBtn")' in source
    assert 'type: "NM_GET_STATE"' in source
    assert "waitForStartAck" in source
    assert "waitForTerminalState" in source
    assert "hard_blocker_recorded" in source


def test_live_probe_report_is_tagged():
    source = (Path(PROJECT_ROOT) / "tools" / "provider_real_signup_probe.js").read_text(encoding="utf-8")
    assert 'const REPORT_ROOT = path.join(ROOT, "reports", "provider-real-probes");' in source
    assert 'runType: "live_probe"' in source


def test_microsoft_problem_auto_retry_is_limited_and_visible():
    background_path = Path(DEFAULT_NINJEMAIL_EXTENSION_PATH) / "background" / "background.js"
    background = background_path.read_text(encoding="utf-8")
    assert "const MICROSOFT_PROBLEM_AUTO_RETRY_MAX = 1;" in background
    assert "function restartAfterMicrosoftProblem" in background
    assert "Microsoft 问题页自动重开已达上限，等待手动开始注册" in background
    assert "regenerate_required" in background
