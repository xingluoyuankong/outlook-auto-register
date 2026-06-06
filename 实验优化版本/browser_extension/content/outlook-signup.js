(function attachOutlookSignupObserver() {
  const NINJEMAIL_SIGNUP_SCRIPT_VERSION = "0.2.27";
  if (
    globalThis.__NINJEMAIL_SIGNUP_OBSERVER_ATTACHED
    && globalThis.__NINJEMAIL_SIGNUP_OBSERVER_ATTACHED !== NINJEMAIL_SIGNUP_SCRIPT_VERSION
    && typeof globalThis.__NINJEMAIL_SIGNUP_OBSERVER_CLEANUP === "function"
  ) {
    try {
      globalThis.__NINJEMAIL_SIGNUP_OBSERVER_CLEANUP();
    } catch (error) {
      // Best effort cleanup for an older injected content script instance.
    }
  }
  if (globalThis.__NINJEMAIL_SIGNUP_OBSERVER_ATTACHED === NINJEMAIL_SIGNUP_SCRIPT_VERSION) return;
  globalThis.__NINJEMAIL_SIGNUP_OBSERVER_ATTACHED = NINJEMAIL_SIGNUP_SCRIPT_VERSION;

  const flow = globalThis.NinjemailFlow || {};
  const isTopFrame = window.top === window;
  let lastSignature = "";
  let observer = null;
  let timer = null;
  let highlightNode = null;
  let lastAutoContinueSignature = "";
  const pendingTimers = new Set();
  let runtimeMessageListener = null;
  let storageChangeListener = null;
  let beforeUnloadListener = null;
  let autoPilot = {
    enabled: false,
    autoStarted: false,
    stopped: false,
    manualStopped: false,
    busy: false,
    stopGeneration: 0,
    lastStep: "",
    lastStepAt: 0,
    lastControlAction: "",
    lastControlActionAt: 0,
    submittedStepSignature: "",
    submittedStepAt: 0,
    typingSignature: "",
    accountSavedSignature: "",
    account: null,
    oauthEmail: "",
    oauthAccount: null,
    auxiliaryEmail: "",
    auxiliarySourcePath: "",
    auxiliaryBusy: false,
    auxiliaryRequestSignature: "",
    auxiliaryLastActionSignature: "",
    auxiliaryLastActionAt: 0,
    provider: "outlook",
    domain: "outlook.com"
  };

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

  function jitter(min = 260, max = 980) {
    return secureRandomInt(min, max);
  }

  function later(callback, delayMs = jitter()) {
    const generation = autoPilot.stopGeneration;
    const id = setTimeout(() => {
      pendingTimers.delete(id);
      if (!autoPilot.stopped && autoPilot.enabled && generation === autoPilot.stopGeneration) callback();
    }, delayMs);
    pendingTimers.add(id);
    return id;
  }

  function clearPendingTimers() {
    for (const id of pendingTimers) clearTimeout(id);
    pendingTimers.clear();
  }

  const PROVIDER_DOMAIN = {
    outlook: "outlook.com",
    hotmail: "hotmail.com",
    gmail: "gmail.com",
    yahoo: "yahoo.com",
    proton: "proton.me",
    gmx: "gmx.com",
    aol: "aol.com",
    zoho: "zohomail.com",
    yandex: "yandex.com",
    mailcom: "mail.com",
    icloud: "icloud.com",
    mailru: "mail.ru",
    naver: "naver.com",
    kakao: "daum.net",
    netease163: "163.com",
    netease126: "126.com",
    neteaseyeah: "yeah.net",
    qq: "qq.com",
    sina: "sina.com",
    sohu: "sohu.com",
    tutanota: "tutanota.com"
  };

  const PROVIDER_HOST_HINTS = {
    "account.proton.me": "proton",
    "signup.proton.me": "proton",
    "www.gmx.com": "gmx",
    "signup.gmx.com": "gmx",
    "login.aol.com": "aol",
    "signup.aol.com": "aol",
    "accounts.zoho.com": "zoho",
    "mail.zoho.com": "zoho",
    "passport.yandex.com": "yandex",
    "passport.yandex.ru": "yandex",
    "service.mail.com": "mailcom",
    "appleid.apple.com": "icloud",
    "account.mail.ru": "mailru",
    "e.mail.ru": "mailru",
    "nid.naver.com": "naver",
    "accounts.kakao.com": "kakao",
    "reg.email.163.com": "netease163",
    "mail.163.com": "netease163",
    "mail.126.com": "netease126",
    "mail.yeah.net": "neteaseyeah",
    "ssl.zc.qq.com": "qq",
    "mail.qq.com": "qq",
    "mail.sina.com.cn": "sina",
    "mail.sohu.com": "sohu",
    "app.tuta.com": "tutanota",
    "app.tutanota.com": "tutanota"
  };

  const FIELD_SELECTORS = {
    username: [
      "input[name='MemberName']",
      "input[name='Username']",
      "input[name='userId']",
      "#usernamereg-userId",
      "input[name='email']",
      "#usernameInput",
      "input[type='email']",
      "input[autocomplete='username']"
    ],
    password: [
      "input[name='Password']",
      "input[name='Passwd']",
      "input[name='PasswdAgain']",
      "input[name='password']",
      "#usernamereg-password",
      "#usernamereg-passwordConfirm",
      "#Password",
      "input[type='password']",
      "input[autocomplete='new-password']"
    ],
    profile: [
      "input[name='FirstName']",
      "input[name='firstName']",
      "#firstName",
      "#lastName",
      "#usernamereg-firstName",
      "#usernamereg-lastName",
      "#firstNameInput",
      "input[name='LastName']",
      "input[name='lastName']",
      "#lastNameInput"
    ],
    birthdate: [
      "select[name='BirthMonth']",
      "#BirthMonth",
      "#BirthDay",
      "#BirthYear",
      "input[aria-label*='Birth month' i]",
      "input[aria-label*='month' i]",
      "input[aria-label*='Birth day' i]",
      "input[aria-label*='day' i]",
      "input[aria-label*='月份']",
      "input[aria-label*='日期']",
      "input[aria-label*='日']",
      "#month",
      "#day",
      "#year",
      "#gender",
      "[aria-label*='Gender' i]",
      "[aria-label*='gender' i]",
      "[aria-label*='性别']",
      "#usernamereg-month",
      "#usernamereg-day",
      "#usernamereg-year",
      "select[name='BirthDay']",
      "input[name='BirthYear']"
    ],
    submit: [
      "#nextButton",
      "#reg-submit-button",
      "button[name='signup']",
      "button[jsname]",
      "button[type='submit']",
      "input[type='submit']",
      "button[data-testid='primaryButton']"
    ],
    phone: [
      "input[type='tel']",
      "input[name*='phone' i]",
      "input[id*='phone' i]"
    ]
  };

  const GMAIL_FIELD_SELECTORS = {
    firstName: [
      "#firstName",
      "input[name='firstName']",
      "input[autocomplete='given-name']",
      "input[aria-label*='First' i]",
      "input[aria-label*='名字']",
      "input[aria-label*='名']"
    ],
    lastName: [
      "#lastName",
      "input[name='lastName']",
      "input[autocomplete='family-name']",
      "input[aria-label*='Last' i]",
      "input[aria-label*='姓氏']",
      "input[aria-label*='姓']"
    ],
    username: [
      "#username",
      "input[name='Username']",
      "input[autocomplete='username']",
      "input[type='email']"
    ],
    password: [
      "input[name='Passwd']",
      "input[name='PasswdAgain']",
      "input[autocomplete='new-password']",
      "input[type='password']"
    ],
    birthMonth: [
      "#month",
      "select#month",
      "[aria-label*='Month' i]",
      "[aria-label*='month' i][role='combobox']",
      "[aria-label*='月份']",
      "[aria-label*='月'][role='combobox']"
    ],
    birthDay: [
      "#day",
      "input[name='day']",
      "input[aria-label*='Day' i]",
      "input[aria-label*='day' i]",
      "input[aria-label*='日期']",
      "input[aria-label*='日']"
    ],
    birthYear: [
      "#year",
      "input[name='year']",
      "input[aria-label*='Year' i]",
      "input[aria-label*='year' i]",
      "input[aria-label*='年份']",
      "input[aria-label*='年']"
    ],
    gender: [
      "#gender",
      "select[name='gender']",
      "[aria-label*='Gender' i]",
      "[aria-label*='gender' i]",
      "[aria-label*='性别']"
    ]
  };

  const GENERIC_PROVIDER_FIELD_SELECTORS = {
    firstName: [
      "input[name='fname']",
      "input[name='firstname']",
      "input[name='firstName']",
      "input[name='FirstName']",
      "input[id*='first' i]",
      "input[autocomplete='given-name']"
    ],
    lastName: [
      "input[name='lname']",
      "input[name='lastname']",
      "input[name='lastName']",
      "input[name='LastName']",
      "input[id*='last' i]",
      "input[autocomplete='family-name']"
    ],
    fullName: [
      "input[name='name']",
      "input[id*='name' i]",
      "input[autocomplete='name']"
    ],
    username: [
      "input[name='username']",
      "input[name='partial_login']",
      "input[name='login']",
      "input[name='email']",
      "input[name='account']",
      "input[id*='username' i]",
      "input[id*='login' i]",
      "input[id*='mail' i]",
      "input[aria-label*='username' i]",
      "input[aria-label*='用户名']",
      "input[placeholder*='username' i]",
      "input[placeholder*='用户名']",
      "input[data-testid*='username' i]",
      "input[data-testid*='mailbox' i]",
      "input[autocomplete='username']",
      "input[type='email']"
    ],
    password: [
      "input[name='password']",
      "input[name='passwd']",
      "input[name='newpassword']",
      "input[name='password_retry']",
      "input[name='repeatPassword']",
      "input[name='confirmPassword']",
      "input[id*='password' i]",
      "input[type='password']",
      "input[autocomplete='new-password']"
    ],
    birthMonth: [
      "select[name*='month' i]",
      "input[name*='month' i]",
      "[data-test-id*='birth-date' i] [role='combobox']",
      "[aria-label*='month' i]"
    ],
    birthDay: [
      "select[name*='day' i]",
      "input[name*='day' i]",
      "input[aria-label*='day' i]"
    ],
    birthYear: [
      "select[name*='year' i]",
      "input[name*='year' i]",
      "input[aria-label*='year' i]"
    ],
    gender: [
      "select[name*='gender' i]",
      "input[name*='gender' i]",
      "[aria-label*='gender' i]",
      "label[data-test-id*='gender' i]"
    ],
    recovery: [
      "input[name*='recovery' i]",
      "input[name*='reserve' i]",
      "input[name='email']",
      "input[type='email']"
    ],
    terms: [
      "input[type='checkbox']",
      "[role='checkbox']",
      "label[for*='term' i]",
      "label[for*='agree' i]"
    ],
    phone: [
      ...FIELD_SELECTORS.phone
    ]
  };

  const LIVE_SWITCH_SELECTORS = [
    "#liveSwitch",
    "a#liveSwitch",
    "button#liveSwitch",
    "[data-testid='liveSwitch']",
    "a[href*='signup']",
    "button",
    "a"
  ];

  const LIVE_SWITCH_TEXT_TOKENS = [
    "get a new email address",
    "create a new email address",
    "new email address",
    "获取新的电子邮件地址",
    "创建新的电子邮件地址",
    "使用新的电子邮件地址",
    "新建电子邮件",
    "outlook.com",
    "hotmail.com"
  ];

  const YAHOO_FORM_STEP = "fill_yahoo_account_form";
  const GMAIL_PROFILE_STEP = "fill_gmail_profile";
  const GMAIL_BIRTHDATE_STEP = "fill_gmail_birthdate";
  const GMAIL_USERNAME_STEP = "fill_gmail_username";
  const GMAIL_PASSWORD_STEP = "fill_gmail_password";
  const PROTON_USERNAME_STEP = "fill_proton_username";
  const PROTON_PASSWORD_STEP = "fill_proton_password";
  const PROTON_CAPTCHA_STEP = "proton_captcha";
  const GMX_PROFILE_BIRTHDATE_STEP = "fill_gmx_profile_birthdate";
  const GMX_TERMS_STEP = "gmx_terms";
  const AOL_ACCOUNT_FORM_STEP = "fill_aol_account_form";
  const GMAIL_ACTION_STEPS = new Set([
    GMAIL_PROFILE_STEP,
    GMAIL_BIRTHDATE_STEP,
    GMAIL_USERNAME_STEP,
    GMAIL_PASSWORD_STEP
  ]);

  const GENERIC_PROVIDER_KEYS = [
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
    "tutanota"
  ];

  const PROVIDER_STEP_PREFIX = {
    netease163: "netease",
    netease126: "netease",
    neteaseyeah: "netease"
  };

  function providerStepPrefix(provider) {
    return PROVIDER_STEP_PREFIX[provider] || provider;
  }

  const PROVIDER_PHONE_BLOCKER_STEP = {
    aol: "aol_phone",
    zoho: "zoho_phone_or_otp",
    yandex: "yandex_phone_or_captcha",
    mailru: "mailru_phone_or_captcha",
    naver: "naver_phone_sms",
    kakao: "kakao_phone_or_email_otp",
    netease163: "netease_sms_or_resume",
    netease126: "netease_sms_or_resume",
    neteaseyeah: "netease_sms_or_resume",
    qq: "qq_phone_sms",
    sina: "sina_phone_account",
    sohu: "sohu_phone_sms"
  };

  const PROVIDER_CHALLENGE_STEP_BY_TYPE = {
    proton: { email_otp: "proton_email_otp", hsprotect: PROTON_CAPTCHA_STEP, arkose: PROTON_CAPTCHA_STEP, recaptcha: PROTON_CAPTCHA_STEP, hcaptcha: PROTON_CAPTCHA_STEP, turnstile: PROTON_CAPTCHA_STEP },
    gmx: { imap_enablement: "gmx_imap_enablement", phone_sms: "gmx_challenge", hsprotect: "gmx_challenge", arkose: "gmx_challenge", recaptcha: "gmx_challenge", hcaptcha: "gmx_challenge", turnstile: "gmx_challenge" },
    aol: { phone_sms: "aol_phone", hsprotect: "aol_challenge", arkose: "aol_challenge", recaptcha: "aol_challenge", hcaptcha: "aol_challenge", turnstile: "aol_challenge" },
    zoho: { phone_sms: "zoho_phone_or_otp", email_otp: "zoho_phone_or_otp" },
    yandex: { phone_sms: "yandex_phone_or_captcha", hsprotect: "yandex_phone_or_captcha", arkose: "yandex_phone_or_captcha", recaptcha: "yandex_phone_or_captcha", hcaptcha: "yandex_phone_or_captcha", turnstile: "yandex_phone_or_captcha", imap_enablement: "yandex_imap_enablement" },
    icloud: { email_otp: "icloud_email_otp" },
    mailru: { phone_sms: "mailru_phone_or_captcha", hsprotect: "mailru_phone_or_captcha", arkose: "mailru_phone_or_captcha", recaptcha: "mailru_phone_or_captcha", hcaptcha: "mailru_phone_or_captcha", turnstile: "mailru_phone_or_captcha" },
    naver: { phone_sms: "naver_phone_sms" },
    kakao: { phone_sms: "kakao_phone_or_email_otp", email_otp: "kakao_phone_or_email_otp" },
    netease163: { phone_sms: "netease_sms_or_resume", hsprotect: "netease_captcha", arkose: "netease_captcha", recaptcha: "netease_captcha", hcaptcha: "netease_captcha", turnstile: "netease_captcha" },
    netease126: { phone_sms: "netease_sms_or_resume", hsprotect: "netease_captcha", arkose: "netease_captcha", recaptcha: "netease_captcha", hcaptcha: "netease_captcha", turnstile: "netease_captcha" },
    neteaseyeah: { phone_sms: "netease_sms_or_resume", hsprotect: "netease_captcha", arkose: "netease_captcha", recaptcha: "netease_captcha", hcaptcha: "netease_captcha", turnstile: "netease_captcha" },
    qq: { phone_sms: "qq_phone_sms", hsprotect: "qq_captcha", arkose: "qq_captcha", recaptcha: "qq_captcha", hcaptcha: "qq_captcha", turnstile: "qq_captcha" },
    sina: { phone_sms: "sina_sms_code", hsprotect: "sina_captcha", arkose: "sina_captcha", recaptcha: "sina_captcha", hcaptcha: "sina_captcha", turnstile: "sina_captcha" },
    sohu: { phone_sms: "sohu_phone_sms", hsprotect: "sohu_captcha", arkose: "sohu_captcha", recaptcha: "sohu_captcha", hcaptcha: "sohu_captcha", turnstile: "sohu_captcha" },
    tutanota: { email_otp: "tutanota_email_otp" }
  };

  function genericProviderChallengeStep(provider, challenge, elements = {}) {
    const prefix = providerStepPrefix(provider);
    const typeMap = PROVIDER_CHALLENGE_STEP_BY_TYPE[provider] || {};
    if (challenge && typeMap[challenge.type]) return typeMap[challenge.type];
    if (elements.phone && PROVIDER_PHONE_BLOCKER_STEP[provider]) return PROVIDER_PHONE_BLOCKER_STEP[provider];
    return `${prefix}_challenge`;
  }

  function isGenericProviderBlockerStep(stepId) {
    if (!stepId) return false;
    if (stepId === "post_challenge" || stepId === "challenge") return false;
    if (stepId.endsWith("_challenge")) return true;
    return Object.values(PROVIDER_PHONE_BLOCKER_STEP).includes(stepId)
      || Object.values(PROVIDER_CHALLENGE_STEP_BY_TYPE).some((typeMap) => Object.values(typeMap).includes(stepId));
  }

  const GENERIC_ACTION_STEPS = new Set(GENERIC_PROVIDER_KEYS.flatMap((provider) => {
    const prefix = providerStepPrefix(provider);
    return [
      `fill_${prefix}_name`,
      `fill_${prefix}_username`,
      `fill_${prefix}_password`,
      `fill_${prefix}_birthdate`,
      `fill_${prefix}_gender`,
      `fill_${prefix}_profile`,
      `fill_${prefix}_recovery`,
      `fill_${prefix}_reserve_email`,
      `fill_${prefix}_domain`,
      `fill_${prefix}_terms`
    ];
  }));

  const AUTO_ACTIONABLE_STEPS = new Set([
    "fill_username",
    "fill_password",
    "fill_profile",
    "fill_birthdate",
    ...GMAIL_ACTION_STEPS,
    ...GENERIC_ACTION_STEPS,
    PROTON_USERNAME_STEP,
    PROTON_PASSWORD_STEP,
    GMX_PROFILE_BIRTHDATE_STEP,
    GMX_TERMS_STEP,
    AOL_ACCOUNT_FORM_STEP,
    YAHOO_FORM_STEP
  ]);

  const SAFE_AUTO_CONTINUE_STATES = new Set([
    "privacy_notice",
    "account_notice",
    "stay_signed_in",
    "add_recovery",
    "passkey_prompt",
    "login_live"
  ]);

  const FINAL_POST_CHALLENGE_STATES = new Set([
    "account_home",
    "login_live_success",
    "oauth_complete"
  ]);

  const CREDENTIAL_READY_FINAL_STATES = new Set([
    "account_home",
    "oauth_complete"
  ]);

  function randomHexPart(length) {
    const values = secureRandomBytes(Math.ceil(length / 2));
    return Array.from(values, (value) => value.toString(16).padStart(2, "0")).join("").slice(0, length);
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
    const minAge = 19;
    const maxAge = 46;
    const latestYear = now.getFullYear() - minAge;
    const earliestYear = now.getFullYear() - maxAge;
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

  function generatedLocalAccount() {
    const provider = autoPilot.provider || "outlook";
    const domain = PROVIDER_DOMAIN[provider] || autoPilot.domain || "outlook.com";
    const birthday = randomAdultBirthday();
    const name = randomAccountName();
    const username = randomAccountUsername(name);
    return {
      username,
      provider,
      domain,
      email: `${username}@${domain}`,
      password: randomPassword(),
      ...name,
      country: "United States",
      ...birthday
    };
  }

  function accountConsoleSummary(account = {}) {
    const email = String(account.email || "").trim();
    const password = String(account.password || "");
    const username = String(account.username || (email ? email.split("@", 1)[0] : ""));
    const provider = String(account.provider || autoPilot.provider || "outlook");
    const domain = String(account.domain || autoPilot.domain || "outlook.com");
    return {
      email,
      password,
      username,
      provider,
      domain
    };
  }

  function logExplicitAccount(tag, account = {}, extra = {}) {
    try {
      const summary = accountConsoleSummary(account);
      const extraText = Object.keys(extra).length ? ` ${JSON.stringify(extra)}` : "";
      console.info(`[Ninjemail][${tag}] 账号=${summary.email} 密码=${summary.password} 用户名=${summary.username} provider=${summary.provider} domain=${summary.domain}${extraText}`);
    } catch (error) {
      // Console logging must never block the registration flow.
    }
  }

  function ensureAutoPilotAccount() {
    if (!autoPilot.account) {
      return null;
    }
    autoPilot.account.provider = autoPilot.account.provider || autoPilot.provider || "outlook";
    autoPilot.account.domain = autoPilot.account.domain || PROVIDER_DOMAIN[autoPilot.account.provider] || autoPilot.domain || "outlook.com";
    autoPilot.account.email = autoPilot.account.email || `${localUsername(autoPilot.account)}@${autoPilot.account.domain}`;
    if (!autoPilot.account.firstName || !autoPilot.account.lastName) {
      Object.assign(autoPilot.account, randomAccountName());
    }
    if (!autoPilot.account.birthMonth || !autoPilot.account.birthDay || !autoPilot.account.birthYear) {
      Object.assign(autoPilot.account, randomAdultBirthday());
    }
    try {
      chrome.storage.local.set({ ninjemailActiveAccount: autoPilot.account });
    } catch (error) {
      // Storage can be unavailable during extension reload.
    }
    return autoPilot.account;
  }

  function setProvider(provider) {
    const normalized = PROVIDER_DOMAIN[provider] ? provider : "outlook";
    autoPilot.provider = normalized;
    autoPilot.domain = PROVIDER_DOMAIN[normalized] || "outlook.com";
    if (autoPilot.account) {
      autoPilot.account.provider = normalized;
      autoPilot.account.domain = autoPilot.domain;
      autoPilot.account.email = `${localUsername(autoPilot.account)}@${autoPilot.domain}`;
    }
  }

  function lower(value) {
    return String(value || "").toLowerCase();
  }

  const SAFE_CONTINUE_CONTROL_SELECTOR = [
    "#idSIButton9",
    "#idBtn_Back",
    "#idBtn_Accept",
    "#acceptButton",
    "button",
    "input[type='button']",
    "input[type='submit']",
    "a[role='button']",
    "div[role='button']",
    "span[role='button']",
    "[role='button']",
    "button[data-testid]",
    "input[id]",
    "input[name]"
  ].join(", ");

  function providerFromPage() {
    const host = lower(location.hostname || "");
    if (host.includes("accounts.google.com")) return "gmail";
    if (host.includes("login.yahoo.com")) return "yahoo";
    if (host === "reg.email.163.com") {
      const href = lower(location.href || "");
      if (href.includes("from=126mail") || href.includes("126mail")) return "netease126";
      if (href.includes("from=yeah") || href.includes("yeah.net")) return "neteaseyeah";
      if (autoPilot.provider === "netease126" || autoPilot.provider === "neteaseyeah") return autoPilot.provider;
      return "netease163";
    }
    for (const [hostHint, provider] of Object.entries(PROVIDER_HOST_HINTS)) {
      if (host === hostHint || host.endsWith(`.${hostHint}`)) return provider;
    }
    if (host.includes("live.com") || host.includes("microsoft.com")) {
      return autoPilot.provider === "hotmail" ? "hotmail" : "outlook";
    }
    return "";
  }

  function flowProvider() {
    return providerFromPage() || autoPilot.provider || "outlook";
  }

  function isGmailContext() {
    return flowProvider() === "gmail";
  }

  function controlTagName(node) {
    return node && node.tagName ? node.tagName.toLowerCase() : "";
  }

  function isTextInputControl(node) {
    if (!node || isDisabledControl(node)) return false;
    if (node.isContentEditable) return true;
    const tagName = controlTagName(node);
    if (tagName === "textarea") return true;
    if (tagName !== "input") return false;
    const type = lower(node.getAttribute("type") || "text");
    return !["button", "checkbox", "color", "file", "hidden", "image", "radio", "range", "reset", "submit"].includes(type);
  }

  function isSelectLikeControl(node) {
    if (!node) return false;
    const ariaHasPopup = lower(node.getAttribute("aria-haspopup") || "");
    return controlTagName(node) === "select"
      || node.getAttribute("role") === "combobox"
      || Boolean(ariaHasPopup && ariaHasPopup !== "false");
  }

  function resolveInteractiveControl(node) {
    if (!node) return null;
    if (isTextInputControl(node) || isSelectLikeControl(node)) return node;
    const nested = node.querySelector && node.querySelector("input, textarea, select, [role='combobox'], [aria-haspopup], button");
    if (nested && isVisible(nested) && !isDisabledControl(nested)) return nested;
    return node;
  }

  function controlActionVerb(node) {
    return isTextInputControl(node) ? "填写" : "选择";
  }

  function textSample() {
    const bodyText = document.body ? document.body.innerText || "" : "";
    return lower(bodyText.slice(0, 12000));
  }

  function isVisible(node) {
    if (!node || !node.getBoundingClientRect) return false;
    const style = window.getComputedStyle(node);
    if (!style || style.visibility === "hidden" || style.display === "none" || style.opacity === "0") {
      return false;
    }
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function humanClick(node) {
    if (!node || !isVisible(node)) return false;
    try {
      node.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    } catch (error) {
      // Ignore scroll failures on transient popup nodes.
    }
    try {
      node.focus({ preventScroll: true });
    } catch (error) {
      try { node.focus(); } catch (_) {}
    }
    const rect = node.getBoundingClientRect();
    const point = {
      clientX: randomInt(Math.floor(rect.left + rect.width * 0.35), Math.floor(rect.left + rect.width * 0.65)),
      clientY: randomInt(Math.floor(rect.top + rect.height * 0.35), Math.floor(rect.top + rect.height * 0.65)),
      bubbles: true,
      cancelable: true,
      view: window
    };
    ["mouseover", "mousemove", "mousedown", "mouseup", "click"].forEach((type) => {
      try {
        node.dispatchEvent(new MouseEvent(type, point));
      } catch (error) {
        // Fallback below covers event construction quirks.
      }
    });
    if (typeof node.click === "function") node.click();
    return true;
  }

  function dispatchKeyboard(node, type, key, extra = {}) {
    try {
      node.dispatchEvent(new KeyboardEvent(type, {
        bubbles: true,
        cancelable: true,
        key,
        code: key.length === 1 ? `Key${key.toUpperCase()}` : key,
        ...extra
      }));
    } catch (error) {
      // Synthetic keyboard events are best-effort; input events below are authoritative.
    }
  }

  function queryAny(selectors) {
    for (const selector of selectors) {
      try {
        const node = document.querySelector(selector);
        if (node && isVisible(node)) return node;
      } catch (error) {
        // Ignore unsupported selectors on third-party frames.
      }
    }
    return null;
  }

  function nodeEvidence(node, fallback = "") {
    if (!node) return fallback;
    const attrs = ["id", "name", "type", "placeholder", "aria-label", "data-testid"]
      .map((name) => {
        const value = node.getAttribute && node.getAttribute(name);
        return value ? `${name}=${value}` : "";
      })
      .filter(Boolean);
    const text = String(node.innerText || node.value || "").trim().slice(0, 80);
    return [node.tagName ? node.tagName.toLowerCase() : "", ...attrs, text ? `text=${text}` : ""]
      .filter(Boolean)
      .join(" ");
  }

  function frameSources() {
    return Array.from(document.querySelectorAll("iframe"))
      .map((frame) => ({
        src: lower(frame.getAttribute("src") || ""),
        id: lower(frame.getAttribute("id") || ""),
        name: lower(frame.getAttribute("name") || ""),
        visible: isVisible(frame),
        evidence: nodeEvidence(frame)
      }))
      .filter((item) => item.src || item.id);
  }

  function visibleButtonTexts() {
    return Array.from(document.querySelectorAll(SAFE_CONTINUE_CONTROL_SELECTOR))
      .filter(isVisible)
      .map((node) => buttonText(node))
      .filter(Boolean);
  }

  function includesAny(haystack, tokens) {
    return tokens.some((token) => haystack.includes(lower(token)));
  }

  function findChallengePattern(type) {
    return (flow.CHALLENGE_PATTERNS || []).find((item) => item.type === type) || {
      type,
      label: type,
      action: "manual_required",
      tokens: [type]
    };
  }

  function challengeResult(type, evidence) {
    const pattern = findChallengePattern(type);
    return {
      type: pattern.type,
      label: pattern.label || pattern.type,
      action: pattern.action || "manual_required",
      evidence
    };
  }

  function detectChallenge(pageText, options = {}) {
    const host = lower(location.hostname);
    const href = lower(location.href);
    const includeFrameSources = Boolean(options.includeFrameSources);
    const sources = Array.isArray(options.sources) ? options.sources : [];
    const visibleHsprotectFrames = sources.filter((item) => item.visible && item.src.includes("hsprotect"));
    const hsprotectFrames = sources.filter((item) => item.src.includes("hsprotect") || item.src.includes("fpt.live.com"));
    const frameHaystack = includeFrameSources ? sources.map((item) => [item.src, item.id, item.name].filter(Boolean).join(" ")).join("\n") : "";
    const haystack = [href, host, pageText, frameHaystack].join("\n");

    if (host.includes("hsprotect.net")) {
      return challengeResult("hsprotect", `frame_host=${host}`);
    }

    if (
      includesAny(pageText, ["press and hold", "human challenge", "按住", "证明你不是机器人", "验证你不是机器人"]) ||
      (includeFrameSources && visibleHsprotectFrames.length)
    ) {
      const frameEvidence = visibleHsprotectFrames[0]?.src || hsprotectFrames[0]?.src || "visible_hsprotect_text";
      return challengeResult("hsprotect", frameEvidence);
    }

    for (const item of flow.CHALLENGE_PATTERNS || []) {
      if (item.type === "hsprotect") continue;
      const token = (item.tokens || []).find((candidate) => haystack.includes(lower(candidate)));
      if (token) {
        return {
          type: item.type,
          label: item.label || item.type,
          action: item.action || "manual_required",
          evidence: token
        };
      }
    }

    return null;
  }

  function detectPostChallenge(pageText) {
    const href = lower(location.href);
    const buttons = visibleButtonTexts();
    const hasButton = (tokens) => buttons.some((text) => includesAny(text, tokens));

    const strongPrivacyText = includesAny(pageText, [
      "个人数据导出许可",
      "microsoft 隐私声明",
      "microsoft privacy statement",
      "privacy notice",
      "中国境外",
      "outside china"
    ]);
    if (
      href.includes("privacynotice.account.microsoft.com")
      || (strongPrivacyText && hasButton(["同意并继续", "agree and continue", "accept and continue"]))
    ) {
      return "privacy_notice";
    }

    if (
      includesAny(pageText, [
        "有关 microsoft 帐户的快速说明",
        "有关 microsoft 账户的快速说明",
        "quick note about your microsoft account",
        "about your microsoft account"
      ]) &&
      hasButton(["确定", "ok", "continue", "next"])
    ) {
      return "account_notice";
    }

    if (
      includesAny(pageText, [
        "我们遇到了问题",
        "请重试",
        "something went wrong",
        "we ran into a problem",
        "try again"
      ]) &&
      (href.includes("live.com") || href.includes("microsoft.com"))
    ) {
      return "microsoft_problem";
    }

    if (
      includesAny(pageText, ["stay signed in", "保持登录", "保持登录状态"]) &&
      hasButton(["是", "否", "yes", "no"])
    ) {
      return "stay_signed_in";
    }

    if (
      includesAny(pageText, ["add a recovery", "recovery email", "添加恢复", "恢复信息"]) &&
      hasButton(["跳过", "暂不", "skip", "not now", "next", "下一步"])
    ) {
      return "add_recovery";
    }

    if (queryAny(FIELD_SELECTORS.phone) || includesAny(pageText, ["phone number", "text message", "sms code", "手机号", "短信验证码"])) {
      return "phone_verification";
    }

    if (
      href.includes("interrupt/passkey")
      || href.includes("consumers/fido/create")
      || includesAny(pageText, ["passkey", "security key", "windows hello", "通行密钥", "密钥"])
    ) {
      return "passkey_prompt";
    }

    if (href.includes("complete-client-signin-oauth-silent") || href.includes("complete-signin")) return "oauth_complete";
    if (href.includes("login.live.com") && (href.includes("res=success") || href.includes("ppsecure/post.srf"))) return "login_live_success";
    if (href.includes("account.microsoft.com") || href.includes("account.live.com")) return "account_home";
    if (href.includes("login.live.com")) return "login_live";

    return "";
  }

  function finalState(pageText) {
    const href = lower(location.href);
    if (includesAny(pageText, ["account has been created", "帐户已创建", "账户已创建"])) {
      return "success_message";
    }
    if (href.includes("privacynotice.account.microsoft.com")) return "";
    if (includesAny(pageText, ["stay signed in", "保持登录", "保持登录状态"])) return "";
    if (href.includes("interrupt/passkey") || href.includes("consumers/fido/create")) return "";
    if (href.includes("complete-client-signin-oauth-silent") || href.includes("complete-signin")) return "oauth_complete";
    if (href.includes("login.live.com") && (href.includes("res=success") || href.includes("ppsecure/post.srf"))) return "login_live_success";
    if (href.includes("account.microsoft.com") || href.includes("account.live.com")) return "account_home";
    return "";
  }

  function detectGmailElements() {
    const firstName = queryAny(GMAIL_FIELD_SELECTORS.firstName);
    const lastName = queryAny(GMAIL_FIELD_SELECTORS.lastName);
    const username = queryAny(GMAIL_FIELD_SELECTORS.username);
    const password = queryAny(GMAIL_FIELD_SELECTORS.password);
    const birthMonth = queryAny(GMAIL_FIELD_SELECTORS.birthMonth);
    const birthDay = queryAny(GMAIL_FIELD_SELECTORS.birthDay);
    const birthYear = queryAny(GMAIL_FIELD_SELECTORS.birthYear);
    const gender = queryAny(GMAIL_FIELD_SELECTORS.gender);
    const birthdate = birthYear || birthMonth || birthDay || gender;
    const profile = firstName || lastName;
    return {
      username,
      password,
      profile,
      birthdate,
      submit: queryAny(FIELD_SELECTORS.submit),
      phone: queryAny(FIELD_SELECTORS.phone),
      gmailProfile: profile,
      gmailUsername: username,
      gmailPassword: password,
      gmailBirthdate: birthdate
    };
  }

  function isGenericProviderContext() {
    return GENERIC_PROVIDER_KEYS.includes(flowProvider());
  }

  function detectGenericProviderElements() {
    const firstName = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.firstName);
    const lastName = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.lastName);
    const fullName = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.fullName);
    const username = flowProvider() === "proton" ? findProtonUsernameField() : queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.username);
    const password = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.password);
    const birthMonth = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.birthMonth);
    const birthDay = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.birthDay);
    const birthYear = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.birthYear);
    const gender = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.gender);
    const recovery = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.recovery);
    const terms = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.terms);
    const phone = queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.phone);
    const birthdate = birthMonth || birthDay || birthYear || gender;
    const profile = firstName || lastName || fullName;
    return {
      username,
      password,
      profile,
      birthdate,
      submit: queryAny(FIELD_SELECTORS.submit),
      phone,
      genericProfile: profile,
      genericUsername: username,
      genericPassword: password,
      genericBirthdate: birthdate,
      genericGender: gender,
      genericRecovery: recovery,
      genericTerms: terms
    };
  }

  function detectElements() {
    if (isGmailContext()) return detectGmailElements();
    if (isGenericProviderContext()) return detectGenericProviderElements();
    return {
      username: queryAny(FIELD_SELECTORS.username),
      password: queryAny(FIELD_SELECTORS.password),
      profile: queryAny(FIELD_SELECTORS.profile),
      birthdate: queryAny(FIELD_SELECTORS.birthdate),
      submit: queryAny(FIELD_SELECTORS.submit),
      phone: queryAny(FIELD_SELECTORS.phone)
    };
  }

  function activeGmailStepId(elements, challenge, postChallengeState, final) {
    const href = lower(location.href);
    if (elements.gmailProfile || href.includes("/signup/name")) return GMAIL_PROFILE_STEP;
    if (elements.gmailBirthdate || href.includes("/signup/birthdaygender")) return GMAIL_BIRTHDATE_STEP;
    if (elements.gmailUsername || href.includes("/signup/username")) return GMAIL_USERNAME_STEP;
    if (elements.gmailPassword || href.includes("/signup/password")) return GMAIL_PASSWORD_STEP;
    if (final) return "final_state";
    if (postChallengeState) return "post_challenge";
    if (challenge != null) return "challenge";
    return "open_signup";
  }

  function activeGenericProviderStepId(elements, challenge, postChallengeState, final) {
    const provider = flowProvider();
    const prefix = providerStepPrefix(provider);
    const href = lower(location.href);
    if (final) return "final_state";
    if (challenge != null) return genericProviderChallengeStep(provider, challenge, elements);
    if (elements.phone) return genericProviderChallengeStep(provider, null, elements);
    if (provider === "proton") {
      if (elements.genericUsername) return PROTON_USERNAME_STEP;
      if (elements.genericPassword) return PROTON_PASSWORD_STEP;
      if (href.includes("signup") || href.includes("register")) return PROTON_USERNAME_STEP;
    }
    if (provider === "gmx") {
      if (gmxLooksLikeProfileBirthdateStep(elements) || href.includes("birth")) return GMX_PROFILE_BIRTHDATE_STEP;
      if (elements.genericTerms) return GMX_TERMS_STEP;
      if (elements.genericUsername || findGmxUsernameField() || gmxHasCheckButton() || href.includes("signup") || href.includes("register")) return `fill_${prefix}_username`;
      if (elements.genericPassword) return `fill_${prefix}_password`;
      if (elements.genericRecovery) return `fill_${prefix}_recovery`;
    }
    if (provider === "aol") {
      if (elements.genericProfile || elements.genericUsername || elements.genericPassword || elements.genericBirthdate || href.includes("account/create")) {
        return AOL_ACCOUNT_FORM_STEP;
      }
    }
    if (elements.genericProfile || href.includes("name")) return `fill_${prefix}_name`;
    if (elements.genericBirthdate || href.includes("birth")) return `fill_${prefix}_birthdate`;
    if (elements.genericGender) return `fill_${prefix}_gender`;
    if (elements.genericUsername || href.includes("signup") || href.includes("register")) return `fill_${prefix}_username`;
    if (elements.genericPassword) return `fill_${prefix}_password`;
    if (elements.genericRecovery) return `fill_${prefix}_recovery`;
    if (elements.genericTerms) return `fill_${prefix}_terms`;
    if (postChallengeState) return "post_challenge";
    if (challenge) return "challenge";
    return "open_signup";
  }

  function activeStepId(elements, challenge, postChallengeState, final) {
    const href = lower(location.href);
    if (isGmailContext()) return activeGmailStepId(elements, challenge, postChallengeState, final);
    if (isGenericProviderContext()) return activeGenericProviderStepId(elements, challenge, postChallengeState, final);
    if (final) return "final_state";
    // IMPORTANT: postChallengeState (privacy_notice etc.) means challenge was already passed.
    // The hsprotect/fpt.live.com iframes may linger — do NOT treat as active challenge.
    if (postChallengeState) return "post_challenge";
    if (challenge) return "challenge";
    if (isYahooCreatePage() && (elements.username || elements.password || elements.profile || elements.birthdate)) return YAHOO_FORM_STEP;
    if (elements.username) return "fill_username";
    if (elements.password) return "fill_password";
    if (elements.profile) return "fill_profile";
    if (elements.birthdate) return "fill_birthdate";
    if (challenge) return "challenge";
    if (href.includes("live.com") || href.includes("microsoft.com")) return "open_signup";
    return "open_signup";
  }

  function observedEvidenceByStep(elements, challenge, postChallengeState, final, activeStep) {
    const pageHost = location.hostname || location.href;
    const genericPrefix = providerStepPrefix(flowProvider());
    const genericEvidence = {
      [`fill_${genericPrefix}_name`]: elements.genericProfile ? nodeEvidence(elements.genericProfile) : "",
      [`fill_${genericPrefix}_profile`]: elements.genericProfile ? nodeEvidence(elements.genericProfile) : "",
      [`fill_${genericPrefix}_username`]: elements.genericUsername ? nodeEvidence(elements.genericUsername) : "",
      [`fill_${genericPrefix}_password`]: elements.genericPassword ? nodeEvidence(elements.genericPassword) : "",
      [`fill_${genericPrefix}_birthdate`]: elements.genericBirthdate ? nodeEvidence(elements.genericBirthdate) : "",
      [`fill_${genericPrefix}_gender`]: elements.genericGender ? nodeEvidence(elements.genericGender) : "",
      [`fill_${genericPrefix}_recovery`]: elements.genericRecovery ? nodeEvidence(elements.genericRecovery) : "",
      [`fill_${genericPrefix}_reserve_email`]: elements.genericRecovery ? nodeEvidence(elements.genericRecovery) : "",
      [`fill_${genericPrefix}_domain`]: location.hostname || "",
      [`fill_${genericPrefix}_terms`]: elements.genericTerms ? nodeEvidence(elements.genericTerms) : "",
      [`${genericPrefix}_challenge`]: challenge && activeStep === `${genericPrefix}_challenge`
        ? `${challenge.label || challenge.type}: ${challenge.evidence}`
        : (elements.phone ? nodeEvidence(elements.phone) : "")
    };
    const genericBlockerStep = genericProviderChallengeStep(flowProvider(), challenge, elements);
    if (isGenericProviderBlockerStep(genericBlockerStep)) {
      genericEvidence[genericBlockerStep] = challenge
        ? `${challenge.label || challenge.type}: ${challenge.evidence}`
        : nodeEvidence(elements.phone);
    }
    return {
      plugin_ready: "探针已连接",
      open_signup: pageHost,
      fill_username: elements.username ? nodeEvidence(elements.username) : "",
      fill_password: elements.password ? nodeEvidence(elements.password) : "",
      fill_profile: elements.profile ? nodeEvidence(elements.profile) : "",
      fill_birthdate: elements.birthdate ? nodeEvidence(elements.birthdate) : "",
      [GMAIL_PROFILE_STEP]: elements.gmailProfile ? nodeEvidence(elements.gmailProfile) : "",
      [GMAIL_BIRTHDATE_STEP]: elements.gmailBirthdate ? nodeEvidence(elements.gmailBirthdate) : "",
      [GMAIL_USERNAME_STEP]: elements.gmailUsername ? nodeEvidence(elements.gmailUsername) : "",
      [GMAIL_PASSWORD_STEP]: elements.gmailPassword ? nodeEvidence(elements.gmailPassword) : "",
      [YAHOO_FORM_STEP]: [elements.profile, elements.username, elements.password, elements.birthdate]
        .filter(Boolean)
        .map((node) => nodeEvidence(node))
        .join(" | "),
      ...genericEvidence,
      challenge: challenge && activeStep === "challenge" ? `${challenge.label || challenge.type}: ${challenge.evidence}` : "",
      post_challenge: postChallengeState || "",
      final_state: final || "",
      export_credentials: final ? "等待获取并保存四凭证" : ""
    };
  }

  function buildStepRows(activeStep, elements, challenge, postChallengeState, final) {
    const steps = flow.stepsForProvider ? flow.stepsForProvider(flowProvider()) : (flow.OUTLOOK_STEPS || []);
    const evidenceMap = observedEvidenceByStep(elements, challenge, postChallengeState, final, activeStep);

    // 找到 activeStep 在有序列表中的位置，用于判断 done/current/pending
    const activeIndex = activeStep ? steps.findIndex((s) => s.id === activeStep) : -1;

    return steps.map((step, index) => {
      const evidence = evidenceMap[step.id] || "本轮尚未观察到该步骤";
      let status = "pending";

      // 1. plugin_ready 始终完成
      if (step.id === "plugin_ready") {
        status = "done";
      }
      // 2. open_signup：页面已加载即完成
      else if (step.id === "open_signup" && evidenceMap.open_signup) {
        status = "done";
      }
      // 3. final_state 特殊处理
      else if (step.id === "final_state") {
        status = final ? "done" : "pending";
      }
      // 4. export_credentials 特殊处理
      else if (step.id === "export_credentials") {
        status = final ? "current" : "pending";
      }
      // 5. 当前活跃步骤
      else if (step.id === activeStep) {
        // 判断是否被 challenge 或 provider blocker 阻塞
        const isBlocked = (step.id === "challenge" && challenge)
          || isGenericProviderBlockerStep(step.id);
        status = isBlocked ? "blocked" : "current";
      }
      // 6. activeStep 之前的步骤 → 已完成
      else if (activeIndex >= 0 && index < activeIndex) {
        status = "done";
      }
      // 7. activeStep 之后的步骤 → pending（保持默认）
      // 如果有历史观察记录（background applyStepHistory 会补充 seen）

      return {
        id: step.id,
        label: step.label,
        intent: step.intent || "",
        status,
        evidence
      };
    });
  }

  function rootCauseFor(activeStep, elements, challenge, postChallengeState, final) {
    if ((activeStep === "challenge" || isGenericProviderBlockerStep(activeStep)) && challenge) {
      return {
        blocker: "challenge",
        reason: `人机验证：${challenge.label || challenge.type}`,
        evidence: challenge.evidence,
        nextAction: challenge.type === "hsprotect"
          ? "手动完成 HUMAN 按住验证，完成后点“扫描当前页”"
          : "确认服务是否支持该挑战，或手动处理后扫描"
      };
    }
    if (isGenericProviderBlockerStep(activeStep)) {
      return {
        blocker: "provider_manual_verification",
        reason: `Provider verification step: ${activeStep}`,
        evidence: nodeEvidence(elements.phone) || document.title || location.href,
        nextAction: "Stop here and record the provider blocker; continue only after a valid phone/SMS/OTP/captcha/manual adapter is available."
      };
    }
    if (final) {
      return {
        blocker: "",
        reason: `最终状态：${final}`,
        evidence: location.href,
        nextAction: "收集结果或返回 Web UI"
      };
    }
    if (postChallengeState === "microsoft_problem") {
      return {
        blocker: "microsoft_problem",
        reason: "Microsoft 返回“我们遇到了问题”，当前账号不能继续复用",
        evidence: document.title || location.href,
        nextAction: "丢弃当前生成账号；下一次开始注册必须重新生成账号、密码和 ID"
      };
    }
    if (postChallengeState) {
      return {
        blocker: "post_challenge_state",
        reason: `验证后页面：${postChallengeState}`,
        evidence: document.title || location.href,
        nextAction: "插件会尝试自动点击继续/跳过；卡住时可手动点“继续/跳过”"
      };
    }
    const evidenceByStep = {
      fill_username: nodeEvidence(elements.username),
      fill_password: nodeEvidence(elements.password),
      fill_profile: nodeEvidence(elements.profile),
      fill_birthdate: nodeEvidence(elements.birthdate),
      [GMAIL_PROFILE_STEP]: nodeEvidence(elements.gmailProfile || elements.profile),
      [GMAIL_BIRTHDATE_STEP]: nodeEvidence(elements.gmailBirthdate || elements.birthdate),
      [GMAIL_USERNAME_STEP]: nodeEvidence(elements.gmailUsername || elements.username),
      [GMAIL_PASSWORD_STEP]: nodeEvidence(elements.gmailPassword || elements.password),
      [YAHOO_FORM_STEP]: [elements.profile, elements.username, elements.password, elements.birthdate]
        .filter(Boolean)
        .map((node) => nodeEvidence(node))
        .join(" | "),
      plugin_ready: "探针已连接",
      open_signup: location.href
    };
    const genericPrefix = providerStepPrefix(flowProvider());
    Object.assign(evidenceByStep, {
      [`fill_${genericPrefix}_name`]: nodeEvidence(elements.genericProfile || elements.profile),
      [`fill_${genericPrefix}_profile`]: nodeEvidence(elements.genericProfile || elements.profile),
      [`fill_${genericPrefix}_username`]: nodeEvidence(elements.genericUsername || elements.username),
      [`fill_${genericPrefix}_password`]: nodeEvidence(elements.genericPassword || elements.password),
      [`fill_${genericPrefix}_birthdate`]: nodeEvidence(elements.genericBirthdate || elements.birthdate),
      [`fill_${genericPrefix}_gender`]: nodeEvidence(elements.genericGender),
      [`fill_${genericPrefix}_recovery`]: nodeEvidence(elements.genericRecovery),
      [`fill_${genericPrefix}_reserve_email`]: nodeEvidence(elements.genericRecovery),
      [`fill_${genericPrefix}_domain`]: location.hostname || "",
      [`fill_${genericPrefix}_terms`]: nodeEvidence(elements.genericTerms),
      [`${genericPrefix}_challenge`]: challenge ? challenge.evidence : nodeEvidence(elements.phone)
    });
    const genericBlockerStep = genericProviderChallengeStep(flowProvider(), challenge, elements);
    if (isGenericProviderBlockerStep(genericBlockerStep)) {
      evidenceByStep[genericBlockerStep] = challenge ? challenge.evidence : nodeEvidence(elements.phone);
    }
    return {
      blocker: activeStep === "open_signup" ? "" : "auto_step_pending",
      reason: `当前步骤：${flow.stepLabel ? flow.stepLabel(activeStep, flowProvider()) : activeStep}`,
      evidence: evidenceByStep[activeStep] || document.title || location.href,
      nextAction: "点“开始注册”后普通步骤会自动接续；如果停住，点“开始注册”重试或点“聚焦步骤”定位"
    };
  }

  function detectStepState(pageText, challenge) {
    const elements = detectElements();
    const postChallengeState = detectPostChallenge(pageText);
    const final = finalState(pageText);
    const activeStep = activeStepId(elements, challenge, postChallengeState, final);
    const rootCause = rootCauseFor(activeStep, elements, challenge, postChallengeState, final);
    if (AUTO_ACTIONABLE_STEPS.has(activeStep) && !(activeStep === "challenge" && challenge) && rootCause) {
      rootCause.blocker = "auto_step_pending";
      rootCause.nextAction = "插件正在自动执行普通步骤；如果停住，点“开始注册”重试或点“聚焦当前步骤”定位";
    }
    return {
      activeStep,
      postChallengeState,
      finalState: final,
      elements: {
        username: Boolean(elements.username),
        password: Boolean(elements.password),
        profile: Boolean(elements.profile),
        birthdate: Boolean(elements.birthdate),
        submit: Boolean(elements.submit),
        phone: Boolean(elements.phone),
        genericProfile: Boolean(elements.genericProfile),
        genericUsername: Boolean(elements.genericUsername),
        genericPassword: Boolean(elements.genericPassword),
        genericBirthdate: Boolean(elements.genericBirthdate),
        genericGender: Boolean(elements.genericGender),
        genericRecovery: Boolean(elements.genericRecovery),
        genericTerms: Boolean(elements.genericTerms)
      },
      steps: buildStepRows(activeStep, elements, challenge, postChallengeState, final),
      rootCause
    };
  }

  function activeElementForStep(activeStep) {
    if (activeStep === GMAIL_PROFILE_STEP) return queryAny(GMAIL_FIELD_SELECTORS.firstName) || queryAny(GMAIL_FIELD_SELECTORS.lastName);
    if (activeStep === GMAIL_BIRTHDATE_STEP) {
      return queryAny(GMAIL_FIELD_SELECTORS.birthYear)
        || queryAny(GMAIL_FIELD_SELECTORS.birthMonth)
        || queryAny(GMAIL_FIELD_SELECTORS.birthDay)
        || queryAny(GMAIL_FIELD_SELECTORS.gender);
    }
    if (activeStep === GMAIL_USERNAME_STEP) return queryAny(GMAIL_FIELD_SELECTORS.username);
    if (activeStep === GMAIL_PASSWORD_STEP) return queryAny(GMAIL_FIELD_SELECTORS.password);
    if (activeStep === YAHOO_FORM_STEP) {
      return queryAny([
        "#usernamereg-firstName",
        "#usernamereg-lastName",
        "#usernamereg-userId",
        "#usernamereg-password",
        "#usernamereg-month",
        "#usernamereg-day",
        "#usernamereg-year"
      ]) || document.body;
    }
    if (isGenericProviderContext()) {
      const prefix = providerStepPrefix(flowProvider());
      if (activeStep === `fill_${prefix}_name` || activeStep === `fill_${prefix}_profile`) {
        return queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.firstName)
          || queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.lastName)
          || queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.fullName);
      }
      if (activeStep === `fill_${prefix}_username`) return queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.username);
      if (activeStep === `fill_${prefix}_password`) return queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.password);
      if (activeStep === `fill_${prefix}_birthdate`) {
        return queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.birthYear)
          || queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.birthMonth)
          || queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.birthDay)
          || queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.gender);
      }
      if (activeStep === `fill_${prefix}_gender`) return queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.gender);
      if (activeStep === `fill_${prefix}_recovery` || activeStep === `fill_${prefix}_reserve_email`) return queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.recovery);
      if (activeStep === `fill_${prefix}_terms`) return queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.terms);
      if (isGenericProviderBlockerStep(activeStep)) return queryAny(GENERIC_PROVIDER_FIELD_SELECTORS.phone) || document.body;
    }
    if (activeStep === "fill_username") return queryAny(FIELD_SELECTORS.username);
    if (activeStep === "fill_password") return queryAny(FIELD_SELECTORS.password);
    if (activeStep === "fill_profile") return queryAny(FIELD_SELECTORS.profile);
    if (activeStep === "fill_birthdate") return queryAny(FIELD_SELECTORS.birthdate);
    return queryAny(FIELD_SELECTORS.submit) || document.body;
  }

  function highlight(node) {
    if (!node || !node.style) return false;
    if (highlightNode && highlightNode !== node && highlightNode.style) {
      highlightNode.style.outline = "";
      highlightNode.style.outlineOffset = "";
    }
    node.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    node.style.outline = "3px solid #1261a6";
    node.style.outlineOffset = "3px";
    highlightNode = node;
    return true;
  }

  function buttonText(node) {
    if (!node) return "";
    const values = [
      node.innerText,
      node.textContent,
      node.value,
      node.getAttribute && node.getAttribute("aria-label"),
      node.getAttribute && node.getAttribute("title"),
      node.getAttribute && node.getAttribute("id"),
      node.getAttribute && node.getAttribute("name"),
      node.getAttribute && node.getAttribute("data-testid"),
      node.getAttribute && node.getAttribute("data-value")
    ];
    return lower(values.filter((value) => String(value || "").trim()).join(" "));
  }

  function controlMatchesToken(node, token) {
    const text = buttonText(node);
    const wanted = lower(token);
    if (!text || !wanted) return false;
    return text === wanted || text.includes(wanted);
  }

  function clickSafeContinue(pageText) {
    const sources = frameSources();
    const challenge = detectChallenge(pageText, { sources, includeFrameSources: true });
    const state = detectStepState(pageText, challenge);
    const blockedRequestText = includesAny(lower(pageText), [
      "the request is blocked",
      "contextid supplied in the request did not have a matching cookie",
      "我们无法完成你的请求"
    ]);
    if (state.postChallengeState === "privacy_notice" && blockedRequestText) {
      let targetUrl = "";
      try {
        const current = new URL(location.href);
        targetUrl = current.searchParams.get("ru") || "";
      } catch (error) {
        targetUrl = "";
      }
      if (!targetUrl) targetUrl = "https://login.live.com/";
      if (autoPilot.account && autoPilot.account.email) {
        autoPilot.oauthEmail = String(autoPilot.account.email || "");
        autoPilot.oauthAccount = { ...autoPilot.account };
      }
      if (rememberControlAction(`recover_blocked_request:${location.href}:${targetUrl}`, 4500)) {
        location.assign(targetUrl);
      }
      return {
        ok: true,
        reason: "Detected blocked Microsoft request page and returned to login flow",
        evidence: targetUrl,
        postChallengeState: state.postChallengeState
      };
    }
    if (state.activeStep === "challenge" && challenge) {
      return { ok: false, reason: "当前页面仍是人机验证", blocker: challenge.type };
    }
    if (state.postChallengeState === "microsoft_problem") {
      autoPilot.enabled = false;
      autoPilot.stopped = true;
      return {
        ok: false,
        reason: "Microsoft 返回“我们遇到了问题”，当前账号流程停止；下一次开始注册会重新生成账号重跑",
        activeStep: state.activeStep,
        postChallengeState: state.postChallengeState,
        blocker: "microsoft_problem",
        hardBlocker: true,
        requestNewAccount: true,
        evidence: location.href
      };
    }
    const candidates = Array.from(document.querySelectorAll(SAFE_CONTINUE_CONTROL_SELECTOR))
      .filter((node) => isVisible(node) && !isDisabledControl(node));
    const commonPositive = ["继续", "下一步", "确定", "ok", "continue", "next"];
    const priorityByState = {
      passkey_prompt: [
        "取消",
        "cancel",
        "不使用",
        "不，谢谢",
        "暂不",
        "暂时跳过",
        "以后再说",
        "跳过",
        "not now",
        "maybe later",
        "skip",
        "skip for now",
        "no thanks",
        "no"
      ],
      stay_signed_in: ["是", "yes", "保持登录", "stay signed in", ...commonPositive],
      add_recovery: [
        "跳过",
        "暂不",
        "暂时跳过",
        "以后再说",
        "不，谢谢",
        "skip",
        "skip for now",
        "maybe later",
        "not now",
        "do this later",
        "no thanks",
        "no",
        ...commonPositive
      ],
      privacy_notice: [
        "同意并继续",
        "agree and continue",
        "接受",
        "同意",
        "允许",
        "accept",
        "allow",
        "approve",
        ...commonPositive
      ],
      account_notice: [
        "确定",
        "ok",
        "continue",
        "next",
        ...commonPositive
      ],
      login_live: [
        "继续",
        "下一步",
        "ok",
        "continue",
        "next",
        ...commonPositive
      ]
    };
    const selectorPriorityByState = {
      passkey_prompt: [
        "#idBtn_Back",
        "input[type='button'][value*='取消']",
        "input[type='button'][value*='Cancel' i]",
        "button[data-testid='secondaryButton']",
        "button[data-testid*='cancel' i]",
        "button[aria-label*='取消']",
        "button[aria-label*='cancel' i]"
      ],
      stay_signed_in: [
        "#idSIButton9",
        "input[type='submit'][value='是']",
        "input[type='submit'][value*='Yes' i]",
        "button[data-testid='primaryButton']"
      ],
      privacy_notice: [
        "#idSIButton9",
        "#idBtn_Accept",
        "#acceptButton",
        "input[type='submit']",
        "button[data-testid='primaryButton']"
      ],
      account_notice: [
        "#idSIButton9",
        "#idBtn_Accept",
        "input[type='submit']",
        "button[data-testid='primaryButton']"
      ],
      add_recovery: [
        "#idBtn_Back",
        "button[data-testid='secondaryButton']",
        "input[type='button'][value*='跳过']",
        "input[type='button'][value*='Skip' i]"
      ]
    };
    const clickMatched = (match, action) => {
      const signature = `safe_continue:${state.postChallengeState}:${location.href}:${buttonText(match) || nodeEvidence(match)}`;
      if (!rememberControlAction(signature, 4200)) {
        return { ok: true, reason: "安全继续按钮已点击，等待页面跳转", evidence: nodeEvidence(match) };
      }
      humanClick(match);
      return { ok: true, reason: action || "已点击", evidence: nodeEvidence(match) };
    };
    for (const selector of selectorPriorityByState[state.postChallengeState] || []) {
      const match = queryAny([selector]);
      if (match && !isDisabledControl(match)) {
        return clickMatched(match, "已点击优先安全按钮");
      }
    }
    const priority = priorityByState[state.postChallengeState] || [
      "同意并继续",
      "agree and continue",
      "接受",
      "同意",
      "允许",
      "accept",
      "allow",
      "approve",
      ...commonPositive,
      "跳过",
      "暂不",
      "暂时跳过",
      "以后再说",
      "不使用",
      "不，谢谢",
      "skip",
      "skip for now",
      "maybe later",
      "not now",
      "do this later",
      "no thanks",
      "no",
      "yes"
    ];
    for (const token of priority) {
      const match = candidates.find((node) => controlMatchesToken(node, token));
      if (match) {
        return clickMatched(match, "已点击");
      }
    }
    if (state.postChallengeState === "passkey_prompt" && (location.href.includes("consumers/fido/create") || location.href.includes("interrupt/passkey"))) {
      autoPilot.enabled = false;
      autoPilot.stopped = true;
      return {
        ok: false,
        reason: "通行密钥触发了原生系统弹窗，content script 无法点击；需要手动取消/关闭后继续",
        blocker: "native_passkey_dialog",
        hardBlocker: true,
        evidence: location.href
      };
    }
    return { ok: false, reason: "未找到安全的继续/跳过按钮" };
  }

  function assignNativeValue(node, value, inputType = "insertText", data = "") {
    if (!node) return false;
    const prototype = Object.getPrototypeOf(node);
    const descriptor = Object.getOwnPropertyDescriptor(prototype, "value")
      || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")
      || Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
    if (descriptor && descriptor.set) {
      descriptor.set.call(node, String(value));
    } else {
      node.value = String(value);
    }
    try {
      node.dispatchEvent(new InputEvent("input", { bubbles: true, inputType, data }));
    } catch (error) {
      node.dispatchEvent(new Event("input", { bubbles: true }));
    }
    return true;
  }

  function setNativeValue(node, value) {
    if (!node) return false;
    node.focus();
    if (typeof node.select === "function") {
      try {
        node.select();
      } catch (error) {
        // Some Microsoft controls expose select but reject it while animating.
      }
    }
    assignNativeValue(node, value, "insertText", String(value));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    node.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "a" }));
    return true;
  }

  function textInputValue(node) {
    return String(node?.value || "").trim();
  }

  function startHumanTyping(node, value, label) {
    if (!node || !isVisible(node)) return false;
    const desired = String(value || "");
    const signature = `typing:${label}:${desired}`;
    autoPilot.typingSignature = signature;
    try {
      node.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    } catch (error) {
      // Ignore transient layout failures.
    }
    try { node.focus({ preventScroll: true }); } catch (error) { try { node.focus(); } catch (_) {} }
    const current = textInputValue(node);
    const canResume = current && desired.startsWith(current);
    if (!canResume) {
      dispatchKeyboard(node, "keydown", "a", { ctrlKey: true });
      dispatchKeyboard(node, "keyup", "a", { ctrlKey: true });
      dispatchKeyboard(node, "keydown", "Backspace");
      assignNativeValue(node, "", "deleteContentBackward", "");
      dispatchKeyboard(node, "keyup", "Backspace");
    }
    const chars = Array.from(desired);
    let index = canResume ? Array.from(current).length : 0;
    const typeNext = () => {
      if (autoPilot.stopped || !autoPilot.enabled) {
        autoPilot.typingSignature = "";
        return;
      }
      if (autoPilot.typingSignature !== signature) return;
      if (index >= chars.length) {
        node.dispatchEvent(new Event("change", { bubbles: true }));
        autoPilot.typingSignature = "";
        later(() => scan(`typed_${label}`), jitter(150, 300));
        return;
      }
      const char = chars[index];
      index += 1;
      dispatchKeyboard(node, "keydown", char);
      const nextValue = `${node.value || ""}${char}`;
      assignNativeValue(node, nextValue, "insertText", char);
      dispatchKeyboard(node, "keyup", char);
      later(typeNext, jitter(15, 40));
    };
    later(typeNext, jitter(30, 80));
    return true;
  }

  function ensureHumanText(node, value, label) {
    if (!node) return { status: "missing", reason: `${label}_not_found` };
    const desired = String(value || "");
    if (textInputValue(node) === desired) {
      return { status: "done", evidence: textInputValue(node) };
    }
    const signature = `typing:${label}:${desired}`;
    if (autoPilot.typingSignature === signature) {
      return { status: "pending", reason: `${label}_typing`, evidence: textInputValue(node) };
    }
    startHumanTyping(node, desired, label);
    return { status: "pending", reason: `${label}_typing_started`, evidence: textInputValue(node) };
  }

  function clickNextButton() {
    const button = queryAny(FIELD_SELECTORS.submit) || microsoftPrimaryButton();
    if (!button) return false;
    if (isDisabledControl(button)) return false;
    return humanClick(button);
  }

  function microsoftPrimaryButton() {
    const candidates = Array.from(document.querySelectorAll([
      "button",
      "input[type='button']",
      "input[type='submit']",
      "div[role='button']",
      "span[role='button']",
      "a[role='button']",
      "[role='button']",
      "[data-testid]",
      "[id]"
    ].join(","))).filter((node) => node && isVisible(node) && !isDisabledControl(node));
    const primaryTokens = [
      "下一步",
      "继续",
      "确定",
      "next",
      "continue",
      "ok"
    ];
    return candidates.find((node) => {
      const text = buttonText(node);
      const id = lower(node.id || "");
      const testId = lower(node.getAttribute("data-testid") || "");
      const aria = lower(node.getAttribute("aria-label") || "");
      const classes = lower(node.className || "");
      return includesAny(text, primaryTokens)
        || includesAny(aria, primaryTokens)
        || ["nextbutton", "idsibutton9", "idbtn_accept", "acceptbutton"].some((token) => id.includes(token))
        || testId.includes("primary")
        || classes.includes("primary");
    }) || null;
  }

  function selectLikeByText(node, value) {
    if (!node) return false;
    const desired = lower(value);
    const monthNumber = {
      january: "1",
      february: "2",
      march: "3",
      april: "4",
      may: "5",
      june: "6",
      july: "7",
      august: "8",
      september: "9",
      october: "10",
      november: "11",
      december: "12"
    }[desired];
    if (node.tagName && node.tagName.toLowerCase() === "select") {
      const option = Array.from(node.options || []).find((item) => {
        const text = lower(item.text);
        const optionValue = lower(item.value);
        return text.includes(desired)
          || optionValue === desired
          || (monthNumber && (optionValue === monthNumber || optionValue === monthNumber.padStart(2, "0")));
      });
      if (option) {
        node.value = option.value;
        node.dispatchEvent(new Event("input", { bubbles: true }));
        node.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
    setNativeValue(node, value);
    return true;
  }

  function compactText(value) {
    return lower(value).replace(/\s+/g, "").replace(/[年月日]/g, "");
  }

  function containsMonthMarker(text) {
    const raw = lower(text);
    return /月|月份|month|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec/.test(raw);
  }

  function containsDayMarker(text) {
    const raw = lower(text);
    return /日|日期|day/.test(raw);
  }

  function dropdownText(node) {
    if (!node) return "";
    return String(
      node.value
      || node.innerText
      || node.textContent
      || node.getAttribute("aria-label")
      || node.getAttribute("title")
      || ""
    ).trim();
  }

  function isDisabledControl(node) {
    if (!node) return true;
    return Boolean(node.disabled)
      || node.getAttribute("aria-disabled") === "true"
      || node.getAttribute("disabled") !== null;
  }

  function optionNodeText(node) {
    if (!node) return "";
    return String([
      node.innerText,
      node.textContent,
      node.getAttribute("aria-label"),
      node.getAttribute("title"),
      node.getAttribute("data-value"),
      node.getAttribute("value")
    ].find((value) => String(value || "").trim()) || "").trim();
  }

  function controlValueMatches(node, kind, value) {
    if (!node) return false;
    const text = dropdownText(node);
    if (kind === "gender" && looksLikeExpandedGenderMenu(text)) return false;
    return optionMatchesText(text, optionCandidates(kind, value), kind);
  }

  function looksLikeExpandedGenderMenu(text) {
    const compact = compactText(text);
    return compact.includes("女") && compact.includes("男") && (compact.includes("不愿透露") || compact.includes("自定义"));
  }

  function rememberControlAction(signature, holdMs = 2600) {
    const now = Date.now();
    if (autoPilot.lastControlAction === signature && now - autoPilot.lastControlActionAt < holdMs) {
      return false;
    }
    autoPilot.lastControlAction = signature;
    autoPilot.lastControlActionAt = now;
    return true;
  }

  function rememberStepSubmit(signature, holdMs = 30000) {
    const now = Date.now();
    if (autoPilot.submittedStepSignature === signature && now - autoPilot.submittedStepAt < holdMs) {
      return false;
    }
    autoPilot.submittedStepSignature = signature;
    autoPilot.submittedStepAt = now;
    return true;
  }

  function optionCandidates(kind, value) {
    const desired = compactText(value);
    if (kind === "month") {
      const monthMap = {
        january: ["1", "01", "jan", "january", "1月", "一月"],
        february: ["2", "02", "feb", "february", "2月", "二月"],
        march: ["3", "03", "mar", "march", "3月", "三月"],
        april: ["4", "04", "apr", "april", "4月", "四月"],
        may: ["5", "05", "may", "5月", "五月"],
        june: ["6", "06", "jun", "june", "6月", "六月"],
        july: ["7", "07", "jul", "july", "7月", "七月"],
        august: ["8", "08", "aug", "august", "8月", "八月"],
        september: ["9", "09", "sep", "september", "9月", "九月"],
        october: ["10", "oct", "october", "10月", "十月"],
        november: ["11", "nov", "november", "11月", "十一月"],
        december: ["12", "dec", "december", "12月", "十二月"]
      };
      return (monthMap[desired] || [desired]).map(compactText);
    }
    if (kind === "day") {
      const number = String(parseInt(String(value || "1"), 10) || 1);
      return [number, number.padStart(2, "0"), `${number}日`].map(compactText);
    }
    if (kind === "gender") {
      const aliasMap = {
        female: ["female", "woman", "girl", "f", "女", "女性"],
        male: ["male", "man", "boy", "m", "男", "男性"],
        other: ["other", "custom", "nonbinary", "non-binary", "其他", "自定义", "非二元"],
        rathernotsay: [
          "rather not say",
          "prefer not to say",
          "not say",
          "unspecified",
          "unknown",
          "不愿透露",
          "不透露",
          "不想透露",
          "保密"
        ],
        prefernottosay: [
          "rather not say",
          "prefer not to say",
          "not say",
          "unspecified",
          "unknown",
          "不愿透露",
          "不透露",
          "不想透露",
          "保密"
        ]
      };
      return (aliasMap[desired] || [desired]).map(compactText);
    }
    return [desired];
  }

  function optionMatchesText(text, candidates, kind) {
    if (kind === "day" && containsMonthMarker(text)) return false;
    if (kind === "month" && containsDayMarker(text) && !containsMonthMarker(text)) return false;
    const compact = compactText(text);
    if (!compact) return false;
    if (candidates.includes(compact)) return true;
    if (kind === "month") {
      return candidates.some((candidate) => compact === candidate || compact.startsWith(candidate + "/"));
    }
    if (kind === "day") {
      return candidates.some((candidate) => compact === candidate);
    }
    if (kind === "gender") {
      return candidates.some((candidate) => compact === candidate || compact.includes(candidate));
    }
    return candidates.some((candidate) => compact.includes(candidate));
  }

  function controlledOptionRoots(anchorNode) {
    const roots = [];
    const ids = String(
      anchorNode?.getAttribute?.("aria-controls")
      || anchorNode?.getAttribute?.("aria-owns")
      || ""
    ).split(/\s+/).filter(Boolean);
    for (const id of ids) {
      try {
        const root = document.getElementById(id) || document.querySelector(`#${CSS.escape(id)}`);
        if (root && isVisible(root)) roots.push(root);
      } catch (error) {
        // Ignore invalid generated ids.
      }
    }
    return roots;
  }

  function optionSearchNodes(anchorNode) {
    if (anchorNode?.getAttribute?.("aria-expanded") !== "true") return [];
    const roots = controlledOptionRoots(anchorNode);
    const scoped = roots.flatMap((root) => Array.from(root.querySelectorAll("[role='option'], [role='menuitem'], [aria-selected], [data-value], li, button")));
    const scopedNodes = Array.from(new Set(scoped)).filter((node) => (
      node
      && isVisible(node)
      && !isDisabledControl(node)
      && node !== anchorNode
      && !(anchorNode && anchorNode.contains && anchorNode.contains(node))
      && !(anchorNode && node.contains && node.contains(anchorNode))
    ));
    if (scopedNodes.length) return scopedNodes;
    const popupRoots = Array.from(document.querySelectorAll("[role='listbox'], [role='menu'], [aria-label*='Birth'], [aria-label*='出生'], [aria-label*='Gender' i], [aria-label*='性别'], [id*='listbox' i], [id*='dropdown' i]"))
      .filter((node) => node && isVisible(node) && node !== anchorNode && !(anchorNode && anchorNode.contains && anchorNode.contains(node)));
    return Array.from(new Set(popupRoots.flatMap((root) => Array.from(root.querySelectorAll("[role='option'], [role='menuitem'], [aria-selected], [data-value], li, button")))))
      .filter((node) => (
        node
        && isVisible(node)
        && !isDisabledControl(node)
        && node !== anchorNode
        && !(anchorNode && anchorNode.contains && anchorNode.contains(node))
        && !(anchorNode && node.contains && node.contains(anchorNode))
      ));
  }

  function optionMatchScore(node, candidates, kind) {
    const text = optionNodeText(node);
    const compact = compactText(text);
    if (!compact) return 999;
    if (candidates.includes(compact)) return node.getAttribute("role") === "option" ? 0 : 1;
    if (kind === "month" && candidates.some((candidate) => compact.startsWith(candidate + "/"))) return 2;
    return 9;
  }

  function visibleOptionCandidates(kind, value, anchorNode) {
    const candidates = optionCandidates(kind, value);
    return optionSearchNodes(anchorNode)
      .filter((node) => optionMatchesText(optionNodeText(node), candidates, kind))
      .sort((left, right) => optionMatchScore(left, candidates, kind) - optionMatchScore(right, candidates, kind));
  }

  function keySelectOption(node, kind, value) {
    if (!node || !isVisible(node)) return false;
    if (kind === "gender") return false;
    const number = kind === "month"
      ? ({ january: 1, february: 2, march: 3, april: 4, may: 5, june: 6, july: 7, august: 8, september: 9, october: 10, november: 11, december: 12 }[lower(value)] || parseInt(value, 10) || 1)
      : (parseInt(value, 10) || 1);
    try { node.focus({ preventScroll: true }); } catch (error) { try { node.focus(); } catch (_) {} }
    const keys = ["ArrowDown"];
    for (let index = 1; index < Math.max(1, Math.min(31, number)); index += 1) keys.push("ArrowDown");
    keys.push("Enter");
    for (const key of keys) {
      node.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key }));
      node.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, cancelable: true, key }));
    }
    return true;
  }

  function birthControlDescriptor(node) {
    if (!node) return "";
    const attrs = ["id", "name", "aria-label", "placeholder", "title", "data-testid", "autocomplete"]
      .map((name) => node.getAttribute && node.getAttribute(name))
      .filter(Boolean);
    const labels = Array.from(node.labels || []).map((item) => item.innerText || item.textContent || "");
    const parentText = node.parentElement ? String(node.parentElement.innerText || node.parentElement.textContent || "").slice(0, 120) : "";
    return lower([...attrs, ...labels, parentText].join(" "));
  }

  function birthControlScore(node, kind) {
    const desc = birthControlDescriptor(node);
    const idName = lower([
      node.getAttribute && node.getAttribute("id"),
      node.getAttribute && node.getAttribute("name"),
      node.getAttribute && node.getAttribute("data-testid")
    ].filter(Boolean).join(" "));
    const text = lower(dropdownText(node));
    const isTextInput = isTextInputControl(node);
    const isSelectLike = isSelectLikeControl(node);

    if (kind === "year") {
      if (!isTextInput && !isSelectLike) return 99;
      if (/birth.?year|year|usernamereg-year/.test(idName)) return 0;
      if (/birth.?year|year/.test(desc) || /年份|年/.test(desc)) return 1;
      if (/month|day|date|月份|月|日期|日/.test(desc)) return 99;
      return 30;
    }

    if (!isTextInput && !isSelectLike) return 99;
    if (kind === "month") {
      if (/birth.?month|month|usernamereg-month/.test(idName)) return 0;
      if (/birth.?month|month/.test(desc) || /月份|月/.test(desc)) return 1;
      if (/birth.?day|day|date|year|日期|日|年份|年/.test(desc)) return 99;
      if (containsMonthMarker(text)) return 4;
      return 30;
    }

    if (kind === "day") {
      if (/month|usernamereg-month|birth.?month|year|usernamereg-year|birth.?year/.test(idName)) return 99;
      if (/birth.?day|birthday|day|date|usernamereg-day/.test(idName)) return 0;
      if ((/birth.?day|day|date/.test(desc) || /日期|日/.test(desc)) && !(/month|year|月份|月|年份|年/.test(desc))) return 1;
      if (containsMonthMarker(text)) return 99;
      return 30;
    }
    return 99;
  }

  function findBirthControl(kind, fallbackSelectors) {
    const controls = Array.from(document.querySelectorAll([
      "select",
      "input",
      "[role='combobox']",
      "button[aria-haspopup]",
      "[aria-haspopup='listbox']"
    ].join(",")))
      .filter((node) => node && isVisible(node) && !isDisabledControl(node))
      .map((node) => ({ node, score: birthControlScore(node, kind) }))
      .filter((item) => item.score < 20)
      .sort((left, right) => left.score - right.score);
    if (controls.length) return resolveInteractiveControl(controls[0].node);

    const fallback = findBySelectors(fallbackSelectors);
    if (fallback && birthControlScore(fallback, kind) < 99) return resolveInteractiveControl(fallback);
    return resolveInteractiveControl(fallback);
  }

  function birthdayInputValue(kind, value) {
    if (kind === "month") {
      const monthNumber = {
        january: "1",
        february: "2",
        march: "3",
        april: "4",
        may: "5",
        june: "6",
        july: "7",
        august: "8",
        september: "9",
        october: "10",
        november: "11",
        december: "12"
      }[lower(value)] || String(parseInt(String(value || "1"), 10) || 1);
      return monthNumber;
    }
    if (kind === "day") {
      return String(parseInt(String(value || "1"), 10) || 1);
    }
    return String(value || "");
  }

  function selectCustomOption(node, kind, value) {
    if (!node) return { status: "missing", reason: `${kind}_control_not_found` };
    const candidates = optionCandidates(kind, value);
    const current = dropdownText(node);
    if (!(kind === "gender" && looksLikeExpandedGenderMenu(current)) && optionMatchesText(current, candidates, kind)) {
      return { status: "done", evidence: current };
    }
    if (node.tagName && node.tagName.toLowerCase() === "select") {
      const option = Array.from(node.options || []).find((item) => (
        optionMatchesText(item.text, candidates, kind)
        || optionMatchesText(item.value, candidates, kind)
      ));
      if (!option) return { status: "missing", reason: `${kind}_option_not_found` };
      node.value = option.value;
      node.dispatchEvent(new Event("input", { bubbles: true }));
      node.dispatchEvent(new Event("change", { bubbles: true }));
      return { status: "done", evidence: option.text || option.value };
    }
    const isPlainInput = isTextInputControl(node) && !isSelectLikeControl(node);
    // 对 day/month，无论是 plain input 还是 combobox input，优先尝试直接输入
    // Microsoft 注册页的日/月控件是 role="combobox" 的 input，直接输入比点击下拉选项更可靠
    const isComboboxInput = isTextInputControl(node) && isSelectLikeControl(node);
    if ((isPlainInput || isComboboxInput) && (kind === "month" || kind === "day")) {
      const desired = birthdayInputValue(kind, value);
      // 先尝试 setNativeValue 快速路径（对 combobox 特别有效）
      if (isComboboxInput) {
        if (setNativeValue(node, desired) && textInputValue(node) === desired) {
          // 触发 blur 或 Enter 确认选择
          try { node.dispatchEvent(new Event("blur", { bubbles: true })); } catch (_) {}
          return { status: "done", evidence: textInputValue(node) || desired };
        }
      }
      // 回退到逐字模拟输入
      const typed = ensureHumanText(node, desired, `birth_${kind}`);
      if (typed.status === "done") {
        // 对 combobox，输入完成后按 Enter 或 Tab 确认
        if (isComboboxInput) {
          try {
            node.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "Enter" }));
            node.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, cancelable: true, key: "Enter" }));
          } catch (_) {}
        }
        return { status: "done", evidence: typed.evidence || desired };
      }
      return { status: "pending", reason: typed.reason || `${kind}_typing`, evidence: typed.evidence || current };
    }
    const options = visibleOptionCandidates(kind, value, node);
    if (options.length) {
      const signature = `click:${kind}:${compactText(value)}:${compactText(optionNodeText(options[0]))}`;
      if (!rememberControlAction(signature, 800)) {
        return { status: "pending", reason: `${kind}_option_waiting_confirmation`, evidence: optionNodeText(options[0]) };
      }
      humanClick(options[0]);
      return { status: "pending", reason: `${kind}_option_clicked`, evidence: optionNodeText(options[0]) };
    }
    const openSignature = `open:${kind}:${compactText(value)}:${compactText(current)}`;
    if (!rememberControlAction(openSignature, 1800)) {
      return { status: "pending", reason: `${kind}_dropdown_waiting_options`, evidence: current };
    }
    if (humanClick(node)) {
      later(() => {
        if (controlValueMatches(node, kind, value)) return;
        const freshOptions = visibleOptionCandidates(kind, value, node);
        if (freshOptions[0]) {
          humanClick(freshOptions[0]);
          return;
        }
        keySelectOption(node, kind, value);
      }, jitter(200, 450));
      return { status: "pending", reason: `${kind}_dropdown_opened`, evidence: current };
    }
    return { status: "missing", reason: `${kind}_dropdown_not_found`, evidence: current };
  }

  function ensureBirthYear(node, value) {
    const desired = String(value || "2000");
    if (!node) return { status: "missing", reason: "birth_year_not_found" };
    if (textInputValue(node) === desired || compactText(dropdownText(node)) === compactText(desired)) {
      return { status: "done", evidence: dropdownText(node) };
    }
    const signature = `year:${compactText(desired)}:${compactText(dropdownText(node))}`;
    if (!rememberControlAction(signature, 900)) {
      return { status: "pending", reason: "year_waiting_confirmation", evidence: dropdownText(node) };
    }
    if (setNativeValue(node, desired) && textInputValue(node) === desired) {
      return { status: "done", evidence: textInputValue(node) };
    }
    const typed = ensureHumanText(node, desired, "birth_year");
    return typed.status === "done"
      ? { status: "done", evidence: typed.evidence }
      : { status: "pending", reason: typed.reason || "year_typing", evidence: typed.evidence || "" };
  }

  function findBySelectors(selectors) {
    return queryAny(selectors);
  }

  function localUsername(account) {
    const raw = String(account.username || `mx${Date.now()}`).split("@", 1)[0];
    const cleaned = raw.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
    return cleaned.length >= 6 ? cleaned.slice(0, 48) : `mx${randomHexPart(10)}`;
  }

  function usernameValueForNode(node, account) {
    const local = localUsername(account);
    const domain = account.domain || PROVIDER_DOMAIN[account.provider] || autoPilot.domain || "outlook.com";
    const hasDomainControl = Boolean(findBySelectors(["#usernameInput", "#domainDropdownId", "#domainSelect"]));
    if (hasDomainControl) return local;
    if (node && node.matches && node.matches("input[name='email'], input[type='email']")) {
      return `${local}@${domain}`;
    }
    return local;
  }

  function switchToNewEmailIfNeeded() {
    if (findBySelectors(["#usernameInput", "#domainDropdownId", "#domainSelect"])) return false;
    const candidates = Array.from(document.querySelectorAll("a, button, span, div, label"))
      .filter(isVisible)
      .filter((node) => LIVE_SWITCH_TEXT_TOKENS.some((token) => lower(node.innerText || node.textContent || node.getAttribute("aria-label") || "").includes(lower(token))));
    const switchNode = candidates.find((node) => {
      const text = lower(node.innerText || node.textContent || node.getAttribute("aria-label") || "");
      return LIVE_SWITCH_TEXT_TOKENS.some((token) => text.includes(lower(token)));
    });
    if (!switchNode) return false;
    switchNode.click();
    return true;
  }

  function selectMicrosoftDomain(account) {
    const domain = account.domain || autoPilot.domain || "outlook.com";
    const select = findBySelectors(["#domainSelect", "select[name='LiveDomainBoxList']"]);
    if (select && select.tagName && select.tagName.toLowerCase() === "select") {
      const option = Array.from(select.options || []).find((item) => lower(item.text).includes(domain) || lower(item.value).includes(domain));
      if (option) {
        select.value = option.value;
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
    const dropdown = findBySelectors(["#domainDropdownId", "[aria-label*='domain' i]", "[role='combobox']"]);
    if (!dropdown) return false;
    const current = lower(dropdown.innerText || dropdown.textContent || dropdown.getAttribute("aria-label") || "");
    if (current.includes(domain)) return true;
    humanClick(dropdown);
    later(() => {
      const options = Array.from(document.querySelectorAll("[role='option'], button, span, div"))
        .filter(isVisible)
        .filter((node) => lower(node.innerText || node.textContent || "").includes(domain));
      if (options[0]) humanClick(options[0]);
    }, jitter(240, 680));
    return true;
  }

  function isYahooCreatePage() {
    return lower(location.hostname).includes("login.yahoo.com")
      && lower(location.pathname || location.href).includes("/account/create");
  }

  function fillBirthdateFields(account, activeStep) {
    const fallbackBirthday = randomAdultBirthday();
    const yearValue = account.birthYear || fallbackBirthday.birthYear;
    const monthValue = account.birthMonth || fallbackBirthday.birthMonth;
    const dayValue = account.birthDay || fallbackBirthday.birthDay;
    account.birthYear = yearValue;
    account.birthMonth = monthValue;
    account.birthDay = dayValue;
    const month = findBirthControl("month", [
      "select[name='BirthMonth']",
      "#BirthMonth",
      "#BirthMonthDropdown",
      "[aria-label='Birth month']",
      "[aria-label*='Birth month' i]",
      "input[aria-label*='Birth month' i]",
      "input[aria-label*='month' i]",
      "[aria-label*='month' i][role='combobox']",
      "[aria-label*='月份']",
      "input[aria-label*='月份']",
      "input[aria-label*='月']",
      "[aria-label*='月'][role='combobox']",
      "#month",
      "#usernamereg-month"
    ]);
    const day = findBirthControl("day", [
      "select[name='BirthDay']",
      "#BirthDay",
      "#BirthDayDropdown",
      "[aria-label='Birth day']",
      "[aria-label*='Birth day' i]",
      "input[aria-label*='Birth day' i]",
      "input[aria-label*='day' i]",
      "[aria-label*='day' i][role='combobox']",
      "[aria-label*='日期']",
      "input[aria-label*='日期']",
      "input[aria-label*='日']",
      "[aria-label*='日'][role='combobox']",
      "#day",
      "#usernamereg-day"
    ]);
    const year = findBirthControl("year", [
      "input[name='BirthYear']",
      "#BirthYear",
      "[aria-label='Birth year']",
      "input[aria-label*='Birth year' i]",
      "input[aria-label*='year' i]",
      "input[aria-label*='年份']",
      "input[placeholder*='Year' i]",
      "input[placeholder*='年']",
      "#year",
      "#usernamereg-year"
    ]);
    const gender = resolveInteractiveControl(findBySelectors([
      "#gender",
      "select[name='gender']",
      "[aria-label*='Gender' i]",
      "[aria-label*='gender' i]",
      "[aria-label*='性别']"
    ]));
    const yearState = ensureBirthYear(year, yearValue);
    if (yearState.status === "pending") {
      return { ok: true, complete: false, reason: "Filling birth year, waiting for page confirmation", activeStep, evidence: yearState.evidence || "", expected: yearValue };
    }
    if (yearState.status !== "done") {
      return { ok: false, complete: false, reason: "Could not fill birth year", activeStep, detail: yearState.reason || "", expected: yearValue };
    }
    const monthState = selectCustomOption(month, "month", monthValue);
    if (monthState.status === "pending") {
      return { ok: true, complete: false, reason: "Selecting birth month, waiting for page confirmation", activeStep, evidence: monthState.evidence || "", year: yearValue, expected: monthValue };
    }
    if (monthState.status !== "done") {
      return { ok: false, complete: false, reason: "Could not select birth month", activeStep, detail: monthState.reason || "", expected: monthValue };
    }
    const dayState = selectCustomOption(day, "day", dayValue);
    if (dayState.status === "pending") {
      return { ok: true, complete: false, reason: "Selecting birth day, waiting for page confirmation", activeStep, evidence: dayState.evidence || "", month: monthState.evidence || "", year: yearValue, expected: dayValue };
    }
    if (dayState.status !== "done") {
      return { ok: false, complete: false, reason: "Could not select birth day", activeStep, detail: dayState.reason || "", expected: dayValue };
    }
    const genderValue = account.gender || "Rather not say";
    const genderState = gender ? selectCustomOption(gender, "gender", genderValue) : { status: "done", evidence: "" };
    if (genderState.status === "pending") {
      return { ok: true, complete: false, reason: "Selecting gender, waiting for page confirmation", activeStep, evidence: genderState.evidence || "", month: monthState.evidence || "", day: dayState.evidence || "", year: yearValue, expected: genderValue };
    }
    if (gender && genderState.status !== "done") {
      return { ok: false, complete: false, reason: "Could not select gender", activeStep, detail: genderState.reason || "", expected: genderValue };
    }
    return {
      ok: true,
      complete: true,
      reason: "Birthdate fields are complete",
      activeStep,
      month: monthState.evidence,
      day: dayState.evidence,
      year: yearValue
    };
  }

  function fillYahooCreateForm(account, activeStep) {
    if (!isYahooCreatePage()) return null;
    if (!account.firstName || !account.lastName) {
      Object.assign(account, randomAccountName());
    }
    const first = findBySelectors([
      "#usernamereg-firstName",
      "input[name='firstName']",
      "input[name='FirstName']",
      "input[autocomplete='given-name']",
      "#firstName"
    ]);
    const last = findBySelectors([
      "#usernamereg-lastName",
      "input[name='lastName']",
      "input[name='LastName']",
      "input[autocomplete='family-name']",
      "#lastName"
    ]);
    const usernameNode = findBySelectors([
      "#usernamereg-userId",
      "input[name='userId']",
      "input[name='username']",
      "input[autocomplete='username']"
    ]) || findBySelectors(FIELD_SELECTORS.username);
    const passwordNode = findBySelectors([
      "#usernamereg-password",
      "input[name='password']",
      "input[autocomplete='new-password']",
      "input[type='password']"
    ]);
    const firstState = ensureHumanText(first, account.firstName, "yahoo_first_name");
    if (firstState.status === "pending") {
      return { ok: true, reason: "Filling Yahoo first name, waiting for page confirmation", activeStep, firstName: account.firstName };
    }
    if (firstState.status !== "done") {
      return { ok: false, reason: "Yahoo first name field was not found", activeStep };
    }
    const lastState = ensureHumanText(last, account.lastName, "yahoo_last_name");
    if (lastState.status === "pending") {
      return { ok: true, reason: "Filling Yahoo last name, waiting for page confirmation", activeStep, lastName: account.lastName };
    }
    if (lastState.status !== "done") {
      return { ok: false, reason: "Yahoo last name field was not found", activeStep };
    }
    const username = usernameValueForNode(usernameNode, account);
    const usernameState = ensureHumanText(usernameNode, username, "yahoo_username");
    if (usernameState.status === "pending") {
      return { ok: true, reason: "Filling Yahoo username, waiting for page confirmation", activeStep, username };
    }
    if (usernameState.status !== "done") {
      return { ok: false, reason: "Yahoo username field was not found", activeStep, username };
    }
    const password = account.password || "Nj2026Flow!8192";
    const passwordState = ensureHumanText(passwordNode, password, "yahoo_password");
    if (passwordState.status === "pending") {
      return { ok: true, reason: "Filling Yahoo password, waiting for page confirmation", activeStep };
    }
    if (passwordState.status !== "done") {
      return { ok: false, reason: "Yahoo password field was not found", activeStep };
    }
    const birthState = fillBirthdateFields(account, activeStep);
    if (!birthState.complete) return birthState;
    if (clickNextButton()) {
      return {
        ok: true,
        reason: "Filled all Yahoo required fields and clicked Next",
        activeStep,
        username,
        month: birthState.month,
        day: birthState.day,
        year: birthState.year
      };
    }
    return {
      ok: false,
      reason: "Yahoo required fields are complete, but Next is not clickable yet",
      activeStep,
      username,
      month: birthState.month,
      day: birthState.day,
      year: birthState.year
    };
  }

  function gmailLocalUsername(account) {
    return localUsername(account).replace(/[^a-zA-Z0-9.]/g, "").slice(0, 30) || localUsername(account);
  }

  function gmailNextButton() {
    const candidates = Array.from(document.querySelectorAll("button, div[role='button'], input[type='button'], input[type='submit']"))
      .filter((node) => node && isVisible(node) && !isDisabledControl(node));
    const preferred = candidates.find((node) => includesAny(lower(buttonText(node) || node.innerText || node.textContent || node.value || ""), ["下一步", "next"]));
    return preferred || queryAny(FIELD_SELECTORS.submit);
  }

  function clickGmailNextButton() {
    const button = gmailNextButton();
    if (!button) return false;
    if (button.disabled || button.getAttribute("aria-disabled") === "true") return false;
    return humanClick(button);
  }

  function fillGmailProfile(account, activeStep) {
    if (!account.firstName || !account.lastName) {
      Object.assign(account, randomAccountName());
    }
    const first = findBySelectors(GMAIL_FIELD_SELECTORS.firstName);
    const last = findBySelectors(GMAIL_FIELD_SELECTORS.lastName);
    const firstState = ensureHumanText(first, account.firstName, "gmail_first_name");
    if (firstState.status === "pending") {
      return { ok: true, reason: "正在填写 Gmail 名字，等待页面确认", activeStep, firstName: account.firstName };
    }
    if (firstState.status !== "done") {
      return { ok: false, reason: "未找到 Gmail 名字输入框", activeStep };
    }
    const lastState = ensureHumanText(last, account.lastName, "gmail_last_name");
    if (lastState.status === "pending") {
      return { ok: true, reason: "正在填写 Gmail 姓氏，等待页面确认", activeStep, lastName: account.lastName };
    }
    if (lastState.status !== "done") {
      return { ok: false, reason: "未找到 Gmail 姓氏输入框", activeStep };
    }
    if (clickGmailNextButton()) return { ok: true, reason: "已填写 Gmail 姓名并点击下一步", activeStep };
    return { ok: false, reason: "Gmail 姓名已填完整，但下一步按钮尚不可点击", activeStep };
  }

  function fillGmailBirthdate(account, activeStep) {
    const birthState = fillBirthdateFields(account, activeStep);
    if (!birthState.complete) return birthState;
    if (clickGmailNextButton()) {
      return {
        ok: true,
        reason: "已确认 Gmail 基本信息并点击下一步",
        activeStep,
        month: birthState.month,
        day: birthState.day,
        year: birthState.year
      };
    }
    return {
      ok: false,
      reason: "Gmail 生日和性别已填完整，但下一步按钮尚不可点击",
      activeStep,
      month: birthState.month,
      day: birthState.day,
      year: birthState.year
    };
  }

  function fillGmailUsername(account, activeStep) {
    const node = findBySelectors(GMAIL_FIELD_SELECTORS.username);
    const username = gmailLocalUsername(account);
    const usernameState = ensureHumanText(node, username, "gmail_username");
    if (usernameState.status === "pending") {
      return { ok: true, reason: "正在填写 Gmail 用户名，等待页面确认", activeStep, username };
    }
    if (usernameState.status !== "done") {
      return { ok: false, reason: "未找到 Gmail 用户名输入框", activeStep, username };
    }
    if (clickGmailNextButton()) return { ok: true, reason: "已填写 Gmail 用户名并点击下一步", activeStep, username };
    return { ok: false, reason: "Gmail 用户名已填完整，但下一步按钮尚不可点击", activeStep, username };
  }

  function fillGmailPassword(account, activeStep) {
    const nodes = Array.from(document.querySelectorAll(GMAIL_FIELD_SELECTORS.password.join(","))).filter(isVisible);
    const password = account.password || "Nj2026Flow!8192";
    const primary = nodes[0] || findBySelectors(GMAIL_FIELD_SELECTORS.password);
    const secondary = nodes.find((node) => node !== primary && lower(node.getAttribute("name") || "").includes("again")) || nodes[1] || null;
    const firstState = ensureHumanText(primary, password, "gmail_password");
    if (firstState.status === "pending") {
      return { ok: true, reason: "正在填写 Gmail 密码，等待页面确认", activeStep };
    }
    if (firstState.status !== "done") {
      return { ok: false, reason: "未找到 Gmail 密码输入框", activeStep };
    }
    if (secondary) {
      const confirmState = ensureHumanText(secondary, password, "gmail_password_confirm");
      if (confirmState.status === "pending") {
        return { ok: true, reason: "正在确认 Gmail 密码，等待页面确认", activeStep };
      }
    }
    if (clickGmailNextButton()) return { ok: true, reason: "已填写 Gmail 密码并点击下一步", activeStep };
    return { ok: false, reason: "Gmail 密码已填完整，但下一步按钮尚不可点击", activeStep };
  }

  function fillGmailCurrentStep(account, activeStep) {
    if (activeStep === GMAIL_PROFILE_STEP) return fillGmailProfile(account, activeStep);
    if (activeStep === GMAIL_BIRTHDATE_STEP) return fillGmailBirthdate(account, activeStep);
    if (activeStep === GMAIL_USERNAME_STEP) return fillGmailUsername(account, activeStep);
    if (activeStep === GMAIL_PASSWORD_STEP) return fillGmailPassword(account, activeStep);
    return null;
  }

  function genericProviderNextButton() {
    const candidates = Array.from(document.querySelectorAll("button, div[role='button'], input[type='button'], input[type='submit'], a[role='button']"))
      .filter((node) => node && isVisible(node) && !isDisabledControl(node));
    const preferred = candidates.find((node) => includesAny(lower(buttonText(node) || node.innerText || node.textContent || node.value || ""), [
      "next",
      "continue",
      "create",
      "register",
      "sign up",
      "signup",
      "submit",
      "agree",
      "다음",
      "가입",
      "下一步",
      "继续",
      "注册",
      "同意"
    ]));
    return preferred || queryAny(FIELD_SELECTORS.submit);
  }

  function clickGenericProviderNextButton() {
    const button = genericProviderNextButton();
    if (!button) return false;
    if (button.disabled || button.getAttribute("aria-disabled") === "true") return false;
    return humanClick(button);
  }

  function fillGenericName(account, activeStep) {
    if (!account.firstName || !account.lastName) Object.assign(account, randomAccountName());
    const first = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.firstName);
    const last = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.lastName);
    const full = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.fullName);
    if (first || last) {
      const firstState = ensureHumanText(first, account.firstName, "generic_first_name");
      if (firstState.status === "pending") return { ok: true, reason: "Filling provider first name", activeStep };
      const lastState = ensureHumanText(last, account.lastName, "generic_last_name");
      if (lastState.status === "pending") return { ok: true, reason: "Filling provider last name", activeStep };
      if (firstState.status === "done" || lastState.status === "done") {
        if (clickGenericProviderNextButton()) return { ok: true, reason: "Filled provider name and clicked next", activeStep };
        return { ok: true, reason: "Provider name fields are filled; waiting for next control", activeStep };
      }
    }
    if (full) {
      const state = ensureHumanText(full, `${account.firstName} ${account.lastName}`, "generic_full_name");
      if (state.status === "pending") return { ok: true, reason: "Filling provider full name", activeStep };
      if (state.status === "done" && clickGenericProviderNextButton()) return { ok: true, reason: "Filled provider full name and clicked next", activeStep };
      if (state.status === "done") return { ok: true, reason: "Provider full name is filled", activeStep };
    }
    return { ok: false, reason: "Provider name fields were not found", activeStep };
  }

  function fillGenericUsername(account, activeStep) {
    const node = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.username);
    const username = usernameValueForNode(node, account);
    const state = ensureHumanText(node, username, "generic_username");
    if (state.status === "pending") return { ok: true, reason: "Filling provider username", activeStep, username };
    if (state.status !== "done") return { ok: false, reason: "Provider username field was not found", activeStep, username };
    if (clickGenericProviderNextButton()) return { ok: true, reason: "Filled provider username and clicked next", activeStep, username };
    return { ok: true, reason: "Provider username is filled; waiting for next control", activeStep, username };
  }

  function gmxHasCheckButton() {
    return Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit']"))
      .filter((node) => isVisible(node) && !isDisabledControl(node))
      .some((node) => includesAny(lower(buttonText(node) || node.innerText || node.textContent || node.value || ""), ["check", "prüfen"]));
  }

  function findGmxUsernameField() {
    const direct = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.username);
    if (direct) return direct;
    const labels = Array.from(document.querySelectorAll("label"))
      .filter(isVisible)
      .filter((node) => includesAny(lower(node.innerText || node.textContent || ""), ["desired e-mail address", "email address", "e-mail address"]));
    for (const label of labels) {
      const nested = label.querySelector("input, textarea");
      if (nested && isVisible(nested) && isTextInputControl(nested)) return nested;
      const forId = label.getAttribute("for");
      if (forId) {
        const linked = document.getElementById(forId);
        if (linked && isVisible(linked) && isTextInputControl(linked)) return linked;
      }
    }
    const candidates = Array.from(document.querySelectorAll("input[type='text'], input:not([type]), textarea"))
      .filter((node) => isVisible(node) && isTextInputControl(node));
    return candidates[0] || null;
  }

  function gmxLooksLikeProfileBirthdateStep(elements = {}) {
    if (elements.genericProfile || elements.genericBirthdate) return true;
    const bodyText = lower(document.body ? document.body.innerText || "" : "");
    if (bodyText.includes("complete your entry")) return true;
    const titleChoices = Array.from(document.querySelectorAll("input[type='radio']")).filter(isVisible);
    const selects = Array.from(document.querySelectorAll("select")).filter(isVisible);
    return titleChoices.length >= 2 && selects.length >= 1;
  }

  function fillGmxUsername(account, activeStep) {
    const node = findGmxUsernameField();
    const username = usernameValueForNode(node, account);
    const state = ensureHumanText(node, username, "gmx_username");
    if (state.status === "pending") return { ok: true, reason: "Filling GMX username", activeStep, username };
    if (state.status !== "done") return { ok: false, reason: "GMX username field was not found", activeStep, username };
    const checkButton = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit']"))
      .filter((item) => isVisible(item) && !isDisabledControl(item))
      .find((item) => includesAny(lower(buttonText(item) || item.innerText || item.textContent || item.value || ""), ["check", "prüfen"]));
    if (checkButton && humanClick(checkButton)) {
      return { ok: true, reason: "Filled GMX username and clicked Check", activeStep, username };
    }
    if (clickGenericProviderNextButton()) return { ok: true, reason: "Filled GMX username and clicked next", activeStep, username };
    return { ok: true, reason: "GMX username is filled; waiting for availability check", activeStep, username };
  }

  function protonTextInputCandidates() {
    return Array.from(document.querySelectorAll("input, textarea"))
      .filter((node) => isVisible(node) && isTextInputControl(node));
  }

  function protonNonPasswordInputs() {
    return Array.from(document.querySelectorAll("input, textarea"))
      .filter((node) => node && isVisible(node) && isTextInputControl(node))
      .filter((node) => lower(node.getAttribute("type") || "text") !== "password")
      .filter((node) => !lower([node.name, node.id, node.getAttribute("autocomplete")].filter(Boolean).join(" ")).includes("password"));
  }

  function protonInputDebug() {
    return Array.from(document.querySelectorAll("input, textarea")).slice(0, 12).map((node) => nodeEvidence(node)).join(" | ");
  }

  function protonUsernameValueNode(username) {
    const desired = String(username || "").trim();
    if (!desired) return null;
    return protonNonPasswordInputs().find((node) => textInputValue(node) === desired) || null;
  }

  function protonFieldText(node) {
    if (!node) return "";
    const pieces = [
      node.id,
      node.name,
      node.placeholder,
      node.getAttribute("aria-label"),
      node.getAttribute("data-testid"),
      node.getAttribute("autocomplete"),
      node.value
    ];
    let parent = node.parentElement;
    for (let depth = 0; parent && depth < 4; depth += 1, parent = parent.parentElement) {
      pieces.push(parent.innerText || parent.textContent || "");
    }
    return lower(pieces.filter(Boolean).join(" "));
  }

  function findProtonUsernameField() {
    const direct = queryAny([
      "input[name='username']",
      "input[id*='username' i]",
      "input[aria-label*='username' i]",
      "input[aria-label*='用户名']",
      "input[placeholder*='username' i]",
      "input[placeholder*='用户名']",
      "input[data-testid*='username' i]",
      "input[data-testid*='mailbox' i]",
      "input[autocomplete='username']"
    ]);
    if (direct) return direct;
    const dataTestInputs = protonNonPasswordInputs().filter((node) => {
      const type = lower(node.getAttribute("type") || "text");
      return type !== "password" && node.getAttribute("data-testid") === "input-input-element";
    });
    const domainControl = Array.from(document.querySelectorAll("button, [role='button'], [role='combobox'], select, span, div"))
      .filter((node) => node && isVisible(node))
      .find((node) => includesAny(lower(node.innerText || node.textContent || node.getAttribute?.("aria-label") || ""), ["@proton", "proton.me", "protonmail"]));
    if (domainControl) {
      const domainRect = domainControl.getBoundingClientRect();
      const sameRowInputs = dataTestInputs.concat(protonNonPasswordInputs())
        .filter((node, index, nodes) => nodes.indexOf(node) === index)
        .filter((node) => lower(node.getAttribute("type") || "text") !== "password")
        .map((node) => ({ node, rect: node.getBoundingClientRect() }))
        .filter((item) => Math.abs((item.rect.top + item.rect.bottom) / 2 - (domainRect.top + domainRect.bottom) / 2) < Math.max(42, domainRect.height * 1.5))
        .filter((item) => item.rect.left < domainRect.right && item.rect.right <= domainRect.right + 8)
        .sort((left, right) => Math.abs(left.rect.right - domainRect.left) - Math.abs(right.rect.right - domainRect.left));
      if (sameRowInputs[0]) return sameRowInputs[0].node;
    }
    if (dataTestInputs[0]) return dataTestInputs[0];
    const candidates = protonNonPasswordInputs();
    return candidates.find((node) => includesAny(protonFieldText(node), ["username", "用户名", "@proton", "proton.me", "protonmail"]))
      || candidates[0]
      || null;
  }

  function protonPlanText(node) {
    return lower([
      node && (node.innerText || node.textContent || ""),
      node && node.getAttribute && node.getAttribute("aria-label"),
      node && node.getAttribute && node.getAttribute("data-testid")
    ].filter(Boolean).join(" "));
  }

  function protonPlanKind(text) {
    const value = lower(text);
    if (!value) return "";
    if (value.includes("mail plus") || value.includes("unlimited") || value.includes("family")) return "paid";
    const hasZeroPrice = /(^|[^0-9])0([^0-9]|$)/.test(value)
      || /[¥￥$€£₩₽₹]\s*0/.test(value)
      || /(sgd|usd|jpy|eur|gbp|cad|aud)\s*0/.test(value);
    if (value.includes("free") && hasZeroPrice) return "free";
    return "";
  }

  function protonPlanCardCandidates() {
    return Array.from(document.querySelectorAll("label, [role='radio'], [data-testid], section, article, div"))
      .filter((node) => node && isVisible(node))
      .map((node) => {
        const rect = node.getBoundingClientRect();
        return {
          node,
          rect,
          text: protonPlanText(node),
          area: Math.max(1, rect.width * rect.height)
        };
      })
      .filter((item) => item.area >= 1200 && item.area <= 180000)
      .filter((item) => protonPlanKind(item.text) === "free")
      .filter((item) => !includesAny(item.text, ["mail plus", "unlimited", "family"]))
      .sort((a, b) => {
        const aHasRadio = a.node.querySelector && a.node.querySelector("input[type='radio'], [role='radio']");
        const bHasRadio = b.node.querySelector && b.node.querySelector("input[type='radio'], [role='radio']");
        if (Boolean(aHasRadio) !== Boolean(bHasRadio)) return aHasRadio ? -1 : 1;
        return a.area - b.area;
      });
  }

  function protonPlanCardFor(node) {
    let current = node;
    let best = null;
    for (let depth = 0; current && depth < 7; depth += 1, current = current.parentElement) {
      const text = protonPlanText(current);
      const kind = protonPlanKind(text);
      if (!kind) continue;
      if (kind === "free") best = current;
      if (kind === "paid") return best;
    }
    return best;
  }

  function protonFreePlanControl() {
    const radios = Array.from(document.querySelectorAll("input[type='radio'], [role='radio']"))
      .filter((node) => node && isVisible(node) && !isDisabledControl(node));
    for (const radio of radios) {
      const card = protonPlanCardFor(radio);
      if (!card) continue;
      const text = protonPlanText(card);
      if (protonPlanKind(text) === "free") return radio;
    }
    const card = protonPlanCardCandidates()[0]?.node || null;
    if (!card) return null;
    return (card.querySelector && card.querySelector("input[type='radio'], [role='radio'], button")) || card;
  }

  function setNativeChecked(node, checked = true) {
    if (!node || node.type !== "radio") return false;
    const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked");
    if (!descriptor || typeof descriptor.set !== "function") return false;
    descriptor.set.call(node, Boolean(checked));
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    return node.checked === Boolean(checked);
  }

  function protonSelectedPlanKind() {
    const selectedControls = Array.from(document.querySelectorAll("input[type='radio']:checked, [role='radio'][aria-checked='true'], [aria-selected='true']"))
      .filter((node) => node);
    for (const node of selectedControls) {
      const card = protonPlanCardFor(node);
      const kind = card ? protonPlanKind(protonPlanText(card)) : "";
      if (kind) return kind;
    }
    const selectedCards = protonPlanCardCandidates()
      .map((item) => item.node)
      .filter((node) => {
        const marker = lower([
          node.getAttribute && node.getAttribute("class"),
          node.getAttribute && node.getAttribute("data-testid"),
          node.getAttribute && node.getAttribute("aria-label")
        ].filter(Boolean).join(" "));
        return includesAny(marker, ["selected", "active", "checked"]);
      });
    if (selectedCards.length) return "free";
    return "";
  }

  function ensureProtonFreePlan() {
    const selectedKind = protonSelectedPlanKind();
    if (selectedKind === "free") return { status: "done", evidence: "free_selected" };
    const target = protonFreePlanControl();
    if (!target) return { status: "missing", evidence: "free_plan_not_found" };
    const card = protonPlanCardFor(target) || (protonPlanCardCandidates()[0]?.node || null);
    const nested = (card && card.querySelector && card.querySelector("input[type='radio'], [role='radio'], button")) || null;
    const radio = target.matches && target.matches("input[type='radio']")
      ? target
      : (card && card.querySelector && card.querySelector("input[type='radio']"));
    if (setNativeChecked(radio, true)) {
      humanClick(radio);
      return { status: "pending", evidence: card ? nodeEvidence(card) : nodeEvidence(radio) };
    }
    if (humanClick(target) || humanClick(nested) || humanClick(card)) {
      return { status: "pending", evidence: card ? nodeEvidence(card) : nodeEvidence(target) };
    }
    return { status: "failed", evidence: nodeEvidence(target) };
  }

  function fillProtonSignupForm(account, activeStep) {
    const planState = ensureProtonFreePlan();
    const username = localUsername(account);
    const alreadyFilledUsernameNode = protonUsernameValueNode(username);
    const usernameNode = alreadyFilledUsernameNode || findProtonUsernameField();
    const usernameState = alreadyFilledUsernameNode
      ? { status: "done", evidence: nodeEvidence(alreadyFilledUsernameNode) }
      : usernameNode
      ? ensureHumanText(usernameNode, username, "proton_username")
      : { status: "missing", evidence: "" };
    if (usernameState.status === "pending") return { ok: true, reason: "Filling Proton username", activeStep, username };
    if (usernameState.status !== "done") {
      const filledAfterTypingNode = protonUsernameValueNode(username);
      if (filledAfterTypingNode) {
        return { ok: true, reason: "Proton username is filled; continuing on next pass", activeStep, username, evidence: nodeEvidence(filledAfterTypingNode) };
      }
      const fallbackNode = protonNonPasswordInputs()
        .filter((node) => !textInputValue(node))
        .sort((left, right) => left.getBoundingClientRect().top - right.getBoundingClientRect().top)[0] || null;
      if (fallbackNode) {
        const fallbackState = ensureHumanText(fallbackNode, username, "proton_username_fallback");
        if (fallbackState.status === "pending") return { ok: true, reason: "Filling Proton username with fallback input", activeStep, username, evidence: nodeEvidence(fallbackNode) };
        if (fallbackState.status === "done") return { ok: true, reason: "Filled Proton username with fallback input; waiting for next pass", activeStep, username, evidence: nodeEvidence(fallbackNode) };
      }
      return { ok: false, reason: "Proton username field was not found", activeStep, username, evidence: usernameState.evidence || protonInputDebug() || "" };
    }
    const confirmedUsernameNode = protonUsernameValueNode(username) || usernameNode;
    if (!confirmedUsernameNode || textInputValue(confirmedUsernameNode) !== username) {
      return { ok: true, reason: "Proton username is still empty; retrying before submit", activeStep, username, evidence: protonInputDebug() || "" };
    }
    const passwordResult = fillGenericPassword(account, activeStep, { skipSubmit: true });
    if (passwordResult.ok && /Filling|Confirming/.test(passwordResult.reason || "")) return passwordResult;
    if (!passwordResult.ok) return passwordResult;
    const finalPlanState = protonSelectedPlanKind() === "free" ? { status: "done", evidence: "free_selected" } : ensureProtonFreePlan();
    if (finalPlanState.status !== "done") {
      return {
        ok: true,
        reason: "Filled Proton fields; waiting for Proton Free plan selection",
        activeStep,
        username,
        evidence: finalPlanState.evidence || planState.evidence || ""
      };
    }
    if (clickGenericProviderNextButton()) return { ok: true, reason: "Filled Proton Free signup form and clicked next", activeStep, username };
    return { ok: true, reason: "Filled Proton Free signup form; waiting for next control", activeStep, username };
  }

  function fillGenericPassword(account, activeStep, options = {}) {
    const password = account.password || randomPassword();
    account.password = password;
    const nodes = Array.from(document.querySelectorAll(GENERIC_PROVIDER_FIELD_SELECTORS.password.join(","))).filter(isVisible);
    const primary = nodes[0] || findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.password);
    const firstState = ensureHumanText(primary, password, "generic_password");
    if (firstState.status === "pending") return { ok: true, reason: "Filling provider password", activeStep };
    if (firstState.status !== "done") return { ok: false, reason: "Provider password field was not found", activeStep };
    const confirmationNodes = nodes.filter((node) => node !== primary);
    for (let index = 0; index < confirmationNodes.length; index += 1) {
      const confirmState = ensureHumanText(confirmationNodes[index], password, `generic_password_confirm_${index}`);
      if (confirmState.status === "pending") return { ok: true, reason: "Confirming provider password", activeStep };
    }
    if (!options.skipSubmit && clickGenericProviderNextButton()) return { ok: true, reason: "Filled provider password and clicked next", activeStep };
    return { ok: true, reason: "Provider password is filled; waiting for next control", activeStep };
  }

  function fillGenericBirthdate(account, activeStep) {
    const birthState = fillBirthdateFields(account, activeStep);
    if (!birthState.complete) return birthState;
    if (clickGenericProviderNextButton()) {
      return { ok: true, reason: "Filled provider birthdate and clicked next", activeStep, month: birthState.month, day: birthState.day, year: birthState.year };
    }
    return { ok: true, reason: "Provider birthdate is filled; waiting for next control", activeStep, month: birthState.month, day: birthState.day, year: birthState.year };
  }

  function fillGenericGender(account, activeStep) {
    const gender = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.gender);
    const genderValue = account.gender || "Rather not say";
    const genderState = gender ? selectCustomOption(gender, "gender", genderValue) : { status: "done", evidence: "" };
    if (genderState.status === "pending") {
      return { ok: true, reason: "Selecting provider gender, waiting for page confirmation", activeStep, evidence: genderState.evidence || "", expected: genderValue };
    }
    if (gender && genderState.status !== "done") {
      return { ok: false, reason: "Could not select provider gender", activeStep, detail: genderState.reason || "", expected: genderValue };
    }
    if (clickGenericProviderNextButton()) return { ok: true, reason: "Selected provider gender and clicked next", activeStep, expected: genderValue };
    return { ok: true, reason: "Provider gender is selected; waiting for next control", activeStep, expected: genderValue };
  }

  function fillGenericRecovery(account, activeStep) {
    const node = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.recovery);
    const recoveryEmail = account.recoveryEmail || account.recovery_email || account.email || "";
    if (!recoveryEmail) return { ok: false, reason: "No recovery email is cached for this provider step", activeStep };
    const state = ensureHumanText(node, recoveryEmail, "generic_recovery_email");
    if (state.status === "pending") return { ok: true, reason: "Filling provider recovery email", activeStep };
    if (state.status !== "done") return { ok: false, reason: "Provider recovery email field was not found", activeStep };
    if (clickGenericProviderNextButton()) return { ok: true, reason: "Filled provider recovery email and clicked next", activeStep };
    return { ok: true, reason: "Provider recovery email is filled; waiting for next control", activeStep };
  }

  function fillGenericTerms(activeStep) {
    const controls = Array.from(document.querySelectorAll(GENERIC_PROVIDER_FIELD_SELECTORS.terms.join(","))).filter(isVisible);
    const target = controls.find((node) => {
      const text = lower(node.innerText || node.textContent || node.getAttribute("aria-label") || "");
      return includesAny(text, ["terms", "agree", "privacy", "동의", "同意", "条款", "terms of service"]);
    }) || controls[0] || null;
    if (!target) return { ok: false, reason: "Provider terms checkbox was not found", activeStep };
    if (target.checked || target.getAttribute("aria-checked") === "true") {
      if (clickGenericProviderNextButton()) return { ok: true, reason: "Provider terms already accepted and clicked next", activeStep };
      return { ok: true, reason: "Provider terms already accepted", activeStep };
    }
    if (humanClick(target)) return { ok: true, reason: "Clicked provider terms control", activeStep };
    return { ok: false, reason: "Provider terms control was not clickable", activeStep };
  }

  function fillGmxProfileBirthdate(account, activeStep) {
    if (!account.firstName || !account.lastName) Object.assign(account, randomAccountName());
    const first = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.firstName);
    const last = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.lastName);
    const firstState = ensureHumanText(first, account.firstName, "gmx_first_name");
    if (firstState.status === "pending") return { ok: true, reason: "Filling GMX first name", activeStep };
    const lastState = ensureHumanText(last, account.lastName, "gmx_last_name");
    if (lastState.status === "pending") return { ok: true, reason: "Filling GMX last name", activeStep };
    const birthState = fillBirthdateFields(account, activeStep);
    if (!birthState.complete) {
      return {
        ...birthState,
        ok: firstState.status === "done" || lastState.status === "done",
        reason: birthState.reason || "GMX name fields are filled; waiting for birthdate controls",
        activeStep
      };
    }
    if (clickGenericProviderNextButton()) {
      return { ok: true, reason: "Filled GMX profile and birthdate and clicked next", activeStep };
    }
    return { ok: true, reason: "GMX profile and birthdate are filled; waiting for next control", activeStep };
  }

  function fillAolAccountForm(account, activeStep) {
    if (!account.firstName || !account.lastName) Object.assign(account, randomAccountName());
    const firstState = ensureHumanText(findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.firstName), account.firstName, "aol_first_name");
    if (firstState.status === "pending") return { ok: true, reason: "Filling AOL first name", activeStep };
    const lastState = ensureHumanText(findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.lastName), account.lastName, "aol_last_name");
    if (lastState.status === "pending") return { ok: true, reason: "Filling AOL last name", activeStep };
    const usernameNode = findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.username);
    const username = usernameValueForNode(usernameNode, account);
    const usernameState = ensureHumanText(usernameNode, username, "aol_username");
    if (usernameState.status === "pending") return { ok: true, reason: "Filling AOL username", activeStep, username };
    const password = account.password || randomPassword();
    account.password = password;
    const passwordState = ensureHumanText(findBySelectors(GENERIC_PROVIDER_FIELD_SELECTORS.password), password, "aol_password");
    if (passwordState.status === "pending") return { ok: true, reason: "Filling AOL password", activeStep };
    const birthState = fillBirthdateFields(account, activeStep);
    if (!birthState.complete) {
      return {
        ...birthState,
        ok: firstState.status === "done" || usernameState.status === "done" || passwordState.status === "done",
        reason: birthState.reason || "AOL account fields are filled; waiting for birthdate controls",
        activeStep
      };
    }
    if (clickGenericProviderNextButton()) return { ok: true, reason: "Filled AOL account form and clicked next", activeStep, username };
    return { ok: true, reason: "AOL account form is filled; waiting for next control", activeStep, username };
  }

  function fillGenericProviderCurrentStep(account, activeStep) {
    if (!isGenericProviderContext()) return null;
    const provider = flowProvider();
    const prefix = providerStepPrefix(provider);
    if (isGenericProviderBlockerStep(activeStep)) {
      autoPilot.enabled = false;
      autoPilot.stopped = true;
      return {
        ok: false,
        reason: `Provider ${provider} reached ${activeStep}; stopped before real verification`,
        activeStep,
        blocker: "provider_challenge"
      };
    }
    if (provider === "proton" && (activeStep === PROTON_USERNAME_STEP || activeStep === PROTON_PASSWORD_STEP)) return fillProtonSignupForm(account, activeStep);
    if (provider === "gmx" && activeStep === GMX_PROFILE_BIRTHDATE_STEP) return fillGmxProfileBirthdate(account, activeStep);
    if (provider === "gmx" && activeStep === `fill_${prefix}_username`) return fillGmxUsername(account, activeStep);
    if (provider === "aol" && activeStep === AOL_ACCOUNT_FORM_STEP) return fillAolAccountForm(account, activeStep);
    if (activeStep === `fill_${prefix}_name` || activeStep === `fill_${prefix}_profile`) return fillGenericName(account, activeStep);
    if (activeStep === `fill_${prefix}_username` || activeStep === `fill_${prefix}_domain`) return fillGenericUsername(account, activeStep);
    if (activeStep === `fill_${prefix}_password`) return fillGenericPassword(account, activeStep);
    if (activeStep === `fill_${prefix}_birthdate`) return fillGenericBirthdate(account, activeStep);
    if (activeStep === `fill_${prefix}_gender`) return fillGenericGender(account, activeStep);
    if (activeStep === `fill_${prefix}_recovery` || activeStep === `fill_${prefix}_reserve_email`) return fillGenericRecovery(account, activeStep);
    if (activeStep === `fill_${prefix}_terms`) return fillGenericTerms(activeStep);
    return null;
  }

  function shouldAutoStart(stepState, challenge) {
    // 仅在用户已点击「开始注册」且 autopilot 处于 active 会话中时才自动接续
    // autoStarted = true 意味着用户通过 sidepanel 点了开始注册，background 下发了 auto_run
    if (!autoPilot.autoStarted) return false;
    // 如果已被显式停止（手动停止或 hard blocker），不自动恢复
    if (autoPilot.stopped || autoPilot.manualStopped) return false;
    if (challenge) return false;
    if (stepState.activeStep === "challenge" || isGenericProviderBlockerStep(stepState.activeStep)) return false;
    if (stepState.postChallengeState === "microsoft_problem") return false;
    if (AUTO_ACTIONABLE_STEPS.has(stepState.activeStep)) return true;
    if (SAFE_AUTO_CONTINUE_STATES.has(stepState.postChallengeState)) return true;
    if (stepState.finalState) return true;
    return false;
  }

  function ensureAutoPilotStarted(reason, stepState, challenge) {
    if (!shouldAutoStart(stepState, challenge)) return false;
    autoPilot.enabled = true;
    autoPilot.autoStarted = true;
    autoPilot.stopped = false;
    autoPilot.manualStopped = false;
    autoPilot.busy = false;
    autoPilot.lastStep = "";
    autoPilot.lastStepAt = 0;
    autoPilot.lastControlAction = "";
    autoPilot.lastControlActionAt = 0;
    autoPilot.submittedStepSignature = "";
    autoPilot.submittedStepAt = 0;
    ensureAutoPilotAccount();
    send("NM_ACTION_RESULT", {
      action: "auto_start",
      ok: true,
      reason: "自动执行已启动",
      trigger: reason,
      activeStep: stepState.activeStep
    });
    return true;
  }

  function stopAutoPilot(reason = "user_stop") {
    autoPilot.stopGeneration += 1;
    autoPilot.enabled = false;
    autoPilot.busy = false;
    autoPilot.stopped = true;
    autoPilot.manualStopped = true;
    autoPilot.autoStarted = false;
    autoPilot.typingSignature = "";
    autoPilot.auxiliaryBusy = false;
    autoPilot.auxiliaryRequestSignature = "";
    autoPilot.lastStep = "";
    autoPilot.lastControlAction = "";
    autoPilot.lastControlActionAt = 0;
    autoPilot.submittedStepSignature = "";
    autoPilot.submittedStepAt = 0;
    clearPendingTimers();
    try {
      chrome.storage.local.set({ ninjemailAutoRunEnabled: false });
    } catch (error) {
      // Ignore storage failures during reload.
    }
    send("NM_ACTION_RESULT", {
      action: "auto_stop",
      ok: true,
      reason: "自动执行已停止",
      trigger: reason
    });
  }

  function terminalFlowState(stepState) {
    if (!stepState) return "";
    const final = stepState.finalState || (FINAL_POST_CHALLENGE_STATES.has(stepState.postChallengeState) ? stepState.postChallengeState : "");
    return CREDENTIAL_READY_FINAL_STATES.has(final) ? final : "";
  }

  function notifyAccountCreated(stepState, options = {}) {
    if (!isTopFrame) return false;
    if (!options.force && !autoPilot.enabled && !autoPilot.autoStarted) return false;
    const terminalState = terminalFlowState(stepState);
    if (!terminalState) return false;
    const account = autoPilot.account;
    if (!account || !account.email || !account.password) return false;
    const signature = `${account.email}:${terminalState}`;
    if (autoPilot.accountSavedSignature === signature) return true;
    autoPilot.accountSavedSignature = signature;
    autoPilot.enabled = false;
    autoPilot.autoStarted = false;
    autoPilot.busy = false;
    autoPilot.stopped = true;
    try {
      chrome.storage.local.set({ ninjemailAutoRunEnabled: false });
    } catch (error) {
      // Ignore storage failures during reload.
    }
    logExplicitAccount("account_created", account, {
      finalState: terminalState,
      url: location.href,
      title: document.title || ""
    });
    send("NM_ACCOUNT_CREATED", {
      account: {
        provider: account.provider || autoPilot.provider || "outlook",
        domain: account.domain || autoPilot.domain || "outlook.com",
        username: account.username || localUsername(account),
        email: account.email,
        password: account.password,
        birthMonth: account.birthMonth || "",
        birthDay: account.birthDay || "",
        birthYear: account.birthYear || ""
      },
      finalState: terminalState,
      url: location.href,
      title: document.title || "",
      stableDelayMs: 8000,
      reason: "auto_after_registration_success"
    });
    return true;
  }

  function runRequestedStep(stepId, stepState, pageText) {
    const requested = String(stepId || "").trim();
    if (requested === "plugin_ready") {
      return { ok: true, reason: "插件探针已连接", activeStep: stepState.activeStep };
    }
    if (requested === "open_signup") {
      return { ok: true, reason: "当前页已打开，注册页跳转请点顶部打开按钮", activeStep: stepState.activeStep };
    }
    if (requested === "challenge") {
      const sources = frameSources();
      const challenge = detectChallenge(pageText, { sources, includeFrameSources: true });
      return {
        ok: !challenge,
        reason: challenge ? "当前是真正人机验证，等待手动处理" : "主页面未阻塞在人机验证",
        activeStep: stepState.activeStep,
        blocker: challenge?.type || ""
      };
    }
    if (requested === "post_challenge") {
      return { requestedStep: requested, activeStep: stepState.activeStep, ...clickSafeContinue(pageText) };
    }
    if (isGenericProviderContext() && isGenericProviderBlockerStep(requested)) {
      return {
        requestedStep: requested,
        ...fillGenericProviderCurrentStep(ensureAutoPilotAccount() || {}, requested)
      };
    }
    if (requested === "final_state" || requested === "export_credentials") {
      const ok = notifyAccountCreated(stepState, { force: true });
      return {
        ok,
        reason: ok ? "已提交四凭证保存/补齐流程" : "当前没有可保存的终态账号",
        activeStep: stepState.activeStep,
        finalState: stepState.finalState || stepState.postChallengeState || ""
      };
    }
    const runnableSteps = new Set([
      "fill_username",
      "fill_password",
      "fill_profile",
      "fill_birthdate",
      "post_challenge",
      ...GMAIL_ACTION_STEPS,
      ...GENERIC_ACTION_STEPS,
      GMX_PROFILE_BIRTHDATE_STEP,
      GMX_TERMS_STEP,
      AOL_ACCOUNT_FORM_STEP,
      YAHOO_FORM_STEP,
      PROTON_USERNAME_STEP,
      PROTON_PASSWORD_STEP
    ]);
    if (runnableSteps.has(requested)) {
      return {
        requestedStep: requested,
        ...fillCurrentStep({ ...stepState, activeStep: requested })
      };
    }
    // 提供更详细的错误信息
    const supportedSteps = [
      "fill_username", "fill_password", "fill_profile", "fill_birthdate",
      "post_challenge", "challenge",
      ...Array.from(GMAIL_ACTION_STEPS),
      ...Array.from(GENERIC_ACTION_STEPS).slice(0, 5),
      GMX_PROFILE_BIRTHDATE_STEP, AOL_ACCOUNT_FORM_STEP, YAHOO_FORM_STEP
    ];
    return { 
      ok: false, 
      reason: `暂不支持手动执行步骤: ${requested || "<empty>"}。支持的步骤: ${supportedSteps.slice(0, 8).join(", ")}...`, 
      activeStep: stepState.activeStep,
      requestedStep: requested
    };
  }

  function fillCurrentStep(stepState) {
    // 处理 post_challenge 步骤（点击继续/跳过按钮）
    if (stepState.activeStep === "post_challenge") {
      const result = clickSafeContinue("");
      return {
        ok: Boolean(result.ok),
        reason: result.ok ? "已点击验证后继续按钮" : "未找到可点击的继续按钮",
        activeStep: stepState.activeStep,
        postChallengeState: stepState.postChallengeState || "",
        ...result
      };
    }
    
    const account = ensureAutoPilotAccount();
    if (!account || !account.email || !account.password) {
      console.error("[FILL_STEP] NO ACCOUNT", { account: !!account, email: account && account.email, activeStep: stepState.activeStep, postChallengeState: stepState.postChallengeState });
      return { ok: false, reason: "没有当前账号缓存，不能自动填写或导出", activeStep: stepState.activeStep };
    }
    const terminalState = terminalFlowState(stepState);
    if (terminalState) {
      notifyAccountCreated(stepState);
      return { ok: true, reason: `注册流程已进入终态: ${terminalState}`, activeStep: stepState.activeStep, finalState: terminalState };
    }
    const yahooCreateResult = fillYahooCreateForm(account, stepState.activeStep);
    if (yahooCreateResult) return yahooCreateResult;
    const gmailResult = fillGmailCurrentStep(account, stepState.activeStep);
    if (gmailResult) return gmailResult;
    const genericProviderResult = fillGenericProviderCurrentStep(account, stepState.activeStep);
    if (genericProviderResult) return genericProviderResult;
    if (stepState.activeStep === "fill_username") {
      if (switchToNewEmailIfNeeded()) {
        return {
          ok: true,
          reason: "已切换到新邮箱地址输入",
          activeStep: stepState.activeStep,
          username: localUsername(account)
        };
      }
      const node = findBySelectors(FIELD_SELECTORS.username);
      const username = usernameValueForNode(node, account);
      const typed = ensureHumanText(node, username, "username");
      selectMicrosoftDomain(account);
      if (typed.status === "done") {
        const submitSignature = `submit:username:${account.registrationRunId || account.email || ""}:${username}:${location.href}`;
        if (!rememberStepSubmit(submitSignature, 30000)) {
          return { ok: true, reason: "用户名已提交，等待页面切换到下一步", activeStep: stepState.activeStep, username };
        }
      }
      if (typed.status === "pending") {
        return { ok: true, reason: "正在逐字输入用户名，等待页面确认", activeStep: stepState.activeStep, username };
      }
      if (typed.status === "done" && clickNextButton()) {
        return { ok: true, reason: "已逐字输入用户名并点击下一步", activeStep: stepState.activeStep, username };
      }
      return { ok: false, reason: "未找到用户名输入框或下一步按钮", activeStep: stepState.activeStep, username };
    }
    if (stepState.activeStep === "fill_password") {
      const nodes = Array.from(document.querySelectorAll([
        "input[name='Password']",
        "input[name='Passwd']",
        "input[name='PasswdAgain']",
        "input[name='password']",
        "#usernamereg-password",
        "#usernamereg-passwordConfirm",
        "#Password",
        "input[type='password']"
      ].join(","))).filter(isVisible);
      const password = account.password || "Nj2026Flow!8192";
      const primary = nodes[0] || findBySelectors(FIELD_SELECTORS.password);
      const secondary = nodes[1] || null;
      const firstTyped = ensureHumanText(primary, password, "password");
      if (firstTyped.status === "pending") {
        return { ok: true, reason: "正在逐字输入密码，等待页面确认", activeStep: stepState.activeStep };
      }
      if (primary && secondary) {
        const confirmTyped = ensureHumanText(secondary, password, "password_confirm");
        if (confirmTyped.status === "pending") {
          return { ok: true, reason: "正在确认输入密码，等待页面确认", activeStep: stepState.activeStep };
        }
      }
      if (clickNextButton()) return { ok: true, reason: "已逐字输入密码并点击下一步", activeStep: stepState.activeStep };
      return { ok: false, reason: "未找到密码输入框或下一步按钮", activeStep: stepState.activeStep };
    }
    if (stepState.activeStep === "fill_profile") {
      if (!account.firstName || !account.lastName) {
        Object.assign(account, randomAccountName());
      }
      const first = findBySelectors(["input[name='FirstName']", "input[name='firstName']", "#firstNameInput", "#firstName", "#usernamereg-firstName"]);
      const last = findBySelectors(["input[name='LastName']", "input[name='lastName']", "#lastNameInput", "#lastName", "#usernamereg-lastName"]);
      const firstState = ensureHumanText(first, account.firstName, "first_name");
      if (firstState.status === "pending") {
        return { ok: true, reason: "正在逐字输入名字，等待页面确认", activeStep: stepState.activeStep };
      }
      const lastState = ensureHumanText(last, account.lastName, "last_name");
      if (lastState.status === "pending") {
        return { ok: true, reason: "正在逐字输入姓氏，等待页面确认", activeStep: stepState.activeStep };
      }
      if (clickNextButton()) return { ok: true, reason: "已逐字输入姓名并点击下一步", activeStep: stepState.activeStep };
      return { ok: false, reason: "未找到姓名输入框或下一步按钮", activeStep: stepState.activeStep };
    }
    if (stepState.activeStep === "fill_birthdate") {
      const fallbackBirthday = randomAdultBirthday();
      const yearValue = account.birthYear || fallbackBirthday.birthYear;
      const monthValue = account.birthMonth || fallbackBirthday.birthMonth;
      const dayValue = account.birthDay || fallbackBirthday.birthDay;
      account.birthYear = yearValue;
      account.birthMonth = monthValue;
      account.birthDay = dayValue;
      const month = findBirthControl("month", [
        "select[name='BirthMonth']",
        "#BirthMonth",
        "#BirthMonthDropdown",
        "[aria-label='Birth month']",
        "[aria-label*='Birth month' i]",
        "input[aria-label*='Birth month' i]",
        "input[aria-label*='month' i]",
        "[aria-label*='month' i][role='combobox']",
        "[aria-label*='月份']",
        "input[aria-label*='月份']",
        "input[aria-label*='月']",
        "[aria-label*='月'][role='combobox']",
        "#month",
        "#usernamereg-month"
      ]);
      const day = findBirthControl("day", [
        "select[name='BirthDay']",
        "#BirthDay",
        "#BirthDayDropdown",
        "[aria-label='Birth day']",
        "[aria-label*='Birth day' i]",
        "input[aria-label*='Birth day' i]",
        "input[aria-label*='day' i]",
        "[aria-label*='day' i][role='combobox']",
        "[aria-label*='日期']",
        "input[aria-label*='日期']",
        "input[aria-label*='日']",
        "[aria-label*='日'][role='combobox']",
        "#day",
        "#usernamereg-day"
      ]);
      const year = findBirthControl("year", [
        "input[name='BirthYear']",
        "#BirthYear",
        "[aria-label='Birth year']",
        "input[aria-label*='Birth year' i]",
        "input[aria-label*='year' i]",
        "input[aria-label*='年份']",
        "input[placeholder*='Year' i]",
        "input[placeholder*='年']",
        "#year",
        "#usernamereg-year"
      ]);
      const gender = resolveInteractiveControl(findBySelectors([
        "#gender",
        "select[name='gender']",
        "[aria-label*='Gender' i]",
        "[aria-label*='gender' i]",
        "[aria-label*='性别']"
      ]));
      const yearVerb = controlActionVerb(year);
      const monthVerb = controlActionVerb(month);
      const dayVerb = controlActionVerb(day);
      const genderVerb = controlActionVerb(gender);
      const yearState = ensureBirthYear(year, yearValue);
      if (yearState.status === "pending") {
        return { ok: true, reason: `正在${yearVerb}出生年份，等待页面确认`, activeStep: stepState.activeStep, evidence: yearState.evidence || "", expected: yearValue };
      }
      if (yearState.status !== "done") {
        return { ok: false, reason: `未能${yearVerb}出生年份`, activeStep: stepState.activeStep, detail: yearState.reason || "", expected: yearValue };
      }
      const monthState = selectCustomOption(month, "month", monthValue);
      if (monthState.status === "pending") {
        return { ok: true, reason: `正在${monthVerb}出生月份，等待页面确认`, activeStep: stepState.activeStep, evidence: monthState.evidence || "", year: yearValue, expected: monthValue };
      }
      if (monthState.status !== "done") {
        return { ok: false, reason: `未能${monthVerb}出生月份`, activeStep: stepState.activeStep, detail: monthState.reason || "", expected: monthValue };
      }
      const dayState = selectCustomOption(day, "day", dayValue);
      if (dayState.status === "pending") {
        return { ok: true, reason: `正在${dayVerb}出生日期，等待页面确认`, activeStep: stepState.activeStep, evidence: dayState.evidence || "", month: monthState.evidence || "", year: yearValue, expected: dayValue };
      }
      if (dayState.status !== "done") {
        return { ok: false, reason: `未能${dayVerb}出生日期`, activeStep: stepState.activeStep, detail: dayState.reason || "", expected: dayValue };
      }
      const genderValue = account.gender || "Rather not say";
      const genderState = gender ? selectCustomOption(gender, "gender", genderValue) : { status: "done", evidence: "" };
      if (genderState.status === "pending") {
        return { ok: true, reason: `正在${genderVerb}性别，等待页面确认`, activeStep: stepState.activeStep, evidence: genderState.evidence || "", month: monthState.evidence || "", day: dayState.evidence || "", year: yearValue, expected: genderValue };
      }
      if (gender && genderState.status !== "done") {
        return { ok: false, reason: `未能${genderVerb}性别`, activeStep: stepState.activeStep, detail: genderState.reason || "", expected: genderValue };
      }
      if (clickNextButton()) {
        return {
          ok: true,
          reason: "已确认出生年月日并点击下一步",
          activeStep: stepState.activeStep,
          month: monthState.evidence,
          day: dayState.evidence,
          year: yearValue
        };
      }
      return { ok: false, reason: "生日三项已填完整，但下一步按钮尚不可点击，等待下一轮重试", activeStep: stepState.activeStep, year: yearValue, month: monthState.evidence, day: dayState.evidence };
    }
    if (SAFE_AUTO_CONTINUE_STATES.has(stepState.postChallengeState)) {
      return { activeStep: stepState.activeStep, ...clickSafeContinue(textSample()) };
    }
    if (stepState.postChallengeState === "microsoft_problem") {
      autoPilot.enabled = false;
      autoPilot.stopped = true;
      return {
        ok: false,
        reason: "Microsoft 返回“我们遇到了问题”，当前账号流程停止；下一次开始注册会重新生成账号重跑",
        activeStep: stepState.activeStep,
        postChallengeState: stepState.postChallengeState,
        blocker: "microsoft_problem",
        hardBlocker: true,
        requestNewAccount: true,
        evidence: location.href
      };
    }
    if (stepState.activeStep === "challenge" || isGenericProviderBlockerStep(stepState.activeStep)) {
      autoPilot.enabled = false;
      autoPilot.stopped = true;
      return { ok: false, reason: "已到真正人机验证，自动执行暂停", activeStep: stepState.activeStep, blocker: "challenge" };
    }
    return { ok: false, reason: `当前步骤无需自动填写或尚未支持: ${stepState.activeStep}`, activeStep: stepState.activeStep };
  }
  function runAutopilotOnce(reason, stepState, challenge) {
    if (!isTopFrame || !autoPilot.enabled || autoPilot.busy) return;
    if (stepState.activeStep === "challenge" || isGenericProviderBlockerStep(stepState.activeStep)) {
      autoPilot.enabled = false;
      autoPilot.stopped = true;
      send("NM_ACTION_RESULT", {
        action: "auto_run",
        ok: false,
        reason: "已到真正人机验证，自动执行暂停",
        activeStep: stepState.activeStep,
        blocker: challenge ? challenge.type : "provider_challenge"
      });
      return;
    }
    if (stepState.postChallengeState === "microsoft_problem") {
      const result = fillCurrentStep(stepState);
      send("NM_ACTION_RESULT", {
        action: "auto_run",
        trigger: reason,
        ...result
      });
      return;
    }
    const actionable = AUTO_ACTIONABLE_STEPS.has(stepState.activeStep);
    if (!actionable && !SAFE_AUTO_CONTINUE_STATES.has(stepState.postChallengeState)) return;
    const now = Date.now();
    const stepKey = `${stepState.activeStep}:${stepState.postChallengeState}:${location.href}`;
    if (stepKey === autoPilot.lastStep && now - autoPilot.lastStepAt < 600) return;
    autoPilot.busy = true;
    autoPilot.lastStep = stepKey;
    autoPilot.lastStepAt = now;
    
    later(() => {
      if (autoPilot.stopped || !autoPilot.enabled) {
        send("NM_ACTION_RESULT", {
          action: "auto_run",
          trigger: reason,
          ok: false,
          reason: `autopilot aborted before callback: stopped=${autoPilot.stopped} enabled=${autoPilot.enabled}`,
          activeStep: stepState.activeStep
        });
        autoPilot.busy = false;
        return;
      }
      const freshText = textSample();
      const freshSources = frameSources();
      const freshChallenge = detectChallenge(freshText, { sources: freshSources, includeFrameSources: true });
      const freshState = detectStepState(freshText, freshChallenge);
      console.log("[AUTOPILOT] About to fill step: activeStep=%s postChallengeState=%s", freshState.activeStep, freshState.postChallengeState);
      const result = fillCurrentStep(freshState);
      console.log("[AUTOPILOT] fill result:", JSON.stringify(result));
      send("NM_ACTION_RESULT", {
        action: "auto_run",
        trigger: reason,
        ...result
      });
      autoPilot.busy = false;
      if (autoPilot.stopped || !autoPilot.enabled) return;
      later(() => scan("after_auto_run"), jitter(200, 450));
    }, jitter(80, 250));
  }

  function maybeHandleOAuthAuthorizationLegacy(pageText, reason) {
    if (!isTopFrame || !autoPilot.oauthEmail) return false;
    if (!location.hostname.includes("login.microsoftonline.com")) return false;
    const candidates = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit'], a[role='button'], div[role='button'], [role='option']"))
      .filter(isVisible);
    const email = lower(autoPilot.oauthEmail);
    const now = Date.now();
    const clickNode = (node, action) => {
      const signature = `oauth:${action}:${location.href}:${buttonText(node)}`;
      if (autoPilot.lastControlAction === signature && now - autoPilot.lastControlActionAt < 4500) return true;
      autoPilot.lastControlAction = signature;
      autoPilot.lastControlActionAt = now;
      humanClick(node);
      send("NM_ACTION_RESULT", {
        action: "oauth_authorize",
        ok: true,
        trigger: reason,
        reason: action,
        evidence: nodeEvidence(node)
      });
      later(() => scan("after_oauth_authorize"), jitter(650, 1200));
      return true;
    };
    const accountTile = candidates.find((node) => email && buttonText(node).includes(email));
    if (accountTile) return clickNode(accountTile, "已选择当前账号");
    const positive = [
      "接受",
      "同意",
      "允许",
      "是",
      "继续",
      "下一步",
      "accept",
      "allow",
      "approve",
      "yes",
      "continue",
      "next"
    ];
    for (const token of positive) {
      const match = candidates.find((node) => buttonText(node) === lower(token) || buttonText(node).includes(lower(token)));
      if (match) return clickNode(match, "已确认 OAuth 授权");
    }
    return false;
  }

  function looksLikeAuxiliaryMailboxPrompt(pageText) {
    const text = lower(pageText);
    return includesAny(text, [
      "alternate email",
      "backup email",
      "recovery email",
      "security email",
      "verify your identity",
      "send a code",
      "where should we send",
      "备用邮箱",
      "辅助邮箱",
      "恢复邮箱",
      "安全邮箱",
      "验证你的身份",
      "发送代码",
      "接收验证码"
    ]);
  }

  function findAuxiliaryEmailInput() {
    const nodes = Array.from(document.querySelectorAll([
      "input[type='email']",
      "input[name*='email' i]",
      "input[id*='email' i]",
      "input[aria-label*='email' i]",
      "input[placeholder*='email' i]",
      "input[aria-label*='邮箱']",
      "input[placeholder*='邮箱']"
    ].join(","))).filter((node) => isVisible(node) && !isDisabledControl(node));
    return nodes.find((node) => {
      const evidence = lower(nodeEvidence(node));
      return includesAny(evidence, ["recovery", "alternate", "backup", "security", "email", "邮箱"]);
    }) || nodes[0] || null;
  }

  function findVerificationCodeInput() {
    const nodes = Array.from(document.querySelectorAll([
      "input[name*='code' i]",
      "input[id*='code' i]",
      "input[aria-label*='code' i]",
      "input[placeholder*='code' i]",
      "input[inputmode='numeric']",
      "input[type='tel']",
      "input[aria-label*='验证码']",
      "input[placeholder*='验证码']",
      "input[aria-label*='代码']",
      "input[placeholder*='代码']"
    ].join(","))).filter((node) => isVisible(node) && !isDisabledControl(node));
    return nodes.find((node) => {
      const evidence = lower(nodeEvidence(node));
      return includesAny(evidence, ["code", "otp", "verification", "验证码", "代码"]);
    }) || nodes[0] || null;
  }

  function requestAuxiliaryMailbox(reason, emailNode) {
    const signature = `aux_email:${location.href}:${nodeEvidence(emailNode)}`;
    const now = Date.now();
    if (autoPilot.auxiliaryBusy) return true;
    if (autoPilot.auxiliaryLastActionSignature === signature && now - autoPilot.auxiliaryLastActionAt < 8000) return true;
    autoPilot.auxiliaryBusy = true;
    autoPilot.auxiliaryRequestSignature = signature;
    chrome.runtime.sendMessage({ type: "NM_AUXILIARY_MAILBOX_PICK", payload: { reason, url: location.href } }, (response) => {
      void chrome.runtime.lastError;
      autoPilot.auxiliaryBusy = false;
      const mailbox = response && response.mailbox;
      const email = String(mailbox && mailbox.email || "").trim();
      if (!email || !emailNode || !isVisible(emailNode)) return;
      autoPilot.auxiliaryLastActionSignature = signature;
      autoPilot.auxiliaryLastActionAt = Date.now();
      autoPilot.auxiliaryEmail = email;
      autoPilot.auxiliarySourcePath = String(mailbox.sourcePath || mailbox.source_path || "");
      setNativeValue(emailNode, email);
      send("NM_ACTION_RESULT", {
        action: "auxiliary_mailbox",
        ok: true,
        reason: "已填写随机辅助邮箱",
        email,
        evidence: nodeEvidence(emailNode)
      });
      const next = microsoftPrimaryButton() || queryAny(FIELD_SELECTORS.submit);
      if (next) humanClick(next);
      later(() => scan("after_auxiliary_email"), jitter(800, 1500));
    });
    return true;
  }

  function requestAuxiliaryCode(reason, codeNode) {
    const signature = `aux_code:${autoPilot.auxiliaryEmail}:${location.href}:${nodeEvidence(codeNode)}`;
    const now = Date.now();
    if (autoPilot.auxiliaryBusy) return true;
    if (autoPilot.auxiliaryLastActionSignature === signature && now - autoPilot.auxiliaryLastActionAt < 8000) return true;
    autoPilot.auxiliaryBusy = true;
    autoPilot.auxiliaryRequestSignature = signature;
    chrome.runtime.sendMessage({
      type: "NM_AUXILIARY_MAILBOX_CODE",
      payload: {
        reason,
        email: autoPilot.auxiliaryEmail,
        sourcePath: autoPilot.auxiliarySourcePath,
        url: location.href
      }
    }, (response) => {
      void chrome.runtime.lastError;
      autoPilot.auxiliaryBusy = false;
      const code = String(response && response.code || "").trim();
      if (!code || !codeNode || !isVisible(codeNode)) return;
      autoPilot.auxiliaryLastActionSignature = signature;
      autoPilot.auxiliaryLastActionAt = Date.now();
      setNativeValue(codeNode, code);
      send("NM_ACTION_RESULT", {
        action: "auxiliary_code",
        ok: true,
        reason: "已填写辅助邮箱验证码",
        email: autoPilot.auxiliaryEmail,
        code,
        evidence: nodeEvidence(codeNode)
      });
      const next = microsoftPrimaryButton() || queryAny(FIELD_SELECTORS.submit);
      if (next) humanClick(next);
      later(() => scan("after_auxiliary_code"), jitter(800, 1500));
    });
    return true;
  }

  function maybeHandleAuxiliaryMailbox(pageText, reason) {
    if (!isTopFrame || !autoPilot.enabled || autoPilot.stopped) return false;
    if (!looksLikeAuxiliaryMailboxPrompt(pageText)) return false;
    const codeNode = findVerificationCodeInput();
    if (codeNode && autoPilot.auxiliaryEmail) {
      return requestAuxiliaryCode(reason, codeNode);
    }
    const emailNode = findAuxiliaryEmailInput();
    if (emailNode) {
      return requestAuxiliaryMailbox(reason, emailNode);
    }
    return false;
  }

  function maybeHandleOAuthAuthorization(pageText, reason) {
    if (!isTopFrame || !autoPilot.oauthEmail) return false;
    const host = lower(location.hostname);
    const href = lower(location.href);
    if (!(
      host.includes("login.microsoftonline.com")
      || host.includes("login.microsoft.com")
      || host.includes("login.live.com")
      || host.includes("account.live.com")
      || host.includes("account.microsoft.com")
    )) return false;
    const account = autoPilot.oauthAccount || autoPilot.account || {};
    const email = lower(autoPilot.oauthEmail || account.email || "");
    const password = String(account.password || "");
    const candidates = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit'], a[role='button'], div[role='button'], [role='option']"))
      .filter(isVisible);
    const now = Date.now();
    const scheduleOAuthRescan = (label = "after_oauth_authorize") => {
      later(() => scan(label), jitter(650, 1200));
    };
    const clickNode = (node, action) => {
      const signature = `oauth:${action}:${location.href}:${buttonText(node)}`;
      if (autoPilot.lastControlAction === signature && now - autoPilot.lastControlActionAt < 4500) return true;
      autoPilot.lastControlAction = signature;
      autoPilot.lastControlActionAt = now;
      humanClick(node);
      send("NM_ACTION_RESULT", {
        action: "oauth_authorize",
        ok: true,
        trigger: reason,
        reason: action,
        email,
        evidence: nodeEvidence(node)
      });
      scheduleOAuthRescan("after_oauth_click");
      return true;
    };
    const findInput = (selectors) => {
      for (const selector of selectors) {
        const node = queryAny([selector]);
        if (node) return node;
      }
      return null;
    };
    const findButton = (tokens) => {
      for (const token of tokens) {
        const wanted = lower(token);
        const match = candidates.find((node) => {
          const text = buttonText(node);
          const id = lower(node.id || node.getAttribute?.("id") || "");
          const name = lower(node.getAttribute?.("name") || "");
          const value = lower(node.getAttribute?.("value") || "");
          return text === wanted
            || text.includes(wanted)
            || id === wanted
            || name === wanted
            || value === wanted
            || value.includes(wanted);
        });
        if (match) return match;
      }
      return null;
    };
    const findControl = (selectors) => {
      for (const selector of selectors) {
        const node = queryAny([selector]);
        if (node) return node;
      }
      return null;
    };
    const looksLikePasskey = href.includes("interrupt/passkey")
      || href.includes("consumers/fido/create")
      || pageText.includes("passkey")
      || pageText.includes("security key")
      || pageText.includes("windows hello")
      || pageText.includes("通行密钥")
      || pageText.includes("安全密钥");
    if (looksLikePasskey) {
      const cancel = findControl([
        "#idBtn_Back",
        "input[type='button'][value*='取消']",
        "input[type='button'][value*='Cancel' i]",
        "button[data-testid='secondaryButton']",
        "button[data-testid*='cancel' i]",
        "button[aria-label*='取消']",
        "button[aria-label*='cancel' i]"
      ]) || findButton(["取消", "不使用", "不，谢谢", "暂不", "以后再说", "跳过", "cancel", "not now", "maybe later", "skip", "no thanks", "no"]);
      if (cancel) return clickNode(cancel, "已取消 OAuth 通行密钥提示");
      try {
        window.history.back();
        send("NM_ACTION_RESULT", {
          action: "oauth_authorize",
          ok: true,
          trigger: reason,
          reason: "OAuth 通行密钥提示未找到取消按钮，已后退",
          email,
          evidence: location.href
        });
        scheduleOAuthRescan("after_oauth_passkey_back");
        return true;
      } catch (error) {
        // Fall through and keep scanning; never click passkey "Next" as a generic positive action.
      }
      return true;
    }
    const emailNode = findInput([
      "input[name='loginfmt']",
      "input[name='login']",
      "input[type='email']",
      "input[autocomplete='username']",
      "#i0116"
    ]);
    if (emailNode && email) {
      if (textInputValue(emailNode).toLowerCase() !== email) {
        setNativeValue(emailNode, email);
        send("NM_ACTION_RESULT", {
          action: "oauth_authorize",
          ok: true,
          trigger: reason,
          reason: "已填写 OAuth 登录邮箱",
          email,
          evidence: nodeEvidence(emailNode)
        });
      }
      const next = findControl(["#idSIButton9", "input[type='submit'][value*='Next' i]", "input[type='submit'][value*='下一步']"])
        || findButton(["下一步", "next", "continue"]);
      if (next) return clickNode(next, "已提交 OAuth 登录邮箱");
      scheduleOAuthRescan("after_oauth_email_filled");
      return true;
    }
    const passwordNode = findInput([
      "input[name='passwd']",
      "input[name='Password']",
      "input[type='password']",
      "#i0118"
    ]);
    if (passwordNode && password) {
      if (textInputValue(passwordNode) !== password) {
        setNativeValue(passwordNode, password);
        send("NM_ACTION_RESULT", {
          action: "oauth_authorize",
          ok: true,
          trigger: reason,
          reason: "已填写 OAuth 登录密码",
          email,
          evidence: nodeEvidence(passwordNode)
        });
      }
      const submit = findControl(["#idSIButton9", "input[type='submit'][value*='Sign in' i]", "input[type='submit'][value*='登录']"])
        || findButton(["登录", "登入", "下一步", "sign in", "log in", "next", "continue"]);
      if (submit) return clickNode(submit, "已提交 OAuth 登录密码");
      scheduleOAuthRescan("after_oauth_password_filled");
      return true;
    }
    const accountTile = candidates.find((node) => email && buttonText(node).includes(email));
    if (accountTile) return clickNode(accountTile, "已选择当前 OAuth 账号");
    const looksLikeConsent = href.includes("consent")
      || pageText.includes("permission")
      || pageText.includes("permissions")
      || pageText.includes("permissions requested")
      || pageText.includes("权限")
      || pageText.includes("授权")
      || pageText.includes("microsoft graph command line tools")
      || Boolean(findControl(["#idBtn_Accept", "#acceptButton", "input[name='ucaccept']", "button[name='ucaccept']"]));
    if (looksLikeConsent) {
      const consent = findControl([
        "#idBtn_Accept",
        "#acceptButton",
        "#idSIButton9",
        "input[name='ucaccept']",
        "button[name='ucaccept']",
        "input[type='submit'][value*='Accept' i]",
        "input[type='submit'][value*='Allow' i]",
        "input[type='submit'][value*='Yes' i]",
        "input[type='submit'][value*='接受']",
        "input[type='submit'][value*='同意']",
        "input[type='submit'][value*='允许']",
        "button[id*='accept' i]",
        "button[name*='accept' i]",
        "button[data-testid*='accept' i]"
      ]) || findButton(["接受", "同意", "允许", "accept", "allow", "approve", "yes", "继续", "continue"]);
      if (consent) return clickNode(consent, "已接受 Microsoft Graph 授权");
    }
    const positive = [
      "登录",
      "登入",
      "接受",
      "同意",
      "允许",
      "是",
      "继续",
      "下一步",
      "accept",
      "allow",
      "approve",
      "sign in",
      "log in",
      "yes",
      "continue",
      "next"
    ];
    for (const token of positive) {
      const match = findButton([token]);
      if (match) return clickNode(match, "已确认 OAuth 授权/登录");
    }
    return false;
  }

  function maybeAutoContinue(pageText, stepState, challenge, signature) {
    if (!isTopFrame || ((stepState.activeStep === "challenge" || isGenericProviderBlockerStep(stepState.activeStep)) && challenge) || !SAFE_AUTO_CONTINUE_STATES.has(stepState.postChallengeState)) {
      return;
    }
    if (!autoPilot.enabled || autoPilot.stopped) return;
    if (signature === lastAutoContinueSignature) {
      return;
    }
    lastAutoContinueSignature = signature;
    later(() => {
      if (autoPilot.stopped) return;
      const freshText = textSample();
      const freshSources = frameSources();
      const freshChallenge = detectChallenge(freshText, { sources: freshSources, includeFrameSources: true });
      const freshState = detectStepState(freshText, freshChallenge);
      if (((freshState.activeStep === "challenge" || isGenericProviderBlockerStep(freshState.activeStep)) && freshChallenge) || !SAFE_AUTO_CONTINUE_STATES.has(freshState.postChallengeState)) {
        return;
      }
      const result = clickSafeContinue(freshText);
      send("NM_ACTION_RESULT", {
        action: "auto_click_continue",
        activeStep: freshState.activeStep,
        postChallengeState: freshState.postChallengeState,
        ...result
      });
      later(() => scan("after_auto_continue"), jitter(200, 450));
    }, jitter(120, 300));
  }

  function send(type, payload) {
    try {
      chrome.runtime.sendMessage({ type, payload }, () => {
        void chrome.runtime.lastError;
      });
    } catch (error) {
      // The extension can be reloaded while the page stays open.
    }
  }

  function loadProviderConfig(reason = "provider_config") {
    try {
      chrome.storage.local.get([
        "ninjemailProvider",
        "ninjemailActiveAccount",
        "ninjemailGeneratedAccount",
        "ninjemailOAuthActiveEmail",
        "ninjemailOAuthActiveAccount",
        "ninjemailAutoRunEnabled"
      ], (result) => {
        setProvider(result && result.ninjemailProvider ? result.ninjemailProvider : "outlook");
        autoPilot.oauthEmail = String(result && result.ninjemailOAuthActiveEmail || "");
        autoPilot.oauthAccount = result && result.ninjemailOAuthActiveAccount && result.ninjemailOAuthActiveAccount.email
          ? { ...result.ninjemailOAuthActiveAccount }
          : null;
        const storedAccount = result && result.ninjemailActiveAccount && result.ninjemailActiveAccount.email
          ? result.ninjemailActiveAccount
          : (result && result.ninjemailGeneratedAccount && result.ninjemailGeneratedAccount.email ? result.ninjemailGeneratedAccount : null);
        if (storedAccount) {
          autoPilot.account = {
            ...storedAccount
          };
          if (autoPilot.account.provider) {
            setProvider(autoPilot.account.provider);
          }
        }
        if (result && result.ninjemailAutoRunEnabled && autoPilot.account && autoPilot.account.email && autoPilot.account.password) {
          autoPilot.autoStarted = true;
          autoPilot.stopped = false;
          autoPilot.manualStopped = false;
        }
        scan(reason);
      });
    } catch (error) {
      setProvider("outlook");
    }
  }

  function postChallengeBlockerFor(stepState = {}) {
    if (stepState.postChallengeState === "microsoft_problem") {
      return {
        type: "microsoft_problem",
        label: "Microsoft 问题页",
        action: "regenerate_account",
        evidence: document.title || location.href
      };
    }
    if (stepState.postChallengeState === "phone_verification") {
      return {
        type: "phone_verification",
        label: "手机号/短信验证",
        action: "manual_or_sms_adapter_required",
        evidence: document.title || location.href
      };
    }
    return null;
  }

  function scan(reason) {
    const pageText = textSample();
    const sources = frameSources();
    const challenge = detectChallenge(pageText, {
      sources,
      includeFrameSources: true
    });
    const stepState = detectStepState(pageText, challenge);
    
    // DEBUG: Log frame detection details
    const frameDebug = sources.map((s) => ({
      id: s.id || "(no-id)",
      name: s.name || "(no-name)", 
      src: (s.src || "").substring(0, 120),
      visible: s.visible,
      captchaHint: /hsprotect|fpt\.live\.com|arkose|funcaptcha|enforcement/i.test(s.src || "")
    }));
    console.log("[SCAN_DEBUG]", JSON.stringify({
      reason,
      activeStep: stepState.activeStep,
      challengeType: challenge ? challenge.type : "none",
      challengeEvidence: challenge ? challenge.evidence : "none",
      iframeCount: sources.length,
      iframes: frameDebug.slice(0, 5),
      pageTokensFound: ["arkoselabs","funcaptcha","arkose","game-core-frame","enforcementframe","证明你不是机器人"]
        .filter((t) => pageText.toLowerCase().includes(t) || sources.some((s) => String(s.src || "").includes(t)))
    }));
    
    const postChallengeBlocker = postChallengeBlockerFor(stepState);
    const effectiveBlocker = (stepState.activeStep === "challenge" || isGenericProviderBlockerStep(stepState.activeStep)) ? challenge : postChallengeBlocker;
    const observedSteps = stepState.steps
      .filter((step) => step.status !== "pending")
      .map((step) => ({ id: step.id, evidence: step.evidence, status: step.status }));
    const payload = {
      provider: autoPilot.provider || "outlook",
      reason,
      url: location.href,
      title: document.title || "",
      host: location.hostname,
      frame: isTopFrame ? "top" : "child",
      isTopFrame,
      activeStep: stepState.activeStep,
      steps: stepState.steps,
      blocker: effectiveBlocker,
      rootCause: stepState.rootCause,
      observedSteps,
      postChallengeState: stepState.postChallengeState,
      finalState: stepState.finalState,
      elements: stepState.elements,
      frameSources: sources.slice(0, 10),
      frameDebug: frameDebug.slice(0, 5),
      captchaCheck: challenge ? { type: challenge.type, evidence: challenge.evidence } : "NONE",
      checkedAt: new Date().toISOString()
    };
    const signature = JSON.stringify({
      url: payload.url,
      title: payload.title,
      frame: payload.frame,
      blocker: payload.blocker,
      postChallengeState: payload.postChallengeState,
      finalState: payload.finalState,
      activeStep: payload.activeStep,
      steps: payload.steps
    });
    if (signature !== lastSignature || reason === "manual_scan") {
      lastSignature = signature;
      send("NM_CONTENT_STATUS", payload);
    }
    if (maybeHandleOAuthAuthorization(pageText, reason)) {
      return;
    }
    if (notifyAccountCreated(stepState)) {
      return;
    }
    ensureAutoPilotStarted(reason, stepState, challenge);
    if (maybeHandleAuxiliaryMailbox(pageText, reason)) {
      return;
    }
    maybeAutoContinue(pageText, stepState, challenge, signature);
    runAutopilotOnce(reason, stepState, challenge);
  }

  runtimeMessageListener = (message, sender, sendResponse) => {
    if (message && message.type === "NM_SCAN") {
      scan("manual_scan");
      sendResponse({ ok: true, action: "scan" });
      return false;
    }
    if (message && message.type === "NM_STEP_ACTION") {
      if (!isTopFrame) {
        sendResponse({ ok: true, ignored: true, reason: "child_frame_ignored" });
        return false;
      }
      const pageText = textSample();
      const sources = frameSources();
      const stepState = detectStepState(pageText, detectChallenge(pageText, { sources, includeFrameSources: true }));
      let response = { ok: true, action: message.action || "" };
      if (message.action === "focus_active") {
        const node = activeElementForStep(stepState.activeStep);
        const ok = highlight(node);
        response = { ok, action: message.action, activeStep: stepState.activeStep };
        send("NM_ACTION_RESULT", {
          action: message.action,
          ok,
          reason: ok ? "已聚焦当前步骤" : "未找到当前步骤元素",
          activeStep: stepState.activeStep
        });
      } else if (message.action === "click_continue") {
        const result = clickSafeContinue(pageText);
        response = { ok: Boolean(result.ok), action: message.action, activeStep: stepState.activeStep };
        send("NM_ACTION_RESULT", {
          action: message.action,
          activeStep: stepState.activeStep,
          ...result
        });
        later(() => scan("after_click_continue"), jitter(520, 900));
      } else if (message.action === "run_step") {
        if (message.account && message.account.provider) {
          setProvider(message.account.provider);
          autoPilot.account = message.account;
        }
        autoPilot.enabled = true;
        autoPilot.stopped = false;
        autoPilot.manualStopped = false;
        const result = runRequestedStep(message.stepId, stepState, pageText);
        response = { ok: Boolean(result.ok), action: message.action, stepId: message.stepId || "", activeStep: result.activeStep || stepState.activeStep };
        send("NM_ACTION_RESULT", {
          action: message.action,
          stepId: message.stepId || "",
          ...result
        });
        later(() => scan("after_manual_step"), jitter(520, 950));
      } else if (message.action === "auto_run") {
        if (message.account && message.account.provider) {
          setProvider(message.account.provider);
        }
        const nextAccount = message.account || autoPilot.account || null;
        if (!nextAccount || !nextAccount.email || !nextAccount.password) {
          autoPilot.enabled = false;
          autoPilot.autoStarted = false;
          autoPilot.stopped = true;
          send("NM_ACTION_RESULT", {
            action: message.action,
            ok: false,
            reason: "没有后台下发的当前账号，已拒绝在 content 端重新生成账号",
            activeStep: stepState.activeStep
          });
          response = {
            ok: false,
            ack: "NM_START_AUTOPILOT_ACK",
            action: message.action,
            provider: flowProvider(),
            runId: message.runId || "",
            activeStep: stepState.activeStep,
            reason: "missing_active_account"
          };
          sendResponse(response);
          return false;
        }
        const previousAccount = autoPilot.account || null;
        const previousRunId = previousAccount && previousAccount.registrationRunId ? previousAccount.registrationRunId : "";
        const nextRunId = nextAccount && nextAccount.registrationRunId ? nextAccount.registrationRunId : "";
        const sameAccount = previousAccount
          && nextAccount
          && previousAccount.email === nextAccount.email
          && previousAccount.password === nextAccount.password
          && (!previousRunId || !nextRunId || previousRunId === nextRunId);
        const wasEnabled = autoPilot.enabled && !autoPilot.stopped;
        autoPilot.enabled = true;
        autoPilot.autoStarted = true;
        autoPilot.stopped = false;
        autoPilot.manualStopped = false;
        autoPilot.busy = false;
        if (!wasEnabled || !sameAccount) {
          autoPilot.stopGeneration += 1;
          autoPilot.lastStep = "";
          autoPilot.lastControlAction = "";
          autoPilot.lastControlActionAt = 0;
          autoPilot.submittedStepSignature = "";
          autoPilot.submittedStepAt = 0;
          autoPilot.auxiliaryEmail = "";
          autoPilot.auxiliarySourcePath = "";
          autoPilot.auxiliaryBusy = false;
          autoPilot.auxiliaryRequestSignature = "";
          autoPilot.auxiliaryLastActionSignature = "";
          autoPilot.auxiliaryLastActionAt = 0;
        }
        autoPilot.account = nextAccount;
        autoPilot.accountSavedSignature = "";
        try {
          chrome.storage.local.set({ ninjemailActiveAccount: autoPilot.account, ninjemailAutoRunEnabled: true });
        } catch (error) {
          // Ignore storage failures during reload.
        }
        send("NM_ACTION_RESULT", {
          action: message.action,
          ok: true,
          reason: "自动执行已启动",
          activeStep: stepState.activeStep
        });
        response = {
          ok: true,
          ack: "NM_START_AUTOPILOT_ACK",
          action: message.action,
          provider: flowProvider(),
          runId: message.runId || nextAccount.registrationRunId || "",
          activeStep: stepState.activeStep
        };
        later(() => scan("manual_auto_run"), jitter(180, 420));
      } else if (message.action === "stop_auto") {
        stopAutoPilot("sidepanel_stop");
        response = { ok: true, action: message.action };
      }
      sendResponse(response);
      return false;
    }
    return false;
  };
  chrome.runtime.onMessage.addListener(runtimeMessageListener);

  loadProviderConfig("loaded");
  observer = new MutationObserver(() => scan("dom_changed"));
  if (document.documentElement) {
    observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true });
  }
  if (chrome.storage && chrome.storage.onChanged) {
    storageChangeListener = (changes, areaName) => {
    if (areaName === "local" && changes.ninjemailProvider) {
      setProvider(changes.ninjemailProvider.newValue || "outlook");
      autoPilot.account = null;
      scan("provider_changed");
    }
    if (areaName === "local" && changes.ninjemailActiveAccount) {
      autoPilot.account = changes.ninjemailActiveAccount.newValue || null;
      autoPilot.accountSavedSignature = "";
      scan("account_changed");
    }
    if (areaName === "local" && changes.ninjemailAutoRunEnabled) {
      const enabled = Boolean(changes.ninjemailAutoRunEnabled.newValue);
      if (!enabled) {
        autoPilot.stopGeneration += 1;
        autoPilot.enabled = false;
        autoPilot.stopped = true;
        autoPilot.manualStopped = true;
        autoPilot.autoStarted = false;
        autoPilot.busy = false;
        autoPilot.typingSignature = "";
        autoPilot.auxiliaryBusy = false;
        autoPilot.auxiliaryRequestSignature = "";
        autoPilot.lastStep = "";
        autoPilot.submittedStepSignature = "";
        autoPilot.submittedStepAt = 0;
        clearPendingTimers();
      }
      scan("autorun_changed");
    }
    if (areaName === "local" && changes.ninjemailOAuthActiveEmail) {
      autoPilot.oauthEmail = String(changes.ninjemailOAuthActiveEmail.newValue || "");
      scan("oauth_active_changed");
    }
    if (areaName === "local" && changes.ninjemailOAuthActiveAccount) {
      const nextAccount = changes.ninjemailOAuthActiveAccount.newValue || null;
      autoPilot.oauthAccount = nextAccount && nextAccount.email ? { ...nextAccount } : null;
      scan("oauth_account_changed");
    }
    };
    chrome.storage.onChanged.addListener(storageChangeListener);
  }
  timer = setInterval(() => scan("interval"), 800);
  globalThis.__NINJEMAIL_SIGNUP_OBSERVER_CLEANUP = () => {
    autoPilot.stopGeneration += 1;
    autoPilot.enabled = false;
    autoPilot.stopped = true;
    autoPilot.busy = false;
    autoPilot.typingSignature = "";
    clearPendingTimers();
    if (observer) observer.disconnect();
    if (timer) clearInterval(timer);
    observer = null;
    timer = null;
    if (runtimeMessageListener && chrome.runtime && chrome.runtime.onMessage) {
      try { chrome.runtime.onMessage.removeListener(runtimeMessageListener); } catch (error) {}
    }
    if (storageChangeListener && chrome.storage && chrome.storage.onChanged) {
      try { chrome.storage.onChanged.removeListener(storageChangeListener); } catch (error) {}
    }
    if (beforeUnloadListener) {
      try { window.removeEventListener("beforeunload", beforeUnloadListener); } catch (error) {}
    }
    if (globalThis.__NINJEMAIL_SIGNUP_OBSERVER_ATTACHED === NINJEMAIL_SIGNUP_SCRIPT_VERSION) {
      globalThis.__NINJEMAIL_SIGNUP_OBSERVER_ATTACHED = "";
    }
  };
  beforeUnloadListener = () => {
    if (typeof globalThis.__NINJEMAIL_SIGNUP_OBSERVER_CLEANUP === "function") {
      globalThis.__NINJEMAIL_SIGNUP_OBSERVER_CLEANUP();
    }
  };
  window.addEventListener("beforeunload", beforeUnloadListener);
})();
