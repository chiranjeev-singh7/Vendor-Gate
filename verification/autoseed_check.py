import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    errors=[]
    page.on('console', lambda m: errors.append(f'{m.type}: {m.text}') if m.type=='error' else None)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8000', wait_until='networkidle')
    page.locator('[data-page=dashboard]').click()
    page.wait_for_function("document.querySelectorAll('#rows tr').length === 8")
    result={
        'health':page.request.get('http://127.0.0.1:8000/health').json(),
        'runs_api_count':len(page.request.get('http://127.0.0.1:8000/api/runs').json()),
        'dashboard_rows':page.locator('#rows tr').count(),
        'empty_state_hidden': 'hidden' in (page.locator('#dash-empty').get_attribute('class') or ''),
        'errors':errors,
    }
    print(json.dumps(result,ensure_ascii=False))
    browser.close()
