#!/usr/bin/env python3
"""Matched climb-vs-climb comparison: 3-min power / HR / glucose vs climb progress.

Answers "did I fade, or did I run out of fuel?" by taking two climbs from one ride,
trimming both to the SAME duration, and normalising the x-axis to % of climb progress
so the two efforts overlay directly.

Usage:
  python3 scripts/plot_climb_compare.py --date 2026-08-23 --strava-id 19871148789 \
      --start 08:11 --climbs 1,5
Climb indices come from the auto-detected list printed with --list.
"""
import argparse, csv, json, os, subprocess, sys, time
import numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG  = os.path.expanduser('~/.config/strava-mcp/config.json')
BG,CARD,TX,MUT,GRID = '#0d1220','#161f31','#e8edf7','#94a2be','#26324a'
C1,C2,WARN,BAD = '#4f8cff','#ff9f43','#e6a23c','#ff5d5d'
plt.rcParams.update({'figure.facecolor':BG,'axes.facecolor':CARD,'savefig.facecolor':BG,
 'text.color':TX,'axes.labelcolor':TX,'xtick.color':MUT,'ytick.color':MUT,
 'axes.edgecolor':GRID,'grid.color':GRID,'font.size':10})
trapz = getattr(np,'trapezoid',None) or np.trapz

def token():
    """Strava MCP is unregistered; stored creds + curl (urllib TLS fails on this machine)."""
    c=json.load(open(CFG))
    if c['expiresAt'] < time.time()+120:
        o=subprocess.run(['curl','-s','-X','POST','https://www.strava.com/oauth/token',
          '-d',f"client_id={c['clientId']}",'-d',f"client_secret={c['clientSecret']}",
          '-d','grant_type=refresh_token','-d',f"refresh_token={c['refreshToken']}"],
          capture_output=True,text=True).stdout
        if not o.strip(): sys.exit('strava token refresh returned nothing')
        d=json.loads(o)
        if 'access_token' not in d: sys.exit('strava refresh failed: '+o[:200])
        c.update(accessToken=d['access_token'],refreshToken=d['refresh_token'],expiresAt=d['expires_at'])
        tmp=CFG+'.tmp'; json.dump(c,open(tmp,'w'),indent=2); os.replace(tmp,CFG)
    return c['accessToken']

def streams(sid):
    keys="time,watts,heartrate,cadence,altitude,distance,grade_smooth,temp"
    raw=subprocess.run(['curl','-s','-H',f'Authorization: Bearer {token()}',
      f'https://www.strava.com/api/v3/activities/{sid}/streams?keys={keys}&key_by_type=true'],
      capture_output=True,text=True).stdout
    if not raw.strip(): sys.exit('strava streams fetch returned nothing')
    d=json.loads(raw)
    if 'time' not in d: sys.exit('no streams: '+raw[:200])
    if not d.get('watts',{}).get('data'): sys.exit('no power stream — required')
    return d

def find_climbs(t,alt,g,dist,W,H,C,min_min=5,min_gain=80):
    gs=np.convolve(np.nan_to_num(g),np.ones(120)/120,mode='same')
    on=gs>=3.0; segs=[]; i=0
    while i<len(on):
        if on[i]:
            j=i
            while j<len(on) and on[j]: j+=1
            segs.append([i,j]); i=j
        else: i+=1
    merged=[]
    for s in segs:                                  # bridge short false flats
        if merged and t[s[0]]-t[merged[-1][1]-1] < 90: merged[-1][1]=s[1]
        else: merged.append(s)
    out=[]
    for a,b in merged:
        if t[b-1]-t[a] < min_min*60 or alt[b-1]-alt[a] < min_gain: continue
        out.append((a,b))
    return out

def NP(p):
    if len(p)<30: return float(p.mean())
    r=np.convolve(p,np.ones(30)/30,mode='valid'); return float((np.mean(r**4))**0.25)

