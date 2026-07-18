import { useState } from "react";
import { Check, Circle, LoaderCircle, RotateCw, Sparkles } from "lucide-react";
import { JobStatus as JobStatusType, retryJob } from "../api/client";

type Props = {
  job: JobStatusType;
  onRetry?: (next: JobStatusType) => void;
};

const STEP_LABELS: Record<string, string> = {
  uploaded: "업로드 완료",
  preprocessing: "오디오 전처리",
  stt: "STT 실행",
  diarization: "화자 분리",
  alignment: "화자 매칭",
  llm_startup: "vLLM 기동",
  script_cleanup: "스크립트 정리",
  minutes_generation: "회의록 생성",
  summary_generation: "요약 생성",
  completed: "완료",
  failed: "실패",
};

export function JobStatus({ job, onRetry }: Props) {
  const [retryError, setRetryError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  const handleRetry = async () => {
    setIsRetrying(true);
    setRetryError(null);
    try {
      const next = await retryJob(job.job_id);
      onRetry?.(next);
    } catch (error) {
      setRetryError(error instanceof Error ? error.message : "재처리에 실패했습니다.");
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <section className="processing-state">
      <div className="processing-orbit" aria-hidden="true"><Sparkles size={27} /></div>
      <p className="eyebrow">ANALYZING VOICE</p>
      <h1>{job.filename.replace(/\.[^/.]+$/, "")}</h1>
      <p className="processing-copy">{STEP_LABELS[job.current_step] ?? job.current_step} 단계입니다. 완료되면 음성 기록과 AI 노트가 자동으로 열립니다.</p>

      <div className="processing-progress" aria-label={`분석 진행률 ${job.progress}%`}>
        <div className="progress-shell"><div className="progress-bar" style={{ width: `${job.progress}%` }} /></div>
        <strong>{job.progress}%</strong>
      </div>

      <div className="pipeline-steps">
        {Object.entries(STEP_LABELS).slice(0, 9).map(([key, label]) => {
          const keys = Object.keys(STEP_LABELS);
          const currentIndex = keys.indexOf(job.current_step);
          const stepIndex = keys.indexOf(key);
          const completed = job.status === "completed" || stepIndex < currentIndex;
          const active = key === job.current_step && job.status !== "failed";
          return (
            <div key={key} className={`pipeline-step ${completed ? "is-complete" : ""} ${active ? "is-active" : ""}`}>
              <span>{completed ? <Check size={14} /> : active ? <LoaderCircle className="spin" size={14} /> : <Circle size={12} />}</span>
              {label}
            </div>
          );
        })}
      </div>

      {job.error_message ? <p className="error-message">{job.error_message}</p> : null}

      {job.status === "failed" ? (
        <div className="retry-row processing-retry">
          <button
            type="button"
            className="secondary-button"
            onClick={handleRetry}
            disabled={isRetrying}
          >
            <RotateCw size={14} aria-hidden="true" />
            {isRetrying ? "재처리 요청 중..." : "재처리"}
          </button>
          {retryError ? <small className="error-message">{retryError}</small> : null}
        </div>
      ) : null}
    </section>
  );
}
