import { AnalysisResult, JobStatus } from "../api/client";
import { ResultViewer } from "../components/ResultViewer";

type Props = {
  result: AnalysisResult;
  job: JobStatus;
  onResultUpdated: (result: AnalysisResult) => void;
  onDeleted: (jobId: string) => void;
};

export function ResultPage({ result, job, onResultUpdated, onDeleted }: Props) {
  return (
    <ResultViewer
      key={job.job_id}
      result={result}
      job={job}
      onResultUpdated={onResultUpdated}
      onDeleted={onDeleted}
    />
  );
}
