import "server-only";
import { CraftServiceError, CraftMissingDataError } from "@/lib/errors";

/**
 * Typed HTTP client for the craft engines service (engines/, FastAPI).
 *
 * Server-only by construction. The service trusts its caller — it has no session
 * and no RBAC — so it must never be reachable from the browser, and CRAFT_SERVICE_URL
 * is deliberately not a NEXT_PUBLIC_ variable.
 */

const BASE = process.env.CRAFT_SERVICE_URL;
const TIMEOUT_MS = Number(process.env.CRAFT_SERVICE_TIMEOUT_MS ?? 60_000);

export type CraftStatus = "ok" | "missing_data" | "invalid_input" | "error";

export type CraftResult = {
  operation_id: string | null;
  tool: string;
  status: CraftStatus;
  outputs: Record<string, unknown>;
  files: {
    name: string;
    mime: string;
    storage_key: string | null;
    document_id: string | null;
    byte_size: number | null;
    sha256: string | null;
  }[];
  provenance: { value_ref: string; source: string }[];
  missing: { field: string; record: string; note: string | null }[];
  warnings: string[];
  engine_version: string;
  duration_ms: number | null;
};

export type ToolSchema = {
  name: string;
  engine: "grid" | "word" | "cad" | "pdf";
  summary: string;
  modes: ("preview" | "commit")[];
  implemented: boolean;
  input_schema: Record<string, unknown>;
};

function baseUrl(tool: string): string {
  if (!BASE) {
    throw new CraftServiceError(
      tool,
      "unreachable",
      "CRAFT_SERVICE_URL is not set. Start the engines service and set it in .env."
    );
  }
  return BASE.replace(/\/+$/, "");
}

async function call<T>(tool: string, path: string, init?: RequestInit): Promise<T> {
  const url = `${baseUrl(tool)}${path}`;
  const signal = AbortSignal.timeout(TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      signal,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch (cause) {
    const timedOut = cause instanceof Error && cause.name === "TimeoutError";
    throw new CraftServiceError(
      tool,
      timedOut ? "timeout" : "unreachable",
      timedOut ? `No response within ${TIMEOUT_MS} ms` : String(cause)
    );
  }
  if (!response.ok) {
    throw new CraftServiceError(
      tool,
      "bad_status",
      `${response.status} ${response.statusText}: ${await response.text().catch(() => "")}`
    );
  }
  try {
    return (await response.json()) as T;
  } catch (cause) {
    throw new CraftServiceError(tool, "bad_response", String(cause));
  }
}

/** The schemas the AI orchestrator plans against. It sees nothing else. */
export async function listTools(): Promise<ToolSchema[]> {
  return call<ToolSchema[]>("tools", "/tools");
}

/**
 * Run one tool. Throws CraftMissingDataError when the engine declined to invent
 * a value, so runAction can name the missing fields rather than showing a
 * generic failure.
 */
export async function runTool(
  tool: string,
  args: {
    mode: "preview" | "commit";
    input: Record<string, unknown>;
    storageRoot?: string;
    operationId?: string;
  }
): Promise<CraftResult> {
  const result = await call<CraftResult>(tool, `/tools/${encodeURIComponent(tool)}`, {
    method: "POST",
    body: JSON.stringify({
      mode: args.mode,
      input: args.input,
      storage_root: args.storageRoot ?? null,
      operation_id: args.operationId ?? null,
    }),
  });
  if (result.status === "missing_data") {
    throw new CraftMissingDataError(tool, result.missing);
  }
  return result;
}
