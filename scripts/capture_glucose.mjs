#!/usr/bin/env node
/**
 * NIGHTLY GLUCOSE CAPTURE
 *
 * WHY THIS EXISTS: the LibreLinkUp API only retains ~12 hours of history regardless of
 * what you request. Overnight glucose is therefore LOST unless it is pulled the same
 * morning. This script runs daily, pulls the rolling window, and appends to a permanent
 * local archive so overnight-vs-sleep correlations can be built up over time.
 *
 * Usage:  node scripts/capture_glucose.mjs [--hours 14] [--quiet]
 * Output: metrics/glucose_raw.csv        (every reading, deduped by timestamp)
 *         metrics/glucose_overnight.csv  (one summary row per night)
 */
import { spawn } from 'child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
// Path to the built librelink-mcp-server entrypoint. Override with LIBRELINK_MCP_PATH
// if you cloned it somewhere other than ~/projects/librelink-mcp-server.
const MCP = process.env.LIBRELINK_MCP_PATH
  || join(process.env.HOME || '', 'projects', 'librelink-mcp-server', 'dist', 'index.js');
const RAW  = join(ROOT, 'metrics', 'glucose_raw.csv');
const NIGHT= join(ROOT, 'metrics', 'glucose_overnight.csv');
const args = process.argv.slice(2);
const HOURS = Number(args[args.indexOf('--hours') + 1]) || 14;
const QUIET = args.includes('--quiet');
const log = (...a) => { if (!QUIET) console.log(...a); };

// sleep window used for the overnight summary (local hours)
const SLEEP_START = 0;   // 00:00
const SLEEP_END   = 8;   // 08:00

function callMcp(tool, argsObj, waitMs = 9000) {
  return new Promise((resolve, reject) => {
    // FIX 2026-08-06: bare 'node' relied on PATH and failed under cron (spawn ENOENT),
    // silently losing every scheduled capture. process.execPath is the absolute path of
    // the node binary already running this script.
    const srv = spawn(process.execPath, [MCP], { stdio: ['pipe', 'pipe', 'pipe'] });
    let buf = ''; const res = [];
    const send = o => srv.stdin.write(JSON.stringify(o) + '\n');
    srv.stdout.on('data', d => {
      buf += d; let i;
      while ((i = buf.indexOf('\n')) >= 0) {
        const l = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
        if (l) { try { res.push(JSON.parse(l)); } catch {} }
      }
    });
    let stderr = ''; srv.stderr.on('data', d => stderr += d);
    send({ jsonrpc:'2.0', id:1, method:'initialize',
           params:{ protocolVersion:'2024-11-05', capabilities:{}, clientInfo:{name:'capture',version:'1'} }});
    setTimeout(() => {
      send({ jsonrpc:'2.0', method:'notifications/initialized' });
      send({ jsonrpc:'2.0', id:2, method:'tools/call', params:{ name:tool, arguments:argsObj }});
    }, 800);
    setTimeout(() => {
      srv.kill();
      const r = res.find(x => x.id === 2);
      if (!r) return reject(new Error('no MCP response. stderr: ' + stderr.slice(0, 400)));
      if (r.error) return reject(new Error(JSON.stringify(r.error).slice(0, 400)));
      try { resolve(JSON.parse(r.result.content[0].text)); }
      catch (e) { reject(new Error('unparseable: ' + r.result?.content?.[0]?.text?.slice(0,200))); }
    }, waitMs);
  });
}

const localParts = ts => {
  // en-CA gives YYYY-MM-DD; force the athlete's tz so cron TZ can't shift the night boundary
  const d = new Date(ts);
  const f = new Intl.DateTimeFormat('en-CA', { timeZone:'America/Los_Angeles', year:'numeric',
    month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false });
  const p = Object.fromEntries(f.formatToParts(d).map(x => [x.type, x.value]));
  return { date:`${p.year}-${p.month}-${p.day}`, hour:+p.hour, min:+p.minute };
};

function loadCsv(path) {
  if (!existsSync(path)) return { header: null, rows: [] };
  const lines = readFileSync(path, 'utf8').trim().split('\n');
  return { header: lines[0].split(','), rows: lines.slice(1).map(l => l.split(',')) };
}

