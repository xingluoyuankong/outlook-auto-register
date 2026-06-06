# Provider Repo Deep Dive - 2026-05-23

Scope: static research only. Unknown third-party code was cloned under `research_sources/provider_tools/` and not executed. Findings are for Ninjemail flow design, service adapters, UI grouping, and risk assessment.

## Automation Update

- Heartbeat `ninjemail-4` was updated from 30 minutes to 10 minutes.
- The automation prompt now requires parallel searches, fallback to GitHub mirrors/proxies when GitHub is slow or limited, broader open-source sources, and continued static analysis instead of only downloading.
- Direct GitHub clone started failing with reset/connect errors; `https://gh-proxy.com/https://github.com/...` worked for small repositories this round.

## Newly Cloned This Round

| Provider / area | Repository | Local path | Initial classification |
|---|---|---|---|
| Yandex Mail | `hendrikbgr/YandexMail-Account-Creator` | `research_sources/provider_tools/hendrikbgr__YandexMail-Account-Creator` | Real Selenium/undetected-chromedriver flow; uses 5sim and proxies; includes IMAP/POP enablement. |
| Yandex Mail | `selim9445/yandex-mail-creator` | `research_sources/provider_tools/selim9445__yandex-mail-creator` | Real Selenium flow; older no-phone path plus 2captcha image captcha. |
| Mail.com | `jacopoji/mail.com_account_generator` | `research_sources/provider_tools/jacopoji__mail.com_account_generator` | PyAutoGUI click/tab automation; manual captcha; useful only as rough step order. |
| Proton | `mbleskine-droid/ProtempMail` | `research_sources/provider_tools/mbleskine-droid__ProtempMail` | Real Playwright flow with TemporyMail API; strongest Proton reference found so far. |
| SMS24 | `Roshan-Here/Scrap-SMS24` | `research_sources/provider_tools/Roshan-Here__Scrap-SMS24` | Django/BeautifulSoup scraper for `sms24.me`; useful parser reference. |
| SMS24 | `SamiUlHaq27/PhoneNumbers` | `research_sources/provider_tools/SamiUlHaq27__PhoneNumbers` | Scrapy project for numbers/messages from `sms24.me`; clean selector reference. |
| Temp mail | `temp-mail-io/temp-mail-node` | `research_sources/provider_tools/temp-mail-io__temp-mail-node` | Official API SDK; API key required, not free public. Good adapter shape reference. |
| Temp mail | `mailtd/mailtd-node` | `research_sources/provider_tools/mailtd__mailtd-node` | Official API SDK; token/pro tier oriented. Good typed client/error model reference. |

## Provider-Specific Flow Notes

### Proton / ProtonMail

Strongest useful repo this round: `mbleskine-droid/ProtempMail`.

Observed flow:
- Opens `https://account.proton.me/start` with Playwright in headful Chromium.
- Generates username and password locally.
- Creates a temporary mailbox through `https://api.temporymail.com/api/v1`.
- Fills Proton username, password, password confirmation.
- Selects email verification, submits temp mailbox, polls mailbox every 4 seconds for up to 120 seconds.
- Extracts a 6-digit code from email body or subject.
- Completes recovery checkbox using three fallback methods: direct click, label click, JavaScript state change.
- Fills display name, chooses Proton Mail app, dismisses final popups.
- Saves `email:password` to `proton_accounts.txt`.

Useful for Ninjemail:
- Add a provider-isolated Proton flow with iframe-aware locator helpers.
- Use a mailbox adapter contract with `createMailbox`, `pollInbox`, and `extractCode`.
- Recovery checkbox and post-creation popups need fallback click strategies and should not block the main step machine indefinitely.

Risks:
- Uses temporary email verification, which can fail or be blocked.
- Headful automation and anti-detection flags are fragile.
- Do not import directly; use as flow/adapter reference.

### Yandex Mail

Repos studied:
- `hendrikbgr/YandexMail-Account-Creator`
- `selim9445/yandex-mail-creator`

