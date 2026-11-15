import "./style.css";
import { type Manifest, loadManifest, loadSearchIndex } from "./data";
import { conn } from "./db";
import { clear, h } from "./dom";
import { type Lang, initLang, lang, setLang, t } from "./i18n";
import { buildSearch, search } from "./search";
import { type Ctx, itemView, overview, resultRow, searchView, sourcesView } from "./views";

const app = document.getElementById("app")!;
let manifest: Manifest;

interface Route {
  view: "overview" | "item" | "sources" | "search";
  arg: string;
  year: number;
}

function parseRoute(): Route {
  const [path, qs = ""] = location.hash.replace(/^#/, "").split("?");
  const params = new URLSearchParams(qs);
  const latest = manifest.years[manifest.years.length - 1];
  const y = Number(params.get("year"));
  const year = manifest.years.includes(y) ? y : latest;
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "item" && parts[1]) return { view: "item", arg: parts[1], year };
  if (parts[0] === "sources") return { view: "sources", arg: "", year };
  if (parts[0] === "search") return { view: "search", arg: params.get("q") ?? "", year };
  return { view: "overview", arg: "", year };
}

const go = (hash: string) => {
  location.hash = hash;
};

function header(route: Route): HTMLElement {
  const yearSelect = h(
    "select",
    {
      id: "year",
      "aria-label": t("year.label"),
      onchange: (e) => {
        const y = (e.target as HTMLSelectElement).value;
        const base = location.hash.replace(/^#/, "").split("?")[0] || "/";
        const q = new URLSearchParams(location.hash.split("?")[1] ?? "");
        q.set("year", y);
        go(`#${base}?${q}`);
      },
    },
    ...manifest.years.map((y) => h("option", { value: y, selected: y === route.year }, String(y))),
  );
  const langBtn = (l: Lang, label: string) =>
    h("button", { class: "lang", type: "button", "aria-pressed": lang() === l, lang: l, onclick: () => { setLang(l); render(); } }, label);

  return h(
    "header",
    { class: "top" },
    h(
      "div",
      { class: "bar" },
      h("a", { class: "brand", href: `#/?year=${route.year}` }, t("app.title")),
      h(
        "nav",
        { "aria-label": "Main" },
        h("a", { href: `#/?year=${route.year}` }, t("nav.overview")),
        h("a", { href: `#/sources?year=${route.year}` }, t("nav.sources")),
      ),
      h(
        "div",
        { class: "controls" },
        h("label", { class: "year" }, h("span", { class: "visually-hidden" }, t("year.label")), yearSelect),
        h("div", { class: "langs", role: "group", "aria-label": t("nav.language") }, langBtn("en", "EN"), langBtn("fi", "FI")),
      ),
    ),
    h("p", { class: "tagline" }, t("app.tagline")),
    searchBox(route.year),
  );
}

function searchBox(year: number): HTMLElement {
  const input = h("input", {
    id: "search",
    type: "search",
    role: "combobox",
    autocomplete: "off",
    "aria-expanded": "false",
    "aria-controls": "suggestions",
    "aria-label": t("search.label"),
    placeholder: t("search.placeholder"),
  }) as HTMLInputElement;
  const list = h("ul", { id: "suggestions", role: "listbox", class: "suggestions", hidden: true });
  let active = -1;

  const close = () => {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    active = -1;
  };
  const paint = () => {
    [...list.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === active)));
  };
  const update = () => {
    const hits = search(input.value);
    clear(list);
    if (input.value.trim().length < 2) return close();
    if (!hits.length) list.append(h("li", { class: "none", role: "presentation" }, t("search.none")));
    for (const r of hits) {
      const li = h("li", { role: "option", "aria-selected": "false" }, resultRow(r, year).childNodes[0].cloneNode(true), h("span", { class: "muted" }, ` ${r.code}`));
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        close();
        input.value = "";
        go(`#/item/${r.momentti}?year=${year}`);
      });
      list.append(li);
    }
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    active = -1;
  };
  input.addEventListener("input", update);
  input.addEventListener("blur", close);
  input.addEventListener("keydown", (e) => {
    const n = list.children.length;
    if (e.key === "ArrowDown" && n) { e.preventDefault(); active = (active + 1) % n; paint(); }
    else if (e.key === "ArrowUp" && n) { e.preventDefault(); active = (active - 1 + n) % n; paint(); }
    else if (e.key === "Escape") close();
    else if (e.key === "Enter") {
      e.preventDefault();
      const q = input.value.trim();
      const hits = search(q);
      if (active >= 0 && hits[active]) go(`#/item/${hits[active].momentti}?year=${year}`);
      else if (q) go(`#/search?q=${encodeURIComponent(q)}&year=${year}`);
      close();
      input.value = "";
    }
  });
  return h("div", { class: "search" }, input, list);
}

function footer(): HTMLElement {
  return h("footer", { class: "foot" }, h("p", { class: "muted" }, t("footer.text")), h("p", { class: "muted" }, t("sources.attribution")));
}

async function render(): Promise<void> {
  const route = parseRoute();
  const ctx: Ctx = { manifest, year: route.year, go };
  const main = h("main", { id: "main", tabindex: "-1" }, h("p", { class: "muted" }, t("loading")));
  app.replaceChildren(header(route), main, footer());
  document.title = t("app.title");
  try {
    if (route.view === "item") await itemView(main, ctx, route.arg);
    else if (route.view === "sources") sourcesView(main, ctx);
    else if (route.view === "search") searchView(main, ctx, route.arg);
    else await overview(main, ctx);
    document.body.dataset.ready = route.view;
  } catch (e) {
    console.error(e);
    clear(main);
    main.append(h("p", { class: "error", role: "alert" }, t("error.load")));
    document.body.dataset.ready = "error";
  }
}

async function boot(): Promise<void> {
  initLang();
  app.append(h("p", { class: "muted pad" }, t("loading")));
  try {
    const [m, docs] = await Promise.all([loadManifest(), loadSearchIndex(), conn()]);
    manifest = m;
    buildSearch(docs);
  } catch (e) {
    console.error(e);
    app.replaceChildren(h("p", { class: "error pad", role: "alert" }, t("error.load")));
    document.body.dataset.ready = "error";
    return;
  }
  addEventListener("hashchange", () => void render());
  await render();
}

void boot();
