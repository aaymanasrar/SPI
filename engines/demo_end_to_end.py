"""End-to-end: drawing -> count -> BOQ -> compliance -> PDF -> pack."""
import io, os, shutil, ezdxf
from craft.core import LocalStorage
from craft.cad import CountInput, count_devices, ReadDxfInput, read_dxf, RoomsInput, extract_rooms
from craft.grid import write_boq, WriteBoqInput, BoqLine
from craft.word import (templates, FillInput, fill_template, Clause,
                        ComplianceInput, compliance_sheet, ToPdfInput, to_pdf)
from craft.pdf import PackInput, StampSpec, pack, ExtractInput, extract

from pathlib import Path
import os
#: Generated files go to out/, which is gitignored: they are
#: regenerable and this directory holds only the source.
OUT = Path(os.environ.get("SPI_OUT",
    Path(__file__).resolve().parents[2] / "out" / "walkthrough"))
OUT.mkdir(parents=True, exist_ok=True)


W = str(OUT / "e2efull")
shutil.rmtree(W, ignore_errors=True)
st = LocalStorage(W)
for k in templates.names():
    st.write(f"templates/{k}.docx", templates.build(k))
step = lambda n, t: print(f"\n[{n}] {t}")

# ---- a floor plan with descriptive block names -------------------------------
d = ezdxf.new("R2010", setup=True); d.header["$INSUNITS"] = 4
for b in ("SMOKE-DETECTOR","MANUAL-CALL-POINT","SOUNDER-STROBE","DOME-CAMERA"):
    d.blocks.new(b)
for l in ("FA-DEVICES","CCTV","ROOM-BOUNDARY","ROOM-NAMES"):
    d.layers.add(l)
m = d.modelspace()
for i in range(14): m.add_blockref("SMOKE-DETECTOR",(i*1200,1000),dxfattribs={"layer":"FA-DEVICES"})
for i in range(3):  m.add_blockref("MANUAL-CALL-POINT",(i*3000,200),dxfattribs={"layer":"FA-DEVICES"})
for i in range(6):  m.add_blockref("SOUNDER-STROBE",(i*2500,2000),dxfattribs={"layer":"FA-DEVICES"})
for i in range(9):  m.add_blockref("DOME-CAMERA",(i*1800,2800),dxfattribs={"layer":"CCTV"})
for (x0,y0,x1,y1,nm) in [(0,0,9000,6000,"OPEN OFFICE"),(9000,0,14000,3000,"MEETING"),
                         (9000,3000,14000,6000,"SERVER ROOM")]:
    m.add_lwpolyline([(x0,y0),(x1,y0),(x1,y1),(x0,y1)],close=True,dxfattribs={"layer":"ROOM-BOUNDARY"})
    m.add_text(nm,dxfattribs={"layer":"ROOM-NAMES","height":200}).set_placement(((x0+x1)/2,(y0+y1)/2))
s=io.StringIO(); d.write(s); st.write("L01.dxf", s.getvalue().encode())

step(1,"cad.read_dxf")
r = read_dxf(ReadDxfInput(document_id="L01", storage_key="L01.dxf"), st)
print(f"    {r.status} | units {r.outputs['units']['name']} | {r.outputs['insert_total']} inserts "
      f"| layers {', '.join(r.outputs['entity_layers'])}")

step(2,"cad.extract_rooms")
rm = extract_rooms(RoomsInput(document_id="L01", storage_key="L01.dxf",
      boundary_layers=["ROOM-BOUNDARY"], label_layers=["ROOM-NAMES"]), st)
print(f"    {rm.status} | {rm.outputs['room_count']} rooms, "
      f"{sum(x['area_m2'] for x in rm.outputs['rooms']):.1f} m2 total")
for x in rm.outputs["rooms"]: print(f"      {str(x['name']):<14} {x['area_m2']:>7.2f} m2")

step(3,"cad.count_devices (default symbol map)")
c = count_devices(CountInput(document_id="L01", storage_key="L01.dxf"), st)
print(f"    {c.status} | {c.outputs['mapped_insert_count']} mapped, "
      f"{c.outputs['unmapped_insert_count']} unmapped")
for x in c.outputs["counts"]: print(f"      {x['system']:<12} {x['device_type']:<20} {x['quantity']:>3}")
assert c.status == "ok", c.missing

step(4,"grid.write_boq WITHOUT prices (must refuse)")
lines = [BoqLine(description=f"{x['device_type'].replace('_',' ').title()}", unit=x["unit"],
                 quantity=x["quantity"], system=x["system"],
                 quantity_source="imported",
                 quantity_reference="cad.count_devices on L01.dxf")
         for x in c.outputs["counts"]]
b0 = write_boq(WriteBoqInput(boq_id="B1", project_name="Riyadh Commercial Tower",
      project_code="RYD-001", revision=3, lines=lines, require_pricing=True,
      output_key="boq_nopricing.xlsx"), st)
