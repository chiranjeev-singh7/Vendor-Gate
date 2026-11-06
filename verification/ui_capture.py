import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path('verification/ui')
ROUND=os.getenv('UI_ROUND','round1')
DEST=ROOT/ROUND
DEST.mkdir(parents=True,exist_ok=True)
errors=[]

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width,height in [(1440,1000),(375,812)]:
        prefix=str(width)
        page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
        page.on('console',lambda m:errors.append(f'{width} console {m.type}: {m.text}') if m.type=='error' else None)
        page.on('pageerror',lambda e:errors.append(f'{width} pageerror: {e}'))
        page.goto('http://127.0.0.1:8000',wait_until='networkidle')
        page.add_style_tag(content='*,*::before,*::after{cursor:none!important}.toast-region{display:none!important}')
        page.wait_for_selector('.sample-card')

        def navigate(name):
            if page.locator('#run-drawer.is-open').count():
                page.locator('#run-drawer .drawer-header .icon-button').click()
                page.wait_for_timeout(250)
            if width<768:
                page.locator('#menu-open').click()
            page.locator(f'.nav-item[data-page="{name}"]').click()
            page.wait_for_timeout(100)

        def shot(name):
            if name == 'new-form-sample':
                page.locator('#form-cards').scroll_into_view_if_needed()
            elif name == 'new-json-sample':
                page.locator('#json-editor').scroll_into_view_if_needed()
            page.mouse.move(width-2,height-2)
            page.screenshot(path=str(DEST/f'{prefix}-{name}.png'),full_page=name not in {'new-form-sample','new-json-sample'},animations='disabled')

        def reset():
            page.request.post('http://127.0.0.1:8000/api/admin/reset')

        def select(key):
            navigate('new')
            page.locator(f'.sample-card[data-sample="{key}"]').click()

        def run(key,mid_name=None,final_name=None):
            select(key)
            page.locator('#run-process').click()
            if mid_name:
                page.wait_for_selector('.step-row.running',timeout=15000)
                page.wait_for_timeout(250)
                shot(mid_name)
            page.wait_for_selector('#live-content .decision-card',timeout=20000)
            if final_name:shot(final_name)

        reset()
        navigate('dashboard')
        page.wait_for_selector('#runs-content .empty-state')
        shot('dashboard-empty')

        select('edge_name_variants')
        shot('new-form-sample')
        page.locator('#tab-json').click()
        shot('new-json-sample')

        reset()
        run('happy_path_clean','live-mid','decision-approved')
        reset()
        run('edge_holder_mismatch',final_name='decision-pending')
        reset()
        run('edge_duplicate_bank_account',final_name='decision-rejected')

        reset()
        navigate('new')
        page.locator('#run-all').click()
        page.wait_for_selector('#runs-content table tbody tr',timeout=20000)
        shot('dashboard-populated')

        reset()
        select('edge_incomplete_and_expired')
        page.locator('#run-process').click()
        page.wait_for_selector('#live-content .decision-card',timeout=20000)
        page.get_by_role('button',name='Resubmit with corrections').click()
        page.locator('.sample-card[data-sample="edge_incomplete_and_expired_corrected"]').click()
        page.locator('#run-process').click()
        page.wait_for_selector('#live-content .diff-panel',timeout=20000)
        navigate('dashboard')
        row=page.locator('#runs-content tbody tr').filter(has_text='Oldstone Trading Inc').first
        row.click()
        page.wait_for_selector('#run-drawer .diff-panel',timeout=10000)
        page.locator('#run-drawer .diff-panel').scroll_into_view_if_needed()
        page.wait_for_timeout(3800)
        shot('drawer-diff')

        navigate('rules')
        shot('rules')

        at_width=page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth')
        page.set_viewport_size({'width':768,'height':1024})
        page.wait_for_timeout(100)
        overflow=page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth')
        print(f'VIEWPORT width={width} overflow={at_width}; 768 overflow={overflow}')
        page.close()
    browser.close()

print('BROWSER_ERRORS',json.dumps(errors,ensure_ascii=False))
print('SCREENSHOTS',len(list(DEST.glob('*.png'))),str(DEST))
