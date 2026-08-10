#!/usr/bin/env python3
"""Standing ride chart: power + HR + glucose overlay (+ elevation profile).
Usage: python3 scripts/plot_ride.py --date 2026-08-06 --strava-id 19630090461 --start 08:44
Fetches per-second streams from Strava REST (refreshes the token automatically),
overlays the CGM archive. Writes charts/{date}_ride_power_hr_glucose.png
"""
import argparse,csv,json,os,subprocess,sys,time
import numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG=os.path.expanduser('~/.config/strava-mcp/config.json')
BG='#0d1220';CARD='#161f31';TX='#e8edf7';MUT='#94a2be';GRID='#26324a'
PW='#4f8cff';HRC='#ff6fae';GL='#2fd4c6';WARN='#e6a23c';BAD='#ff5d5d'
plt.rcParams.update({'figure.facecolor':BG,'axes.facecolor':CARD,'savefig.facecolor':BG,
 'text.color':TX,'axes.labelcolor':TX,'xtick.color':MUT,'ytick.color':MUT,
 'axes.edgecolor':GRID,'grid.color':GRID,'font.size':10})

def token():
    """Strava MCP is not registered; use the stored creds + curl (urllib TLS fails here)."""
    c=json.load(open(CFG))
    if c['expiresAt']<time.time()+120:
        o=subprocess.run(['curl','-s','-X','POST','https://www.strava.com/oauth/token',
          '-d',f"client_id={c['clientId']}",'-d',f"client_secret={c['clientSecret']}",
          '-d','grant_type=refresh_token','-d',f"refresh_token={c['refreshToken']}"],
          capture_output=True,text=True).stdout
        d=json.loads(o)
        if 'access_token' not in d: sys.exit('strava refresh failed: '+o[:200])
        c.update(accessToken=d['access_token'],refreshToken=d['refresh_token'],expiresAt=d['expires_at'])
        json.dump(c,open(CFG,'w'),indent=2)
    return c['accessToken']

def smooth(a,w):
    a=np.nan_to_num(np.array(a,dtype=float)); return np.convolve(a,np.ones(w)/w,mode='same')

ap=argparse.ArgumentParser()
ap.add_argument('--date',required=True); ap.add_argument('--strava-id',required=True)
ap.add_argument('--start',required=True,help='local HH:MM of ride start')
ap.add_argument('--ftp',type=float,default=273)
a=ap.parse_args(); D=a.date
hh,mm=a.start.split(':'); START=int(hh)*3600+int(mm)*60

tok=token()
raw=subprocess.run(['curl','-s','-H',f'Authorization: Bearer {tok}',
  f'https://www.strava.com/api/v3/activities/{a.strava_id}/streams'
  '?keys=time,watts,heartrate,altitude&key_by_type=true'],capture_output=True,text=True).stdout
d=json.loads(raw)
if 'time' not in d: sys.exit('no streams: '+raw[:200])
t=np.array(d['time']['data']); clock=(START+t)/3600.
w=np.array([x or 0 for x in d['watts']['data']],dtype=float)
h=np.array([x if x else np.nan for x in d['heartrate']['data']],dtype=float)
alt=np.array([x if x else np.nan for x in d.get('altitude',{}).get('data',[np.nan]*len(t))],dtype=float)

gp=os.path.join(ROOT,'metrics','glucose_raw.csv')
g=[r for r in csv.DictReader(open(gp))] if os.path.exists(gp) else []
lo_x,hi_x=clock[0]-.75,clock[-1]+.9
gt=[];gv=[]
for r in [x for x in g if x['local_date']==D]:
    H,M=r['local_time'].split(':'); c=int(H)+int(M)/60
    if lo_x<=c<=hi_x: gt.append(c); gv.append(int(r['mg_dl']))

fig,(axE,ax)=plt.subplots(2,1,figsize=(14,8.5),height_ratios=[1,4],sharex=True)
ride=next((r for r in csv.DictReader(open(os.path.join(ROOT,'metrics','rides.csv')))
           if r['date']==D),{}) if os.path.exists(os.path.join(ROOT,'metrics','rides.csv')) else {}
