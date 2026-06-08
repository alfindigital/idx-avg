import { createFileRoute } from "@tanstack/react-router";
import { Calculator } from "@/components/calculator";

export const Route = createFileRoute("/buat")({
  component: BuatPage,
  head: () => ({
    meta: [
      { title: "Hitung Average Saham — IDXAvg" },
      {
        name: "description",
        content:
          "Buka langsung kalkulator average saham IDX. Hitung average down, lot tambahan, dan break-even dengan auto tick-size.",
      },
      {
        property: "og:title",
        content: "Hitung Average Saham — IDXAvg",
      },
      {
        property: "og:description",
        content:
          "Buka langsung kalkulator average saham IDX. Hitung average down, lot tambahan, dan break-even dengan auto tick-size.",
      },
      { property: "og:url", content: "https://idx-avg.lovable.app/buat" },
      { property: "og:type", content: "website" },
    ],
    // Canonical points to "/" so the duplicate /buat shortcut entry doesn't fragment SEO.
    links: [{ rel: "canonical", href: "https://idx-avg.lovable.app/" }],
  }),
});

function BuatPage() {
  return <Calculator />;
}
