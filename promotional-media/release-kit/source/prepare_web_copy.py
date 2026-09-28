"""Build a paste-ready HTML description and local review pages; never publish."""
from pathlib import Path
import re,html
ROOT=Path(__file__).resolve().parents[1]
REMOTE='https://raw.githubusercontent.com/caleblee789/Homescreen-Dashboard/main/docs/images/1.8.7/'
def inline(t):
 t=html.escape(t)
 t=re.sub(r'\[([^\]]+)\]\((https://[^)]+)\)',r'<a href="\2">\1</a>',t)
 return re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',t)
def convert(s):
 out=[];para=[];ls=None
 def flush():
  if para:out.append('<p>'+inline(' '.join(para))+'</p>');para.clear()
 for line in s.splitlines()+['']:
  if not line:flush();continue
  match=re.match(r'^(\d+\. |[-*] )(.*)',line)
  if match:
   flush();kind='ol' if match[1][0].isdigit() else 'ul'
   if ls!=kind:
    if ls:out.append('</'+ls+'>')
    out.append('<'+kind+'>');ls=kind
   out.append('<li>'+inline(match[2])+'</li>');continue
  if ls:out.append('</'+ls+'>');ls=None
  if line.startswith('#'):
   flush();n=len(line)-len(line.lstrip('#'));out.append(f'<h{n}>'+inline(line[n:].strip())+f'</h{n}>')
  else:para.append(line)
 if ls:out.append('</'+ls+'>')
 return '\n'.join(out)
body=convert((ROOT/'drafts/ankiweb-description.md').read_text())
for section,stem,alt in [('See your progress','dashboard-sapphire-year','Sapphire Glass Year view with four statistics cards and the optional Bible verse hidden'),('Make it yours','dashboard-emerald-month','Emerald Month view with a Practice exam event and optional Bible verse')]:
 marker=f'<h2>{section}</h2>'
 image=f'<p><a href="{REMOTE}{stem}-full.png"><img src="{REMOTE}{stem}-web.jpg" alt="{alt}" width="960"></a></p>'
 body=body.replace(marker,image+'\n'+marker)
(ROOT/'drafts/ankiweb-description.html').write_text('<!-- DRAFT: Stage matching image assets after approval before applying this description. -->\n'+body+'\n')
style='body{font:17px/1.6 system-ui;max-width:960px;margin:40px auto;padding:0 24px;color:#192430;background:#f3f2ee}img{max-width:100%;height:auto}h1,h2{line-height:1.2}a{color:#236397}.status{padding:16px;background:#fff0d2;border:1px solid #dbc089}'
local=body.replace(REMOTE,'../docs/images/1.8.7/')
(ROOT/'review/ankiweb-preview.html').write_text('<!doctype html><meta charset="utf-8"><title>Home Screen Dashboard — description draft</title><style>'+style+'</style><p class="status">Local draft. Nothing published. Fresh native images are prepared. Package reconciliation and explicit approval are required before publication.</p>'+local)
(ROOT/'review/reddit-preview.html').write_text('<!doctype html><meta charset="utf-8"><title>Home Screen Dashboard — Reddit draft</title><style>'+style+'</style><p class="status">Local draft. Suggested flair: Add-ons. Recheck community rules when posting is authorized.</p>'+convert((ROOT/'drafts/reddit-announcement.md').read_text()))
print('Prepared AnkiWeb HTML and local copy previews.')
