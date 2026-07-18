import { FormEvent, useEffect, useState } from "react";
import { Bookmark, Check, Highlighter, MessageSquarePlus, Pencil, X } from "lucide-react";
import { ResultSegment } from "../api/client";
import { formatTime } from "../utils/format";

export function HighlightedText({ text, query }: { text: string; query: string }) {
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

type Props = {
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
  onEditText: (text: string) => void;
  onRenameSpeaker: (name: string) => void;
};

export function TranscriptSegment({
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
  onEditText,
  onRenameSpeaker,
}: Props) {
  const [isEditingText, setIsEditingText] = useState(false);
  const [textDraft, setTextDraft] = useState(segment.text);
  const [isEditingSpeaker, setIsEditingSpeaker] = useState(false);
  const [speakerDraft, setSpeakerDraft] = useState(label);

  useEffect(() => setTextDraft(segment.text), [segment.text]);
  useEffect(() => setSpeakerDraft(label), [label]);

  const saveText = () => {
    const text = textDraft.trim();
    if (!text) return;
    onEditText(text);
    setIsEditingText(false);
  };

  const saveSpeaker = (event: FormEvent) => {
    event.preventDefault();
    const name = speakerDraft.trim();
    if (!name) return;
    onRenameSpeaker(name);
    setIsEditingSpeaker(false);
  };

  return (
    <article className={`transcript-segment ${isHighlighted ? "is-highlighted" : ""}`}>
      <div className={`speaker-avatar ${tone}`}>{label.slice(-1)}</div>
      <div className="segment-body">
        <div className="segment-meta">
          {isEditingSpeaker ? (
            <form className="speaker-inline-editor" onSubmit={saveSpeaker}>
              <input value={speakerDraft} onChange={(event) => setSpeakerDraft(event.target.value)} autoFocus maxLength={100} />
              <button type="submit" aria-label="참석자 이름 저장"><Check size={13} /></button>
              <button type="button" onClick={() => setIsEditingSpeaker(false)} aria-label="참석자 이름 편집 취소"><X size={13} /></button>
            </form>
          ) : (
            <button className="speaker-name-button" type="button" onClick={() => setIsEditingSpeaker(true)}>
              <strong>{label}</strong>
              <Pencil size={11} />
            </button>
          )}
          <button type="button" onClick={onSeek}>{formatTime(segment.start)}</button>
        </div>
        {isEditingText ? (
          <div className="segment-text-editor">
            <textarea value={textDraft} onChange={(event) => setTextDraft(event.target.value)} autoFocus />
            <div>
              <button type="button" onClick={saveText} disabled={!textDraft.trim()}><Check size={14} /> 저장</button>
              <button type="button" onClick={() => { setTextDraft(segment.text); setIsEditingText(false); }}><X size={14} /> 취소</button>
            </div>
          </div>
        ) : (
          <p><HighlightedText text={segment.text} query={query} /></p>
        )}
      </div>
      <div className="segment-actions">
        <button type="button" onClick={() => setIsEditingText(true)} aria-label="발화문 편집"><Pencil size={16} /></button>
        <button type="button" className={isBookmarked ? "is-active" : ""} onClick={onBookmark} aria-label="북마크"><Bookmark size={16} fill={isBookmarked ? "currentColor" : "none"} /></button>
        <button type="button" className={isHighlighted ? "is-active" : ""} onClick={onHighlight} aria-label="하이라이트"><Highlighter size={16} /></button>
        <button type="button" onClick={onMemo} aria-label="메모 추가"><MessageSquarePlus size={16} /></button>
      </div>
    </article>
  );
}
