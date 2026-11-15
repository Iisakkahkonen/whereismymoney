import MiniSearch from "minisearch";
import type { SearchDoc } from "./data";

let engine: MiniSearch<SearchDoc> | null = null;

export function buildSearch(docs: SearchDoc[]): void {
  engine = new MiniSearch<SearchDoc>({
    fields: ["title", "text"],
    storeFields: ["title", "title_en", "type", "code", "group", "momentti"],
    searchOptions: { prefix: true, fuzzy: 0.2, boost: { title: 3 }, combineWith: "AND" },
    // Lower-case and split on anything that is not a letter or digit, Finnish letters included.
    tokenize: (s) => s.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(Boolean),
  });
  engine.addAll(docs);
}

export function search(query: string, limit = 8) {
  if (!engine || query.trim().length < 2) return [];
  return engine.search(query.trim()).slice(0, limit) as unknown as (SearchDoc & { score: number })[];
}
