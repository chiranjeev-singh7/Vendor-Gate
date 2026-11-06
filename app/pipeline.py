import re, time, uuid, json, os
from datetime import datetime, timezone, date, timedelta
from .validators import ein_ok, iban_ok, gstin_ok, pan_ok, ifsc_ok, aba_ok, individual_company_holder, name_score
from . import db

def process(payload, delay_ms=0, on_stage=None):
 start=time.time(); sub=dict(payload or {}); findings=[]; events=[]
 def clean(v):
  if isinstance(v,str): return ' '.join(v.replace('\u00a0',' ').split())
  if isinstance(v,list): return [clean(x) for x in v]
  if isinstance(v,dict): return {k:clean(x) for k,x in v.items()}
  return v
 sub=clean(sub); sub.setdefault('submission_id',str(uuid.uuid4())); sub.setdefault('submitted_at',datetime.now(timezone.utc).isoformat())
 stages=[('intake','Intake'),('completeness','Completeness'),('tax','Tax ID validation'),('bank','Bank validation'),('names','Name consistency'),('documents','Document check'),('risk','Risk and duplicate checks'),('decision','Decision engine'),('communication','Communication'),('persist','Persist and notify')]
 def stage(i,status,summary,details=None,evidence=None,severity='none'):
  ev={'stage_id':i,'name':dict(stages).get(i,i),'status':status,'summary':summary,'details':details or [],'evidence':evidence or {},'severity':severity,'duration_ms':0}; events.append(ev)
  if on_stage:on_stage({**ev,'status':'running','summary':'Stage is running'})
  if delay_ms:time.sleep(delay_ms/1000)
  ev['duration_ms']=delay_ms or max(1,int((time.time()-start)*1000))
  if on_stage:on_stage(ev)
  if severity!='none':findings.append({'stage':i,'summary':summary,'severity':severity,'evidence':evidence or {}})
  return ev
 docs=sub.get('documents') if isinstance(sub.get('documents'),list) else []; bank=sub.get('bank') or {}; tax=sub.get('tax') or {}
 stage('intake','pass','Submission parsed and normalized',evidence={'vendor':sub.get('legal_name','')})
 required=['legal_name','country','vendor_type']; missing=[k for k in required if not sub.get(k)]
 if sub.get('vendor_type')=='company':
  for d in ['incorporation_certificate','tax_certificate','bank_letter']:
   if not any(x.get('type')==d for x in docs):missing.append('document: '+d)
 stage('completeness','warn' if missing else 'pass','Missing: '+', '.join(missing) if missing else 'Required fields and documents present',missing,{'rule_id':'R-COMPLETE-01'} if missing else {},'fixable' if missing else 'none')
 t=tax.get('tax_id',''); typ=(tax.get('tax_id_type') or '').upper(); valid=True; expected=''
 if typ=='EIN': valid=ein_ok(t) and sub.get('country')=='US'; expected='XX-XXXXXXX (United States only)'
 elif typ=='GSTIN': valid=gstin_ok(t); expected='15-character GSTIN with valid check digit'
 elif typ=='PAN': valid=pan_ok(t); expected='AAAAA9999A'
 elif typ=='VAT' and sub.get('country')=='DE':valid=bool(re.fullmatch(r'DE\d{9}',t.upper()));expected='DE followed by 9 digits'
 elif typ=='VAT' and sub.get('country')=='GB':valid=bool(re.fullmatch(r'GB\d{9}(\d{3})?',t.upper()));expected='GB followed by 9 or 12 digits'
 elif typ=='COMPANY_NUMBER' and sub.get('country')=='GB':valid=bool(re.fullmatch(r'[A-Z0-9]{8}',t.upper()));expected='8 alphanumeric characters'
 else: valid=False; expected='supported country-specific tax ID';
 msg='Tax identifier format is valid' if valid else f"tax.{typ or 'tax_id'} expected format: {expected}"
 stage('tax','pass' if valid else 'warn',msg,evidence={'type':typ,'value':t,'expected':expected,**({'rule_id':'R-TAX-02'} if not valid else {})},severity='none' if valid else 'fixable')
 country=sub.get('country',''); bankok=True; bankmsg='Bank details structurally valid'
 if country=='IN':
  code=bank.get('routing_or_ifsc',''); bankok=ifsc_ok(code) and 6<=len(bank.get('account_number',''))<=18; bankmsg='India IFSC expected ABCD0123456 and account number 6–18 chars'
 elif country=='US' and bank.get('routing_or_ifsc'):
  code=bank['routing_or_ifsc']; bankok=aba_ok(code); bankmsg='US ABA routing number must be 9 digits with valid checksum'
 elif bank.get('iban'): bankok=iban_ok(bank['iban']); bankmsg='IBAN mod-97 checksum is valid' if bankok else 'IBAN format or mod-97 checksum is invalid'
 stage('bank','pass' if bankok else 'warn',bankmsg,evidence={'bank_country':bank.get('bank_country'), 'country':country,**({'rule_id':'R-BANK-01'} if not bankok else {})},severity='none' if bankok else 'fixable')
 legal=sub.get('legal_name',''); names=[(bank.get('account_holder_name') or '', 'bank.account_holder_name')]+[(d.get('name_on_document',''),'document.'+d.get('type','')) for d in docs if d.get('name_on_document')]
 low=[]
 for val,field in names:
  score=name_score(legal,val)
  if score<.92: low.append({'field':field,'value':val,'score':round(score,3)})
 individual_holder=individual_company_holder(sub.get('vendor_type'),legal,names[0][0] if names else '')
 nmsev='fixable' if low else 'none'; nmsg='Name signals: '+json.dumps(low) if low else 'Legal, bank, and document names match after normalization'
 stage('names','warn' if low else 'pass',nmsg,low,{'legal_name':legal,**({'rule_id':'R-NAME-03'} if low else {})},nmsev)
 expired=[d.get('type','document') for d in docs if d.get('expiry_date') and d['expiry_date']<datetime.now(timezone.utc).date().isoformat()]
 issuer_mismatch=[{'type':d.get('type','document'),'issuing_country':d.get('issuing_country'),'claimed_country':country} for d in docs if d.get('issuing_country') and country and d.get('issuing_country').upper()!=country.upper()]
 docflags=[]
 if expired:docflags.append({'summary':'Expired documents: '+', '.join(expired),'severity':'fixable','evidence':{'rule_id':'R-DOC-01','documents':expired}})
 if issuer_mismatch:docflags.append({'summary':'Document issuing country differs from vendor country','severity':'fixable','evidence':{'rule_id':'R-DOC-02','documents':issuer_mismatch}})
 for f in docflags:findings.append({'stage':'documents',**f})
 stage('documents','warn' if docflags else 'pass','; '.join(f['summary'] for f in docflags) if docflags else 'Document metadata is current and country-consistent',docflags,{},'fixable' if docflags else 'none')
 # Duplicate indicators; existing vendor master is populated by approved runs.
 db.init_db(); c=db.connect(); existing=c.execute('SELECT name,tax_id,bank_ref FROM vendors').fetchall(); c.close(); fraud=[]
 for row in existing:
  if bank.get('iban') and row['bank_ref']==bank['iban'] and name_score(legal,row['name'])<.75:fraud.append(f"Duplicate bank account is already registered to existing vendor {row['name']}")
  if t and row['tax_id']==t and name_score(legal,row['name'])<.75:fraud.append('tax ID already registered to a different name')
  elif t and row['tax_id']==t: findings.append({'stage':'risk','summary':'Possible duplicate vendor tax ID','severity':'fixable','evidence':{'tax_id':t}})
 contact=sub.get('contact') or {}; email=(contact.get('email') or '').rsplit('@',1)[-1].lower(); website=re.sub(r'^https?://','',contact.get('website') or '',flags=re.I).split('/')[0].lower(); website=website.removeprefix('www.')
 email_domain=email.removeprefix('www.'); free_domains={'gmail.com','yahoo.com','outlook.com','hotmail.com'}; contact_flags=[]
 if sub.get('vendor_type')=='company' and email in free_domains:
  contact_flags.append('R-CONTACT-02');findings.append({'stage':'risk','summary':f'Company contact uses free-mail domain {email}; provide a company email address','severity':'fixable','evidence':{'rule_id':'R-CONTACT-02','email_domain':email}})
 if email and website and email_domain!=website:
  contact_flags.append('R-CONTACT-01');findings.append({'stage':'risk','summary':f'Contact email domain {email_domain} does not match company website domain {website}; confirm the authorized contact address','severity':'fixable','evidence':{'rule_id':'R-CONTACT-01','email_domain':email_domain,'website_domain':website}})
 riskstatus='fail' if fraud else ('warn' if sub.get('country') in ['KP','IR','SY'] or individual_holder or contact_flags else 'pass')
 if individual_holder: findings.append({'stage':'risk','summary':'Company bank account holder appears to be an individual; provide authorization letter or company-name bank letter','severity':'fixable','evidence':{'rule_id':'R-NAME-04','holder':bank.get('account_holder_name')}})
 if fraud:
  for f in fraud:findings.append({'stage':'risk','summary':f,'severity':'fraud','evidence':{'rule_id':'R-FRAUD-01','vendor':legal}})
 risk_summary='; '.join(fraud) if fraud else ('Contact checks require attention: '+', '.join(contact_flags) if contact_flags else 'Enhanced manual review' if riskstatus=='warn' else 'No duplicate or high-risk signals')
 stage('risk',riskstatus,risk_summary,fraud,{'flags':fraud,'contact_rule_ids':contact_flags,'high_risk_country':country in ['KP','IR','SY']},'fraud' if fraud else ('fixable' if riskstatus=='warn' else 'none'))
 blocking=any(f['severity'] in ('fraud','blocking') for f in findings); pending=any(f['severity']=='fixable' for f in findings)
 status='REJECTED' if blocking else 'PENDING' if pending else 'APPROVED'; risk=min(100, len(findings)*18+(40 if blocking else 0)); confidence=92 if status=='APPROVED' else 86
 triggered=sorted({f.get('evidence',{}).get('rule_id') for f in findings if f.get('evidence',{}).get('rule_id')})
 triggered += ['R-DECISION-01']
 stage('decision','fail' if blocking else 'warn' if pending else 'pass',status+' based on recorded rules',findings,{'rule_id':'R-DECISION-01','risk_score':risk,'rule_ids':triggered},'fraud' if blocking else 'fixable' if pending else 'none')
 requests=[]
 def request(item):
  if item and item not in requests:requests.append(item)
 for finding in findings:
  evidence=finding.get('evidence') or {}; rule=evidence.get('rule_id'); summary=finding.get('summary','')
  if rule=='R-COMPLETE-01':
   missing=summary.partition('Missing:')[2]
   for entry in (x.strip() for x in missing.split(',')):
    if entry.startswith('document:'):
     kind=entry.partition(':')[2].strip().replace('_',' ')
     request(f'Please provide your {kind}.')
    elif entry:request(f'Please provide the vendor {entry.replace("_"," ")} field.')
  elif rule=='R-TAX-02':
   tax_formats={
    'DE':('German VAT ID (USt-IdNr)','format DE followed by 9 digits, e.g. DE123456789'),
    'US':('EIN','format XX-XXXXXXX'),
    'IN':('PAN (AAAAA9999A) and GSTIN (15 characters)',''),
    'GB':('VAT number','format GB followed by 9 or 12 digits'),
   }
   submitted_types={'EIN':('US','US EIN'),'PAN':('IN','Indian PAN'),'GSTIN':('IN','Indian GSTIN')}
   expected=tax_formats.get(country)
   if expected:
    expected_name,expected_format=expected
    requested=f'{expected_name}{", "+expected_format if expected_format else ""}'
    submitted=submitted_types.get(typ)
    if submitted and submitted[0]!=country:
     request(f"The ID provided is a {submitted[1]}, but we need the {requested}.")
    else:
     request(f'Please provide the {requested}.')
   else:
    request(f"Please provide the expected country-specific tax ID and format for {country or 'the vendor country'}.")
  elif rule=='R-BANK-01':
   request('Please review and correct the bank details so we can verify the payment account.')
  elif rule=='R-NAME-03':
   request('Please confirm that your legal name matches the name on your bank account and supporting documents.')
  elif rule=='R-NAME-04':
   request("For bank.account_holder_name, please provide an authorization letter or a bank letter in your company's name.")
  elif rule=='R-DOC-01':
   for kind in evidence.get('documents',[]):request(f"Please provide a current {str(kind).replace('_',' ')}.")
  elif rule=='R-DOC-02':
   request(f"Please provide a document issued in {country} to confirm the vendor's country.")
  elif rule=='R-CONTACT-01':
   domain=(contact.get('website') or '').removeprefix('https://').removeprefix('http://').removeprefix('www.').split('/')[0]
   request(f"Please confirm that {contact.get('email','')} is an authorized company contact, or provide an email using your company website domain ({domain}).")
  elif rule=='R-CONTACT-02':
   request("Please provide a contact email using your company's domain.")
  elif rule=='R-FRAUD-01' or finding.get('severity')=='fraud':
   request('We need to confirm your company registration details. Please reply with your official tax registration certificate.')
  elif finding.get('stage')=='risk' and evidence.get('contact_rule_ids'):
   continue
  elif finding.get('stage')=='risk' and summary=='Enhanced manual review' and requests:
   continue
  elif finding.get('severity') in ('fixable','blocking'):
   request('Please reply with an official document that confirms your company details.')
 generic_request='Please reply with an official document that confirms your company details.'
 if len(requests)>1 and generic_request in requests:requests.remove(generic_request)
 if status=='APPROVED':
  vendor_message='Welcome to VendorGate. Your vendor profile is approved. We will contact you with onboarding next steps.'
 elif status=='REJECTED':
  vendor_message='Thank you for applying. We are unable to complete your onboarding at this time. If you believe this is an error, please contact our procurement team.'
 else:
  intro='We need the following information to complete your verification:'
  if status=='PENDING':
   deadline=date.today()+timedelta(days=14)
   intro=f"Please provide the following information by {deadline.day} {deadline.strftime('%B %Y')} to complete your verification:"
  vendor_message=intro+'\n'+'\n'.join('• '+item for item in requests)+'\nReply to this email with the requested details.'
 internal='Internal findings: '+json.dumps(findings,ensure_ascii=False)
 stage('communication','pass','Vendor message and internal note generated',evidence={'vendor_message':vendor_message,'internal_note':internal})
 total=int((time.time()-start)*1000); stage('persist','pass','Run and immutable stage log saved',evidence={'status':status})
 return {'id':str(uuid.uuid4()),'payload':sub,'result':{'status':status,'risk_score':risk,'confidence':confidence,'decision_reasons':findings,'decision_rule_ids':triggered,'vendor_message':vendor_message,'internal_note':internal,'total_ms':total,'decision_mode':'rule-based'},'events':events}
