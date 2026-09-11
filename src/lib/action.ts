import "server-only";
import { z } from "zod";
import { AuthError, PermissionError } from "@/lib/auth";

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
