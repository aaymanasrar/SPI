import "server-only";

/**
 * Typed failures that runAction translates into a message a user can act on.
 *
 * The existing classes (AuthError, PermissionError) live in lib/auth.ts next to
 * the code that raises them. These are the craft-engine equivalents: without a
 * named class and a matching branch in runAction, every Python-service failure
 * collapses into "Something went wrong", which is correct for a database error
 * (those leak table and constraint names) but useless for "the engine is not
 * running" or "that product has no alarm current captured".
 */

/** The craft service could not be reached, timed out, or answered with a 5xx. */
export class CraftServiceError extends Error {
  constructor(
    public readonly tool: string,
    public readonly reason: "unreachable" | "timeout" | "bad_status" | "bad_response",
    message: string
  ) {
    super(message);
    this.name = "CraftServiceError";
  }
}

/**
 * A tool declined to produce output because a value it needed was never
 * captured. This is NOT a bug — it is the no-guess policy working. The user is
 * told exactly which field on which record to go and fill in.
 */
export class CraftMissingDataError extends Error {
  constructor(
    public readonly tool: string,
    public readonly missing: { field: string; record: string; note?: string | null }[]
  ) {
    super(
      `${tool} needs values that have not been captured: ` +
        missing.map((m) => `${m.record}.${m.field}`).join(", ")
    );
    this.name = "CraftMissingDataError";
  }
}
