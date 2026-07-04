import { useEffect, useRef, useState } from "react";

type Social = {
  href: string;
  label: string;
  handle: string;
  path: string;
};

const SOCIALS: Social[] = [
  {
    href: "https://x.com/alfindigital",
    label: "X",
    handle: "@alfindigital",
    path: "M18.2 2.2h3.3l-7.2 8.3 8.5 11.3h-6.7l-5.2-6.8-6 6.8H1.7l7.7-8.8L1.2 2.2H8l4.7 6.2zM17 19.8h1.8L7.1 4.1H5.1z",
  },
  {
    href: "https://www.threads.net/@alfindigitalcom",
    label: "Threads",
    handle: "@alfindigitalcom",
    path: "M12.19 24h-.01c-3.58-.02-6.34-1.2-8.18-3.51C2.35 18.44 1.5 15.59 1.47 12.01v-.02c.03-3.58.88-6.43 2.53-8.48C5.84 1.2 8.6.02 12.18 0h.01c2.75.02 5.04.73 6.83 2.1 1.68 1.29 2.86 3.13 3.51 5.47l-2.04.57c-1.1-3.96-3.9-5.99-8.3-6.02-2.91.02-5.11.94-6.54 2.72C4.31 6.5 3.62 8.91 3.59 12c.03 3.09.72 5.5 2.06 7.16 1.43 1.78 3.63 2.7 6.54 2.72 2.62-.02 4.36-.63 5.8-2.05 1.65-1.61 1.62-3.59 1.09-4.8-.31-.71-.87-1.3-1.63-1.75-.19 1.35-.62 2.45-1.28 3.27-.89 1.1-2.14 1.7-3.73 1.79-1.2.07-2.36-.22-3.26-.8-1.06-.69-1.69-1.74-1.75-2.96-.07-1.19.41-2.29 1.33-3.08.88-.76 2.12-1.21 3.58-1.29 1.07-.06 2.08-.01 3.02.14-.13-.74-.38-1.33-.74-1.76-.5-.59-1.27-.89-2.29-.89h-.03c-.82 0-1.93.22-2.54 1.18l-1.74-1.14c.81-1.25 2.12-1.95 3.69-1.95h.03c3.24.02 5.16 2.02 5.35 5.48.1.05.21.09.32.14 1.49.7 2.58 1.76 3.15 3.07.8 1.82.87 4.79-1.55 7.16-1.85 1.81-4.09 2.63-7.28 2.65zm1.4-9.18c-.32 0-.65.01-.98.03-1.46.08-2.37.75-2.32 1.71.05.99 1.14 1.45 2.19 1.39 1.31-.07 2.5-.59 2.69-2.95a8.5 8.5 0 0 0-1.58-.18z",
  },
  {
    href: "https://youtube.com/@alfindigital",
    label: "YouTube",
    handle: "@alfindigital",
    path: "M23 7.5a3 3 0 0 0-2.1-2.1C19 4.9 12 4.9 12 4.9s-7 0-8.9.5A3 3 0 0 0 1 7.5C.5 9.4.5 12 .5 12s0 2.6.5 4.5a3 3 0 0 0 2.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-4.5.5-4.5s0-2.6-.5-4.5zM9.7 15.4V8.6l5.8 3.4z",
  },
  {
    href: "https://t.me/lotmetrik",
    label: "Telegram",
    handle: "@lotmetrik",
    path: "M9.8 18.7l.3-4.2 7.7-6.9c.3-.3-.1-.5-.5-.2L7.7 13.3 3.6 12c-.9-.3-.9-.9.2-1.3L19.8 4.5c.7-.3 1.4.2 1.1 1.3l-2.7 12.8c-.2.9-.7 1.1-1.5.7L12.6 16.3l-2 1.9c-.2.2-.4.4-.8.4z",
  },
  {
    href: "https://instagram.com/lotmetrik",
    label: "Instagram",
    handle: "@lotmetrik",
    path: "M12 2.2c3.2 0 3.6 0 4.85.07 1.17.05 1.8.25 2.23.42.56.22.96.48 1.38.9.42.42.68.82.9 1.38.17.42.37 1.06.42 2.23.06 1.25.07 1.63.07 4.85s0 3.6-.07 4.85c-.05 1.17-.25 1.8-.42 2.23-.22.56-.48.96-.9 1.38-.42.42-.82.68-1.38.9-.42.17-1.06.37-2.23.42-1.25.06-1.63.07-4.85.07s-3.6 0-4.85-.07c-1.17-.05-1.8-.25-2.23-.42-.56-.22-.96-.48-1.38-.9-.42-.42-.68-.82-.9-1.38-.17-.42-.37-1.06-.42-2.23C2.2 15.6 2.2 15.22 2.2 12s0-3.6.07-4.85c.05-1.17.25-1.8.42-2.23.22-.56.48-.96.9-1.38.42-.42.82-.68 1.38-.9.42-.17 1.06-.37 2.23-.42C8.4 2.2 8.78 2.2 12 2.2zm0 1.8c-3.16 0-3.53.01-4.77.07-1.07.05-1.65.23-2.04.38-.51.2-.88.44-1.26.82-.38.38-.62.75-.82 1.26-.15.39-.33.97-.38 2.04C2.67 8.47 2.66 8.84 2.66 12s.01 3.53.07 4.77c.05 1.07.23 1.65.38 2.04.2.51.44.88.82 1.26.38.38.75.62 1.26.82.39.15.97.33 2.04.38 1.24.06 1.61.07 4.77.07s3.53-.01 4.77-.07c1.07-.05 1.65-.23 2.04-.38.51-.2.88-.44 1.26-.82.38-.38.62-.75.82-1.26.15-.39.33-.97.38-2.04.06-1.24.07-1.61.07-4.77s-.01-3.53-.07-4.77c-.05-1.07-.23-1.65-.38-2.04-.2-.51-.44-.88-.82-1.26-.38-.38-.75-.62-1.26-.82-.39-.15-.97-.33-2.04-.38C15.53 4.01 15.16 4 12 4zm0 3.06a4.94 4.94 0 1 1 0 9.88 4.94 4.94 0 0 1 0-9.88zm0 8.14a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4zm5.13-8.34a1.15 1.15 0 1 1 0-2.3 1.15 1.15 0 0 1 0 2.3z",
  },
  {
    href: "https://tiktok.com/@lotmetrik",
    label: "TikTok",
    handle: "@lotmetrik",
    path: "M20.5 8.6a7.3 7.3 0 0 1-4.3-1.4v7.9a5.9 5.9 0 1 1-5.9-5.9c.3 0 .6 0 .9.08v3a3 3 0 1 0 2.1 2.87V2h2.9a4.4 4.4 0 0 0 4.3 4.4z",
  },
];

