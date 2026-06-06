# GitHub 邮箱注册流程参考筛选 2026-05-23

本轮只做流程参考筛选，不把第三方注册器代码直接合并进插件主流程。

## 搜索到的项目

| 项目 | 语言 | 星标 | 说明 | 处理 |
| --- | --- | ---: | --- | --- |
| MatrixTM/OutlookGen | Python | 412 | Outlook account generator | 不下载执行，不合并；仅确认 Microsoft 注册器普遍采用用户名、密码、资料、生日、验证后的分步流程 |
| Skuxblan/Outlook-account-creator | Python | 82 | Outlook account creator with captcha automation | 不下载执行，不合并；涉及自动验证码处理 |
| 0xrushi/mass-outlook-email-generator | Python | 37 | Selenium mass email account generator | 不下载执行，不合并；面向批量生成 |
| kaajjaak/OutlookGenerator | Python | 10 | Selenium/WireGuard/NopeCha Outlook generator | 不下载执行，不合并；涉及验证码和代理 |
| SEO-AIO/Microsoft-Account-Generator | Python | 9 | Microsoft/Outlook Selenium generator | 不下载执行，不合并；流程已被本插件 Outlook/Hotmail 链路覆盖 |
| YOGESHVENKATAPATHI/dropbox_auto_creator | JavaScript | 2 | 带浏览器扩展和临时邮箱的账号创建系统 | 不下载执行，不合并；不是邮箱注册流程 |
| adkitteamolv/Practise_selenium | 未标注 | 0 | Gmail and Yahoo signup 练习 | 不下载执行，不合并；过旧，不能作为稳定流程来源 |

## 已落地到插件的流程隔离

- Outlook: `plugin_ready -> open_signup -> fill_username -> fill_password -> fill_profile -> fill_birthdate -> challenge -> post_challenge -> final_state -> export_credentials`
- Hotmail: 与 Microsoft 注册页同链路，但 provider/domain 保持 `hotmail.com`，不会自动改成 Outlook。
- Gmail: `plugin_ready -> open_signup -> fill_gmail_profile -> fill_gmail_birthdate -> fill_gmail_username -> fill_gmail_password -> challenge -> post_challenge -> final_state -> export_credentials`
- Yahoo: `plugin_ready -> open_signup -> fill_yahoo_account_form -> challenge -> post_challenge -> final_state -> export_credentials`

## 插件接入原则

- 第三方项目只作为流程结构参考，不运行、不导入依赖、不复用绕验证码逻辑。
- 插件前端通过“当前邮箱流程”面板显示当前 provider 的独立步骤链路。
- 后台和 content script 继续通过 provider key 选择流程，避免 Yahoo 单页表单和 Microsoft 分步流程混用。
