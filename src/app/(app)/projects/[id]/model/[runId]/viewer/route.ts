import { z } from "zod";
import { getSession } from "@/lib/auth";
import { getBuildingRun } from "@/modules/prototype/repository";
import { VIEWER_JS, VIEWER_PAGE, VIEWER_RULES } from "@/modules/model/viewer-assets.generated";

/**
 * The 3D simulator page for one recorded run: the same page simulator/build.sh
 * writes, with this project's scene in place of a file. Shown inside the app in
 * an iframe (projects/[id]/model/[runId]).
 */

const uuid = z.string().uuid();

/** JSON inside a <script>: "</" and the line separators must not end or break it. */
function embed(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, "\\u003c")
    .replace(new RegExp("\\u2028", "g"), "\\u2028")
    .replace(new RegExp("\\u2029", "g"), "\\u2029");
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; runId: string }> }
) {
  const { id, runId } = await params;
  const session = await getSession();
  if (!session) return new Response("Not signed in", { status: 401 });
  if (!session.permissions.has("craft.preview")) {
    return new Response("Your role does not allow viewing engine results", { status: 403 });
  }
  if (!uuid.safeParse(id).success || !uuid.safeParse(runId).success) {
    return new Response("Not found", { status: 404 });
  }
  const scene = await getBuildingRun(session.organizationId, id, runId);
  if (!scene) return new Response("Not found", { status: 404 });

  const html =
    VIEWER_PAGE +
    `<script>window.__SCENE__=${embed(scene)};\nwindow.__RULES__=${embed(VIEWER_RULES)};\n` +
    `window.__META__=${embed({ fixture: null, source_file: null })};</script>\n` +
    `<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n` +
    `<script>\n(function () {\n"use strict";\n${VIEWER_JS.replace(/<\/script/gi, "<\\/script")}})();\n</script>\n` +
    `</body>\n</html>\n`;

  return new Response(html, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "x-content-type-options": "nosniff",
      // Only this app may frame it.
      "x-frame-options": "SAMEORIGIN",
      "cache-control": "private, no-store",
    },
  });
}
