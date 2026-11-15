// ECharts, imported module by module so the bundle only carries what the views use.
// Chart library decision (Phase 1): ECharts. Chart.js (used in the Finland vs EU
// dashboard) has no treemap; ECharts also covers the Sankey view planned for later.
import * as echarts from "echarts/core";
import { BarChart, LineChart, TreemapChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { eur, eurExact, pct } from "./format";
import type { Item } from "./data";

echarts.use([BarChart, LineChart, TreemapChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

// Colour-blind-safe pair (Okabe-Ito): blue for traced, grey for not traced.
export const COLOR = { traced: "#0072B2", untraced: "#9aa3ad", series: ["#0072B2", "#D55E00", "#009E73", "#CC79A7"] };

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const text = () => ({ color: css("--text"), fontFamily: "inherit" });

const live = new Set<echarts.ECharts>();

export function mount(el: HTMLElement, option: echarts.EChartsCoreOption): echarts.ECharts {
  const chart = echarts.init(el, undefined, { renderer: "canvas" });
  chart.setOption({ textStyle: text(), animation: false, ...option });
  live.add(chart);
  return chart;
}

export function disposeAll(): void {
  for (const c of live) c.dispose();
  live.clear();
}

addEventListener("resize", () => live.forEach((c) => c.resize()));

/** Treemap of spending: parent = main class, leaf = budget item. Blue share = traced. */
export function treemap(el: HTMLElement, items: Item[], onOpen: (momentti: string) => void): void {
  const groups = new Map<string, { name: string; children: unknown[] }>();
  for (const it of items) {
    const g = groups.get(it.paaluokka) ?? { name: it.paaluokka_name, children: [] };
    g.children.push({
      name: it.name,
      value: it.actual_eur,
      momentti: it.momentti,
      traced: it.traced_share,
      itemStyle: { color: tracedColor(it.traced_share) },
    });
    groups.set(it.paaluokka, g);
  }
  const chart = mount(el, {
    tooltip: {
      formatter: (p: { name: string; value: number; data: { traced?: number } }) =>
        `<b>${escapeHtml(p.name)}</b><br/>${eurExact(p.value)}` +
        (p.data.traced !== undefined ? `<br/>${pct(Math.min(p.data.traced, 1))}` : ""),
    },
    series: [
      {
        type: "treemap",
        roam: false,
        nodeClick: "link",
        breadcrumb: { show: false },
        label: { show: true, formatter: "{b}", overflow: "truncate", color: "#10151a" },
        upperLabel: { show: true, height: 22, color: "#10151a" },
        itemStyle: { borderColor: css("--bg"), borderWidth: 1, gapWidth: 1 },
        levels: [
          { itemStyle: { borderWidth: 0, gapWidth: 3 } },
          { itemStyle: { gapWidth: 1, borderColorSaturation: 0.4 } },
        ],
        data: [...groups.values()],
      },
    ],
  });
  chart.on("click", (p) => {
    const m = (p.data as { momentti?: string }).momentti;
    if (m) onOpen(m);
  });
}

// Lighter grey to full blue by traced share. Untraced items stay a neutral light grey.
function tracedColor(share: number): string {
  const s = Math.max(0, Math.min(1, share));
  const mix = (a: number, b: number) => Math.round(a + (b - a) * s);
  return `rgb(${mix(207, 0)},${mix(212, 114)},${mix(218, 178)})`;
}

export function barsByYear(el: HTMLElement, years: number[], series: { name: string; data: number[] }[]): void {
  mount(el, {
    tooltip: { trigger: "axis", valueFormatter: (v: number) => eurExact(v) },
    legend: { bottom: 0, textStyle: text() },
    grid: { left: 8, right: 8, top: 16, bottom: 36, containLabel: true },
    xAxis: { type: "category", data: years.map(String) },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => eur(v) } },
    color: COLOR.series,
    series: series.map((s) => ({ type: "bar", name: s.name, data: s.data })),
  });
}

export function lineByYear(el: HTMLElement, years: number[], name: string, data: number[]): void {
  mount(el, {
    tooltip: { trigger: "axis", valueFormatter: (v: number) => eurExact(v) },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: years.map(String) },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => eur(v) } },
    color: COLOR.series,
    series: [{ type: "line", name, data, symbolSize: 8 }],
  });
}

export function horizontalBars(el: HTMLElement, rows: { name: string; value: number }[]): void {
  const sorted = [...rows].sort((a, b) => a.value - b.value);
  mount(el, {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: number) => eurExact(v) },
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "value", axisLabel: { formatter: (v: number) => eur(v) } },
    yAxis: { type: "category", data: sorted.map((r) => r.name) },
    color: [COLOR.traced],
    series: [{ type: "bar", data: sorted.map((r) => r.value) }],
  });
}

export const escapeHtml = (s: string): string =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
