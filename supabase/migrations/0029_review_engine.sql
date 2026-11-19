-- 0029_review_engine
--
-- Review: drawings, specifications and client BOQs checked against each other
-- and against SPI's rules (engines/craft/review). Its runs are craft
-- operations like any other, so the engine needs its enum value. Nothing else
-- changes: a review writes a workbook and a marked-up drawing as new documents,
-- and its quantities stay proposals until a person promotes them.
--
-- ADD VALUE cannot be used in the transaction that adds it, so it runs alone.

alter type craft_engine add value if not exists 'review';

comment on type craft_engine is
  'Which craft engine ran. grid=xlsx, word=docx/pdf, cad=dxf, pdf=pdf, bim=ifc, '
  'review=drawing/spec/BOQ cross-check.';
