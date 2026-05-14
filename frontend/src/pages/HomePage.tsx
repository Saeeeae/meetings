import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import {
  AnalysisResult,
  fetchJob,
  fetchResult,
  jobEventsUrl,
  JobStatus as JobStatusType,
  uploadRecording,
} from "../api/client";
import { FileUpload } from "../components/FileUpload";
import { JobStatus } from "../components/JobStatus";
import { ResultPage } from "./ResultPage";

const POLL_INITIAL_MS = 2000;
const POLL_MAX_MS = 15000;
const POLL_GROWTH = 1.4;

type JobEventPayload = Partial<Pick<JobStatusType, "status" | "progress" | "current_step" | "error_message">> & {
  job_id?: string;
};

export function HomePage() {
  const [job, setJob] = useState<JobStatusType | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    setError(null);
    setResult(null);
    setJob(null);
    setUploadProgress(0);
    try {
      const uploaded = await uploadRecording(file, (pct) => setUploadProgress(pct));
      const currentJob = await fetchJob(uploaded.job_id);
      setJob(currentJob);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "업로드에 실패했습니다.");
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
    }
  };

  const jobId = job?.job_id;
  const jobStatus = job?.status;

  useEffect(() => {
    if (!jobId || jobStatus === "completed" || jobStatus === "failed") {
      return;
    }

    let cancelled = false;
    let pollTimer: number | undefined;
    let eventSource: EventSource | null = null;

    const handleTerminal = async (terminal: JobStatusType) => {
      if (terminal.status === "completed") {
        try {
          const nextResult = await fetchResult(terminal.job_id);
          if (!cancelled) setResult(nextResult);
        } catch (fetchError) {
          if (!cancelled) {
            setError(fetchError instanceof Error ? fetchError.message : "결과 조회에 실패했습니다.");
          }
        }
      }
    };

    const applyEvent = (next: JobStatusType) => {
      if (cancelled) return;
      setJob(next);
      if (next.status === "completed" || next.status === "failed") {
        void handleTerminal(next);
      }
    };

    const startPollingFallback = () => {
      let delay = POLL_INITIAL_MS;
      const tick = async () => {
        if (cancelled) return;
        try {
          const nextJob = await fetchJob(jobId);
          if (cancelled) return;
          applyEvent(nextJob);
          if (nextJob.status === "completed" || nextJob.status === "failed") return;
          delay = Math.min(POLL_MAX_MS, Math.round(delay * POLL_GROWTH));
          pollTimer = window.setTimeout(tick, delay);
        } catch (pollError) {
          if (!cancelled) {
            setError(pollError instanceof Error ? pollError.message : "상태 조회에 실패했습니다.");
          }
        }
      };
      pollTimer = window.setTimeout(tick, delay);
    };

    try {
      eventSource = new EventSource(jobEventsUrl(jobId));
      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as JobEventPayload;
          setJob((prev) => {
            const base = prev ?? ({ job_id: jobId } as JobStatusType);
            const next: JobStatusType = {
              ...base,
              ...payload,
              job_id: payload.job_id ?? base.job_id,
              updated_at: new Date().toISOString(),
            } as JobStatusType;
            if (next.status === "completed" || next.status === "failed") {
              void handleTerminal(next);
            }
            return next;
          });
        } catch {
          // ignore heartbeats and non-JSON
        }
      };
      eventSource.onerror = () => {
        eventSource?.close();
        eventSource = null;
        if (!cancelled) startPollingFallback();
      };
    } catch {
      startPollingFallback();
    }

    return () => {
      cancelled = true;
      if (pollTimer !== undefined) window.clearTimeout(pollTimer);
      eventSource?.close();
    };
  }, [jobId, jobStatus]);

  return (
    <main className="app-shell">
      <div className="app-grid">
        <div className="left-stack">
          <FileUpload disabled={isUploading} onUpload={handleUpload} />
          {isUploading && uploadProgress !== null ? (
            <div className="upload-progress" aria-label={`업로드 진행률 ${uploadProgress}%`}>
              <div className="progress-shell">
                <div className="progress-bar" style={{ width: `${uploadProgress}%` }} />
              </div>
              <small>업로드 중… {uploadProgress}%</small>
            </div>
          ) : null}
          {error ? (
            <div className="error-banner" role="alert">
              <AlertCircle size={18} aria-hidden="true" />
              {error}
            </div>
          ) : null}
        </div>

        <div className="right-stack">
          {job ? (
            <JobStatus job={job} onRetry={(next) => { setJob(next); setResult(null); setError(null); }} />
          ) : (
            <div className="empty-panel">업로드 후 분석 상태가 표시됩니다.</div>
          )}
          {result ? <ResultPage result={result} /> : null}
        </div>
      </div>
    </main>
  );
}
