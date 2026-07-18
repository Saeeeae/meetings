import { useCallback, useEffect, useState } from "react";
import { AlertCircle, FileAudio2, Menu, Plus, Sparkles, X } from "lucide-react";
import {
  AnalysisResult,
  fetchJob,
  fetchJobs,
  fetchResult,
  jobEventsUrl,
  JobStatus as JobStatusType,
  uploadRecording,
} from "../api/client";
import { FileUpload } from "../components/FileUpload";
import { JobStatus } from "../components/JobStatus";
import { NoteSidebar } from "../components/NoteSidebar";
import { ResultPage } from "./ResultPage";

const POLL_INITIAL_MS = 2000;
const POLL_MAX_MS = 15000;
const POLL_GROWTH = 1.4;

type JobEventPayload = Partial<Pick<JobStatusType, "status" | "progress" | "current_step" | "error_message">> & {
  job_id?: string;
};

export function HomePage() {
  const [jobs, setJobs] = useState<JobStatusType[]>([]);
  const [job, setJob] = useState<JobStatusType | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [noteSearch, setNoteSearch] = useState("");
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const loadJob = useCallback(async (nextJob: JobStatusType) => {
    setJob(nextJob);
    setResult(null);
    setError(null);
    setIsSidebarOpen(false);
    if (nextJob.status === "completed") {
      try {
        setResult(await fetchResult(nextJob.job_id));
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "결과 조회에 실패했습니다.");
      }
    }
  }, []);

  const refreshJobs = useCallback(async () => {
    const recentJobs = await fetchJobs();
    setJobs(recentJobs);
    return recentJobs;
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadRecent = async () => {
      try {
        const recentJobs = await refreshJobs();
        if (!cancelled && recentJobs.length > 0) {
          await loadJob(recentJobs[0]);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "노트 목록을 불러오지 못했습니다.");
        }
      }
    };
    void loadRecent();
    return () => {
      cancelled = true;
    };
  }, [loadJob, refreshJobs]);

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
      setJobs((previous) => [currentJob, ...previous.filter((item) => item.job_id !== currentJob.job_id)]);
      setIsUploadOpen(false);
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
      if (!cancelled) {
        try {
          await refreshJobs();
        } catch {
          // The selected note remains usable even if the sidebar refresh fails.
        }
      }
    };

    const applyEvent = (next: JobStatusType) => {
      if (cancelled) return;
      setJob(next);
      setJobs((previous) => previous.map((item) => (item.job_id === next.job_id ? next : item)));
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
          const updatedAt = new Date().toISOString();
          setJob((prev) => {
            const base = prev ?? ({ job_id: jobId } as JobStatusType);
            return {
              ...base,
              ...payload,
              job_id: payload.job_id ?? base.job_id,
              updated_at: updatedAt,
            } as JobStatusType;
          });
          setJobs((previous) => previous.map((item) => (
            item.job_id === (payload.job_id ?? jobId)
              ? { ...item, ...payload, updated_at: updatedAt } as JobStatusType
              : item
          )));
          if (payload.status === "completed" || payload.status === "failed") {
            void fetchJob(jobId).then(applyEvent).catch(() => undefined);
          }
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
  }, [jobId, jobStatus, refreshJobs]);

  return (
    <main className="voice-app">
      <NoteSidebar
        jobs={jobs}
        selectedJobId={job?.job_id}
        searchQuery={noteSearch}
        isOpen={isSidebarOpen}
        onSearchChange={setNoteSearch}
        onSelect={(nextJob) => void loadJob(nextJob)}
        onNewNote={() => setIsUploadOpen(true)}
        onClose={() => setIsSidebarOpen(false)}
      />
      {isSidebarOpen ? <button className="sidebar-backdrop" onClick={() => setIsSidebarOpen(false)} aria-label="노트함 닫기" /> : null}

      <section className="workspace-shell">
        <header className="workspace-topbar">
          <button className="icon-button mobile-menu" type="button" onClick={() => setIsSidebarOpen(true)} aria-label="노트함 열기">
            <Menu size={20} />
          </button>
          <div className="workspace-heading">
            <span>내 음성 노트</span>
            <strong>{job?.filename?.replace(/\.[^/.]+$/, "") ?? "새 노트를 시작해보세요"}</strong>
          </div>
          <button className="topbar-new-button" type="button" onClick={() => setIsUploadOpen(true)}>
            <Plus size={17} />
            새 노트
          </button>
        </header>

        {error ? (
          <div className="global-error" role="alert">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)} aria-label="오류 메시지 닫기">
              <X size={16} />
            </button>
          </div>
        ) : null}

        <div className="workspace-content">
          {!job ? (
            <section className="welcome-state">
              <div className="welcome-icon"><FileAudio2 size={32} /></div>
              <p className="eyebrow">VOICE WORKSPACE</p>
              <h1>대화를 기록하고, 필요한 순간을 바로 찾으세요</h1>
              <p>회의나 인터뷰 파일을 올리면 화자별 음성 기록과 AI 요약을 한 화면에서 확인할 수 있습니다.</p>
              <button className="primary-command" type="button" onClick={() => setIsUploadOpen(true)}>
                <Sparkles size={18} />
                첫 음성 노트 만들기
              </button>
            </section>
          ) : result ? (
            <ResultPage result={result} job={job} />
          ) : (
            <JobStatus job={job} onRetry={(next) => { setJob(next); setResult(null); setError(null); }} />
          )}
        </div>
      </section>

      {isUploadOpen ? (
        <div className="dialog-backdrop" role="presentation" onMouseDown={() => !isUploading && setIsUploadOpen(false)}>
          <div className="upload-dialog" role="dialog" aria-modal="true" aria-label="새 음성 노트" onMouseDown={(event) => event.stopPropagation()}>
            <button className="icon-button dialog-close" type="button" onClick={() => setIsUploadOpen(false)} disabled={isUploading} aria-label="업로드 창 닫기">
              <X size={20} />
            </button>
            <FileUpload disabled={isUploading} onUpload={handleUpload} />
            {isUploading && uploadProgress !== null ? (
              <div className="upload-progress" aria-label={`업로드 진행률 ${uploadProgress}%`}>
                <div className="progress-shell"><div className="progress-bar" style={{ width: `${uploadProgress}%` }} /></div>
                <small>파일을 안전하게 업로드하는 중입니다. {uploadProgress}%</small>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </main>
  );
}
