// Client-only PWA registration with iframe + Lovable preview guards.
// Service workers must NEVER register inside the editor preview iframe —
// they cache stale content and break the preview routing.

export function registerPWA() {
  if (typeof window === "undefined") return;
  if (!("serviceWorker" in navigator)) return;

  const host = window.location.hostname;
  const isPreviewHost =
    host.includes("id-preview--") ||
    host.includes("lovableproject.com") ||
    (host.includes("lovable.app") === false && host.endsWith(".lovable.dev"));

  let isInIframe = false;
  try {
    isInIframe = window.self !== window.top;
  } catch {
    isInIframe = true;
  }

  if (isPreviewHost || isInIframe) {
    // Clean up any previously registered SW in preview contexts.
    navigator.serviceWorker.getRegistrations().then((regs) => {
      regs.forEach((r) => r.unregister());
    });
    return;
  }

  // Register Workbox-generated SW (vite-plugin-pwa output).
  Promise.all([import("virtual:pwa-register"), import("sonner")])
    .then(([{ registerSW }, { toast }]) => {
      const updateSW = registerSW({
        immediate: true,
        onNeedRefresh() {
          toast("Versi baru tersedia", {
            duration: Infinity,
            action: {
              label: "Muat ulang",
              onClick: () => updateSW(true),
            },
          });
        },
      });
    })
    .catch(() => {
      // virtual module unavailable (e.g. dev without PWA) — ignore.
    });
}
