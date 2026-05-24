## Diagnosis

Logika `calcNewAvg` di `src/lib/calc.ts` sudah benar:
`(100×100 + 150×100) / 200 = 125`.

Yang terjadi di screenshot: kartu hasil menampilkan **Lot Baru 101 (+1)** dan **Modal Tambahan Rp 15.000**. Itu artinya saat tombol HITUNG ditekan sebelumnya, `lotTambah` masih **"1"** — lalu user mengetik `00` menjadi `100`, tapi **tidak menekan HITUNG lagi**. Kartu hasil tidak invalidasi saat input berubah, jadi angka lama (`Rp 100`) tetap nempel padahal field di atas sudah berubah → terlihat seperti kalkulasi salah.

Konfirmasi cocok:
- `Modal Awal Rp 1.000.000` = 100×100×100 ✓ (lotSekarang masih 100)
- `Modal Tambahan Rp 15.000` = 150×**1**×100 ✓
- `Total Modal Rp 1.015.000` ✓
- `Lot Baru 101 (+1)` ✓

Jadi bug-nya **stale result**, bukan rumus. Tetap fatal karena menyesatkan.

## Perbaikan

### `src/components/calculator.tsx`

1. **Auto-invalidate hasil saat input berubah.**
   Tambah `useEffect` yang reset `setResult(null)` setiap kali salah satu input perhitungan berubah (`avgPrice`, `totalLot`, `hargaAvg`, `lotTambah`, `targetAvg`, `stockName`). Dengan begitu kartu hasil hilang begitu user mulai mengubah angka, dan user wajib tekan HITUNG lagi untuk melihat hasil terbaru — tidak ada lagi angka stale yang menyesatkan.

   Catatan: harus skip efek ini saat hasil baru saja di-set oleh `runCalc` (kalau tidak, efek langsung menghapusnya). Caranya: simpan snapshot input "yang dipakai untuk hasil terakhir" di `ref`, dan baru clear kalau snapshot itu beda dengan input saat ini.

2. **Tidak ada perubahan business logic** di `src/lib/calc.ts` — rumus sudah benar.

## Hasil yang diharapkan

- Begitu user mengetik di field apa pun setelah HITUNG, kartu hasil + sticky bar langsung hilang sampai HITUNG ditekan ulang.
- Skenario di screenshot: setelah user ubah `Lot Tambah` dari `1` → `100`, hasil lama (`Rp 100`) menghilang. Tekan HITUNG → muncul `Avg Baru Rp 125`, Lot Baru 200 (+100), Modal Tambahan Rp 1.500.000, Total Modal Rp 2.500.000.
