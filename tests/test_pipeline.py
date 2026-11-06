from app.validators import ein_ok, iban_ok, gstin_ok, pan_ok, ifsc_ok, aba_ok, individual_company_holder, normalize_name, name_score
from app.pipeline import process
from app.samples import SAMPLES

def test_ein():
 assert ein_ok('12-3456789') and not ein_ok('123456789')
def test_iban_mod97():
 assert iban_ok('GB82 WEST 1234 5698 7654 32') and not iban_ok('GB82WEST12345698765433')
def test_gstin_checksum():
 assert gstin_ok('27AAPFU0939F1ZV') and not gstin_ok('27AAPFU0939F1ZW')
def test_pan_format():
 assert pan_ok('ABCDE1234F') and not pan_ok('ABCD1234F')
def test_aba_checksum():
 assert aba_ok('021000021') and not aba_ok('021000022') and not aba_ok('12345678')
def test_ifsc_format():
 assert ifsc_ok('ABCD0123456') and not ifsc_ok('ABC0123456') and not ifsc_ok('ABCD1123456')
def test_name_suffix_normalization():
 assert normalize_name('Sunrise Textiles Pvt. Ltd.')==normalize_name('SUNRISE TEXTILES PRIVATE LIMITED')
 assert name_score('Sunrise Textiles Pvt. Ltd.','SUNRISE TEXTILES PRIVATE LIMITED')>=.92
 assert normalize_name('  ACME, Inc. ')==normalize_name('Acme Incorporated')
def test_individual_holder_detection():
 assert individual_company_holder('company','Northwind Logistics LLC','Rahul Mehta')
 assert not individual_company_holder('individual','Rahul Mehta','Rahul Mehta')
def test_expected_sample_outcomes(tmp_path, monkeypatch):
 from app import db
 monkeypatch.setattr(db,'DB',str(tmp_path/'test.db'))
 expected={'happy_path_clean':('APPROVED',{'R-DECISION-01'}),'edge_name_variants':('APPROVED',{'R-DECISION-01'}),'edge_holder_mismatch':('PENDING',{'R-NAME-03','R-NAME-04','R-DECISION-01'}),'edge_wrong_taxid_country':('PENDING',{'R-TAX-02','R-DECISION-01'}),'edge_duplicate_bank_account':('REJECTED',{'R-FRAUD-01','R-DECISION-01'}),'edge_incomplete_and_expired':('PENDING',{'R-COMPLETE-01','R-DOC-01','R-DECISION-01'}),'edge_incomplete_and_expired_corrected':('APPROVED',{'R-DECISION-01'}),'edge_email_domain_mismatch':('PENDING',{'R-CONTACT-01','R-CONTACT-02','R-DECISION-01'})}
 for name,(status,rules) in expected.items():
  result=process(SAMPLES[name])['result']; assert result['status']==status
  actual=set(result.get('decision_rule_ids',[]))
  actual|={f.get('evidence',{}).get('rule_id') for f in result['decision_reasons'] if f.get('evidence',{}).get('rule_id')}
  assert rules<=actual,(name,rules,actual)

def test_vendor_messages_never_expose_internal_terms(tmp_path,monkeypatch):
 from app import db
 monkeypatch.setattr(db,'DB',str(tmp_path/'messages.db'))
 forbidden=('duplicate','fraud','other vendor','r-','recorded rules')
 for name,payload in SAMPLES.items():
  result=process(payload)['result'];message=result['vendor_message'].lower()
  assert not any(term in message for term in forbidden),name
  if result['status']!='APPROVED':
   bullets=[line for line in result['vendor_message'].splitlines() if line.startswith('• ')]
   assert bullets and len(bullets)==len(set(bullets)),name

def test_pending_vendor_message_uses_calendar_deadline_and_unique_bullets(tmp_path,monkeypatch):
 from datetime import date,timedelta
 from app import db
 monkeypatch.setattr(db,'DB',str(tmp_path/'pending-message.db'))
 message=process(SAMPLES['edge_holder_mismatch'])['result']['vendor_message']
 deadline=date.today()+timedelta(days=14)
 assert f'by {deadline.day} {deadline.strftime("%B %Y")}' in message
 bullets=[line for line in message.splitlines() if line.startswith('• ')]
 assert len(bullets)==2 and len(bullets)==len(set(bullets))
 assert any('authorization letter or a bank letter' in line and 'bank.account_holder_name' in line for line in bullets)

def test_duplicate_bank_account_rule_id(tmp_path,monkeypatch):
 from app import db
 monkeypatch.setattr(db,'DB',str(tmp_path/'dupe.db'))
 result=process(SAMPLES['edge_duplicate_bank_account'])['result']
 assert result['status']=='REJECTED'
 assert any(f.get('evidence',{}).get('rule_id')=='R-FRAUD-01' for f in result['decision_reasons'])

def test_resubmission_flow_links_parent_and_approves(tmp_path, monkeypatch):
 from app import db
 from fastapi.testclient import TestClient
 from app.main import app
 monkeypatch.setattr(db,'DB',str(tmp_path/'resubmit.db'))
 with TestClient(app) as client:
  first=client.post('/api/runs',json=SAMPLES['edge_incomplete_and_expired']).json()
  corrected=client.post('/api/runs/'+first['id']+'/resubmit',json=SAMPLES['edge_incomplete_and_expired_corrected']).json()
  assert first['result']['status']=='PENDING'
  assert corrected['result']['status']=='APPROVED'
  assert corrected['parent_run_id']==first['id']

def test_autoseed_runs_once_only_when_empty(tmp_path,monkeypatch):
 import os
 from app import db
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setattr(db,'DB',str(tmp_path/'seed.db'))
 monkeypatch.setenv('VENDORGATE_AUTOSEED','true')
 with TestClient(app) as client:
  seeded=client.get('/api/runs').json()
  assert len(seeded)==len(SAMPLES)
 with TestClient(app) as client:
  assert len(client.get('/api/runs').json())==len(SAMPLES)

def test_admin_reset_restores_seed_and_happy_path(tmp_path,monkeypatch):
 from app import db
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setattr(db,'DB',str(tmp_path/'reset.db'))
 monkeypatch.delenv('VENDORGATE_AUTOSEED',raising=False)
 with TestClient(app) as client:
  client.post('/api/runs',json=SAMPLES['happy_path_clean'])
  assert client.get('/api/runs').json()
  reset=client.post('/api/admin/reset').json()
  assert reset=={'status':'reset','runs':0}
  rerun=client.post('/api/runs',json=SAMPLES['happy_path_clean']).json()
  assert rerun['result']['status']=='APPROVED'

def test_admin_reset_stays_empty_when_autoseed_is_enabled(tmp_path,monkeypatch):
 from app import db
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setattr(db,'DB',str(tmp_path/'reset-autoseed.db'))
 monkeypatch.setenv('VENDORGATE_AUTOSEED','true')
 with TestClient(app) as client:
  assert len(client.get('/api/runs').json())==len(SAMPLES)
  reset=client.post('/api/admin/reset').json()
  assert reset=={'status':'reset','runs':0}
  assert client.get('/api/runs').json()==[]
