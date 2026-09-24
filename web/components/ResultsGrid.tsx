import ResultCard from "@/components/ResultCard";
import type { Moment } from "@/lib/types";

export default function ResultsGrid({
  moments,
  assetNames,
}: {
  moments: Moment[];
  assetNames: Record<string, string>;
}) {
  return (
    <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {moments.map((moment) => (
        <li key={moment.moment_id} className="h-full">
          <ResultCard moment={moment} assetName={assetNames[moment.asset_id]} />
        </li>
      ))}
    </ul>
  );
}
