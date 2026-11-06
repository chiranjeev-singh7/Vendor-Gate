from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path('verification/ui')
states=['dashboard-empty','new-form-sample','new-json-sample','live-mid','decision-approved','decision-pending','decision-rejected','dashboard-populated','drawer-diff','rules']
for round_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith('round')):
 for width in (1440,375):
  thumbs=[]
  for state in states:
   path=round_dir/f'{width}-{state}.png'
   if not path.exists():continue
   im=Image.open(path).convert('RGB'); im.thumbnail((340,210))
   tile=Image.new('RGB',(360,242),'#E9EDF3'); tile.paste(im,((360-im.width)//2,24))
   ImageDraw.Draw(tile).text((10,5),state,fill='#0F172A')
   thumbs.append(tile)
  if not thumbs:continue
  cols=2 if width==375 else 3; rows=(len(thumbs)+cols-1)//cols
  sheet=Image.new('RGB',(cols*360,rows*242),'#DDE3EA')
  for i,im in enumerate(thumbs):sheet.paste(im,((i%cols)*360,(i//cols)*242))
  sheet.save(round_dir/f'{width}-contact-sheet.png')
