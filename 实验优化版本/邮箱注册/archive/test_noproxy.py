"""Test without proxy - see if TUN mode routes from exec"""
import sys, os, logging, time
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
from cdp_browser import CDPBrowser, CDPLaunchConfig

config = CDPLaunchConfig()
browser = CDPBrowser(config).launch()
print('[TEST] Navigating WITHOUT proxy...')
browser.navigate('https://signup.live.com/signup', wait_for_load=True, timeout=30)
time.sleep(5)
url = browser.get_url()
title = browser.get_title()
body = browser.get_body_text()[:500]
print(f'URL: {url}')
print(f'Title: {title}')
print(f'Body: {body[:300]}')
els = browser.evaluate("(() => { const all = document.querySelectorAll('input,button,select'); return Array.from(all).map(e => e.tagName+'#'+e.id+'.'+e.name+' type:'+e.type+' vis:'+(e.offsetParent!==null)); })()")
print(f'Elements: {els}')
browser.close()
