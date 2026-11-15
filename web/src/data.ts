import { dataUrl, rows } from "./db";

export interface Manifest {
  generated_at: string;
  years: number[];
  reconciliation_tolerance: number;
  reconciliation: { year: number; benefit: string; treasury_eur: number; kela_eur: number; difference: number }[];
  benefits: { key: string; momentti: string; name_fi: string; name_en: string; source_url: string }[];
  sources: { id: string; name: string; url: string; licence: string; attribution?: string }[];
  kela_files: { benefit: string; year: number; source_url: string; sha256: string; retrieved_at: string }[];
}

export interface SearchDoc {
  id: string;
  type: "budget" | "benefit";
  title: string;
  title_en?: string;
  code: string;
  group: string;
  momentti: string;
  text: string;
}

export interface Item {
  year: number;
  momentti: string;
  code: string;
  name: string;
  paaluokka: string;
  paaluokka_name: string;
  hallinnonala: string;
  side: string;
  budget_eur: number;
  actual_eur: number;
  traced_eur: number;
  untraced_eur: number;
  traced_share: number;
  reported_eur: number;
  note: string;
  source: string;
}

export async function loadManifest(): Promise<Manifest> {
  const res = await fetch(dataUrl("manifest.json"));
  if (!res.ok) throw new Error(`manifest.json: HTTP ${res.status}`);
  return res.json();
}

export async function loadSearchIndex(): Promise<SearchDoc[]> {
  const res = await fetch(dataUrl("search_index.json"));
  if (!res.ok) throw new Error(`search_index.json: HTTP ${res.status}`);
  return res.json();
}

// momentti and year come from the URL, so they are validated before reaching SQL.
const digits = (s: string): string => {
  if (!/^\d{4,9}$/.test(s)) throw new Error("bad budget item id");
  return s;
};
const yearNum = (y: number): number => {
  if (!Number.isInteger(y) || y < 1990 || y > 2100) throw new Error("bad year");
  return y;
};

const ITEM_SQL = `
  SELECT b.year, b.momentti, b.code, b.name, b.paaluokka, b.paaluokka_name, b.hallinnonala, b.side,
         b.budget_eur, b.actual_eur, c.traced_eur, c.untraced_eur, c.traced_share, c.reported_eur, c.note, c.source
  FROM budget_items b JOIN coverage c USING (year, momentti)`;

export const spendingItems = (year: number) =>
  rows<Item>(`${ITEM_SQL} WHERE b.year = ${yearNum(year)} AND b.side = 'expenditure' AND b.actual_eur > 0`);

export const item = async (momentti: string, year: number): Promise<Item | undefined> =>
  (await rows<Item>(`${ITEM_SQL} WHERE b.momentti = '${digits(momentti)}' AND b.year = ${yearNum(year)}`))[0];

export const itemTrend = (momentti: string) =>
  rows<{ year: number; actual_eur: number; traced_eur: number }>(
    `SELECT b.year, b.actual_eur, c.traced_eur FROM budget_items b JOIN coverage c USING (year, momentti)
     WHERE b.momentti = '${digits(momentti)}' ORDER BY b.year`,
  );

export const totals = async (year: number) =>
  (
    await rows<{ actual: number; traced: number }>(
      `SELECT SUM(b.actual_eur) AS actual, SUM(c.traced_eur) AS traced
       FROM budget_items b JOIN coverage c USING (year, momentti)
       WHERE b.year = ${yearNum(year)} AND b.side = 'expenditure' AND b.actual_eur > 0`,
    )
  )[0];

export const tracedItems = (year: number) =>
  rows<Item>(`${ITEM_SQL} WHERE b.year = ${yearNum(year)} AND c.traced_eur > 0 ORDER BY b.actual_eur DESC`);

export const kelaTotals = () =>
  rows<{ year: number; benefit: string; paid_eur: number }>(
    `SELECT year, benefit, paid_eur FROM kela WHERE dimension = 'total' ORDER BY benefit, year`,
  );

export const kelaBreakdown = (benefit: string, dimension: string, year: number) =>
  rows<{ category: string; paid_eur: number }>(
    `SELECT category, paid_eur FROM kela
     WHERE benefit = '${benefit.replace(/[^a-z_]/g, "")}' AND dimension = '${dimension.replace(/[^a-z_]/g, "")}'
       AND year = ${yearNum(year)} ORDER BY paid_eur DESC`,
  );

export const kelaUnknown = async (benefit: string, year: number): Promise<number> =>
  (
    await rows<{ paid_eur: number }>(
      `SELECT paid_eur FROM kela WHERE benefit = '${benefit.replace(/[^a-z_]/g, "")}'
       AND dimension = 'unknown_municipality' AND year = ${yearNum(year)}`,
    )
  )[0]?.paid_eur ?? 0;

export const treasuryCsvUrl = (momentti: string, year: number): string =>
  `https://api.tutkihallintoa.fi/valtiontalous/v1/budjettitaloudentapahtumat?momentti=${digits(momentti)}&yearFrom=${yearNum(year)}&yearTo=${yearNum(year)}`;
