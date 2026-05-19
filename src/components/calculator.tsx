"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Menu,
  Moon,
  Sun,
  History,
  Trash2,
  Link2,
  Download,
  RotateCcw,
  TrendingDown,
  TrendingUp,
  Check,
  X,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
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
import { formatRupiah, roundToTick } from "@/lib/idx-tick";
import {
  type CalcMode,
  type CalcResult,
  calcLotsNeeded,
  calcNewAvg,
} from "@/lib/calc";
import html2canvas from "html2canvas";

const HISTORY_KEY = "idxavg-history-v1";
const THEME_KEY = "idxavg-theme";

function todayISO() {
  const d = new Date();
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().split("T")[0];
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

  const canCalculate = useMemo(() => {
    const a = parseFloat(avgPrice);
    const l = parseInt(totalLot);
    const h = parseFloat(hargaAvg);
    if (!isFinite(a) || a <= 0 || !isFinite(l) || l <= 0 || !isFinite(h) || h <= 0) return false;
    if (mode === "new-avg") {
      const lt = parseInt(lotTambah);
      return isFinite(lt) && lt > 0;
    }
    if (mode === "lots-needed") {
      const t = parseFloat(targetAvg);
      return isFinite(t) && t > 0;
    }
    return false;
  }, [avgPrice, totalLot, hargaAvg, lotTambah, targetAvg, mode]);

  const handlePriceBlur = (
    value: string,
    setter: (v: string) => void,
    label: string
  ) => {
    const n = parseFloat(value);
    if (!isFinite(n) || n <= 0) return;
    const rounded = roundToTick(n);
    if (rounded !== n) {
      setter(String(rounded));
      toast(`${label}: dibulatkan ke ${formatRupiah(rounded)}`, { duration: 1500 });
    }
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

  // Enter shortcut
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && canCalculate) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "BUTTON") runCalc();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

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

  const saveImage = async () => {
    if (!resultRef.current) return;
    try {
      const canvas = await html2canvas(resultRef.current, {
        backgroundColor: isDark ? "#0b1220" : "#ffffff",
        scale: 2,
        logging: false,
      });
      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.download = `IDXAvg-${result?.stockName || "result"}-${todayISO()}.png`;
        link.href = url;
        link.click();
        URL.revokeObjectURL(url);
      }, "image/png");
    } catch {
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

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-background text-foreground">
        {/* Header */}
        <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
          <div className="mx-auto flex max-w-2xl items-center justify-between px-3 py-2">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <TrendingUp className="h-4 w-4" />
              </div>
              <div className="leading-tight">
                <h1 className="text-sm font-semibold">IDXAvg</h1>
                <p className="text-[10px] text-muted-foreground">
                  Hitung avg sebelum beli
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={toggleTheme}
                aria-label="Toggle theme"
              >
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
                <SheetTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="History">
                    <History className="h-4 w-4" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="right" className="w-[88vw] sm:w-96">
                  <SheetHeader>
                    <SheetTitle className="flex items-center justify-between">
                      Riwayat
                      {history.length > 0 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={clearHistory}
                          className="h-7 text-xs text-destructive"
                        >
                          <Trash2 className="mr-1 h-3 w-3" /> Hapus
                        </Button>
                      )}
                    </SheetTitle>
                  </SheetHeader>
                  <div className="mt-3 space-y-2">
                    {history.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Belum ada riwayat.</p>
                    ) : (
                      history.map((h) => (
                        <button
                          key={h.id}
                          onClick={() => loadHistory(h)}
                          className="w-full rounded-md border border-border p-2 text-left hover:bg-accent"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold">{h.stockName}</span>
                            <span className="text-muted-foreground">
                              {new Date(h.timestamp).toLocaleDateString("id-ID")}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground tabular">
                            <span>
                              {formatRupiah(h.avgSekarang)} → {formatRupiah(h.newAvgPrice)}
                            </span>
                            <span
                              className={cn(
                                "font-medium",
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
                </SheetContent>
              </Sheet>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Menu">
                    <Menu className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={shareLink} disabled={!result}>
                    <Link2 className="mr-2 h-4 w-4" /> Salin link
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={saveImage} disabled={!result}>
                    <Download className="mr-2 h-4 w-4" /> Simpan gambar
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={resetAvg}>
                    <RotateCcw className="mr-2 h-4 w-4" /> Reset
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>

        {/* Main */}
        <main className="mx-auto max-w-2xl px-3 pb-10 pt-3">
          {/* Position */}
          <section className="space-y-2.5">
            <div className="flex items-center gap-1.5">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Posisi Saat Ini
              </h2>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2">
                <Label className="mb-1 block text-[11px] text-muted-foreground">
                  Kode Saham
                </Label>
                <Input
                  value={stockName}
                  onChange={(e) => setStockName(e.target.value.toUpperCase().slice(0, 6))}
                  placeholder="BBRI"
                  className="h-9 uppercase"
                  autoFocus
                />
              </div>
              <div>
                <Label className="mb-1 block text-[11px] text-muted-foreground">
                  Tanggal
                </Label>
                <Input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="h-9"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="mb-1 block text-[11px] text-muted-foreground">
                  Avg Sekarang (Rp)
                </Label>
                <Input
                  inputMode="decimal"
                  value={avgPrice}
                  onChange={(e) => setAvgPrice(numOnly(e.target.value))}
                  onBlur={(e) => handlePriceBlur(e.target.value, setAvgPrice, "Avg")}
                  placeholder="0"
                  className="h-9 tabular"
                />
              </div>
              <div>
                <Label className="mb-1 block text-[11px] text-muted-foreground">
                  Total Lot
                </Label>
                <Input
                  inputMode="numeric"
                  value={totalLot}
                  onChange={(e) => setTotalLot(intOnly(e.target.value))}
                  placeholder="0"
                  className="h-9 tabular"
                />
              </div>
            </div>
            <div className="flex items-center justify-between rounded-md bg-muted/60 px-3 py-2 text-sm">
              <span className="flex items-center gap-1 text-muted-foreground">
                Modal Awal
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3 w-3 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent side="top" className="text-xs">
                    Avg × Lot × 100
                  </TooltipContent>
                </Tooltip>
              </span>
              <span className="font-semibold tabular">{formatRupiah(modalAwal)}</span>
            </div>
          </section>

          {/* Averaging */}
          <section className="mt-5 space-y-2.5">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Averaging
              </h2>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-3 w-3 cursor-help text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-[220px] text-xs">
                  Isi <b>Lot Tambah</b> untuk hitung avg baru, atau <b>Target Avg</b> untuk
                  hitung lot yang dibutuhkan. Yang lain otomatis disable.
                </TooltipContent>
              </Tooltip>
            </div>

            <div>
              <Label className="mb-1 block text-[11px] text-muted-foreground">
                Harga Averaging (Rp)
              </Label>
              <Input
                inputMode="decimal"
                value={hargaAvg}
                onChange={(e) => setHargaAvg(numOnly(e.target.value))}
                onBlur={(e) => handlePriceBlur(e.target.value, setHargaAvg, "Harga")}
                placeholder="0"
                className="h-9 tabular"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className={cn(lotTambahDisabled && "opacity-50")}>
                <Label className="mb-1 block text-[11px] text-muted-foreground">
                  Lot Tambah
                </Label>
                <Input
                  inputMode="numeric"
                  value={lotTambah}
                  onChange={(e) => setLotTambah(intOnly(e.target.value))}
                  placeholder="0"
                  className="h-9 tabular"
                  disabled={lotTambahDisabled}
                />
              </div>
              <div className={cn(targetAvgDisabled && "opacity-50")}>
                <Label className="mb-1 block text-[11px] text-muted-foreground">
                  Target Avg (Rp)
                </Label>
                <Input
                  inputMode="decimal"
                  value={targetAvg}
                  onChange={(e) => setTargetAvg(numOnly(e.target.value))}
                  onBlur={(e) => handlePriceBlur(e.target.value, setTargetAvg, "Target")}
                  placeholder="0"
                  className="h-9 tabular"
                  disabled={targetAvgDisabled}
                />
              </div>
            </div>

            <Button
              className="h-10 w-full text-sm font-semibold tracking-wide"
              disabled={!canCalculate}
              onClick={runCalc}
            >
              HITUNG
              <span className="ml-2 hidden text-[10px] opacity-60 sm:inline">
                (Enter)
              </span>
            </Button>
            {!mode && (hargaAvg || avgPrice) && (
              <p className="text-center text-[11px] text-muted-foreground">
                Isi <b>Lot Tambah</b> atau <b>Target Avg</b>
              </p>
            )}
          </section>

          {/* Result */}
          {result && (
            <section className="mt-5">
              <div
                ref={resultRef}
                data-result-card
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      {result.stockName} · {result.mode === "new-avg" ? "Avg Baru" : "Lot Diperlukan"}
                    </p>
                    <p className="mt-0.5 text-2xl font-bold tabular">
                      {formatRupiah(result.newAvgPrice)}
                    </p>
                  </div>
                  <Badge
                    variant="secondary"
                    className={cn(
                      "gap-1 text-xs",
                      result.status === "down" &&
                        "bg-destructive/10 text-destructive hover:bg-destructive/10",
                      result.status === "up" &&
                        "bg-[color:var(--success)]/15 text-[color:var(--success)] hover:bg-[color:var(--success)]/15"
                    )}
                  >
                    {result.status === "down" ? (
                      <TrendingDown className="h-3 w-3" />
                    ) : (
                      <TrendingUp className="h-3 w-3" />
                    )}
                    {result.status === "down" ? "Down" : "Up"} {result.percentage.toFixed(2)}%
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
                  <div className="flex justify-between border-t border-border pt-2 col-span-2">
                    <span className="text-muted-foreground">Lot Baru</span>
                    <span className="font-medium tabular">
                      {result.totalLotBaru} <span className="text-muted-foreground">(+{result.lotDelta})</span>
                    </span>
                  </div>
                  <div className="flex justify-between col-span-2">
                    <span className="text-muted-foreground">Modal Tambahan</span>
                    <span className="font-medium tabular">{formatRupiah(result.modalTambahan)}</span>
                  </div>
                  <div className="flex justify-between col-span-2">
                    <span className="text-muted-foreground">Total Modal</span>
                    <span className="font-semibold tabular">{formatRupiah(result.totalModal)}</span>
                  </div>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2">
                <Button variant="outline" size="sm" onClick={shareLink} className="h-9">
                  <Link2 className="mr-1.5 h-3.5 w-3.5" /> Link
                </Button>
                <Button variant="outline" size="sm" onClick={saveImage} className="h-9">
                  <Download className="mr-1.5 h-3.5 w-3.5" /> PNG
                </Button>
                <Button variant="outline" size="sm" onClick={resetAvg} className="h-9">
                  <X className="mr-1.5 h-3.5 w-3.5" /> Reset
                </Button>
              </div>
            </section>
          )}

          <footer className="mt-8 text-center text-[10px] text-muted-foreground">
            made with <span className="text-destructive">♥</span> · IDXAvg
          </footer>
        </main>
      </div>
    </TooltipProvider>
  );
}
