import { AnalysisResult, JobStatus } from "../api/client";
import { ResultViewer } from "../components/ResultViewer";

type Props = {
  result: AnalysisResult;
  job: JobStatus;
};

export function ResultPage({ result, job }: Props) {
  return <ResultViewer key={job.job_id} result={result} job={job} />;
}
