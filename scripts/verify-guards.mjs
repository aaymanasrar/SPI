#!/usr/bin/env node
// Verifies that the database actually enforces the guarantees the schema
// claims — that the triggers and constraints fire, not merely that they exist.
//
// Every fixture is created and then rolled back by a deliberate exception at
// the end, so the database is left exactly as it was found.
//
// Usage: node scripts/verify-guards.mjs

import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const env = {};
for (const line of readFileSync(join(root, ".env"), "utf8").split("\n")) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
  if (m) env[m[1]] = m[2].trim().replace(/^["']|["']$/g, "");
}

const token = process.env.SUPABASE_ACCESS_TOKEN || env.SUPABASE_ACCESS_TOKEN;
const ref = process.env.SUPABASE_PROJECT_REF || env.SUPABASE_PROJECT_REF;
if (!token || !ref) {
  console.error("Need SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF in .env");
  process.exit(1);
}

const sql = `
do $guard$
declare
  org uuid; proj uuid; b_app uuid; b_dft uuid; r text := '';
begin
  insert into organizations(name,slug) values('__guard','__guard') returning id into org;
  insert into projects(organization_id,name) values(org,'__guard') returning id into proj;
  insert into boqs(project_id,revision,status) values(proj,1,'approved') returning id into b_app;
  insert into boqs(project_id,revision,status) values(proj,2,'draft')    returning id into b_dft;

  begin
    update boqs set status='draft' where id=b_app;
    r := r || ' FAIL: approved BOQ was editable |';
  exception when others then r := r || ' pass: approved BOQ is immutable |';
  end;

  begin
    insert into boq_items(boq_id,description,unit,quantity,quantity_source)
      values(b_app,'x','ea',1,'manual');
    r := r || ' FAIL: line added to approved BOQ |';
  exception when others then r := r || ' pass: approved BOQ rejects new lines |';
  end;

  begin
    insert into boq_items(boq_id,description,unit,quantity,quantity_source)
      values(b_dft,'x','ea',10,'rule_execution');
    r := r || ' FAIL: rule quantity accepted with no execution |';
  exception when others then r := r || ' pass: rule quantity needs a rule execution |';
  end;

  begin
    execute 'insert into boq_items(boq_id,description,unit,quantity,quantity_source)
             values($1,''x'',''ea'',1000,''ai_proposal'')' using b_dft;
    r := r || ' FAIL: AI-inferred quantity accepted |';
  exception when others then r := r || ' pass: ai_proposal is not a valid quantity_source |';
  end;

  begin
    insert into boq_items(boq_id,description,unit,quantity,quantity_source,unit_cost_minor)
      values(b_dft,'x','ea',1,'manual',50000);
    r := r || ' FAIL: cost accepted with no price source |';
  exception when others then r := r || ' pass: cost requires a price source |';
  end;

  begin
    insert into cable_routes(project_id,system_id,length_basis,length_m)
      values(proj,(select id from systems where code='cctv'),'unknown',1000);
    r := r || ' FAIL: cable length accepted with unknown basis |';
  exception when others then r := r || ' pass: cable length requires a stated basis |';
  end;

  begin
    insert into audit_logs(action) values('x');
    update audit_logs set action='tampered' where action='x';
    r := r || ' FAIL: audit_logs was mutable |';
  exception when others then r := r || ' pass: audit_logs is append-only |';
  end;

  begin
    insert into boq_items(boq_id,description,unit,quantity,quantity_source)
      values(b_dft,'legit','ea',5,'manual');
    r := r || ' pass: legitimate write on a draft BOQ succeeds |';
  exception when others then r := r || ' FAIL: legitimate write was blocked |';
  end;

  -- Aborts the statement, rolling back every fixture above.
  raise exception '%', r;
end $guard$;
`;

const res = await fetch(
  `https://api.supabase.com/v1/projects/${ref}/database/query`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query: sql }),
  }
);

const body = await res.text();
const results = (body.match(/(pass|FAIL):[^|]+/g) || []).map((s) => s.trim());

if (!results.length) {
  console.error("Could not read results:\n" + body.slice(0, 800));
  process.exit(1);
}

console.log(`Guard verification against ${ref}\n`);
for (const line of results) console.log(`  ${line}`);

const failures = results.filter((r) => r.startsWith("FAIL"));
console.log(
  `\n${results.length - failures.length}/${results.length} passed` +
    (failures.length ? " — FAILURES PRESENT" : ". All fixtures rolled back.")
);
process.exit(failures.length ? 1 : 0);
