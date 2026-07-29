import { useEffect, useState } from "react";
import { Send, X, TrendingUp, Bell } from "lucide-react";

const KEY = "idxavg-tg-popup-v1";
const TG_URL = "https://t.me/lotmetrik";
const DURATION_MS = 5000;

type ClarityWindow = Window & {
  clarity?: (...args: unknown[]) => void;
};

function trackClarityEvent(name: string) {
  if (typeof window === "undefined") return;
  const cw = window as ClarityWindow;
  if (typeof cw.clarity === "function") {
    cw.clarity("event", name);
  }
}

export function TelegramPopup() {
  const [open, setOpen] = useState(false);
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    try {
      if (localStorage.getItem(KEY)) return;
    } catch {}

    const showTimer = setTimeout(() => setOpen(true), 600);
    return () => clearTimeout(showTimer);
  }, []);

  useEffect(() => {
    if (!open) return;

    trackClarityEvent("telegram_popup_impression");

    const start = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const elapsed = now - start;
      const remaining = Math.max(0, DURATION_MS - elapsed);
      setProgress((remaining / DURATION_MS) * 100);
      if (remaining > 0) {
        raf = requestAnimationFrame(tick);
      } else {
        close("auto");
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [open]);

  function close(source: "x" | "later" | "backdrop" | "auto" = "auto") {
    try {
      localStorage.setItem(KEY, "1");
    } catch {}

    if (source === "x") trackClarityEvent("telegram_popup_click_close");
    if (source === "later") trackClarityEvent("telegram_popup_click_later");

    setOpen(false);
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Ajakan bergabung channel Telegram"
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm animate-in fade-in duration-300"
      onClick={(e) => {
        if (e.target === e.currentTarget) close("backdrop");
      }}
    >
      <div className="relative w-[min(92vw,380px)] overflow-hidden rounded-3xl border border-primary/40 bg-card/95 p-6 pt-7 shadow-2xl shadow-primary/25 backdrop-blur-xl animate-in zoom-in-95 slide-in-from-bottom-6 duration-300 dark:border-white/15">
        {/* Countdown bar */}
        <div
          role="timer"
          aria-label="Waktu tersisa sebelum popup tertutup"
          className="absolute left-0 top-0 h-1 w-full bg-secondary"
        >
          <div
            className="h-full bg-gradient-to-r from-primary to-success transition-[width] ease-linear"
            style={{ width: `${progress}%`, transitionDuration: "100ms" }}
          />
        </div>

        <button
          type="button"
          onClick={() => close("x")}
          aria-label="Tutup"
          className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>

        <div className="flex flex-col items-center text-center">
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/30">
            <Send className="h-8 w-8" aria-hidden />
            <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-success text-[10px] font-bold text-success-foreground">
              <Bell className="h-3 w-3" aria-hidden />
            </span>
          </div>

          <h2 className="mt-4 text-lg font-bold leading-tight text-foreground">
            Mau sinyal cuan lebih dulu?
          </h2>

          <p className="mt-2 text-sm text-muted-foreground">
            Gabung channel Telegram{" "}
            <span className="font-semibold text-primary">@lotmetrik</span> —
            update saham, tips averaging, dan peluang momentum langsung ke HP-mu.
          </p>

          <div className="mt-4 flex w-full items-center gap-2 rounded-xl border border-success/30 bg-success/10 px-3 py-2 text-left dark:border-success/20">
            <TrendingUp className="h-5 w-5 shrink-0 text-success" aria-hidden />
            <p className="text-xs leading-snug text-success-strong dark:text-success-foreground">
              Gratis. Tanpa spam. Cukup 1 klik untuk ikut komunitas trader Indonesia.
            </p>
          </div>

          <a
            href={TG_URL}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => {
              trackClarityEvent("telegram_popup_click_join");
              close("auto");
            }}
            className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-bold text-primary-foreground shadow-lg shadow-primary/25 transition-transform hover:scale-[1.02] hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.98]"
          >
            <Send className="h-4 w-4" aria-hidden />
            Join Sekarang — Gratis
          </a>

          <button
            type="button"
            onClick={() => close("later")}
            className="mt-3 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Nanti aja
          </button>
        </div>
      </div>
    </div>
  );
}

export default TelegramPopup;
