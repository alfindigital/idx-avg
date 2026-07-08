"use client";

import { type FormEvent, type RefObject, useEffect, useMemo, useRef, useState } from "react";
import {
  Moon,
  Sun,
  History,
  Trash2,
  Link2,
  Download,
  Upload,
  FileDown,
  TrendingDown,
  TrendingUp,
  X,
  Info,
  ChevronDown,
  Send,
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
import { SiteFooter } from "@/components/site-footer";
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
const FEE_KEY = "idxavg-fee-v2";

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
  // Which averaging mode the user picked — exclusive. Default: compute new avg from Add Lots.
  const [pickedMode, setPickedMode] = useState<CalcMode>("new-avg");

  const selectMode = (m: CalcMode) => {
    setPickedMode(m);
    if (m === "new-avg") setTargetAvg("");
    else setLotTambah("");
  };

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
    // Sanitize a stored/URL price string: drop non-numeric, parse, and only
    // return it if it falls within the valid input bounds. Returns "" otherwise.
    const sanitizePrice = (raw: unknown): string => {
      if (typeof raw !== "string") return "";
      const cleaned = numOnly(raw);
      if (!cleaned) return "";
      const n = parseFloat(cleaned);
      if (!isFinite(n) || n <= 0 || n > MAX_PRICE) return "";
      return cleaned;
    };
    const sanitizeLot = (raw: unknown): string => {
      if (typeof raw !== "string") return "";
      const cleaned = intOnly(raw);
      if (!cleaned) return "";
      const n = Number(cleaned);
      if (!Number.isInteger(n) || n <= 0 || n > MAX_LOT) return "";
      return cleaned;
    };
    // Validate a CalcResult shape before trusting it from storage. A future
    // schema change or hand-edited storage value must never crash the History UI.
    const isValidHistoryItem = (h: unknown): h is CalcResult => {
      if (!h || typeof h !== "object") return false;
      const o = h as Record<string, unknown>;
      return (
        typeof o.id === "string" &&
        typeof o.timestamp === "number" &&
        (o.mode === "new-avg" || o.mode === "lots-needed") &&
        typeof o.avgSekarang === "number" &&
        typeof o.lotSekarang === "number" &&
        typeof o.newAvgPrice === "number" &&
        typeof o.totalLotBaru === "number" &&
        typeof o.lotDelta === "number" &&
        typeof o.totalModal === "number" &&
        (o.status === "down" || o.status === "up" || o.status === "flat") &&
        typeof o.percentage === "number"
      );
    };

    try {
      const h = localStorage.getItem(HISTORY_KEY);
      if (h) {
        const parsed = JSON.parse(h);
        if (Array.isArray(parsed)) {
          setHistory(parsed.filter(isValidHistoryItem).slice(0, 20));
        }
      }
    } catch {}
    try {
      const f = localStorage.getItem(FEE_KEY);
      if (f) {
        const v = JSON.parse(f);
        const clampPct = (n: unknown, fallback: number) =>
          typeof n === "number" && isFinite(n) && n >= 0 && n <= 5 ? n : fallback;
        setFee({
          enabled: typeof v.enabled === "boolean" ? v.enabled : true,
          buyPct: clampPct(v.buyPct, 0.15),
          sellPct: clampPct(v.sellPct, 0.25),
        });
      }
    } catch {}

    let recovered = false;
    try {
      const saved = localStorage.getItem(INPUTS_KEY);
      if (saved) {
        const v = JSON.parse(saved);
        const sAvg = sanitizePrice(v.avgPrice);
        const sLot = sanitizeLot(v.totalLot);
        const sHarga = sanitizePrice(v.hargaAvg);
        const sLotTambah = sanitizeLot(v.lotTambah);
        const sTarget = sanitizePrice(v.targetAvg);
        if (sAvg) setAvgPrice(sAvg);
        if (sLot) setTotalLot(sLot);
        if (sHarga) setHargaAvg(sHarga);
        if (v.mode === "new-avg") {
          if (sLotTambah) setLotTambah(sLotTambah);
          setTargetAvg("");
          setPickedMode("new-avg");
        } else if (v.mode === "lots-needed") {
          if (sTarget) setTargetAvg(sTarget);
          setLotTambah("");
          setPickedMode("lots-needed");
        } else {
          if (sLotTambah) setLotTambah(sLotTambah);
          if (sTarget) setTargetAvg(sTarget);
          if (sTarget && !sLotTambah) setPickedMode("lots-needed");
        }
        recovered = !!(sAvg || sLot || sHarga || sLotTambah || sTarget);
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

    // URL params — sanitize and clamp to MAX_PRICE / MAX_LOT so a crafted link
    // can never push an out-of-range value into state on first paint.
    const p = new URLSearchParams(window.location.search);
    const urlAvg = sanitizePrice(p.get("avg") ?? "");
    const urlLot = sanitizeLot(p.get("lot") ?? "");
    const urlHarga = sanitizePrice(p.get("harga") ?? "");
    const urlLotTambah = sanitizeLot(p.get("lotTambah") ?? "");
    const urlTarget = sanitizePrice(p.get("target") ?? "");
    if (urlAvg) setAvgPrice(urlAvg);
    if (urlLot) setTotalLot(urlLot);
    if (urlHarga) setHargaAvg(urlHarga);
    if (urlLotTambah) {
      setLotTambah(urlLotTambah);
      setTargetAvg("");
      setPickedMode("new-avg");
    } else if (urlTarget) {
      setTargetAvg(urlTarget);
      setLotTambah("");
      setPickedMode("lots-needed");
    }

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
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    } catch {
      // Storage quota exceeded or unavailable (Safari private mode); history
      // stays in memory for this session.
    }
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
    } else {
      document.documentElement.classList.remove("dark");
    }
    try {
      localStorage.setItem(THEME_KEY, n ? "dark" : "light");
    } catch {
      // Storage unavailable; theme applies for this session only.
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
    const node = resultRef.current;
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

  const fileInputRef = useRef<HTMLInputElement>(null);

  const exportHistory = () => {
    try {
      const blob = new Blob([JSON.stringify(history, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `idxavg-history-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(t.historyExported);
    } catch {
      toast.error(t.copyFail);
    }
  };

  const importHistory = async (file: File) => {
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      if (!Array.isArray(parsed)) throw new Error("not array");
      const isValid = (h: unknown): h is CalcResult => {
        if (!h || typeof h !== "object") return false;
        const o = h as Record<string, unknown>;
        return (
          typeof o.id === "string" &&
          typeof o.timestamp === "number" &&
          (o.mode === "new-avg" || o.mode === "lots-needed") &&
          typeof o.avgSekarang === "number" &&
          typeof o.lotSekarang === "number" &&
          typeof o.newAvgPrice === "number" &&
          typeof o.totalLotBaru === "number" &&
          typeof o.lotDelta === "number" &&
          typeof o.totalModal === "number" &&
          (o.status === "down" || o.status === "up" || o.status === "flat") &&
          typeof o.percentage === "number"
        );
      };
      const valid = parsed.filter(isValid);
      if (valid.length === 0) {
        toast.error(t.historyImportFail);
        return;
      }
      // Merge by id, newest first, cap 20
      const map = new Map<string, CalcResult>();
      [...valid, ...history].forEach((h) => map.set(h.id, h));
      const merged = Array.from(map.values())
        .sort((a, b) => b.timestamp - a.timestamp)
        .slice(0, 20);
      setHistory(merged);
      try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(merged));
      } catch {}
      toast.success(t.historyImported(valid.length));
    } catch {
      toast.error(t.historyImportFail);
    }
  };

  const loadHistory = (r: CalcResult) => {
    setAvgPrice(String(r.avgSekarang));
    setTotalLot(String(r.lotSekarang));
    setHargaAvg(String(r.hargaAveraging));
    if (r.mode === "new-avg") {
      setLotTambah(String(r.lotDelta));
      setTargetAvg("");
      setPickedMode("new-avg");
    } else {
      setTargetAvg(String(r.targetAvg ?? ""));
      setLotTambah("");
      setPickedMode("lots-needed");
    }
    setResult(r);
    setHistoryOpen(false);
  };


  const inputCls =
    "h-11 w-full rounded-xl border-2 border-transparent bg-card px-3.5 text-base font-bold text-foreground shadow-none transition-all scroll-mt-24 focus-visible:border-primary focus-visible:ring-0 placeholder:text-muted-foreground";
  const labelCls =
    "mb-1 ml-0.5 flex h-8 items-end text-xs font-semibold leading-tight text-foreground/70";
  const sectionHead =
    "mb-3 font-display text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground";
  const cardCls =
    "rounded-2xl border border-white/70 bg-secondary/60 p-4 shadow-sm dark:border-white/5 border-l-2 border-l-primary/15";
  const flashCls = "border-destructive ring-2 ring-destructive/40 animate-pulse";

  // Enter → jump to next input; last input → submit form.
  const advanceOnEnter =
    (next?: RefObject<HTMLInputElement | null>) =>
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key !== "Enter") return;
      if (e.nativeEvent.isComposing) return;
      if (!next) return; // let the form's onSubmit handle it
      e.preventDefault();
      const el = next.current;
      if (!el) return;
      try {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      } catch {}
      el.focus({ preventScroll: true });
    };
  const lastInputRef = pickedMode === "new-avg" ? lotTambahRef : targetRef;

  return (
    <TooltipProvider delayDuration={150}>
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
            <h1 className="min-w-0 leading-tight">
              <span className="font-display text-xl font-extrabold tracking-tight block truncate">
                {t.appTitle}
              </span>
              <span className="font-sans text-[11px] font-medium text-muted-foreground block truncate">
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
                <DialogHeader>
                  <DialogTitle className="font-display text-lg font-extrabold tracking-tight">
                    {t.history}
                  </DialogTitle>
                  <div className="absolute right-10 top-2.5 flex items-center gap-0.5">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="application/json,.json"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) importHistory(f);
                        e.target.value = "";
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => fileInputRef.current?.click()}
                      aria-label={t.importHistory}
                      title={t.importHistory}
                      className="h-7 w-7 rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                    >
                      <Upload className="h-4 w-4" />
                    </Button>
                    {history.length > 0 && (
                      <>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={exportHistory}
                          aria-label={t.exportHistory}
                          title={t.exportHistory}
                          className="h-7 w-7 rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                        >
                          <FileDown className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={clearHistory}
                          aria-label={t.clearHistory}
                          title={t.clearHistory}
                          className="h-7 w-7 rounded-md text-destructive hover:bg-destructive/10 hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                  </div>
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
        <main className="mx-auto w-full max-w-[480px] flex-1 px-4 pt-4 pb-6">
          {showRecovered && (
            <div className="pointer-events-none fixed inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-40 flex justify-center animate-in fade-in slide-in-from-bottom-2 duration-300">
              <span className="rounded-full bg-muted/80 px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground backdrop-blur-sm">
                {t.recovered}
              </span>
            </div>
          )}
          <form onSubmit={handleSubmit} noValidate className="space-y-3">
            {/* Position */}
            <section aria-labelledby="posisi-heading" className={cardCls}>
              <div className="mb-3 flex items-center justify-between">
                <h2 id="posisi-heading" className={cn(sectionHead, "mb-0")}>
                  {t.positionTitle}
                </h2>
                <Tooltip>
                  <TooltipTrigger asChild aria-label="Info">
                    <Info className="h-4 w-4 cursor-help text-primary/60" />
                  </TooltipTrigger>
                  <TooltipContent side="left" className="max-w-[220px] text-xs">
                    {t.positionTip}
                  </TooltipContent>
                </Tooltip>
              </div>
              <div className="grid grid-cols-2 gap-3">
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
              <div className="mt-3 flex items-center justify-between rounded-xl border border-white/70 bg-primary/[0.04] px-4 py-2.5 dark:border-white/5">
                <span className="text-sm font-semibold text-primary/70">
                  {t.modalAwal}
                </span>
                <span className="font-display text-base font-extrabold tabular">
                  {formatRupiah(modalAwal)}
                </span>
              </div>
            </section>

            {/* Averaging */}
            <section aria-labelledby="averaging-heading" className={cardCls}>
              <div className="mb-3 flex items-center justify-between">
                <h2 id="averaging-heading" className={cn(sectionHead, "mb-0")}>
                  {t.averagingTitle}
                </h2>
                <Tooltip>
                  <TooltipTrigger asChild aria-label="Info">
                    <Info className="h-4 w-4 cursor-help text-primary/60" />
                  </TooltipTrigger>
                  <TooltipContent side="left" className="max-w-[220px] text-xs">
                    {t.averagingTip}
                  </TooltipContent>
                </Tooltip>
              </div>

              <div className="space-y-3">
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

                {/* Mode picker — these two calculations are mutually exclusive */}
                <div
                  role="tablist"
                  aria-label={t.averagingTip}
                  className="relative grid grid-cols-2 gap-1 rounded-xl bg-card/70 p-1 ring-1 ring-border/60"
                >
                  <span
                    aria-hidden
                    className={cn(
                      "pointer-events-none absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-lg bg-primary shadow-sm transition-transform duration-300 ease-out",
                      pickedMode === "lots-needed" && "translate-x-[calc(100%+0.25rem)]",
                    )}
                  />
                  {(
                    [
                      { key: "new-avg" as const, label: t.lotTambah },
                      { key: "lots-needed" as const, label: t.targetAvg },
                    ]
                  ).map((opt) => {
                    const active = pickedMode === opt.key;
                    return (
                      <button
                        key={opt.key}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        onClick={() => selectMode(opt.key)}
                        className={cn(
                          "relative z-10 h-9 rounded-lg px-3 text-xs font-bold uppercase tracking-wider transition-colors",
                          active ? "text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
                {pickedMode === "new-avg" ? (
                  <div>
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
                      tabIndex={4}
                    />
                    {errLotTambah && (
                      <p className="mt-1 ml-0.5 text-xs font-medium text-destructive">
                        {errLotTambah}
                      </p>
                    )}
                  </div>
                ) : (
                  <div>
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
                      tabIndex={4}
                    />
                    {errTarget && (
                      <p className="mt-1 ml-0.5 text-xs font-medium text-destructive">
                        {errTarget}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </section>

            {/* Fee Section */}
            <Collapsible open={feeOpen} onOpenChange={setFeeOpen} className={cn(cardCls, "py-3.5")}>
              <CollapsibleTrigger className="flex w-full items-center justify-between select-none [&[data-state=open]>svg]:rotate-180">
                <span className="inline-flex h-4 items-center font-display text-xs font-bold uppercase leading-none tracking-[0.18em] text-muted-foreground">
                  {t.feeTitle}
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200" />
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="mt-3 space-y-3">
                  <label className="flex h-5 cursor-pointer items-center gap-2.5 select-none">
                    <Checkbox
                      checked={fee.enabled}
                      onCheckedChange={(c) => setFee((f) => ({ ...f, enabled: c === true }))}
                      aria-label={t.feeInclude}
                      className="h-4 w-4 rounded-full border-primary/80 bg-transparent shadow-none data-[state=checked]:bg-primary [&_svg]:h-3 [&_svg]:w-3"
                    />
                    <span className="text-sm font-semibold text-foreground">{t.feeInclude}</span>
                  </label>
                  {fee.enabled && (
                    <div className="grid grid-cols-2 gap-3">
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
                            const n = v === "" ? 0 : parseFloat(v) || 0;
                            setFee((f) => ({ ...f, buyPct: Math.min(5, Math.max(0, n)) }));
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
                            const n = v === "" ? 0 : parseFloat(v) || 0;
                            setFee((f) => ({ ...f, sellPct: Math.min(5, Math.max(0, n)) }));
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
              className="font-display flex h-12 w-full items-center justify-center gap-2 rounded-2xl text-base font-extrabold uppercase tracking-[0.15em] shadow-lg shadow-primary/25 transition-all active:scale-[0.98] disabled:opacity-50"
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
                  <div className="bg-primary/10 px-4 pt-4 pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="font-display text-[11px] font-extrabold uppercase tracking-[0.22em] text-primary">
                          {headLabel}
                        </h2>
                        <p className="mt-2 font-display text-3xl font-extrabold leading-none tabular text-foreground break-words">
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

                  <div className="space-y-2.5 px-4 py-4 text-sm font-medium">
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
                  <section className="mt-4">
                    {resultCard(resultRef)}
                    {actions}
                  </section>
                </>
              );
            })()}
        </main>

        {/* Footer */}
        <div className="mx-auto mt-auto w-full max-w-[480px]">
          <SiteFooter />
        </div>
      </div>
    </TooltipProvider>
  );
}
