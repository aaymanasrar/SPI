import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";
import { requireSession } from "@/lib/auth";
import { getProject } from "@/modules/projects/repository";
import { getDrawingDetail } from "@/modules/model/repository";
import { Card, Pill, Empty } from "@/components/ui";

const KIND: Record<string, string> = {
  uploaded: "Uploaded drawing",
  takeoff: "Device takeoff",
  sheet: "Shop drawing",
  preview: "Preview picture",
  other: "Engine output",
};

const tone: Record<string, string> = {
  blocker: "text-danger",
  review: "text-warn",
  info: "text-muted",
};

export default async function DrawingPage({
  params,
}: {
  params: Promise<{ id: string; docId: string }>;
}) {
  const { id, docId } = await params;
  if (!z.string().uuid().safeParse(docId).success) notFound();
  const session = await requireSession();
  const project = await getProject(session.organizationId, id);
  if (!project) notFound();
  const d = await getDrawingDetail(session.organizationId, id, docId);
  if (!d) notFound();

  const picture = d.previewId ? `/projects/${id}/files/${d.previewId}` : null;
  const schedule = d.schedule;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <Link href={`/projects/${id}/model`} className="text-xs text-muted hover:text-foreground">
            ← 3D model &amp; drawings
          </Link>
          <h1 className="mt-1 flex items-center gap-2 truncate text-xl font-light tracking-tight text-foreground">
            {d.filename} {d.status && <Pill value={d.missing.length > 0 && d.status === "ok" ? "missing_data" : d.status} />}
          </h1>
          <p className="text-xs text-muted">
            {KIND[d.kind]}
            {d.sourceFilename && <> · made from {d.sourceFilename}</>}
            {" · "}
            {d.createdAt.toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2">
          {picture && (
            <a
              href={picture}
              target="_blank"
              rel="noopener"
              className="rounded-full border border-line-strong px-3.5 py-1.5 text-xs text-foreground hover:bg-white/5"
            >
              Open full size ↗
            </a>
          )}
          <a
            href={`/projects/${id}/files/${d.id}?download=1`}
            className="rounded-full bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-ink hover:brightness-110"
          >
            Download {d.filename.split(".").pop()?.toUpperCase()}
          </a>
        </div>
      </div>

      <div className="overflow-auto rounded-2xl border border-line bg-white">
        {picture ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={picture} alt={`Drawing ${d.filename}`} className="block h-auto w-full min-w-[720px]" />
        ) : (
          <p className="px-6 py-16 text-center text-sm text-slate-500">
            {/\.ifc$/i.test(d.filename)
              ? "An IFC model has no flat picture. Make a 3D model from it on the previous page."
              : "No picture of this file. Pictures are made for DXF drawings when they are uploaded."}
          </p>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Still open" description="What the engine could not read or was not given. Nothing here was guessed.">
          {d.missing.length === 0 && d.findings.length === 0 ? (
            <Empty>{d.operationId ? "Nothing open." : "An upload is the original: nothing was computed."}</Empty>
          ) : (
            <ul className="space-y-2 text-sm">
              {d.missing.map((m, i) => (
                <li key={`m${i}`} className="text-warn">
                  <span className="font-medium">{m.field.replace(/^title_block\./, "Title block: ").replace(/_/g, " ")}</span>
                  {m.note && <> — {m.note}</>}
                </li>
              ))}
              {d.findings.map((f, i) => (
                <li key={`f${i}`} className={tone[f.severity] ?? "text-muted"}>
                  <span className="font-mono text-xs">{f.code}</span> — {f.detail}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Device schedule" description={d.kind === "takeoff" ? "Counted from block names on the drawing." : "From the takeoff this sheet frames."}>
          {schedule.length === 0 ? (
            <Empty>No schedule on this file.</Empty>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-faint">
                  <th className="px-2 py-1.5">Item</th>
                  <th className="px-2 py-1.5">System</th>
                  <th className="px-2 py-1.5">Device</th>
                  <th className="px-2 py-1.5 text-right">Qty</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {schedule.map((s, i) => (
                  <tr key={i}>
                    <td className="px-2 py-1.5 font-mono text-xs">{s.item ?? ""}</td>
                    <td className="px-2 py-1.5 text-muted">{s.system.replace(/_/g, " ")}</td>
                    <td className="px-2 py-1.5">{s.device_type.replace(/_/g, " ")}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{s.quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {d.assumptions.length > 0 && (
            <p className="mt-3 text-xs text-faint">
              Assumed: {d.assumptions.map((a) => `${a.key} = ${String(a.value)} (${a.basis})`).join("; ")}
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
