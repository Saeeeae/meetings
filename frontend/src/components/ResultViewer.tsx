import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bookmark,
  Check,
  ChevronDown,
  Download,
  FileJson,
  FileText,
  Highlighter,
  ListFilter,
  MessageSquarePlus,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  Search,
  Sparkles,
  StickyNote,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnalysisResult, audioUrl, downloadUrl, JobStatus, ResultSegment } from "../api/client";

type Props = {
  result: AnalysisResult;
  job: JobStatus;
};

type InsightTab = "summary" | "minutes" | "memo" | "saved";

type NoteMemo = {
  id: string;
  time: number;
  text: string;
  createdAt: string;
};

const SPEAKER_TONES = ["tone-mint", "tone-coral", "tone-violet", "tone-blue", "tone-amber", "tone-rose"];

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function noteTitle(filename: string) {
  return filename.replace(/\.[^/.]+$/, "") || "제목 없는 노트";
}

function loadStored<T>(key: string, fallback: T): T {
  try {
    const value = window.localStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : fallback;
  } catch {
    return fallback;
  }
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) return <>{text}</>;
  const escaped = normalizedQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  return (
    <>
      {parts.map((part, index) =>
        part.toLowerCase() === normalizedQuery.toLowerCase() ? <mark key={`${part}-${index}`}>{part}</mark> : part,
      )}
    </>
  );
}

