import { AlertCircle, CheckCircle2, FileAudio2, LoaderCircle, Mic2, Plus, Search, X } from "lucide-react";
import { JobStatus } from "../api/client";

type Props = {
  jobs: JobStatus[];
  selectedJobId?: string;
  searchQuery: string;
  isOpen: boolean;
  onSearchChange: (query: string) => void;
  onSelect: (job: JobStatus) => void;
  onNewNote: () => void;
  onClose: () => void;
};

function noteTitle(filename: string) {
  return filename.replace(/\.[^/.]+$/, "") || "제목 없는 노트";
}

function formatNoteDate(value: string) {
  const date = new Date(value);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
}

function StatusIcon({ status }: { status: JobStatus["status"] }) {
  if (status === "completed") return <CheckCircle2 size={15} aria-label="완료" />;
  if (status === "failed") return <AlertCircle size={15} aria-label="실패" />;
  return <LoaderCircle className="spin" size={15} aria-label="처리 중" />;
}

export function NoteSidebar({
  jobs,
  selectedJobId,
  searchQuery,
  isOpen,
  onSearchChange,
  onSelect,
  onNewNote,
  onClose,
}: Props) {
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const visibleJobs = normalizedQuery
    ? jobs.filter((job) => job.filename.toLowerCase().includes(normalizedQuery))
    : jobs;

  return (
    <aside className={`notes-sidebar ${isOpen ? "is-open" : ""}`} aria-label="음성 노트 목록">
      <div className="sidebar-brand">
        <div className="brand-mark" aria-hidden="true">
          <Mic2 size={20} />
        </div>
        <div>
          <strong>VoiceNote AI</strong>
          <span>회의 기록 워크스페이스</span>
        </div>
        <button className="icon-button sidebar-close" type="button" onClick={onClose} aria-label="노트함 닫기">
          <X size={19} />
        </button>
      </div>

      <button className="new-note-button" type="button" onClick={onNewNote}>
        <Plus size={18} />
        새 음성 노트
      </button>

      <label className="sidebar-search">
        <Search size={16} aria-hidden="true" />
        <input
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="노트 검색"
          aria-label="노트 검색"
        />
      </label>

      <div className="sidebar-section-label">
        <span>내 노트</span>
        <span>{visibleJobs.length}</span>
      </div>

      <nav className="note-list">
        {visibleJobs.length > 0 ? (
          visibleJobs.map((job) => (
            <button
              type="button"
              key={job.job_id}
              className={`note-list-item ${selectedJobId === job.job_id ? "is-active" : ""}`}
              onClick={() => onSelect(job)}
            >
              <span className="note-file-icon" aria-hidden="true">
                <FileAudio2 size={17} />
              </span>
              <span className="note-list-copy">
                <strong>{noteTitle(job.filename)}</strong>
                <span>{formatNoteDate(job.created_at)}</span>
              </span>
              <span className={`note-status status-${job.status}`}>
                <StatusIcon status={job.status} />
              </span>
            </button>
          ))
        ) : (
          <div className="sidebar-empty">
            <FileAudio2 size={22} />
            <p>{searchQuery ? "검색 결과가 없습니다." : "아직 생성된 노트가 없습니다."}</p>
          </div>
        )}
      </nav>

      <div className="sidebar-footer">
        <span className="storage-dot" />
        모델과 녹음은 이 서버에 저장됩니다
      </div>
    </aside>
  );
}
