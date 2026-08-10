import { createSdkMcpServer, tool } from '@anthropic-ai/claude-agent-sdk'
import { z } from 'zod'
import path from 'node:path'
import fs from 'node:fs'
import { and, eq, gte } from 'drizzle-orm'
import { db } from '../db/client.js'
import { metricsCache, user } from '../db/schema.js'
import { userDataDir } from '../lib/paths.js'
import { loadCreds, type Provider } from '../integrations/creds.js'
import { hevy, type HevyCreds } from '../integrations/hevy.js'
import { strava, type StravaCreds } from '../integrations/strava.js'
import { oura, type OuraCreds } from '../integrations/oura.js'

const ok = (data: unknown) => ({ content: [{ type: 'text' as const, text: typeof data === 'string' ? data : JSON.stringify(data) }] })
const err = (m: string) => ({ content: [{ type: 'text' as const, text: `ERROR: ${m}` }], isError: true })

// Build the per-user in-process MCP tool server. Only tools for connected
// integrations are registered; all credentials are captured per-request.
export function buildUserToolServer(userId: string, connected: Set<Provider>, opts: { onboarding?: boolean } = {}) {
  const tools = []

  if (connected.has('hevy')) {
    tools.push(
      tool('hevy_get_workouts', 'Get recent strength workouts from Hevy (paged, most recent first).',
        { page: z.number().optional(), pageSize: z.number().optional() },
        async (a) => {
          const c = await loadCreds<HevyCreds>(userId, 'hevy'); if (!c) return err('hevy not connected')
          try { return ok(await hevy.getWorkouts(c, a.page ?? 1, a.pageSize ?? 10)) } catch (e) { return err(String(e)) }
        }),
      tool('hevy_get_routines', 'Get the athlete\'s Hevy routines.', { page: z.number().optional() },
        async (a) => {
          const c = await loadCreds<HevyCreds>(userId, 'hevy'); if (!c) return err('hevy not connected')
          try { return ok(await hevy.getRoutines(c, a.page ?? 1)) } catch (e) { return err(String(e)) }
        }),
      tool('hevy_create_routine', 'Create a Hevy routine (consent-gated). Pass the full routine payload.',
        { routine: z.any() },
        async (a) => {
          const c = await loadCreds<HevyCreds>(userId, 'hevy'); if (!c) return err('hevy not connected')
          try { return ok(await hevy.createRoutine(c, a.routine)) } catch (e) { return err(String(e)) }
        }),
    )
  }

  if (connected.has('strava')) {
    tools.push(
      tool('strava_list_activities', 'List Strava activities in a date window (ISO dates).',
        { afterISO: z.string().optional(), beforeISO: z.string().optional() },
        async (a) => {
          const c = await loadCreds<StravaCreds>(userId, 'strava'); if (!c) return err('strava not connected')
          try { return ok(await strava.listActivities(userId, c, a.afterISO, a.beforeISO)) } catch (e) { return err(String(e)) }
        }),
      tool('strava_get_activity', 'Get one Strava activity in full detail.', { id: z.number() },
        async (a) => {
          const c = await loadCreds<StravaCreds>(userId, 'strava'); if (!c) return err('strava not connected')
          try { return ok(await strava.getActivity(userId, c, a.id)) } catch (e) { return err(String(e)) }
        }),
      tool('strava_get_activity_streams', 'Get per-point streams (watts, heartrate, cadence, grade_smooth, altitude, etc.) for terrain-segmented analysis.',
        { id: z.number(), keys: z.string().describe('comma-separated: e.g. watts,heartrate,cadence,grade_smooth,altitude') },
        async (a) => {
          const c = await loadCreds<StravaCreds>(userId, 'strava'); if (!c) return err('strava not connected')
          try { return ok(await strava.getStreams(userId, c, a.id, a.keys)) } catch (e) { return err(String(e)) }
        }),
    )
  }

  if (connected.has('oura')) {
    tools.push(
      tool('oura_get_daily', 'Get daily Oura data. metric: readiness | sleep | activity | heartrate. Dates ISO YYYY-MM-DD.',
        { metric: z.enum(['readiness', 'sleep', 'activity', 'heartrate']), start: z.string(), end: z.string() },
        async (a) => {
          const c = await loadCreds<OuraCreds>(userId, 'oura'); if (!c) return err('oura not connected')
          try { return ok(await oura.getDaily(userId, c, a.metric, a.start, a.end)) } catch (e) { return err(String(e)) }
        }),
    )
  }

  // Always available:
  tools.push(
    tool('metrics_query', 'Query cached daily metric trends (hrv, sleep_hours, weight_lb, rhr, ride_tss, etc.) without a live API call.',
      { metric: z.string(), startDate: z.string(), endDate: z.string() },
      async (a) => {
        const rows = await db.select({ date: metricsCache.date, value: metricsCache.value, source: metricsCache.source })
          .from(metricsCache)
          .where(and(eq(metricsCache.userId, userId), eq(metricsCache.metric, a.metric), gte(metricsCache.date, a.startDate)))
        return ok(rows.filter((r) => r.date <= a.endDate))
      }),
    tool('commit_week_plan', 'Commit the approved week plan (consent-gated). Writes plan.json + refreshes state/current.md; feeds the week view and calendar feed.',
      {
        weekStart: z.string().describe('ISO date of the week Monday'),
        days: z.array(z.object({
          date: z.string(), title: z.string(), type: z.string(),
          details: z.string().optional(), menu: z.string().optional(),
        })),
      },
      async (a) => {
        const dir = userDataDir(userId)
        fs.mkdirSync(path.join(dir, 'state'), { recursive: true })
        fs.writeFileSync(path.join(dir, 'state', 'plan.json'), JSON.stringify({ weekStart: a.weekStart, days: a.days }, null, 2))
        return ok('week plan committed')
      }),
    tool('save_dashboard', 'Save the dashboard state JSON (athlete tiles, big3/goals, biometrics). Refreshes the dashboard.',
      { dashboard: z.any() },
      async (a) => {
        const dir = userDataDir(userId)
        fs.mkdirSync(path.join(dir, 'state'), { recursive: true })
        fs.writeFileSync(path.join(dir, 'state', 'dashboard.json'), JSON.stringify(a.dashboard, null, 2))
        return ok('dashboard saved')
      }),
  )

  if (opts.onboarding) {
    tools.push(
      tool('complete_onboarding', 'Mark onboarding complete once the wiki + first week are set up.', {},
        async () => {
          await db.update(user).set({ onboardingStage: 'done', updatedAt: new Date() }).where(eq(user.id, userId))
          return ok('onboarding complete')
        }),
    )
  }

  return createSdkMcpServer({ name: 'coach', version: '1.0.0', tools })
}