(async () => {
  mkdirSync(join(ROOT, 'metrics'), { recursive: true });
  const d = await callMcp('get_glucose_history', { hours: HOURS });
  const readings = d.readings || [];
  log(`pulled ${readings.length} readings (requested ${HOURS}h — API caps ~12h)`);
  if (!readings.length) { console.error('NO READINGS — sensor offline or auth failed'); process.exit(1); }

  // ---- 1. append to the permanent raw archive, deduped ----
  const existing = loadCsv(RAW);
  const seen = new Set(existing.rows.map(r => r[0]));
  const fresh = readings.filter(r => !seen.has(r.timestamp))
    .map(r => { const L = localParts(r.timestamp);
      return [r.timestamp, L.date, String(L.hour).padStart(2,'0')+':'+String(L.min).padStart(2,'0'),
              r.value, r.trend || ''].join(','); });
  const header = 'timestamp_utc,local_date,local_time,mg_dl,trend';
  const allRows = existing.rows.map(r => r.join(',')).concat(fresh).sort();
  writeFileSync(RAW, header + '\n' + allRows.join('\n') + '\n');
  log(`archive: +${fresh.length} new  → ${allRows.length} total rows`);

  // ---- 2. summarise the most recent complete night ----
  const byNight = {};
  for (const r of readings) {
    const L = localParts(r.timestamp);
    if (L.hour >= SLEEP_END && L.hour < 20) continue;         // daytime — skip
    // attribute 20:00-23:59 to the NEXT calendar date so a night is one bucket
    let night = L.date;
    if (L.hour >= 20) { const dt = new Date(L.date + 'T12:00:00'); dt.setDate(dt.getDate()+1);
                        night = dt.toISOString().slice(0,10); }
    (byNight[night] ||= []).push({ ...L, v: r.value, ts: r.timestamp });
  }
  const nights = Object.keys(byNight).sort();
  const target = nights[nights.length - 1];
  const pts = (byNight[target] || []).filter(p => p.hour >= SLEEP_START && p.hour < SLEEP_END)
                                     .sort((a,b) => a.ts.localeCompare(b.ts));
  if (pts.length < 12) { log(`night ${target}: only ${pts.length} in-window readings — not summarising`); process.exit(0); }

  const vals = pts.map(p => p.v);
  const mean = vals.reduce((a,b)=>a+b,0)/vals.length;
  const sd = Math.sqrt(vals.reduce((s,v)=>s+(v-mean)**2,0)/vals.length);
  const min = Math.min(...vals), max = Math.max(...vals);
  const nadir = pts.find(p => p.v === min);
  const first = vals[0], last = vals[vals.length-1];
  const below80 = vals.filter(v => v < 80).length * 5;   // 5-min sampling
  const below70 = vals.filter(v => v < 70).length * 5;
  // count distinct downward excursions >15 mg/dL
  let dips = 0, falling = false;
  for (let i = 1; i < vals.length; i++) {
    if (!falling && vals[i] < vals[i-1] - 3) falling = true;
    else if (falling && vals[i] > vals[i-1] + 3) { falling = false; dips++; }
  }
  const row = {
    night: target, n_readings: pts.length,
    mean: mean.toFixed(1), sd: sd.toFixed(1), cv_pct: (sd/mean*100).toFixed(1),
    min, max, range: max-min,
    nadir_time: nadir ? `${String(nadir.hour).padStart(2,'0')}:${String(nadir.min).padStart(2,'0')}` : '',
    at_sleep_onset: first, at_wake: last, dawn_rise: last - min,
    min_below_80: below80, min_below_70: below70, excursions: dips,
    // sleep columns left blank — filled in when the Oura connector is available
    sleep_h:'', deep_min:'', rem_min:'', efficiency:'', awakenings:'', hrv:''
  };
  const NHEAD = Object.keys(row).join(',');
  const ex = loadCsv(NIGHT);
  const keep = ex.rows.filter(r => r[0] !== target).map(r => r.join(','));
  writeFileSync(NIGHT, NHEAD + '\n' + keep.concat(Object.values(row).join(',')).sort().join('\n') + '\n');

  log(`\n=== NIGHT OF ${target} (${SLEEP_START}:00–${SLEEP_END}:00 local) ===`);
  log(`  readings ${row.n_readings} · mean ${row.mean} · SD ${row.sd} · CV ${row.cv_pct}%`);
  log(`  range ${row.min}–${row.max} (${row.range}) · nadir ${row.min} @ ${row.nadir_time}`);
  log(`  sleep-onset ${row.at_sleep_onset} → wake ${row.at_wake} · dawn rise +${row.dawn_rise}`);
  log(`  time <80: ${row.min_below_80} min · <70: ${row.min_below_70} min · excursions: ${row.excursions}`);
  log(`\n  archive: metrics/glucose_raw.csv · nightly: metrics/glucose_overnight.csv`);
})().catch(e => { console.error('CAPTURE FAILED:', e.message); process.exit(1); });
