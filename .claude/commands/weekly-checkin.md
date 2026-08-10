Run the weekly coaching check-in and planning cycle. This is the core coaching loop.

## BEFORE STARTING

Read `~/.coach_memory/wiki.md` in full. If the file doesn't exist, stop and tell the athlete to run `/coach-setup` first.

Note from the wiki:
- Athlete's HRV baseline
- Current training block and goals
- Private calendar ID
- Slack user ID and email
- Current working weights
- Last week's planned sessions
- Stored HR + power zones (Section 4) — needed to detect zone changes during this week's Garmin pull

---

## STEP 1 — PULL THIS WEEK'S DATA (run in parallel)

### Nori — Biometrics (last 7 days)
Pull:
- HRV (daily morning readings)
- Resting HR
- Sleep duration and quality scores
- Body weight
- Active energy / calories burned
- VO2max (if updated)

### Hevy — Strength Sessions (last 7 days)
Pull all workouts. For each: date, exercises, sets × reps × weight, RPE (if logged).

### Garmin Connect — Cardio / Sport Sessions (last 7 days)
**Primary cardio source.** Garmin owns all ride/run metrics — duration, distance, HR, power, training effect, training load, performance metrics, L/R balance.
- Call `query_activities` for the last 7 days — capture every activity (type, name, duration, distance, elevation, avg/max HR, training effect, training load).
- For each session ≥30 min OR named/marked as a workout/race/interval/threshold session, call `get_activity_details` to pull the FULL metric set: power suite (avg, NP, max, kJ, IF, TSS, VI, peak-power curve, L/R balance, torque effectiveness, pedal smoothness when available), HR (avg, max, Pw:HR decoupling first vs second half, time-in-zones), cadence (avg, max, % in target band), speed/elevation/max gradient, temperature.
- **Run the WORKOUT EVALUATION PROTOCOL from CLAUDE.md on every session ≥30 min.** Write 2–3 strengths and 2–3 specific points to improve per activity. Save into Coach AI Notes (Section 12) with the activity date so trends are visible week over week.
- Call `get_performance_metrics` and `analyze_training_period` for the weekly load trend (CTL/ATL/TSB if available, VO2max change, fitness/freshness trajectory).
- If the wiki's stored zones are >4 weeks old, call `get_user_profile` to check for a new threshold test logged on the device. Update wiki Section 4 if zones changed.

**Strava — DO NOT pull weekly activities.** Strava is segments-only. Only call Strava tools (`explore-segments`, `list-starred-segments`, etc.) if the athlete asks about a specific segment or route during the check-in.

**Fallback (Garmin Connect unavailable):** pull cardio sessions from Nori — type, duration, distance, elevation, avg HR. Note in Coach AI Notes that Garmin is offline so the granular evaluation protocol cannot run; tag all rides this week as "ungraded" until Garmin is back.

### BodySpec — DEXA (check for new scan)
Pull scan results. Note if a new scan has been added since last check.

---

## STEP 2 — ANALYZE

**Biometrics analysis:**
- Compare each day's HRV to athlete's baseline
- Flag any days with >15% HRV drop (elevated fatigue)
- Flag any days with >25% HRV drop (caution — reduce load)
- Note sleep trend — was sleep adequate? Any nights <6h?
- Weight trend — direction, any large spikes (retention vs. real change)?

**Training load analysis:**
- Were planned sessions completed? Any skipped?
- Strength: are working weights progressing? Any PRs?
- Endurance: total volume for the week (hours, km/miles, elevation)
- Intensity distribution: mostly easy or did hard days stack up?
- Recovery between hard sessions — was there enough space?

**Recovery assessment:**
- Overall: Well recovered / Partially recovered / Under-recovered
- Flag any signals that should influence next week (e.g. lingering fatigue, plateau)

---

## STEP 3 — SEND CHECK-IN MESSAGE

Send simultaneously:
1. **Slack DM** to athlete's Slack user ID (from wiki)
2. **Gmail** to athlete's email (from wiki)

### Slack message (plain text only — no tables, no pipes):
Keep it short. Include:
- Brief summary of the week's data highlights (2–3 bullets, plain text)
- 5–6 check-in questions as a numbered list
- Ask them to reply when they have a moment

Questions to ask (adapt to what the data shows):
1. How does your body feel overall — energy, heaviness, freshness?
2. Any pain, soreness, or injuries to flag?
3. Sleep quality this week — how did it feel subjectively?
4. Motivation and mental state?
5. Any races, events, or schedule constraints coming up?
6. Anything about last week's plan you'd like to change?

### Gmail (HTML formatted):
Subject: `Weekly Training Review — Week of [DATE RANGE]`

Include:
- Biometrics table (HRV, RHR, sleep, weight per day)
- Workout summary (sessions completed, key lifts, sport sessions)
- Coach observations (2–3 key insights)
- Same check-in questions
- Preview of what next week will look like (pending their feedback)

---

## STEP 4 — WAIT FOR ATHLETE RESPONSE

