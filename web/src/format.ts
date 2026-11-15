import { lang, t } from "./i18n";

const locale = () => (lang() === "fi" ? "fi-FI" : "en-GB");

/** Euro amount in a short readable form: 1.7 bn€, 515.5 m€, or the plain number below a million. */
export function eur(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "−" : "";
  const fmt = (n: number, digits: number) => new Intl.NumberFormat(locale(), { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n);
  if (abs >= 1e9) return sign + t("unit.bn", { n: fmt(abs / 1e9, 2) });
  if (abs >= 1e6) return sign + t("unit.m", { n: fmt(abs / 1e6, 1) });
  return sign + new Intl.NumberFormat(locale(), { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(abs);
}

/** Exact amount for tooltips and tables. */
export function eurExact(value: number): string {
  return new Intl.NumberFormat(locale(), { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
}

export function pct(share: number, digits = 1): string {
  return new Intl.NumberFormat(locale(), { style: "percent", maximumFractionDigits: digits, minimumFractionDigits: digits }).format(share);
}
