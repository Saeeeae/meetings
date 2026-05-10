import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { AnalysisResult, fetchJob, fetchResult, JobStatus as JobStatusType, uploadRecording } from "../api/client";
import { FileUpload } from "../components/FileUpload";
import { JobStatus } from "../components/JobStatus";
import { ResultPage } from "./ResultPage";

export function HomePage() {
  const [job, setJob] = useState<JobStatusType | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    setError(null);
    setResult(null);
    try {
      const uploaded = await uploadRecording(file);
      const currentJob = await fetchJob(uploaded.job_id);
      setJob(currentJob);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "업로드에 실패했습니다.");
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const nextJob = await fetchJob(job.job_id);
        setJob(nextJob);
        if (nextJob.status === "completed") {
          const nextResult = await fetchResult(nextJob.job_id);
          setResult(nextResult);
        }
      } catch (pollError) {
        setError(pollError instanceof Error ? pollError.message : "상태 조회에 실패했습니다.");
      }
    }, 2000);

    return () => window.clearInterval(timer);
  }, [job]);

  useEffect(() => {
    if (!job || job.status !== "completed" || result) {
      return;
    }
    fetchResult(job.job_id)
      .then(setResult)
      .catch((resultError) => setError(resultError instanceof Error ? resultError.message : "결과 조회에 실패했습니다."));
  }, [job, result]);

  return (
    <main className="app-shell">
      <div className="app-grid">
        <div className="left-stack">
          <FileUpload disabled={isUploading} onUpload={handleUpload} />
          {error ? (
            <div className="error-banner" role="alert">
              <AlertCircle size={18} aria-hidden="true" />
              {error}
            </div>
          ) : null}
        </div>

        <div className="right-stack">
          {job ? <JobStatus job={job} /> : <div className="empty-panel">업로드 후 분석 상태가 표시됩니다.</div>}
          {result ? <ResultPage result={result} /> : null}
        </div>
      </div>
    </main>
  );
}
