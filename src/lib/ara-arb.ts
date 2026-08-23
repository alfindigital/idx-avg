import { getTickSize } from "@/lib/idx-tick";

/**
 * Batas Auto Rejection IDX (pasar reguler).
 *
 * ARA (Auto Rejection Atas) bertingkat berdasarkan harga penutupan sebelumnya:
 *   Rp50 – Rp200        -> 35%
 *   > Rp200 – Rp5.000   -> 25%
 *   > Rp5.000           -> 20%
 * ARB (Auto Rejection Bawah): 15% untuk semua rentang harga.
 *
 * Hasil disesuaikan ke fraksi harga (tick size): ARA dibulatkan ke bawah dan
 * ARB dibulatkan ke atas agar tidak melampaui persentase batas bursa.
 */

export const MIN_PRICE = 50;

export interface AraArbResult {
  /** Harga penutupan acuan (prev close). */
  base: number;
  /** Persentase ARA yang berlaku untuk rentang harga ini (mis. 0.35). */
  araPct: number;
  /** Persentase ARB (0.15). */
  arbPct: number;
  /** Harga batas atas, sudah disesuaikan tick. */
  ara: number;
  /** Harga batas bawah, sudah disesuaikan tick. */
  arb: number;
  /** Label rentang harga untuk ditampilkan. */
  tierLabel: string;
}

export function getAraPct(prevClose: number): number {
  if (prevClose <= 200) return 0.35;
  if (prevClose <= 5000) return 0.25;
  return 0.2;
}

export function getTierLabel(prevClose: number): string {
  if (prevClose <= 200) return "Rp50 – Rp200";
  if (prevClose <= 5000) return "> Rp200 – Rp5.000";
  return "> Rp5.000";
}

function floorToTick(price: number): number {
  const t = getTickSize(price);
  return Math.floor(price / t) * t;
}

function ceilToTick(price: number): number {
  const t = getTickSize(price);
  return Math.ceil(price / t) * t;
}

export function calcAraArb(prevClose: number): AraArbResult | null {
  if (!isFinite(prevClose) || prevClose < MIN_PRICE) return null;
  const araPct = getAraPct(prevClose);
  const arbPct = 0.15;
  const ara = floorToTick(prevClose * (1 + araPct));
  const arb = Math.max(MIN_PRICE, ceilToTick(prevClose * (1 - arbPct)));
  return { base: prevClose, araPct, arbPct, ara, arb, tierLabel: getTierLabel(prevClose) };
}
