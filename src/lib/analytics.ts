type ClarityWindow = Window & {
  clarity?: (...args: unknown[]) => void;
};

export function trackEvent(name: string) {
  if (typeof window === "undefined") return;
  const cw = window as ClarityWindow;
  if (typeof cw.clarity === "function") {
    cw.clarity("event", name);
  }
}