Observed `hendrikbgr` flow:
- Opens `https://passport.yandex.com/registration`.
- Uses `undetected_chromedriver`, per-proxy loop, human-like typing.
- Generates first name, last name, username, recovery name, password, birthday.
- Buys a phone number from 5sim for product `yandex`, polls activation by phone id, enters SMS code.
- After registration, creates an app password, opens `https://mail.yandex.com/?dpda=yes#setup/client`, enables IMAP/POP3, and writes CSV columns:
  `Email, Password, First Name, Last Name, Security Question, Proxy Used, App Password (imap), Phone Number Used, Phone Number ID`.

Observed `selim9445` flow:
- Starts from `https://mail.yandex.com/`, clicks registration.
- Uses `.link_has-no-phone`, fills first name, last name, login, password, hint answer.
- Solves image captcha via 2captcha by downloading `.captcha__image`.
- Writes `mail@yandex.com:password` to `yandexaccounts.txt`.

Useful for Ninjemail:
- Yandex should be a separate provider flow; do not reuse Microsoft/Yahoo ordering.
- Two possible Yandex modes should be modeled separately: phone-required flow and no-phone/captcha flow.
- If supporting IMAP credentials, store both login password and app password as distinct credential fields.

Risks:
- Selectors are old and likely drifted.
- 5sim/2captcha dependencies mean not "free".
- The phone/no-phone branch must be detected at runtime.

### GMX

Repos studied:
- `Zockerbeule/GMX-generator`
- `RUSOCIAL-SU/GMX-Creator`
- `ShadowTheBan/gmx-account-generator`

Observed useful flow:
- Web UI registration URL: `https://registrierung.gmx.net/#.pc_page.mail.index.hero_1.registrierung` in old Selenium reference.
- Request-based registration URL: `https://signup.gmx.com/` followed by `POST https://signup.gmx.com/account/email-registration`.
- Session bootstrap extracts `accessToken`, `clientCredentialGuid`, and `statistics`.
- Registration payload includes `givenName`, `familyName`, `gender`, `birthDate`, `mobileNumber`, US address country/region, password, email, product `gmxcomFree`.
- CAPTCHA site key seen in RUSOCIAL repo: `sk_vKdD8WGlPF5FKpRDs1U4qTuu6Jv0w` for CaptchaFox.
- After creation, repo logs in, handles registration welcome interception, navigates to settings, finds POP3/IMAP settings, toggles checkbox, handles possible image captcha, and saves `email:password`.

Useful for Ninjemail:
- GMX flow likely benefits from a request/session adapter rather than pure DOM driving.
- IMAP/POP enablement is a separate post-registration phase and should be shown separately in UI.
- Session token extraction and form field discovery should be resilient and logged as diagnostic evidence.

Risks:
- RUSOCIAL code has syntax placeholders and commercial/captcha/proxy dependencies; treat as partial reference only.
- ShadowTheBan repo is mostly advertising/Telegram lead generation, not usable code.

### Outlook / Hotmail

Repo studied:
- `MatrixTM/OutlookGen`

Observed flow:
- Opens `https://outlook.live.com/owa/?nlp=1&signup=1`.
- If configured domain is `@hotmail.com`, selects `LiveDomainBoxList` value `hotmail.com`.
- Fills `MemberName`, clicks `iSignupAction`.
- Fills `PasswordInput`, then `FirstName`, `LastName`.
- Fills country, birth month/day/year.
- Switches to `enforcementFrame`, solves FunCaptcha through AnyCaptcha/2captcha, posts `challenge-complete` with session token.
- Writes credentials with `Utils.logger`.

Useful for Ninjemail:
- Confirms Hotmail and Outlook can share Microsoft primitives, but Hotmail must retain a domain-selection branch and must not silently become Outlook.
- The domain option should be an explicit provider-mode field in state and credential output.

Risks:
- Uses external captcha services and proxies.
- Current selectors may drift.
- Auto-updater in repo should not be run.

### Mail.com

Repo studied:
- `jacopoji/mail.com_account_generator`

