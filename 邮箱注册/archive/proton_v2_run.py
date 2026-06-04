#!/usr/bin/env python3
"""
Proton Mail 完整注册实跑 v2
发现: 第一次提交后会显示确认密码字段 #password-confirm
需要: 填写用户名 → 密码 → 提交 → 填写确认密码 → 再次提交
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_base import (
    AccountInfo, RegistrationResult, generate_account, launch_browser,
    wait_and_click, wait_and_type, set_value_and_dispatch, click_submit,
    detect_captcha, wait_for_captcha_clear, take_screenshot, save_result,
    random_password,
)
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live_run.log"), encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def try_proton_v2(headless=False):
    account = generate_account("proton", "proton.me")
    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Proton Mail v2 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(10)
        
        take_screenshot(browser, "proton_v2_initial")
        
        # Step 1: Fill username
        nid = browser.query_selector("#username")
        if nid and browser.is_element_visible(nid):
            rect = browser.get_element_rect(nid)
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.5)
            browser.type_text(account.username, delay_ms=80)
            logger.info("[STEP1] 用户名: %s", account.username)
        
        time.sleep(1)
        
        # Step 2: Fill password
        nid = browser.query_selector("#password")
        if nid and browser.is_element_visible(nid):
            rect = browser.get_element_rect(nid)
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.5)
            browser.type_text(account.password, delay_ms=80)
            logger.info("[STEP2] 密码已填写")
        
        time.sleep(1)
        
        # Step 3: First submit (reveals confirm password)
        submit_info = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                if (btn) {
                    const r = btn.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2, text: btn.textContent.trim()};
                }
                return null;
            })()
        """)
        if submit_info:
            browser.click_at(submit_info['x'], submit_info['y'])
            logger.info("[STEP3] 第一次提交: '%s'", submit_info.get('text', ''))
        
        time.sleep(3)
        take_screenshot(browser, "proton_v2_after_first_submit")
        
        # Step 4: Check for confirm password field
        confirm_pwd = browser.query_selector("#password-confirm")
        if confirm_pwd and browser.is_element_visible(confirm_pwd):
            rect = browser.get_element_rect(confirm_pwd)
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.5)
            browser.type_text(account.password, delay_ms=80)
            logger.info("[STEP4] 确认密码已填写")
            time.sleep(1)
        else:
            logger.info("[STEP4] 未发现确认密码字段")
        
        # Step 5: Check for other new fields (email recovery, etc.)
        new_elements = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('input:not([type=hidden]), button[type="submit"]');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName, type: e.type || '',
                    id: e.id || '', name: e.name || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 60),
                    placeholder: e.placeholder || '',
                })).slice(0, 20);
            })()
        """)
        logger.info("[STEP5] 当前元素: %s", json.dumps(new_elements, ensure_ascii=False, indent=2))
        
        # Step 6: Check for recovery email option (skip if present)
        body = browser.get_body_text().lower()
        if 'recovery' in body or 'recover' in body or '恢复' in body:
            logger.info("[STEP6] 检测到恢复选项")
            # Try to skip
            skip_info = browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button, a');
                    for (const b of btns) {
                        const text = (b.textContent || '').toLowerCase();
                        if (text.includes('skip') || text.includes('跳过') || text.includes('maybe later') || text.includes('稍后')) {
                            const r = b.getBoundingClientRect();
                            if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2, text: b.textContent.trim()};
                        }
                    }
                    return null;
                })()
            """)
            if skip_info:
                browser.click_at(skip_info['x'], skip_info['y'])
                logger.info("[STEP6] 跳过恢复选项: '%s'", skip_info.get('text', ''))
                time.sleep(3)
        
        # Step 7: Second submit
        submit_info = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                if (btn) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        return {x: r.x + r.width/2, y: r.y + r.height/2, text: btn.textContent.trim()};
                    }
                }
                return null;
            })()
        """)
        if submit_info:
            browser.click_at(submit_info['x'], submit_info['y'])
            logger.info("[STEP7] 第二次提交: '%s'", submit_info.get('text', ''))
        
        time.sleep(10)
        take_screenshot(browser, "proton_v2_after_second_submit")
        
        result.final_url = browser.get_url()
        body = browser.get_body_text().lower()
        logger.info("[RESULT] URL: %s", result.final_url[:100])
        logger.info("[RESULT] Body: %s", body[:500])
        
        # Check for CAPTCHA
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "proton_v2_captcha")
            
            # Wait for auto-solve
            if wait_for_captcha_clear(browser, timeout=90):
                logger.info("[CAPTCHA] 已通过!")
                time.sleep(5)
            else:
                result.error = f"captcha: {captcha}"
        
        # Check for phone verification
        if 'phone' in body or 'mobile' in body:
            phone_el = browser.evaluate("""
                (() => {
                    const el = document.querySelector("input[type='tel'], input[name*='phone']");
                    if (el) { const r = el.getBoundingClientRect(); return {visible: r.width > 0 && r.height > 0}; }
                    return null;
                })()
            """)
            if phone_el and phone_el.get('visible'):
                result.error = "phone_verification_required"
                logger.warning("[WARN] Proton 需要手机号验证")
        
        # Check final state
        body = browser.get_body_text().lower()
        if 'welcome' in body or 'inbox' in body or 'mail.proton' in result.final_url:
            result.success = True
            logger.info("[OK] Proton 注册成功!")
        elif 'congratulations' in body or 'created' in body:
            result.success = True
            logger.info("[OK] Proton 注册成功!")
        elif not result.error:
            # Log what's on the page
            final_elements = browser.evaluate("""
                (() => {
                    const els = document.querySelectorAll('input:not([type=hidden]), button');
                    return Array.from(els).filter(e => {
                        const r = e.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    }).map(e => ({
                        tag: e.tagName, type: e.type || '',
                        id: e.id || '', text: (e.textContent || e.value || '').trim().substring(0, 60),
                    })).slice(0, 20);
                })()
            """)
            logger.info("[FINAL] 页面元素: %s", json.dumps(final_elements, ensure_ascii=False, indent=2))
        
        take_screenshot(browser, "proton_v2_final")
        browser.close()
        
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Proton v2 异常")
        if browser:
            try:
                take_screenshot(browser, "proton_v2_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


if __name__ == "__main__":
    r = try_proton_v2()
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
