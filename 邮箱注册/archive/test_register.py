"""Quick CDP registration test"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from cdp_outlook import register_outlook_account

print("[TEST] Starting CDP Outlook registration (NO PROXY)...")

result = register_outlook_account(
    proxy="",
    headless=False,
)

print(f"\n{'='*50}")
print(f"Success: {result.success}")
print(f"Email: {result.email}")
print(f"Password: {result.password}")
print(f"Client ID: {result.client_id}")
print(f"Refresh Token: {getattr(result, 'refresh_token', 'N/A')}")
print(f"Error: {result.error}")
print(f"Final State: {result.final_state}")
print(f"Challenge: {result.challenge_type}")
print(f"{'='*50}")