Observed flow:
- Opens `https://service.mail.com/registration.html?edition=int&lang=en&#.1258-header-signup2-1`.
- Uses PyAutoGUI tab sequencing and image recognition, not DOM selectors.
- Fills first name, last name, birthday, desired address, password, security question.
- Clicks email verification and captcha areas; asks user to finish captcha manually if not complete.
- Saves screenshot of registration details.

Useful for Ninjemail:
- Step order only: profile, DOB, address, password confirmation, security question, verification/captcha, accept/complete.
- Because it is coordinate/image driven, it is not directly suitable for browser extension logic.

Risks:
- Hardcoded password and security answer in sample.
- No robust success/credential persistence.

### 163 / NetEase Mail

Source inspected through GitHub API:
- `bayson/autojs`, file `src/work/网易邮箱-注册.js`.

Observed flow:
- Android Auto.js flow targeting QQ Browser package `com.tencent.mtt`.
- Opens `mail.163.com`.
- Handles web/mobile entry screens.
- Registration page fields: username `6-18位字母数字组合`, password `6-16位字母数字字符组合密码`.
- Clicks agreement checkbox and `点此进行验证`, waits for `验证成功`, clicks next.
- Phone verification page requests `register_phone`, clicks `获取验证码`.
- Alternate send-SMS confirmation page calls `register_send_code`, waits, clicks `我已发送短信，注册`.
- Success page marked by `恭喜您，` and home by `收件箱`.

Useful for Ninjemail:
- Domestic providers may require mobile browser/app automation patterns and SMS send-confirm flows, not just receive-code flows.
- Step model should allow `sms_send_required` as a separate challenge type from `sms_receive_code`.

Risks:
- Android/Auto.js environment, not directly portable to Chrome extension.
- Likely outdated UI text.

## SMS / OTP / Temporary Number Notes

### SMS24

Repos studied:
- `SamiUlHaq27/PhoneNumbers`
- `Roshan-Here/Scrap-SMS24`

Observed selectors:
- Number list page: `https://sms24.me/en/numbers`
- Country page: `https://sms24.me/en/countries/{code}`
- Number page: `https://sms24.me/en/numbers/{number}`
- Number cards: `a.callout`
- Number text: `div.text-primary::text` or `div.fw-bold.text-primary.placeholder`
- Country: `h5::text` or `h5.text-secondary.placeholder`
- Messages: parse `dl` pairs; timestamp from `div[data-created]`, sender from `label a::text`, body from `span::text`.

Useful for Ninjemail:
- SMS adapters should not only test homepage status. A usable service needs three checks: list page parses, number page parses, recent messages parse.
- Plugin UI should show `free public`, `scrape based`, `last tested`, `numbers parsed`, and `messages parsed`.

Risks:
- Public number services are often blocked by target providers and change markup often.
- Scraping may trigger 403/500 from hosting providers; need per-provider timeout and error isolation.

### Temp Email APIs

Repos/packages studied:
- `@temp-mail-io/sdk` / `temp-mail-io/temp-mail-node`
- `mailtd` / `mailtd/mailtd-node`

Useful adapter patterns:
- Typed client wrapper around `fetch`.
- `createEmail`, `listEmailMessages`, `getMessage`, `deleteEmail`.
- Explicit rate-limit tracking and typed error classes.
- Overrideable `baseUrl`, timeout, and fetch implementation.

Suitability:
- Good for Ninjemail's email OTP retrieval architecture, but these are API-key/token services, not free public no-login services.
- Mark as `api_key_required`, not `free_public`.

## Search Results Worth Following Next

- `0x178F/YandexMail-Account-Creator`: likely a fork/variant of Yandex flow; inspect next if time.
- `jacopoji/mail.com_account_generator`: already inspected; only step-order value.
- `iP1SMS/disposable-phone-numbers`: large disposable phone number list, not cloned because disk usage is large; inspect via API/file if needed.
- `fetch-phone-numbers` npm: claims to fetch free US phone numbers from `receive-sms-free.cc`, but npm metadata did not expose a repository. Inspect package tarball metadata later without running it.
- Search gaps remain for AOL, Zoho, iCloud/Apple ID, Mail.ru, Naver, Daum/Kakao, Sina, Sohu. Current GitHub searches returned mostly empty/noise.

