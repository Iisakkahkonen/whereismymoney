import { barsByYear, disposeAll, horizontalBars, lineByYear, treemap } from "./charts";
import {
  type Manifest, item, itemTrend, kelaBreakdown, kelaTotals, kelaUnknown, spendingItems, totals,
  tracedItems, treasuryCsvUrl,
} from "./data";
import { clear, h } from "./dom";
import { eur, eurExact, pct } from "./format";
import { lang, t } from "./i18n";
import { search } from "./search";

export interface Ctx {
  manifest: Manifest;
  year: number;
  go: (hash: string) => void;
}

const link = (href: string, label: string) => h("a", { href, target: "_blank", rel: "noopener noreferrer" }, label);

/** The coverage meter: traced share in blue, the rest grey. Never colour alone; the numbers are printed too. */
function meter(tracedEur: number, actualEur: number, share: number): HTMLElement {
  const width = Math.max(0, Math.min(1, share)) * 100;
  return h(
    "div",
    { class: "meter-wrap" },
    h(
      "div",
      { class: "meter", role: "img", "aria-label": `${t("item.coverage.traced")} ${pct(share)}` },
      h("div", { class: "meter-traced", style: `width:${width}%` }),
    ),
    h(
      "div",
      { class: "meter-legend" },
      h("span", { class: "dot traced" }),
      h("span", {}, `${t("overview.traced")}: ${eur(tracedEur)} (${pct(share)})`),
      h("span", { class: "dot untraced" }),
      h("span", {}, `${t("overview.untraced")}: ${eur(Math.max(0, actualEur - tracedEur))}`),
    ),
  );
}

export async function overview(root: HTMLElement, ctx: Ctx): Promise<void> {
  const [tot, items, traced, kela] = await Promise.all([totals(ctx.year), spendingItems(ctx.year), tracedItems(ctx.year), kelaTotals()]);
  const share = tot.actual > 0 ? tot.traced / tot.actual : 0;
  const names = new Map(ctx.manifest.benefits.map((b) => [b.key, lang() === "fi" ? b.name_fi : b.name_en]));

  const treemapEl = h("div", { class: "chart tall", id: "treemap", role: "img", "aria-label": t("overview.treemap") });
  const compareEl = h("div", { class: "chart", id: "compare", role: "img", "aria-label": t("overview.compare") });

  clear(root);
  root.append(
    h(
      "section",
      { class: "card hero" },
      h("h2", {}, t("overview.spent", { year: ctx.year })),
      h("p", { class: "big", id: "total-spent" }, eur(tot.actual)),
      meter(tot.traced, tot.actual, share),
      h("p", { class: "muted" }, t("overview.spent.note")),
      h("p", { class: "muted" }, t("overview.traced.note")),
    ),
    h("section", { class: "card" }, h("h2", {}, t("overview.treemap")), h("p", { class: "muted" }, t("overview.treemap.help")), treemapEl),
    h(
      "section",
      { class: "card" },
      h("h2", {}, t("overview.traced.items")),
      h(
        "ul",
        { class: "list", id: "traced-items" },
        ...traced.map((it) =>
          h(
            "li",
            {},
            h("a", { href: `#/item/${it.momentti}?year=${ctx.year}` }, it.name),
            h("span", { class: "muted" }, ` ${eur(it.actual_eur)} · ${pct(it.traced_share)} ${t("item.coverage.traced")}`),
          ),
        ),
      ),
    ),
    h("section", { class: "card" }, h("h2", {}, t("overview.compare")), h("p", { class: "muted" }, t("overview.compare.help")), compareEl),
  );

  disposeAll();
  treemap(treemapEl, items, (m) => ctx.go(`#/item/${m}?year=${ctx.year}`));
  const benefits = [...new Set(kela.map((k) => k.benefit))];
  barsByYear(
    compareEl,
    ctx.manifest.years,
    benefits.map((b) => ({
      name: names.get(b) ?? b,
      data: ctx.manifest.years.map((y) => kela.find((k) => k.benefit === b && k.year === y)?.paid_eur ?? 0),
    })),
  );
}

