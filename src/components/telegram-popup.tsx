import { useEffect, useState } from "react";
import { Send, X } from "lucide-react";

const KEY = "idxavg-tg-popup-v1";
const TG_URL = "https://t.me/lotmetrik";

export function TelegramPopup() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(KEY)) return;
    } catch {}
    const showTimer = setTimeout(() => setOpen(true), 600);
    const hideTimer = setTimeout(() => close(), 5600);
    return () => {
      clearTimeout(showTimer);
      clearTimeout(hideTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function close() {
    try {
      localStorage.setItem(KEY, "1");
    } catch {}
    setOpen(false);
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-label="Join Telegram channel"
      className="fixed bottom-4 left-1/2 z-50 w-[min(92vw,360px)] -translate-x-1/2 animate-in fade-in slide-in-from-bottom-4 duration-300"
    >
      <div className="relative flex items-center gap-3 rounded-2xl border border-primary/30 bg-card/95 p-3 pr-9 shadow-xl shadow-primary/20 backdrop-blur dark:border-white/10">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Send className="h-5 w-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold leading-tight">Gabung channel Telegram</p>
          <p className="truncate text-xs text-muted-foreground">Update & tips saham dari @lotmetrik</p>
        </div>
        <a
          href={TG_URL}
          target="_blank"
          rel="noopener noreferrer"
          onClick={close}
          className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          Join
        </a>
        <button
          type="button"
          onClick={close}
          aria-label="Close"
          className="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    </div>
  );
}

export default TelegramPopup;