## Ninjemail Integration Takeaways

- Add provider-specific flow modules rather than shared generic signup logic.
- Keep Microsoft Outlook and Hotmail split by selected domain even if using shared selectors.
- Add challenge types: `captcha_required`, `sms_receive_code`, `sms_send_required`, `email_otp_required`, `imap_enablement`.
- Add service status tags in the plugin: `free_public`, `api_key_required`, `paid_or_credit_required`, `scrape_based`, `usable`, `blocked`, `last_tested`.
- Persist credentials with provider, domain, registration mode, challenge type, recovery/app password fields, and unique filename/append-only log.

## 2026-05-23 20:21 CST Heartbeat Round

Scope:
- Focused on providers that were still thin after earlier rounds: Naver, Sina, Apple ID/iCloud-adjacent flows, 163/126 NetEase, Tutanota, Yandex variants, AOL, Zoho, Mail.ru, QQ/Sohu.
- Used GitHub code/repo search, npm metadata/tarballs, PyPI metadata/wheels, and live HTTP/parser probes for public SMS sites.
- Static analysis only. No third-party project code was executed.

### Naver

Source inspected through GitHub API:
- `johanna-II/naver_e2e_test`, file `page_objects/registration_page.py`.

Observed flow:
- Selenium page object aimed at `https://nid.naver.com/user2/join/agree?lang={language}`.
- Supports language variants: `ko_KR`, `en_US`, `zh-Hans_CN`, `zh-Hant_TW`, `ja_JP`.
- Consent step: select all terms via `chk_all`, continue via `btnAgree`.
- Form fields: `id`, `pswd1`, `pswd2`, `name`, `yy`, `mm`, `dd`, optional `email`, `nationNo`, `phoneNo`, `authNo`.
- SMS branch is language dependent: non-Korean flow exposes send-code and enter-code helpers; Korean flow has separate resident/foreigner field handling.

Useful for Ninjemail:
- Naver should be a distinct provider module with localized selectors and a `sms_receive_code` challenge branch.
- The plugin step model should not assume every locale has the same gender/nationality/phone fields.

Risks:
- Looks like an educational/E2E test page object, not a maintained account creator.
- Password/random-data generation is weak and hardcoded; use only as selector/state reference.

### Sina Mail

Source inspected through GitHub API:
- `k1myok/fetch`, file `src/com/longriver/netpro/webview/carcontroller/SinaMailRegister.java`.

Observed flow:
- Java Selenium/Firefox flow against `https://mail.sina.com.cn/register/regmail.php`.
- Switches to phone registration tab, fills phone-number account, clicks SMS send button, polls an external SIM-card pool/database, fills SMS code, fills password, submits.
- Contains screenshot/captcha helper code wired to a third-party captcha service.

Useful for Ninjemail:
- Sina needs its own `sina_mail` provider flow with `sms_receive_code` and old-style captcha-blocking states.
- SMS polling should be adapter-driven and status-tagged; do not hardwire one card-pool backend into the provider flow.

Risks:
- Very old code, likely stale selectors.
- Tightly coupled to private SMS card-pool infrastructure and captcha service.
- Not suitable to run or copy directly.

### Apple ID / 163 / Yandex / Tutanota Multi-Flow Repo

Source inspected through GitHub API:
- `arshiay/create-appleId`.
- Files read: `README.md`, `package.json`, `apple-signup.js`, `getMail.js`, `saveAppleId.js`, `163email-signup.js`, `yandex-email-signup.js`, `tutanota-email-signup.js`, `mail-email-signup.js`.

Observed Apple ID flow:
- Selenium 3 / Chrome / standalone Selenium server.
- Opens `https://appleid.apple.com/account`.
- Generates Apple ID profile fields, security questions, DOB, country, password, then handles image captcha and email verification.
- Email OTP is retrieved through IMAP and parsed from the latest inbox message.
- Saves Apple ID, password, security answers, birth date, and country through an external web-service client.

