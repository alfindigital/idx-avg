"use client";

import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, ArrowDown, ArrowUp, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { trackEvent } from "@/lib/analytics";
import { SiteFooter } from "@/components/site-footer";
import { TelegramPopup } from "@/components/telegram-popup";
import { formatRupiah } from "@/lib/idx-tick";
import { MIN_PRICE, calcAraArb } from "@/lib/ara-arb";

const THEME_KEY = "idxavg-theme";
const MAX_PRICE = 1_000_000;

// IDX prices are whole Rupiah — strip everything except digits so pasted
// strings like "Rp 1.500" or "12,500" normalize to plain integers.
const numOnly = (v: string) => v.replace(/[^\d]/g, "");

const TIERS = [
  { range: "Rp50 – Rp200", ara: "35%" },
  { range: "> Rp200 – Rp5.000", ara: "25%" },
  { range: "> Rp5.000", ara: "20%" },
];

export function AraArbCalculator() {
  const [isDark, setIsDark] = useState(false);
  const [price, setPrice] = useState("");
  const [touched, setTouched] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const th = localStorage.getItem(THEME_KEY);
    if (th === "dark") {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    }
    trackEvent("ara_arb_page_view");
    inputRef.current?.focus();
  }, []);

  const toggleTheme = () => {
    setIsDark((d) => {
      const next = !d;
      document.documentElement.classList.toggle("dark", next);
      try {
        localStorage.setItem(THEME_KEY, next ? "dark" : "light");
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const n = price ? parseFloat(price) : NaN;
  let error: string | null = null;
  if (price) {
    if (!isFinite(n) || n <= 0) error = "Harga harus lebih dari 0.";
    else if (n < MIN_PRICE) error = `Harga minimum saham IDX adalah ${formatRupiah(MIN_PRICE)}.`;
    else if (n > MAX_PRICE) error = `Harga maksimum ${formatRupiah(MAX_PRICE)}.`;
  }

  const result = error ? null : price ? calcAraArb(n) : null;
  const showError = touched && !!error;

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/* Header */}
      <header className="mx-auto flex w-full max-w-[480px] items-center justify-between gap-2 px-4 pt-2 pb-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-primary shadow-lg shadow-primary/25">
            <img
              src="/icon-512.png"
              alt="IDXAvg"
              width={40}
              height={40}
              className="h-full w-full object-cover"
            />
          </div>
          <div className="min-w-0 leading-tight">
            <span className="font-display block truncate text-xl font-extrabold tracking-tight">
              Kalkulator ARA ARB
            </span>
            <span className="font-sans block truncate text-[11px] font-medium text-muted-foreground">
              IDXAvg — by @lotmetrik
            </span>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-0.5 text-muted-foreground">
          <Button
            variant="ghost"
            size="icon"
            className="h-10 w-10 rounded-xl hover:bg-secondary hover:text-primary"
            onClick={toggleTheme}
            aria-label={isDark ? "Ganti ke mode terang" : "Ganti ke mode gelap"}
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
        </div>
      </header>

      {/* Main */}
      <main className="mx-auto w-full max-w-[480px] flex-1 px-4 pt-4 pb-6">
        <h1 className="font-display text-2xl font-extrabold tracking-tight">
          Kalkulator ARA ARB Saham IDX
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Hitung batas Auto Rejection Atas (ARA) dan Auto Rejection Bawah (ARB) dari harga
          penutupan terakhir — otomatis disesuaikan dengan fraksi harga (tick size) bursa.
        </p>

        {/* Input */}
        <section className="mt-4 rounded-3xl border border-border bg-card p-5">
          <Label
            htmlFor="ara-arb-price"
            className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            Harga Penutupan Terakhir (Rp)
          </Label>
          <Input
            ref={inputRef}
            id="ara-arb-price"
            inputMode="numeric"
            autoComplete="off"
            placeholder="mis. 1500"
            value={price}
            aria-invalid={showError}
            aria-describedby={showError ? "ara-arb-error" : "ara-arb-hint"}
            onChange={(e) => setPrice(numOnly(e.target.value))}
            onBlur={() => setTouched(true)}
            className="mt-2 h-12 rounded-2xl border-border bg-background text-base tabular"
          />
          {showError ? (
            <p id="ara-arb-error" role="alert" className="mt-2 text-xs font-medium text-destructive">
              {error}
            </p>
          ) : (
            <p id="ara-arb-hint" className="mt-2 text-xs text-muted-foreground">
              Masukkan harga penutupan (prev close) saham yang mau kamu cek.
            </p>
          )}

          {/* Result */}
          <div aria-live="polite" aria-atomic="true" className="mt-4">
            {result && (
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-success/30 bg-success/10 p-4 dark:border-success/20">
                  <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-success-strong dark:text-success-foreground">
                    <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                    ARA {(result.araPct * 100).toFixed(0)}%
                  </div>
                  <p className="font-display mt-1.5 text-xl font-extrabold tabular text-foreground">
                    {formatRupiah(result.ara)}
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">Batas naik maksimum</p>
                </div>
                <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 dark:border-destructive/20">
                  <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-destructive-strong">
                    <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                    ARB {(result.arbPct * 100).toFixed(0)}%
                  </div>
                  <p className="font-display mt-1.5 text-xl font-extrabold tabular text-foreground">
                    {formatRupiah(result.arb)}
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">Batas turun maksimum</p>
                </div>
                <p className="col-span-2 text-center text-[11px] text-muted-foreground">
                  Rentang harga {result.tierLabel} — ARA{" "}
                  {(result.araPct * 100).toFixed(0)}%, ARB {(result.arbPct * 100).toFixed(0)}%.
                  Sudah dibulatkan ke fraksi harga (tick size) terdekat.
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Tier table */}
        <section className="mt-4 rounded-3xl border border-border bg-card p-5">
          <h2 className="font-display text-base font-extrabold tracking-tight">
            Persentase ARA & ARB per Rentang Harga
          </h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="pb-2 pr-2">Harga Penutupan</th>
                <th scope="col" className="pb-2 pr-2">ARA</th>
                <th scope="col" className="pb-2">ARB</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {TIERS.map((t) => (
                <tr key={t.range} className="border-b border-border/60 last:border-0">
                  <td className="py-2 pr-2 font-medium">{t.range}</td>
                  <td className="py-2 pr-2 font-bold text-success-strong dark:text-success-foreground">
                    {t.ara}
                  </td>
                  <td className="py-2 font-bold text-destructive-strong">15%</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            Catatan: persentase mengikuti aturan auto rejection Bursa Efek Indonesia di pasar
            reguler dan dapat berubah sewaktu-waktu. Selalu cek pengumuman resmi IDX untuk
            ketentuan terbaru.
          </p>
        </section>

        {/* SEO content */}
        <section className="mt-4 space-y-4 rounded-3xl border border-border bg-card p-5">
          <div>
            <h2 className="font-display text-base font-extrabold tracking-tight">
              Apa itu ARA dan ARB?
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              ARA (Auto Rejection Atas) adalah batas kenaikan harga maksimum saham dalam satu
              hari perdagangan, sedangkan ARB (Auto Rejection Bawah) adalah batas penurunan
              maksimumnya. Jika harga menyentuh batas ini, sistem perdagangan JATS otomatis
              menolak order di luar rentang tersebut — saham bisa “terkunci” di ARA atau ARB.
            </p>
          </div>
          <div>
            <h2 className="font-display text-base font-extrabold tracking-tight">
              Cara menghitung ARA ARB
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Rumusnya sederhana: ARA = harga penutupan × (1 + persentase ARA), ARB = harga
              penutupan × (1 − 15%). Hasilnya kemudian dibulatkan ke fraksi harga (tick size)
              yang berlaku: Rp1 untuk harga di bawah Rp200, Rp2 untuk Rp200–&lt;Rp500, Rp5
              untuk Rp500–&lt;Rp2.000, Rp10 untuk Rp2.000–&lt;Rp5.000, dan Rp25 untuk Rp5.000
              ke atas. Kalkulator ini melakukan semuanya otomatis.
            </p>
          </div>
          <div>
            <h2 className="font-display text-base font-extrabold tracking-tight">
              Kenapa trader perlu tahu batas ARA ARB?
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Mengetahui batas ARA membantumu memperkirakan potensi kenaikan maksimum dalam
              sehari — berguna saat mengejar saham yang sedang momentum. Sebaliknya, batas ARB
              menunjukkan risiko penurunan maksimum, penting untuk menentukan level cut loss
              dan mengatur money management sebelum masuk posisi.
            </p>
          </div>
        </section>

        {/* Cross-link */}
        <nav className="mt-4 text-center" aria-label="Kalkulator lainnya">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold text-primary transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Coba Kalkulator Rata-rata Saham
          </Link>
        </nav>
      </main>

      {/* Footer */}
      <div className="mx-auto mt-auto w-full max-w-[480px]">
        <SiteFooter />
      </div>
      <TelegramPopup />
    </div>
  );
}

export default AraArbCalculator;