sub=f"IF {ride.get('if_','?')} · NP {ride.get('np_w','?')} W · TSS {ride.get('tss','?')} · TE {ride.get('te_aerobic','?')}" if ride else ''
fig.suptitle(f"Ride — {D} · {ride.get('name','')} · {ride.get('dist_mi','?')} mi / {ride.get('gain_ft','?')} ft",
             fontsize=15,fontweight='bold',y=.97,color=TX)
axE.set_title(sub,fontsize=10.5,color=MUT,pad=6)
if not np.all(np.isnan(alt)):
    axE.fill_between(clock,alt,np.nanmin(alt),color=MUT,alpha=.18,lw=0)
    axE.plot(clock,alt,color=MUT,lw=.8)
axE.set_ylabel('elev\n(m)',fontsize=9); axE.grid(alpha=.25); axE.tick_params(labelbottom=False)

ax.fill_between(clock,smooth(w,30),0,color=PW,alpha=.18,lw=0)
ax.plot(clock,smooth(w,30),color=PW,lw=1.3)
ax.axhline(a.ftp,color=PW,ls=':',lw=1.2,alpha=.75)
ax.text(lo_x+.05,a.ftp+10,f'FTP {a.ftp:.0f} W',color=PW,fontsize=8.5)
ax.set_ylabel('Power (W)',color=PW); ax.set_ylim(0,max(620,np.nanmax(smooth(w,30))*1.25)); ax.grid(alpha=.25)
axH=ax.twinx(); axH.plot(clock,smooth(h,20),color=HRC,lw=1.5)
axH.set_ylabel('HR (bpm)',color=HRC); axH.set_ylim(55,200)
axG=ax.twinx(); axG.spines['right'].set_position(('outward',52))
axG.set_ylabel('Glucose (mg/dL)',color=GL); axG.set_ylim(55,150)
if gt:
    axG.plot(gt,gv,color=GL,lw=3,marker='o',ms=5,zorder=6)
    axG.axhspan(55,70,color=BAD,alpha=.16,zorder=0)
    axG.axhline(70,color=BAD,ls='--',lw=1.2,alpha=.8)
    axG.text(lo_x+.05,72,'hypoglycaemia < 70',color=BAD,fontsize=9,fontweight='bold')
    low=[(x,y) for x,y in zip(gt,gv) if y<70]
    if low:
        axG.scatter([x for x,_ in low],[y for _,y in low],s=130,facecolor='none',
                    edgecolor=BAD,lw=2.2,zorder=7)
        mn=min(y for _,y in low)
        axG.annotate(f'nadir {mn} mg/dL · {len(low)*5} min <70',
            xy=low[len(low)//2],xytext=(low[len(low)//2][0]+.55,62),color=BAD,
            fontsize=9.5,fontweight='bold',arrowprops=dict(arrowstyle='->',color=BAD,lw=1.6))
else:
    axG.text((lo_x+hi_x)/2,100,'NO CGM DATA FOR THIS RIDE',color=BAD,fontsize=13,
             ha='center',fontweight='bold')
ax.axvspan(clock[0],clock[-1],color=WARN,alpha=.05,zorder=0)
ax.set_xlim(lo_x,hi_x); ax.set_xlabel('Time of day')
tk=np.arange(np.floor(lo_x*2)/2,hi_x,.5); ax.set_xticks(tk)
ax.set_xticklabels([f'{int(v):02d}:{int((v%1)*60):02d}' for v in tk])
ax.legend(handles=[plt.Line2D([],[],color=PW,lw=2.5,label='Power (30 s avg)'),
                   plt.Line2D([],[],color=HRC,lw=2.5,label='Heart rate'),
                   plt.Line2D([],[],color=GL,lw=2.5,marker='o',label='Glucose')],
          loc='upper left',facecolor=CARD,edgecolor=GRID,labelcolor=TX,fontsize=9.5)
fig.tight_layout(rect=[0,0.01,1,0.95])
out=os.path.join(ROOT,'charts',f'{D}_ride_power_hr_glucose.png')
fig.savefig(out,dpi=145); print('✅',out)
