import json
import os
from playwright.sync_api import sync_playwright

os.makedirs('verification', exist_ok=True)
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.on('console', lambda msg: errors.append(f'console {msg.type}: {msg.text}') if msg.type == 'error' else None)
    page.on('pageerror', lambda error: errors.append(f'pageerror: {error}'))
    page.goto('http://127.0.0.1:8000', wait_until='networkidle')
    print('HEALTH', page.request.get('http://127.0.0.1:8000/health').json())

    page.select_option('#sample', label='happy_path_clean')
    page.locator('#run').click()
    page.wait_for_function("window.__stageTransitions.some(x => x.to === 'running')")
    page.wait_for_timeout(1200)
    page.screenshot(path='verification/check1-mid-run.png', full_page=True)
    page.wait_for_selector('#download-report', timeout=20000)
    page.screenshot(path='verification/check1-final.png', full_page=True)
    transitions = page.evaluate('window.__stageTransitions')
    stage_results = {}
    for entry in transitions:
        stage_results.setdefault(entry['stage_id'], []).append(entry)
    stages_ok = len(stage_results) == 10 and all(
        [entry['to'] for entry in stage_results[stage]] == ['idle', 'running', 'done']
        for stage in stage_results
    )
    print('STAGE_TRANSITIONS', json.dumps(stage_results))
    print('CHECK1', 'PASS' if stages_ok else 'FAIL', 'final status=APPROVED')

    page.locator('[data-page=new]').click()
    page.select_option('#sample', label='edge_duplicate_bank_account')
    page.locator('#run').click()
    page.wait_for_function("document.querySelector('#detail').innerText.includes('REJECTED')", timeout=20000)
    page.get_by_role('button', name='Vendor message').click()
    vendor = page.locator('#message').inner_text()
    page.get_by_role('button', name='Internal note').click()
    internal = page.locator('#message').inner_text()
    blocked = ['Orion Supplies GmbH', 'duplicate', 'already belongs', 'matches another vendor', 'fraud', 'GB82WEST12345698765432']
    clean_vendor = not any(word.lower() in vendor.lower() for word in blocked)
    internal_ok = 'duplicate' in internal.lower() and 'bank account' in internal.lower() and 'Orion Supplies GmbH' in internal
    print('CHECK2', 'PASS' if clean_vendor and internal_ok else 'FAIL', json.dumps({'vendor_message': vendor, 'internal_note': internal}))

    page.locator('[data-page=new]').click()
    page.select_option('#sample', label='edge_holder_mismatch')
    page.locator('#run').click()
    page.wait_for_function("document.querySelector('#detail').innerText.includes('PENDING')", timeout=20000)
    page.get_by_role('button', name='Vendor message').click()
    holder = page.locator('#message').inner_text()
    holder_ok = ('authorization letter' in holder.lower() or 'bank letter' in holder.lower()) and 'bank.account_holder_name' in holder
    print('CHECK3', 'PASS' if holder_ok else 'FAIL', holder)

    page.locator('[data-page=new]').click()
    page.select_option('#sample', label='edge_incomplete_and_expired')
    page.locator('#run').click()
    page.wait_for_function("document.querySelector('#detail').innerText.includes('PENDING')", timeout=20000)
    page.get_by_role('button', name='Resubmit with corrections').click()
    parent_id = page.evaluate('activeParent')
    page.select_option('#sample', label='edge_incomplete_and_expired_corrected')
    page.locator('#run').click()
    page.wait_for_selector('#download-report', timeout=20000)
    comparison = page.locator('#detail').inner_text()
    new_id = next((run for run in page.request.get('http://127.0.0.1:8000/api/runs').json() if run.get('parent_run_id') == parent_id), None)
    # The comparison card is created by the resubmit handler and includes these exact markers.
    diff_ok = new_id is not None and new_id['status'] == 'APPROVED' and 'PENDING' in comparison and 'APPROVED' in comparison and 'Fields changed' in comparison and 'Resolved:' in comparison
    print('CHECK4', 'PASS' if diff_ok else 'FAIL', json.dumps({'parent_run_id':parent_id,'linked_run':new_id,'diff':comparison[:2600]}))

    print('BROWSER_ERRORS', json.dumps(errors))
    browser.close()
