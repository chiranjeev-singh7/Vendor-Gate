import sqlite3, json, os
DB=os.getenv('VENDORGATE_DB','vendorgate.db')
def connect():
 c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; return c
def init_db():
 c=connect(); c.executescript('''CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, submitted_at TEXT, vendor TEXT, country TEXT, status TEXT, risk INTEGER, confidence INTEGER, total_ms INTEGER, payload TEXT, result TEXT, previous_id TEXT); CREATE TABLE IF NOT EXISTS events(run_id TEXT, seq INTEGER, event TEXT, PRIMARY KEY(run_id,seq)); CREATE TABLE IF NOT EXISTS vendors(name TEXT, country TEXT, tax_id TEXT, bank_ref TEXT, payload TEXT);''')
 if c.execute('SELECT COUNT(*) FROM vendors').fetchone()[0]==0:
  seeds=[('Orion Supplies GmbH','DE','DE123456789','GB82WEST12345698765432')]
  seeds += [(f'Seed Vendor {i} Ltd','GB',f'GB1234567{i:02d}',f'GB29NWBK601613319268{i:02d}') for i in range(1,8)]
  c.executemany('INSERT INTO vendors VALUES(?,?,?,?,?)',[(n,co,t,b,'{}') for n,co,t,b in seeds])
 c.commit(); c.close()
def save_run(run, events):
 c=connect(); r=run['result']; p=run['payload']; c.execute('INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(run['id'],p.get('submitted_at'),p.get('legal_name',''),p.get('country',''),r['status'],r['risk_score'],r['confidence'],r['total_ms'],json.dumps(p),json.dumps(r),run.get('previous_id')))
 for i,e in enumerate(events): c.execute('INSERT OR REPLACE INTO events VALUES(?,?,?)',(run['id'],i,json.dumps(e)))
 if r['status']=='APPROVED': c.execute('INSERT INTO vendors VALUES(?,?,?,?,?)',(p.get('legal_name',''),p.get('country',''),p.get('tax',{}).get('tax_id',''),p.get('bank',{}).get('iban') or p.get('bank',{}).get('account_number',''),json.dumps(p)))
 c.commit(); c.close()
def all_runs():
 c=connect(); rows=c.execute('SELECT * FROM runs ORDER BY submitted_at DESC').fetchall(); c.close(); result=[dict(x) for x in rows]
 for x in result:x['parent_run_id']=x.get('previous_id')
 return result
def run_count():
 c=connect(); count=c.execute('SELECT COUNT(*) FROM runs').fetchone()[0]; c.close(); return count
def get_run(id):
 c=connect(); r=c.execute('SELECT * FROM runs WHERE id=?',(id,)).fetchone(); ev=c.execute('SELECT event FROM events WHERE run_id=? ORDER BY seq',(id,)).fetchall(); c.close()
 if not r:return None
 d=dict(r); d['parent_run_id']=d.get('previous_id'); d['payload']=json.loads(d['payload']); d['result']=json.loads(d['result']); d['events']=[json.loads(x[0]) for x in ev]; return d
