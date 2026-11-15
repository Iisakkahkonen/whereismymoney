// DuckDB-WASM over the Parquet files the pipeline built. The files are tiny at
// this stage, so they are loaded into memory instead of fetched with range
// requests; Phase 5 (supplier invoices) is where that choice gets revisited.
import * as duckdb from "@duckdb/duckdb-wasm";
import ehWasm from "@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url";
import ehWorker from "@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url";

const FILES = ["budget_items", "kela", "coverage"] as const;

let connection: Promise<duckdb.AsyncDuckDBConnection> | null = null;

export const dataUrl = (name: string): string => new URL(`data/${name}`, document.baseURI).href;

async function open(): Promise<duckdb.AsyncDuckDBConnection> {
  const worker = new Worker(ehWorker);
  const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker);
  await db.instantiate(ehWasm);
  for (const f of FILES) {
    const res = await fetch(dataUrl(`${f}.parquet`));
    if (!res.ok) throw new Error(`${f}.parquet: HTTP ${res.status}`);
    await db.registerFileBuffer(`${f}.parquet`, new Uint8Array(await res.arrayBuffer()));
  }
  const conn = await db.connect();
  for (const f of FILES) await conn.query(`CREATE VIEW ${f} AS SELECT * FROM read_parquet('${f}.parquet')`);
  return conn;
}

export function conn(): Promise<duckdb.AsyncDuckDBConnection> {
  connection ??= open();
  return connection;
}

/** Run a query and return plain JS rows (BigInt counts become numbers). */
export async function rows<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  const c = await conn();
  const table = await c.query(sql);
  return table.toArray().map((r) => {
    const o: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(r.toJSON())) o[k] = typeof v === "bigint" ? Number(v) : v;
    return o as T;
  });
}
