import { createFileRoute } from "@tanstack/react-router";
import { AraArbCalculator } from "@/components/ara-arb-calculator";

const SITE = "https://idx-avg.lovable.app";
const PAGE_URL = `${SITE}/kalkulator-ara-arb`;
const DESCRIPTION =
  "Kalkulator ARA ARB saham IDX — hitung batas Auto Rejection Atas & Bawah dari harga penutupan, otomatis sesuai fraksi harga (tick size). Gratis.";

export const Route = createFileRoute("/kalkulator-ara-arb")({
  component: AraArbPage,
  head: () => ({
    meta: [
      { title: "Kalkulator ARA ARB Saham IDX — IDXAvg" },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: "Kalkulator ARA ARB Saham IDX — IDXAvg" },
      { property: "og:description", content: DESCRIPTION },
      { property: "og:url", content: PAGE_URL },
      { property: "og:type", content: "website" },
      { property: "og:image", content: `${SITE}/og.jpg` },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:title", content: "Kalkulator ARA ARB Saham IDX — IDXAvg" },
      { name: "twitter:description", content: DESCRIPTION },
      { name: "twitter:image", content: `${SITE}/og.jpg` },
    ],
    links: [{ rel: "canonical", href: PAGE_URL }],
    scripts: [
      {
        type: "application/ld+json",
        children: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "WebApplication",
          name: "Kalkulator ARA ARB",
          applicationCategory: "FinanceApplication",
          operatingSystem: "Any",
          browserRequirements: "Requires JavaScript. Requires HTML5.",
          description:
            "Kalkulator ARA ARB saham IDX — hitung batas Auto Rejection Atas & Bawah dari harga penutupan, otomatis sesuai fraksi harga (tick size).",
          url: PAGE_URL,
          inLanguage: "id-ID",
          offers: { "@type": "Offer", price: "0", priceCurrency: "IDR" },
        }),
      },
      {
        type: "application/ld+json",
        children: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Beranda", item: `${SITE}/` },
            { "@type": "ListItem", position: 2, name: "Kalkulator ARA ARB", item: PAGE_URL },
          ],
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
              name: "Apa itu ARA dan ARB dalam saham?",
              acceptedAnswer: {
                "@type": "Answer",
                text: "ARA (Auto Rejection Atas) adalah batas kenaikan harga maksimum saham dalam satu hari perdagangan, sedangkan ARB (Auto Rejection Bawah) adalah batas penurunan maksimumnya. Order di luar rentang ini otomatis ditolak sistem perdagangan bursa.",
              },
            },
            {
              "@type": "Question",
              name: "Berapa persen ARA dan ARB saham IDX?",
              acceptedAnswer: {
                "@type": "Answer",
                text: "ARA bertingkat berdasarkan harga penutupan: Rp50–Rp200 sebesar 35%, di atas Rp200–Rp5.000 sebesar 25%, dan di atas Rp5.000 sebesar 20%. ARB berlaku 15% untuk semua rentang harga di pasar reguler.",
              },
            },
            {
              "@type": "Question",
              name: "Bagaimana cara menghitung ARA ARB?",
              acceptedAnswer: {
                "@type": "Answer",
                text: "ARA = harga penutupan × (1 + persentase ARA), ARB = harga penutupan × (1 − 15%). Hasilnya dibulatkan ke fraksi harga (tick size) IDX yang berlaku. Kalkulator ARA ARB IDXAvg menghitung ini otomatis.",
              },
            },
          ],
        }),
      },
    ],
  }),
});

function AraArbPage() {
  return <AraArbCalculator />;
}
