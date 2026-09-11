import "server-only";
import type postgres from "postgres";
import { sql } from "@/lib/db";
import type { Session } from "@/lib/auth";

/**
 * Audit logging (spec §22, ARCHITECTURE.md §12).
 *
 * audit_logs is append-only at the database level — migration 0010 attaches a
 * trigger that rejects UPDATE and DELETE — so a written entry cannot later be
 * revised or quietly removed.
 *
 * Pass the transaction handle when auditing a mutation, so the record and its
 * audit entry commit or fail together. An audit entry for a write that rolled
 * back is a lie about what happened.
 */
export async function recordAudit(
  session: Session,
  entry: {
    action: string;
    subjectType: string;
    subjectId?: string | null;
    before?: unknown;
    after?: unknown;
  },
  tx?: postgres.TransactionSql
): Promise<void> {
  const db = tx ?? sql;
  await db`
    insert into audit_logs
      (organization_id, actor_id, action, subject_type, subject_id, before, after)
    values (
      ${session.organizationId},
      ${session.userId},
      ${entry.action},
      ${entry.subjectType},
      ${entry.subjectId ?? null},
      ${entry.before ? JSON.stringify(entry.before) : null},
      ${entry.after ? JSON.stringify(entry.after) : null}
    )
  `;
}