Tell the athlete you're waiting for their check-in answers before finalizing next week's plan. Do not create calendar events yet.

When they respond, continue to Step 5.

---

## STEP 5 — PROCESS FEEDBACK & ADJUST PLAN

Incorporate subjective feedback:
- Pain reported → modify sessions (remove loading, substitute exercises, add rest)
- Low energy + low HRV → reduce intensity, protect easy sessions
- High motivation + good HRV → can push harder or add volume
- Schedule constraints → reschedule sessions accordingly
- Race/event upcoming → start taper protocol if within 2 weeks

---

## STEP 6 — PROPOSE NEXT WEEK

Drive the plan from this week's WORKOUT EVALUATION PROTOCOL output, not from a default template. Inputs in priority order:
1. **Points to improve** from each ride's evaluation (see Coach AI Notes for this week) — pick session types using the protocol's *evaluation → next week's plan* table in CLAUDE.md.
2. **Recovery signals** (HRV trend, sleep, subjective feedback) — apply the HRV action ladder from CLAUDE.md.
3. **Goals** (from wiki) and current training block.
4. **Progressive overload** — strength +2.5–5% if RPE ≤8 last week; endurance +5–10% only if aerobic efficiency held or improved.

Layer the baseline structure (3–4 strength, 2–3 sport, 1 long, 1–2 rest) underneath the targeted-session selections.

Apply the protocol's *evaluation → diet adjustments* table to each day based on its prescribed workout AND the recovery signal from the prior week. Adjust the per-day macros from Section 6 of the wiki accordingly.

Format the proposal clearly:
- Day by day: session type, duration, key targets, the SPECIFIC weakness it addresses (e.g. "Tue cadence-focused Z2 — targets the <80 rpm pattern from this week's rides")
- Day by day: nutrition adjustments vs baseline targets (e.g. "+60g carbs post-ride", "−40g carbs on Thu rest day")
- Note any changes from the default template and why
- Highlight the weekend long session

Ask the athlete to confirm or request changes before creating calendar events.

---

## STEP 7 — CREATE CALENDAR EVENTS + PUSH WORKOUTS TO GARMIN

### 7a. Google Calendar events

Once the athlete confirms the plan, create all events on the private training calendar (ID from wiki — NEVER on work/primary calendar).

Every event MUST include:
- Full workout details (exercises, sets, zones, duration)
- The complete nutrition section with:
  - Day type and calorie/macro targets
  - Full timestamped meal plan with gram weights and per-meal macros
  - Pre and post-workout meals called out specifically
  - Day total
  - Tips with effort-based adjustment callouts (⚡)

Follow the CALENDAR EVENT FORMAT from CLAUDE.md exactly.

Create all events in parallel for efficiency.

### 7b. Garmin structured-workout push (cardio sessions only)

For every cardio session in next week's plan that has a structured target (intervals, tempo, threshold, base — anything with HR / power / cadence prescriptions):
1. Build the Garmin workout JSON (warmup + main steps with primary HR or power target and secondary cadence target where useful + cooldown). See CLAUDE.md ENDURANCE TRAINING PRINCIPLES for the exact two-step contract.
2. `manage_workouts` `action=upload` with the JSON → record the returned `workoutId`.
3. `manage_workouts` `action=schedule` with `workout_id` and `date=YYYY-MM-DD` → record the returned `workoutScheduleId`.
4. Store both IDs in the wiki Section 9 (Current Week Plan) alongside the day so an unschedule is one call away.

Strength sessions and unstructured easy rides are calendar-only — no Garmin push.

Pure-cycling rides should also get a route suggestion from Strava (`explore-segments` / `list-starred-segments`) only if the athlete asked for one; otherwise leave route open.

---

## STEP 8 — UPDATE WIKI

Add to the wiki:
- New weekly log entry (Section 8) with biometrics table and check-in summary
- **Per-activity evaluation:** for every ride ≥30 min this week, append to Coach AI Notes (Section 12) the 2–3 strengths and 2–3 points to improve identified by the WORKOUT EVALUATION PROTOCOL, dated to the activity. Track trends week-over-week (L/R asymmetry, Pw:HR decoupling, cadence consistency, power durability, climbing W/kg).
- Update current week plan (Section 9) with the new week. For each cardio day with a Garmin-pushed structured workout, include the `workoutId` and `workoutScheduleId` for traceability.
- Update communication log (Section 10)
- Update working weights if PRs were set
- Update any baseline changes (HRV, weight trend, zones if Garmin showed a new threshold test)
- Note any injuries or modifications in Coach AI Notes (Section 12) — separately from the per-activity evaluations.

---

## STEP 9 — CLOSE THE LOOP

Send a brief Slack DM confirming:
- Calendar events created ✅
- Link to the first event (or describe the week)
- One coaching note or focus for the week
- Reminder to run `/weekly-checkin` again same day next week — the cycle is **manual**, there is no auto-trigger; suggest they set a recurring calendar reminder

Weekly check-in complete.