export function ResultViewer({ result, job }: Props) {
  const storagePrefix = `voice-note:${job.job_id}`;
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const memoInputRef = useRef<HTMLTextAreaElement | null>(null);
  const [activeTab, setActiveTab] = useState<InsightTab>("summary");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSpeaker, setSelectedSpeaker] = useState("all");
  const [bookmarks, setBookmarks] = useState<number[]>(() => loadStored(`${storagePrefix}:bookmarks`, []));
  const [highlights, setHighlights] = useState<number[]>(() => loadStored(`${storagePrefix}:highlights`, []));
  const [memos, setMemos] = useState<NoteMemo[]>(() => loadStored(`${storagePrefix}:memos`, []));
  const [memoDraft, setMemoDraft] = useState("");
  const [memoTime, setMemoTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [audioAvailable, setAudioAvailable] = useState(true);
  const [showDownloads, setShowDownloads] = useState(false);

  useEffect(() => window.localStorage.setItem(`${storagePrefix}:bookmarks`, JSON.stringify(bookmarks)), [bookmarks, storagePrefix]);
  useEffect(() => window.localStorage.setItem(`${storagePrefix}:highlights`, JSON.stringify(highlights)), [highlights, storagePrefix]);
  useEffect(() => window.localStorage.setItem(`${storagePrefix}:memos`, JSON.stringify(memos)), [memos, storagePrefix]);

  const speakers = useMemo(() => Array.from(new Set(result.segments.map((segment) => segment.speaker))), [result.segments]);
  const speakerLabels = useMemo(
    () => new Map(speakers.map((speaker, index) => [speaker, speaker === "UNKNOWN" ? "화자 미상" : /^SPEAKER_|^[A-Z]$/.test(speaker) ? `참석자 ${index + 1}` : speaker])),
    [speakers],
  );
  const speakerTone = (speaker: string) => SPEAKER_TONES[Math.max(0, speakers.indexOf(speaker)) % SPEAKER_TONES.length];
  const fallbackDuration = result.segments[result.segments.length - 1]?.end ?? 0;
  const visibleDuration = duration || fallbackDuration;

  const filteredSegments = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    return result.segments
      .map((segment, index) => ({ segment, index }))
      .filter(({ segment }) => selectedSpeaker === "all" || segment.speaker === selectedSpeaker)
      .filter(({ segment }) => {
        if (!normalizedQuery) return true;
        return segment.text.toLowerCase().includes(normalizedQuery) || (speakerLabels.get(segment.speaker) ?? "").toLowerCase().includes(normalizedQuery);
      });
  }, [result.segments, searchQuery, selectedSpeaker, speakerLabels]);

  const savedSegments = useMemo(() => {
    const indices = Array.from(new Set([...bookmarks, ...highlights])).sort((a, b) => a - b);
    return indices.map((index) => ({ index, segment: result.segments[index] })).filter((item) => item.segment);
  }, [bookmarks, highlights, result.segments]);

  const seekTo = (seconds: number, autoplay = true) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, seconds);
    setCurrentTime(audio.currentTime);
    if (autoplay) void audio.play().catch(() => setIsPlaying(false));
  };

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) void audio.play().catch(() => setIsPlaying(false));
    else audio.pause();
  };

  const skip = (seconds: number) => seekTo(Math.min(visibleDuration, Math.max(0, currentTime + seconds)), false);

  const cyclePlaybackRate = () => {
    const rates = [1, 1.25, 1.5, 2];
    const next = rates[(rates.indexOf(playbackRate) + 1) % rates.length];
    setPlaybackRate(next);
    if (audioRef.current) audioRef.current.playbackRate = next;
  };

  const toggleIndex = (values: number[], index: number, setter: (next: number[]) => void) => {
    setter(values.includes(index) ? values.filter((value) => value !== index) : [...values, index]);
  };

  const openMemoAt = (time: number) => {
    setMemoTime(time);
    setActiveTab("memo");
    window.setTimeout(() => memoInputRef.current?.focus(), 0);
  };

  const addMemo = () => {
    const text = memoDraft.trim();
    if (!text) return;
    setMemos((previous) => [
      ...previous,
      { id: `${Date.now()}`, time: memoTime, text, createdAt: new Date().toISOString() },
    ]);
    setMemoDraft("");
  };

  return (
    <section className="note-workspace">
      <header className="note-detail-header">
        <div className="note-title-block">
          <div className="note-title-row">
            <h1>{noteTitle(job.filename)}</h1>
            <span className="complete-badge"><Check size={13} /> 분석 완료</span>
          </div>
          <p>
            {new Date(job.created_at).toLocaleString("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}
            <span /> {formatTime(visibleDuration)}
            <span /> 참석자 {speakers.length || 1}명
          </p>
        </div>

        <div className="note-header-actions">
          <label className="transcript-search header-search">
            <Search size={16} />
            <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="대화 내용 검색" />
            {searchQuery ? <button type="button" onClick={() => setSearchQuery("")} aria-label="검색어 지우기"><X size={14} /></button> : null}
          </label>
          <div className="download-menu-wrap">
            <button className="secondary-command" type="button" onClick={() => setShowDownloads((value) => !value)}>
              <Download size={16} /> 내보내기 <ChevronDown size={14} />
            </button>
            {showDownloads ? (
              <div className="download-menu">
                <a href={downloadUrl(result.job_id, "transcript")}><FileText size={15} /> 음성 기록</a>
                <a href={downloadUrl(result.job_id, "minutes")}><StickyNote size={15} /> 회의록</a>
                <a href={downloadUrl(result.job_id, "summary")}><Sparkles size={15} /> AI 요약</a>
                <a href={downloadUrl(result.job_id, "json")}><FileJson size={15} /> JSON 데이터</a>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      <div className="note-detail-grid">
        <section className="transcript-pane">
          <div className="pane-heading">
            <div>
              <h2>음성 기록</h2>
              <span>{filteredSegments.length}개 구간</span>
            </div>
            <ListFilter size={18} aria-hidden="true" />
          </div>

          <div className="speaker-filters" aria-label="참석자 필터">
            <button type="button" className={selectedSpeaker === "all" ? "is-active" : ""} onClick={() => setSelectedSpeaker("all")}>전체</button>
            {speakers.map((speaker) => (
              <button key={speaker} type="button" className={selectedSpeaker === speaker ? "is-active" : ""} onClick={() => setSelectedSpeaker(speaker)}>
                <span className={`speaker-filter-dot ${speakerTone(speaker)}`} />
                {speakerLabels.get(speaker)}
              </button>
            ))}
          </div>

          <div className="transcript-list">
            {filteredSegments.length > 0 ? filteredSegments.map(({ segment, index }) => (
              <TranscriptSegment
                key={`${segment.start}-${index}`}
                segment={segment}
                label={speakerLabels.get(segment.speaker) ?? segment.speaker}
                tone={speakerTone(segment.speaker)}
                query={searchQuery}
                isBookmarked={bookmarks.includes(index)}
                isHighlighted={highlights.includes(index)}
                onSeek={() => seekTo(segment.start)}
                onBookmark={() => toggleIndex(bookmarks, index, setBookmarks)}
                onHighlight={() => toggleIndex(highlights, index, setHighlights)}
                onMemo={() => openMemoAt(segment.start)}
              />
            )) : (
              <div className="transcript-empty"><Search size={22} /><p>조건에 맞는 대화가 없습니다.</p></div>
            )}
          </div>
        </section>

        <aside className="insight-pane">
          <div className="insight-tabs" role="tablist" aria-label="노트 도구">
            <button type="button" className={activeTab === "summary" ? "is-active" : ""} onClick={() => setActiveTab("summary")}>AI 요약</button>
            <button type="button" className={activeTab === "minutes" ? "is-active" : ""} onClick={() => setActiveTab("minutes")}>회의록</button>
            <button type="button" className={activeTab === "memo" ? "is-active" : ""} onClick={() => { setMemoTime(currentTime); setActiveTab("memo"); }}>메모</button>
            <button type="button" className={activeTab === "saved" ? "is-active" : ""} onClick={() => setActiveTab("saved")}>모아보기</button>
          </div>

          <div className="insight-content">
            {activeTab === "summary" ? (
              <div className="ai-note">
                <div className="ai-note-label"><Sparkles size={16} /> AI가 정리한 핵심 내용</div>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.summary}</ReactMarkdown>
              </div>
            ) : null}
            {activeTab === "minutes" ? (
              <div className="markdown-note"><ReactMarkdown remarkPlugins={[remarkGfm]}>{result.meeting_minutes}</ReactMarkdown></div>
            ) : null}
            {activeTab === "memo" ? (
              <div className="memo-panel">
                <div className="memo-composer">
                  <button type="button" className="memo-time" onClick={() => seekTo(memoTime)}>{formatTime(memoTime)}</button>
                  <textarea ref={memoInputRef} value={memoDraft} onChange={(event) => setMemoDraft(event.target.value)} placeholder="이 시점에 대한 메모를 남겨보세요" />
                  <button className="primary-command" type="button" onClick={addMemo} disabled={!memoDraft.trim()}><MessageSquarePlus size={16} /> 메모 추가</button>
                </div>
                <div className="memo-list">
                  {memos.length > 0 ? memos.map((memo) => (
                    <div className="memo-item" key={memo.id}>
                      <button type="button" onClick={() => seekTo(memo.time)}>{formatTime(memo.time)}</button>
                      <p>{memo.text}</p>
                      <button type="button" className="memo-delete" onClick={() => setMemos((previous) => previous.filter((item) => item.id !== memo.id))} aria-label="메모 삭제"><X size={14} /></button>
                    </div>
                  )) : <p className="empty-copy">아직 작성한 메모가 없습니다.</p>}
                </div>
              </div>
            ) : null}
            {activeTab === "saved" ? (
              <div className="saved-panel">
                <div className="saved-summary">
                  <span><Bookmark size={15} /> 북마크 {bookmarks.length}</span>
                  <span><Highlighter size={15} /> 하이라이트 {highlights.length}</span>
                </div>
                {savedSegments.length > 0 ? savedSegments.map(({ segment, index }) => (
                  <button className="saved-segment" type="button" key={index} onClick={() => seekTo(segment.start)}>
                    <span>{formatTime(segment.start)}</span>
                    <strong>{speakerLabels.get(segment.speaker)}</strong>
                    <p>{segment.text}</p>
                    <span className="saved-icons">{bookmarks.includes(index) ? <Bookmark size={14} fill="currentColor" /> : null}{highlights.includes(index) ? <Highlighter size={14} /> : null}</span>
                  </button>
                )) : <p className="empty-copy">중요한 구간에 북마크나 하이라이트를 추가해보세요.</p>}
              </div>
            ) : null}
          </div>
        </aside>
      </div>

      <audio
        ref={audioRef}
        src={audioUrl(result.job_id)}
        preload="metadata"
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        onError={() => setAudioAvailable(false)}
      />

      <div className="audio-dock">
        <div className="audio-controls">
          <button type="button" className="skip-button" onClick={() => skip(-10)} aria-label="10초 뒤로"><RotateCcw size={18} /><span>10</span></button>
          <button type="button" className="play-button" onClick={togglePlay} disabled={!audioAvailable} aria-label={isPlaying ? "일시정지" : "재생"}>{isPlaying ? <Pause size={21} fill="currentColor" /> : <Play size={21} fill="currentColor" />}</button>
          <button type="button" className="skip-button" onClick={() => skip(10)} aria-label="10초 앞으로"><RotateCw size={18} /><span>10</span></button>
        </div>
        <span className="player-time">{formatTime(currentTime)}</span>
        <input
          className="player-range"
          type="range"
          min="0"
          max={Math.max(1, visibleDuration)}
          step="0.1"
          value={Math.min(currentTime, Math.max(1, visibleDuration))}
          onChange={(event) => seekTo(Number(event.target.value), false)}
          aria-label="재생 위치"
        />
        <span className="player-time">{formatTime(visibleDuration)}</span>
        <button className="rate-button" type="button" onClick={cyclePlaybackRate}>{playbackRate}x</button>
        {!audioAvailable ? <span className="audio-unavailable">오디오 만료</span> : null}
      </div>
    </section>
  );
}

function TranscriptSegment({
  segment,
  label,
  tone,
  query,
  isBookmarked,
  isHighlighted,
  onSeek,
  onBookmark,
  onHighlight,
  onMemo,
}: {
  segment: ResultSegment;
  label: string;
  tone: string;
  query: string;
  isBookmarked: boolean;
  isHighlighted: boolean;
  onSeek: () => void;
  onBookmark: () => void;
  onHighlight: () => void;
  onMemo: () => void;
}) {
  return (
    <article className={`transcript-segment ${isHighlighted ? "is-highlighted" : ""}`}>
      <div className={`speaker-avatar ${tone}`}>{label.slice(-1)}</div>
      <div className="segment-body">
        <div className="segment-meta">
          <strong>{label}</strong>
          <button type="button" onClick={onSeek}>{formatTime(segment.start)}</button>
        </div>
        <p><HighlightedText text={segment.text} query={query} /></p>
      </div>
      <div className="segment-actions">
        <button type="button" className={isBookmarked ? "is-active" : ""} onClick={onBookmark} aria-label="북마크"><Bookmark size={16} fill={isBookmarked ? "currentColor" : "none"} /></button>
        <button type="button" className={isHighlighted ? "is-active" : ""} onClick={onHighlight} aria-label="하이라이트"><Highlighter size={16} /></button>
        <button type="button" onClick={onMemo} aria-label="메모 추가"><MessageSquarePlus size={16} /></button>
      </div>
    </article>
  );
}
