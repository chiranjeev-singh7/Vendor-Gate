import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':768,'height':1024});page.goto('http://127.0.0.1:8000',wait_until='networkidle')
 for name in ['new','live','dashboard','rules']:
  page.locator(f'.nav-item[data-page="{name}"]').click();page.wait_for_timeout(120)
  result=page.evaluate('''()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,items:[...document.querySelectorAll('body *')].map(e=>({tag:e.tagName,id:e.id,cls:typeof e.className==='string'?e.className:'',left:Math.round(e.getBoundingClientRect().left),right:Math.round(e.getBoundingClientRect().right),w:Math.round(e.getBoundingClientRect().width)})).filter(x=>x.right>innerWidth+1||x.left<-1).slice(0,20)})''')
  print(name,json.dumps(result))
 b.close()
