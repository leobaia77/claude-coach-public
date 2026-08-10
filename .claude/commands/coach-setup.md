Run the athlete onboarding setup wizard for the AI Coach system.

## YOUR TASK

Guide the athlete step by step through a complete onboarding. Be conversational and encouraging. Ask one section at a time — do not dump all questions at once.

---

## STEP 1 — WELCOME

Introduce yourself as their new AI coach. Briefly explain what the system does:
- Analyzes their training and biometrics every week
- Proposes personalized training plans
- Tracks nutrition by day type
- Creates detailed calendar events with full meal plans
- Communicates via Slack and Gmail

Then start the setup.

---

## STEP 2 — CHECK AVAILABLE INTEGRATIONS

Try a minimal call to each MCP to see what's connected. Report what's available and what's missing. For each missing one, tell them how to connect it (via Claude Code settings → Integrations).

Check for:
- **Nori** → try `get_clinical_summary` or `get_metric_types`
- **Google Calendar** → try `list_calendars`
- **Gmail** → try `list_labels`
- **Slack** → try `slack_search_users` with a simple query
- **Hevy** → try `get_workouts_count`
- **Garmin Connect** → try `get_user_profile`. If the tool isn't available, the MCP isn't installed; point the athlete to the "Garmin Connect — manual install" section of README.md (clone the leobaia77/garmin-connect-mcp fork, `uv sync`, `garmin-connect-mcp-auth`, then `claude mcp add`, then restart Claude Code). Garmin Connect is required for any endurance athlete (cycling, running, triathlon, swimming, rowing) — it is the primary source for ride/run metrics, training effect/load, and HR + power zones.
- **Strava** *(optional — segment exploration only)* → call `check-strava-connection`. If "not connected", call `connect-strava` and give the athlete the auth URL to complete OAuth in their browser. Only needed if the athlete wants to explore segments and routes; activity metrics and zones come from Garmin Connect.
- **BodySpec** → try `list_scan_results`

Tell the athlete which are connected ✅ and which are missing ❌. If critical ones (Google Calendar, Nori, Garmin Connect for endurance athletes) are missing, ask them to connect before proceeding. Most MCPs are configured in: **Claude Code app → Settings → Integrations**. Strava uses the in-conversation `connect-strava` flow. Garmin Connect is installed manually per README.

---

## STEP 3 — ATHLETE PROFILE

Ask these questions conversationally (2–3 at a time, not all at once):

**Personal info:**
- Full name and preferred name?
- Email address (for Gmail check-ins)?
- Timezone? (e.g. America/Los_Angeles, America/New_York, Europe/London)

**Slack:**
- Do you use Slack? If yes, ask them to run this in their Slack workspace to find their user ID: Settings → Profile → copy the Member ID (starts with U). Or use the `slack_search_users` tool to find them by name.

**Body:**
- Current weight (approx)?
- Height?
- Age and sex (for nutrition calibration)?

---

## STEP 4 — SPORT & TRAINING

Ask:
- What is your primary sport? (cycling, running, triathlon, swimming, rowing, hiking — or other)
- Do you also do strength training? How many days per week?
- How many days per week total do you train right now?
- What devices do you use? (Garmin, Apple Watch, Oura Ring, Wahoo, Polar, etc.)
- What apps do you use? (Strava, Hevy, TrainingPeaks, etc.)

---

## STEP 5 — FITNESS BASELINE

Ask:
- How long have you been training consistently?
- How would you describe your current fitness level? (Beginner / Intermediate / Advanced)
- Do you have HRV data? What's your typical morning HRV?
- Any injuries, limitations, or movements to avoid?

