import { db } from '../db/client.js'
import { auditLog } from '../db/schema.js'

// Append-only audit trail. NEVER put key material or credentials in `detail`.
export function audit(userId: string | null, action: string, detail?: unknown) {
  try {
    db.insert(auditLog)
      .values({
        userId,
        action,
        detail: detail == null ? null : JSON.stringify(detail).slice(0, 2000),
        createdAt: new Date(),
      })
      .run()
  } catch (err) {
    // Auditing must never break the request path.
    console.error('[audit] write failed:', err)
  }
}