const FOOTER_CSS = `
.afd-foot{position:relative;overflow:hidden;font-family:inherit;background:var(--card,var(--background));border-top:1px solid var(--border);padding:10px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.afd-foot>*{position:relative;z-index:1}
.afd-glow{position:absolute;top:-40%;bottom:-40%;width:48%;border-radius:50%;z-index:0;pointer-events:none;left:-48%;background:radial-gradient(closest-side, color-mix(in oklab, var(--primary) 22%, transparent), transparent);filter:blur(8px);transition:left 6s ease-in-out, top 6s ease-in-out}
.afd-cr{font-size:11px;color:var(--muted-foreground);display:inline-flex;align-items:center;border-left:3px solid var(--primary);padding-left:9px}
.afd-brand{color:var(--primary);font-weight:600;text-decoration:none;margin-left:4px}
.afd-brand:hover{text-decoration:underline}
.afd-caret{display:inline-block;width:6px;height:12px;background:var(--primary);margin-left:3px;animation:afd-blink 1.1s step-end infinite}
@keyframes afd-blink{50%{opacity:0}}
.afd-rot{position:relative;height:28px;min-width:160px;flex:0 0 auto}
.afd-item{position:absolute;right:0;top:0;height:28px;display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--foreground);font-size:12px;opacity:0;transform:translateY(6px);transition:opacity .5s,transform .5s;pointer-events:none}
.afd-item.afd-active{opacity:1;transform:translateY(0);pointer-events:auto}
.afd-item b{color:var(--primary);font-weight:600}
.afd-ico{position:relative;width:28px;height:28px;border-radius:50%;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;background:color-mix(in oklab, var(--primary) 11%, transparent);color:var(--primary);transition:all .25s}
.afd-ico svg{width:15px;height:15px}
.afd-rot:hover .afd-item.afd-active .afd-ico{background:var(--primary);color:var(--card,var(--background))}
.afd-rot:hover .afd-item.afd-active .afd-ico::after{content:"";position:absolute;inset:0;border-radius:50%;animation:afd-ripple 1.3s ease-out infinite}
@keyframes afd-ripple{0%{box-shadow:0 0 0 0 color-mix(in oklab, var(--primary) 50%, transparent)}100%{box-shadow:0 0 0 16px color-mix(in oklab, var(--primary) 0%, transparent)}}
`;

export function SiteFooter() {
  const [active, setActive] = useState(0);
  const pausedRef = useRef(false);
  const glowRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const id = setInterval(() => {
      if (pausedRef.current) return;
      setActive((i) => (i + 1) % SOCIALS.length);
    }, 2300);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;
    const move = () => {
      const el = glowRef.current;
      if (el) {
        el.style.left = Math.random() * 120 - 30 + "%";
        el.style.top = Math.random() * 60 - 30 + "%";
      }
      timeoutId = setTimeout(move, 4000 + Math.random() * 4000);
    };
    move();
    return () => clearTimeout(timeoutId);
  }, []);

  const year = new Date().getFullYear();

  return (
    <footer className="afd-foot">
      <style>{FOOTER_CSS}</style>
      <div className="afd-glow" ref={glowRef} />
      <span className="afd-cr">
        © {year}
        <a
          href="https://alfindigital.com"
          target="_blank"
          rel="noopener noreferrer"
          className="afd-brand"
        >
          alfindigital
        </a>
        <span className="afd-caret" />
      </span>
      <div
        className="afd-rot"
        onMouseEnter={() => (pausedRef.current = true)}
        onMouseLeave={() => (pausedRef.current = false)}
      >
        {SOCIALS.map((s, idx) => (
          <a
            key={s.label}
            className={`afd-item${idx === active ? " afd-active" : ""}`}
            href={s.href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={s.label}
          >
            <span className="afd-ico">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d={s.path} />
              </svg>
            </span>
            <b>{s.handle}</b>
          </a>
        ))}
      </div>
    </footer>
  );
}

export default SiteFooter;
