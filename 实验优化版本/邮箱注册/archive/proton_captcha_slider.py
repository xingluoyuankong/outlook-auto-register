#!/usr/bin/env python3
"""Proton CAPTCHA - 滑块验证（向右拖动到缺口位置）"""
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

def drag_to(browser, from_x, from_y, to_x, to_y, steps=30, duration_ms=800):
    """平滑拖拽"""
    step_time = duration_ms / steps / 1000.0
    
    # 按下
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": from_x, "y": from_y, "button": "left", "clickCount": 1
    })
    time.sleep(0.15)
    
    # 移动（分步模拟平滑拖拽）
    for i in range(1, steps + 1):
        t = i / steps
        # 使用缓动函数，开始慢，中间快，结束慢
        ease = t * t * (3 - 2 * t)  # smoothstep
        mx = from_x + (to_x - from_x) * ease
        my = from_y + (to_y - from_y) * ease
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
snap(browser, "slider_0_captcha_page")

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

# ===== 分析 CAPTCHA 结构 =====
# 从截图看，CAPTCHA 是一个滑块验证：
# - 上方：图片区域（有缺口）
# - 下方：滑块条（从左到右）
# - 滑块在最左边，需要拖到右边的缺口位置
#
# CAPTCHA iframe 大小: 672x600
# 图片区域大约在上半部分
# 滑块条在下半部分

# 滑块位置（从截图估算）
# 滑块在 iframe 底部，大约 y = iy + ih - 50
slider_y = iy + ih - 80  # 滑块的 Y 坐标
slider_start_x = ix + 80  # 滑块起始 X（左边）
slider_end_x = ix + iw - 80  # 滑块结束 X（右边）

logger.info("滑块区域: Y=%.0f, X: %.0f → %.0f", slider_y, slider_start_x, slider_end_x)

# ===== 截图 CAPTCHA 区域 =====
r = browser._send_cmd("Page.captureScreenshot", {
    "format": "png",
    "clip": {
        "x": ix, "y": iy, "width": iw, "height": ih, "scale": 1,
    }
})
with open(os.path.join(OUT, "slider_1_captcha_area.png"), "wb") as f:
    f.write(base64.b64decode(r['data']))

# ===== 尝试拖拽滑块 =====
# 方案 1: 拖拽到不同位置（从左到右，尝试不同距离）
distances = [0.3, 0.5, 0.7, 0.9]  # 尝试拖拽到滑块条的不同比例位置

for attempt, ratio in enumerate(distances):
    target_x = slider_start_x + (slider_end_x - slider_start_x) * ratio
    logger.info("尝试 %d: 拖拽滑块到 %.0f%% 位置 (%.0f)", attempt+1, ratio*100, target_x)
    
    drag_to(browser, slider_start_x, slider_y, target_x, slider_y, steps=25, duration_ms=600)
    time.sleep(2)
    snap(browser, f"slider_2_attempt_{attempt+1}")
    
    # 检查是否通过
    state = eval_json(browser, """
        (() => {
            return JSON.stringify({
                url: location.href,
                bodyText: (document.body ? document.body.innerText : '').substring(0, 500),
            });
        })()
    """)
    body = str(state.get('bodyText', ''))
    logger.info("状态: %s", body[:150])
    
    # 如果不再显示 Human Verification，说明通过了
    if 'Human Verification' not in body and '人机验证' not in body:
        logger.info("🎉 CAPTCHA 通过！")
        break
    
    # 如果还在验证页面，刷新 CAPTCHA 重试
    if attempt < len(distances) - 1:
        logger.info("还在验证页面，刷新 CAPTCHA...")
        # 点击刷新按钮（如果有的话）
        # 或者重新加载页面
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(15)
        # 重新填写表单
        browser.set_input_value("#username", "proton" + str(int(time.time())))
        time.sleep(1)
        browser.set_input_value("#password", "Pr0ton!@Test123")
        time.sleep(1)
        browser.set_input_value("#password-confirm", "Pr0ton!@Test123")
        time.sleep(3)
        # 重新提交
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
        
        # 重新获取 CAPTCHA 坐标
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
        if captcha_rect:
            ix = captcha_rect['x']
            iy = captcha_rect['y']
            iw = captcha_rect['w']
            ih = captcha_rect['h']
            slider_y = iy + ih - 80
            slider_start_x = ix + 80
            slider_end_x = ix + iw - 80

# 最终状态
time.sleep(5)
snap(browser, "slider_final")
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
