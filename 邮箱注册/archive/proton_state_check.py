#!/usr/bin/env python3
"""Proton CAPTCHA - 分析当前页面状态"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser
import logging, base64
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUT = os.path.join(os.path.dirname(__file__), "proton_steps")
os.makedirs(OUT, exist_ok=True)

def snap(browser, name):
    r = browser._send_cmd("Page.captureScreenshot", {"format": "png"})
    path = os.path.join(OUT, f"{name}.png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(r['data']))
    return path

def eval_json(browser, expr):
    r = browser._send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    val = r.get('result', {}).get('value', '')
    try: return json.loads(val) if isinstance(val, str) else val
    except: return val

# 启动浏览器
logger.info("启动浏览器...")
browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(20)

# 截图
snap(browser, "state_0_initial")

# 检查页面状态
state = eval_json(browser, """
    (() => {
        return JSON.stringify({
            url: location.href,
            bodyText: (document.body ? document.body.innerText : '').substring(0, 2000),
            iframeCount: document.querySelectorAll('iframe').length,
            iframes: Array.from(document.querySelectorAll('iframe')).map(f => ({
                src: f.src.substring(0, 200),
                visible: f.getBoundingClientRect().width > 0
            })),
        });
    })()
""")
logger.info("页面状态: %s", json.dumps(state, ensure_ascii=False, indent=2))

# 保持浏览器打开
logger.info("浏览器保持打开 60 秒...")
time.sleep(60)
browser.close()
logger.info("完成！")
