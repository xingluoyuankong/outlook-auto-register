(function attachNinjemailFlow(root) {
  const OUTLOOK_STEPS = [
    {
      id: "plugin_ready",
      label: "插件连接",
      intent: "确认浏览器插件、页面探针和侧栏状态通道已连接。"
    },
    {
      id: "open_signup",
      label: "打开注册页",
      intent: "加载 Microsoft 注册页面，确认页面可控制。"
    },
    {
      id: "fill_username",
      label: "填写用户名",
      intent: "等待用户名/邮箱输入框，或确认用户名已进入下一步。"
    },
    {
      id: "fill_password",
      label: "填写密码",
      intent: "等待密码输入框和下一步按钮。"
    },
    {
      id: "fill_profile",
      label: "填写姓名",
      intent: "等待名字和姓氏输入框。"
    },
    {
      id: "fill_birthdate",
      label: "填写生日",
      intent: "等待国家、月份、日期、年份控件。"
    },
    {
      id: "challenge",
      label: "人机验证",
      intent: "识别人机验证页面，并给出证据和处理状态。"
    },
    {
      id: "post_challenge",
      label: "验证后页面",
      intent: "识别隐私许可、保持登录、恢复信息、账号跳转等页面。"
    },
    {
      id: "final_state",
      label: "最终状态",
      intent: "确认账号主页、成功提示，或给出剩余阻塞点。"
    },
    {
      id: "export_credentials",
      label: "获取四凭证",
      intent: "注册成功后获取并保存：账号----密码----客户端ID----刷新令牌。"
    }
  ];

  function baseStep(id, overrides = {}) {
    const base = OUTLOOK_STEPS.find((item) => item.id === id) || { id, label: id, intent: "" };
    return { ...base, ...overrides };
  }

  const GMAIL_STEPS = [
    baseStep("plugin_ready"),
    baseStep("open_signup", {
      label: "打开 Gmail 注册页",
      intent: "加载 Google/Gmail 注册页，确认页面可控。"
    }),
    {
      id: "fill_gmail_profile",
      label: "填写 Gmail 姓名",
      intent: "等待名字和姓氏输入框。"
    },
    {
      id: "fill_gmail_birthdate",
      label: "填写 Gmail 基本信息",
      intent: "等待生日和性别等 Google 账号资料控件。"
    },
    {
      id: "fill_gmail_username",
      label: "填写 Gmail 用户名",
      intent: "等待 Gmail 用户名输入框。"
    },
    {
      id: "fill_gmail_password",
      label: "填写 Gmail 密码",
      intent: "等待密码和确认密码输入框。"
    },
    baseStep("challenge"),
    baseStep("post_challenge", {
      label: "Gmail 验证后页面",
      intent: "识别手机号验证、恢复信息、安全提示或注册完成后的页面。"
    }),
    baseStep("final_state"),
    baseStep("export_credentials")
  ];

  const YAHOO_STEPS = [
    baseStep("plugin_ready"),
    baseStep("open_signup", {
      label: "打开 Yahoo 注册页",
      intent: "加载 Yahoo 注册页，确认页面可控。"
    }),
    {
      id: "fill_yahoo_account_form",
      label: "填写 Yahoo 必填表单",
      intent: "填写名字、姓氏、Yahoo 用户名、密码和出生日期，全部完整后再提交。"
    },
    baseStep("challenge"),
    baseStep("post_challenge", {
      label: "Yahoo 验证后页面",
      intent: "识别手机号验证、安全提示或注册完成后的页面。"
    }),
    baseStep("final_state"),
    baseStep("export_credentials")
  ];

  const HOTMAIL_STEPS = OUTLOOK_STEPS.map((step) => ({
    ...step,
    label: String(step.label || step.id).replace(/Outlook/gi, "Hotmail"),
    intent: `${step.intent || ""} Domain must stay hotmail.com.`
  }));

  function providerSignupSteps(providerKey, title, fields = []) {
    const normalFields = fields.length ? fields : ["name", "username", "password", "birthdate"];
    const blockingFields = new Set([
      "captcha",
      "email_otp",
      "imap_enablement",
      "phone",
      "phone_account",
      "phone_or_captcha",
      "phone_or_email_otp",
      "phone_or_otp",
      "phone_sms",
      "sms_code",
      "sms_or_resume"
    ]);
    return [
      baseStep("plugin_ready"),
      baseStep("open_signup", {
        label: `Open ${title} signup`,
        intent: `Load the ${title} registration page and keep this provider isolated from other mailbox flows.`
      }),
      ...normalFields.map((field) => {
        if (blockingFields.has(field)) {
          return {
            id: `${providerKey}_${field}`,
            label: `${title} ${field}`,
            intent: `Detect the ${title} ${field} blocker and stop without borrowing another provider's flow.`
          };
        }
        return {
          id: `fill_${providerKey}_${field}`,
          label: `Fill ${title} ${field}`,
          intent: `Fill the ${title} ${field} controls only when they are present on this provider page.`
        };
      }),
      {
        id: `${providerKey}_challenge`,
        label: `${title} challenge`,
        intent: "Detect captcha, SMS, phone, OTP, app-password, or provider-specific manual blockers without mixing another provider's flow."
      },
      baseStep("post_challenge", {
        label: `${title} post-check`,
        intent: `Handle only safe ${title} post-registration notices; stop at real verification challenges.`
      }),
      baseStep("final_state"),
      baseStep("export_credentials")
    ];
  }

  const PROTON_STEPS = [
    baseStep("plugin_ready"),
    baseStep("open_signup", {
      label: "Open Proton signup",
      intent: "Load Proton Mail signup and keep the Proton flow isolated."
    }),
    {
      id: "fill_proton_username",
      label: "Fill Proton username",
      intent: "Fill Proton username/email controls only when Proton exposes them."
    },
    {
      id: "fill_proton_password",
      label: "Fill Proton password",
      intent: "Fill Proton password controls only when they are present on the Proton page."
    },
    {
      id: "proton_captcha",
      label: "Proton captcha/challenge",
      intent: "Detect Proton embedded anti-abuse challenge and stop without bypassing it."
    },
    {
      id: "proton_email_otp",
      label: "Proton email OTP",
      intent: "Detect Proton email verification and stop for manual/adapter handling."
    },
    baseStep("post_challenge", {
      label: "Proton post-check",
      intent: "Handle only safe Proton notices after manual verification."
    }),
    baseStep("final_state"),
    baseStep("export_credentials")
  ];

  const GMX_STEPS = [
    baseStep("plugin_ready"),
    baseStep("open_signup", {
      label: "Open GMX signup",
      intent: "Load GMX signup and keep the GMX flow isolated."
    }),
    {
      id: "fill_gmx_profile_birthdate",
      label: "Fill GMX profile and birthdate",
      intent: "GMX first page combines first name, last name, and date of birth; fill them as one step before Next."
    },
    {
      id: "fill_gmx_username",
      label: "Fill GMX username",
      intent: "Fill the later GMX email address/username step only after the profile page advances."
    },
    {
      id: "fill_gmx_password",
      label: "Fill GMX password",
      intent: "Fill GMX password controls only on the GMX password page."
    },
    {
      id: "fill_gmx_recovery",
      label: "Fill GMX recovery",
      intent: "Fill optional GMX recovery email controls only when shown."
    },
    {
      id: "gmx_terms",
      label: "GMX terms gate",
      intent: "Detect GMX terms/consent gates and keep them in the GMX flow."
    },
    {
      id: "gmx_imap_enablement",
      label: "GMX IMAP/app password",
      intent: "Detect later GMX IMAP or app-password requirements and stop for manual settings."
    },
    {
      id: "gmx_challenge",
      label: "GMX challenge",
      intent: "Detect GMX captcha, SMS, OTP, or provider-specific blockers without mixing another provider's flow."
    },
    baseStep("post_challenge", {
      label: "GMX post-check",
      intent: "Handle only safe GMX post-registration notices; stop at real verification challenges."
    }),
    baseStep("final_state"),
    baseStep("export_credentials")
  ];

  const AOL_STEPS = [
    baseStep("plugin_ready"),
    baseStep("open_signup", {
      label: "Open AOL signup",
      intent: "Load AOL signup and keep the AOL flow isolated."
    }),
    {
      id: "fill_aol_account_form",
      label: "Fill AOL account form",
      intent: "AOL exposes first name, last name, username, password, and birthdate on one page; fill the whole AOL form before Next."
    },
    {
      id: "aol_phone",
      label: "AOL phone/SMS",
      intent: "Detect AOL phone or SMS verification and stop without bypassing it."
    },
    {
      id: "aol_challenge",
      label: "AOL challenge",
      intent: "Detect AOL captcha or provider-specific blockers without mixing another provider's flow."
    },
    baseStep("post_challenge", {
      label: "AOL post-check",
      intent: "Handle only safe AOL post-registration notices; stop at real verification challenges."
    }),
    baseStep("final_state"),
    baseStep("export_credentials")
  ];
  const ZOHO_STEPS = providerSignupSteps("zoho", "Zoho", ["name", "username", "password", "phone_or_otp"]);
  const YANDEX_STEPS = providerSignupSteps("yandex", "Yandex", ["name", "username", "password", "phone_or_captcha", "imap_enablement"]);
  const MAILCOM_STEPS = providerSignupSteps("mailcom", "Mail.com", ["name", "username", "password", "birthdate", "recovery"]);
  const ICLOUD_STEPS = providerSignupSteps("icloud", "iCloud", ["name", "birthdate", "username", "password", "email_otp"]);
  const MAILRU_STEPS = providerSignupSteps("mailru", "Mail.ru", ["name", "username", "password", "birthdate", "reserve_email", "phone_or_captcha"]);
  const NAVER_STEPS = providerSignupSteps("naver", "Naver", ["username", "password", "name", "birthdate", "gender", "phone_sms"]);
  const KAKAO_STEPS = providerSignupSteps("kakao", "Daum/Kakao", ["terms", "username", "password", "profile", "phone_or_email_otp"]);
  const NETEASE_STEPS = providerSignupSteps("netease", "NetEase mail", ["domain", "username", "password", "captcha", "sms_or_resume"]);
  const QQ_STEPS = providerSignupSteps("qq", "QQ Mail", ["username", "password", "phone_sms", "captcha"]);
  const SINA_STEPS = providerSignupSteps("sina", "Sina Mail", ["phone_account", "password", "sms_code", "captcha"]);
  const SOHU_STEPS = providerSignupSteps("sohu", "Sohu Mail", ["username", "password", "phone_sms", "captcha"]);
  const TUTANOTA_STEPS = providerSignupSteps("tutanota", "Tutanota", ["username", "password", "terms", "email_otp"]);

  const FLOW_STEPS_BY_PROVIDER = Object.freeze({
    outlook: OUTLOOK_STEPS,
    hotmail: HOTMAIL_STEPS,
    gmail: GMAIL_STEPS,
    yahoo: YAHOO_STEPS,
    proton: PROTON_STEPS,
    gmx: GMX_STEPS,
    aol: AOL_STEPS,
    zoho: ZOHO_STEPS,
    yandex: YANDEX_STEPS,
    mailcom: MAILCOM_STEPS,
    icloud: ICLOUD_STEPS,
    mailru: MAILRU_STEPS,
    naver: NAVER_STEPS,
    kakao: KAKAO_STEPS,
    netease163: NETEASE_STEPS,
    netease126: NETEASE_STEPS,
    neteaseyeah: NETEASE_STEPS,
    qq: QQ_STEPS,
    sina: SINA_STEPS,
    sohu: SOHU_STEPS,
    tutanota: TUTANOTA_STEPS
  });

  const CHALLENGE_PATTERNS = [
    {
      type: "hsprotect",
      label: "HUMAN hsprotect",
      action: "manual_required",
      tokens: ["hsprotect", "iframe.hsprotect.net", "fpt.live.com", "app_id=pxzc5j78di", "press and hold", "human challenge", "按住", "证明你不是机器人", "验证你不是机器人"]
    },
    {
      type: "arkose",
      label: "Arkose/FunCaptcha",
      action: "provider_or_manual_required",
      tokens: ["arkoselabs", "funcaptcha", "arkose", "game-core-frame", "enforcementframe", "fc-tokens", "证明你不是机器人", "验证你不是机器人", "are you a robot", "prove you are human", "你是机器人吗"]
    },
    {
      type: "recaptcha",
      label: "reCAPTCHA",
      action: "provider_or_manual_required",
      tokens: ["recaptcha", "g-recaptcha"]
    },
    {
      type: "hcaptcha",
      label: "hCaptcha",
      action: "provider_or_manual_required",
      tokens: ["hcaptcha"]
    },
    {
      type: "turnstile",
      label: "Turnstile",
      action: "provider_or_manual_required",
      tokens: ["turnstile", "cf-challenge"]
    },
    {
      type: "phone_sms",
      label: "Phone/SMS verification",
      action: "manual_or_sms_adapter_required",
      tokens: ["phone number", "mobile number", "sms", "text message", "verification code", "短信", "手机号码", "手机号", "验证码", "인증번호", "휴대폰"]
    },
    {
      type: "email_otp",
      label: "Email OTP verification",
      action: "manual_or_mail_adapter_required",
      tokens: ["email verification", "verification email", "one-time code", "otp", "check your email", "邮箱验证码", "邮件验证码"]
    },
    {
      type: "imap_enablement",
      label: "IMAP/POP enablement",
      action: "manual_settings_required",
      tokens: ["imap", "pop3", "app password", "application password", "客户端授权码", "授权码"]
    }
  ];

  const POST_CHALLENGE_STATES = [
    { id: "privacy_notice", label: "个人数据/隐私许可", tokens: ["个人数据导出许可", "Microsoft 隐私声明", "privacy notice", "同意并继续", "agree and continue"] },
    { id: "account_notice", label: "Microsoft 帐户说明", tokens: ["有关 Microsoft 帐户的快速说明", "有关 Microsoft 账户的快速说明", "quick note about your microsoft account", "确定", "ok"] },
    { id: "stay_signed_in", label: "保持登录", tokens: ["stay signed in", "保持登录"] },
    { id: "add_recovery", label: "添加恢复信息", tokens: ["add a recovery", "recovery", "恢复"] },
    { id: "passkey_prompt", label: "通行密钥/安全密钥", tokens: ["passkey", "security key", "windows hello", "通行密钥", "密钥"] },
    { id: "microsoft_problem", label: "Microsoft 问题页", tokens: ["我们遇到了问题", "请重试", "something went wrong", "try again"] },
    { id: "phone_verification", label: "手机验证", tokens: ["phone number", "text message", "sms", "手机号", "短信"] },
    { id: "login_live_success", label: "登录完成", tokens: ["res=success", "post.srf"] },
    { id: "oauth_complete", label: "OAuth 完成", tokens: ["complete-client-signin-oauth-silent", "complete-signin"] },
    { id: "account_home", tokens: ["account.microsoft.com", "account.live.com"] },
    { id: "login_live", tokens: ["login.live.com"] }
  ];

  const STATUS_LABELS = Object.freeze({
    idle: "待命",
    opening: "打开中",
    observing: "观察中",
    manual_wait: "等待人工",
    blocked: "已阻塞",
    post_challenge: "验证后处理",
    done: "完成",
    done_step: "已完成",
    current: "当前",
    pending: "未观察",
    seen: "已观察"
  });

  function providerFlowKey(provider) {
    const key = String(provider || "outlook").toLowerCase();
    return FLOW_STEPS_BY_PROVIDER[key] ? key : "outlook";
  }

  function stepsForProvider(provider) {
    return FLOW_STEPS_BY_PROVIDER[providerFlowKey(provider)] || OUTLOOK_STEPS;
  }

  function stepLabel(stepId, provider = "outlook") {
    const steps = stepsForProvider(provider);
    const step = steps.find((item) => item.id === stepId)
      || OUTLOOK_STEPS.find((item) => item.id === stepId)
      || GMAIL_STEPS.find((item) => item.id === stepId)
      || YAHOO_STEPS.find((item) => item.id === stepId);
    return step ? step.label : stepId;
  }

  root.NinjemailFlow = Object.freeze({
    OUTLOOK_STEPS,
    HOTMAIL_STEPS,
    GMAIL_STEPS,
    YAHOO_STEPS,
    PROTON_STEPS,
    GMX_STEPS,
    AOL_STEPS,
    ZOHO_STEPS,
    YANDEX_STEPS,
    MAILCOM_STEPS,
    ICLOUD_STEPS,
    MAILRU_STEPS,
    NAVER_STEPS,
    KAKAO_STEPS,
    NETEASE_STEPS,
    QQ_STEPS,
    SINA_STEPS,
    SOHU_STEPS,
    TUTANOTA_STEPS,
    FLOW_STEPS_BY_PROVIDER,
    CHALLENGE_PATTERNS,
    POST_CHALLENGE_STATES,
    STATUS_LABELS,
    providerFlowKey,
    stepsForProvider,
    stepLabel
  });
})(globalThis);