print(f"    {b0.status} | files written: {len(b0.files)}")
for mi in b0.missing[:2]: print(f"      - {mi.record}.{mi.field}")

step(5,"grid.write_boq WITH supplied prices")
PRICES = {"smoke_detector":(18500,"SPT price list 2026-Q4"),
          "manual_call_point":(12000,"SPT price list 2026-Q4"),
          "sounder_strobe":(21000,"SPT price list 2026-Q4"),
          "camera":(145000,"SPT price list 2026-Q4")}
for ln, x in zip(lines, c.outputs["counts"]):
    cost, src = PRICES[x["device_type"]]
    ln.unit_cost_minor, ln.price_source, ln.currency = cost, src, "SAR"
b = write_boq(WriteBoqInput(boq_id="B1", project_name="Riyadh Commercial Tower",
      project_code="RYD-001", revision=3, lines=lines, require_pricing=True,
      output_key="BOQ.xlsx", currency="SAR"), st)
print(f"    {b.status} | {b.files[0].byte_size} bytes | {len(b.provenance)} provenance links")
print(f"    outputs: {sorted(b.outputs)}")
for pv in b.provenance[:4]: print(f"      {pv.value_ref:<18} <- {pv.source}")
if b.warnings: print("    warnings:", b.warnings)

step(6,"word.compliance_sheet")
cs = compliance_sheet(ComplianceInput(project_name="Riyadh Commercial Tower",
  product_model="FDO221", clauses=[
    Clause(reference="2.3.A", text="Operating voltage shall be at least 12 V DC",
           parameter="operating_voltage_v", operator=">=", value=12, unit="V DC"),
    Clause(reference="2.3.B", text="Quiescent current shall not exceed 0.5 mA",
           parameter="quiescent_current_ma", operator="<=", value=0.5, unit="mA"),
    Clause(reference="2.4.A", text="Finish shall be agreed with the architect")],
  captured_specs={"operating_voltage_v":24.0,"quiescent_current_ma":0.9},
  spec_source="Siemens capture, migration 0020", output_key="compliance.docx"), st)
print(f"    {cs.status} | {cs.outputs['counts']}")

step(7,"word.fill_template (submittal cover)")
vals = {"project_name":"Riyadh Commercial Tower","project_number":"RYD-001",
        "package":"Fire Alarm","spec_section":"28 31 00","date":"2026-10-23",
        "revision":"03","manufacturer":"Siemens","product_model":"FDO221",
        "prepared_by":"A. Engineer"}
fc = fill_template(FillInput(template_key="templates/submittal_cover.docx",
      values=vals, output_key="cover.docx"), st)
print(f"    {fc.status} | {fc.files[0].byte_size} bytes")

step(8,"word.to_pdf x2 (LibreOffice)")
for n in ("cover","compliance"):
    p = to_pdf(ToPdfInput(storage_key=f"{n}.docx", output_key=f"{n}.pdf"), st)
    print(f"    {n}.pdf {p.status} | {p.files[0].byte_size} bytes | {p.duration_ms} ms")

step(9,"pdf.pack (merge + stamp)")
pk = pack(PackInput(storage_keys=["cover.pdf","compliance.pdf"],
      stamp=StampSpec(text="RYD-001  Rev 03  -  FOR APPROVAL"),
      output_key="SUBMITTAL.pdf", output_name="Submittal_RYD-001_Rev03.pdf"), st)
print(f"    {pk.status} | {pk.outputs['page_count']} pages | {pk.files[0].byte_size} bytes")

step(10,"pdf.extract (read the result back)")
ex = extract(ExtractInput(document_id="pk", storage_key="SUBMITTAL.pdf"), st)
print(f"    {ex.status} | {ex.outputs['pages_read']} pages | {ex.outputs['table_count']} table(s)")
txt = "\n".join(p["text"] for p in ex.outputs["pages"])
checks = [("cover title","Material Submittal"),("compliance title","Compliance Statement"),
          ("project","Riyadh Commercial Tower"),("verdict Comply","Comply"),
          ("verdict Deviate","Deviate"),("deviation figures","0.9"),
          ("provenance","Siemens capture"),("caveat","not a submittal until signed"),
          ("stamp p1","Page 1 of 2"),("stamp p2","Page 2 of 2")]
for label, needle in checks:
    print(f"      {'PASS' if needle in txt else 'FAIL':<5} {label}")
assert all(n in txt for _, n in checks)

os.makedirs("../out", exist_ok=True)
for k, nm in (("BOQ.xlsx","E2E_BOQ_RYD-001_Rev03.xlsx"),
              ("SUBMITTAL.pdf","E2E_Submittal_RYD-001_Rev03.pdf")):
    open(f"../out/{nm}","wb").write(st.read(k))
print(f"\nwritten: out/E2E_BOQ_RYD-001_Rev03.xlsx, out/E2E_Submittal_RYD-001_Rev03.pdf")
print("END-TO-END CHAIN COMPLETE")
