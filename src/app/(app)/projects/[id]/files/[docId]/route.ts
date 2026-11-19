import { readFile } from "node:fs/promises";
import path from "node:path";
import { z } from "zod";
import { getSession } from "@/lib/auth";
import { getProjectDocument } from "@/modules/model/repository";
import { storageRoot } from "@/modules/prototype/storage";

/**
 * Serve one project document: inline for pictures and PDFs, as a download
 * otherwise, or always with ?download=1.
 *
 * The proxy only redirects; this checks the session, the permission and that
 * the document belongs to this organization's project before reading a byte.
 */

const INLINE = new Set(["image/svg+xml", "image/png", "image/jpeg", "application/pdf"]);
const uuid = z.string().uuid();

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; docId: string }> }
) {
  const { id, docId } = await params;
  const session = await getSession();
  if (!session) return new Response("Not signed in", { status: 401 });
  if (!session.permissions.has("document.read")) {
    return new Response("Your role does not allow reading documents", { status: 403 });
  }
  if (!uuid.safeParse(id).success || !uuid.safeParse(docId).success) {
    return new Response("Not found", { status: 404 });
  }
  const doc = await getProjectDocument(session.organizationId, id, docId);
  if (!doc) return new Response("Not found", { status: 404 });

  // Keys are written by the server, but resolve and check anyway: a row that
  // somehow pointed outside the root must not become a file read.
  const root = storageRoot();
  const file = path.resolve(root, doc.storageKey);
  if (!file.startsWith(root + path.sep)) return new Response("Not found", { status: 404 });

  let body: Buffer;
  try {
    body = await readFile(file);
  } catch {
    return new Response("The file is recorded but missing from storage", { status: 410 });
  }

  const type = doc.contentType || "application/octet-stream";
  const download = new URL(request.url).searchParams.has("download") || !INLINE.has(type);
  const name = doc.filename.replace(/["\\\r\n]/g, "_");
  const headers: Record<string, string> = {
    "content-type": type,
    "content-length": String(body.length),
    "content-disposition": `${download ? "attachment" : "inline"}; filename="${name}"`,
    "x-content-type-options": "nosniff",
    "cache-control": "private, max-age=300",
  };
  // An SVG opened on its own is a document that could run script. Ours come
  // from the renderer, but the policy makes that not matter.
  if (type === "image/svg+xml") {
    headers["content-security-policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:";
  }
  return new Response(new Uint8Array(body), { headers });
}
