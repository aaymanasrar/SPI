import "server-only";
import type { CraftEngine } from "./repository";

/**
 * What the AI orchestrator is allowed to see and call.
 *
 * The authoritative schemas come from the engine itself (GET /tools). This file
 * adds only what the engine cannot know: which permission gates the call, and
 * whether the AI may initiate it at all.
 *
 * ARCHITECTURE.md §4.1 rule 1 — "ai/ may not write to authoritative tables" — is
 * why aiMayCommit is false everywhere. An AI may look; a person commits.
 */

export type ToolPolicy = {
  name: string;
  engine: CraftEngine;
  /** Permission required for a preview (read-only) call. */
  previewPermission: "craft.preview";
  /** Permission required for a commit (writes a file and rows) call. */
  commitPermission: "craft.commit" | null;
  /** May the orchestrator call this without a human in the loop? Preview only. */
  aiMayPreview: boolean;
  aiMayCommit: false;
};

export const TOOL_POLICY: Record<string, ToolPolicy> = {
  "grid.write_boq": {
    name: "grid.write_boq",
    engine: "grid",
    previewPermission: "craft.preview",
    commitPermission: "craft.commit",
    aiMayPreview: true,
    aiMayCommit: false,
  },
  "grid.read_client_boq": {
    name: "grid.read_client_boq",
    engine: "grid",
    previewPermission: "craft.preview",
    // Reading a client workbook produces proposals, never truth. There is no
    // commit mode: promotion is a separate, human act.
    commitPermission: null,
    aiMayPreview: true,
    aiMayCommit: false,
  },
};

export function policyFor(tool: string): ToolPolicy {
  const p = TOOL_POLICY[tool];
  if (!p) throw new Error(`Unknown craft tool: ${tool}`);
  return p;
}
