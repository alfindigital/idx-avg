## Tujuan

Refresh tampilan kalkulator IDXAvg jadi modern minimalis dan mobile-responsive, dengan font lebih besar agar nyaman dibaca di desktop maupun mobile. Tidak ada perubahan business logic — semua field, validasi, history, share/export, dan keyboard shortcut tetap.

## Arah desain (terkunci)

- Palet **Cloud White**: bg `#fafbfc`, surface kartu `#e8ecf1`, muted `#94a3b8`, primary `#3b82f6`.
- Tipografi: **Urbanist** (heading/angka/tombol) + **Epilogue** (body/label) via Google Fonts.
- Layout **single-column**, max width ~480px, terpusat di desktop dan mobile.
- Komposisi mengikuti prototype terpilih: dua kartu berlapis (Posisi Saat Ini + Averaging), tombol HITUNG full-width rounded, sticky result bar gelap (`slate-900`) mengambang di bawah.

## Perubahan file

### 1. `src/styles.css`
- Tambah `@import` Google Fonts untuk Urbanist 700/800 dan Epilogue 400/500/600.
- Set `--font-sans: 'Epilogue'` dan `--font-display: 'Urbanist'` di `:root`, lalu register di `@theme inline`.
- Update `body` agar pakai Epilogue, tambah utility `.font-display` untuk Urbanist.
- Sesuaikan token `--background`, `--card`, `--muted`, `--primary` ke oklch yang setara dengan palet Cloud White (light mode), dan turunan gelap yang konsisten untuk dark mode (tetap dukung toggle theme yang sudah ada).
- Naikkan `--radius` ke `1rem` agar match rounded-3xl prototype.

### 2. `src/components/calculator.tsx` (visual saja)
- Container utama: `bg-background`, padding longgar, `max-w-[480px] mx-auto`.
- Header: logo bulat biru `rounded-xl` + judul Urbanist 2xl + subtitle muted. Tombol header tetap (theme, history, menu) tapi pakai ukuran ikon lebih besar (`h-5 w-5`).
- Section "Posisi Saat Ini" & "Averaging" jadi `<section className="bg-muted/60 border border-white/60 rounded-3xl p-5 shadow-sm">` dengan heading kecil uppercase tracking-widest Urbanist.
- Semua Input diberi class besar: `h-auto py-4 px-4 text-lg font-bold rounded-2xl bg-card border-2 border-transparent focus-visible:border-primary focus-visible:ring-0`. Label naik jadi `text-sm font-semibold`.
- "Modal Awal" callout: `rounded-2xl bg-card/50` dengan angka Urbanist `text-lg font-bold`.
- Tombol HITUNG: `w-full py-5 rounded-3xl text-xl font-extrabold tracking-wider shadow-xl shadow-primary/20` dengan label "(Enter)" kecil di samping.
- Sticky result bar (mobile + desktop): kartu mengambang `fixed bottom-4` `max-w-[440px]` `bg-slate-900 text-white rounded-3xl p-5 shadow-2xl`, dua kolom (Avg Baru / metric kedua) dengan divider vertikal, angka Urbanist 2xl. Saat belum ada result → tetap sembunyikan seperti sekarang.
- Result detail panel desktop tetap, hanya rebrand visual (rounded-3xl, font baru, padding lebih lega).
- Pesan error inline tetap di bawah input (`text-xs text-destructive`).
- Footer "made with ♥ IDXAvg" kecil muted-foreground.

### 3. Tidak diubah
- `src/lib/calc.ts`, `src/lib/idx-tick.ts`, history, share link, copy summary, export image, keyboard, validasi, tabIndex — semua logic tetap.

## Catatan teknis (untuk kontributor)

```text
styles.css
  └── @import Urbanist + Epilogue
  └── --font-sans / --font-display tokens
  └── tweak oklch values → Cloud White light mode

calculator.tsx (visual layer only)
  └── header     → logo pill + 2xl title
  └── sections   → bg-muted rounded-3xl cards
  └── inputs     → text-lg, py-4, rounded-2xl, focus ring primary
  └── HITUNG     → py-5 rounded-3xl text-xl shadow primary
  └── result bar → fixed bottom dark pill (slate-900)
```

## QA

- Cek desktop (1280+) & mobile (375) di preview — pastikan single-column, font terbaca, sticky bar tidak menutupi tombol HITUNG (padding bawah `pb-32`).
- Toggle dark mode masih kontras.
- Semua field tetap berfungsi, Enter tetap submit, error inline tampil.