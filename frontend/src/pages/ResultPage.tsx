import { AnalysisResult } from "../api/client";
import { ResultViewer } from "../components/ResultViewer";

type Props = {
  result: AnalysisResult;
};

export function ResultPage({ result }: Props) {
  return <ResultViewer result={result} />;
}