Observed 163 helper:
- Opens `http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=163mail_right`.
- Fields include `nameIpt`, `mainPwdIpt`, `mainCfmPwdIpt`, `mainMobileIpt`, `vcodeIpt`, `vcodeImg`, `mainAcodeIpt`.
- Attempts to capture image captcha pixels through browser canvas.

Observed Yandex helper:
- Opens `https://passport.yandex.com/registration/mail`.
- Uses fields `firstname`, `lastname`, `login`, `password`, `password_confirm`.
- Switches from phone verification to captcha/security-question branch.

Observed Tutanota helper:
- Opens `https://app.tutanota.com/#register`.
- Fields include `mailAddress`, `newpassword`, `newpassword2`, `termsInput`.
- Waits until the submit button is enabled.

Observed Mail.com helper:
- Starts at `https://service.mail.com/registration.html`, but the file appears incomplete/mixed with copied Yandex selectors and should be treated as unreliable.

Useful for Ninjemail:
- The Apple ID flow is useful as a reference for `email_otp_required` plus IMAP polling, but Apple ID is not an email-inbox provider in the same sense as Outlook/Yahoo/Gmail.
- NetEase/163 needs a dedicated phone/captcha branch; do not reuse Apple ID or Yandex sequence.
- Tutanota/Proton-style privacy mailbox providers can share only generic primitives such as wait-for-enabled and OTP polling, not provider steps.

Risks:
- Includes captcha-solving dependencies and bundled/old Selenium binaries.
- Hardcoded credentials, weak generators, external services, and recursive retry loops.
- Do not run or integrate directly.

### SMS Service Live Parser Probes

All probes were simple HTTP GET/parser checks with a browser user-agent. No provider signup flow was attempted.

`receive-sms.io`
- Homepage: HTTP 200, about 114 KB, 24 phone-like matches.
- Parsed number links such as `/temporary-numbers/{country}/{number}/`.
- Detail page: HTTP 200, about 54 KB; message rows are present.
- Useful selectors/patterns: `.cards-item`, `.tel`, `.sms-item`, `.left[data-title="From"]`, `.center[data-title="Message"]`, timestamp column where present.
- Tag recommendation: `free_public`, `scrape_based`, `usable_parser_probe`, `public_inbox`.

`sms24.me`
- Number list: HTTP 200, about 25 KB, 18 phone-like matches.
- Detail page: HTTP 200, about 21 KB; public message articles are present.
- Useful selectors/patterns: `/en/numbers/{number}`, article cards, sender link prefixed by `From:`, `<time>`, message paragraph.
- Tag recommendation: `free_public`, `scrape_based`, `usable_parser_probe`, `public_inbox`.

`temporary-phone-number.io`
- Homepage: HTTP 200, about 82 KB, 8 phone-like matches.
- Parsed number links such as `/sms/{number}/`.
- Detail page: HTTP 200, about 55 KB; message rows are present.
- Useful selectors/patterns: `.list-numers-item[data-time]`, `.td2`, load-more metadata.
- Tag recommendation: `free_public`, `scrape_based`, `usable_parser_probe`, `public_inbox`, with optional paid upsell warning.

`receive-smss.live`
- Documentation page: HTTP 200, about 67 KB.
- Documentation explicitly distinguishes free public numbers, premium shared numbers, and private paid numbers.
- Tag recommendation: `free_public` only for the public tier; `login_required`/`paid_or_credit_required` for premium/private groups.

Important:
- These public inboxes may be blocked by target mail providers even when the parser works. Plugin UI should show two independent indicators: `parser_ok` and `accepted_by_target_unknown/blocked`.
- Do not display all services flat. Use a collapsed `Free public SMS inboxes` group with per-service detail rows and last-test metadata.

### npm / PyPI Package Notes

`fetch-phone-numbers@1.2.0`
- Package downloaded to `research_sources/package_snapshots/fetch-phone-numbers-1.2.0.tgz`.
- Claims to fetch free US numbers from `receive-sms-free.cc`.
- Static read found hardcoded Cloudflare/session cookies and a fixed sample phone number in the example.
- Suitability: low. Mark `scrape_based`, `fragile`, `hardcoded_cookie`, `do_not_run_unknown`.

