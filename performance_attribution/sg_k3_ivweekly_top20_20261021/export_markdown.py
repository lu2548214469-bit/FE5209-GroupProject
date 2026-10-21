"""Export the same standalone report to GitHub-readable Markdown."""
from pathlib import Path
from html.parser import HTMLParser
import re

HERE=Path(__file__).resolve().parent
class ReportMarkdown(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.out=[];self.rows=None;self.row=[]
        self.cell=None;self.pre=False;self.links=[];self.figures=[]
    def emit(self,s):self.out.append(s)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='main':self.active=True;return
        if not self.active:return
        if tag=='table':self.rows=[];return
        if self.rows is not None:
            if tag=='tr':self.row=[]
            elif tag in ['td','th']:self.cell=[]
            return
        if tag in ['h1','h2','h3']:self.emit('\n\n'+'#'*int(tag[1])+' ')
        elif tag in ['p','div','section','dl','ol','ul']:self.emit('\n\n')
        elif tag=='li':self.emit('\n- ')
        elif tag=='dt':self.emit('\n\n**')
        elif tag=='dd':self.emit('\n\n')
        elif tag=='blockquote':self.emit('\n\n> ')
        elif tag=='strong':self.emit('**')
        elif tag=='pre':self.pre=True;self.emit('\n\n```text\n')
        elif tag=='code' and not self.pre:self.emit('`')
        elif tag=='a':self.links.append(a['href']);self.emit('[')
        elif tag=='img':
            name=a['alt'];assert (HERE/'report/figures'/name).is_file()
            self.figures.append(name);self.emit(f'\n\n![{name}](report/figures/{name})\n\n')
    def handle_endtag(self,tag):
        if not self.active:return
        if self.rows is not None:
            if tag in ['th','td']:
                self.row.append(' '.join(''.join(self.cell).split()).replace('|','\\|'));self.cell=None
            elif tag=='tr':self.rows.append(self.row)
            elif tag=='table':
                rows=self.rows;self.rows=None
                self.emit('\n\n'+'\n'.join('| '+' | '.join(r)+' |' for r in [rows[0],['---']*len(rows[0]),*rows[1:]])+'\n\n')
            return
        if tag=='main':self.active=False
        elif tag in ['h1','h2','h3','p','div','section','ol','ul','dl','dd','blockquote']:self.emit('\n\n')
        elif tag in ['strong','dt']:self.emit('**')
        elif tag=='pre':self.pre=False;self.emit('\n```\n\n')
        elif tag=='code' and not self.pre:self.emit('`')
        elif tag=='a':self.emit(']('+self.links.pop()+')')
    def handle_data(self,data):
        if not self.active:return
        if self.rows is not None:
            if self.cell is not None:self.cell.append(data)
        else:self.emit(data)

p=ReportMarkdown();p.feed((HERE/'report/SG_K3_ATTRIBUTION_ZH.html').read_text(encoding='utf-8'))
assert len(p.figures)==8
text=re.sub(r'\n[ \t]+','\n',''.join(p.out))
text=re.sub(r'\n{3,}','\n\n',text).strip()+'\n'
(HERE/'REPORT_ZH.md').write_text(text,encoding='utf-8')
print('Exported REPORT_ZH.md with',len(p.figures),'figures')
