# Research Lessons Memory

## 2026-05-23 open-source search round 1

- Treat third-party email account creators as flow references only. Many include captcha solving, proxies, fingerprinting, bulk generation, or commercial redirects, so do not execute or merge them directly.
- Keep provider flows isolated by provider key. Outlook and Hotmail can share Microsoft page primitives, but Hotmail must preserve `hotmail.com`; Gmail and Yahoo need separate step IDs and detectors.
- Yahoo registration should be treated as a single required-form flow until all required fields are correct. Do not reuse Microsoft username/password/profile/birthdate step sequencing for Yahoo.
- Gmail references are mostly Selenium/Cucumber examples; useful parts are field detection, dropdown retry, stale-element retry, and next-button gating, not mass-creation logic.
- SMS adapters should share a normalized shape: `list_numbers(provider, country, limit)` and `fetch_messages(provider, phone, message_url, limit)`.
- Do not mark a SMS source as usable from homepage HTTP status alone. Usability means number list loads, message page loads, and a code-like token can be extracted from a real message page.
- Frontend should display SMS services in collapsible groups with status tags: `free_public`, `login_required`, `api_key_required`, `last_tested`, `usable`.
- Store raw search results and curated results separately. Dedupe by canonical URL plus repository full name/package name.

## 2026-05-23 provider deep-dive round 2

- When direct GitHub clone fails or rate-limits, try a small `git ls-remote` against mirror/proxy URLs first. This round `https://gh-proxy.com/https://github.com/...` worked for small repos while direct GitHub clone failed.
- Proton's current useful references are Playwright/iframe-aware flows with email OTP polling. Model Proton as its own provider with `email_otp_required`; do not mix it with Yahoo/Gmail/Microsoft flows.
- Yandex has at least two distinct branches: phone/5sim activation plus IMAP app-password setup, and older no-phone/captcha registration. The plugin flow state must represent these branches separately.
- GMX request-based flows expose a useful two-phase model: account creation through signup API/session tokens, then post-registration POP3/IMAP enablement. UI should display IMAP enablement as a separate post-step.
- Domestic providers such as 163 may require SMS send-confirm (`我已发送短信，注册`), not just receiving a code. Add an `sms_send_required` challenge type to avoid mislabeling it as normal OTP receive.
- For public SMS services like sms24.me, mark usability only after list page, number detail page, and message extraction all work. Homepage or domain status alone is not enough.
- Temp email SDKs such as temp-mail.io and Mail.td offer clean adapter patterns but are API-key/token services, so mark them `api_key_required`, not free public.

## 2026-05-23 heartbeat round at 20:21 CST

- Naver has a localized registration surface. Treat language as part of the provider state because Korean/non-Korean flows expose different gender, nationality, phone, and SMS-code fields.
- Sina and NetEase/163 references are old but useful for state modeling: phone account, captcha image, SMS receive, and sometimes provider-specific send-confirm are separate challenge states.
- Apple ID should not be mixed into normal mailbox-provider registration. It is better modeled as an identity/account flow that depends on an already working inbox plus `email_otp_required`.
- Tutanota/Proton-style mailbox services may share generic browser primitives, but their selectors and blocking states must remain provider-specific.
- Public SMS service health needs three fields in UI/backend: `homepage_ok`, `number_list_ok`, and `message_detail_ok`. Add `parser_ok` separately from `accepted_by_target`.
- Mark free SMS sites as `free_public` only when the public number list/detail pages parse. Paid/API services such as smsactivate must be `api_key_required` and `paid_or_credit_required`.
- npm packages with hardcoded Cloudflare/session cookies are not stable adapters. They can reveal selectors, but should be marked `fragile` and never treated as a reliable backend.

## 2026-05-23 heartbeat round at 21:50 CST

- Long `gh api repos/.../contents/...` reads should be avoided in heartbeat work because they look like stalls. Use short batches, local clones under `research_sources/`, or one-file reads with visible progress.
- Mail.ru has enough independent references to deserve a dedicated provider flow. Keep phone and reserve-email branches separate, and surface `captcha_required` plus `sms_receive_code` instead of looping blindly.
- The best Mail.ru architectural reference is the C#/PuppeteerSharp flow that separates `RegistrateByPhone` and `RegistrateByEmail` and delegates SMS to an adapter. Use the state model, not the implementation.
- Mail.ru selectors vary by era. Keep a fallback selector table per provider, but never let fallback tables become a shared Outlook/Yahoo/Gmail step sequence.
- NetEase/163 references show an HTTP-session flow with entrance, username check, form telemetry, captcha image, resume, and final submit. Model this as a NetEase-specific state machine.
- NetEase domains `163.com`, `126.com`, and `yeah.net` can share primitives, but the selected domain must stay explicit just like Hotmail must not silently become Outlook.
- Credential saving must be append-only and include unique account/run names. The research confirms many tools save simple text outputs, which increases overwrite risk if Ninjemail writes fixed filenames.

## 2026-05-23 heartbeat round at 23:23 CST

- `bayson/autojs` is an Android Auto.js reference for NetEase/163 mail registration, not a desktop extension flow. It confirms the provider states but is not directly portable.
- NetEase mobile registration should model ad/login/register/manual-verify/SMS-send/SMS-code/success/redirect states separately. Do not collapse these into a generic `phone_verification` label.
- Repos that require Android root, Auto.js, QQ Browser, or external SMS-code platforms should be marked `platform_mismatch` and `do_not_run_unknown`; keep only state-machine lessons.

## 2026-05-24 foreign provider fixture validation

- Browser-extension provider flows now cover Proton, GMX, AOL, Zoho, Yandex, Mail.com, iCloud, Mail.ru, Naver, Kakao, and Tutanota as separate provider keys.
- Generic provider pages must detect provider-specific input fields before falling back to generic `post_challenge`; otherwise a partially filled signup page can be mislabeled as a challenge too early.
- Manual sidepanel `run_step` needs temporary autopilot context so safe text-entry helpers can type into local fixture/provider pages. Without this, manual step execution appears to succeed but leaves fields empty.
- Provider blockers such as `proton_email_otp`, `aol_phone`, `mailru_phone_or_captcha`, and `gmx_imap_enablement` should be supported as explicit stop states, not reported as unsupported steps.
- Local Playwright fixtures are the correct regression layer for provider isolation: they can verify detection, field filling, and blocker-stop behavior without creating real accounts or bypassing CAPTCHA/SMS/OTP.

## 2026-05-24 17-provider fixture validation

- The current browser-extension fixture covers 17 provider keys: Proton, GMX, AOL, Zoho, Yandex, Mail.com, iCloud, Mail.ru, Naver, Kakao, Tutanota, NetEase 163, NetEase 126, NetEase Yeah, QQ, Sina, and Sohu.
- Provider isolation is the main regression guard. Each provider needs its own step prefix and blocker mapping, even when multiple providers share a registration surface.
- Hotmail must remain `hotmail.com` when the selected provider is Hotmail. Microsoft page reuse must not collapse Hotmail into Outlook.
- NetEase domains can share implementation primitives, but the chosen domain branch must stay explicit as `netease163`, `netease126`, or `neteaseyeah`.
- A provider fixture should always include both a normal form page and a blocker page. Passing only the normal page can hide challenge-state regressions.
- Extension startup must be checked separately from flow fixtures. The load ACK smoke should verify unpacked extension load, Manifest V3 service worker readiness, content-script injection, and start-button acknowledgment.
- Latest local validation passed: provider fixture `foreign_provider_flow_fixture_20260524_122259`, extension load ACK `20260524_130901`, browser-extension pytest `36 passed`, and full pytest `136 passed`.
