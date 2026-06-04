import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_outlook import register_outlook_account, _random_account

print("[1] Starting registration...")
account = _random_account()
print(f"    email={account.email}")
print(f"    password={account.password}")
print(f"    name={account.first_name} {account.last_name}")
print(f"    birth={account.birth_year}-{account.birth_month}-{account.birth_day}")

print("[2] Launching CDP browser...")
result = register_outlook_account(account=account, headless=True)

print(f"\n{'='*60}")
print(f"[RESULT]")
print(f"  success: {result.success}")
print(f"  email: {result.email}")
print(f"  password: {result.password}")
print(f"  error: {result.error}")
print(f"  final_url: {result.final_url}")
print(f"  final_state: {result.final_state}")
print(f"  challenge_type: {result.challenge_type}")
print(f"  challenge_cleared: {result.challenge_cleared}")
print(f"  screenshot: {result.screenshot_path}")
