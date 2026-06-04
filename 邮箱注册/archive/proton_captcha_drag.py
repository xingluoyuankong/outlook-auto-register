#!/usr/bin/env python3
"""Proton CAPTCHA - 拖拽数字图案到对应位置"""
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
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1
    })
    time.sleep(0.05)
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1
    })
    time.sleep(0.3)

def drag_to(browser, from_x, from_y, to_x, to_y, steps=20, duration_ms=500):
    """拖拽：从 (from_x, from_y) 拖到 (to_x, to_y)"""
    step_time = duration_ms / steps / 1000.0
    
    # 按下
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": from_x, "y": from_y, "button": "left", "clickCount": 1
    })
    time.sleep(0.1)
    
    # 移动（分步模拟平滑拖拽）
    for i in range(1, steps + 1):
        t = i / steps
        mx = from_x + (to_x - from_x) * t
        my = from_y + (to_y - from_y) * t
        browser._send_cmd("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": mx, "y": my, "button": "left"
        })
        time.sleep(step_time)
    
    # 释放
    time.sleep(0.1)
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": to_x, "y": to_y, "button": "left", "clickCount": 1
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
snap(browser, "drag_0_captcha_page")

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

ix = captcha_rect['x']
iy = captcha_rect['y']
iw = captcha_rect['w']
ih = captcha_rect['h']

# CAPTCHA 图片中心
captcha_cx = ix + iw / 2
captcha_cy = iy + ih / 2

# ===== 分析 CAPTCHA 结构 =====
# 从截图看，CAPTCHA 显示：
# - 中心：绿色"验证"圆
# - 周围：6个编号圆圈（0-5）排成六边形
# - 需要拖拽数字到对应位置
#
# 假设：
# - 数字圆圈在外圈（半径 ~100px）
# - 目标位置在内圈（半径 ~50px）
# - 需要将每个数字拖到对应的目标位置

# 外圈半径（数字当前位置）
outer_r = 100
# 内圈半径（目标位置）
inner_r = 50

# 数字当前位置（外圈，从顶部开始顺时针）
outer_positions = {}
for i in range(6):
    angle = math.radians(270 + i * 60)
    x = captcha_cx + outer_r * math.cos(angle)
    y = captcha_cy + outer_r * math.sin(angle)
    outer_positions[i] = (x, y)

# 目标位置（内圈，可能也是顺时针）
inner_positions = {}
for i in range(6):
    angle = math.radians(270 + i * 60)
    x = captcha_cx + inner_r * math.cos(angle)
    y = captcha_cy + inner_r * math.sin(angle)
    inner_positions[i] = (x, y)

logger.info("CAPTCHA 中心: (%.0f, %.0f)", captcha_cx, captcha_cy)
logger.info("外圈位置（数字当前位置）:")
for i, (x, y) in outer_positions.items():
    logger.info("  %d: (%.0f, %.0f)", i, x, y)
logger.info("内圈位置（目标位置）:")
for i, (x, y) in inner_positions.items():
    logger.info("  %d: (%.0f, %.0f)", i, x, y)

# ===== 尝试拖拽 =====
# 方案 1: 将每个数字拖到内圈对应位置
logger.info("方案 1: 拖拽数字 0-5 到内圈对应位置...")
for i in range(6):
    from_x, from_y = outer_positions[i]
    to_x, to_y = inner_positions[i]
    logger.info("拖拽 %d: (%.0f,%.0f) → (%.0f,%.0f)", i, from_x, from_y, to_x, to_y)
    drag_to(browser, from_x, from_y, to_x, to_y, steps=15, duration_ms=300)
    time.sleep(0.5)

time.sleep(3)
snap(browser, "drag_1_after_drag")

# 检查状态
state = eval_json(browser, """
    (() => {
        return JSON.stringify({
            url: location.href,
            bodyText: (document.body ? document.body.innerText : '').substring(0, 500),
        });
    })()
""")
logger.info("状态: %s", state.get('bodyText', '')[:200])

# 如果还在验证页面，尝试其他方案
if 'Human Verification' in str(state.get('bodyText', '')) or '人机验证' in str(state.get('bodyText', '')):
    logger.info("还在验证页面，尝试其他方案...")
    
    # 方案 2: 将数字拖到中心"验证"按钮
    logger.info("方案 2: 拖拽数字到中心验证按钮...")
    for i in range(6):
        from_x, from_y = outer_positions[i]
        logger.info("拖拽 %d → 中心 (%.0f,%.0f)", i, captcha_cx, captcha_cy)
        drag_to(browser, from_x, from_y, captcha_cx, captcha_cy, steps=15, duration_ms=300)
        time.sleep(0.5)
    
    time.sleep(3)
    snap(browser, "drag_2_after_center")
    
    # 方案 3: 尝试将数字拖到外圈的下一个位置（旋转）
    logger.info("方案 3: 拖拽数字到外圈下一个位置（旋转）...")
    for i in range(6):
        from_x, from_y = outer_positions[i]
        to_x, to_y = outer_positions[(i + 1) % 6]
        logger.info("拖拽 %d → %d: (%.0f,%.0f) → (%.0f,%.0f)", i, (i+1)%6, from_x, from_y, to_x, to_y)
        drag_to(browser, from_x, from_y, to_x, to_y, steps=15, duration_ms=300)
        time.sleep(0.5)
    
    time.sleep(3)
    snap(browser, "drag_3_after_rotate")
    
    # 方案 4: 尝试点击中心"验证"按钮
    logger.info("方案 4: 点击中心验证按钮...")
    click_at(browser, captcha_cx, captcha_cy)
    time.sleep(3)
    snap(browser, "drag_4_after_click")

# 最终状态
time.sleep(5)
snap(browser, "drag_5_final")
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
