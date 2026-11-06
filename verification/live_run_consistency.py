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


def run_and_check(page, base, sample, expected_name, expected_email, expected_status, screenshot=None, expected_rules=(), require_single_run=False):
    page.locator('.nav-item[data-page="new"]').click()
    page.locator(f'.sample-card[data-sample="{sample}"]').click()
    page.locator('#run-process').click()
    page.wait_for_function("""({name,status}) => {
      const card=document.querySelector('#live-content .decision-card');
      const vendor=card?.querySelector('.decision-meta')?.textContent.split(String.fromCharCode(183))[0].trim();
      const decision=card?.querySelector('.decision-top .badge span')?.textContent.trim().toUpperCase();
      return vendor===name && decision===status;
    }""", arg={'name': expected_name, 'status': expected_status}, timeout=20000)
    card = page.locator('#live-content .decision-card')

    decision_name = card.locator('.decision-meta').evaluate('(el) => el.textContent.split(String.fromCharCode(183))[0].trim()')
    header_name = page.locator('#live-content .live-vendor-name').evaluate('(el) => el.firstChild.textContent.trim()')
    to_address = card.locator('.message-meta span').first.inner_text()
    vendor_message = card.locator('.message-body').inner_text()
    risk = card.locator('.risk-label strong').inner_text()
    status = card.locator('.decision-top .badge span').inner_text().upper()
    reason_ids = card.locator('.reason-link .rule-id').all_inner_texts()
    reason_summaries = card.locator('.reason-link > span:not(.rule-id)').all_inner_texts()
    tabs_spacing = card.locator('.message-tabs').evaluate('(el) => getComputedStyle(el).marginTop')
    assert decision_name == expected_name, (sample, 'decision vendor', decision_name)
    assert header_name == expected_name, (sample, 'header vendor', header_name)
    assert to_address == expected_email, (sample, 'recipient', to_address)
    assert status == expected_status, (sample, 'status', status)
    assert tabs_spacing == '16px', (sample, 'reason-to-tabs spacing', tabs_spacing)
    assert set(expected_rules).issubset(reason_ids), (sample, 'reasons', reason_ids)
    assert len(reason_summaries) == len(set(reason_summaries)), (sample, 'duplicate displayed reasons', reason_summaries)
    assert not any(token in text.lower() for text in reason_summaries for token in ('tax.ein','bank_letter','tax_certificate','account_holder_name')),(sample,'raw field label in reasons',reason_summaries)

    runs = request(base, '/api/runs')
    if require_single_run:
        assert len(runs) == 1, (sample, 'expected exactly one run after reset', len(runs))
    saved = max((r for r in runs if r['vendor'] == expected_name), key=lambda r: r['submitted_at'])
    assert risk == f"{saved['result']['risk_score']}/100", (sample, risk, saved['result']['risk_score'])
    full_reason_ids = set(saved['result'].get('decision_rule_ids', []))
    assert set(reason_ids).issubset(full_reason_ids), (sample, reason_ids, full_reason_ids)
    expected_visible_ids={f.get('evidence',{}).get('rule_id') for f in saved['result'].get('decision_reasons',[]) if f.get('stage')!='decision' and f.get('evidence',{}).get('rule_id')}
    assert set(reason_ids)==expected_visible_ids,(sample,'displayed reasons do not exactly match the findings',reason_ids,expected_visible_ids)
    if screenshot:
        card.screenshot(path=str(ARTIFACTS / screenshot))
    if status=='REJECTED':
        expected='Thank you for applying. We are unable to complete your onboarding at this time. If you believe this is an error, please contact our procurement team.'
        assert vendor_message==expected,(sample,'rejected wording',vendor_message)
        assert not any(term in vendor_message.lower() for term in ('document','certificate','provide','upload'))
    return {'sample': sample, 'vendor': header_name, 'status': status, 'to': to_address, 'risk': risk, 'reasons': reason_ids, 'vendor_message': vendor_message}


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

                first = run_and_check(page, base, 'happy_path_clean', 'Brightstar Systems LLC', 'operations@brightstar.example', 'APPROVED')
                second = run_and_check(page, base, 'edge_email_domain_mismatch', 'Oakfield Services Inc', 'accounts@gmail.com', 'PENDING', expected_rules=('R-CONTACT-01', 'R-CONTACT-02'))
                assert second['vendor'] != first['vendor'] and second['to'] != first['to']
                assert not any(term in card_message.lower() for card_message in page.locator('.message-body').all_inner_texts() for term in ('duplicate', 'fraud', 'r-', 'recorded rules'))

                cases = [
                    ('edge_holder_mismatch','Northwind Logistics LLC','operations@northwind-logistics.example','PENDING',('R-NAME-03','R-NAME-04')),
                    ('edge_duplicate_bank_account','Bluepeak Consulting Ltd','operations@bluepeak-consulting.example','REJECTED',('R-FRAUD-01',)),
                ]
                outcomes=[]
                for sample,name,email,status,rules in cases:
                    request(base, '/api/admin/reset', method='POST')
                    assert request(base, '/api/runs') == [], f'{sample}: database reset did not leave zero runs'
                    outcomes.append(run_and_check(page,base,sample,name,email,status,f'{sample}.png',rules,require_single_run=True))
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
