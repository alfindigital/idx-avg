export type CalcMode = "new-avg" | "lots-needed";

export type FeeOptions = {
  enabled: boolean;
  buyPct: number; // %
  sellPct: number; // %
};

export type CalcResult = {
  id: string;
  timestamp: number;
  mode: CalcMode;
  avgSekarang: number;
  lotSekarang: number;
  hargaAveraging: number;
  newAvgPrice: number;
  totalLotBaru: number;
  lotDelta: number;
  modalAwal: number;
  modalTambahan: number;
  totalModal: number;
  status: "down" | "up" | "flat";
  percentage: number;
  targetAvg?: number;
  // Fees (only set when fee.enabled)
  feeEnabled?: boolean;
  buyPct?: number;
  sellPct?: number;
  feeBeli?: number;
  feeJualEst?: number;
  breakEvenPrice?: number;
};

function computeFees(
  avgBaru: number,
  totalLotBaru: number,
  hargaAveraging: number,
  lotDelta: number,
  fee?: FeeOptions
): Partial<CalcResult> {
  if (!fee || !fee.enabled) return {};
  const buy = fee.buyPct / 100;
  const sell = fee.sellPct / 100;
  const feeBeli = hargaAveraging * lotDelta * 100 * buy;
  // Estimate sell fee if everything sold at new avg
  const feeJualEst = avgBaru * totalLotBaru * 100 * sell;
  const breakEvenPrice = (1 - sell) > 0 ? (avgBaru * (1 + buy)) / (1 - sell) : avgBaru;
  return {
    feeEnabled: true,
    buyPct: fee.buyPct,
    sellPct: fee.sellPct,
    feeBeli,
    feeJualEst,
    breakEvenPrice,
  };
}

export function calcNewAvg(args: {
  avgSekarang: number;
  lotSekarang: number;
  hargaAveraging: number;
  lotTambah: number;
  fee?: FeeOptions;
}): CalcResult {
  const { avgSekarang, lotSekarang, hargaAveraging, lotTambah, fee } = args;
  const totalLotBaru = lotSekarang + lotTambah;
  const newAvg =
    (avgSekarang * lotSekarang + hargaAveraging * lotTambah) / totalLotBaru;
  const modalAwal = avgSekarang * lotSekarang * 100;
  const modalTambahan = hargaAveraging * lotTambah * 100;
  const status: CalcResult["status"] =
    hargaAveraging < avgSekarang ? "down" : hargaAveraging > avgSekarang ? "up" : "flat";
  const percentage = Math.abs(((newAvg - avgSekarang) / avgSekarang) * 100);
  const fees = computeFees(newAvg, totalLotBaru, hargaAveraging, lotTambah, fee);
  const totalModal = modalAwal + modalTambahan + (fees.feeBeli ?? 0);
  return {
    id: crypto.randomUUID(),
    timestamp: Date.now(),
    mode: "new-avg",
    avgSekarang,
    lotSekarang,
    hargaAveraging,
    newAvgPrice: newAvg,
    totalLotBaru,
    lotDelta: lotTambah,
    modalAwal,
    modalTambahan,
    totalModal,
    status,
    percentage,
    ...fees,
  };
}

export function calcLotsNeeded(args: {
  avgSekarang: number;
  lotSekarang: number;
  hargaAveraging: number;
  targetAvg: number;
  fee?: FeeOptions;
}): { result: CalcResult } | { error: string } {
  const { avgSekarang, lotSekarang, hargaAveraging, targetAvg, fee } = args;
  if (hargaAveraging === targetAvg)
    return { error: "Target tidak boleh sama dengan harga averaging" };
  const lotDibutuhkan = Math.round(
    (targetAvg * lotSekarang - avgSekarang * lotSekarang) /
      (hargaAveraging - targetAvg)
  );
  if (lotDibutuhkan < 0)
    return { error: "Tidak bisa mencapai target dengan harga ini" };
  const totalLotBaru = lotSekarang + lotDibutuhkan;
  const newAvg =
    totalLotBaru === 0
      ? avgSekarang
      : (avgSekarang * lotSekarang + hargaAveraging * lotDibutuhkan) / totalLotBaru;
  const modalAwal = avgSekarang * lotSekarang * 100;
  const modalTambahan = hargaAveraging * lotDibutuhkan * 100;
  const status: CalcResult["status"] =
    hargaAveraging < avgSekarang ? "down" : hargaAveraging > avgSekarang ? "up" : "flat";
  const percentage = Math.abs(((newAvg - avgSekarang) / avgSekarang) * 100);
  const fees = computeFees(newAvg, totalLotBaru, hargaAveraging, lotDibutuhkan, fee);
  const totalModal = modalAwal + modalTambahan + (fees.feeBeli ?? 0);
  return {
    result: {
      id: crypto.randomUUID(),
      timestamp: Date.now(),
      mode: "lots-needed",
      avgSekarang,
      lotSekarang,
      hargaAveraging,
      newAvgPrice: newAvg,
      totalLotBaru,
      lotDelta: lotDibutuhkan,
      modalAwal,
      modalTambahan,
      totalModal,
      status,
      percentage,
      targetAvg,
      ...fees,
    },
  };
}
