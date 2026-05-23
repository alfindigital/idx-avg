"use client";

import { type FormEvent, type RefObject, useEffect, useMemo, useRef, useState } from "react";
import {
  Menu,
  Moon,
  Sun,
  History,
  Trash2,
  Link2,
  Copy,
  Download,
  RotateCcw,
  TrendingDown,
  TrendingUp,
  X,
  Info,
  ChevronUp,
  Send,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { formatRupiah, getTickSize, roundToTick } from "@/lib/idx-tick";
import {
  type CalcMode,
  type CalcResult,
  calcLotsNeeded,
  calcNewAvg,
} from "@/lib/calc";
import { toPng } from "html-to-image";

const HISTORY_KEY = "idxavg-history-v1";
const THEME_KEY = "idxavg-theme";

const MAX_PRICE = 1_000_000;
const MAX_LOT = 1_000_000;

function todayISO() {
  const d = new Date();
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().split("T")[0];
}

function validatePrice(v: string): string | null {
  if (!v) return null;
  const n = parseFloat(v);
  if (!isFinite(n) || n <= 0) return "Harus angka > 0";
  if (n > MAX_PRICE) return `Maks ${formatRupiah(MAX_PRICE)}`;
  const tick = getTickSize(n);
  if (Math.abs(n - Math.round(n / tick) * tick) > 1e-9) {
    return `Kelipatan ${tick}`;
  }
  return null;
}

function validateLot(v: string): string | null {
  if (!v) return null;
  const n = Number(v);
  if (!Number.isInteger(n) || n <= 0) return "Bilangan bulat > 0";
  if (n > MAX_LOT) return `Maks ${MAX_LOT.toLocaleString("id-ID")} lot`;
  return null;
}

export function Calculator() {
  // Position
  const [stockName, setStockName] = useState("");
  const [date, setDate] = useState(todayISO());
  const [avgPrice, setAvgPrice] = useState("");
  const [totalLot, setTotalLot] = useState("");

  // Averaging
  const [hargaAvg, setHargaAvg] = useState("");
  const [lotTambah, setLotTambah] = useState("");
  const [targetAvg, setTargetAvg] = useState("");

  // UX
  const [result, setResult] = useState<CalcResult | null>(null);
  const [history, setHistory] = useState<CalcResult[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);
  const mobileResultRef = useRef<HTMLDivElement>(null);
  const [barOpen, setBarOpen] = useState(false);

  // Init: theme, history, URL params
  useEffect(() => {
    const t = localStorage.getItem(THEME_KEY);
    if (t === "dark") {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    }
    try {
      const h = localStorage.getItem(HISTORY_KEY);
      if (h) setHistory(JSON.parse(h));
    } catch {}

    const p = new URLSearchParams(window.location.search);
    const s = p.get("stock");
    const a = p.get("avg");
    const l = p.get("lot");
    const h = p.get("harga");
    const lt = p.get("lotTambah");
    const tg = p.get("target");
    if (s) setStockName(s.toUpperCase());
    if (a) setAvgPrice(a);
    if (l) setTotalLot(l);
    if (h) setHargaAvg(h);
    if (lt) setLotTambah(lt);
    if (tg) setTargetAvg(tg);
  }, []);

  const modalAwal = useMemo(() => {
    const a = parseFloat(avgPrice);
    const l = parseInt(totalLot);
    return isFinite(a) && isFinite(l) ? a * l * 100 : 0;
  }, [avgPrice, totalLot]);

  const mode: CalcMode | null = useMemo(() => {
    if (lotTambah && !targetAvg) return "new-avg";
    if (targetAvg && !lotTambah) return "lots-needed";
    return null;
  }, [lotTambah, targetAvg]);

  const errAvg = useMemo(() => validatePrice(avgPrice), [avgPrice]);
  const errHarga = useMemo(() => validatePrice(hargaAvg), [hargaAvg]);
  const errTarget = useMemo(() => validatePrice(targetAvg), [targetAvg]);
  const errLot = useMemo(() => validateLot(totalLot), [totalLot]);
  const errLotTambah = useMemo(() => validateLot(lotTambah), [lotTambah]);

  const canCalculate = useMemo(() => {
    if (!avgPrice || !totalLot || !hargaAvg) return false;
    if (errAvg || errLot || errHarga) return false;
    if (mode === "new-avg") return !!lotTambah && !errLotTambah;
    if (mode === "lots-needed") return !!targetAvg && !errTarget;
    return false;
  }, [avgPrice, totalLot, hargaAvg, lotTambah, targetAvg, mode, errAvg, errLot, errHarga, errLotTambah, errTarget]);

  const handlePriceBlur = (
    value: string,
    setter: (v: string) => void
  ) => {
    const n = parseFloat(value);
    if (!isFinite(n) || n <= 0 || n > MAX_PRICE) return;
    const rounded = roundToTick(n);
    if (rounded !== n) setter(String(rounded));
  };

  const intOnly = (v: string) => v.replace(/[^\d]/g, "");
  const numOnly = (v: string) => v.replace(/[^\d.]/g, "");

  const saveHistory = (r: CalcResult) => {
    const next = [r, ...history].slice(0, 20);
    setHistory(next);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  };

  const runCalc = () => {
    if (!canCalculate || !mode) return;
    const a = parseFloat(avgPrice);
    const l = parseInt(totalLot);
    const h = parseFloat(hargaAvg);
    const s = stockName.trim().toUpperCase() || "-";
    if (mode === "new-avg") {
      const r = calcNewAvg({
        avgSekarang: a,
        lotSekarang: l,
        hargaAveraging: h,
        lotTambah: parseInt(lotTambah),
        stockName: s,
        date,
      });
      setResult(r);
      saveHistory(r);
    } else {
      const out = calcLotsNeeded({
        avgSekarang: a,
        lotSekarang: l,
        hargaAveraging: h,
        targetAvg: parseFloat(targetAvg),
        stockName: s,
        date,
      });
      if ("error" in out) {
        toast.error(out.error);
        return;
      }
      setResult(out.result);
      saveHistory(out.result);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (canCalculate) runCalc();
  };

  const toggleTheme = () => {
    const n = !isDark;
    setIsDark(n);
    if (n) {
      document.documentElement.classList.add("dark");
      localStorage.setItem(THEME_KEY, "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem(THEME_KEY, "light");
    }
  };

  const resetAvg = () => {
    setHargaAvg("");
    setLotTambah("");
    setTargetAvg("");
    setResult(null);
  };

  const shareLink = async () => {
    if (!result) return;
    const p = new URLSearchParams({
      stock: result.stockName,
      avg: String(result.avgSekarang),
      lot: String(result.lotSekarang),
      harga: String(result.hargaAveraging),
    });
    if (result.mode === "new-avg") p.set("lotTambah", String(result.lotDelta));
    else if (result.targetAvg) p.set("target", String(result.targetAvg));
    const url = `${window.location.origin}${window.location.pathname}?${p}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link disalin");
    } catch {
      toast.error("Gagal menyalin link");
    }
  };

  const copyValue = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} disalin`);
    } catch {
      toast.error("Gagal menyalin");
    }
  };

  const copySummary = async () => {
    if (!result) return;
    const arrow = result.status === "down" ? "↓" : result.status === "up" ? "↑" : "→";
    const head =
      result.mode === "new-avg" ? "Avg Baru" : "Lot Diperlukan";
    const lines = [
      `${result.stockName} · ${result.date}`,
      `${head}: ${formatRupiah(result.newAvgPrice)} (${arrow} ${result.percentage.toFixed(2)}%)`,
      `Lot Baru: ${result.totalLotBaru} (+${result.lotDelta})`,
      `Modal Tambahan: ${formatRupiah(result.modalTambahan)}`,
      `Total Modal: ${formatRupiah(result.totalModal)}`,
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      toast.success("Ringkasan disalin");
    } catch {
      toast.error("Gagal menyalin");
    }
  };
  const saveImage = async () => {
    if (!result) return;
    const node =
      resultRef.current?.offsetParent ? resultRef.current : mobileResultRef.current;
    if (!node) return;
    try {
      const dataUrl = await toPng(node, {
        pixelRatio: 2,
        cacheBust: true,
        backgroundColor: isDark ? "#1a1d2e" : "#ffffff",
      });
      const link = document.createElement("a");
      link.download = `IDXAvg-${result.stockName || "result"}-${todayISO()}.png`;
      link.href = dataUrl;
      link.click();
      toast.success("Gambar disimpan");
    } catch (err) {
      console.error(err);
      toast.error("Gagal menyimpan gambar");
    }
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem(HISTORY_KEY);
    toast("Riwayat dihapus");
  };

  const loadHistory = (r: CalcResult) => {
    setStockName(r.stockName);
    setDate(r.date);
    setAvgPrice(String(r.avgSekarang));
    setTotalLot(String(r.lotSekarang));
    setHargaAvg(String(r.hargaAveraging));
    if (r.mode === "new-avg") {
      setLotTambah(String(r.lotDelta));
      setTargetAvg("");
    } else {
      setTargetAvg(String(r.targetAvg ?? ""));
      setLotTambah("");
    }
    setResult(r);
    setHistoryOpen(false);
  };

  const lotTambahDisabled = !!targetAvg;
  const targetAvgDisabled = !!lotTambah;

  const inputCls =
    "h-auto rounded-2xl border-2 border-transparent bg-card px-4 py-3.5 text-lg font-bold text-foreground shadow-none transition-all focus-visible:border-primary focus-visible:ring-0 placeholder:text-muted-foreground/50 md:text-lg";
  const labelCls = "mb-1.5 ml-1 block text-sm font-semibold text-foreground/70";
  const sectionHead =
    "mb-4 font-display text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground";
  const cardCls =
    "rounded-3xl border border-white/70 bg-secondary/60 p-5 shadow-sm dark:border-white/5";

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-background text-foreground">
        {/* Header */}
        <header className="mx-auto flex w-full max-w-[480px] items-center justify-between px-4 pt-6 pb-2 sm:pt-8">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/25">
              <TrendingUp className="h-5 w-5" strokeWidth={2.5} />
            </div>
            <div className="leading-tight">
              <h1 className="font-display text-2xl font-extrabold tracking-tight">IDXAvg</h1>
              <p className="font-sans text-xs font-medium text-muted-foreground">
                Kalkulator averaging IDX
              </p>
            </div>
          </div>

          <div className="flex items-center gap-0.5 text-muted-foreground">
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 rounded-xl hover:bg-secondary hover:text-primary"
              onClick={toggleTheme}
              aria-label="Toggle theme"
            >
              {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
            <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
              <DialogTrigger asChild>
                <Button variant="ghost" size="icon" className="h-10 w-10 rounded-xl hover:bg-secondary hover:text-primary" aria-label="History">
                  <History className="h-5 w-5" />
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-[440px] gap-3 rounded-3xl border-border bg-card p-6">
                <DialogHeader>
                  <DialogTitle className="flex items-center justify-between gap-2 font-display text-lg font-extrabold tracking-tight">
                    <span>Riwayat</span>
                    {history.length > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={clearHistory}
                        className="h-8 rounded-lg text-xs font-semibold text-destructive hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 className="mr-1 h-3.5 w-3.5" /> Hapus
                      </Button>
                    )}
                  </DialogTitle>
                </DialogHeader>
                <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
                  {history.length === 0 ? (
                    <p className="py-6 text-center text-sm font-medium text-muted-foreground">
                      Belum ada riwayat.
                    </p>
                  ) : (
                    history.map((h) => (
                      <button
                        key={h.id}
                        onClick={() => loadHistory(h)}
                        className="w-full rounded-2xl border border-border bg-secondary/40 p-3 text-left transition-colors hover:border-primary/40 hover:bg-accent"
                      >
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-display text-base font-extrabold tracking-tight">{h.stockName}</span>
                          <span className="text-xs font-medium text-muted-foreground">
                            {new Date(h.timestamp).toLocaleDateString("id-ID")}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center justify-between text-xs font-medium text-muted-foreground tabular">
                          <span>
                            {formatRupiah(h.avgSekarang)} → {formatRupiah(h.newAvgPrice)}
                          </span>
                          <span
                            className={cn(
                              "font-bold",
                              h.status === "down" && "text-destructive",
                              h.status === "up" && "text-[color:var(--success)]"
                            )}
                          >
                            {h.status === "down" ? "↓" : h.status === "up" ? "↑" : "→"}{" "}
                            {h.percentage.toFixed(2)}%
                          </span>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </DialogContent>
            </Dialog>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-10 w-10 rounded-xl hover:bg-secondary hover:text-primary" aria-label="Menu">
                  <Menu className="h-5 w-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-[200px] rounded-2xl border-border bg-card p-1.5 font-sans">
                <DropdownMenuItem onClick={copySummary} disabled={!result} className="rounded-xl px-3 py-2 text-sm font-semibold text-foreground focus:bg-secondary focus:text-primary">
                  <Copy className="mr-2 h-4 w-4" /> Salin ringkasan
                </DropdownMenuItem>
                <DropdownMenuItem onClick={shareLink} disabled={!result} className="rounded-xl px-3 py-2 text-sm font-semibold text-foreground focus:bg-secondary focus:text-primary">
                  <Link2 className="mr-2 h-4 w-4" /> Salin link
                </DropdownMenuItem>
                <DropdownMenuItem onClick={saveImage} disabled={!result} className="rounded-xl px-3 py-2 text-sm font-semibold text-foreground focus:bg-secondary focus:text-primary">
                  <Download className="mr-2 h-4 w-4" /> Simpan gambar
                </DropdownMenuItem>
                <DropdownMenuSeparator className="my-1 bg-border" />
                <DropdownMenuItem onClick={resetAvg} className="rounded-xl px-3 py-2 text-sm font-semibold text-foreground focus:bg-secondary focus:text-primary">
                  <RotateCcw className="mr-2 h-4 w-4" /> Reset
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Main */}
        <main className="mx-auto w-full max-w-[480px] px-4 pt-4 pb-[calc(9rem+env(safe-area-inset-bottom))] sm:pb-[calc(5rem+env(safe-area-inset-bottom))]">
          <form onSubmit={handleSubmit} noValidate className="space-y-5">
          {/* Position */}
          <section className={cardCls}>
            <h2 className={sectionHead}>Posisi Saat Ini</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className={labelCls}>Kode Saham</Label>
                <Input
                  value={stockName}
                  onChange={(e) => setStockName(e.target.value.toUpperCase().slice(0, 6))}
                  placeholder="BUMI"
                  className={cn(inputCls, "font-display uppercase tracking-wide")}
                  autoFocus
                  tabIndex={1}
                />
              </div>
              <div>
                <Label className={labelCls}>Tanggal</Label>
                <Input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className={cn(inputCls, "text-base font-semibold")}
                  tabIndex={8}
                />
              </div>
              <div>
                <Label className={labelCls}>Avg Sekarang (Rp)</Label>
                <Input
                  inputMode="decimal"
                  value={avgPrice}
                  onChange={(e) => setAvgPrice(numOnly(e.target.value))}
                  onBlur={(e) => handlePriceBlur(e.target.value, setAvgPrice)}
                  placeholder="0"
                  aria-invalid={!!errAvg}
                  className={cn(inputCls, "tabular", errAvg && "border-destructive focus-visible:border-destructive")}
                  tabIndex={2}
                />
                {errAvg && <p className="mt-1.5 ml-1 text-xs font-medium text-destructive">{errAvg}</p>}
              </div>
              <div>
                <Label className={labelCls}>Total Lot</Label>
                <Input
                  inputMode="numeric"
                  value={totalLot}
                  onChange={(e) => setTotalLot(intOnly(e.target.value))}
                  placeholder="0"
                  aria-invalid={!!errLot}
                  className={cn(inputCls, "tabular", errLot && "border-destructive focus-visible:border-destructive")}
                  tabIndex={3}
                />
                {errLot && <p className="mt-1.5 ml-1 text-xs font-medium text-destructive">{errLot}</p>}
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between rounded-2xl border border-white/70 bg-card/60 px-4 py-3 dark:border-white/5">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
                Modal Awal
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3.5 w-3.5 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent side="top" className="text-xs">
                    Avg × Lot × 100
                  </TooltipContent>
                </Tooltip>
              </span>
              <button
                type="button"
                onClick={() => copyValue("Modal Awal", formatRupiah(modalAwal))}
                className="flex items-center gap-1.5 rounded-xl px-2 py-1 text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
                aria-label="Salin Modal Awal"
              >
                <span className="font-display text-lg font-extrabold tabular">{formatRupiah(modalAwal)}</span>
                <Copy className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            </div>
          </section>

          {/* Averaging */}
          <section className={cardCls}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className={cn(sectionHead, "mb-0")}>Averaging</h2>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 cursor-help text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-[220px] text-xs">
                  Isi <b>Lot Tambah</b> untuk hitung avg baru, atau <b>Target Avg</b> untuk
                  hitung lot yang dibutuhkan. Yang lain otomatis disable.
                </TooltipContent>
              </Tooltip>
            </div>

            <div className="space-y-3">
              <div>
                <Label className={labelCls}>Harga Averaging (Rp)</Label>
                <Input
                  inputMode="decimal"
                  value={hargaAvg}
                  onChange={(e) => setHargaAvg(numOnly(e.target.value))}
                  onBlur={(e) => handlePriceBlur(e.target.value, setHargaAvg)}
                  placeholder="0"
                  aria-invalid={!!errHarga}
                  className={cn(inputCls, "tabular", errHarga && "border-destructive focus-visible:border-destructive")}
                  tabIndex={4}
                />
                {errHarga && <p className="mt-1.5 ml-1 text-xs font-medium text-destructive">{errHarga}</p>}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className={cn(lotTambahDisabled && "opacity-50")}>
                  <Label className={labelCls}>Lot Tambah</Label>
                  <Input
                    inputMode="numeric"
                    value={lotTambah}
                    onChange={(e) => setLotTambah(intOnly(e.target.value))}
                    placeholder="0"
                    aria-invalid={!!errLotTambah}
                    className={cn(inputCls, "tabular", errLotTambah && "border-destructive focus-visible:border-destructive")}
                    disabled={lotTambahDisabled}
                    tabIndex={5}
                  />
                  {errLotTambah && <p className="mt-1.5 ml-1 text-xs font-medium text-destructive">{errLotTambah}</p>}
                </div>
                <div className={cn(targetAvgDisabled && "opacity-50")}>
                  <Label className={labelCls}>Target Avg (Rp)</Label>
                  <Input
                    inputMode="decimal"
                    value={targetAvg}
                    onChange={(e) => setTargetAvg(numOnly(e.target.value))}
                    onBlur={(e) => handlePriceBlur(e.target.value, setTargetAvg)}
                    placeholder="0"
                    aria-invalid={!!errTarget}
                    className={cn(inputCls, "tabular", errTarget && "border-destructive focus-visible:border-destructive")}
                    disabled={targetAvgDisabled}
                    tabIndex={6}
                  />
                  {errTarget && <p className="mt-1.5 ml-1 text-xs font-medium text-destructive">{errTarget}</p>}
                </div>
              </div>
            </div>
          </section>

          <Button
            type="submit"
            className="font-display h-auto w-full rounded-3xl py-5 text-lg font-extrabold uppercase tracking-[0.15em] shadow-xl shadow-primary/25 transition-all active:scale-[0.98]"
            disabled={!canCalculate}
          >
            Hitung
          </Button>
          {!mode && (hargaAvg || avgPrice) && (
            <p className="text-center text-xs font-medium text-muted-foreground">
              Isi <b>Lot Tambah</b> atau <b>Target Avg</b>
            </p>
          )}

          </form>


          {/* Result */}
          {result && (() => {
            const headLabel = result.mode === "new-avg" ? "Avg Baru" : "Lot Diperlukan";
            const headValue =
              result.mode === "new-avg"
                ? formatRupiah(result.newAvgPrice)
                : `${result.lotDelta} lot`;
            const resultCard = (ref: RefObject<HTMLDivElement | null>) => (
              <div
                ref={ref}
                data-result-card
                className="overflow-hidden rounded-3xl border border-white/70 bg-card shadow-sm dark:border-white/5"
              >
                <div className="bg-primary/10 px-5 pt-5 pb-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-display text-[11px] font-extrabold uppercase tracking-[0.22em] text-primary">
                        {result.stockName} · {headLabel}
                      </p>
                      <p className="mt-2 font-display text-4xl font-extrabold leading-none tabular text-foreground">
                        {headValue}
                      </p>
                      {result.mode === "lots-needed" && (
                        <p className="mt-2 font-sans text-sm font-semibold text-muted-foreground tabular">
                          Avg jadi {formatRupiah(result.newAvgPrice)}
                        </p>
                      )}
                    </div>
                    <Badge
                      variant="secondary"
                      className={cn(
                        "shrink-0 gap-1 rounded-full px-3 py-1.5 text-xs font-bold",
                        result.status === "down" &&
                          "bg-destructive/15 text-destructive hover:bg-destructive/15",
                        result.status === "up" &&
                          "bg-[color:var(--success)]/15 text-[color:var(--success)] hover:bg-[color:var(--success)]/15"
                      )}
                    >
                      {result.status === "down" ? (
                        <TrendingDown className="h-3.5 w-3.5" />
                      ) : (
                        <TrendingUp className="h-3.5 w-3.5" />
                      )}
                      {result.percentage.toFixed(2)}%
                    </Badge>
                  </div>
                </div>

                <div className="space-y-2.5 px-5 py-4 text-sm font-medium">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Lot Baru</span>
                    <span className="font-bold tabular text-foreground">
                      {result.totalLotBaru} <span className="text-muted-foreground">(+{result.lotDelta})</span>
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Modal Tambahan</span>
                    <button
                      type="button"
                      onClick={() => copyValue("Modal Tambahan", formatRupiah(result.modalTambahan))}
                      className="flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
                      aria-label="Salin Modal Tambahan"
                    >
                      <span className="font-bold tabular text-foreground">{formatRupiah(result.modalTambahan)}</span>
                      <Copy className="h-3 w-3 text-muted-foreground" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between border-t border-border/70 pt-2.5">
                    <span className="text-muted-foreground">Total Modal</span>
                    <button
                      type="button"
                      onClick={() => copyValue("Total Modal", formatRupiah(result.totalModal))}
                      className="flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
                      aria-label="Salin Total Modal"
                    >
                      <span className="font-display text-base font-extrabold tabular text-foreground">{formatRupiah(result.totalModal)}</span>
                      <Copy className="h-3 w-3 text-muted-foreground" />
                    </button>
                  </div>
                </div>
              </div>
            );

            const actions = (
              <div className="mt-4 flex items-center justify-center gap-2">
                <Button variant="outline" size="icon" onClick={copySummary} aria-label="Salin ringkasan" className="h-11 w-11 rounded-2xl border-border bg-card hover:border-primary/40 hover:bg-secondary hover:text-primary">
                  <Copy className="h-4.5 w-4.5" />
                </Button>
                <Button variant="outline" size="icon" onClick={shareLink} aria-label="Salin link" className="h-11 w-11 rounded-2xl border-border bg-card hover:border-primary/40 hover:bg-secondary hover:text-primary">
                  <Link2 className="h-4.5 w-4.5" />
                </Button>
                <Button variant="outline" size="icon" onClick={saveImage} aria-label="Simpan PNG" className="h-11 w-11 rounded-2xl border-border bg-card hover:border-primary/40 hover:bg-secondary hover:text-primary">
                  <Download className="h-4.5 w-4.5" />
                </Button>
                <Button variant="outline" size="icon" onClick={resetAvg} aria-label="Reset" className="h-11 w-11 rounded-2xl border-border bg-card hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive">
                  <X className="h-4.5 w-4.5" />
                </Button>
              </div>
            );

            return (
              <>
                {/* Desktop: inline */}
                <section className="mt-5 hidden sm:block">
                  {resultCard(resultRef)}
                  {actions}
                </section>

                {/* Mobile: floating sticky bar + drawer */}
                <Drawer open={barOpen} onOpenChange={setBarOpen}>
                  <div className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-30 flex justify-center px-4 sm:hidden">
                    <DrawerTrigger asChild>
                      <button
                        type="button"
                        className="flex w-full max-w-[440px] items-center justify-between gap-3 rounded-3xl border border-slate-700 bg-slate-900 px-5 py-4 text-left text-white shadow-2xl backdrop-blur transition-transform active:scale-[0.98]"
                        aria-label="Lihat detail hasil"
                      >
                        <div className="min-w-0 space-y-0.5">
                          <p className="font-display text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
                            {headLabel}
                          </p>
                          <p className="font-display text-xl font-extrabold tabular leading-tight text-white">
                            {headValue}
                          </p>
                        </div>
                        <div className="h-10 w-px bg-slate-700" />
                        <div className="min-w-0 space-y-0.5 text-right">
                          <p className="font-display text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
                            {result.status === "down" ? "Turun" : result.status === "up" ? "Naik" : "Flat"}
                          </p>
                          <p
                            className={cn(
                              "font-display text-xl font-extrabold tabular leading-tight",
                              result.status === "down" && "text-rose-400",
                              result.status === "up" && "text-emerald-400",
                              result.status === "flat" && "text-white"
                            )}
                          >
                            {result.status === "down" ? "↓" : result.status === "up" ? "↑" : "→"}{" "}
                            {result.percentage.toFixed(2)}%
                          </p>
                        </div>
                        <ChevronUp className="h-5 w-5 shrink-0 text-slate-400" />
                      </button>
                    </DrawerTrigger>
                  </div>
                  <DrawerContent className="sm:hidden">
                    <DrawerHeader className="pb-2">
                      <DrawerTitle className="font-display">Hasil Perhitungan</DrawerTitle>
                    </DrawerHeader>
                    <div className="px-4 pb-6">
                      {resultCard(mobileResultRef)}
                      {actions}
                    </div>
                  </DrawerContent>
                </Drawer>
              </>
            );
          })()}

        </main>

        {/* Sticky footer */}
        <footer className="fixed inset-x-0 bottom-0 z-20 border-t border-border/60 bg-background/85 pb-[env(safe-area-inset-bottom)] backdrop-blur-md">
          <div className="mx-auto flex w-full max-w-[480px] items-center justify-between gap-3 px-4 py-2">
            <div className="flex items-center gap-1">
              <a
                href="https://x.com/alfindigital"
                target="_blank"
                rel="noreferrer"
                aria-label="X (Twitter) @alfindigital"
                className="flex h-11 min-h-11 w-11 min-w-11 items-center justify-center rounded-xl text-foreground/60 transition-all hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
              >
                <svg viewBox="0 0 24 24" className="h-[1.125rem] w-[1.125rem]" fill="currentColor" aria-hidden="true">
                  <path d="M18.244 2H21.5l-7.5 8.575L23 22h-6.844l-5.36-6.99L4.5 22H1.244l8.02-9.166L1 2h7.02l4.85 6.41L18.244 2Zm-2.4 18h1.9L7.27 4H5.27l10.574 16Z" />
                </svg>
              </a>
              <a
                href="https://tiktok.com/@alfindigital"
                target="_blank"
                rel="noreferrer"
                aria-label="TikTok @alfindigital"
                className="flex h-11 min-h-11 w-11 min-w-11 items-center justify-center rounded-xl text-foreground/60 transition-all hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
              >
                <svg viewBox="0 0 24 24" className="h-[1.125rem] w-[1.125rem]" fill="currentColor" aria-hidden="true">
                  <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5.8 20.1a6.34 6.34 0 0 0 10.86-4.43V8.83a8.16 8.16 0 0 0 4.77 1.52V6.9a4.85 4.85 0 0 1-1.84-.21Z" />
                </svg>
              </a>
              <a
                href="https://facebook.com/alfindigital"
                target="_blank"
                rel="noreferrer"
                aria-label="Facebook @alfindigital"
                className="flex h-11 min-h-11 w-11 min-w-11 items-center justify-center rounded-xl text-foreground/60 transition-all hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
                  <path d="M13.5 22v-8h2.7l.4-3.2h-3.1V8.7c0-.92.26-1.55 1.57-1.55H17V4.27A22 22 0 0 0 14.56 4.1c-2.42 0-4.06 1.48-4.06 4.2v2.5H8v3.2h2.5V22h3Z" />
                </svg>
              </a>
            </div>
            <a
              href="https://t.me/alfindx"
              target="_blank"
              rel="noreferrer"
              aria-label="Telegram @alfindx"
              className="inline-flex h-11 min-h-11 max-w-[7.5rem] items-center gap-1.5 truncate rounded-full bg-primary/10 px-3 text-sm font-bold text-primary transition-all hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95 sm:max-w-none sm:px-4"
            >
              <Send className="h-4 w-4 shrink-0" />
              <span className="truncate">@alfindx</span>
            </a>
          </div>
        </footer>
      </div>
    </TooltipProvider>
  );
}
