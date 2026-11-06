"""Browser regression check for stale Live run decisions and vendor messages."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    raise SystemExit('Playwright is missing from this Python environment. Run: pip install -r requirements-dev.txt') from exc

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'verification' / 'bugfix'
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def request(base, path, method='GET'):
    req = urllib.request.Request(base + path, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())


def run_and_check(page, base, sample, expected_name, expected_email, screenshot=None, expected_rules=()):
    page.locator('.nav-item[data-page="new"]').click()
    page.locator(f'.sample-card[data-sample="{sample}"]').click()
    page.locator('#run-process').click()
    page.wait_for_selector('#live-content .decision-card .decision-meta', timeout=20000)
    card = page.locator('#live-content .decision-card')
    page.wait_for_function("document.querySelector('#live-content .live-vendor-name')?.textContent.trim().length > 0")

    decision_name = card.locator('.decision-meta').inner_text().split(' · ')[0]
    header_name = page.locator('#live-content .live-vendor-name').evaluate('(el) => el.firstChild.textContent.trim()')
    to_address = card.locator('.message-meta span').first.inner_text()
    risk = card.locator('.risk-label strong').inner_text()
    reason_ids = card.locator('.reason-link .rule-id').all_inner_texts()
    assert decision_name == expected_name, (sample, 'decision vendor', decision_name)
    assert header_name == expected_name, (sample, 'header vendor', header_name)
    assert to_address == expected_email, (sample, 'recipient', to_address)
    assert set(expected_rules).issubset(reason_ids), (sample, 'reasons', reason_ids)

    runs = request(base, '/api/runs')
    saved = max((r for r in runs if r['vendor'] == expected_name), key=lambda r: r['submitted_at'])
    assert risk == f"{saved['result']['risk_score']}/100", (sample, risk, saved['result']['risk_score'])
    full_reason_ids = set(saved['result'].get('decision_rule_ids', []))
    assert set(reason_ids).issubset(full_reason_ids), (sample, reason_ids, full_reason_ids)
    if screenshot:
        card.screenshot(path=str(ARTIFACTS / screenshot))
    return {'sample': sample, 'vendor': header_name, 'to': to_address, 'risk': risk, 'reasons': reason_ids}


def main():
    with tempfile.TemporaryDirectory(prefix='vendorgate-live-') as temporary:
        env = os.environ.copy()
        env['VENDORGATE_DB'] = str(Path(temporary) / 'fresh.sqlite3')
        env['VENDORGATE_AUTOSEED'] = 'false'
        env['STAGE_DELAY_MS'] = '35'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    if request(base, '/health').get('status') == 'ok':
                        break
                except Exception:
                    time.sleep(.2)
            else:
                raise RuntimeError('Local VendorGate server did not become healthy')

            request(base, '/api/admin/reset', method='POST')
            browser_errors = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.on('pageerror', lambda error: browser_errors.append(str(error)))
                page.on('console', lambda message: browser_errors.append(message.text) if message.type == 'error' else None)
                page.goto(base, wait_until='networkidle')
                page.wait_for_selector('.sample-card')

                first = run_and_check(page, base, 'happy_path_clean', 'Brightstar Systems LLC', 'alex@brightstar.example', expected_rules=())
                second = run_and_check(page, base, 'edge_email_domain_mismatch', 'Oakfield Services Inc', 'accounts@gmail.com', expected_rules=('R-CONTACT-01', 'R-CONTACT-02'))
                assert second['vendor'] != first['vendor'] and second['to'] != first['to']
                assert not any(term in card_message.lower() for card_message in page.locator('.message-body').all_inner_texts() for term in ('duplicate', 'fraud', 'r-', 'recorded rules'))

                request(base, '/api/admin/reset', method='POST')
                outcomes = [
                    run_and_check(page, base, 'happy_path_clean', 'Brightstar Systems LLC', 'alex@brightstar.example', 'happy_path_clean.png'),
                    run_and_check(page, base, 'edge_duplicate_bank_account', 'Bluepeak Consulting Ltd', 'alex@brightstar.example', 'edge_duplicate_bank_account.png', ('R-FRAUD-01',)),
                    run_and_check(page, base, 'edge_holder_mismatch', 'Northwind Logistics LLC', 'alex@brightstar.example', 'edge_holder_mismatch.png', ('R-NAME-03', 'R-NAME-04')),
                ]
                browser.close()
            if browser_errors:
                raise AssertionError(f'Browser errors: {browser_errors}')
            print(json.dumps({'stale_run_test': 'PASS', 'sample_a': first, 'sample_b': second, 'decision_cards': outcomes, 'browser_errors': browser_errors, 'screenshots': str(ARTIFACTS)}, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == '__main__':
    main()
