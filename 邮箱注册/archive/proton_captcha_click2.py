#!/usr/bin/env python3
"""Proton CAPTCHA - 精确定位并点击数字圆圈"""
import sys, os, time, json, math
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
    time.sleep(0.5)

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
snap(browser, "step1_captcha_page")

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
logger.info("CAPTCHA iframe: %s", json.dumps(captcha_rect))

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
with open(os.path.join(OUT, "step1_captcha_area.png"), "wb") as f:
    f.write(base64.b64decode(r['data']))

# ===== 计算数字圆圈在页面上的坐标 =====
# 从截图分析，CAPTCHA 图片在 iframe 中居中
# iframe 大小: ~682x150
# CAPTCHA 图片大约 150x150，在 iframe 中居中

ix = captcha_rect['x']
iy = captcha_rect['y']
iw = captcha_rect['w']
ih = captcha_rect['h']

# CAPTCHA 图片中心在 iframe 中心
captcha_cx = ix + iw / 2
captcha_cy = iy + ih / 2

# 六边形半径（从截图估算，数字圆圈距中心约 50px）
hex_r = 50

# 数字位置（从顶部开始顺时针）
# 0: 顶部 (270°)
# 1: 右上 (330°)
# 2: 右下 (30°)
# 3: 底部 (90°)
# 4: 左下 (150°)
# 5: 左上 (210°)
number_positions = {}
for i in range(6):
    angle = math.radians(270 + i * 60)
    nx = captcha_cx + hex_r * math.cos(angle)
    ny = captcha_cy + hex_r * math.sin(angle)
    number_positions[i] = (nx, ny)
    logger.info("数字 %d: (%.0f, %.0f)", i, nx, ny)

# ===== 先点击 iframe 区域获取焦点 =====
logger.info("点击 iframe 区域获取焦点...")
click_at(browser, captcha_cx, captcha_cy)
time.sleep(1)

# ===== 截图看看 =====
snap(browser, "step2_after_focus")

# ===== 尝试不同的点击顺序 =====
# 从截图看，CAPTCHA 显示 6 个编号圆圈（0-5）排成六边形
# 可能需要按特定顺序点击

# 尝试 1: 按顺序 0,1,2,3,4,5
logger.info("尝试顺序 0,1,2,3,4,5...")
for i in range(6):
    x, y = number_positions[i]
    logger.info("点击数字 %d at (%.0f, %.0f)", i, x, y)
    click_at(browser, x, y)
    time.sleep(0.5)

time.sleep(3)
snap(browser, "step3_after_seq_012345")

# 检查是否通过
state1 = eval_json(browser, """
    (() => {
        return JSON.stringify({
            url: location.href,
            bodyText: (document.body ? document.body.innerText : '').substring(0, 500),
        });
    })()
""")
logger.info("状态: %s", state1.get('bodyText', '')[:200])

# 如果还在验证码页面，尝试其他顺序
if 'Human Verification' in str(state1.get('bodyText', '')) or '人机验证' in str(state1.get('bodyText', '')):
    logger.info("还在验证页面，尝试其他顺序...")
    
    # 尝试 2: 逆序 5,4,3,2,1,0
    logger.info("尝试逆序 5,4,3,2,1,0...")
    for i in [5,4,3,2,1,0]:
        x, y = number_positions[i]
        click_at(browser, x, y)
        time.sleep(0.5)
    time.sleep(3)
    snap(browser, "step4_after_seq_543210")
    
    state2 = eval_json(browser, """
        (() => {
            return JSON.stringify({
                url: location.href,
                bodyText: (document.body ? document.body.innerText : '').substring(0, 500),
            });
        })()
    """)
    logger.info("状态: %s", state2.get('bodyText', '')[:200])
    
    # 尝试 3: 点击中心"验证"按钮
    if 'Human Verification' in str(state2.get('bodyText', '')) or '人机验证' in str(state2.get('bodyText', '')):
        logger.info("尝试点击中心验证按钮...")
        click_at(browser, captcha_cx, captcha_cy)
        time.sleep(3)
        snap(browser, "step5_after_center_click")
        
        # 尝试 4: 从截图分析，数字可能需要按特定顺序
        # 从截图看，数字 0 在顶部，然后顺时针
        # 可能需要按 0,1,2,3,4,5 的顺序，但需要先点击中心
        logger.info("再次尝试顺序 0,1,2,3,4,5（先点中心）...")
        click_at(browser, captcha_cx, captcha_cy)
        time.sleep(0.5)
        for i in range(6):
            x, y = number_positions[i]
            click_at(browser, x, y)
            time.sleep(0.3)
        time.sleep(3)
        snap(browser, "step6_after_center_then_seq")

# 最终状态
time.sleep(5)
snap(browser, "step7_final")
final_state = eval_json(browser, """
    (() => {
        return JSON.stringify({
            url: location.href,
            bodyText: (document.body ? document.body.innerText : '').substring(0, 1000),
        });
    })()
""")
logger.info("最终状态: %s", json.dumps(final_state, ensure_ascii=False, indent=2)[:500])

# 保持浏览器打开
logger.info("浏览器保持打开 60 秒...")
time.sleep(60)
browser.close()
logger.info("完成！")
