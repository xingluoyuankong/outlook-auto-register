#!/usr/bin/env python3
"""Ninjemail 启动测试脚本"""

from ninjemail import Ninjemail

print("=" * 50)
print("Ninjemail 库加载成功!")
print("=" * 50)

# 初始化 Ninjemail（不带API密钥，仅测试初始化）
ninja = Ninjemail(browser="firefox")

print(f"\n✓ 初始化成功")
print(f"  - 浏览器: {ninja.browser}")
print(f"  - 支持的验证码服务: {ninja.captcha_services_supported}")
print(f"  - 支持的短信服务: {ninja.sms_services_supported}")

print("\n" + "=" * 50)
print("示例用法:")
print("=" * 50)
print("""
# 创建 Outlook 账户
email, password = ninja.create_outlook_account(
    username="testuser",
    password="testpassword123",
    first_name="John",
    last_name="Doe",
    country="USA",
    birthdate="01-01-1990"
)

# 创建 Gmail 账户
email, password = ninja.create_gmail_account(
    username="testuser",
    password="testpassword123",
    first_name="John",
    last_name="Doe",
    birthdate="01-01-1990"
)

# 创建 Yahoo 账户
email, password = ninja.create_yahoo_account(
    username="testuser",
    password="testpassword123",
    first_name="John",
    last_name="Doe",
    birthdate="01-01-1990"
)
""")
print("=" * 50)
print("✓ Ninjemail 项目已就绪！")
print("=" * 50)
