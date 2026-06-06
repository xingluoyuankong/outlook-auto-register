#!/usr/bin/env python3
"""
Proton 完整注册流程 - 智能滑块 CAPTCHA 解决方案

核心改进：
1. 通过图像分析找到拼图缺口位置（不再猜测比例）
2. 使用 touch 事件模拟人类拖拽
3. 多种拖拽策略备选
"""
import sys, os, time, json, math, random, base64, logging
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proton_steps")
os.makedirs(OUT, exist_ok=True)


def snap(browser, name, retries=3):
    for i in range(retries):
        try:
            r = browser._send_cmd("Page.captureScreenshot", {"format": "png"})
            path = os.path.join(OUT, f"{name}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(r['data']))
            logger.info("截图: %s", name)
            return path
        except Exception as e:
            logger.warning("截图失败 (尝试 %d/%d): %s", i+1, retries, e)
            time.sleep(1)
    return ""


def eval_json(browser, expr, default=None):
    try:
        r = browser._send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        val = r.get('result', {}).get('value', '')
        try:
            return json.loads(val) if isinstance(val, str) else val
        except:
            return val
    except Exception as e:
        logger.warning("eval_json 失败: %s", e)
        return default


def is_browser_alive(browser):
    """检查浏览器是否还活着"""
    try:
        result = browser._send_cmd("Runtime.evaluate", {
            "expression": "1+1",
            "returnByValue": True
        }, timeout=3)
        return result.get('result', {}).get('value') == 2
    except:
        return False


def safe_eval(browser, expr, default=None):
    """安全执行 JS，如果浏览器挂了返回默认值"""
    if not is_browser_alive(browser):
        logger.error("浏览器已断开连接")
        return default
    return eval_json(browser, expr, default)


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

    # 移动 - ease-out: 快起慢停
    for i in range(1, steps + 1):
        t = i / steps
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


def touch_drag(browser, from_x, from_y, to_x, to_y, duration_ms=1200):
    """用触摸事件拖拽 - 可能更适合某些CAPTCHA"""
    steps = random.randint(20, 35)
    step_time = duration_ms / steps / 1000.0

    # Touch start
    browser._send_cmd("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": from_x, "y": from_y}]
    })
    time.sleep(random.uniform(0.05, 0.15))

    # Move with easing
    for i in range(1, steps + 1):
        t = i / steps
        ease = 1 - (1 - t) ** 3  # cubic ease-out
        mx = from_x + (to_x - from_x) * ease + random.uniform(-1, 1)
        my = from_y + (to_y - from_y) * ease + random.uniform(-0.5, 0.5)
        browser._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": mx, "y": my}]
        })
        time.sleep(step_time + random.uniform(-0.003, 0.008))

    # Touch end
    time.sleep(random.uniform(0.03, 0.1))
    browser._send_cmd("Input.dispatchTouchEvent", {
        "type": "touchEnd",
        "touchPoints": []
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
                        rect = {x: r.x, y: r.y, w: r.width, h: r.height, src: f.src};
                    }
                });
                return rect;
            })()
        """)
        if captcha and isinstance(captcha, dict) and captcha.get('w', 0) > 0:
            return captcha
        time.sleep(1)
    return None


def find_gap_by_pixel_diff(browser, captcha_rect):
    """
    通过像素差异分析找到拼图缺口位置。
    
    原理：拼图缺口区域的颜色/亮度与周围有明显差异。
    我们扫描图片的中间区域，找到亮度突变的位置。
    """
    # 截取 CAPTCHA 区域
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
    img_data = base64.b64decode(r['data'])
    
    # 保存截图
    img_path = os.path.join(OUT, "captcha_area_fresh.png")
    with open(img_path, "wb") as f:
        f.write(img_data)
    
    # 尝试用 PIL/Pillow 分析
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_data))
        pixels = img.load()
        w, h = img.size
        
        logger.info("CAPTCHA 图片尺寸: %dx%d", w, h)
        
        # 图片区域大约在上半部分 (y: 0 到 h*0.7)
        # 滑块区域在下半部分
        img_area_h = int(h * 0.7)
        
        # 扫描中间水平行，找亮度突变
        # 拼图缺口通常在图片中间区域
        best_x = -1
        best_diff = 0
        
        # 扫描多行取平均
        rows_to_scan = range(img_area_h // 4, img_area_h * 3 // 4, 5)
        
        for y in rows_to_scan:
            prev_brightness = 0
            for x in range(1, w - 1):
                r_val, g_val, b_val = pixels[x, y][:3]
                brightness = (r_val + g_val + b_val) / 3
                
                if x > 1:
                    diff = abs(brightness - prev_brightness)
                    # 缺口边缘会有明显亮度变化
                    if diff > best_diff and diff > 30:  # 阈值
                        best_diff = diff
                        best_x = x
                
                prev_brightness = brightness
        
        if best_x > 0:
            logger.info("像素分析找到缺口位置: x=%d (亮度差异=%d)", best_x, best_diff)
            return best_x, w
        
        logger.warning("像素分析未找到明显缺口，尝试边缘检测...")
    except ImportError:
        logger.warning("PIL 不可用，尝试 OpenCV...")
    except Exception as e:
        logger.warning("PIL 分析失败: %s", e)
    
    # 尝试用 OpenCV
    try:
        import cv2
        import numpy as np
        
        img_array = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 使用 Canny 边缘检测
        edges = cv2.Canny(gray, 50, 150)
        
        # 找垂直边缘（缺口的左右边界）
        h, w = edges.shape
        img_area_h = int(h * 0.7)
        
        # 统计每列的边缘像素数
        col_sums = np.sum(edges[:img_area_h, :], axis=0)
        
        # 找峰值（垂直边缘集中的位置）
        threshold = np.mean(col_sums) + 2 * np.std(col_sums)
        peaks = np.where(col_sums > threshold)[0]
        
        if len(peaks) > 0:
            # 取峰值区域的中心作为缺口位置
            gap_x = int(np.mean(peaks))
            logger.info("OpenCV 边缘检测找到缺口位置: x=%d (peaks=%d)", gap_x, len(peaks))
            return gap_x, w
        
        logger.warning("OpenCV 边缘检测未找到缺口")
    except ImportError:
        logger.warning("OpenCV 不可用")
    except Exception as e:
        logger.warning("OpenCV 分析失败: %s", e)
    
    return None, None


def find_gap_by_color_patch(browser, captcha_rect):
    """
    通过颜色块检测找缺口位置。
    
    缺口区域通常有明显的颜色块或半透明遮罩。
    """
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
    img_data = base64.b64decode(r['data'])
    
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_data))
        pixels = img.load()
        w, h = img.size
        
        # 图片区域
        img_area_h = int(h * 0.7)
        
        # 找异常亮或异常暗的区域（缺口通常有特殊颜色）
        # 计算整体平均亮度
        total_brightness = 0
        count = 0
        for y in range(img_area_h // 4, img_area_h * 3 // 4):
            for x in range(w // 4, w * 3 // 4):
                r_val, g_val, b_val = pixels[x, y][:3]
                total_brightness += (r_val + g_val + b_val) / 3
                count += 1
        avg_brightness = total_brightness / count
        
        # 找与平均亮度差异大的连续区域
        threshold = 40
        candidate_x = []
        
        for x in range(w // 4, w * 3 // 4):
            diff_sum = 0
            for y in range(img_area_h // 4, img_area_h * 3 // 4, 3):
                r_val, g_val, b_val = pixels[x, y][:3]
                brightness = (r_val + g_val + b_val) / 3
                diff_sum += abs(brightness - avg_brightness)
            
            if diff_sum > threshold * (img_area_h // 2):
                candidate_x.append(x)
        
        if candidate_x:
            # 取连续区域的中心
            gap_x = sum(candidate_x) // len(candidate_x)
            logger.info("颜色块检测找到缺口位置: x=%d", gap_x)
            return gap_x, w
        
    except Exception as e:
        logger.warning("颜色块检测失败: %s", e)
    
    return None, None


def calculate_drag_distance(gap_x, img_width, slider_start_x, slider_width):
    """
    计算拖拽距离。
    
    gap_x: 缺口在图片中的x坐标
    img_width: 图片宽度
    slider_start_x: 滑块起始x坐标
    slider_width: 滑块条宽度
    
    返回: 拖拽目标x坐标
    """
    # 缺口位置占图片宽度的比例
    ratio = gap_x / img_width
    
    # 滑块需要拖拽的距离 = 比例 * 滑动条可拖动宽度
    # 滑块手柄大约宽40px，可拖动范围 = 滑动条宽度 - 手柄宽度
    draggable_width = slider_width - 40
    
    target_x = slider_start_x + ratio * draggable_width
    
    return target_x


# ===== 主流程 =====
logger.info("===== 启动 Proton 智能注册 =====")

# 使用持久化 user data dir 防止 Chrome 崩溃
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile_proton")
os.makedirs(USER_DATA_DIR, exist_ok=True)

def safe_launch():
    """安全启动浏览器，带重试"""
    for browser_type in ["chrome", "edge"]:
        try:
            from cdp_browser import CDPBrowser, CDPLaunchConfig
            config = CDPLaunchConfig(
                browser_type=browser_type,
                headless=False,
                window_size=(1366, 768),
                user_data_dir=USER_DATA_DIR,
            )
            b = CDPBrowser(config)
            b.launch()
            logger.info("使用 %s 启动成功", browser_type)
            return b
        except Exception as e:
            logger.warning("%s 启动失败: %s", browser_type, e)
    raise RuntimeError("无法启动任何浏览器")

browser = safe_launch()

# 分步导航，防止页面加载过快导致 WebSocket 断开
logger.info("导航到 Proton 注册页...")
try:
    browser.navigate("https://account.proton.me/signup?plan=free", timeout=60)
except Exception as e:
    logger.warning("导航命令失败（可能页面已加载）: %s", e)

time.sleep(3)

# 等待页面完全加载
if is_browser_alive(browser):
    for i in range(30):
        try:
            state = browser.evaluate("document.readyState")
            url = browser.get_url()
            logger.info("页面状态: %s, URL: %s", state, url[:80])
            if state in ('complete', 'interactive') and 'proton' in url.lower():
                break
        except:
            logger.warning("查询页面状态失败，等待...")
        time.sleep(2)
    
    time.sleep(10)  # 额外等待 JS 渲染
    snap(browser, "01_signup_page")
else:
    logger.error("浏览器在导航后断开！")
    # 不要立即退出，Chrome 可能还在
    time.sleep(5)

# 填写表单
username = "proton" + str(int(time.time()))
logger.info("用户名: %s", username)

# 等待表单出现 - 自动发现选择器
logger.info("等待表单加载...")
form_selectors = {}
for i in range(20):
    # 发现表单元素
    discovered = eval_json(browser, """
        (() => {
            const inputs = document.querySelectorAll('input');
            const result = {};
            inputs.forEach(inp => {
                const id = inp.id;
                const name = inp.name;
                const type = inp.type;
                const placeholder = inp.placeholder || '';
                const label = inp.closest('label') ? inp.closest('label').textContent.trim() : '';
                if (id && (type === 'text' || type === 'email' || type === '')) {
                    result[id] = {type, placeholder, label, name};
                }
                if (id && type === 'password') {
                    result[id] = {type, placeholder, label, name};
                }
            });
            return result;
        })
    """)
    if discovered and isinstance(discovered, dict) and len(discovered) > 0:
        form_selectors = discovered
        logger.info("发现表单元素: %s", json.dumps(form_selectors, ensure_ascii=False))
        break
    logger.info("等待表单... (%d/20)", i+1)
    time.sleep(2)

# 根据发现的元素选择正确的选择器
username_sel = None
password_sel = None
confirm_sel = None

for sel_id, info in form_selectors.items():
    itype = info.get('type', '')
    placeholder = info.get('placeholder', '').lower()
    label = info.get('label', '').lower()
    
    if itype == 'password':
        if 'confirm' in label or 'confirm' in placeholder or not password_sel:
            if 'confirm' in label or 'confirm' in placeholder:
                confirm_sel = f"#{sel_id}"
            else:
                password_sel = f"#{sel_id}"
    elif itype in ('text', 'email', ''):
        username_sel = f"#{sel_id}"

# 兜底
if not username_sel:
    username_sel = "#email"
if not password_sel:
    password_sel = "#password"
if not confirm_sel:
    confirm_sel = "#password-confirm"

logger.info("使用选择器: username=%s, password=%s, confirm=%s", username_sel, password_sel, confirm_sel)

browser.set_input_value(username_sel, username + "@proton.me")
time.sleep(1)
browser.set_input_value(password_sel, "Pr0ton!@Test123")
time.sleep(1)
browser.set_input_value(confirm_sel, "Pr0ton!@Test123")
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

# 截取 CAPTCHA 区域
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

# ===== 分析缺口位置 =====
logger.info("===== 分析缺口位置 =====")

# 方法1: 像素差异分析
gap_x, img_w = find_gap_by_pixel_diff(browser, captcha_rect)

# 方法2: 颜色块检测（如果方法1失败）
if gap_x is None:
    gap_x, img_w = find_gap_by_color_patch(browser, captcha_rect)

# 计算拖拽参数
ix = captcha_rect['x']
iy = captcha_rect['y']
iw = captcha_rect['w']
ih = captcha_rect['h']

# 滑块在底部，手柄在左边
slider_y = iy + ih - 80
slider_start_x = ix + 50
slider_width = iw - 100

if gap_x is not None:
    # 使用分析结果
    target_x = calculate_drag_distance(gap_x, img_w, slider_start_x, slider_width)
    logger.info("智能分析结果: 缺口x=%d, 图片宽=%d, 目标x=%.0f", gap_x, img_w, target_x)
else:
    # 如果分析失败，使用多种比例尝试
    logger.warning("图像分析失败，使用多比例尝试策略")
    ratios = [0.3, 0.4, 0.5, 0.6, 0.7]
    ratio = ratios[0]  # 先试30%
    target_x = slider_start_x + slider_width * ratio

# ===== 尝试拖拽 =====
logger.info("===== 开始拖拽 =====")

# 策略1: 鼠标拖拽
logger.info("策略1: 鼠标拖拽到 x=%.0f", target_x)
snap(browser, "before_mouse_drag")
human_like_drag(browser, slider_start_x, slider_y, target_x, slider_y, duration_ms=1500)
time.sleep(2)
snap(browser, "after_mouse_drag")

# 检查结果
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
    logger.info("🎉 策略1成功！CAPTCHA 通过！")
else:
    # 策略2: 触摸拖拽
    logger.info("策略2: 触摸拖拽")
    # 需要刷新 CAPTCHA 或者重试
    # 先检查滑块是否还在原位
    snap(browser, "before_touch_drag")
    touch_drag(browser, slider_start_x, slider_y, target_x, slider_y, duration_ms=1500)
    time.sleep(2)
    snap(browser, "after_touch_drag")
    
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
        logger.info("🎉 策略2成功！CAPTCHA 通过！")
    else:
        # 策略3: 如果分析失败，尝试不同比例
        if gap_x is None:
            logger.info("策略3: 尝试不同比例")
            for ratio in [0.4, 0.5, 0.6, 0.7]:
                target_x = slider_start_x + slider_width * ratio
                logger.info("尝试比例 %.0f%%", ratio * 100)
                human_like_drag(browser, slider_start_x, slider_y, target_x, slider_y)
                time.sleep(2)
                
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
                    logger.info("🎉 策略3成功！CAPTCHA 通过！")
                    break
                
                snap(browser, f"after_ratio_{int(ratio*100)}")

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
