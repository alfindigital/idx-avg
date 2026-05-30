import { createFileRoute } from "@tanstack/react-router";
import { Calculator } from "@/components/calculator";

export const Route = createFileRoute("/")({
  component: Index,
  head: () => ({
    meta: [
      { title: "IDXAvg — Kalkulator Averaging Saham IDX" },
      {
        name: "description",
        content:
          "Hitung average price & lot tambahan sebelum beli saham IDX. Auto tick-size, mobile-first, gratis.",
      },
      {
        property: "og:title",
        content: "IDXAvg — Kalkulator Averaging Saham IDX",
      },
      {
        property: "og:description",
        content:
          "Hitung average price & lot tambahan sebelum beli saham IDX. Auto tick-size, mobile-first, gratis.",
      },
      { property: "og:url", content: "https://idx-avg.lovable.app/" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      {
        name: "twitter:title",
        content: "IDXAvg — Kalkulator Averaging Saham IDX",
      },
      {
        name: "twitter:description",
        content:
          "Hitung average price & lot tambahan sebelum beli saham IDX. Auto tick-size, mobile-first, gratis.",
      },
    ],
    links: [
      { rel: "canonical", href: "https://idx-avg.lovable.app/" },
    ],
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
          url: "https://idx-avg.lovable.app/",
          offers: {
            "@type": "Offer",
            price: "0",
            priceCurrency: "IDR",
          },
        }),
      },
    ],
  }),
});

function Index() {
  return <Calculator />;
}
