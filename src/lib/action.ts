import "server-only";
import { z } from "zod";
import { AuthError, PermissionError } from "@/lib/auth";
import { CraftServiceError, CraftMissingDataError } from "@/lib/errors";

/**
 * Shared result shape for Server Actions, and the error translation that keeps
 * internal failures from reaching the browser.
 */

export type ActionState =
  | { ok: true; message?: string }
  | { ok: false; error: string; fieldErrors?: Record<string, string[]> };

export const idle: ActionState = { ok: true };

/**
 * Wraps an action body so every failure returns a message rather than an
 * unhandled rejection, and so no internal detail leaks.
 *
 * Authorization failures are reported as such — a user should be told they
 * lack permission rather than shown a generic error that looks like a bug.
 * Everything else is logged server-side and reduced to a neutral message,
 * because database errors routinely contain table names, constraint names and
 * fragments of the failing row.
 */
export async function runAction(
  fn: () => Promise<ActionState>
): Promise<ActionState> {
  try {
    return await fn();
  } catch (error) {
    if (error instanceof PermissionError) {
      return {
        ok: false,
        error: `You do not have permission to do this (${error.permission}).`,
      };
    }
    if (error instanceof AuthError) {
      return { ok: false, error: "Your session has expired. Sign in again." };
    }
    if (error instanceof z.ZodError) {
      return {
        ok: false,
        error: "Please correct the highlighted fields.",
        fieldErrors: z.flattenError(error).fieldErrors as Record<
          string,
          string[]
        >,
      };
    }

    // A craft tool refusing to invent a value is a normal outcome, not a fault.
    // Name the fields so the user knows what to go and capture.
    if (error instanceof CraftMissingDataError) {
      return {
        ok: false,
        error:
          `Not enough captured data to run ${error.tool}. Missing: ` +
          error.missing.map((m) => `${m.record}.${m.field}`).join(", ") +
          ". These must come from the datasheet \u2014 the engine will not assume a value.",
      };
    }
    if (error instanceof CraftServiceError) {
      console.error("[craft]", error.tool, error.reason, error.message);
      return {
        ok: false,
        error:
          error.reason === "unreachable" || error.reason === "timeout"
            ? "The calculation service is not responding. Try again, or tell an administrator."
            : `The calculation service rejected the request (${error.tool}).`,
      };
    }

    console.error("[action]", error);
    return { ok: false, error: "Something went wrong. Please try again." };
  }
}

/** Empty string from a form input means "not provided", not "empty value". */
export const optionalText = z
  .string()
  .trim()
  .transform((v) => (v === "" ? null : v))
  .nullable();

export const optionalNumber = z
  .string()
  .trim()
  .transform((v) => (v === "" ? null : Number(v)))
  .refine((v) => v === null || Number.isFinite(v), "Must be a number")
  .nullable();

export const optionalInt = z
  .string()
  .trim()
  .transform((v) => (v === "" ? null : Number(v)))
  .refine(
    (v) => v === null || Number.isInteger(v),
    "Must be a whole number"
  )
  .nullable();