`temporary-phone-number@1.0.9`
- Package downloaded to `research_sources/package_snapshots/temporary-phone-number-1.0.9.tgz`.
- Metadata points to Textita.com disposable phone-number API.
- Tarball contains README/package metadata only; no implementation code in the package.
- Suitability: low until API docs/implementation are found. Mark `api_service`, `insufficient_package_code`.

`smsactivate==1.5`
- Wheel downloaded to `research_sources/package_snapshots/smsactivate-1.5-py3-none-any.whl`.
- Official Python wrapper for `sms-activate.org` API.
- Exposes balance, number rental, activation status, full SMS, countries/prices, rent list, and set-status actions.
- Suitability: adapter reference for paid/API-key service only. Mark `api_key_required`, `paid_or_credit_required`, not `free_public`.

### Negative / Low-Signal Search Results

- AOL/Yahoo-family searches for `signup.aol.com/account/create` returned no useful provider-specific creator in this round.
- Zoho-specific repo/code searches were empty or unrelated.
- Mail.ru searches were mostly bug-bounty lists, account checkers, or leaked/noisy data, not creation flows.
- QQ/Sohu searches were mostly generic SMS endpoints, login docs, or unrelated web-app registrations; no clean provider-specific mailbox registration flow yet.

### Mail.ru Provider-Specific Creator Round

Sources inspected through GitHub API, static read only:
- `FunnyRain/autoreg-mail-ru`, file `app.php`.
- `Draugrol/MailRu-autoreg`, file `src/main.py`.
- `entreee/MailRuAutoreg-python`, file `MailRuAutoreg.py`.
- `try1975/RegBot`, file `MailRu.Bot/MailRuRegistration.cs`.
- `davomelkumyan40/Mail_Ru_Generator`, file `MailRuCreator/MailRuCreator.cs`.
- `DanilTrash/mailru_autoreg`, file `browser.py`.
- `Dopneer/MikuBomber`, file `registration/reg_mail.js`.

Common observed signup surface:
- Signup URL family: `https://account.mail.ru/signup` and `https://account.mail.ru/signup?rf=auth.mail.ru&from=main`.
- Current-ish browser selectors include `#fname`, `#lname`, `name=username`, `name=partial_login`, `name=password`, `name=repeatPassword`, DOB widgets under `div[data-test-id="birth-date"]`, gender labels such as `label[data-test-id="gender-male"]`, captcha image `img[data-test-id="captcha-image"]`, captcha input `input[data-test-id="captcha"]`, and submit buttons such as `button[data-test-id="first-step-submit"]`.
- Older selectors still useful as fallbacks include `[name="firstname"]`, `[name="lastname"]`, `.b-date__day`, `.b-date__month`, `.b-date__year`, `.b-email__name input`, `.b-email__domain`, `[name="password_retry"]`, `.b-captcha img`, and `.b-captcha__code input`.

Important branch patterns:
- `try1975/RegBot` models Mail.ru with separate `RegistrateByPhone(page)` and `RegistrateByEmail(page)` branches. That is the cleanest architectural reference because it does not force every registration through one linear flow.
- The same repo uses an SMS-service abstraction with request id, `GetSmsValidation`, code entry, and `SetSmsValidationSuccess`. This maps well to Ninjemail's desired service adapter layer.
- `entreee/MailRuAutoreg-python` detects `id='phone-number__phone-input'` and returns a phone-required failure state. This is useful for a Ninjemail `sms_receive_code` or `sms_send_required` block instead of silently retrying.
- Multiple repos use captcha solving or manual captcha capture. Ninjemail should represent this as `captcha_required`; do not embed any third-party solver directly.

Output/persistence notes:
- `FunnyRain/autoreg-mail-ru` appends `email@mail.ru:password` to `emails.txt`.
- `entreee/MailRuAutoreg-python` saves tab-separated rows including email, first name, last name, password, and reserve email into `Autoreg_MailRU.txt`.
- These reinforce the need for Ninjemail credential persistence to be append-only and uniquely named per account/run; never overwrite a provider's previous four-credential file.

