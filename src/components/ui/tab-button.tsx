/**
 * Centralized, accessible tab primitive used across the calculator.
 *
 * WAI-ARIA "Tabs" pattern:
 *   - Container is role="tablist"
 *   - Each trigger is role="tab" with aria-selected and aria-controls
 *   - Roving tabindex: only the selected tab is in the tab sequence (tabIndex=0),
 *     inactive tabs get tabIndex=-1. Users Tab into the tablist once, then use
 *     Arrow keys inside.
 *   - Arrow Left/Right (Up/Down too) move focus between tabs and activate them
 *     immediately (automatic-activation flavor — matches the existing Alt+1/Alt+2
 *     shortcut behavior).
 *   - Home / End jump to the first / last tab.
 *   - Each panel is role="tabpanel", labelled by its tab, and focusable via
 *     tabIndex=0 so its content is reachable with a single Tab press after the
 *     tablist.
 *
 * Also owns the shared typography + geometry so tabs stay visually consistent.
 */

import {
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";

// ------------------------------ style tokens ------------------------------

export const tabListCls =
  "relative grid auto-cols-fr grid-flow-col gap-1 rounded-xl bg-card/70 p-1 ring-1 ring-border/60";

export const tabIndicatorCls =
  "pointer-events-none absolute inset-y-1 left-1 rounded-lg bg-primary shadow-sm transition-transform duration-300 ease-out " +
  "w-[calc((100%-0.5rem)/var(--tab-count,2))] " +
  "data-[index='0']:translate-x-0 " +
  "data-[index='1']:translate-x-[calc(100%+0.25rem)] " +
  "data-[index='2']:translate-x-[calc(200%+0.5rem)]";

export const tabButtonCls =
  "relative z-10 inline-flex min-w-0 items-center justify-center whitespace-nowrap rounded-lg font-bold uppercase transition-colors " +
  "h-10 px-1.5 text-[10px] leading-none tracking-[0.04em] " +
  "xs:px-2 xs:text-[11px] xs:tracking-[0.06em] " +
  "sm:h-9 sm:px-3 sm:text-xs sm:tracking-wider " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background";

export const tabButtonActiveCls = "text-primary-foreground";
export const tabButtonInactiveCls = "text-muted-foreground hover:text-foreground";

// ------------------------------ context ------------------------------

type TabsCtx = {
  /** Stable id prefix so tabs and panels can be paired without collisions. */
  idBase: string;
  /** Currently-selected value. */
  value: string;
  /** Move selection to `next`, focusing the newly-active tab. */
  setValue: (next: string) => void;
  /** Registry of tab values in DOM order — used for arrow / Home / End nav. */
  register: (value: string, el: HTMLButtonElement | null) => void;
};

const TabsContext = createContext<TabsCtx | null>(null);

function useTabs(component: string): TabsCtx {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error(`${component} must be used inside <Tabs>`);
  return ctx;
}

export function tabId(idBase: string, value: string) {
  return `${idBase}-tab-${value}`;
}
export function panelId(idBase: string, value: string) {
  return `${idBase}-panel-${value}`;
}

// ------------------------------ root ------------------------------

export interface TabsProps {
  value: string;
  onValueChange: (next: string) => void;
  /** Optional id base for stable tab/panel ids. Falls back to a generated id. */
  id?: string;
  children: ReactNode;
}

export function Tabs({ value, onValueChange, id, children }: TabsProps) {
  const auto = useId();
  const idBase = id ?? `tabs-${auto.replace(/[:]/g, "")}`;
  // Ordered list of registered tab values, keyed by element for stable order.
  const orderRef = useRef<{ value: string; el: HTMLButtonElement }[]>([]);

  const register = useCallback((v: string, el: HTMLButtonElement | null) => {
    const arr = orderRef.current;
    const existing = arr.findIndex((x) => x.value === v);
    if (!el) {
      if (existing >= 0) arr.splice(existing, 1);
      return;
    }
    if (existing >= 0) arr[existing] = { value: v, el };
    else arr.push({ value: v, el });
    // Keep DOM order stable — sort by document position.
    arr.sort((a, b) =>
      a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
    );
  }, []);

  const setValue = useCallback(
    (next: string) => {
      onValueChange(next);
    },
    [onValueChange],
  );

  const ctx = useMemo<TabsCtx>(
    () => ({ idBase, value, setValue, register }),
    [idBase, value, setValue, register],
  );

  return <TabsContext.Provider value={ctx}>{children}</TabsContext.Provider>;
}

// ------------------------------ list + indicator ------------------------------

export interface TabListProps extends HTMLAttributes<HTMLDivElement> {
  tabCount?: number;
  children: ReactNode;
}

export const TabList = forwardRef<HTMLDivElement, TabListProps>(
  ({ tabCount = 2, className, style, children, ...rest }, ref) => (
    <div
      ref={ref}
      role="tablist"
      className={cn(tabListCls, className)}
      style={{ ["--tab-count" as string]: String(tabCount), ...style }}
      {...rest}
    >
      {children}
    </div>
  ),
);
TabList.displayName = "TabList";

export interface TabIndicatorProps extends HTMLAttributes<HTMLSpanElement> {
  activeIndex: number;
}

export const TabIndicator = ({ activeIndex, className, ...rest }: TabIndicatorProps) => (
  <span aria-hidden data-index={activeIndex} className={cn(tabIndicatorCls, className)} {...rest} />
);

// ------------------------------ trigger ------------------------------

export interface TabButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "value" | "role" | "aria-selected"> {
  value: string;
}

export const TabButton = forwardRef<HTMLButtonElement, TabButtonProps>(
  ({ value, className, type = "button", onClick, onKeyDown, children, ...rest }, ref) => {
    const { idBase, value: current, setValue, register } = useTabs("TabButton");
    const active = current === value;
    const localRef = useRef<HTMLButtonElement | null>(null);

    const setRefs = useCallback(
      (el: HTMLButtonElement | null) => {
        localRef.current = el;
        register(value, el);
        if (typeof ref === "function") ref(el);
        else if (ref) (ref as { current: HTMLButtonElement | null }).current = el;
      },
      [ref, register, value],
    );

    // Deregister on unmount.
    useEffect(() => () => register(value, null), [register, value]);

    const handleKeyDown = (e: ReactKeyboardEvent<HTMLButtonElement>) => {
      onKeyDown?.(e);
      if (e.defaultPrevented) return;
      const el = e.currentTarget;
      const parent = el.closest('[role="tablist"]');
      if (!parent) return;
      const tabs = Array.from(
        parent.querySelectorAll<HTMLButtonElement>('[role="tab"]:not([disabled])'),
      );
      if (tabs.length === 0) return;
      const i = tabs.indexOf(el);
      let target: HTMLButtonElement | null = null;
      switch (e.key) {
        case "ArrowRight":
        case "ArrowDown":
          target = tabs[(i + 1) % tabs.length];
          break;
        case "ArrowLeft":
        case "ArrowUp":
          target = tabs[(i - 1 + tabs.length) % tabs.length];
          break;
        case "Home":
          target = tabs[0];
          break;
        case "End":
          target = tabs[tabs.length - 1];
          break;
        default:
          return;
      }
      if (!target) return;
      e.preventDefault();
      const nextValue = target.getAttribute("data-tab-value");
      if (nextValue) setValue(nextValue);
      target.focus();
    };

    return (
      <button
        ref={setRefs}
        type={type}
        role="tab"
        id={tabId(idBase, value)}
        data-tab-value={value}
        aria-selected={active}
        aria-controls={panelId(idBase, value)}
        tabIndex={active ? 0 : -1}
        onClick={(e) => {
          onClick?.(e);
          if (e.defaultPrevented) return;
          setValue(value);
        }}
        onKeyDown={handleKeyDown}
        className={cn(tabButtonCls, active ? tabButtonActiveCls : tabButtonInactiveCls, className)}
        {...rest}
      >
        {children}
      </button>
    );
  },
);
TabButton.displayName = "TabButton";

// ------------------------------ panel ------------------------------

export interface TabPanelProps extends HTMLAttributes<HTMLDivElement> {
  value: string;
  /** When false, the panel is hidden but kept mounted. Default: unmount. */
  keepMounted?: boolean;
}

export const TabPanel = forwardRef<HTMLDivElement, TabPanelProps>(
  ({ value, keepMounted = false, className, children, ...rest }, ref) => {
    const { idBase, value: current } = useTabs("TabPanel");
    const active = current === value;
    if (!active && !keepMounted) return null;
    return (
      <div
        ref={ref}
        role="tabpanel"
        id={panelId(idBase, value)}
        aria-labelledby={tabId(idBase, value)}
        hidden={!active}
        tabIndex={0}
        className={cn("focus-visible:outline-none", className)}
        {...rest}
      >
        {children}
      </div>
    );
  },
);
TabPanel.displayName = "TabPanel";
