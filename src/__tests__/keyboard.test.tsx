// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// jsdom lacks a matchMedia — sonner / radix rely on it in some code paths.
beforeEach(() => {
  if (!window.matchMedia) {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    });
  }
  // scrollIntoView isn't implemented in jsdom.
  Element.prototype.scrollIntoView = vi.fn();
  window.localStorage.clear();
  // Force Indonesian labels so tests are deterministic regardless of jsdom's
  // navigator.language (which defaults to en-US).
  window.localStorage.setItem("idxavg-lang", "id");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function loadCalc() {
  const mod = await import("../components/calculator");
  return mod.Calculator;
}

async function fill(user: ReturnType<typeof userEvent.setup>) {
  const avg = screen.getByLabelText(/Rata-rata Sekarang/i) as HTMLInputElement;
  avg.focus();
  await user.keyboard("1000");
  const lot = screen.getByLabelText(/Total Lot/i) as HTMLInputElement;
  await user.click(lot);
  await user.keyboard("10");
  const harga = screen.getByLabelText(/Harga Beli Tambahan/i) as HTMLInputElement;
  await user.click(harga);
  await user.keyboard("900");
  const lotTambah = screen.getByLabelText(/^Lot Tambah$/i) as HTMLInputElement;
  await user.click(lotTambah);
  await user.keyboard("5");
  return { avg, lot, harga, lotTambah };
}

describe("Calculator keyboard flow", () => {
  it("no input uses a positive tabIndex (natural DOM order)", async () => {
    const Calculator = await loadCalc();
    render(<Calculator />);
    for (const input of screen.getAllByRole("textbox") as HTMLInputElement[]) {
      expect(input.tabIndex).toBeLessThanOrEqual(0);
    }
  });

  it("Enter inside an input advances focus to the next input", async () => {
    const Calculator = await loadCalc();
    render(<Calculator />);
    const user = userEvent.setup();

    const avg = screen.getByLabelText(/Rata-rata Sekarang/i);
    avg.focus();
    await user.keyboard("1000{Enter}");
    expect(document.activeElement).toBe(screen.getByLabelText(/Total Lot/i));
  });

  it("switching mode moves focus to the freshly rendered input", async () => {
    const Calculator = await loadCalc();
    render(<Calculator />);
    const user = userEvent.setup();

    // Default mode: new-avg (Lot Tambah). Switch to lots-needed (Target).
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(2);
    await user.click(tabs[1]);

    await act(async () => {
      await new Promise(requestAnimationFrame);
    });
    const target = screen.getByRole("textbox", { name: /Target Rata-rata/i });
    expect(document.activeElement).toBe(target);
  });

  it("Ctrl+Enter computes the result when the form is valid", async () => {
    const Calculator = await loadCalc();
    render(<Calculator />);
    const user = userEvent.setup();

    await fill(user);
    // Trigger from an input (shortcut must fire even inside inputs).
    await user.keyboard("{Control>}{Enter}{/Control}");

    // Result panel renders the "Rata-rata Baru" label after a successful calc.
    expect(await screen.findByText(/Rata-rata Baru/i)).toBeTruthy();
  });

  it("Alt+R resets all inputs", async () => {
    const Calculator = await loadCalc();
    render(<Calculator />);
    const user = userEvent.setup();

    const { avg } = await fill(user);
    expect((avg as HTMLInputElement).value).toBe("1000");

    // Alt+R uses e.code === 'KeyR' — userEvent maps 'r' to that code.
    await user.keyboard("{Alt>}r{/Alt}");
    expect((avg as HTMLInputElement).value).toBe("");
  });

  it("Alt+L toggles language (Indonesian ↔ English)", async () => {
    const Calculator = await loadCalc();
    render(<Calculator />);
    const user = userEvent.setup();

    // Default heading is Indonesian.
    expect(screen.getByText(/Posisi Saat Ini/i)).toBeTruthy();
    await user.keyboard("{Alt>}l{/Alt}");
    // English heading appears.
    expect(await screen.findByText(/Current Position/i)).toBeTruthy();
  });
});
