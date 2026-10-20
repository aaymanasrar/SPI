import "server-only";
import postgres from "postgres";

/**
 * Direct Postgres connection (ARCHITECTURE.md §2, confirmed for Prompt C).
 *
 * Chosen over PostgREST because this system needs real multi-statement
 * transactions: creating a BOQ revision with its items and an audit entry has
 * to be atomic, and approval transitions must not half-apply.
 *
 * DATABASE_URL is the single switch between environments. Point it at local
 * Postgres for development or at Supabase for staging/production — the schema
 * is identical, applied from the same migrations.
 */

const connectionString =
  process.env.DATABASE_URL || process.env.LOCAL_DATABASE_URL;

if (!connectionString) {
  throw new Error(
    "No database connection. Set DATABASE_URL (or LOCAL_DATABASE_URL) in .env"
  );
}

declare global {
  // `var` is required here: a `declare global` augmentation of globalThis
  // cannot use let/const.
  var __spi_sql: ReturnType<typeof postgres> | undefined;
}

// Reused across hot reloads in development, otherwise each reload opens a new
// pool and the connection limit is reached quickly.
export const sql =
  global.__spi_sql ??
  postgres(connectionString, {
    max: 10,
    idle_timeout: 20,
    connect_timeout: 10,
    // Snake case in the database, camelCase in TypeScript.
    transform: postgres.camel,
    onnotice: () => {},
  });

if (process.env.NODE_ENV !== "production") global.__spi_sql = sql;

/**
 * Runs a set of statements in one transaction.
 *
 * Anything that writes more than one row, or writes a row plus an audit
 * entry, belongs in here. A partially applied mutation is worse than a failed
 * one: it leaves a record that looks complete and is not.
 */
export async function transaction<T>(
  fn: (tx: postgres.TransactionSql) => Promise<T>
): Promise<T> {
  return sql.begin(fn) as Promise<T>;
}

/** True when the database is reachable. Used by the health check. */
export async function isReachable(): Promise<boolean> {
  try {
    await sql`select 1`;
    return true;
  } catch {
    return false;
  }
}

/** Which database this process is talking to — surfaced in the health check. */
export function describeTarget(): { host: string; database: string } {
  try {
    const u = new URL(connectionString!);
    return {
      host: u.hostname,
      database: u.pathname.replace(/^\//, "") || "(default)",
    };
  } catch {
    return { host: "(unparsed)", database: "(unparsed)" };
  }
}
