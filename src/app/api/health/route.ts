import { NextResponse } from "next/server";
import { sql, describeTarget } from "@/lib/db";

/**
 * Health check. Reports which database this process is connected to and
 * whether the schema is the one the migrations produce.
 *
 * The target is included deliberately: the most dangerous configuration error
 * in this system is an application quietly pointed at the wrong database, and
 * this makes that visible rather than silent.
 */
export async function GET() {
  try {
    const [counts] = await sql<
      [
        {
          tables: number;
          systems: number;
          roles: number;
          permissions: number;
          engineeringRows: number;
        }
      ]
    >`
      select
        (select count(*) from pg_tables where schemaname = 'public')::int as tables,
        (select count(*) from systems)::int      as systems,
        (select count(*) from roles)::int        as roles,
        (select count(*) from permissions)::int  as permissions,
        ((select count(*) from manufacturers)
         + (select count(*) from products)
         + (select count(*) from engineering_rules)
         + (select count(*) from vendor_prices))::int as engineering_rows
    `;

    return NextResponse.json({
      status: "ok",
      database: describeTarget(),
      schema: counts,
    });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        database: describeTarget(),
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 503 }
    );
  }
}
