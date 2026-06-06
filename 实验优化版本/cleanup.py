#!/usr/bin/env python3
"""
项目结构清理脚本
将测试/debug/原型文件移到 archive/ 目录，保留核心文件。
运行方式: cd 到项目根目录后执行 py cleanup.py
"""
import os
import shutil
from pathlib import Path

PROJECT = Path(__file__).parent

# ── 邮箱注册/ 目录下的测试/debug/原型文件 → 邮箱注册/archive/ ──
邮箱注册_ARCHIVE = [
    # 代理测试迭代 (7个)
    "test_proxy.py", "test_proxy2.py", "test_proxy3.py", "test_proxy4.py",
    "test_proxy5.py", "test_proxy6.py", "test_proxy_chrome.py", "test_chrome_proxy.py",
    # 验证码测试迭代 (5个)
    "test_captcha.py", "test_captcha2.py", "test_captcha3.py", "test_captcha4.py", "test_captcha5.py",
    # 调试文件 (12个)
    "debug_signup.py", "debug_consent.py", "debug_new_email.py", "debug_urls.py",
    "debug_enter_email.py", "debug_typed.py", "debug_steps.py", "debug_selectors.py",
    "debug_fill.py", "debug_full.py", "debug_manual.py", "debug_verbose.py",
    "debug_birthdate.py", "debug_birthdate2.py", "debug_page.py", "debug_page2.py",
    # 注册测试/原型
    "test_real_reg.py", "test_e2e.py", "test_final.py", "test_deep.py",
    "test_remaining.py", "test_noproxy.py", "test_register.py", "test_single_provider.py",
    # Proton 版本迭代 (v2-v9 + 其他)
    "proton_v2_run.py", "proton_v3_run.py", "proton_v4_check.py",
    "proton_v5_run.py", "proton_v6_run.py", "proton_v7_run.py",
    "proton_v8_run.py", "proton_v9_run.py",
    "proton_full_run.py", "proton_deep_probe.py", "proton_full_flow.py",
    "proton_captcha_solve.py", "proton_captcha_drag.py", "proton_captcha_click.py",
    "proton_captcha_click2.py", "proton_captcha_v2.py", "proton_captcha_deep.py",
    "proton_captcha_screenshot.py", "proton_captcha_slider.py",
    "proton_smart_captcha.py", "proton_probe_form.py",
    "proton_challenge_direct.py", "proton_state_check.py",
    # 其他测试/原型
    "tutanota_deep.py", "aol_full_run.py", "live_run.py", "live_test_all.py",
    "probe_all.py", "sohu_probe.py", "run_all_providers.py",
    "run_register.py",  # 旧的注册入口，已被 integrated_server.py 替代
]

# ── 根目录测试文件 → archive/ ──
ROOT_ARCHIVE = [
    "test_run.py", "test_cdp.py", "test_cdp_quick.py",
]

# ── 根目录可删除的旧入口文件 (被 integrated_server.py 替代) ──
# 不删除，移到 archive
ROOT_OLD_ENTRY = [
    "launcher.py",  # desktop_ui 的 wrapper
    "start.py",     # 旧启动器
    "web_ui.py",    # 旧 web UI (gradio)
    "desktop_ui.py",  # 旧桌面 UI
]


def move_files(file_list, src_dir, dst_dir):
    """移动文件列表到目标目录"""
    moved = 0
    skipped = 0
    os.makedirs(dst_dir, exist_ok=True)
    for fname in file_list:
        src = os.path.join(src_dir, fname)
        if not os.path.exists(src):
            skipped += 1
            continue
        dst = os.path.join(dst_dir, fname)
        try:
            shutil.move(src, dst)
            moved += 1
            print(f"  ✅ {fname}")
        except Exception as e:
            print(f"  ❌ {fname}: {e}")
    return moved, skipped


def main():
    print("=" * 60)
    print("  邮箱注册 项目结构清理")
    print("=" * 60)

    # 1. 移动 邮箱注册/ 下的测试/debug 文件
    print(f"\n📁 移动 邮箱注册/ 下的测试/debug 文件 → 邮箱注册/archive/")
    n_dir = os.path.join(PROJECT, "邮箱注册")
    n_archive = os.path.join(n_dir, "archive")
    m, s = move_files(邮箱注册_ARCHIVE, n_dir, n_archive)
    print(f"   移动: {m}, 跳过(不存在): {s}")

    # 2. 移动根目录测试文件
    print(f"\n📁 移动根目录测试文件 → archive/")
    r_archive = os.path.join(PROJECT, "archive")
    m, s = move_files(ROOT_ARCHIVE, PROJECT, r_archive)
    print(f"   移动: {m}, 跳过(不存在): {s}")

    # 3. 移动旧入口文件
    print(f"\n📁 移动旧入口文件 → archive/")
    m, s = move_files(ROOT_OLD_ENTRY, PROJECT, r_archive)
    print(f"   移动: {m}, 跳过(不存在): {s}")

    # 4. 统计结果
    print("\n" + "=" * 60)
    print("  清理完成!")
    print("=" * 60)

    # 列出保留的核心文件
    print("\n📋 保留的核心文件:")
    core_files = []
    for f in sorted(os.listdir(PROJECT)):
        fp = os.path.join(PROJECT, f)
        if os.path.isfile(fp) and not f.startswith('.') and f != "cleanup.py":
            core_files.append(f)
    for f in core_files:
        print(f"  {f}")

    print(f"\n📋 邮箱注册/ 核心文件:")
    for f in sorted(os.listdir(n_dir)):
        fp = os.path.join(n_dir, f)
        if os.path.isfile(fp) and f.endswith('.py') and not f.startswith('test_') and not f.startswith('debug_'):
            print(f"  {f}")


if __name__ == "__main__":
    main()

