from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio, json, os
from . import db
from .pipeline import process
from .samples import SAMPLES
app=FastAPI(title='VendorGate')
QUEUES={}
ROOT=Path(__file__).resolve().parent
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
@app.on_event('startup')
def startup():
 db.init_db()
 if os.getenv('VENDORGATE_AUTOSEED','false').lower()=='true' and db.run_count()==0:
  for payload in SAMPLES.values():
   rec=process(payload,0); db.save_run(rec,rec['events'])
@app.get('/',response_class=HTMLResponse)
def home(): return (ROOT/'static'/'index.html').read_text(encoding='utf-8').replace('</body>','<script src="/static/stepper.js"></script></body>')
@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/api/admin/reset')
def reset_demo_data():
 c=db.connect(); c.execute('DELETE FROM events'); c.execute('DELETE FROM runs'); c.execute('DELETE FROM vendors'); c.commit(); c.close()
 db.init_db(); QUEUES.clear()
 return {'status':'reset','runs':db.run_count()}
@app.get('/api/samples')
def samples(): return SAMPLES
@app.get('/api/runs')
def runs(): return [{**x,'payload':json.loads(x['payload']),'result':json.loads(x['result'])} for x in db.all_runs()]
@app.get('/api/runs/{rid}')
def run(rid):
 x=db.get_run(rid)
 if not x: raise HTTPException(404,'Run not found')
 return x
async def execute(payload,parent_id=None):
 rec=process(payload,0); rec['previous_id']=parent_id; db.save_run(rec,rec['events']); return rec
@app.post('/api/runs/start')
async def start_run(request:Request):
 try:payload=await request.json()
 except Exception:payload={}
 rid=__import__('uuid').uuid4().hex; queue=asyncio.Queue(); QUEUES[rid]=queue; loop=asyncio.get_running_loop()
 def work():
  rec=process(payload,int(os.getenv('STAGE_DELAY_MS','400')),lambda ev:loop.call_soon_threadsafe(queue.put_nowait,ev)); rec['id']=rid; db.save_run(rec,rec['events']); loop.call_soon_threadsafe(queue.put_nowait,{'done':True,'result':rec['result']})
 asyncio.create_task(asyncio.to_thread(work)); return {'id':rid}
@app.get('/api/stream/{rid}')
async def live_stream(rid):
 queue=QUEUES.get(rid)
 if queue is None:raise HTTPException(404,'No active stream for this run')
 async def gen():
  while True:
   item=await queue.get(); yield 'data: '+json.dumps(item)+'\n\n'
   if item.get('done'):QUEUES.pop(rid,None);break
 return StreamingResponse(gen(),media_type='text/event-stream')
@app.post('/api/runs')
async def create(request:Request):
 try: payload=await request.json()
 except Exception: payload={}
 return await execute(payload)
@app.post('/api/runs/{rid}/resubmit')
async def resubmit(rid,request:Request):
 parent=db.get_run(rid)
 if not parent:raise HTTPException(404,'Previous run not found')
 try:payload=await request.json()
 except Exception:raise HTTPException(400,'Submission must be valid JSON')
 rec=await execute(payload,parent_id=rid); rec['previous_id']=rid; rec['parent_run_id']=rid
 return rec
@app.post('/api/upload')
async def upload(file:UploadFile=File(...)):
 try: payload=json.loads((await file.read()).decode('utf-8'))
 except Exception: raise HTTPException(400,'Upload must be valid JSON')
 return await execute(payload)
@app.post('/api/run-samples')
async def run_samples():
 out=[]
 for payload in SAMPLES.values(): out.append(await execute(payload))
 return out
@app.get('/api/runs/{rid}/events')
async def stream(rid):
 x=db.get_run(rid)
 if not x: raise HTTPException(404,'Run not found')
 async def gen():
  for ev in x['events']:
   yield 'data: '+json.dumps(ev)+'\n\n'; await asyncio.sleep(.35)
  yield 'data: '+json.dumps({'done':True,'result':x['result']})+'\n\n'
 return StreamingResponse(gen(),media_type='text/event-stream')
