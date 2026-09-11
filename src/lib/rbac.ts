import "server-only";
import {
  getSession,
  requireSessionOrThrow,
  PermissionError,
  type Session,
} from "@/lib/auth";

/**
 * Permission enforcement (ARCHITECTURE.md §6.2, spec §21.1 "authorize every
 * mutation").
 *
 * Permission codes are seeded rows, not constants in code, so the set is
 * inspectable and auditable. The union below mirrors migration 0012 and exists
 * only to catch typos at compile time — the database remains the source of
 * truth.
 */
export type Permission =
  | "organization.manage"
  | "user.manage"
  | "project.create"
  | "project.read"
  | "project.update"
  | "project.archive"
  | "document.upload"
  | "document.read"
  | "building_model.edit"
  | "building_model.review"
  | "system.select"
  | "rule.author"
  | "rule.approve"
  | "rule.execute"
  | "design.generate"
  | "design.edit"
  | "catalogue.manage"
  | "catalogue.authorize"
  | "pricing.manage"
  | "pricing.view_internal"
  | "boq.generate"
  | "boq.edit"
  | "boq.approve"
  | "quotation.generate"
  | "quotation.edit"
  | "quotation.approve"
  | "quotation.issue"
  | "quotation.view_customer"
  | "validation.run"
  | "validation.resolve"
  | "review_task.resolve"
  | "rfq.manage"
  | "rfq.respond"
  | "audit.read";

/**
 * Asserts the caller holds a permission, and returns the session.
 *
 * Call this FIRST in every Server Action. Server Actions are reachable by
 * direct POST regardless of what the UI renders, so an unguarded action is
 * a public endpoint.
 */
export async function requirePermission(
  permission: Permission
): Promise<Session> {
  const session = await requireSessionOrThrow();
  if (!session.permissions.has(permission)) {
    throw new PermissionError(permission);
  }
  return session;
}

/** Non-throwing check, for deciding what to render. */
export async function can(permission: Permission): Promise<boolean> {
  const session = await getSession();
  return session?.permissions.has(permission) ?? false;
}

/**
 * Whether internal cost and margin may be shown.
 *
 * Spec §13.3, §21.1 and §29.1 all require these to stay invisible to
 * client-facing users. Hiding them in the UI is not enough — this gates
 * serialization, so the values never reach the response at all.
 */
export async function canSeeInternalCommercials(): Promise<boolean> {
  return can("pricing.view_internal");
}
