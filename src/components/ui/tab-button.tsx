/**
 * Centralized tab-button styles used across the calculator.
 *
 * Rationale: font-size, line-height, tracking, height, and horizontal padding
 * for tab labels used to be inlined at every call-site. That made it easy to
 * drift between screens (e.g. one tab picker used `h-9`, another `h-10`, and
 * label wrapping bugs appeared only on 320px). Consolidating here guarantees:
 *   - one source of truth for tab typography + geometry
 *   - identical focus-visible ring across the app
 *   - single place to tune responsive breakpoints (xs → sm)
 */

import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Container geometry — grid, gap, padding, ring. */
export const tabListCls =
  "relative grid auto-cols-fr grid-flow-col gap-1 rounded-xl bg-card/70 p-1 ring-1 ring-border/60";

/**
 * Sliding-indicator geometry. The parent must set --tab-count on the tablist
 * (default 2). `translate-x` is driven by `data-index` on the indicator.
 */
export const tabIndicatorCls =
  "pointer-events-none absolute inset-y-1 left-1 rounded-lg bg-primary shadow-sm transition-transform duration-300 ease-out " +
  "w-[calc((100%-0.5rem)/var(--tab-count,2))] " +
  "data-[index='0']:translate-x-0 " +
  "data-[index='1']:translate-x-[calc(100%+0.25rem)] " +
  "data-[index='2']:translate-x-[calc(200%+0.5rem)]";

/**
 * Per-tab typography + geometry. Kept intentionally identical to the previous
 * inline string so this refactor is a pure move — no visual regressions.
 *
 * Responsive scale:
 *   - default (<=360px):  h-10, text-[10px], px-1.5, tracking-[0.04em]
 *   - xs (>=400px):       text-[11px], px-2, tracking-[0.06em]
 *   - sm (>=640px):       h-9,  text-xs,   px-3, tracking-wider
 *
 * `leading-none` + `whitespace-nowrap` keeps every label on a single line.
 */
export const tabButtonCls =
  "relative z-10 inline-flex min-w-0 items-center justify-center whitespace-nowrap rounded-lg font-bold uppercase transition-colors " +
  "h-10 px-1.5 text-[10px] leading-none tracking-[0.04em] " +
  "xs:px-2 xs:text-[11px] xs:tracking-[0.06em] " +
  "sm:h-9 sm:px-3 sm:text-xs sm:tracking-wider " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background";

export const tabButtonActiveCls = "text-primary-foreground";
export const tabButtonInactiveCls = "text-muted-foreground hover:text-foreground";

export interface TabListProps extends HTMLAttributes<HTMLDivElement> {
  /** Number of tabs — sets the CSS var used by the sliding indicator width. */
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
  /** Zero-based index of the currently active tab. */
  activeIndex: number;
}

export const TabIndicator = ({ activeIndex, className, ...rest }: TabIndicatorProps) => (
  <span aria-hidden data-index={activeIndex} className={cn(tabIndicatorCls, className)} {...rest} />
);

export interface TabButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active: boolean;
}

export const TabButton = forwardRef<HTMLButtonElement, TabButtonProps>(
  ({ active, className, type = "button", children, ...rest }, ref) => (
    <button
      ref={ref}
      type={type}
      role="tab"
      aria-selected={active}
      className={cn(tabButtonCls, active ? tabButtonActiveCls : tabButtonInactiveCls, className)}
      {...rest}
    >
      {children}
    </button>
  ),
);
TabButton.displayName = "TabButton";
