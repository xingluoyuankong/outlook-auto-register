#!/usr/bin/env python3
"""Proton 完整注册流程 - 含滑块 CAPTCHA 处理"""
import sys, os, time, json, math, random
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
    logger.info("截图: %s", name)
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

def human_like_drag(browser, from_x, from_y, to_x, to_y, duration_ms=1200):
    """模拟人类拖拽：变速、微微抖动"""
    steps = random.randint(25, 40)
    step_time = duration_ms / steps / 1000.0
    
    # 按下
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": from_x, "y": from_y, "button": "left", "clickCount": 1
    })
    time.sleep(random.uniform(0.1, 0.2))
    
    # 移动
    for i in range(1, steps + 1):
        t = i / steps
        # ease-out: 快起慢停
        ease = 1 - (1 - t) ** 2
        mx = from_x + (to_x - from_x) * ease + random.uniform(-1.5, 1.5)
        my = from_y + (to_y - from_y) * ease + random.uniform(-1, 1)
        browser._send_cmd("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": round(mx), "y": round(my), "button": "left"
        })
        time.sleep(step_time)
    
    # 释放
    time.sleep(random.uniform(0.05, 0.15))
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": to_x, "y": to_y, "button": "left", "clickCount": 1
    })
    time.sleep(0.5)

def close_upsell(browser):
    """关闭 upsell 页面"""
    for _ in range(5):
        d = eval_json(browser, """
            (() => {
                for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                    const t = (el.textContent || '').toLowerCase().trim();
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.width < 200 && r.height < 60) {
                        if (['no thanks','skip','谢谢','不用','later','decline','continue','关闭','free','no, thanks'].some(k => t.includes(k))) {
                            el.click(); return t;
                        }
                    }
                }
                return '';
            })()
        """)
        if not d:
            break
        time.sleep(2)

def wait_for_captcha(browser, max_wait=30):
    """等待 CAPTCHA 出现"""
    for i in range(max_wait):
        captcha = eval_json(browser, """
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
        if captcha:
            return captcha
        time.sleep(1)
    return None

def get_slider_handle(browser, captcha_rect):
    """获取滑块手柄位置"""
    # 滑块在 CAPTCHA 底部
    # 从截图看，滑块条在底部，手柄在最左边
    ix = captcha_rect['x']
    iy = captcha_rect['y']
    iw = captcha_rect['w']
    ih = captcha_rect['h']
    
    # 滑块条大约在底部 80px 的位置
    slider_y = iy + ih - 80
    # 滑块手柄起始位置（左边）
    slider_start_x = ix + 50
    
    return slider_start_x, slider_y

def solve_slider_captcha(browser, captcha_rect):
    """解决滑块 CAPTCHA"""
    ix = captcha_rect['x']
    iy = captcha_rect['y']
    iw = captcha_rect['w']
    ih = captcha_rect['h']
    
    # 获取滑块位置
    slider_start_x, slider_y = get_slider_handle(browser, captcha_rect)
    
    # 尝试不同的拖拽距离
    # 滑块条总宽度约 iw - 100
    # 需要拖拽到缺口位置，大约在 30%-80% 的位置
    ratios = [0.35, 0.45, 0.55, 0.65, 0.75, 0.85]
    
    for attempt, ratio in enumerate(ratios):
        target_x = slider_start_x + (iw - 100) * ratio
        logger.info("尝试 %d/%d: 拖拽滑块到 %.0f%% 位置", attempt+1, len(ratios), ratio*100)
        
        # 先截图
        snap(browser, f"slider_before_{attempt}")
        
        # 拖拽
        human_like_drag(browser, slider_start_x, slider_y, target_x, slider_y)
        time.sleep(2)
        
        # 截图
        snap(browser, f"slider_after_{attempt}")
        
        # 检查是否通过
        page_state = eval_json(browser, """
            (() => {
                return JSON.stringify({
                    url: location.href,
                    bodyText: (document.body ? document.body.innerText : '').substring(0, 500),
                });
            })()
        """)
        body = str(page_state.get('bodyText', ''))
        
        if 'Human Verification' not in body and '人机验证' not in body:
            logger.info("🎉 CAPTCHA 通过！")
            return True
        
        # 检查是否需要刷新 CAPTCHA
        logger.info("还在验证页面，检查 CAPTCHA 状态...")
        time.sleep(1)
    
    return False

# ===== 主流程 =====
logger.info("===== 启动 Proton 注册 =====")
browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(15)
snap(browser, "01_signup_page")

# 填写表单
username = "proton" + str(int(time.time()))
logger.info("用户名: %s", username)
browser.set_input_value("#username", username)
time.sleep(1)
browser.set_input_value("#password", "Pr0ton!@Test123")
time.sleep(1)
browser.set_input_value("#password-confirm", "Pr0ton!@Test123")
time.sleep(3)
snap(browser, "02_form_filled")

# 提交表单
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
    logger.info("提交表单...")
    click_at(browser, submit_pos['x'], submit_pos['y'])
    time.sleep(8)
    snap(browser, "03_after_submit")
else:
    logger.error("未找到提交按钮！")
    time.sleep(30)
    browser.close()
    sys.exit(1)

# 关闭 upsell
logger.info("关闭 upsell...")
close_upsell(browser)
time.sleep(3)
snap(browser, "04_after_upsell")

# 等待 CAPTCHA
logger.info("等待 CAPTCHA...")
captcha_rect = wait_for_captcha(browser, max_wait=30)

if not captcha_rect:
    logger.error("CAPTCHA 未出现！")
    snap(browser, "04_no_captcha")
    time.sleep(30)
    browser.close()
    sys.exit(1)

logger.info("CAPTCHA 坐标: %s", json.dumps(captcha_rect))
snap(browser, "05_captcha_found")

# 截图 CAPTCHA 区域
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
with open(os.path.join(OUT, "06_captcha_area.png"), "wb") as f:
    f.write(base64.b64decode(r['data']))

# 解决滑块 CAPTCHA
logger.info("尝试解决滑块 CAPTCHA...")
if solve_slider_captcha(browser, captcha_rect):
    logger.info("🎉 注册成功！")
else:
    logger.warning("CAPTCHA 未通过，继续尝试...")

# 检查最终状态
time.sleep(5)
snap(browser, "07_final")
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
