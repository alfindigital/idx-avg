import { createFileRoute } from "@tanstack/react-router";
import { Calculator } from "@/components/calculator";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  return <Calculator />;
}
