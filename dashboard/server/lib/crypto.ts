import crypto from 'node:crypto'

// AES-256-GCM at-rest encryption for per-user credentials (Anthropic keys,
// integration tokens). Key = 32-byte hex MASTER_ENCRYPTION_KEY env var
// (generate with: openssl rand -hex 32).
//
// Blob format (base64): iv(12B) | authTag(16B) | ciphertext

function masterKey(): Buffer {
  const hex = process.env.MASTER_ENCRYPTION_KEY
  if (!hex || !/^[0-9a-f]{64}$/i.test(hex)) {
    throw new Error(
      'MASTER_ENCRYPTION_KEY missing or malformed — set a 64-char hex string (openssl rand -hex 32)',
    )
  }
  return Buffer.from(hex, 'hex')
}

export function encrypt(plaintext: string): string {
  const key = masterKey()
  const iv = crypto.randomBytes(12)
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv)
  const ct = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()])
  const tag = cipher.getAuthTag()
  return Buffer.concat([iv, tag, ct]).toString('base64')
}

export function decrypt(blob: string): string {
  const key = masterKey()
  const buf = Buffer.from(blob, 'base64')
  const iv = buf.subarray(0, 12)
  const tag = buf.subarray(12, 28)
  const ct = buf.subarray(28)
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv)
  decipher.setAuthTag(tag)
  return Buffer.concat([decipher.update(ct), decipher.final()]).toString('utf8')
}

// Boot-time self-test: a mis-set MASTER_ENCRYPTION_KEY must fail loudly at
// startup, not corrupt data silently at 2am.
export function cryptoSelfTest() {
  const probe = `probe-${Date.now()}`
  if (decrypt(encrypt(probe)) !== probe) {
    throw new Error('crypto self-test failed — MASTER_ENCRYPTION_KEY misconfigured')
  }
  console.log('[crypto] AES-256-GCM self-test ok')
}

export function randomToken(bytes = 32): string {
  return crypto.randomBytes(bytes).toString('base64url')
}

// Short human-friendly invite code like 'KX7-Q2M-9DP' (avoids ambiguous chars).
export function inviteCode(): string {
  const alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
  const pick = () => alphabet[crypto.randomInt(alphabet.length)]
  const grp = () => pick() + pick() + pick()
  return `${grp()}-${grp()}-${grp()}`
}
