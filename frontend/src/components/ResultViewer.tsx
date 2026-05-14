import { useMemo, useRef, useState } from "react";
import { Download, FileJson, FileText, ListChecks, MessageSquareText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnalysisResult, audioUrl, downloadUrl, ResultSegment } from "../api/client";

type Props = {
  result: AnalysisResult;
};

type TabKey = "speaker" | "cleaned" | "minutes" | "summary" | "segments" | "json";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "speaker", label: "화자별 스크립트" },
  { key: "cleaned", label: "정리된 스크립트" },
  { key: "minutes", label: "회의록" },
  { key: "summary", label: "요약본" },
  { key: "segments", label: "세그먼트" },
  { key: "json", label: "JSON" },
];

const MARKDOWN_TABS: TabKey[] = ["minutes", "summary"];

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function contentForTab(result: AnalysisResult, tab: TabKey) {
  switch (tab) {
    case "speaker":
      return result.speaker_transcript;
    case "cleaned":
      return result.cleaned_transcript;
    case "minutes":
      return result.meeting_minutes;
    case "summary":
      return result.summary;
    case "segments":
      return "";
    case "json":
      return JSON.stringify(result, null, 2);
  }
}

export function ResultViewer({ result }: Props) {
  const [activeTab, setActiveTab] = useState<TabKey>("minutes");
  const [audioAvailable, setAudioAvailable] = useState(true);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const activeContent = useMemo(() => contentForTab(result, activeTab), [result, activeTab]);
  const renderAsMarkdown = MARKDOWN_TABS.includes(activeTab);

  const handleSeek = (start: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, start);
    void audio.play();
  };

  return (
    <section className="tool-panel result-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Result</p>
          <h2>분석 결과</h2>
        </div>
        <ListChecks aria-hidden="true" />
      </div>

      {audioAvailable ? (
        <audio
          ref={audioRef}
          src={audioUrl(result.job_id)}
          controls
          preload="metadata"
          className="result-audio"
          onError={() => setAudioAvailable(false)}
        />
      ) : (
        <small className="muted">오디오 미리보기를 불러올 수 없습니다 (보관 기간 만료 또는 비활성화).</small>
      )}

      <div className="download-row">
        <a className="secondary-button" href={downloadUrl(result.job_id, "minutes")}>
          <FileText size={16} aria-hidden="true" />
          회의록
        </a>
        <a className="secondary-button" href={downloadUrl(result.job_id, "summary")}>
          <MessageSquareText size={16} aria-hidden="true" />
          요약
        </a>
        <a className="secondary-button" href={downloadUrl(result.job_id, "transcript")}>
          <Download size={16} aria-hidden="true" />
          스크립트
        </a>
        <a className="secondary-button" href={downloadUrl(result.job_id, "cleaned_transcript")}>
          <Download size={16} aria-hidden="true" />
          정리본
        </a>
        <a className="secondary-button" href={downloadUrl(result.job_id, "json")}>
          <FileJson size={16} aria-hidden="true" />
          JSON
        </a>
      </div>

      <div className="tab-row" role="tablist" aria-label="결과 탭">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? "tab active" : "tab"}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "segments" ? (
        <SegmentsList segments={result.segments} onSeek={handleSeek} />
      ) : renderAsMarkdown ? (
        <div className="result-content result-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{activeContent}</ReactMarkdown>
        </div>
      ) : (
        <pre className="result-content">{activeContent}</pre>
      )}
    </section>
  );
}

function SegmentsList({ segments, onSeek }: { segments: ResultSegment[]; onSeek: (start: number) => void }) {
  if (!segments || segments.length === 0) {
    return <p className="muted">세그먼트가 없습니다.</p>;
  }
  return (
    <ul className="segment-list">
      {segments.map((segment, index) => (
        <li key={`${segment.start}-${index}`}>
          <button type="button" className="segment-row" onClick={() => onSeek(segment.start)}>
            <span className="segment-time">{formatTime(segment.start)}</span>
            <span className="segment-speaker">{segment.speaker}</span>
            <span className="segment-text">{segment.text}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