export async function itemView(root: HTMLElement, ctx: Ctx, momentti: string): Promise<void> {
  const [it, trend] = await Promise.all([item(momentti, ctx.year), itemTrend(momentti)]);
  if (!it) {
    clear(root);
    root.append(h("p", {}, t("search.none")), h("a", { href: `#/?year=${ctx.year}` }, t("item.back")));
    return;
  }
  const bene = ctx.manifest.benefits.find((b) => b.momentti === momentti);
  const title = bene ? (lang() === "fi" ? bene.name_fi : bene.name_en) : it.name;

  const sections: HTMLElement[] = [];
  const stat = (label: string, help: string, value: number) =>
    h("div", { class: "stat" }, h("span", { class: "muted" }, label), h("strong", { title: eurExact(value) }, eur(value)), h("span", { class: "muted small" }, help));
  sections.push(
    h(
      "section",
      { class: "card" },
      h("div", { class: "stats" }, stat(t("item.budget"), t("item.budget.help"), it.budget_eur), stat(t("item.actual"), t("item.actual.help"), it.actual_eur)),
    ),
  );

  const cov: HTMLElement[] = [h("h2", {}, t("item.coverage")), meter(it.traced_eur, it.actual_eur, it.traced_share)];
  if (it.traced_eur > 0 && bene) {
    const gap = Math.abs(it.actual_eur - it.traced_eur);
    const key = it.traced_eur <= it.actual_eur ? "item.coverage.diff.below" : "item.coverage.diff.above";
    cov.push(h("p", { class: "muted", id: "coverage-note" }, t(key, { traced: eur(it.traced_eur), actual: eur(it.actual_eur), gap: eur(gap) })));
  } else {
    cov.push(h("p", { class: "muted", id: "coverage-note" }, t("item.coverage.none")));
  }
  sections.push(h("section", { class: "card" }, ...cov));

  const trendEl = h("div", { class: "chart", role: "img", "aria-label": t("item.trend") });
  sections.push(h("section", { class: "card" }, h("h2", {}, t("item.trend")), trendEl));

  const breakdownEls: [string, HTMLElement, { name: string; value: number }[]][] = [];
  if (bene) {
    const dims = bene.key === "asumistuki" ? ["elamantilanne"] : ["etuus", "oppilaitosaste"];
    for (const d of dims) {
      const rows = (await kelaBreakdown(bene.key, d, ctx.year)).map((r) => ({ name: r.category, value: r.paid_eur }));
      const el = h("div", { class: "chart", role: "img", "aria-label": t(`item.breakdown.${d}` as never) });
      breakdownEls.push([d, el, rows]);
      sections.push(h("section", { class: "card" }, h("h2", {}, t(`item.breakdown.${d}` as never)), el));
    }
    const unknown = await kelaUnknown(bene.key, ctx.year);
    sections.push(h("p", { class: "muted" }, `${t("item.unknown")}: ${eur(unknown)}`));
  }

  const srcLinks = [h("li", {}, link(treasuryCsvUrl(momentti, ctx.year), t("item.source.treasury")))];
  if (bene) srcLinks.push(h("li", {}, link(bene.source_url, t("item.source.kela"))));
  sections.push(h("section", { class: "card" }, h("h2", {}, t("item.sources")), h("ul", { class: "list" }, ...srcLinks)));

  clear(root);
  root.append(
    h("a", { class: "back", href: `#/?year=${ctx.year}` }, `← ${t("item.back")}`),
    h("h1", { id: "item-title" }, title),
    h("p", { class: "muted" }, `${t("item.code")} ${it.code} · ${t("item.group")}: ${it.hallinnonala}`),
    ...sections,
  );
  disposeAll();
  lineByYear(trendEl, trend.map((r) => r.year), t("item.actual"), trend.map((r) => r.actual_eur));
  for (const [, el, rows] of breakdownEls) horizontalBars(el, rows);
  document.title = `${title} · ${t("app.title")}`;
}

export function searchView(root: HTMLElement, ctx: Ctx, query: string): void {
  const results = search(query, 30);
  clear(root);
  root.append(
    h("h1", {}, t("search.results")),
    results.length
      ? h("ul", { class: "list", id: "search-results" }, ...results.map((r) => resultRow(r, ctx.year)))
      : h("p", {}, t("search.none")),
  );
}

export function resultRow(r: { title: string; title_en?: string; type: string; code: string; group: string; momentti: string }, year: number): HTMLElement {
  const title = lang() === "en" && r.title_en ? r.title_en : r.title;
  return h(
    "li",
    {},
    h("a", { href: `#/item/${r.momentti}?year=${year}` }, title),
    h("span", { class: "muted" }, ` ${r.type === "benefit" ? t("type.benefit") : t("type.budget")} · ${r.code}`),
  );
}

export function sourcesView(root: HTMLElement, ctx: Ctx): void {
  clear(root);
  root.append(
    h("h1", {}, t("sources.title")),
    h("p", {}, t("sources.intro")),
    h(
      "section",
      { class: "card" },
      h("h2", {}, t("sources.datasets")),
      h(
        "ul",
        { class: "list" },
        ...ctx.manifest.sources.map((s) =>
          h("li", {}, link(s.url, s.name), h("span", { class: "muted" }, ` · ${s.licence}`)),
        ),
      ),
      h("p", { class: "muted" }, t("sources.attribution")),
    ),
    h("section", { class: "card" }, h("h2", {}, t("sources.coverage.title")), h("p", {}, t("sources.coverage.text"))),
    h("section", { class: "card" }, h("h2", {}, t("sources.gaps.title")), h("p", {}, t("sources.gaps.text"))),
    h("section", { class: "card" }, h("h2", {}, t("sources.diff.title")), h("p", {}, t("sources.diff.text"))),
    h("p", { class: "muted" }, `${t("sources.generated")}: ${ctx.manifest.generated_at}`),
  );
  document.title = `${t("sources.title")} · ${t("app.title")}`;
}
