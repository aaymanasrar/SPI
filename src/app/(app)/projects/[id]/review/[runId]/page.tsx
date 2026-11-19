import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";
import { requireSession } from "@/lib/auth";
import { getProject } from "@/modules/projects/repository";
import { getReview, type ReviewIssue } from "@/modules/review/repository";
import { Card, Empty, NoPermission, Pill } from "@/components/ui";

const DOC_LABEL: Record<string, string> = { drawing: "Drawing", spec: "Spec", boq: "BOQ", rules: "Rule" };
const DOC_TONE: Record<string, string> = {
  drawing: "bg-sky-400/15 text-sky-300",
  spec: "bg-violet-400/15 text-violet-300",
  boq: "bg-accent-soft text-accent",
  rules: "bg-leaf-soft text-leaf",
};
const STATUS_TONE: Record<string, string> = {
  matches: "text-leaf",
  "fewer than recommended": "text-warn",
  "not drawn": "text-danger",
  "more than recommended": "text-muted",
  "no rule": "text-faint",
};

const label = (s: string) => s.replace(/_/g, " ");
const tone = (status: string | null) =>
  status?.startsWith("total matches") ? "text-warn" : (STATUS_TONE[status ?? ""] ?? "text-muted");

/** Which documents disagree, in the order an engineer resolves them. */
const GROUPS: { title: string; hint: string; codes: RegExp }[] = [
  { title: "Spec vs drawing", hint: "The drawing does not do what a clause requires.", codes: /^(SPEC-VS-DRAWING|SPEC-SYSTEM-NOT-DRAWN|DRAWING-SYSTEM-NOT-IN-SPEC)/ },
  { title: "BOQ vs drawing", hint: "The client BOQ prices something other than what is drawn.", codes: /^(BOQ-VS-DRAWING|DRAWING-NOT-IN-BOQ|BOQ-NOT-ON-DRAWING)/ },
  { title: "BOQ vs spec", hint: "A BOQ line contradicts the specification.", codes: /^BOQ-VS-SPEC/ },
  { title: "Spec vs itself and the code", hint: "Clauses that disagree, or fall outside a code band.", codes: /^(SPEC-CONTRADICTS-ITSELF|SPEC-OUTSIDE-CODE-BAND)/ },
  { title: "Drawing vs SPI's rules", hint: "Rooms with fewer devices than the rules library places.", codes: /^DRAWING-BELOW-RULE/ },
];

function grouped(issues: ReviewIssue[]) {
  const used = new Set<ReviewIssue>();
  const out = GROUPS.map((g) => {
    const items = issues.filter((i) => g.codes.test(i.code));
    items.forEach((i) => used.add(i));
    return { ...g, items };
  });
  const rest = issues.filter((i) => !used.has(i));
  if (rest.length) out.push({ title: "Other", hint: "", codes: /./, items: rest });
  return out.filter((g) => g.items.length > 0);
}

