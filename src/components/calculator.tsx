"use client";

import { type FormEvent, type RefObject, useEffect, useMemo, useRef, useState } from "react";
import {
  Moon,
  Sun,
  History,
  Trash2,
  Link2,
  Copy,
  Download,
  TrendingDown,
  TrendingUp,
  X,
  Info,
  ChevronDown,
  Send,
  Sigma,
  Globe,
  Facebook,
  Youtube,
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
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";

import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { formatRupiah, getTickSize, roundToTick } from "@/lib/idx-tick";
import {
  type CalcMode,
  type CalcResult,
  type FeeOptions,
  calcLotsNeeded,
  calcNewAvg,
} from "@/lib/calc";
import { useLang, type Dict } from "@/lib/i18n";
// html-to-image is loaded lazily inside saveImage() to keep it out of the initial bundle.

const HISTORY_KEY = "idxavg-history-v1";
const THEME_KEY = "idxavg-theme";
const INPUTS_KEY = "idxavg-inputs-v2";
const FEE_KEY = "idxavg-fee-v1";

const MAX_PRICE = 1_000_000;
const MAX_LOT = 1_000_000;

const DEFAULT_FEE: FeeOptions = { enabled: true, buyPct: 0.15, sellPct: 0.25 };

function todayISO() {
  const d = new Date();
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().split("T")[0];
}

function validatePrice(v: string, t: Dict): string | null {
  if (!v) return null;
  const n = parseFloat(v);
  if (!isFinite(n) || n <= 0) return t.positive;
  if (n > MAX_PRICE) return t.maxPrice(formatRupiah(MAX_PRICE));
  const tick = getTickSize(n);
  if (Math.abs(n - Math.round(n / tick) * tick) > 1e-9) {
    return t.tickError(tick, roundToTick(n));
  }
  return null;
}

function validateLot(v: string, t: Dict): string | null {
  if (!v) return null;
  const n = Number(v);
  if (!Number.isInteger(n) || n <= 0) return t.integerPositive;
  if (n > MAX_LOT) return t.maxLot(MAX_LOT);
  return null;
}

const intOnly = (v: string) => v.replace(/[^\d]/g, "");
const numOnly = (v: string) => v.replace(/[^\d.]/g, "");

export function Calculator() {
  const { lang, toggle: toggleLang, t } = useLang();

  // Position
  const [avgPrice, setAvgPrice] = useState("");
  const [totalLot, setTotalLot] = useState("");

  // Averaging
  const [hargaAvg, setHargaAvg] = useState("");
  const [lotTambah, setLotTambah] = useState("");
  const [targetAvg, setTargetAvg] = useState("");

  // Fee
  const [fee, setFee] = useState<FeeOptions>(DEFAULT_FEE);

  // UX
  const [result, setResult] = useState<CalcResult | null>(null);
  const [history, setHistory] = useState<CalcResult[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const [feeOpen, setFeeOpen] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);
  const firstInputRef = useRef<HTMLInputElement>(null);
  const lotRef = useRef<HTMLInputElement>(null);
  const hargaRef = useRef<HTMLInputElement>(null);
  const lotTambahRef = useRef<HTMLInputElement>(null);
  const targetRef = useRef<HTMLInputElement>(null);
  const [flashField, setFlashField] = useState<string | null>(null);
  const flashTimeoutRef = useRef<number | null>(null);
  const resultInputsRef = useRef<string>("");
  const [barOpen, setBarOpen] = useState(false);
  const hydratedRef = useRef(false);
  const [showRecovered, setShowRecovered] = useState(false);
  const recoveredTimeoutRef = useRef<number | null>(null);

  const feeKey = `${fee.enabled}|${fee.buyPct}|${fee.sellPct}`;
  const currentInputsKey = `${avgPrice}|${totalLot}|${hargaAvg}|${lotTambah}|${targetAvg}|${feeKey}`;
  useEffect(() => {
    if (result && currentInputsKey !== resultInputsRef.current) {
      setResult(null);
    }
  }, [currentInputsKey, result]);

  // Init
  useEffect(() => {
    const th = localStorage.getItem(THEME_KEY);
    if (th === "dark") {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    }
    try {
      const h = localStorage.getItem(HISTORY_KEY);
      if (h) setHistory(JSON.parse(h));
    } catch {}
    try {
      const f = localStorage.getItem(FEE_KEY);
      if (f) {
        const v = JSON.parse(f);
        setFee({
          enabled: typeof v.enabled === "boolean" ? v.enabled : true,
          buyPct: typeof v.buyPct === "number" ? v.buyPct : 0.15,
          sellPct: typeof v.sellPct === "number" ? v.sellPct : 0.25,
        });
      }
    } catch {}

    let recovered = false;
    try {
      const saved = localStorage.getItem(INPUTS_KEY);
      if (saved) {
        const v = JSON.parse(saved);
        if (typeof v.avgPrice === "string") setAvgPrice(v.avgPrice);
        if (typeof v.totalLot === "string") setTotalLot(v.totalLot);
        if (typeof v.hargaAvg === "string") setHargaAvg(v.hargaAvg);
        if (v.mode === "new-avg") {
          if (typeof v.lotTambah === "string") setLotTambah(v.lotTambah);
          setTargetAvg("");
        } else if (v.mode === "lots-needed") {
          if (typeof v.targetAvg === "string") setTargetAvg(v.targetAvg);
          setLotTambah("");
        } else {
          if (typeof v.lotTambah === "string") setLotTambah(v.lotTambah);
          if (typeof v.targetAvg === "string") setTargetAvg(v.targetAvg);
        }
        recovered = true;
      }
    } catch {}

    if (recovered) {
      setShowRecovered(true);
      if (recoveredTimeoutRef.current) window.clearTimeout(recoveredTimeoutRef.current);
      recoveredTimeoutRef.current = window.setTimeout(() => {
        setShowRecovered(false);
        recoveredTimeoutRef.current = null;
      }, 3000);
    }

    // URL params
    const p = new URLSearchParams(window.location.search);
    const a = p.get("avg");
    const l = p.get("lot");
    const h = p.get("harga");
    const lt = p.get("lotTambah");
    const tg = p.get("target");
    if (a) setAvgPrice(numOnly(a));
    if (l) setTotalLot(intOnly(l));
    if (h) setHargaAvg(numOnly(h));
    if (lt) setLotTambah(intOnly(lt));
    if (tg) setTargetAvg(numOnly(tg));

    hydratedRef.current = true;
    return () => {
      if (recoveredTimeoutRef.current) window.clearTimeout(recoveredTimeoutRef.current);
    };
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

  // Auto-save inputs
  const saveTimeoutRef = useRef<number | null>(null);
  useEffect(() => {
    if (!hydratedRef.current) return;
    if (saveTimeoutRef.current) window.clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = window.setTimeout(() => {
      try {
        localStorage.setItem(
          INPUTS_KEY,
          JSON.stringify({ avgPrice, totalLot, hargaAvg, lotTambah, targetAvg, mode }),
        );
      } catch {}
      saveTimeoutRef.current = null;
    }, 800);
    return () => {
      if (saveTimeoutRef.current) window.clearTimeout(saveTimeoutRef.current);
    };
  }, [avgPrice, totalLot, hargaAvg, lotTambah, targetAvg, mode]);

  // Auto-save fee
  useEffect(() => {
    if (!hydratedRef.current) return;
    try {
      localStorage.setItem(FEE_KEY, JSON.stringify(fee));
    } catch {}
  }, [fee]);

  const errAvg = useMemo(() => validatePrice(avgPrice, t), [avgPrice, t]);
  const errHarga = useMemo(() => validatePrice(hargaAvg, t), [hargaAvg, t]);
  const errTarget = useMemo(() => validatePrice(targetAvg, t), [targetAvg, t]);
  const errLot = useMemo(() => validateLot(totalLot, t), [totalLot, t]);
  const errLotTambah = useMemo(() => validateLot(lotTambah, t), [lotTambah, t]);

  const canCalculate = useMemo(() => {
    if (!avgPrice || !totalLot || !hargaAvg) return false;
    if (errAvg || errLot || errHarga) return false;
    if (mode === "new-avg") return !!lotTambah && !errLotTambah;
    if (mode === "lots-needed") return !!targetAvg && !errTarget;
    return false;
  }, [
    avgPrice,
    totalLot,
    hargaAvg,
    lotTambah,
    targetAvg,
    mode,
    errAvg,
    errLot,
    errHarga,
    errLotTambah,
    errTarget,
  ]);

  const canCalculateRef = useRef(canCalculate);
  canCalculateRef.current = canCalculate;

  const handlePriceBlur = (value: string, setter: (v: string) => void) => {
    const n = parseFloat(value);
    if (!isFinite(n) || n <= 0 || n > MAX_PRICE) return;
    const rounded = roundToTick(n);
    if (rounded !== n) setter(String(rounded));
  };


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
    const snapshot = currentInputsKey;
    if (mode === "new-avg") {
      const r = calcNewAvg({
        avgSekarang: a,
        lotSekarang: l,
        hargaAveraging: h,
        lotTambah: parseInt(lotTambah),
        fee,
      });
      resultInputsRef.current = snapshot;
      setResult(r);
      saveHistory(r);
    } else {
      const out = calcLotsNeeded({
        avgSekarang: a,
        lotSekarang: l,
        hargaAveraging: h,
        targetAvg: parseFloat(targetAvg),
        fee,
      });
      if ("error" in out) {
        toast.error(out.error);
        return;
      }
      resultInputsRef.current = snapshot;
      setResult(out.result);
      saveHistory(out.result);
    }
  };
  const runCalcRef = useRef(runCalc);
  runCalcRef.current = runCalc;

  const focusFirstInvalid = (): boolean => {
    type FieldCheck = { key: string; bad: boolean; ref: RefObject<HTMLInputElement | null> };
    const checks: FieldCheck[] = [
      { key: "avg", bad: !avgPrice || !!errAvg, ref: firstInputRef },
      { key: "lot", bad: !totalLot || !!errLot, ref: lotRef },
      { key: "harga", bad: !hargaAvg || !!errHarga, ref: hargaRef },
    ];
    if (mode === "new-avg") {
      checks.push({ key: "lotTambah", bad: !lotTambah || !!errLotTambah, ref: lotTambahRef });
    } else if (mode === "lots-needed") {
      checks.push({ key: "target", bad: !targetAvg || !!errTarget, ref: targetRef });
    } else {
      checks.push({ key: "lotTambah", bad: true, ref: lotTambahRef });
    }
    const first = checks.find((c) => c.bad);
    if (!first) return false;
    const el = first.ref.current;
    if (el) {
      try {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      } catch {}
      window.setTimeout(() => el.focus({ preventScroll: true }), 150);
    }
    setFlashField(first.key);
    if (flashTimeoutRef.current) window.clearTimeout(flashTimeoutRef.current);
    flashTimeoutRef.current = window.setTimeout(() => setFlashField(null), 1400);
    return true;
  };
  const focusFirstInvalidRef = useRef(focusFirstInvalid);
  focusFirstInvalidRef.current = focusFirstInvalid;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const active = document.activeElement as HTMLElement | null;
    if (active && typeof active.blur === "function") active.blur();
    setTimeout(() => {
      if (canCalculateRef.current) {
        runCalcRef.current();
      } else {
        focusFirstInvalidRef.current();
      }
    }, 0);
  };

  // Keyboard shortcuts (stable refs to avoid re-binding)
  const resetAllRef = useRef<() => void>(() => {});
  const toggleLangRef = useRef<() => void>(() => {});
  const toggleThemeRef = useRef<() => void>(() => {});
  const toggleFeeRef = useRef<() => void>(() => {});
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      const inInput = tag === "input" || tag === "textarea" || tag === "select";

      // Ctrl/Cmd+Enter or Ctrl/Cmd+K → calculate (works inside inputs too)
      if ((e.ctrlKey || e.metaKey) && (e.key === "Enter" || e.key.toLowerCase() === "k")) {
        e.preventDefault();
        const active = document.activeElement as HTMLElement | null;
        if (active && typeof active.blur === "function") active.blur();
        setTimeout(() => {
          if (canCalculateRef.current) runCalcRef.current();
          else focusFirstInvalidRef.current();
        }, 0);
        return;
      }

      // Alt+R → reset, Alt+L → toggle language, Alt+T → toggle theme, Alt+F → toggle fee
      // Use e.code so it works on macOS where Alt+letter produces special chars.
      if (e.altKey && !e.ctrlKey && !e.metaKey) {
        const code = e.code;
        if (code === "KeyR") {
          e.preventDefault();
          resetAllRef.current();
          return;
        }
        if (code === "KeyL") {
          e.preventDefault();
          toggleLangRef.current();
          return;
        }
        if (code === "KeyT") {
          e.preventDefault();
          toggleThemeRef.current();
          return;
        }
        if (code === "KeyF") {
          e.preventDefault();
          toggleFeeRef.current();
          return;
        }
      }

      if (inInput) return;

      if (e.key === "/") {
        e.preventDefault();
        firstInputRef.current?.focus();
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (canCalculateRef.current) runCalcRef.current();
        else focusFirstInvalidRef.current();
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        resetAllRef.current();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

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

  const resetAll = () => {
    setAvgPrice("");
    setTotalLot("");
    setHargaAvg("");
    setLotTambah("");
    setTargetAvg("");
    setResult(null);
    try {
      localStorage.removeItem(INPUTS_KEY);
    } catch {}
    toast(t.formReset);
  };
  resetAllRef.current = resetAll;
  toggleLangRef.current = toggleLang;
  toggleThemeRef.current = toggleTheme;
  toggleFeeRef.current = () => setFeeOpen((o) => !o);

  const shareLink = async () => {
    if (!result) return;
    const p = new URLSearchParams({
      avg: String(result.avgSekarang),
      lot: String(result.lotSekarang),
      harga: String(result.hargaAveraging),
    });
    if (result.mode === "new-avg") p.set("lotTambah", String(result.lotDelta));
    else if (result.targetAvg) p.set("target", String(result.targetAvg));
    const url = `${window.location.origin}${window.location.pathname}?${p}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success(t.linkCopied);
    } catch {
      toast.error(t.copyFail);
    }
  };

  const copyValue = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label}: ${t.copy}`);
    } catch {
      toast.error(t.copyFail);
    }
  };

  const copySummary = async () => {
    if (!result) return;
    const arrow = result.status === "down" ? "↓" : result.status === "up" ? "↑" : "→";
    const head = result.mode === "new-avg" ? t.avgBaru : t.lotDiperlukan;
    const lines = [
      new Date(result.timestamp).toLocaleString(lang === "id" ? "id-ID" : "en-US"),
      `${head}: ${formatRupiah(result.newAvgPrice)} (${arrow} ${result.percentage.toFixed(2)}%)`,
      `${t.lotBaru}: ${result.totalLotBaru} (+${result.lotDelta})`,
      `${t.modalTambahan}: ${formatRupiah(result.modalTambahan)}`,
      `${t.totalModal}: ${formatRupiah(result.totalModal)}`,
    ];
    if (result.feeEnabled) {
      lines.push(`${t.feeBeliLabel}: ${formatRupiah(result.feeBeli ?? 0)}`);
      lines.push(`${t.breakEven}: ${formatRupiah(result.breakEvenPrice ?? 0)}`);
    }
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      toast.success(t.summaryCopied);
    } catch {
      toast.error(t.copyFail);
    }
  };

  const saveImage = async () => {
    if (!result) return;
    const node = resultRef.current?.offsetParent ? resultRef.current : mobileResultRef.current;
    if (!node) return;
    try {
      const { toPng } = await import("html-to-image");
      const dataUrl = await toPng(node, {
        pixelRatio: 2,
        cacheBust: true,
        backgroundColor: isDark ? "#1a1d2e" : "#ffffff",
      });
      const link = document.createElement("a");
      link.download = `IDXAvg-${todayISO()}.png`;
      link.href = dataUrl;
      link.click();
      toast.success(t.imgSaved);
    } catch (err) {
      console.error(err);
      toast.error(t.imgFail);
    }
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem(HISTORY_KEY);
    toast(t.historyCleared);
  };

  const loadHistory = (r: CalcResult) => {
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
    "h-auto rounded-xl border-2 border-transparent bg-card px-3 py-1.5 text-sm font-bold text-foreground shadow-none transition-all focus-visible:border-primary focus-visible:ring-0 placeholder:text-muted-foreground sm:px-4 sm:py-2.5 sm:text-lg";
  const labelCls =
    "mb-0.5 ml-0.5 block text-[11px] font-semibold text-foreground/70 sm:mb-1 sm:text-sm";
  const sectionHead =
    "mb-2 font-display text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground sm:mb-4 sm:text-xs";
  const cardCls =
    "rounded-2xl border border-white/70 bg-secondary/60 p-2.5 shadow-sm dark:border-white/5 sm:rounded-3xl sm:p-5";
  const flashCls = "border-destructive ring-2 ring-destructive/40 animate-pulse";

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-background text-foreground">
        {/* Header */}
        <header className="mx-auto flex w-full max-w-[480px] items-center justify-between gap-2 px-3 pt-1 pb-0.5 sm:px-4 sm:pt-2 sm:pb-1">
          <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/25 sm:h-11 sm:w-11">
              <Sigma className="h-5 w-5" strokeWidth={2.5} />
            </div>
            <h1 className="min-w-0 leading-tight">
              <span className="font-display text-xl font-extrabold tracking-tight block truncate sm:text-2xl">
                {t.appTitle}
              </span>
              <span className="font-sans text-[11px] font-medium text-muted-foreground block truncate sm:text-xs">
                {t.appTagline}
              </span>
            </h1>
          </div>

          <div className="flex shrink-0 items-center gap-0.5 text-muted-foreground">
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleLang}
              aria-label="Toggle language"
              title="Alt+L"
              className="h-10 gap-1 rounded-xl px-2 text-xs font-bold uppercase hover:bg-secondary hover:text-primary"
            >
              {lang.toUpperCase()}
            </Button>
            <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
              <DialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-10 w-10 rounded-xl hover:bg-secondary hover:text-primary"
                  aria-label={t.history}
                >
                  <History className="h-5 w-5" />
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-[440px] gap-3 rounded-3xl border-border bg-card p-6">
                <DialogHeader className="pt-4">
                  <DialogTitle className="flex items-center justify-between gap-2 font-display text-lg font-extrabold tracking-tight">
                    <span>{t.history}</span>
                    {history.length > 0 && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={clearHistory}
                        aria-label={t.clearHistory}
                        title={t.clearHistory}
                        className="mr-8 h-8 w-8 rounded-lg text-destructive hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </DialogTitle>
                </DialogHeader>
                <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
                  {history.length === 0 ? (
                    <p className="py-6 text-center text-sm font-medium text-muted-foreground">
                      {t.noHistory}
                    </p>
                  ) : (
                    history.map((h) => (
                      <button
                        key={h.id}
                        onClick={() => loadHistory(h)}
                        className="w-full rounded-2xl border border-border bg-secondary/40 p-3 text-left transition-colors hover:border-primary/40 hover:bg-accent"
                      >
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-display text-sm font-bold tabular text-foreground">
                            {formatRupiah(h.avgSekarang)} → {formatRupiah(h.newAvgPrice)}
                          </span>
                          <span className="text-xs font-medium text-muted-foreground">
                            {new Date(h.timestamp).toLocaleDateString(
                              lang === "id" ? "id-ID" : "en-US",
                            )}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center justify-between text-xs font-medium text-muted-foreground tabular">
                          <span>
                            {h.lotSekarang} → {h.totalLotBaru} lot
                          </span>
                          <span
                            className={cn(
                              "font-bold",
                              h.status === "down" && "text-destructive",
                              h.status === "up" && "text-success",
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
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 rounded-xl hover:bg-secondary hover:text-primary"
              onClick={toggleTheme}
              aria-label="Toggle theme"
              title="Alt+T"
            >
              {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
          </div>
        </header>

        {/* Main */}
        <main className="mx-auto w-full max-w-[480px] px-3 pt-2 pb-[calc(4.5rem+env(safe-area-inset-bottom))] sm:px-4 sm:pt-4 sm:pb-4">
          {showRecovered && (
            <div className="pointer-events-none fixed inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-40 flex justify-center animate-in fade-in slide-in-from-bottom-2 duration-300">
              <span className="rounded-full bg-muted/80 px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground backdrop-blur-sm">
                {t.recovered}
              </span>
            </div>
          )}
          <form onSubmit={handleSubmit} noValidate className="space-y-2 sm:space-y-5">
            {/* Position */}
            <section aria-labelledby="posisi-heading" className={cardCls}>
              <div className="mb-2 flex items-center justify-between sm:mb-4">
                <h2 id="posisi-heading" className={cn(sectionHead, "mb-0")}>
                  {t.positionTitle}
                </h2>
                <Tooltip>
                  <TooltipTrigger asChild aria-label="Info">
                    <Info className="h-4 w-4 cursor-help text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent side="left" className="max-w-[220px] text-xs">
                    {t.positionTip}
                  </TooltipContent>
                </Tooltip>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:gap-3">
                <div>
                  <Label htmlFor="avg-now-input" className={labelCls}>
                    {t.avgNow}
                  </Label>

                  <Input
                    id="avg-now-input"
                    ref={firstInputRef}
                    inputMode="decimal"
                    value={avgPrice}
                    onChange={(e) => setAvgPrice(numOnly(e.target.value))}
                    onBlur={(e) => handlePriceBlur(e.target.value, setAvgPrice)}
                    placeholder="0"
                    aria-invalid={!!errAvg}
                    className={cn(
                      inputCls,
                      "tabular",
                      errAvg && "border-destructive focus-visible:border-destructive",
                      flashField === "avg" && flashCls,
                    )}
                    tabIndex={1}
                    autoFocus
                  />
                  {errAvg && (
                    <p className="mt-1 ml-0.5 text-xs font-medium text-destructive">{errAvg}</p>
                  )}
                </div>
                <div>
                  <Label htmlFor="total-lot-input" className={labelCls}>
                    {t.totalLot}
                  </Label>
                  <Input
                    id="total-lot-input"
                    ref={lotRef}
                    inputMode="numeric"
                    value={totalLot}
                    onChange={(e) => setTotalLot(intOnly(e.target.value))}
                    placeholder="0"
                    aria-invalid={!!errLot}
                    className={cn(
                      inputCls,
                      "tabular",
                      errLot && "border-destructive focus-visible:border-destructive",
                      flashField === "lot" && flashCls,
                    )}
                    tabIndex={2}
                  />

                  {errLot && (
                    <p className="mt-1 ml-0.5 text-xs font-medium text-destructive">{errLot}</p>
                  )}
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between rounded-xl border border-white/70 bg-card/60 px-3 py-1.5 dark:border-white/5 sm:mt-4 sm:rounded-2xl sm:px-4 sm:py-3">
                <span className="text-xs font-semibold text-muted-foreground sm:text-sm">
                  {t.modalAwal}
                </span>
                <span className="font-display text-sm font-extrabold tabular sm:text-lg">
                  {formatRupiah(modalAwal)}
                </span>
              </div>
            </section>

            {/* Averaging */}
            <section aria-labelledby="averaging-heading" className={cardCls}>
              <div className="mb-2 flex items-center justify-between sm:mb-4">
                <h2 id="averaging-heading" className={cn(sectionHead, "mb-0")}>
                  {t.averagingTitle}
                </h2>
                <Tooltip>
                  <TooltipTrigger asChild aria-label="Info">
                    <Info className="h-4 w-4 cursor-help text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent side="left" className="max-w-[220px] text-xs">
                    {t.averagingTip}
                  </TooltipContent>
                </Tooltip>
              </div>

              <div className="space-y-1.5 sm:space-y-3">
                <div>
                  <Label htmlFor="harga-avg-input" className={labelCls}>
                    {t.hargaAvg}
                  </Label>

                  <Input
                    id="harga-avg-input"
                    ref={hargaRef}
                    inputMode="decimal"
                    value={hargaAvg}
                    onChange={(e) => setHargaAvg(numOnly(e.target.value))}
                    onBlur={(e) => handlePriceBlur(e.target.value, setHargaAvg)}
                    placeholder="0"
                    aria-invalid={!!errHarga}
                    className={cn(
                      inputCls,
                      "tabular",
                      errHarga && "border-destructive focus-visible:border-destructive",
                      flashField === "harga" && flashCls,
                    )}
                    tabIndex={3}
                  />

                  {errHarga && (
                    <p className="mt-1 ml-0.5 text-xs font-medium text-destructive">{errHarga}</p>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 sm:gap-3">
                  <div className={cn(lotTambahDisabled && "opacity-50")}>
                    <Label htmlFor="lot-tambah-input" className={labelCls}>
                      {t.lotTambah}
                    </Label>
                    <Input
                      id="lot-tambah-input"
                      ref={lotTambahRef}
                      inputMode="numeric"
                      value={lotTambah}
                      onChange={(e) => setLotTambah(intOnly(e.target.value))}
                      placeholder="0"
                      aria-invalid={!!errLotTambah}
                      className={cn(
                        inputCls,
                        "tabular",
                        errLotTambah && "border-destructive focus-visible:border-destructive",
                        flashField === "lotTambah" && flashCls,
                      )}
                      disabled={lotTambahDisabled}
                      tabIndex={4}
                    />
                    {errLotTambah && (
                      <p className="mt-1 ml-0.5 text-xs font-medium text-destructive">
                        {errLotTambah}
                      </p>
                    )}
                  </div>
                  <div className={cn(targetAvgDisabled && "opacity-50")}>
                    <Label htmlFor="target-avg-input" className={labelCls}>
                      {t.targetAvg}
                    </Label>
                    <Input
                      id="target-avg-input"
                      ref={targetRef}
                      inputMode="decimal"
                      value={targetAvg}
                      onChange={(e) => setTargetAvg(numOnly(e.target.value))}
                      onBlur={(e) => handlePriceBlur(e.target.value, setTargetAvg)}
                      placeholder="0"
                      aria-invalid={!!errTarget}
                      className={cn(
                        inputCls,
                        "tabular",
                        errTarget && "border-destructive focus-visible:border-destructive",
                        flashField === "target" && flashCls,
                      )}
                      disabled={targetAvgDisabled}
                      tabIndex={5}
                    />
                    {errTarget && (
                      <p className="mt-1 ml-0.5 text-xs font-medium text-destructive">
                        {errTarget}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </section>

            {/* Fee Section */}
            <Collapsible open={feeOpen} onOpenChange={setFeeOpen} className={cn(cardCls, "py-3 sm:py-4")}>
              <CollapsibleTrigger className="flex w-full items-center justify-between select-none [&[data-state=open]>svg]:rotate-180">
                <span className="inline-flex h-4 items-center font-display text-[11px] font-bold uppercase leading-none tracking-[0.18em] text-muted-foreground sm:text-xs">
                  {t.feeTitle}
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200" />
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="mt-3 space-y-3 sm:mt-4">
                  <label className="flex h-5 cursor-pointer items-center gap-2.5 select-none">
                    <Checkbox
                      checked={fee.enabled}
                      onCheckedChange={(c) => setFee((f) => ({ ...f, enabled: c === true }))}
                      aria-label={t.feeInclude}
                      className="h-4 w-4 rounded-full border-primary/80 bg-transparent shadow-none data-[state=checked]:bg-primary [&_svg]:h-3 [&_svg]:w-3"
                    />
                    <span className="text-xs font-semibold text-foreground sm:text-sm">{t.feeInclude}</span>
                  </label>
                  {fee.enabled && (
                    <div className="grid grid-cols-2 gap-2 sm:gap-3">
                      <div>
                        <Label htmlFor="fee-buy-input" className={labelCls}>
                          {t.feeBuy} (%)
                        </Label>
                        <Input
                          id="fee-buy-input"
                          inputMode="decimal"
                          value={String(fee.buyPct)}
                          onChange={(e) => {
                            const v = numOnly(e.target.value);
                            setFee((f) => ({ ...f, buyPct: v === "" ? 0 : parseFloat(v) || 0 }));
                          }}
                          className={cn(inputCls, "tabular")}
                        />
                      </div>
                      <div>
                        <Label htmlFor="fee-sell-input" className={labelCls}>
                          {t.feeSell} (%)
                        </Label>
                        <Input
                          id="fee-sell-input"
                          inputMode="decimal"
                          value={String(fee.sellPct)}
                          onChange={(e) => {
                            const v = numOnly(e.target.value);
                            setFee((f) => ({ ...f, sellPct: v === "" ? 0 : parseFloat(v) || 0 }));
                          }}
                          className={cn(inputCls, "tabular")}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </CollapsibleContent>
            </Collapsible>

            <Button
              type={canCalculate ? "submit" : "button"}
              onClick={canCalculate ? undefined : () => focusFirstInvalid()}
              title="Ctrl/Cmd+Enter"
              className="font-display flex h-auto w-full items-center justify-center gap-2 rounded-2xl py-2.5 text-sm font-extrabold uppercase tracking-[0.15em] shadow-lg shadow-primary/25 transition-all active:scale-[0.98] sm:rounded-3xl sm:py-5 sm:text-lg disabled:opacity-50"
              aria-disabled={!canCalculate}
            >
              <span>{t.hitung}</span>
            </Button>
          </form>

          {/* Result */}
          {result &&
            (() => {
              const headLabel = result.mode === "new-avg" ? t.avgBaru : t.lotDiperlukan;
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
                  <div className="bg-primary/10 px-4 pt-4 pb-3 sm:px-5 sm:pt-5 sm:pb-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="font-display text-[11px] font-extrabold uppercase tracking-[0.22em] text-primary">
                          {headLabel}
                        </h2>
                        <p className="mt-2 font-display text-3xl font-extrabold leading-none tabular text-foreground break-words sm:text-4xl">
                          {headValue}
                        </p>
                        {result.mode === "lots-needed" && (
                          <p className="mt-2 font-sans text-sm font-semibold text-muted-foreground tabular">
                            {t.avgJadi} {formatRupiah(result.newAvgPrice)}
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
                            "bg-success/15 text-success hover:bg-success/15",
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

                  <div className="space-y-2 px-4 py-3 text-sm font-medium sm:space-y-2.5 sm:px-5 sm:py-4">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t.avgSekarangRow}</span>
                      <span className="font-bold tabular text-foreground">
                        {formatRupiah(result.avgSekarang)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t.totalLot}</span>
                      <span className="font-bold tabular text-foreground">
                        {result.lotSekarang.toLocaleString("id-ID")}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t.hargaAveragingRow}</span>
                      <span className="font-bold tabular text-foreground">
                        {formatRupiah(result.hargaAveraging)}
                      </span>
                    </div>
                    <div className="flex justify-between border-t border-border/70 pt-2.5">
                      <span className="text-muted-foreground">{t.lotBaru}</span>
                      <span className="font-bold tabular text-foreground">
                        {result.totalLotBaru.toLocaleString("id-ID")}{" "}
                        <span className="text-muted-foreground">
                          (+{result.lotDelta.toLocaleString("id-ID")})
                        </span>
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">{t.modalTambahan}</span>
                      <button
                        type="button"
                        onClick={() =>
                          copyValue(t.modalTambahan, formatRupiah(result.modalTambahan))
                        }
                        className="flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
                      >
                        <span className="font-bold tabular text-foreground">
                          {formatRupiah(result.modalTambahan)}
                        </span>
                        <Copy className="h-3 w-3 text-muted-foreground" />
                      </button>
                    </div>
                    {result.feeEnabled && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">
                            {t.feeBeliLabel} ({result.buyPct}%)
                          </span>
                          <span className="font-bold tabular text-foreground">
                            {formatRupiah(result.feeBeli ?? 0)}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">
                            {t.feeJualLabel} ({result.sellPct}%)
                          </span>
                          <span className="font-bold tabular text-foreground">
                            {formatRupiah(result.feeJualEst ?? 0)}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">{t.breakEven}</span>
                          <span className="font-bold tabular text-foreground">
                            {formatRupiah(result.breakEvenPrice ?? 0)}
                          </span>
                        </div>
                      </>
                    )}
                    <div className="flex items-center justify-between border-t border-border/70 pt-2.5">
                      <span className="text-muted-foreground">{t.totalModal}</span>
                      <button
                        type="button"
                        onClick={() => copyValue(t.totalModal, formatRupiah(result.totalModal))}
                        className="flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
                      >
                        <span className="font-display text-base font-extrabold tabular text-foreground">
                          {formatRupiah(result.totalModal)}
                        </span>
                        <Copy className="h-3 w-3 text-muted-foreground" />
                      </button>
                    </div>
                  </div>
                </div>
              );

              const actions = (
                <div className="mt-4 flex items-center justify-center gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={copySummary}
                    aria-label={t.copy}
                    className="h-11 w-11 rounded-2xl border-border bg-card hover:border-primary/40 hover:bg-secondary hover:text-primary"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={shareLink}
                    aria-label={t.share}
                    className="h-11 w-11 rounded-2xl border-border bg-card hover:border-primary/40 hover:bg-secondary hover:text-primary"
                  >
                    <Link2 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={saveImage}
                    aria-label={t.savePng}
                    className="h-11 w-11 rounded-2xl border-border bg-card hover:border-primary/40 hover:bg-secondary hover:text-primary"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={resetAll}
                    aria-label={t.reset}
                    title="Alt+R / Esc"
                    className="h-11 w-11 rounded-2xl border-border bg-card hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              );

              return (
                <>
                  <section className="mt-4 hidden sm:block">
                    {resultCard(resultRef)}
                    {actions}
                  </section>
                  <Drawer open={barOpen} onOpenChange={setBarOpen}>
                    <div className="fixed inset-x-0 bottom-[calc(0.5rem+env(safe-area-inset-bottom))] z-30 flex justify-center px-3 sm:hidden">
                      <DrawerTrigger asChild>
                        <button
                          type="button"
                          className="flex w-full max-w-[440px] items-center justify-between gap-2 rounded-2xl border border-border bg-card px-4 py-2.5 text-left text-foreground shadow-2xl backdrop-blur transition-transform active:scale-[0.98]"
                          aria-label={t.resultTitle}
                        >
                          <div className="min-w-0 space-y-0">
                            <p className="font-display text-[9px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                              {headLabel}
                            </p>
                            <p className="font-display text-base font-extrabold tabular leading-tight text-foreground">
                              {headValue}
                            </p>
                          </div>
                          <div className="h-8 w-px bg-border" />
                          <div className="min-w-0 space-y-0 text-right">
                            <p className="font-display text-[9px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                              {result.status === "down"
                                ? t.turun
                                : result.status === "up"
                                  ? t.naik
                                  : t.flat}
                            </p>
                            <p
                              className={cn(
                                "font-display text-base font-extrabold tabular leading-tight",
                                result.status === "down" && "text-destructive",
                                result.status === "up" && "text-success",
                                result.status === "flat" && "text-foreground",
                              )}
                            >
                              {result.status === "down" ? "↓" : result.status === "up" ? "↑" : "→"}{" "}
                              {result.percentage.toFixed(2)}%
                            </p>
                          </div>
                          <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
                        </button>
                      </DrawerTrigger>
                    </div>
                    <DrawerContent className="sm:hidden">
                      <DrawerHeader className="pb-2">
                        <DrawerTitle className="font-display">{t.resultTitle}</DrawerTitle>
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

        {/* Footer */}
        <footer className="mx-auto mt-6 w-full max-w-[480px] border-t border-border/60 px-4 py-3 font-sans sm:mt-8 sm:py-4">
          <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs font-normal text-muted-foreground">
            <span>
              {t.footerBy}{" "}
              <a
                href="https://x.com/alfindigital"
                target="_blank"
                rel="noreferrer"
                className="font-normal text-foreground/80 hover:text-primary"
              >
                @alfindigital
              </a>
            </span>
            <span aria-hidden="true" className="text-muted-foreground">
              |
            </span>
            <div className="flex items-center gap-0.5">
              <a
                href="https://alfin.digital"
                target="_blank"
                rel="noreferrer"
                aria-label="Website"
                className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
              >
                <Globe className="h-3.5 w-3.5" />
              </a>
              <a
                href="https://facebook.com/alfindigital"
                target="_blank"
                rel="noreferrer"
                aria-label="Facebook"
                className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
              >
                <Facebook className="h-3.5 w-3.5" />
              </a>
              <a
                href="https://youtube.com/@alfindigital"
                target="_blank"
                rel="noreferrer"
                aria-label="YouTube"
                className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
              >
                <Youtube className="h-3.5 w-3.5" />
              </a>
              <a
                href="https://tiktok.com/@alfindigital"
                target="_blank"
                rel="noreferrer"
                aria-label="TikTok"
                className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-3.5 w-3.5"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5.8 20.1a6.34 6.34 0 0 0 10.86-4.43V8.83a8.16 8.16 0 0 0 4.77 1.52V6.9a4.85 4.85 0 0 1-1.84-.21Z" />
                </svg>
              </a>
              <a
                href="https://x.com/alfindigital"
                target="_blank"
                rel="noreferrer"
                aria-label="X (Twitter)"
                className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
              >
                <svg viewBox="0 0 24 24" className="h-3 w-3" fill="currentColor" aria-hidden="true">
                  <path d="M18.244 2H21.5l-7.5 8.575L23 22h-6.844l-5.36-6.99L4.5 22H1.244l8.02-9.166L1 2h7.02l4.85 6.41L18.244 2Zm-2.4 18h1.9L7.27 4H5.27l10.574 16Z" />
                </svg>
              </a>
              <a
                href="https://t.me/alfindx"
                target="_blank"
                rel="noreferrer"
                aria-label="Telegram"
                className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
              >
                <Send className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
        </footer>
      </div>
    </TooltipProvider>
  );
}