Suitability:
- Best reference: `try1975/RegBot` for branch/state design and SMS adapter shape.
- Useful selector references: `entreee/MailRuAutoreg-python`, `DanilTrash/mailru_autoreg`, and old C#/PhantomJS code for fallback selectors.
- Low suitability/risk: `Dopneer/MikuBomber` appears adjacent to SMS endpoint abuse/bomber behavior. Treat only as negative/selector reference and do not integrate.

### NetEase 163 / MailRegister Deep Dive

Sources inspected:
- `yqMac/regTool`, file `RegTools/WYEmail.cs`, through GitHub API.
- `wondaeyr/MailRegister`, cloned from Gitee to `research_sources/provider_tools/gitee_wondaeyr__MailRegister`, static read only.
- `nagasawaja/ldController`, file `163Reg.py`, through GitHub API.
- `bayson/autojs`, file `README.md`, through GitHub API.

Observed 163 request flow from `MailRegister/RegThread.cpp`:
- Entrance: `http://reg.email.163.com/unireg/call.do?cmd=register.entrance&flow=m_main&from=m_wapreg`.
- Extracts `sid`, hidden prepare iframe URL, and `envalue`/environment token from the entrance HTML.
- Username check: `cmd=urs.checkName` with body `name={username}`.
- Form telemetry: repeated `cmd=register.formLog` calls for username, password, and captcha fields.
- Captcha image: `cmd=register.verifyCode&v=common/verifycode/vc_en&env={env}&t={timestamp}` returning JPEG content.
- Resume flow: `cmd=register.resume` with `vcode`, `uid`, and `suspendId`.
- Final submit: `https://ssl.mail.163.com/regall/unireg/call.do;jsessionid={sid}?cmd=register.start`.
- Final submit body shape: `name={user}&flow=m_main&uid={user}@163.com&password={password}&confirmPassword={password}&vcode={captcha}&from=m_wapreg&forcedFlow=m_main`.

Observed 163 request flow from `yqMac/regTool`:
- Similar NetEase endpoints, including `register.entrance`, `urs.checkName`, `register.formLog`, `register.verifyCode`, `prepare.jsp`, and `register.start`.
- Error handling mentions `INVALID NAME`, `NAME_EQUALS_PASSWORD`, `PASSWORD TOO SIMPLE`, `INVALID MOBILE`, `BIND TOO MANY`, and `VCODE_NOT_MATCH`.
- Post body may include `mobile` depending on branch, so Ninjemail should not assume captcha-only 163 registration.

Observed minimal 126/163 probe from `nagasawaja/ldController/163Reg.py`:
- Python 2/early Python 3 style script that opens `http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=126mail`.
- Builds a cookie jar and browser-like headers only; no full registration flow found in the first static pass.
- Useful mainly as a hint that NetEase mail domains share the `reg.email.163.com` entrance surface, while the `from=126mail` value preserves the selected domain context.

Observed Android Auto.js NetEase flow from `bayson/autojs`:
- README describes an Auto.js mobile automation script `dist/网易邮箱-注册.js` for NetEase mail registration in QQ Browser.
- Start surface: open `https://mail.163.com` in QQ Browser, then run the Auto.js script.
- README screenshots/steps identify separate states: ad page, login page, registration page, manual verification page, phone-code input, send-verification-SMS page, registration-success page, and final redirect page.
- It explicitly says the verification page still requires manual clicking, while phone number acquisition and SMS sending are integrated with a verification-code platform.

Useful for Ninjemail:
- Reinforces that NetEase should expose separate plugin states for `captcha_required`, `sms_send_required`, `sms_receive_code`, and `manual_verification_page`.
- Since this is Android/QQ Browser automation, it is not directly portable to the desktop browser extension. Use it only to improve state labels and blocker detection.

