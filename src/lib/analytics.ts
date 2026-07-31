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

/**
 * Funnel: open calculator -> pick mode -> fill inputs -> calculate -> result -> download.
 * Each step fires at most once per browser session so Clarity funnel drop-off
 * rates stay meaningful (no double counting from repeated interactions).
 */
export const FUNNEL = {
  pageView: "funnel_1_calculator_view",
  modeSelected: "funnel_2_mode_selected",
  inputStarted: "funnel_3_input_started",
  calculateAttempt: "funnel_4_calculate_attempt",
  resultShown: "funnel_5_result_shown",
  downloadClick: "funnel_6_download_click",
  downloadSuccess: "funnel_7_download_success",
} as const;

export type FunnelStep = (typeof FUNNEL)[keyof typeof FUNNEL];

const fired = new Set<string>();

export function trackFunnelStep(step: FunnelStep) {
  if (typeof window === "undefined") return;
  if (fired.has(step)) return;
  fired.add(step);
  trackEvent(step);
}

export const VALIDATION = {
  requiredField: "validation_error_required_field",
  priceInvalid: "validation_error_price_invalid",
  lotInvalid: "validation_error_lot_invalid",
  tickInvalid: "validation_error_tick_invalid",
  targetEqualsHarga: "validation_error_target_equals_harga",
  targetUnreachable: "validation_error_target_unreachable",
  maxPrice: "validation_error_max_price",
  maxLot: "validation_error_max_lot",
} as const;

export type ValidationEvent = (typeof VALIDATION)[keyof typeof VALIDATION];

export function trackValidation(event: ValidationEvent) {
  trackEvent(event);
}
