import { and, eq } from 'drizzle-orm'
import { db } from '../db/client.js'
import { integrations } from '../db/schema.js'
import { encrypt, decrypt } from '../lib/crypto.js'

export type Provider = 'hevy' | 'strava' | 'oura' | 'garmin'

// Load a user's decrypted credentials for a provider (null if not connected).
export async function loadCreds<T = Record<string, unknown>>(
  userId: string,
  provider: Provider,
): Promise<T | null> {
  const [row] = await db
    .select()
    .from(integrations)
    .where(and(eq(integrations.userId, userId), eq(integrations.provider, provider)))
    .limit(1)
  if (!row || row.status === 'disconnected') return null
  try {
    return JSON.parse(decrypt(row.encryptedCredentials)) as T
  } catch {
    return null
  }
}

// Upsert encrypted credentials + mark connected.
export async function saveCreds(userId: string, provider: Provider, creds: unknown): Promise<void> {
  const now = new Date()
  const blob = encrypt(JSON.stringify(creds))
  const [existing] = await db
    .select({ id: integrations.id })
    .from(integrations)
    .where(and(eq(integrations.userId, userId), eq(integrations.provider, provider)))
    .limit(1)
  if (existing) {
    await db
      .update(integrations)
      .set({ encryptedCredentials: blob, status: 'connected', lastError: null, updatedAt: now })
      .where(eq(integrations.id, existing.id))
  } else {
    await db.insert(integrations).values({
      id: crypto.randomUUID(),
      userId,
      provider,
      encryptedCredentials: blob,
      status: 'connected',
      createdAt: now,
      updatedAt: now,
    })
  }
}

export async function disconnect(userId: string, provider: Provider): Promise<void> {
  await db
    .update(integrations)
    .set({ status: 'disconnected', encryptedCredentials: encrypt('{}'), updatedAt: new Date() })
    .where(and(eq(integrations.userId, userId), eq(integrations.provider, provider)))
}

export async function markError(userId: string, provider: Provider, error: string): Promise<void> {
  await db
    .update(integrations)
    .set({ status: 'error', lastError: error.slice(0, 500), updatedAt: new Date() })
    .where(and(eq(integrations.userId, userId), eq(integrations.provider, provider)))
}

export async function markSynced(userId: string, provider: Provider): Promise<void> {
  await db
    .update(integrations)
    .set({ lastSyncAt: new Date(), status: 'connected', lastError: null, updatedAt: new Date() })
    .where(and(eq(integrations.userId, userId), eq(integrations.provider, provider)))
}
