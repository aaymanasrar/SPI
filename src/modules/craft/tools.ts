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
  "pdf.extract": {
    name: "pdf.extract",
    engine: "pdf",
    previewPermission: "craft.preview",
    // Extraction only reads. There is nothing to commit: what it returns is a
    // proposal for an engineer to promote, like a client BOQ read.
    commitPermission: null,
    aiMayPreview: true,
    aiMayCommit: false,
  },
  "pdf.pack": {
    name: "pdf.pack",
    engine: "pdf",
    previewPermission: "craft.preview",
    commitPermission: "craft.commit",
    // A submittal pack is an outward-facing document. The AI may assemble a
    // preview; issuing it is a person's decision.
    aiMayPreview: true,
    aiMayCommit: false,
  },
  "cad.read_dxf": {
    name: "cad.read_dxf",
    engine: "cad",
    previewPermission: "craft.preview",
    commitPermission: null,
    aiMayPreview: true,
    aiMayCommit: false,
  },
  "cad.count_devices": {
    name: "cad.count_devices",
    engine: "cad",
    previewPermission: "craft.preview",
    // A count writes drawing_objects with review_status='pending'. Those rows
    // are proposals; promoting them to design_devices is the existing
    // building_model.review flow, not this tool.
    commitPermission: "craft.commit",
    aiMayPreview: true,
    aiMayCommit: false,
  },
  "cad.extract_rooms": {
    name: "cad.extract_rooms",
    engine: "cad",
    previewPermission: "craft.preview",
    commitPermission: null,
    aiMayPreview: true,
    aiMayCommit: false,
  },
  "cad.markup": {
    name: "cad.markup",
    engine: "cad",
    previewPermission: "craft.preview",
    commitPermission: "craft.commit",
    // Markup is a drawing that may be issued to a consultant. The AI can draft
    // one; sending it is a person's decision.
    aiMayPreview: true,
    aiMayCommit: false,
  },
  // cad.place_devices and cad.measure_route are deliberately absent. They are
  // registered in the engine as implemented=false and raise NotImplementedError;
  // listing them here would advertise them to the orchestrator as callable.
};

export function policyFor(tool: string): ToolPolicy {
  const p = TOOL_POLICY[tool];
  if (!p) throw new Error(`Unknown craft tool: ${tool}`);
  return p;
}
