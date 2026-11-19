-- 0026_bim_engine
--
-- BIMCraft: the fifth craft engine. It reads IFC models — what Revit, ArchiCAD
-- and every other BIM tool export to — and counts devices, lists rooms and
-- builds the scene the ELV simulator shows (docs/decisions/0002-bim-engine.md).
--
-- craft_operations.engine is an enum, so recording a bim.* run needs the value.
-- Nothing else changes: BIM counts land in drawing_objects as 'imported' and
-- 'pending', exactly like CAD counts, and are promoted by the existing review.
--
-- ADD VALUE cannot be used in the transaction that adds it. Each statement in
-- these migrations runs on its own, so the check below is a separate statement.

alter type craft_engine add value if not exists 'bim';

comment on type craft_engine is
  'Which craft engine ran. grid=xlsx, word=docx/pdf, cad=dxf, pdf=pdf, bim=ifc.';

do $$
begin
  if not exists (select 1 from pg_enum e join pg_type t on t.oid = e.enumtypid
                  where t.typname = 'craft_engine' and e.enumlabel = 'bim') then
    raise exception 'craft_engine has no bim value';
  end if;
  raise notice 'craft_engine now includes bim.';
end $$;
