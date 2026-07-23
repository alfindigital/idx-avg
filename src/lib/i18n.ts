"use client";

import { useEffect, useState } from "react";

export type Lang = "id" | "en";

const LANG_KEY = "idxavg-lang";

export const dict = {
  id: {
    appTitle: "IDXAvg",
    appTagline: "Kalkulator rata-rata IDX",
    history: "Riwayat",
    clearHistory: "Hapus",
    exportHistory: "Ekspor",
    importHistory: "Impor",
    historyExported: "Riwayat diekspor",
    historyImported: (n: number) => `${n} riwayat diimpor`,
    historyImportFail: "File tidak valid",
    updateAvailable: "Versi baru tersedia",
    refresh: "Muat ulang",
    noHistory: "Belum ada riwayat.",
    recovered: "Data sebelumnya dipulihkan",
    positionTitle: "Posisi Saat Ini",
    positionTip: "Isi Rata-rata Sekarang dan Total Lot dari posisi saham yang sedang kamu pegang.",
    avgNow: "Rata-rata Sekarang (Rp)",
    totalLot: "Total Lot",
    modalAwal: "Modal Awal",
    averagingTitle: "Pembelian Tambahan",
    averagingTip: "Isi Lot Tambah untuk hitung rata-rata baru, atau Target Rata-rata untuk hitung lot yang dibutuhkan.",
    hargaAvg: "Harga Beli Tambahan (Rp)",
    lotTambah: "Lot Tambah",
    targetAvg: "Target Rata-rata (Rp)",
    feeTitle: "Biaya Beli/Jual",
    feeInclude: "Sertakan biaya",
    feeBuy: "Biaya Beli",
    feeSell: "Biaya Jual",
    feeHint: "Default broker: beli 0,15% • jual 0,25%",
    hitung: "Hitung",
    fillHint: "Isi Lot Tambah atau Target Rata-rata",
    avgBaru: "Rata-rata Baru",
    lotDiperlukan: "Lot Diperlukan",
    avgJadi: "Rata-rata jadi",
    lotBaru: "Lot Baru",
    modalTambahan: "Modal Tambahan",
    totalModal: "Total Modal",
    feeBeliLabel: "Biaya Beli",
    feeJualLabel: "Perkiraan Biaya Jual",
    breakEven: "Harga Impas",
    projTitle: "Proyeksi TP / CL",
    projTP: "Take Profit",
    projCL: "Cut Loss",
    hargaAveragingRow: "Harga Beli Tambahan",
    avgSekarangRow: "Rata-rata Sekarang",
    copy: "Salin",
    share: "Salin link",
    savePng: "Simpan PNG",
    reset: "Reset",
    resultTitle: "Hasil Perhitungan",
    naik: "Naik",
    turun: "Turun",
    flat: "Flat",
    summaryCopied: "Ringkasan disalin",
    linkCopied: "Link disalin",
    copyFail: "Gagal menyalin",
    imgSaved: "Gambar disimpan",
    imgFail: "Gagal menyimpan gambar",
    historyCleared: "Riwayat dihapus",
    formReset: "Form direset",
    tickHint: "Mengikuti fraksi harga IDX",
    tickError: (tick: number, suggest: number) =>
      `Tidak sesuai fraksi IDX (kelipatan ${tick}). Saran: ${suggest}`,
    positive: "Harus angka > 0",
    integerPositive: "Bilangan bulat > 0",
    maxLot: (n: number) => `Maks ${n.toLocaleString("id-ID")} lot`,
    maxPrice: (rp: string) => `Maks ${rp}`,
    targetEqualsHarga: "Target tidak boleh sama dengan harga averaging",
    targetUnreachable: "Tidak bisa mencapai target dengan harga ini",
    footerBy: "by",
  },
  en: {
    appTitle: "IDXAvg",
    appTagline: "IDX averaging calculator",
    history: "History",
    clearHistory: "Clear",
    exportHistory: "Export",
    importHistory: "Import",
    historyExported: "History exported",
    historyImported: (n: number) => `${n} item(s) imported`,
    historyImportFail: "Invalid file",
    updateAvailable: "New version available",
    refresh: "Refresh",
    noHistory: "No history yet.",
    recovered: "Previous data restored",
    positionTitle: "Current Position",
    positionTip: "Fill in your current Avg Price and Total Lots.",
    avgNow: "Current Avg (Rp)",
    totalLot: "Total Lots",
    modalAwal: "Initial Capital",
    averagingTitle: "Averaging",
    averagingTip: "Fill Add Lots to compute new avg, or Target Avg to compute lots needed.",
    hargaAvg: "Averaging Price (Rp)",
    lotTambah: "Add Lots",
    targetAvg: "Target Avg (Rp)",
    feeTitle: "Buy/Sell Fee",
    feeInclude: "Include fees",
    feeBuy: "Buy Fee",
    feeSell: "Sell Fee",
    feeHint: "Default broker: buy 0.15% • sell 0.25%",
    hitung: "Calculate",
    fillHint: "Fill Add Lots or Target Avg",
    avgBaru: "New Avg",
    lotDiperlukan: "Lots Needed",
    avgJadi: "Avg becomes",
    lotBaru: "New Lots",
    modalTambahan: "Added Capital",
    totalModal: "Total Capital",
    feeBeliLabel: "Buy Fee",
    feeJualLabel: "Est. Sell Fee",
    breakEven: "Break Even Price",
    projTitle: "TP / SL Projection",
    projTP: "Take Profit",
    projCL: "Stop Loss",
    hargaAveragingRow: "Averaging Price",
    avgSekarangRow: "Current Avg",
    copy: "Copy",
    share: "Copy link",
    savePng: "Save PNG",
    reset: "Reset",
    resultTitle: "Calculation Result",
    naik: "Up",
    turun: "Down",
    flat: "Flat",
    summaryCopied: "Summary copied",
    linkCopied: "Link copied",
    copyFail: "Copy failed",
    imgSaved: "Image saved",
    imgFail: "Failed to save image",
    historyCleared: "History cleared",
    formReset: "Form reset",
    tickHint: "Follows IDX price fraction",
    tickError: (tick: number, suggest: number) =>
      `Not on IDX tick (multiple of ${tick}). Suggest: ${suggest}`,
    positive: "Must be > 0",
    integerPositive: "Positive integer",
    maxLot: (n: number) => `Max ${n.toLocaleString("en-US")} lots`,
    maxPrice: (rp: string) => `Max ${rp}`,
    footerBy: "by",
  },
};

export type Dict = typeof dict.id;

export function useLang() {
  const [lang, setLang] = useState<Lang>("id");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(LANG_KEY) as Lang | null;
      if (saved === "id" || saved === "en") {
        setLang(saved);
      } else if (typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("en")) {
        setLang("en");
      }
    } catch {}
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LANG_KEY, lang);
      if (typeof document !== "undefined") {
        document.documentElement.lang = lang;
      }
    } catch {}
  }, [lang]);

  const toggle = () => setLang((l) => (l === "id" ? "en" : "id"));
  const t: Dict = dict[lang];
  return { lang, setLang, toggle, t };
}
