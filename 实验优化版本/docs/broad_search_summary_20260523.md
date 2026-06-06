# Broad Search Summary 2026-05-23

本轮只做广泛搜索和筛选归档，未运行第三方项目，未把第三方注册器代码合并进插件。

## 本地搜索产物

- `docs/broad_github_search_20260523.json`: GitHub API 第一轮宽搜原始结果，64 个唯一仓库。
- `docs/broad_github_search_20260523.md`: 第一轮宽搜表格。
- `docs/broad_github_search_filtered_20260523.json`: GitHub API 精搜过滤结果，34 个候选。
- `docs/broad_github_search_filtered_20260523.md`: 精搜过滤表格。
- `docs/github_email_registration_research_20260523.md`: 前一轮人工筛选记录。

## 邮箱注册流程参考候选

| 类别 | 候选 | 价值 | 风险/备注 |
| --- | --- | --- | --- |
| Microsoft/Outlook | silvestrodecaro/microsoft-account-creator | JavaScript，Microsoft/Outlook 账号创建流程参考 | 不运行；可能包含批量创建或绕验证逻辑 |
| Microsoft/Outlook | ilyasbelfar/Outlook-Account-Creator | Python/Selenium，Outlook 步骤参考 | 明确提到 FunCaptcha solving，不接入绕验证逻辑 |
| Microsoft/Outlook | kalodis/OutlookEmailCreator | Selenium + 2Captcha，字段步骤可作参考 | 依赖付费验证码服务，不直接接入 |
| Microsoft/Outlook | JRBusiness/JMR-OutLook-Creator | Selenium 批量创建流程参考 | 面向 mass create，不能照搬 |
| Gmail | CryonicsX/Gmail-Account-Creator | Gmail 流程字段/步骤参考 | 多线程、代理、手机验证，风险高 |
| Gmail | nischalk17/Signup-Automation---Python-Selenium | 多页 signup 流程、dropdown retry、OTP 测试思路 | 不直接用于创建邮箱账号 |
| Gmail/Yahoo | adkitteamolv/Practise_selenium | Gmail and Yahoo signup 练习项目 | 2015 年项目，过旧，只能看大概字段顺序 |
| Yahoo | xbaika/yahoo-account-creator | Yahoo 与 Hotmail/Outlook 模式描述 | 疑似商业/闭源导流，不接入 |

## 临时 SMS / 接码候选

| 类别 | 候选 | 价值 | 风险/备注 |
| --- | --- | --- | --- |
| 免费公共号码 | InstantNum | 免费公共 inbox，支持国家较少 | 公共短信可见，需实测页面结构 |
| 免费公共号码 | ReceiveSMS.co | 声称多国家和大量 active numbers | 需实测号码页和短信页 |
| 免费/付费混合 | Quackr | 已在插件候选中；公开说明 API 面向租号客户 | 免费号码可抓页面，API 可能需付费租号 |
| 免费公共号码 | TempNumber.live | 免费临时号码页面 | 需实测是否真实可读、是否动态渲染 |
| 免费/需账号 | Numtapper | 已在插件候选中；页面称需创建账号或登录获取号码 | 插件需标注免费/需登录/可用性 |
| 免费公共号码 | Textverified free | 提供 free numbers 页面 | API 是付费/账号体系，免费页需单独抓取 |
| API/账号 | OnlineSim | 官方文档有 free numbers API，但需要注册/API key | 可做“可配置 API 服务”，不能标成纯免登录 |
| API/账号 | SMS-Activate | PyPI 和 Node wrapper 多，适合 paid API adapter | 不是免费公共号码 |
| API/账号 | TextVerified API | 官方 automation/API 页面 | 适合可配置 API adapter，不是公共免费 |

## 筛选结论

- 邮箱注册第三方仓库多数是批量账号创建、代理、验证码绕过或商业导流项目，只能作为流程字段参考，不应直接下载运行或合并。
- 免费公共接码站点必须实测 `列表页 -> 号码页 -> 短信页 -> 验证码提取` 四步，不能只靠 HTTP 200 标记可用。
- 插件里建议把接码服务分成三类显示：`免费公共`、`免费但需登录/不稳定`、`API/需密钥`。
- 邮箱流程继续按 provider 隔离：Outlook/Hotmail、Gmail、Yahoo 分开，不共享步骤执行器。

## 下一步建议

1. 对新发现的 SMS 候选做插件适配前实测。
2. 把通过实测的候选加入 `FREE_SMS_PROVIDER_CATALOG` 和 `ninjemail/service_adapters.py`。
3. 每个服务记录 `free/public/login_required/api_key_required/last_tested/ok_count`，前端折叠显示。