def roll3(p):
    w=min(180,max(1,len(p)//4))
    return np.convolve(p,np.ones(w)/w,mode='same')

ap=argparse.ArgumentParser()
ap.add_argument('--date',required=True); ap.add_argument('--strava-id',required=True)
ap.add_argument('--start',required=True,help='local HH:MM of ride start')
ap.add_argument('--climbs',default='',help='1-based indices, e.g. 1,5')
ap.add_argument('--list',action='store_true')
ap.add_argument('--title',default='')
a=ap.parse_args()

d=streams(a.strava_id)
t=np.array(d['time']['data']); alt=np.array(d['altitude']['data'],float)
dist=np.array(d['distance']['data'],float)
W=np.array([x or 0 for x in d['watts']['data']],float)
H=np.array(d['heartrate']['data'],float)
C=np.array([x or 0 for x in d['cadence']['data']],float)
T=np.array(d['temp']['data'],float)
g=np.array(d.get('grade_smooth',{}).get('data',[0]*len(t)),float)
climbs=find_climbs(t,alt,g,dist,W,H,C)

if a.list or not a.climbs:
    print(f"{'#':<3}{'start':>8}{'dur':>8}{'km':>7}{'gain':>7}{'grade':>8}{'avgW':>7}{'HR':>5}{'rpm':>6}")
    for n,(i,j) in enumerate(climbs,1):
        km=(dist[j-1]-dist[i])/1000; gain=alt[j-1]-alt[i]; c=C[i:j]
        print(f"{n:<3}{t[i]/3600:>7.2f}h{(t[j-1]-t[i])/60:>7.1f}m{km:>7.2f}{gain:>7.0f}"
              f"{100*gain/(km*1000):>7.2f}%{W[i:j].mean():>7.0f}{H[i:j].mean():>5.0f}"
              f"{c[c>0].mean() if (c>0).any() else 0:>6.0f}")
    if not a.climbs: sys.exit(0)

i1,i2=[int(x)-1 for x in a.climbs.split(',')]
a1,_=climbs[i1]; a2,_=climbs[i2]
M=int(min(t[climbs[i1][1]-1]-t[a1], t[climbs[i2][1]-1]-t[a2]))

def blk(s):
    e=s+M; w,h,c,tp=W[s:e],H[s:e],C[s:e],T[s:e]; cm=c[c>0]
    km=(dist[e-1]-dist[s])/1000; gain=alt[e-1]-alt[s]
    return dict(w=w,h=h,c=c,avg=w.mean(),np=NP(w),hr=h.mean(),rpm=cm.mean(),
        torque=9.5493*w[c>0].mean()/cm.mean(),grade=100*gain/(km*1000),temp=tp.mean(),
        km=km,gain=gain,start=float(t[s]),kj=float(trapz(W[:s],t[:s])/1000))
b1,b2=blk(a1),blk(a2)

S=int(a.start[:2])*3600+int(a.start[3:5])*60
gl=sorted((int(r[2][:2])*3600+int(r[2][3:5])*60,int(r[3]))
          for r in csv.reader(open(os.path.join(ROOT,'metrics','glucose_raw.csv')))
          if len(r)>=5 and r[1]==a.date and r[3].isdigit())
def gseg(s):
    e=s+M
    v=[(sec,x) for sec,x in gl if S+t[s] <= sec <= S+t[e-1]]
    if not v: return None,None
    xs=[100*(sec-(S+t[s]))/M for sec,_ in v]; return xs,[x for _,x in v]

fig=plt.figure(figsize=(15,9.2))
gs=fig.add_gridspec(3,3,height_ratios=[.34,1,.9],hspace=.42,wspace=.28,
                    left=.06,right=.97,top=.90,bottom=.06)
fig.suptitle(a.title or f"Climb 1 vs Climb 2 — matched {M/60:.0f} min — {a.date}",
             fontsize=15,fontweight='bold',y=.965)

kpis=[("Matched average power",f"{b1['avg']:.0f} → {b2['avg']:.0f} W",
       f"{100*(b2['avg']-b1['avg'])/b1['avg']:+.0f}% on climb 2"),
      ("Crank torque",f"{b1['torque']:.1f} → {b2['torque']:.1f} Nm",
       f"cadence {b1['rpm']:.0f} → {b2['rpm']:.0f} rpm"),
      ("Before climb 2",f"{b2['kj']:,.0f} kJ",
       f"{b2['gain']+b1['gain']:.0f} m climbed · {b2['start']/3600:.2f} h elapsed")]
for k,(lab,big,sub) in enumerate(kpis):
    ax=fig.add_subplot(gs[0,k]); ax.axis('off')
    ax.add_patch(plt.Rectangle((0,0),1,1,transform=ax.transAxes,facecolor=CARD,
                 edgecolor=GRID,lw=1,zorder=0))
    ax.text(.05,.72,lab,transform=ax.transAxes,color=MUT,fontsize=10.5,va='center')
    ax.text(.05,.40,big,transform=ax.transAxes,color=TX,fontsize=20,fontweight='bold',va='center')
    ax.text(.05,.13,sub,transform=ax.transAxes,color=MUT,fontsize=9.5,va='center')

pct=np.linspace(0,100,M)
panels=[("Three-minute power",roll3(b1['w']),roll3(b2['w']),"Power (W)",None),
        ("Heart rate",b1['h'],b2['h'],"Heart rate (bpm)",None),
        ("Libre glucose",None,None,"Glucose (mg/dL)",'glucose')]
for k,(title,y1,y2,ylab,kind) in enumerate(panels):
    ax=fig.add_subplot(gs[1,k]); ax.set_title(title,color=TX,fontsize=11.5,pad=8)
    if kind=='glucose':
        x1,v1=gseg(a1); x2,v2=gseg(a2)
        if v1: ax.plot(x1,v1,color=C1,lw=2.4,marker='o',ms=5,label='Climb 1')
        if v2: ax.plot(x2,v2,color=C2,lw=2.4,marker='o',ms=5,label='Climb 2')
        ax.axhline(70,color=BAD,ls='--',lw=1,alpha=.8)
        ax.text(99,70.8,'< 70',color=BAD,fontsize=8.5,ha='right')
    else:
        ax.plot(pct,y1,color=C1,lw=2.2,label='Climb 1')
        ax.plot(pct,y2,color=C2,lw=2.2,label='Climb 2')
    ax.set_xlabel('Climb progress',color=MUT,fontsize=9.5); ax.set_ylabel(ylab,fontsize=9.5)
    ax.set_xlim(0,100); ax.grid(alpha=.25)
    ax.set_xticks([0,20,40,60,80,100]); ax.set_xticklabels(['0%','20%','40%','60%','80%','100%'])
    if k==0: ax.legend(facecolor=CARD,edgecolor=GRID,labelcolor=TX,fontsize=9.5,loc='lower right')

ax=fig.add_subplot(gs[2,:]); ax.axis('off')
rows=[('Average power',f"{b1['avg']:.0f} W",f"{b2['avg']:.0f} W",f"{100*(b2['avg']-b1['avg'])/b1['avg']:+.0f}%"),
      ('Normalized power',f"{b1['np']:.0f} W",f"{b2['np']:.0f} W",f"{100*(b2['np']-b1['np'])/b1['np']:+.0f}%"),
      ('Average heart rate',f"{b1['hr']:.0f} bpm",f"{b2['hr']:.0f} bpm",f"{100*(b2['hr']-b1['hr'])/b1['hr']:+.0f}%"),
      ('Pedalling cadence',f"{b1['rpm']:.1f} rpm",f"{b2['rpm']:.1f} rpm",f"{100*(b2['rpm']-b1['rpm'])/b1['rpm']:+.0f}%"),
      ('Crank torque',f"{b1['torque']:.1f} Nm",f"{b2['torque']:.1f} Nm",f"{100*(b2['torque']-b1['torque'])/b1['torque']:+.0f}%"),
      ('Pw:HR ratio',f"{b1['avg']/b1['hr']:.3f}",f"{b2['avg']/b2['hr']:.3f}",
       f"{100*((b2['avg']/b2['hr'])/(b1['avg']/b1['hr'])-1):+.1f}%"),
      ('Average grade',f"{b1['grade']:.2f}%",f"{b2['grade']:.2f}%",
       'easier' if b2['grade']<b1['grade'] else 'steeper'),
      ('Device temperature',f"{b1['temp']:.1f}°C",f"{b2['temp']:.1f}°C",f"{b2['temp']-b1['temp']:+.1f}°C")]
x1v,v1=gseg(a1); x2v,v2=gseg(a2)
if v1 and v2:
    rows.append(('Glucose, start → end',f"{v1[0]} → {v1[-1]} mg/dL",f"{v2[0]} → {v2[-1]} mg/dL",
                 f"min {min(v2)} on climb 2"))
ax.text(.02,1.02,f'Matched {M/60:.0f}-minute measure',transform=ax.transAxes,color=TX,
        fontsize=12.5,fontweight='bold',va='top')
for c,lab in ((.55,'Climb 1'),(.74,'Climb 2'),(.96,'Change')):
    ax.text(c,1.02,lab,transform=ax.transAxes,color=TX,fontsize=12.5,fontweight='bold',
            va='top',ha='right' if c==.96 else 'center')
for n,(lab,va,vb,ch) in enumerate(rows):
    y=.90-n*.112
    ax.axhline(y+.055,xmin=.02,xmax=.96,color=GRID,lw=.8)
    ax.text(.02,y,lab,transform=ax.transAxes,color=TX,fontsize=10.5,va='center')
    ax.text(.55,y,va,transform=ax.transAxes,color=MUT,fontsize=10.5,va='center',ha='center')
    ax.text(.74,y,vb,transform=ax.transAxes,color=MUT,fontsize=10.5,va='center',ha='center')
    col=TX
    if ch.startswith('+') and lab in('Average power','Normalized power','Pw:HR ratio'): col='#4ade80'
    if ch.startswith('-') and lab in('Average power','Normalized power','Pw:HR ratio'): col=BAD
    ax.text(.96,y,ch,transform=ax.transAxes,color=col,fontsize=10.5,va='center',ha='right',
            fontweight='bold')

out=os.path.join(ROOT,'charts',f'{a.date}_climb_compare.png')
plt.savefig(out,dpi=115,bbox_inches='tight'); print('✅',out)
