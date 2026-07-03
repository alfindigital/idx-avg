import { createFileRoute } from "@tanstack/react-router";
import { ImageResponse } from "workers-og";

function fmtRp(n: number) {
  if (!isFinite(n)) return "-";
  return "Rp " + Math.round(n).toLocaleString("id-ID");
}

function parseNum(v: string | null): number | null {
  if (!v) return null;
  const n = Number(v);
  return isFinite(n) && n > 0 ? n : null;
}

export const Route = createFileRoute("/api/og")({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const url = new URL(request.url);
        const q = url.searchParams;

        const avg = parseNum(q.get("avg"));
        const lot = parseNum(q.get("lot"));
        const harga = parseNum(q.get("harga"));
        const lotTambah = parseNum(q.get("lotTambah"));
        const target = parseNum(q.get("target"));
        const ticker = (q.get("t") || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8);

        // Compute new avg (client-friendly, minimal recompute).
        let newAvg: number | null = null;
        let lotDelta: number | null = null;
        let totalLot: number | null = null;
        if (avg && lot && harga && lotTambah) {
          newAvg = (avg * lot + harga * lotTambah) / (lot + lotTambah);
          lotDelta = lotTambah;
          totalLot = lot + lotTambah;
        } else if (avg && lot && harga && target) {
          const need = ((avg - target) * lot) / (target - harga);
          if (isFinite(need) && need > 0) {
            lotDelta = Math.ceil(need);
            totalLot = lot + lotDelta;
            newAvg = (avg * lot + harga * lotDelta) / totalLot;
          }
        }

        const hasResult = newAvg !== null && lotDelta !== null;
        const pct = hasResult && avg ? ((newAvg! - avg) / avg) * 100 : 0;
        const status = pct < -0.001 ? "down" : pct > 0.001 ? "up" : "flat";
        const statusColor = status === "down" ? "#22c55e" : status === "up" ? "#ef4444" : "#94a3b8";
        const arrow = status === "down" ? "↓" : status === "up" ? "↑" : "→";

        const html = `
<div style="display:flex;flex-direction:column;width:100%;height:100%;background:linear-gradient(135deg,#0b1220 0%,#0f172a 55%,#1e293b 100%);color:#f8fafc;font-family:sans-serif;padding:64px;position:relative;">
  <div style="display:flex;align-items:center;gap:16px;">
    <div style="display:flex;width:64px;height:64px;background:#3b82f6;border-radius:16px;align-items:center;justify-content:center;font-size:36px;font-weight:800;color:#fff;">A</div>
    <div style="display:flex;flex-direction:column;">
      <div style="font-size:32px;font-weight:800;letter-spacing:-1px;">IDXAvg</div>
      <div style="font-size:18px;color:#94a3b8;margin-top:2px;">Kalkulator Averaging Saham IDX</div>
    </div>
    ${ticker ? `<div style="display:flex;margin-left:auto;padding:10px 20px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);border-radius:12px;font-size:26px;font-weight:700;color:#93c5fd;">${ticker}</div>` : ""}
  </div>

  ${
    hasResult
      ? `
  <div style="display:flex;flex-direction:column;margin-top:56px;">
    <div style="font-size:22px;color:#94a3b8;">Average baru</div>
    <div style="display:flex;align-items:baseline;gap:20px;margin-top:8px;">
      <div style="font-size:96px;font-weight:800;letter-spacing:-3px;color:#f8fafc;">${fmtRp(newAvg!)}</div>
      <div style="font-size:36px;font-weight:700;color:${statusColor};">${arrow} ${Math.abs(pct).toFixed(2)}%</div>
    </div>
  </div>

  <div style="display:flex;gap:24px;margin-top:auto;">
    <div style="display:flex;flex-direction:column;flex:1;padding:20px 24px;background:rgba(255,255,255,0.04);border-left:3px solid #3b82f6;border-radius:12px;">
      <div style="font-size:18px;color:#94a3b8;">Avg lama</div>
      <div style="font-size:32px;font-weight:700;margin-top:4px;">${fmtRp(avg!)}</div>
    </div>
    <div style="display:flex;flex-direction:column;flex:1;padding:20px 24px;background:rgba(255,255,255,0.04);border-left:3px solid #3b82f6;border-radius:12px;">
      <div style="font-size:18px;color:#94a3b8;">Harga beli</div>
      <div style="font-size:32px;font-weight:700;margin-top:4px;">${fmtRp(harga!)}</div>
    </div>
    <div style="display:flex;flex-direction:column;flex:1;padding:20px 24px;background:rgba(255,255,255,0.04);border-left:3px solid #3b82f6;border-radius:12px;">
      <div style="font-size:18px;color:#94a3b8;">+Lot / Total</div>
      <div style="font-size:32px;font-weight:700;margin-top:4px;">+${lotDelta} / ${totalLot}</div>
    </div>
  </div>
  `
      : `
  <div style="display:flex;flex-direction:column;margin-top:auto;margin-bottom:auto;">
    <div style="font-size:80px;font-weight:800;letter-spacing:-2px;line-height:1.05;">Hitung average<br/>saham IDX<br/><span style="color:#3b82f6;">dalam detik.</span></div>
    <div style="font-size:26px;color:#94a3b8;margin-top:24px;">Auto tick-size • Fee-aware • Gratis • PWA</div>
  </div>
  `
  }

  <div style="display:flex;margin-top:32px;font-size:20px;color:#64748b;">idx-avg.lovable.app</div>
</div>`;

        return new ImageResponse(html, {
          width: 1200,
          height: 630,
          format: "png",
          headers: {
            "cache-control": "public, max-age=3600, s-maxage=86400, immutable",
          },
        });
      },
    },
  },
});
