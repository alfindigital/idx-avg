import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { Calculator } from "@/components/calculator";

const numish = z.union([z.string(), z.number()]).optional().catch(undefined);

const searchSchema = z.object({
  avg: numish,
  lot: numish,
  harga: numish,
  lotTambah: numish,
  target: numish,
  t: z.string().optional().catch(undefined),
}).catch({});

const SITE = "https://idx-avg.lovable.app";
const OG_IMAGE = `${SITE}/og.jpg`;

export const Route = createFileRoute("/")({
  component: Index,
  validateSearch: searchSchema,
  head: () => {
    const ogImage = OG_IMAGE;
      meta: [
        { title: "IDXAvg — Kalkulator Averaging Saham IDX" },
        {
          name: "description",
          content:
            "Hitung average price & lot tambahan sebelum beli saham IDX. Auto tick-size, mobile-first, gratis.",
        },
        { property: "og:title", content: "IDXAvg — Kalkulator Averaging Saham IDX" },
        {
          property: "og:description",
          content:
            "Hitung average price & lot tambahan sebelum beli saham IDX. Auto tick-size, mobile-first, gratis.",
        },
        { property: "og:url", content: `${SITE}/` },
        { property: "og:type", content: "website" },
        { property: "og:image", content: ogImage },
        { property: "og:image:width", content: "1200" },
        { property: "og:image:height", content: "630" },
        { name: "twitter:card", content: "summary_large_image" },
        { name: "twitter:title", content: "IDXAvg — Kalkulator Averaging Saham IDX" },
        {
          name: "twitter:description",
          content:
            "Hitung average price & lot tambahan sebelum beli saham IDX. Auto tick-size, mobile-first, gratis.",
        },
        { name: "twitter:image", content: ogImage },
      ],
      links: [{ rel: "canonical", href: `${SITE}/` }],
      scripts: [
        {
          type: "application/ld+json",
          children: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebApplication",
            name: "IDXAvg",
            applicationCategory: "FinanceApplication",
            operatingSystem: "Any",
            browserRequirements: "Requires JavaScript. Requires HTML5.",
            description:
              "Kalkulator averaging saham IDX — hitung average price & lot tambahan sebelum beli, dengan auto tick-size.",
            url: `${SITE}/`,
            inLanguage: "id-ID",
            offers: { "@type": "Offer", price: "0", priceCurrency: "IDR" },
          }),
        },
        {
          type: "application/ld+json",
          children: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            mainEntity: [
              {
                "@type": "Question",
                name: "Apa itu averaging saham?",
                acceptedAnswer: {
                  "@type": "Answer",
                  text: "Averaging saham adalah strategi membeli tambahan lot saham di harga berbeda untuk menurunkan (average down) atau menaikkan (average up) harga rata-rata pembelian. IDXAvg membantu menghitung avg baru dan lot yang dibutuhkan sebelum eksekusi.",
                },
              },
              {
                "@type": "Question",
                name: "Bagaimana cara menghitung average down saham?",
                acceptedAnswer: {
                  "@type": "Answer",
                  text: "Rumus: avg baru = (avg lama × lot lama × 100 + harga beli × lot tambah × 100) ÷ ((lot lama + lot tambah) × 100). IDXAvg melakukan ini otomatis dengan validasi tick-size IDX.",
                },
              },
              {
                "@type": "Question",
                name: "Apakah IDXAvg gratis?",
                acceptedAnswer: {
                  "@type": "Answer",
                  text: "Ya, IDXAvg 100% gratis, tanpa registrasi, dan bisa dipasang sebagai aplikasi (PWA) di HP maupun desktop.",
                },
              },
              {
                "@type": "Question",
                name: "Apa itu tick-size atau fraksi harga IDX?",
                acceptedAnswer: {
                  "@type": "Answer",
                  text: "Fraksi harga IDX adalah kelipatan minimum perubahan harga: di bawah 200 (Rp1), 200–<500 (Rp2), 500–<2000 (Rp5), 2000–<5000 (Rp10), dan 5000 ke atas (Rp25). IDXAvg memvalidasi otomatis sesuai aturan terbaru bursa.",
                },
              },
            ],
          }),
        },
      ],
    };
  },
});

function Index() {
  return <Calculator />;
}
