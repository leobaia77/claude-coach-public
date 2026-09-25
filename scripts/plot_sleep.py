#!/usr/bin/env python3
"""Standing sleep chart: HR + sleep stage + glucose overlay.
Usage: python3 scripts/plot_sleep.py --date 2026-08-06 [--hr "0:68.5,66,70;1:62.8,60,66;..."]
Reads metrics/sleep_intervals.csv, metrics/sleep_daily.csv, metrics/glucose_raw.csv.
Writes charts/{date}_sleep_hr_stage_glucose.png
"""
import argparse, csv, os, sys
import numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG='#0d1220';CARD='#161f31';TX='#e8edf7';MUT='#94a2be';GRID='#26324a'
HRC='#ff6fae';GL='#2fd4c6';WARN='#e6a23c';BAD='#ff5d5d'
plt.rcParams.update({'figure.facecolor':BG,'axes.facecolor':CARD,'savefig.facecolor':BG,
 'text.color':TX,'axes.labelcolor':TX,'xtick.color':MUT,'ytick.color':MUT,
 'axes.edgecolor':GRID,'grid.color':GRID,'font.size':10})

def rd(p):
    p=os.path.join(ROOT,p)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []

def prev_day(d):
    from datetime import date, timedelta
    return (date.fromisoformat(d)-timedelta(days=1)).isoformat()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--date',required=True)
    ap.add_argument('--hr',default='',help='hour:mean,min,max;… overnight HR (from Oura via Nori)')
    a=ap.parse_args(); D=a.date
    st=[r for r in rd('metrics/sleep_intervals.csv') if r['night']==D]
    if not st: sys.exit(f'no sleep_intervals rows for {D} — pull Oura first')
    daily=next((r for r in rd('metrics/sleep_daily.csv') if r['date']==D),{})
    def hc(t,d):
        hh,mm=t.split(':'); c=int(hh)+int(mm)/60
        return c-24 if d<D else c
    sx=[hc(r['local_time'],r['local_date']) for r in st]
    smap={'DEEP':0,'CORE':1,'REM':2,'AWAKE':3}; sv=[smap[r['state']] for r in st]
    x0=min(sx)-.2; x1=max(sx)+.2
    # Glucose and HR must land on the SAME continuous axis as the stages: a night
    # labelled D can start before midnight (rows dated D-1) and end well after 08:00.
    # Loading only local_date==D and clipping at 08:00 silently dropped both ends and
    # painted a bogus "CGM GAP" over data we actually had (found 2026-08-16).
    gt=[];gv=[]
    for r in rd('metrics/glucose_raw.csv'):
        if r['local_date'] not in (D,prev_day(D)): continue
        hh,mm=r['local_time'].split(':'); c=hc(f'{hh}:{mm}',r['local_date'])
        if x0<=c<=x1: gt.append(c); gv.append(int(r['mg_dl']))
    order=sorted(range(len(gt)),key=lambda i:gt[i])
    gt=[gt[i] for i in order]; gv=[gv[i] for i in order]
    hrh={}
    for blk in [b for b in a.hr.split(';') if b]:
        k,v=blk.split(':'); m,lo,hi=[float(x) for x in v.split(',')]
        h=int(k)
        if h>=18: h-=24         # 6 PM sleep-day boundary: evening hours belong before midnight
        hrh[h]=(m,lo,hi)

    fig,(axS,ax)=plt.subplots(2,1,figsize=(14,7.5),height_ratios=[1.15,3],sharex=True)
    t=f"Sleep — night of {D}"
    if daily: t+=f" · {daily.get('sleep_h','?')}h · {daily.get('eff','?')}% eff · HRV {daily.get('hrv','?')}"
    fig.suptitle(t,fontsize=15,fontweight='bold',y=.97,color=TX)
    cols={0:'#4f8cff',1:'#3a5a8c',2:'#9b7dff',3:'#e6a23c'}
    sm=[int(r['minutes']) for r in st]
    for i in range(len(sx)): axS.axvspan(sx[i],sx[i]+sm[i]/60,color=cols[sv[i]],alpha=.85,lw=0)
    axS.set_yticks([]); axS.set_ylabel('Sleep\nstage',fontsize=9)
    c={s:sum(int(r['minutes']) for r in st if r['state']==s) for s in ('DEEP','CORE','REM','AWAKE')}
    axS.set_title(f"DEEP {c['DEEP']}m · CORE {c['CORE']}m · REM {c['REM']}m · AWAKE {c['AWAKE']}m",
                  fontsize=10.5,color=MUT,pad=6)
    axS.legend(handles=[Patch(color=cols[i],label=l) for i,l in
               enumerate(['Deep','Core','REM','Awake'])],ncol=4,loc='upper right',
               facecolor=CARD,edgecolor=GRID,labelcolor=TX,fontsize=9)
    if hrh:
        hx=sorted(hrh); hm=[hrh[k][0] for k in hx]
        ax.fill_between(hx,[hrh[k][1] for k in hx],[hrh[k][2] for k in hx],color=HRC,alpha=.18,lw=0)
        ax.plot(hx,hm,color=HRC,lw=2.2,marker='o',ms=5)
        ax.annotate(f'nadir {min(hm):.0f} bpm',xy=(hx[hm.index(min(hm))],min(hm)),
                    xytext=(hx[hm.index(min(hm))]+.4,min(hm)-3),color=HRC,fontsize=9,
                    arrowprops=dict(arrowstyle='->',color=HRC))
    else:
        # Hourly HR can be unavailable (connector falling back to daily aggregation).
        # Leaving the axis live paints a bogus 0-1 scale, so blank it and say so.
        ax.set_yticks([]); ax.spines['left'].set_visible(False)
        ax.text(.5,.06,'hourly HR unavailable for this night',transform=ax.transAxes,
                color=MUT,fontsize=9,ha='center',style='italic')
    ax.set_ylabel('HR (bpm)' if hrh else '',color=HRC); ax.grid(alpha=.25)
    ax.set_xlabel('Time of night')
    axG=ax.twinx(); axG.set_ylabel('Glucose (mg/dL)',color=GL)
    # Data-driven floor: a hardcoded 60 clipped the 53-57 readings on 8/25 - i.e. it hid
    # exactly the values worth looking at. Never let the axis crop a hypo.
    g_lo=min(55,min(gv)-5) if gv else 60
    g_hi=max(135,max(gv)+5) if gv else 135
    axG.set_ylim(g_lo,g_hi)
    if gt:
        axG.plot(gt,gv,color=GL,lw=2.6,marker='o',ms=4)
        axG.axhspan(g_lo,80,color=WARN,alpha=.10,zorder=0)
        axG.axhspan(g_lo,70,color=BAD,alpha=.13,zorder=0)
        axG.axhline(70,color=BAD,ls='--',lw=1,alpha=.8)
        axG.text(x1,70.6,'< 70 mg/dL',color=BAD,fontsize=9,ha='right')
        axG.axhline(80,color=WARN,ls='--',lw=1,alpha=.7)
        axG.text(x1,81,'< 80 mg/dL',color=WARN,fontsize=9,ha='right')
        gap_end=min(gt)
        if gap_end>x0+.3:
            axG.axvspan(x0,gap_end,facecolor='none',edgecolor=BAD,hatch='///',lw=0,alpha=.30,zorder=0)
            axG.text((x0+gap_end)/2,124,'CGM GAP — glucose only (HR unaffected)',
                     color=BAD,fontsize=9.5,ha='center',fontweight='bold')
        lo=[(t_,v) for t_,v in zip(gt,gv) if v<70]
        if lo: axG.scatter([t_ for t_,_ in lo],[v for _,v in lo],s=120,facecolor='none',
                           edgecolor=BAD,lw=2,zorder=7)
    else:
        axG.text((x0+x1)/2,100,'NO CGM DATA FOR THIS NIGHT',color=BAD,fontsize=13,
                 ha='center',fontweight='bold')
    ax.set_xlim(x0,x1)
    tk=np.arange(np.ceil(x0),x1,1); ax.set_xticks(tk)
    ax.set_xticklabels([f'{int(v)%24:02d}:00' for v in tk])
    lg=([plt.Line2D([],[],color=HRC,lw=2.5,marker='o',label='HR (hourly, min–max)')] if hrh else []) \
       +[plt.Line2D([],[],color=GL,lw=2.5,marker='o',label='Glucose')]
    ax.legend(handles=lg,
              loc='upper left',facecolor=CARD,edgecolor=GRID,labelcolor=TX,fontsize=9.5)
    fig.tight_layout(rect=[0,0.01,1,0.95])
    out=os.path.join(ROOT,'charts',f'{D}_sleep_hr_stage_glucose.png')
    fig.savefig(out,dpi=145); print('✅',out)
main()