Useful for Ninjemail:
- NetEase/163 should be its own provider module, not a generic Chinese-mail flow.
- The implementation should model a request/session state machine separately from browser-DOM flow: `entrance_loaded`, `username_checked`, `captcha_required`, `resume_required`, `submit_started`, and provider-specific error states.
- `126.com` and `yeah.net` may share NetEase primitives, but the domain choice must remain explicit and must not collapse into `163.com`.

Risks:
- The code is old, Windows/MFC-specific, and includes captcha-recognition hooks. It should not be run.
- The request endpoints may now reject automation, require modern browser fingerprints, or require phone verification. Treat as historical flow intelligence, not a guaranteed working adapter.
- The Auto.js reference requires root/Android/Auto.js and external SMS-code platform integration. Do not clone/run it inside the plugin workflow.

### Browser Extension Adaptation Validation 2026-05-24

Applied the foreign-provider state lessons into the browser extension as provider-isolated flows for:
- Proton
- GMX
- AOL
- Zoho
- Yandex
- Mail.com
- iCloud
- Mail.ru
- Naver
- Kakao
- Tutanota

Validation method:
- Static syntax checks for extension scripts.
- Python browser-extension test suite.
- Local Playwright HTTPS fixture pages that mimic provider-specific normal fields and blocker pages.
- No real provider account creation, no CAPTCHA solving, no SMS/OTP bypass.

Latest passing report:
- `diagnostics_runs/foreign_provider_flow_fixture_20260524_014721.json`
- `diagnostics_runs/foreign_provider_flow_fixture_20260524_014721.md`
- `diagnostics_runs/extension_load_smoke_20260524_0148.md`

Result:
- All 11 foreign providers passed normal-step detection/fill checks.
- All 11 provider-specific blocker steps stopped at the expected provider step.
- This confirms Outlook/Hotmail/Gmail/Yahoo flow sequencing is not reused for the newly added foreign providers.
- The unpacked extension loaded in Playwright Chromium and the Manifest V3 service worker started successfully.

### Browser Extension Provider Validation 2026-05-24 12:22 CST

Scope:
- Re-ran the provider-isolation fixture after adding domestic provider fixture cases.
- Covered 17 provider keys total: Proton, GMX, AOL, Zoho, Yandex, Mail.com, iCloud, Mail.ru, Naver, Kakao, Tutanota, NetEase 163, NetEase 126, NetEase Yeah, QQ, Sina, and Sohu.
- The fixture still uses local mocked HTTPS pages and explicit blocker pages. It does not create real accounts, solve CAPTCHA, bypass SMS, or bypass OTP.

Latest passing reports:
- `diagnostics_runs/foreign_provider_flow_fixture_20260524_122259.json`
- `diagnostics_runs/foreign_provider_flow_fixture_20260524_122259.md`
- `reports/extension-flow-runs/20260524_122259/summary.json`
- `reports/extension-flow-runs/20260524_122259/summary.md`

Result:
- All 17 provider cases passed normal-step detection/fill checks.
- All 17 provider-specific blocker cases stopped at the expected provider-specific step.
- Hotmail remains a separate provider key and domain from Outlook.
- NetEase variants preserve the selected domain branch: `netease163`, `netease126`, and `neteaseyeah`.
- Sina is modeled as a phone-account-first branch instead of being forced through a generic username/password flow.

Additional validation:
- `node --check` passed for `browser_extension/content/outlook-signup.js`, `browser_extension/shared/flow-state.js`, `browser_extension/background/background.js`, `browser_extension/sidepanel/sidepanel.js`, and `tools/provider_flow_fixture_test.js`.
- Browser-extension pytest passed: `36 passed`.
- Full pytest suite passed: `136 passed`.
- Extension load ACK smoke passed at `reports/extension-flow-runs/20260524_130901/extension-load-ack`: extension loaded, Manifest V3 service worker ready, content script injected, start-button ACK succeeded, and blockers were empty.

Current blocker policy:
- Real provider CAPTCHA/SMS/OTP pages must remain explicit stop states in the plugin.
- A provider should only advance to its next configured step after its own required fields are present and accepted by the page.
- New provider work should be added one provider at a time with a fixture normal page, fixture blocker page, report output, and a separate provider step prefix.
