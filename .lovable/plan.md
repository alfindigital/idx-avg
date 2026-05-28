# Rencana perubahan kalkulator

## 1. Hapus input "Kode Saham" & "Tanggal"
- Buang dua field (label + input) dari form di `src/components/calculator.tsx`.
- Buang state `stockName` & `date`, hapus dari validasi, payload simpan/restore `INPUTS_KEY`, hasil kalkulasi (`CalcResult` di `src/lib/calc.ts`), riwayat, export gambar, share text, dan `loadFromHistory`.
- Header hasil cukup menampilkan tanggal otomatis (timestamp saat hitung) tanpa kode saham.

## 2. Accordion "Fee Beli/Jual" (default tertutup, default tercentang)
- Pakai `Accordion` shadcn (single, collapsible, default value kosong) di atas tombol Hitung.
- Konten: checkbox "Sertakan fee" (default ON), 2 input persen: Fee Beli (default `0.15`), Fee Jual (default `0.25`), suffix `%`.
- Simpan ke localStorage key `idxavg-fee-v1`: `{ enabled, buyPct, sellPct }`. Restore saat mount.
- Logika perhitungan (di `src/lib/calc.ts`): bila aktif, tambahkan `modalTambahan_with_fee = hargaAveraging * lotTambah * 100 * (1 + buyPct/100)`. Tambah field hasil `feeBeli`, `feeJual` (estimasi bila dijual di avg baru), `breakEvenPrice = newAvg * (1 + buyPct/100) / (1 - sellPct/100)`.
- Tampilkan baris baru di kartu hasil: "Fee Beli", "Estimasi Fee Jual", "Harga Break Even" (hanya jika fee aktif).

## 3. Validasi tick size IDX (verifikasi aturan terbaru)
- Aturan IDX (efektif sejak revisi):
  - `< 200` → tick 1, max 10
  - `200 – <500` → tick 2, max 20
  - `500 – <2000` → tick 5, max 50
  - `2000 – <5000` → tick 10, max 100
  - `≥ 5000` → tick 25, max 250
- `src/lib/idx-tick.ts` sudah sesuai untuk tick — tidak diubah.
- Perketat `validatePrice`: bila harga tidak kelipatan tick, tampilkan error "Tidak sesuai fraksi IDX (tick Rp X). Saran: Rp Y" alih-alih hanya auto-round saat blur. Tetap sediakan tombol kecil "Bulatkan" / auto-snap saat blur (perilaku saat ini dipertahankan).
- Tambah catatan tooltip kecil "Mengikuti fraksi harga IDX" di sebelah label Avg Sekarang / Harga Averaging / Target.

## 4. PWA Installable (manifest-only, tanpa service worker)
- Buat `public/manifest.webmanifest` dengan `name`, `short_name: "IDXAvg"`, `start_url: "/"`, `display: "standalone"`, `theme_color`, `background_color`, dan ikon 192/512 (gunakan `public/favicon.ico` placeholder; tambah `public/icon-192.png` & `icon-512.png` — generate via imagegen ikon Σ sesuai branding).
- Tambah `<link rel="manifest" href="/manifest.webmanifest">` + `theme-color` + apple-touch-icon di `head()` `src/routes/__root.tsx`.
- TIDAK menambah service worker (sesuai aturan PWA — preview iframe akan rusak).
- Beritahu user: install prompt hanya muncul di domain published, bukan di editor preview.

## 5. Toggle bahasa ID/EN
- Tambah konteks bahasa ringan (tanpa lib i18n): `src/lib/i18n.ts` export `dict = { id: {...}, en: {...} }` + hook `useLang()` yang baca/tulis `idxavg-lang` di localStorage (default `id`, fallback `navigator.language`).
- Tombol toggle di header (di samping ikon Theme/History): button kecil menampilkan `ID` / `EN`, klik untuk toggle.
- Ganti string hardcoded di `calculator.tsx` (label, placeholder, tombol, toast, tooltip, footer, dialog awal, riwayat, hasil) menggunakan `t("key")`.
- `<html lang>` di `__root.tsx` tetap `en` (static SSR); dokumen runtime bisa di-set via efek `document.documentElement.lang = lang`.

## Detail teknis singkat

- File diedit: `src/components/calculator.tsx`, `src/lib/calc.ts`, `src/lib/idx-tick.ts` (tetap, hanya verifikasi), `src/routes/__root.tsx`.
- File baru: `src/lib/i18n.ts`, `public/manifest.webmanifest`, `public/icon-192.png`, `public/icon-512.png`.
- Tidak ada perubahan backend / dependency baru.
- Build dicek dengan `bun run build` setelah selesai.

Setujui untuk saya mulai implementasi?
