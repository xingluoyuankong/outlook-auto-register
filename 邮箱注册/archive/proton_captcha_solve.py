#!/usr/bin/env python3
"""Proton CAPTCHA 处理 - 数字顺序点选"""
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
    logger.info("截图: %s", path)
    return path

def eval_json(browser, expr):
    r = browser._send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    val = r.get('result', {}).get('value', '')
    try: return json.loads(val) if isinstance(val, str) else val
    except: return val

# ===== 启动浏览器，填写表单，提交 =====
logger.info("===== 启动 =====")
browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(15)

# 填写表单
browser.set_input_value("#username", "proton" + str(int(time.time())))
time.sleep(1)
browser.set_input_value("#password", "Pr0ton!@Test123")
time.sleep(1)
browser.set_input_value("#password-confirm", "Pr0ton!@Test123")
time.sleep(3)

# 提交
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
    browser.click_at(submit_pos['x'], submit_pos['y'])
    time.sleep(8)

# 关闭 upsell
for _ in range(5):
    dismissed = eval_json(browser, """
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
    if not dismissed: break
    time.sleep(2)
time.sleep(3)

# 截图当前状态
snap(browser, "captcha_page")

# ===== 获取 CAPTCHA iframe 的坐标 =====
captcha_info = eval_json(browser, """
    (() => {
        const data = {iframes: [], captchaRect: null};
        document.querySelectorAll('iframe').forEach((f, i) => {
            const r = f.getBoundingClientRect();
            if (r.width > 0) {
                const item = {index: i, src: f.src.substring(0, 200), x: r.x, y: r.y, w: r.width, h: r.height};
                data.iframes.push(item);
                if (f.src.includes('core/v4/captcha')) {
                    data.captchaRect = {x: r.x, y: r.y, w: r.width, h: r.height};
                }
            }
        });
        return JSON.stringify(data);
    })()
""")
logger.info("CAPTCHA 信息: %s", json.dumps(captcha_info, ensure_ascii=False, indent=2))

# ===== 使用 CDP Frame Tree 获取 captcha iframe 的内容 =====
frame_tree = browser._send_cmd("Page.getFrameTree", {})
frames = []
def collect_frames(tree):
    fid = tree.get('frame', {}).get('id', '')
    url = tree.get('frame', {}).get('url', '')
    if fid:
        frames.append({'id': fid, 'url': url})
    for child in tree.get('childFrames', []):
        collect_frames(child)
collect_frames(frame_tree.get('frameTree', {}))
logger.info("所有 frame: %s", json.dumps(frames, ensure_ascii=False))

# 找到 core/v4/captcha frame
captcha_frame_id = None
for f in frames:
    if 'core/v4/captcha' in f['url']:
        captcha_frame_id = f['id']
        break

if not captcha_frame_id:
    # 试试 captcha/v1/assets
    for f in frames:
        if 'captcha/v1/assets' in f['url']:
            captcha_frame_id = f['id']
            break

logger.info("CAPTCHA frame ID: %s", captcha_frame_id)

if captcha_frame_id:
    # 使用 Page.createIsolatedWorld 在 iframe 中执行 JS
    try:
        world = browser._send_cmd("Page.createIsolatedWorld", {
            "frameId": captcha_frame_id,
            "grantUniveralAccess": True,
        })
        context_id = world.get('result', {}).get('executionContextId')
        logger.info("Context ID: %s", context_id)
        
        if context_id:
            # 获取 iframe 内部所有元素
            elements = browser._send_cmd("Runtime.evaluate", {
                "expression": """
                    (() => {
                        const els = [];
                        document.querySelectorAll('*').forEach(el => {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {
                                els.push({
                                    tag: el.tagName,
                                    cls: (el.className || '').toString().substring(0, 80),
                                    text: (el.textContent || '').trim().substring(0, 60),
                                    id: el.id || '',
                                    x: r.x, y: r.y, w: r.width, h: r.height,
                                    role: el.getAttribute('role') || '',
                                    dataValue: el.getAttribute('data-value') || '',
                                    inputType: el.type || '',
                                    ariaLabel: el.getAttribute('aria-label') || '',
                                    href: el.href || '',
                                    src: el.src ? el.src.substring(0, 100) : '',
                                });
                            }
                        });
                        return JSON.stringify(els);
                    })()
                """,
                "contextId": context_id,
                "returnByValue": True,
            })
            els_data = json.loads(elements.get('result', {}).get('value', '[]'))
            logger.info("CAPTCHA 元素数量: %d", len(els_data))
            
            with open(os.path.join(OUT, "captcha_elements.json"), "w", encoding="utf-8") as f:
                json.dump(els_data, f, ensure_ascii=False, indent=2)
            
            # 打印所有元素
            for el in els_data:
                logger.info("  %s [%s] text='%s' pos=(%d,%d) size=%dx%d role=%s",
                    el['tag'], el.get('cls', ''), el.get('text', '')[:30],
                    el.get('x', 0), el.get('y', 0), el.get('w', 0), el.get('h', 0),
                    el.get('role', ''))
            
            # 截图 iframe 区域
            iframe_rect = captcha_info.get('captchaRect')
            if iframe_rect:
                r = browser._send_cmd("Page.captureScreenshot", {
                    "format": "png",
                    "clip": {
                        "x": iframe_rect['x'],
                        "y": iframe_rect['y'],
                        "width": iframe_rect['w'],
                        "height": iframe_rect['h'],
                        "scale": 1,
                    }
                })
                with open(os.path.join(OUT, "captcha_iframe_crop.png"), "wb") as f:
                    f.write(base64.b64decode(r['data']))
                logger.info("CAPTCHA iframe 截图已保存")
        else:
            logger.warning("无法创建 isolated world")
    except Exception as e:
        logger.warning("iframe 访问失败: %s", e)
else:
    logger.warning("未找到 CAPTCHA frame")

# 保持浏览器打开
logger.info("浏览器保持打开 60 秒...")
time.sleep(60)
browser.close()
logger.info("完成！")
