// All UI text, English and Finnish side by side. scripts/check-i18n.mjs fails the
// build if a key exists in one language and not the other (EN/FI parity rule).
// Data names (budget items, organisations) stay in Finnish, as published.

export type Lang = "en" | "fi";

export const dict = {
  en: {
    "app.title": "Where is my money?",
    "app.tagline": "Where Finland's public money goes, and how much of it can be traced in public data.",
    "nav.overview": "Overview",
    "nav.sources": "Sources and method",
    "nav.language": "Language",
    "year.label": "Year",
    "search.label": "Search budget items and benefits",
    "search.placeholder": "Search, for example housing allowance or asumistuki",
    "search.none": "Nothing found",
    "search.results": "Search results",
    "type.budget": "Budget item",
    "type.benefit": "Benefit",
    "loading": "Loading data…",
    "error.load": "The data could not be loaded.",
    "overview.spent": "State budget spending in {year}",
    "overview.spent.note": "Actual amounts booked by the State Treasury, all main classes of expenditure.",
    "overview.traced": "Traced in public data",
    "overview.untraced": "Not traced in public data",
    "overview.traced.note": "Money matched to a source that shows where it went. Today this is Kela's housing allowance and student aid only.",
    "overview.treemap": "Where the state spent its money",
    "overview.treemap.help": "Each box is a budget item, sized by actual spending. Blue shows the traced share; grey is not traced in public data. Click a box to open it.",
    "overview.traced.items": "Items with a traced amount",
    "overview.compare": "Benefits compared",
    "overview.compare.help": "Paid out according to Kela, calendar years.",
    "item.back": "Back to overview",
    "item.code": "Budget item",
    "item.group": "Administrative branch",
    "item.budget": "Budget",
    "item.actual": "Actual",
    "item.actual.help": "Booked by the State Treasury for the year.",
    "item.budget.help": "Valid budget including supplementary budgets.",
    "item.trend": "Actual spending by year",
    "item.coverage": "Coverage",
    "item.coverage.none": "No public source traces where this money went. All of it is shown as not traced.",
    "item.coverage.traced": "traced",
    "item.coverage.untraced": "not traced",
    "item.coverage.diff.below": "Kela reports {traced} paid out against {actual} booked by the Treasury. The difference of {gap} is shown as not traced.",
    "item.coverage.diff.above": "Kela reports {traced}, which is {gap} more than the {actual} booked by the Treasury. The two sources are measured differently and are not forced to match.",
    "item.breakdown.elamantilanne": "Paid by household life situation",
    "item.breakdown.etuus": "Paid by type of aid",
    "item.breakdown.oppilaitosaste": "Paid by school level",
    "item.unknown": "Not assigned to a municipality (groups under four people, or missing), net of refunds",
    "item.sources": "Sources for this page",
    "item.source.treasury": "Treasury data for this item and year (CSV)",
    "item.source.kela": "Kela dataset description",
    "unit.m": "{n} m€",
    "unit.bn": "{n} bn€",
    "sources.title": "Sources and method",
    "sources.intro": "Every number on this site comes from an open dataset. This page lists them, what is not covered, and how the coverage meter works.",
    "sources.datasets": "Datasets",
    "sources.treasury": "State budget and actuals: State Treasury, Valtion talous API.",
    "sources.kela": "Housing allowance and student aid: Kela open statistics (Kelasto).",
    "sources.attribution": "Source: Kela (Kelasto), licensed CC BY 4.0.",
    "sources.coverage.title": "How the coverage meter works",
    "sources.coverage.text": "Each budget item shows its actual spending and how much of it is matched to a source that says where the money went. The rest is shown as not traced in public data. Nothing is estimated or filled in.",
    "sources.gaps.title": "What is not covered",
    "sources.gaps.text": "Most of the budget is not traced yet: this first version traces two Kela benefits only. Grants, supplier payments and municipal and wellbeing county spending are planned. Individual-level payments and confidential purchases are not published.",
    "sources.diff.title": "Why the Treasury and Kela totals differ slightly",
    "sources.diff.text": "The two sources count in different ways. The difference is about 1 percent. It is shown, not hidden.",
    "sources.generated": "Data built",
    "footer.text": "Open source. Data: State Treasury and Kela (CC BY 4.0).",
  },
  fi: {
    "app.title": "Mihin rahani menevät?",
    "app.tagline": "Mihin Suomen julkinen raha menee, ja kuinka suuri osa siitä voidaan jäljittää julkisesta datasta.",
    "nav.overview": "Yleiskuva",
    "nav.sources": "Lähteet ja menetelmä",
    "nav.language": "Kieli",
    "year.label": "Vuosi",
    "search.label": "Hae budjettikohtia ja etuuksia",
    "search.placeholder": "Hae, esimerkiksi asumistuki tai housing allowance",
    "search.none": "Ei tuloksia",
    "search.results": "Hakutulokset",
    "type.budget": "Budjettikohta",
    "type.benefit": "Etuus",
    "loading": "Ladataan tietoja…",
    "error.load": "Tietoja ei voitu ladata.",
    "overview.spent": "Valtion budjetin menot vuonna {year}",
    "overview.spent.note": "Valtiokonttorin kirjaamat toteutuneet määrät, kaikki menojen pääluokat.",
    "overview.traced": "Jäljitetty julkisessa datassa",
    "overview.untraced": "Ei jäljitetty julkisessa datassa",
    "overview.traced.note": "Raha, joka on yhdistetty lähteeseen, joka kertoo minne se meni. Tällä hetkellä vain Kelan asumistuki ja opintotuki.",
    "overview.treemap": "Mihin valtio käytti rahansa",
    "overview.treemap.help": "Jokainen laatikko on budjettikohta, koko kuvaa toteutunutta menoa. Sininen on jäljitetty osuus, harmaa ei ole jäljitetty julkisessa datassa. Avaa kohta klikkaamalla.",
    "overview.traced.items": "Kohdat, joissa on jäljitetty osuus",
    "overview.compare": "Etuuksien vertailu",
    "overview.compare.help": "Maksettu Kelan mukaan, kalenterivuodet.",
    "item.back": "Takaisin yleiskuvaan",
    "item.code": "Budjettikohta",
    "item.group": "Hallinnonala",
    "item.budget": "Budjetti",
    "item.actual": "Toteutuma",
    "item.actual.help": "Valtiokonttorin kirjaama vuoden toteutuma.",
    "item.budget.help": "Voimassa oleva budjetti lisätalousarviot mukaan lukien.",
    "item.trend": "Toteutunut meno vuosittain",
    "item.coverage": "Kattavuus",
    "item.coverage.none": "Mikään julkinen lähde ei kerro minne tämä raha meni. Koko määrä näytetään jäljittämättömänä.",
    "item.coverage.traced": "jäljitetty",
    "item.coverage.untraced": "ei jäljitetty",
    "item.coverage.diff.below": "Kela raportoi maksetuksi {traced}, kun Valtiokonttori on kirjannut {actual}. Ero {gap} näytetään jäljittämättömänä.",
    "item.coverage.diff.above": "Kela raportoi {traced}, eli {gap} enemmän kuin Valtiokonttorin kirjaama {actual}. Lähteet mittaavat eri tavoin, eikä niitä pakoteta täsmäämään.",
    "item.breakdown.elamantilanne": "Maksettu ruokakunnan elämäntilanteen mukaan",
    "item.breakdown.etuus": "Maksettu etuuslajin mukaan",
    "item.breakdown.oppilaitosaste": "Maksettu oppilaitosasteen mukaan",
    "item.unknown": "Ei kohdistettu kuntaan (alle neljän henkilön ryhmät tai tieto puuttuu), palautusten jälkeen",
    "item.sources": "Tämän sivun lähteet",
    "item.source.treasury": "Valtiokonttorin tiedot tästä kohdasta ja vuodesta (CSV)",
    "item.source.kela": "Kelan aineiston kuvaus",
    "unit.m": "{n} milj. €",
    "unit.bn": "{n} mrd. €",
    "sources.title": "Lähteet ja menetelmä",
    "sources.intro": "Jokainen tämän sivuston luku tulee avoimesta aineistosta. Tällä sivulla luetellaan aineistot, mitä ei kata ja miten kattavuusmittari toimii.",
    "sources.datasets": "Aineistot",
    "sources.treasury": "Valtion budjetti ja toteutuma: Valtiokonttori, Valtion talous -rajapinta.",
    "sources.kela": "Asumistuki ja opintotuki: Kelan avoin tilasto (Kelasto).",
    "sources.attribution": "Lähde: Kela (Kelasto), lisenssi CC BY 4.0.",
    "sources.coverage.title": "Miten kattavuusmittari toimii",
    "sources.coverage.text": "Jokaisessa budjettikohdassa näytetään toteutunut meno ja kuinka suuri osa siitä on yhdistetty lähteeseen, joka kertoo minne raha meni. Loppu näytetään jäljittämättömänä julkisessa datassa. Mitään ei arvioida eikä täytetä.",
    "sources.gaps.title": "Mitä ei katettu",
    "sources.gaps.text": "Suurin osa budjetista on vielä jäljittämättä: tämä ensimmäinen versio jäljittää vain kaksi Kelan etuutta. Avustukset, toimittajamaksut sekä kuntien ja hyvinvointialueiden menot ovat suunnitelmissa. Yksilötason maksuja ja salassa pidettäviä hankintoja ei julkaista.",
    "sources.diff.title": "Miksi Valtiokonttorin ja Kelan summat poikkeavat vähän",
    "sources.diff.text": "Lähteet laskevat eri tavoin. Ero on noin yksi prosentti. Se näytetään, ei piiloteta.",
    "sources.generated": "Data rakennettu",
    "footer.text": "Avoin lähdekoodi. Data: Valtiokonttori ja Kela (CC BY 4.0).",
  },
} as const satisfies Record<Lang, Record<string, string>>;

export type Key = keyof (typeof dict)["en"];

let current: Lang = "en";

export function initLang(): Lang {
  let saved: string | null = null;
  try {
    saved = localStorage.getItem("lang");
  } catch {
    /* storage can be blocked; the page works without it */
  }
  current = saved === "fi" || saved === "en" ? saved : navigator.language.toLowerCase().startsWith("fi") ? "fi" : "en";
  document.documentElement.lang = current;
  return current;
}

export function setLang(l: Lang): void {
  current = l;
  document.documentElement.lang = l;
  try {
    localStorage.setItem("lang", l);
  } catch {
    /* ignore */
  }
}

export const lang = (): Lang => current;

export function t(key: Key, vars: Record<string, string | number> = {}): string {
  let s: string = dict[current][key];
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}
