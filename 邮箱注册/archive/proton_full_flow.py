#!/usr/bin/env python3
"""Proton 完整注册流程 - 分步推进，每步失败截图"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser
import logging, base64
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUT = os.path.join(os.path.dirname(__file__), "proton_steps")
os.makedirs(OUT, exist_ok=True)

def snap(browser, name):
    """截图并保存"""
    r = browser._send_cmd("Page.captureScreenshot", {"format": "png"})
    path = os.path.join(OUT, f"{name}.png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(r['data']))
    logger.info("截图: %s", path)
    return path

def eval_str(browser, expr):
    """执行JS并返回字符串结果"""
    r = browser._send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get('result', {}).get('value', '')

def eval_json(browser, expr):
    """执行JS并返回JSON"""
    val = eval_str(browser, expr)
    try:
        return json.loads(val) if isinstance(val, str) else val
    except:
        return val

# ===== STEP 1: 打开注册页 =====
logger.info("===== STEP 1: 打开注册页 =====")
browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(15)
snap(browser, "01_signup_page")

# ===== STEP 2: 填写表单 =====
logger.info("===== STEP 2: 填写表单 =====")
browser.set_input_value("#username", "proton" + str(int(time.time())))
time.sleep(1)
browser.set_input_value("#password", "Pr0ton!@Test123")
time.sleep(1)
browser.set_input_value("#password-confirm", "Pr0ton!@Test123")
time.sleep(3)
snap(browser, "02_form_filled")

# ===== STEP 3: 提交表单 =====
logger.info("===== STEP 3: 提交表单 =====")
submit_pos = eval_json(browser, """
    (() => {
        const btn = document.querySelector('button[type="submit"]');
        if (btn && !btn.disabled) {
            const r = btn.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2, text: btn.textContent.trim()};
        }
        return {error: 'no submit button'};
    })()
""")
logger.info("Submit button: %s", json.dumps(submit_pos, ensure_ascii=False))

if 'error' not in submit_pos:
    browser.click_at(submit_pos['x'], submit_pos['y'])
    time.sleep(8)
    snap(browser, "03_after_submit")
else:
    logger.error("找不到提交按钮！")
    snap(browser, "03_no_submit")
    time.sleep(30)
    browser.close()
    sys.exit(1)

# ===== STEP 4: 关闭 upsell =====
logger.info("===== STEP 4: 关闭 upsell =====")
for i in range(5):
    dismissed = eval_str(browser, """
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
    if dismissed:
        logger.info("关闭 upsell: '%s'", dismissed)
        time.sleep(2)
    else:
        break
time.sleep(3)
snap(browser, "04_after_upsell")

# ===== STEP 5: 分析当前页面状态 =====
logger.info("===== STEP 5: 分析当前页面 =====")
page_state = eval_json(browser, """
    (() => {
        const data = {
            url: location.href,
            bodyText: (document.body ? document.body.innerText : '').substring(0, 2000),
            iframes: [],
        };
        document.querySelectorAll('iframe').forEach((f, i) => {
            const r = f.getBoundingClientRect();
            if (r.width > 0) {
                data.iframes.push({
                    index: i, src: f.src.substring(0, 200),
                    x: Math.round(r.x), y: Math.round(r.y),
                    w: Math.round(r.width), h: Math.round(r.height),
                });
            }
        });
        return JSON.stringify(data);
    })()
""")
logger.info("页面状态: %s", json.dumps(page_state, ensure_ascii=False, indent=2)[:1000])

# ===== STEP 6: 处理 CAPTCHA =====
# 根据截图分析，unauth challenge 是一个数字顺序点选 CAPTCHA
# 需要在 iframe 中找到编号圆圈并按顺序点击
logger.info("===== STEP 6: 处理 CAPTCHA =====")

# 先获取所有 iframe 的坐标
captcha_iframe = None
for iframe in page_state.get('iframes', []):
    src = iframe.get('src', '')
    if 'unauth' in src:
        captcha_iframe = iframe
        break

if captcha_iframe:
    logger.info("找到 captcha iframe: %s", json.dumps(captcha_iframe, ensure_ascii=False))
    
    # 获取 iframe 内部的元素（通过 CDP Frame Tree）
    frame_tree = browser._send_cmd("Page.getFrameTree", {})
    frames = frame_tree.get('frameTree', {}).get('childFrames', [])
    logger.info("Frame tree has %d child frames", len(frames))
    
    # 获取每个 frame 的 ID
    frame_ids = []
    def collect_frames(tree):
        fid = tree.get('frame', {}).get('id', '')
        url = tree.get('frame', {}).get('url', '')
        if fid:
            frame_ids.append({'id': fid, 'url': url})
        for child in tree.get('childFrames', []):
            collect_frames(child)
    collect_frames(frame_tree.get('frameTree', {}))
    logger.info("All frames: %s", json.dumps(frame_ids, ensure_ascii=False))
    
    # 找到 captcha frame
    captcha_frame_id = None
    for f in frame_ids:
        if 'challenge' in f['url'] or 'captcha' in f['url']:
            captcha_frame_id = f['id']
            logger.info("Captcha frame: %s", f['url'][:80])
            break
    
    if captcha_frame_id:
        # 在 iframe 中执行 JS 获取元素
        # 需要使用 Runtime.evaluate with contextId
        # 先获取 iframe 的 execution context
        # 使用 Page.createIsolatedWorld 来在 iframe 中执行 JS
        try:
            world = browser._send_cmd("Page.createIsolatedWorld", {
                "frameId": captcha_frame_id,
                "grantUniveralAccess": True,
            })
            context_id = world.get('result', {}).get('executionContextId')
            logger.info("Isolated world context: %s", context_id)
            
            if context_id:
                # 获取 iframe 内部的元素
                elements = browser._send_cmd("Runtime.evaluate", {
                    "expression": """
                        (() => {
                            const els = [];
                            document.querySelectorAll('*').forEach(el => {
                                const r = el.getBoundingClientRect();
                                if (r.width > 0 && r.height > 0) {
                                    els.push({
                                        tag: el.tagName,
                                        cls: (el.className || '').toString().substring(0, 60),
                                        text: (el.textContent || '').trim().substring(0, 40),
                                        id: el.id || '',
                                        x: r.x, y: r.y, w: r.width, h: r.height,
                                        role: el.getAttribute('role') || '',
                                        dataValue: el.getAttribute('data-value') || '',
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
                logger.info("iframe 元素: %s", json.dumps(els_data, ensure_ascii=False, indent=2)[:2000])
                
                # 保存
                with open(os.path.join(OUT, "captcha_elements.json"), "w", encoding="utf-8") as f:
                    json.dump(els_data, f, ensure_ascii=False, indent=2)
                
                # 截图 iframe 区域
                snap(browser, "05_captcha_iframe")
        except Exception as e:
            logger.warning("iframe 访问失败: %s", e)
            snap(browser, "05_iframe_error")
    else:
        logger.warning("未找到 captcha frame")
        snap(browser, "05_no_captcha_frame")
else:
    logger.info("没有 captcha iframe，检查是否已有其他验证")
    snap(browser, "05_no_captcha")

# 保持浏览器打开
logger.info("浏览器保持打开 60 秒，供分析...")
time.sleep(60)
browser.close()
logger.info("完成！")
