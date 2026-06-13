
# Plan: Konsistenkan Tampilan Mobile ↔ Desktop

## Temuan Audit (root cause)

Layout dibatasi `max-w-[480px]` di semua viewport, jadi kolom utama lebarnya sama persis di mobile dan desktop. Tapi di **hampir setiap elemen** ada override `sm:` (≥640px) yang mengubah padding, radius, ukuran font, jarak, dan bahkan alignment — sehingga UI yang sama terlihat sangat berbeda hanya karena lebar layar > 640px.

Akar masalah: pendekatan "mobile-first scaling" diterapkan padahal kontainer tidak ikut membesar. Hasilnya desktop jadi "versi gemuk" dari mobile, bukan layout yang sama.

### Daftar inkonsistensi yang ditemukan (file: `src/components/calculator.tsx`)

| # | Elemen | Mobile | Desktop (`sm:`) | Dampak |
|---|---|---|---|---|
| 1 | Header padding | `pt-1 pb-3` | `pt-2 pb-1` | Ritme vertikal kebalik |
| 2 | Header icon | `h-10 w-10` | `h-11 w-11` | Sedikit beda |
| 3 | App title | `text-xl` | `text-2xl` | Lompatan ukuran |
| 4 | Tagline | `text-[11px]` | `text-xs` | Beda halus |
| 5 | Form gap | `space-y-2` | `space-y-5` | Sangat beda |
| 6 | Card (`cardCls`) padding | `p-2.5` | `p-5` | 2x lebih lega |
| 7 | Card radius | `rounded-2xl` | `rounded-3xl` | Beda lengkungan |
| 8 | Section heading | `text-[11px] mb-2` | `text-xs mb-4` | Beda |
| 9 | Input (`inputCls`) | `px-3 py-1.5 text-sm` | `px-4 py-2.5 text-lg` | Lompatan besar font + tinggi |
| 10 | Label | `text-[11px] mb-0.5` | `text-sm mb-1` | Lompatan besar |
| 11 | "Modal Awal" row | `px-3 py-1.5 rounded-xl text-xs/text-sm` | `px-4 py-3 rounded-2xl text-sm/text-lg` | Beda total |
| 12 | Averaging inner stack | `space-y-1.5` | `space-y-3` | Beda |
| 13 | Grid gap input | `gap-2` | `gap-3` | Beda |
| 14 | Fee accordion padding | `py-3` | `py-4` | Beda |
| 15 | Tombol Hitung | `py-2.5 text-sm rounded-2xl` | `py-5 text-lg rounded-3xl` | Tombol jauh lebih besar di desktop |
| 16 | Main padding | `pt-4 pb-[calc(4.5rem+safe)]` | `pt-4 pb-4` | Bottom sangat beda (tapi safe-area memang khusus mobile, OK) |
| 17 | Hasil — header card | `px-4 pt-4 pb-3` | `px-5 pt-5 pb-4` | Beda |
| 18 | Hasil — value besar | `text-3xl` | `text-4xl` | Beda |
| 19 | Hasil — body padding | `px-4 py-3 space-y-2` | `px-5 py-4 space-y-2.5` | Beda |
| 20 | Footer | `mt-auto py-2 justify-end` | `mt-8 py-4 justify-center` | **Alignment berbeda** (end vs center) |

## Strategi unifikasi (rekomendasi)

**Pilih satu skala visual untuk semua viewport.** Karena kontainer dikunci 480px, tidak ada alasan teknis untuk membesarkan padding/font di desktop. Pendekatan yang saya rekomendasikan:

- **Adopsi skala "desktop-ish menengah" sebagai single source**, sedikit lebih lega daripada mobile saat ini tapi tidak segemuk desktop sekarang. Alasan: mobile saat ini agak terlalu padat (input `py-1.5 text-sm` kecil untuk jempol), desktop saat ini terlalu lega (input `text-lg` kebesaran untuk angka).
- Hapus semua override `sm:` untuk properti visual (padding, gap, radius, font-size, margin).
- **Tetap pertahankan** beberapa override yang memang fungsional, bukan kosmetik:
  - `pb-[calc(4.5rem+env(safe-area-inset-bottom))]` di `<main>` untuk iOS notch — tetap mobile-only.
  - (tidak ada yang lain — semuanya kosmetik)

### Token final yang akan dipakai (single value, tanpa `sm:`)

```
form gap:       space-y-3
card padding:   p-4
card radius:    rounded-2xl
section head:   text-xs mb-3
label:          text-xs mb-1
input:          h-11 px-3.5 text-base (rounded-xl)
modal-awal row: px-4 py-2.5 rounded-xl text-sm / value text-base
inner stack:    space-y-3
grid gap:       gap-3
fee accordion:  py-3.5
tombol Hitung:  h-12 text-base rounded-2xl
result head:    px-4 pt-4 pb-3 / value text-3xl
result body:    px-4 py-4 space-y-2.5
footer:         py-3 justify-center  (samakan alignment di semua ukuran)
header:         pt-2 pb-3 (konsisten), icon h-10 w-10, title text-xl, tagline text-[11px]
```

## Implementasi (saat disetujui — build mode)

1. Edit `src/components/calculator.tsx`:
   - Update konstanta `inputCls`, `labelCls`, `sectionHead`, `cardCls` → buang semua `sm:`-variant.
   - Bersihkan `sm:`-variant kosmetik di header, main, form, setiap `<section>`, fee accordion, tombol Hitung, kartu hasil, footer.
   - Ganti footer `justify-end sm:justify-center` → `justify-center` saja.
   - Pertahankan `pb-[calc(4.5rem+env(safe-area-inset-bottom))]` di main (tidak menambah `sm:pb-4` lagi — padding bottom seragam dengan safe-area = 0 di desktop, hasilnya identik).
2. Tidak menyentuh: logika kalkulasi (`src/lib/calc.ts`), tick (`src/lib/idx-tick.ts`), i18n, PWA, error boundary, route metadata, `__root.tsx` (sudah konsisten).
3. **Verify**:
   - `bun run build` harus sukses.
   - Screenshot preview di 3 viewport: 360×800 (mobile kecil), 414×896 (mobile besar), 1280×720 (desktop). Bandingkan: header, card posisi, card averaging, tombol Hitung, kartu hasil, footer. Semua harus identik kecuali tinggi viewport.
   - Pastikan tidak ada horizontal scroll di 320px (test viewport `320×568`).
   - Cek Lighthouse tap-target tidak regress (input `h-11` = 44px, memenuhi minimum).

## Yang TIDAK diubah

- Logika bisnis, validasi, fee, i18n, history, PWA, share link, save image.
- Struktur DOM dan jumlah section.
- Warna, tema dark/light, ikon, font.
- Max width 480px (memang sengaja agar fokus seperti app mobile).

## Risiko & catatan

- Setelah unifikasi, tampilan **mobile akan sedikit lebih lega** (input dari 32px → 44px tinggi), dan tampilan **desktop akan terlihat lebih ringkas** (tidak lagi "kembung"). Ini efek yang diinginkan dari konsistensi.
- Bila Anda lebih suka mempertahankan tampilan mobile saat ini yang super-compact (`text-sm`, `py-1.5`), beri tahu — saya akan unifikasi ke arah skala compact mobile sebagai gantinya (semua viewport akan kelihatan compact).

Setujui untuk implementasi, atau pilih skala lain (compact / current-desktop / menengah-rekomendasi)?