function Issue({ i }: { i: ReviewIssue }) {
  return (
    <li className="rounded-xl border border-line bg-surface-2 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground">{i.title}</div>
          <div className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-faint">{i.code}</div>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
          i.severity === "review" ? "bg-warn/15 text-warn" : "bg-white/8 text-muted"}`}>
          {i.severity === "review" ? "review" : "note"}
        </span>
      </div>
      <p className="mt-2 text-sm text-muted">{i.detail}</p>
      <ul className="mt-3 space-y-1.5">
        {i.sources.map((s, k) => (
          <li key={k} className="flex gap-2 text-xs">
            <span className={`h-fit shrink-0 rounded px-1.5 py-0.5 font-medium ${DOC_TONE[s.doc] ?? ""}`}>
              {DOC_LABEL[s.doc] ?? s.doc}
            </span>
            <span className="min-w-0 text-muted">
              <span className="text-foreground">{s.name ?? ""}</span>
              {s.ref && <> — {s.ref}</>}
              {s.text && <span className="block truncate text-faint" title={s.text}>“{s.text}”</span>}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-accent">→ {i.action}</p>
    </li>
  );
}

export default async function ReviewResultPage({ params }: { params: Promise<{ id: string; runId: string }> }) {
  const { id, runId } = await params;
  if (!z.string().uuid().safeParse(runId).success) notFound();
  const session = await requireSession();
  const project = await getProject(session.organizationId, id);
  if (!project) notFound();
  if (!session.permissions.has("craft.preview")) return <NoPermission what="viewing engine results" />;
  const r = await getReview(session.organizationId, id, runId);
  if (!r) notFound();
  const o = r.outputs;
  const workbook = r.files.find((f) => f.filename.endsWith(".xlsx"));
  const marked = r.files.find((f) => f.filename.endsWith(".dxf"));
  const review = o?.issues.filter((i) => i.severity === "review") ?? [];
  const notes = o?.issues.filter((i) => i.severity !== "review") ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <Link href={`/projects/${id}/review`} className="text-xs text-muted hover:text-foreground">
            ← Drawing, spec &amp; BOQ check
          </Link>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-light tracking-tight text-foreground">
            Check results <Pill value={r.status} />
          </h1>
          <p className="text-xs text-muted">{r.inputs.join(" · ")} · {r.createdAt.toLocaleString()}</p>
        </div>
        <div className="flex gap-2">
          {marked && (
            <Link href={`/projects/${id}/drawings/${marked.id}`}
              className="rounded-full border border-line-strong px-3.5 py-1.5 text-xs text-foreground hover:bg-white/5">
              Recommended positions
            </Link>
          )}
          {workbook && (
            <a href={`/projects/${id}/files/${workbook.id}?download=1`}
              className="rounded-full bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-ink hover:brightness-110">
              Download BOQ &amp; report (XLSX)
            </a>
          )}
        </div>
      </div>

      {r.error && <p className="rounded-lg bg-danger/12 px-3 py-2 text-sm text-danger">{r.error}</p>}
      {r.missing.length > 0 && (
        <div className="rounded-xl border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-warn">
          {r.missing.map((m, k) => <p key={k}>{m.note ?? `${m.record}.${m.field}`}</p>)}
        </div>
      )}

      {o && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              ["To review", o.summary.review, "text-warn"],
              ["Notes", o.summary.info, "text-muted"],
              ["Devices drawn", o.summary.drawn_devices, "text-foreground"],
              ["SPI recommends", o.summary.recommended_devices, "text-foreground"],
            ].map(([k, v, tone]) => (
              <div key={k as string} className="glass rounded-2xl px-4 py-3">
                <div className="text-[11px] uppercase tracking-wider text-faint">{k}</div>
                <div className={`mt-1 text-3xl font-light tabular-nums ${tone}`}>{v}</div>
              </div>
            ))}
          </div>

          <Card title="BOQ" description="Drawn on the plan, recommended by SPI's rules, stated in the spec, priced in the client BOQ. Hover 'why' for the rule.">
            {o.boq.length === 0 ? <Empty>Nothing to list.</Empty> : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-faint">
                      <th className="px-2 py-2">Item</th>
                      <th className="px-2 py-2 text-right">Drawn</th>
                      <th className="px-2 py-2 text-right">SPI rec.</th>
                      <th className="px-2 py-2 text-right">Spec</th>
                      <th className="px-2 py-2 text-right">Client BOQ</th>
                      <th className="px-2 py-2">Status</th>
                      <th className="px-2 py-2">Where SPI recommends</th>
                      <th className="px-2 py-2">Why</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {o.boq.map((l) => {
                      const off = (a: number | null, b: number | null) => a !== null && b !== null && a !== b;
                      return (
                        <tr key={`${l.system}-${l.device_type}`} className="align-top">
                          <td className="px-2 py-2">
                            <div className="text-foreground">{l.description}</div>
                            <div className="text-xs text-faint">{label(l.system)}</div>
                          </td>
                          <td className="px-2 py-2 text-right tabular-nums">{l.drawn ?? "—"}</td>
                          <td className={`px-2 py-2 text-right tabular-nums ${off(l.drawn, l.recommended) ? "text-warn" : ""}`}>
                            {l.recommended ?? "—"}
                          </td>
                          <td className={`px-2 py-2 text-right tabular-nums ${off(l.drawn, l.spec) ? "text-warn" : ""}`}>
                            {l.spec ?? "—"}
                          </td>
                          <td className={`px-2 py-2 text-right tabular-nums ${off(l.drawn, l.client_boq) ? "text-warn" : ""}`}>
                            {l.client_boq ?? "—"}
                          </td>
                          <td className={`px-2 py-2 text-xs ${tone(l.status)}`}>{l.status ?? "—"}</td>
                          <td className="max-w-[260px] px-2 py-2 text-xs text-muted">{l.where_recommended || "—"}</td>
                          <td className="max-w-[220px] px-2 py-2 text-xs text-faint">
                            <span className="line-clamp-2" title={l.why}>{l.why || "—"}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title={`Contradictions and gaps (${o.issues.length})`}
            description={`${review.length} to review, ${notes.length} notes. Each cites both sources; which side is right is the engineer's call.`}>
            {o.issues.length === 0 ? <Empty>Nothing contradicts.</Empty> : (
              <div className="space-y-6">
                {grouped(o.issues).map((g) => (
                  <section key={g.title}>
                    <div className="mb-2 flex items-baseline gap-2">
                      <h3 className="text-sm font-medium text-foreground">{g.title}</h3>
                      <span className="text-xs text-faint">{g.items.length} · {g.hint}</span>
                    </div>
                    <ul className="grid gap-3 lg:grid-cols-2">
                      {g.items.map((i, k) => <Issue key={k} i={i} />)}
                    </ul>
                  </section>
                ))}
              </div>
            )}
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            {marked?.previewId && (
              <Card title="Recommended positions" description="Magenta crosses: where SPI's rules put each device. Click to open.">
                <Link href={`/projects/${id}/drawings/${marked.id}`} className="block overflow-hidden rounded-xl bg-white">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`/projects/${id}/files/${marked.previewId}`} alt="Drawing with SPI's recommended device positions" className="w-full" />
                </Link>
              </Card>
            )}
            <Card title={`Not checked (${o.not_checked.length})`} description="Listed so a gap is never mistaken for a pass.">
              {o.not_checked.length === 0 ? <Empty>Everything read was checked.</Empty> : (
                <ul className="space-y-1.5 text-xs">
                  {o.not_checked.map((n, k) => (
                    <li key={k}><span className="text-foreground">{n.what}</span> <span className="text-faint">— {n.why}</span></li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          {o.rooms.length > 0 && (
            <Card title="By room" description="Area-based devices. Door-based ones (call points, readers) are compared per floor.">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-faint">
                      <th className="px-2 py-2">Room</th><th className="px-2 py-2">Device</th>
                      <th className="px-2 py-2 text-right">Drawn</th><th className="px-2 py-2 text-right">SPI rec.</th>
                      <th className="px-2 py-2">Status</th><th className="px-2 py-2">Note</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {o.rooms.map((l, k) => (
                      <tr key={k}>
                        <td className="px-2 py-1.5">{l.room}{l.area_m2 ? <span className="text-xs text-faint"> · {l.area_m2} m²</span> : null}</td>
                        <td className="px-2 py-1.5 text-muted">{label(l.device_type)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{l.drawn}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{l.recommended ?? "—"}</td>
                        <td className={`px-2 py-1.5 text-xs ${STATUS_TONE[l.status] ?? ""}`}>{l.status}</td>
                        <td className="px-2 py-1.5 text-xs text-faint">{l.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
