import "server-only";
import { createHash, randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

/**
 * Where submitted drawings are kept, as a key under one storage root that the
 * craft engines read from too (ARCHITECTURE.md §7: originals are never
 * modified; every upload is a new key).
 *
 * Local disk, set by CRAFT_STORAGE_ROOT. In staging and production this is the
 * same layout on S3-compatible storage mounted where the engines can read it.
 */
export function storageRoot(): string {
  return path.resolve(process.env.CRAFT_STORAGE_ROOT || "storage");
}

/** Accepted drawing types and the document classification they get. */
export const DRAWING_TYPES: Record<string, string> = {
  ".dxf": "image/vnd.dxf",
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".tif": "image/tiff",
  ".tiff": "image/tiff",
  ".ifc": "application/x-step",
  // Specifications and BOQs, checked against the drawings (engines/craft/review).
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".txt": "text/plain",
};

export const MAX_FILE_BYTES = 150 * 1024 * 1024;

export type StoredFile = {
  filename: string;
  storageKey: string;
  contentType: string;
  byteSize: number;
  sha256: string;
};

function safeName(name: string): string {
  const base = path.basename(name).normalize("NFKC");
  const cleaned = base.replace(/[^\p{L}\p{N}._-]+/gu, "_").replace(/^\.+/, "");
  return cleaned.slice(-120) || "drawing";
}

export async function saveUpload(
  organizationId: string,
  projectId: string,
  file: File
): Promise<StoredFile> {
  const filename = safeName(file.name);
  const ext = path.extname(filename).toLowerCase();
  const contentType = DRAWING_TYPES[ext];
  if (!contentType) throw new Error(`${file.name}: not a file type this can read`);
  const bytes = Buffer.from(await file.arrayBuffer());
  // Keys are made here, never taken from the request, so a filename cannot
  // reach outside the storage root.
  const storageKey = path.posix.join("org", organizationId, "project", projectId, "drawings",
    `${randomUUID()}-${filename}`);
  const target = path.join(storageRoot(), storageKey);
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, bytes, { flag: "wx" });
  return {
    filename,
    storageKey,
    contentType,
    byteSize: bytes.length,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}