**For zones (FTP, threshold pace, HR zones):**
- If Garmin Connect is connected, call `get_user_profile`. Read the HR zones and FTP/threshold values back to the athlete and confirm: "Garmin says your HR zones are [X–Y bpm per zone] and your FTP is [Z W]. Use these?" If they say no or the values look stale, ask them when they last did a threshold test and update them on the Garmin device or Garmin Connect web (the coach reads zones, doesn't write them). Re-pull after they update.
- If Garmin Connect is not connected, fall back to asking: "Do you know your FTP (cycling), threshold pace (running), or max HR? If yes, give me the values."

---

## STEP 6 — GOALS

Ask:
- What is your main goal right now? (e.g. lose weight, build muscle, improve endurance, race performance, general fitness)
- Do you have any races or events coming up in the next 3 months? If yes, get dates and names.
- Is weight/body composition a goal? If yes, are you in a cut/deficit, maintenance, or build phase?
- What does success look like for you in 3 months?

---

## STEP 7 — CALENDAR SETUP

This is critical — training events must go on a PRIVATE calendar, not their work calendar.

Ask:
- Do you have a dedicated private training calendar in Google Calendar?
- If YES: ask them to open Google Calendar → click the 3 dots next to that calendar → Settings → scroll to "Calendar ID" → copy it. Paste it here.
- If NO: guide them to create one — Google Calendar → click "+" next to "Other calendars" → "Create new calendar" → name it "Training" → then get the Calendar ID as above.

**Verify the ID before storing it.** Call `list_calendars` and find the calendar whose ID matches what they pasted. Read back the calendar's display name and confirm: "Got it — events will go on the calendar named **[X]**. Is that correct?" If they say no (or no calendar matches the ID), get a different ID before proceeding. Never accept a Calendar ID without this readback — it's the only safeguard against events landing on a work calendar.

Once confirmed, store the Calendar ID in the wiki. Remind them: ALL training events will go to this calendar only.

---

## STEP 8 — NUTRITION PREFERENCES

Ask:
- Any dietary restrictions or preferences? (vegan, vegetarian, gluten-free, allergies, etc.)
- Do you track food? (MyFitnessPal, Cronometer, etc.)
- What is your current daily calorie target or rough eating pattern?
- Are you open to a daily nutrition protocol with specific calorie/carb targets by training day type?

---

## STEP 9 — PULL EXISTING DATA

If Nori is connected, pull:
- Last 30 days of HRV, RHR, sleep (to establish baseline)
- Last body weight readings
- VO2max estimate if available

If Hevy is connected, pull:
- Last 2–4 weeks of strength sessions to note current working weights

If Garmin Connect is connected, pull:
- `query_activities` for the last 30 days — baseline weekly volume, session count, sport mix
- `analyze_training_period` for the same window — training load (CTL/ATL/TSB if available), peak-power curves, aerobic-efficiency trend
- `get_activity_details` for 2–3 representative recent sessions (one easy, one hard, one long if possible) — pull the FULL metric set per the WORKOUT EVALUATION PROTOCOL in CLAUDE.md, confirm the data depth and surface any baseline strengths/points to improve already visible
- `get_performance_metrics` — VO2max, lactate threshold, race predictor (if Garmin has calibrated them)

If BodySpec is connected, pull:
- Any existing DEXA scans

Summarize what you found to the athlete.

---

## STEP 10 — CREATE THE WIKI

Ensure the memory directory exists (`mkdir -p ~/.coach_memory`), then create the file `~/.coach_memory/wiki.md` using the template from `templates/wiki-template.md`.

Fill in everything you've learned:
- Athlete profile (all fields)
- Baseline biometrics from Nori data
- Working weights from Hevy data
- DEXA scans from BodySpec (if available)
- Goals and current phase
- Training calendar ID
- Default week structure based on their sport + frequency preferences

Calculate and fill in the nutrition targets table (Section 6) based on:
- Body weight, age, sex
- Training phase (cut / maintenance / build)
- Activity level

---

## STEP 11 — GENERATE DAILY MENU TEMPLATES

Based on their nutrition targets and dietary preferences, generate full daily menu templates for each day type (strength, sport, double, rest). Follow the format from CLAUDE.md exactly — with gram weights, per-meal macros, timing, pre/post workout meals, and tips.

Add these to Section 11 of the wiki.

---

## STEP 12 — PROPOSE FIRST WEEK

Ask: "Would you like me to plan your first training week right now, or would you prefer to start the weekly check-in process next week?"

If they want a plan now:
- Ask for any schedule constraints this week (days they can't train, early morning vs. evening preference)
- Propose a full 7-day plan based on their sport, frequency, and goals
- Create calendar events on their private calendar with full nutrition descriptions

---

## STEP 13 — FINISH

Summarize what was set up:
- Wiki location: `~/.coach_memory/wiki.md`
- How to trigger weekly check-in: type `/weekly-checkin`
- How to re-run setup if needed: type `/coach-setup`
- What happens automatically each week

Send a welcome Slack DM to the athlete (if Slack is connected) with a brief summary.
Send a welcome Gmail to the athlete's email with a brief summary and what to expect.

Setup complete.
