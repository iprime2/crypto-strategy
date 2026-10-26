import json, math
d=json.load(open('chart_data.json'))
L=d['labels']; n=len(L)
W=960; ML,MR,MT,MB=56,150,34,26
BLUE,ORANGE,AQUA,RED='#2a78d6','#eb6834','#1baf7a','#e34948'
INK,INK2,MUTED,GRID,AXIS,SURF='#0b0b0b','#52514e','#898781','#e1e0d9','#c3c2b7','#fcfcfb'
def esc(s): return s.replace('&','&amp;').replace('<','&lt;')
out=[]
def text(x,y,s,size=12,fill=INK2,anchor='start',weight=400,extra=''):
    out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" {extra}>{esc(s)}</text>')
def line_panel(y0,h,title,sub,series,ymin,ymax,ticks,fmt,unit=''):
    # series: list of (name,color,values(list with None))
    text(ML,y0-14,title,13,INK,weight=600); text(ML+len(title)*7.6+6,y0-14,sub,11,MUTED)
    pw=W-ML-MR
    xs=lambda i: ML+pw*i/(n-1)
    ys=lambda v: y0+h-(v-ymin)/(ymax-ymin)*h
    for t in ticks:
        out.append(f'<line x1="{ML}" y1="{ys(t):.1f}" x2="{ML+pw}" y2="{ys(t):.1f}" stroke="{GRID}" stroke-width="1"/>')
        text(ML-8,ys(t)+4,fmt(t),11,MUTED,'end',extra='style="font-variant-numeric:tabular-nums"')
    out.append(f'<line x1="{ML}" y1="{y0+h:.1f}" x2="{ML+pw}" y2="{y0+h:.1f}" stroke="{AXIS}" stroke-width="1"/>')
    for i in range(0,n,3): text(xs(i),y0+h+15,L[i],11,MUTED,'middle')
    ends=[]
    for name,col,vals in series:
        pts=[(xs(i),ys(v)) for i,v in enumerate(vals) if v is not None]
        path='M'+' L'.join(f'{x:.1f},{y:.1f}' for x,y in pts)
        out.append(f'<path d="{path}" fill="none" stroke="{col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        x,y=pts[-1]; out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{col}" stroke="{SURF}" stroke-width="2"/>')
        ends.append([y,name,col,fmt(vals[-1])+unit])
    # spread end labels with leader lines
    ends.sort(key=lambda e:e[0]); ly=[e[0] for e in ends]
    for i in range(1,len(ly)): ly[i]=max(ly[i],ly[i-1]+15)
    shift=max(0,ly[-1]-(y0+h)); ly=[v-shift for v in ly]
    for i in range(len(ly)-2,-1,-1): ly[i]=min(ly[i],ly[i+1]-15)
    for (y,name,col,val),yy in zip(ends,ly):
        x=xs(n-1)
        out.append(f'<line x1="{x+6:.1f}" y1="{y:.1f}" x2="{x+16:.1f}" y2="{yy:.1f}" stroke="{AXIS}" stroke-width="1"/>')
        out.append(f'<rect x="{x+18:.1f}" y="{yy-5:.1f}" width="10" height="10" rx="2" fill="{col}"/>')
        text(x+32,yy+4,f'{name} {val}',11,INK)
    # legend row
    lx=ML
    for name,col,_ in series:
        out.append(f'<rect x="{lx}" y="{y0-5}" width="10" height="10" rx="2" fill="{col}"/>'); text(lx+14,y0+4,name,11,INK2); lx+=14+len(name)*6.4+16
    return y0+h+34
y=MT
text(ML,20,'Trend paper book (daily, TV 0.40, $1,000) vs its model and the close-to-close backtest, 8-26 Oct 2026',14,INK,weight=600)
y+=22
y=line_panel(y,230,'Equity, USD','paper at Delta mids 00:05 UTC; model = unrounded weights at 7.31 bps; backtest = trend_backtest.py, whole contracts, rebased 9 Oct',
    [('paper book',BLUE,d['paper']),('model',ORANGE,d['model']),('backtest $1k',AQUA,d['backtest'])],988,1022,[990,1000,1010,1020],lambda v:f'{v:,.2f}' if v%1 else f'{v:,.0f}','')
y=line_panel(y+26,150,'Gross exposure, x equity','positions / equity after each rebalance; model = sum of unrounded weights; mean signal 1.00 (7 Oct) to 0.15 (25 Oct)',
    [('paper book',BLUE,d['gross']),('model',ORANGE,d['mgross'])],0,0.7,[0,0.2,0.4,0.6],lambda v:f'{v:.2f}x' if v!=int(v) or v==0 else f'{v:.1f}x','')
# panel C: per-coin bars
text(ML,y+14,'Price P&L per coin, USD (positions x mid changes, 8-26 Oct; sum -5.67; fees 0.86, slippage 0.17, funding 0.35 paid)',13,INK,weight=600)
y+=30
pc=sorted(d['percoin'].items(),key=lambda kv:-kv[1]); vmax=max(abs(v) for _,v in pc)
pw=W-ML-MR; bh=18; gap=6; x0=ML+pw/2
sc=(pw/2-60)/vmax
for i,(c,v) in enumerate(pc):
    yy=y+i*(bh+gap); x=x0+ (0 if v<0 else 0); w=abs(v)*sc; col=BLUE if v>=0 else RED
    if v>=0: out.append(f'<path d="M{x0:.1f},{yy:.1f} h{w-4:.1f} a4,4 0 0 1 4,4 v{bh-8} a4,4 0 0 1 -4,4 h{-(w-4):.1f} z" fill="{col}"/>')
    else: out.append(f'<path d="M{x0:.1f},{yy:.1f} h{-(w-4):.1f} a4,4 0 0 0 -4,4 v{bh-8} a4,4 0 0 0 4,4 h{w-4:.1f} z" fill="{col}"/>')
    text(x0-8 if v>=0 else x0+8,yy+bh/2+4,c,11,INK,'end' if v>=0 else 'start',weight=600)
    text(x0+w+8 if v>=0 else x0-w-8,yy+bh/2+4,f'{v:+.2f}',11,INK2,'start' if v>=0 else 'end',extra='style="font-variant-numeric:tabular-nums"')
hC=len(pc)*(bh+gap)
out.append(f'<line x1="{x0:.1f}" y1="{y-4}" x2="{x0:.1f}" y2="{y+hC}" stroke="{AXIS}" stroke-width="1"/>')
y+=hC+8
text(ML,y+6,'Source: daily_journal.jsonl (19 rebalances), Delta public candles fetched 26 Oct 17:40 UTC; scripts fidelity1/2.py, chart_data.py. Paper only, no orders.',10,MUTED)
H=y+16
html=f'''<!doctype html><html><head><meta charset="utf-8"><title>Trend paper fidelity</title>
<style>body{{margin:0;background:#f9f9f7;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}}#c{{width:{W}px;background:{SURF};padding:8px 0}}</style></head>
<body><div id="c"><svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,-apple-system,'Segoe UI',sans-serif">
{chr(10).join(out)}
</svg></div></body></html>'''
open('trend_fidelity_chart.html','w').write(html)
print('html ok',W,H)
