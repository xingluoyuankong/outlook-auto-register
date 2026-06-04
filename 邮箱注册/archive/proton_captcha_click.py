#!/usr/bin/env python3
"""Proton CAPTCHA - 直接用 CDP Input 事件点击数字圆圈"""
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

def click_at(browser, x, y):
    """用 CDP Input 事件点击"""
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1
    })
    time.sleep(0.05)
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1
    })
    time.sleep(0.3)

# ===== 启动、填写、提交 =====
logger.info("启动浏览器...")
browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(15)

browser.set_input_value("#username", "proton" + str(int(time.time())))
time.sleep(1)
browser.set_input_value("#password", "Pr0ton!@Test123")
time.sleep(1)
browser.set_input_value("#password-confirm", "Pr0ton!@Test123")
time.sleep(3)

submit_pos = eval_json(browser, """
    (() => {
        const btn = document.querySelector('button[type="submit"]');
        if (btn && !btn.disabled) {
            const r = btn.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
        return null;
    })()
""")
if submit_pos:
    click_at(browser, submit_pos['x'], submit_pos['y'])
    time.sleep(8)

# 关闭 upsell
for _ in range(5):
    d = eval_json(browser, """
        (() => {
            for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                const t = (el.textContent || '').toLowerCase().trim();
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && r.width < 200 && r.height < 60) {
                    if (['no thanks','skip','谢谢','不用','later','decline','continue','关闭','free'].some(k => t.includes(k))) {
                        el.click(); return t;
                    }
                }
            }
            return '';
        })()
    """)
    if not d: break
    time.sleep(2)
time.sleep(3)

# ===== 截图 CAPTCHA 页面 =====
captcha_snap = snap(browser, "captcha_page")
logger.info("CAPTCHA 页面截图: %s", captcha_snap)

# ===== 获取 CAPTCHA iframe 坐标 =====
captcha_rect = eval_json(browser, """
    (() => {
        let rect = null;
        document.querySelectorAll('iframe').forEach(f => {
            const r = f.getBoundingClientRect();
            if (f.src.includes('core/v4/captcha') && r.width > 0) {
                rect = {x: r.x, y: r.y, w: r.width, h: r.height};
            }
        });
        return rect;
    })()
""")
logger.info("CAPTCHA iframe 坐标: %s", json.dumps(captcha_rect))

if not captcha_rect:
    logger.error("未找到 CAPTCHA iframe！")
    time.sleep(30)
    browser.close()
    sys.exit(1)

# ===== 截图 CAPTCHA 区域 =====
r = browser._send_cmd("Page.captureScreenshot", {
    "format": "png",
    "clip": {
        "x": captcha_rect['x'],
        "y": captcha_rect['y'],
        "width": captcha_rect['w'],
        "height": captcha_rect['h'],
        "scale": 1,
    }
})
with open(os.path.join(OUT, "captcha_area.png"), "wb") as f:
    f.write(base64.b64decode(r['data']))
logger.info("CAPTCHA 区域截图已保存")

# ===== 分析 CAPTCHA 结构 =====
# 从截图看，CAPTCHA 显示：
# - 6个编号圆圈（0-5）排成六边形
# - 中心绿色"验证"圆
# - 需要按正确顺序点击数字
#
# CAPTCHA iframe 大小: 672x600
# CAPTCHA 图片大约在 iframe 中心区域
#
# 数字圆圈的近似位置（相对于 iframe 左上角）：
# 0: 顶部中央
# 1: 右上
# 2: 右下
# 3: 底部中央
# 4: 左下
# 5: 左上
#
# 但具体位置需要根据截图精确定位

# 从截图分析，CAPTCHA 图片在 iframe 中的相对位置
# iframe: 672x600
# 图片大约在中心，大小约 300x300

# 计算数字圆圈在页面上的绝对坐标
cx = captcha_rect['x'] + captcha_rect['w'] / 2  # iframe 中心 X
cy = captcha_rect['y'] + captcha_rect['h'] / 2  # iframe 中心 Y

# 数字圆圈的偏移量（相对于中心，基于六边形排列）
# 假设圆圈半径约 120px
import math
r_hex = 120  # 六边形半径

# 数字位置（从顶部开始顺时针）
# 0: 顶部 (270°)
# 1: 右上 (330°)
# 2: 右下 (30°)
# 3: 底部 (90°)
# 4: 左下 (150°)
# 5: 左上 (210°)
number_positions = {}
for i in range(6):
    angle = math.radians(270 + i * 60)  # 从顶部开始顺时针
    nx = cx + r_hex * math.cos(angle)
    ny = cy + r_hex * math.sin(angle)
    number_positions[i] = (nx, ny)
    logger.info("数字 %d 位置: (%.0f, %.0f)", i, nx, ny)

# ===== 尝试点击数字 =====
# 先截图，然后尝试按顺序点击 0,1,2,3,4,5
logger.info("尝试点击数字 0...")
click_at(browser, number_positions[0][0], number_positions[0][1])
time.sleep(1)
snap(browser, "after_click_0")

logger.info("尝试点击数字 1...")
click_at(browser, number_positions[1][0], number_positions[1][1])
time.sleep(1)
snap(browser, "after_click_1")

logger.info("尝试点击数字 2...")
click_at(browser, number_positions[2][0], number_positions[2][1])
time.sleep(1)
snap(browser, "after_click_2")

logger.info("尝试点击数字 3...")
click_at(browser, number_positions[3][0], number_positions[3][1])
time.sleep(1)
snap(browser, "after_click_3")

logger.info("尝试点击数字 4...")
click_at(browser, number_positions[4][0], number_positions[4][1])
time.sleep(1)
snap(browser, "after_click_4")

logger.info("尝试点击数字 5...")
click_at(browser, number_positions[5][0], number_positions[5][1])
time.sleep(3)
snap(browser, "after_click_5")

# 检查结果
time.sleep(5)
snap(browser, "after_captcha")

# 检查页面状态
page_state = eval_json(browser, """
    (() => {
        return JSON.stringify({
            url: location.href,
            bodyText: (document.body ? document.body.innerText : '').substring(0, 1000),
        });
    })()
""")
logger.info("页面状态: %s", json.dumps(page_state, ensure_ascii=False, indent=2)[:500])

# 保持浏览器打开
logger.info("浏览器保持打开 60 秒...")
time.sleep(60)
browser.close()
logger.info("完成！")
