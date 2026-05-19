export function getTickSize(price: number): number {
  if (price < 200) return 1;
  if (price < 500) return 2;
  if (price < 2000) return 5;
  if (price < 5000) return 10;
  return 25;
}

export function roundToTick(price: number): number {
  const t = getTickSize(price);
  return Math.round(price / t) * t;
}

export function formatRupiah(num: number): string {
  if (!isFinite(num)) return "Rp 0";
  return "Rp " + new Intl.NumberFormat("id-ID").format(Math.round(num));
}

export function formatNumber(num: number): string {
  if (!isFinite(num)) return "0";
  return new Intl.NumberFormat("id-ID").format(Math.round(num));
}
