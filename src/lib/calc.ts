export type CalcMode = "new-avg" | "lots-needed";

export type CalcResult = {
  id: string;
  timestamp: number;
  mode: CalcMode;
  stockName: string;
  date: string;
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
};

export function calcNewAvg(args: {
  avgSekarang: number;
  lotSekarang: number;
  hargaAveraging: number;
  lotTambah: number;
  stockName: string;
  date: string;
}): CalcResult {
  const { avgSekarang, lotSekarang, hargaAveraging, lotTambah, stockName, date } = args;
  const totalLotBaru = lotSekarang + lotTambah;
  const newAvg =
    (avgSekarang * lotSekarang + hargaAveraging * lotTambah) / totalLotBaru;
  const modalAwal = avgSekarang * lotSekarang * 100;
  const modalTambahan = hargaAveraging * lotTambah * 100;
  const status: CalcResult["status"] =
    hargaAveraging < avgSekarang ? "down" : hargaAveraging > avgSekarang ? "up" : "flat";
  const percentage = Math.abs(((newAvg - avgSekarang) / avgSekarang) * 100);
  return {
    id: crypto.randomUUID(),
    timestamp: Date.now(),
    mode: "new-avg",
    stockName,
    date,
    avgSekarang,
    lotSekarang,
    hargaAveraging,
    newAvgPrice: newAvg,
    totalLotBaru,
    lotDelta: lotTambah,
    modalAwal,
    modalTambahan,
    totalModal: modalAwal + modalTambahan,
    status,
    percentage,
  };
}

export function calcLotsNeeded(args: {
  avgSekarang: number;
  lotSekarang: number;
  hargaAveraging: number;
  targetAvg: number;
  stockName: string;
  date: string;
}): { result: CalcResult } | { error: string } {
  const { avgSekarang, lotSekarang, hargaAveraging, targetAvg, stockName, date } = args;
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
  return {
    result: {
      id: crypto.randomUUID(),
      timestamp: Date.now(),
      mode: "lots-needed",
      stockName,
      date,
      avgSekarang,
      lotSekarang,
      hargaAveraging,
      newAvgPrice: newAvg,
      totalLotBaru,
      lotDelta: lotDibutuhkan,
      modalAwal,
      modalTambahan,
      totalModal: modalAwal + modalTambahan,
      status,
      percentage,
      targetAvg,
    },
  };
}
