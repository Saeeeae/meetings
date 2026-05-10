import { RefreshCw } from "lucide-react";
import { JobStatus as JobStatusType } from "../api/client";

type Props = {
  job: JobStatusType;
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

export function JobStatus({ job }: Props) {
  return (
    <section className="tool-panel compact-panel">
      <div className="status-header">
        <div>
          <p className="eyebrow">Job</p>
          <h2>{job.job_id}</h2>
        </div>
        {job.status !== "completed" && job.status !== "failed" ? <RefreshCw className="spin" aria-hidden="true" /> : null}
      </div>

      <div className="progress-shell" aria-label={`분석 진행률 ${job.progress}%`}>
        <div className="progress-bar" style={{ width: `${job.progress}%` }} />
      </div>

      <dl className="status-grid">
        <div>
          <dt>상태</dt>
          <dd>{job.status}</dd>
        </div>
        <div>
          <dt>단계</dt>
          <dd>{STEP_LABELS[job.current_step] ?? job.current_step}</dd>
        </div>
        <div>
          <dt>진행률</dt>
          <dd>{job.progress}%</dd>
        </div>
        <div>
          <dt>갱신</dt>
          <dd>{new Date(job.updated_at).toLocaleString()}</dd>
        </div>
      </dl>

      {job.error_message ? <p className="error-message">{job.error_message}</p> : null}
    </section>
  );
}
