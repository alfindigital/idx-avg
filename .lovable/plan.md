## IDXAvg — Mobile-First Averaging Calculator

Single-page tool. Compact stacked layout, mobile-first. Tidak ada tab — mode kalkulasi auto-detect dari kolom yang user isi.

### Layout (mobile-first, max-w-md, desktop centered)

```
┌─────────────────────────────────┐
│ ▲ IDXAvg          ☰ menu        │  header tipis (32px)
├─────────────────────────────────┤
│ [Kode]  [Tgl]                   │  baris 1: stock + date inline
│ [Avg Sekarang]  [Lot]           │  baris 2: 2 kolom
│ Modal Awal: Rp 12.345.000   ⓘ   │  inline subtle, bukan card
├─────────────────────────────────┤
│ Averaging                       │
│ [Harga Beli]                    │  field selalu visible
│ [+ Lot]    atau  [Target Avg]   │  2 field side-by-side
│                                 │  → isi salah satu, satunya disable
│ [        H I T U N G        ]   │  full-width primary
├─────────────────────────────────┤
│ ▼ Hasil (muncul setelah hitung) │
│ ┌─ badge Down 2.3% ─────────┐   │
│ │ Avg Baru:  Rp 1.245       │   │
│ │ Lot Baru:  35 (+10)       │   │
│ │ Modal+:    Rp 1.250.000   │   │
│ │ Total:     Rp 13.595.000  │   │
│ └───────────────────────────┘   │
│ [Share] [PNG] [Reset]           │
└─────────────────────────────────┘
```

Desktop (≥md): grid 2 kolom — kiri = posisi + averaging input, kanan = hasil sticky. Tetap padat, tanpa card outline tebal.

### Mode auto-detect

- Field "Lot Tambahan" dan "Target Avg" ditampilkan berdampingan (`grid-cols-2`).
- Saat user isi salah satu, yang lain otomatis `disabled` + opacity-50.
- Saat dikosongkan, dua-duanya re-enable.
- Tombol HITUNG memanggil formula sesuai field aktif.
- Tidak ada tab/segmented switch.

### Fitur

1. **Input posisi**: stock code (uppercase auto), tanggal (default today), avg price, total lot
2. **Auto-tick rounding** on blur: aturan IDX (1/2/5/10/25). Toast subtle "Dibulatkan ke Rp X" 1.5 detik
3. **Validasi lot**: integer positif; inline error merah kecil di bawah field
4. **Modal Awal** inline (bukan card besar) — update real-time
5. **Live hasil**: hitung otomatis saat semua field valid (tetap ada tombol HITUNG untuk eksplisit + Enter shortcut)
6. **Status badge**: Down (merah)/Up (hijau) + persen perubahan
7. **History**: 20 terakhir di `localStorage`, drawer dari kanan (sheet); tap entry untuk re-load
8. **Share link**: `?stock=...&avg=...&lot=...&type=...&...` — auto-parse on mount
9. **Save as PNG**: `html2canvas` (atau native canvas) pada result card
10. **Dark mode**: toggle di menu, persist `localStorage`, tokens via CSS variables
11. **Shortcut**: Enter dimana saja = HITUNG; Tab order rapi

### Design tokens (src/styles.css)

Brand: indigo subtle (bukan biru pop seperti screenshot v0). Light = bg putih dengan sentuhan slate; dark = slate-950.

- `--primary` ≈ oklch(0.45 0.18 264) (indigo dalam, professional)
- `--success` (up) hijau emerald lembut; `--destructive` (down) merah coral lembut
- Border-radius 0.5rem, padding rapat (`p-3`/`p-4`), font Inter
- Tidak pakai card berbayang tebal — gunakan border tipis `border-border`
- Numeric font tabular: `font-variant-numeric: tabular-nums`

### Struktur file

```
src/
  routes/
    __root.tsx              (update title + meta IDXAvg)
    index.tsx               (render <Calculator />)
  components/
    calculator.tsx          (main component)
    calculator/
      header.tsx            (logo + menu dropdown: dark, history, reset, share, png)
      position-form.tsx     (stock/date/avg/lot + modal awal)
      averaging-form.tsx    (harga + lot OR target, mode auto-detect)
      result-card.tsx       (badge + 4 baris hasil + actions)
      history-sheet.tsx     (drawer 20 entries)
  lib/
    idx-tick.ts             (getTickSize, roundToTick, formatRupiah)
    calc.ts                 (calculateNewAvg, calculateLotsNeeded, types)
    history.ts              (load/save/clear localStorage)
    share.ts                (build & parse URL params)
  styles.css                (palette indigo + tokens)
```

### Dependencies

- `html2canvas` — export PNG (`bun add html2canvas`)
- `sonner` toast (sudah ada di shadcn) untuk feedback rounding/copy

### Out of scope

- Backend / auth / Lovable Cloud — semua client-side
- Multi-stock portfolio tracking
- Real-time price API

### Validation & polish

- Mobile preview viewport diset ke mobile saat selesai build
- Enter shortcut di-test di semua input
- Dark mode di-test
- URL share roundtrip di-test
