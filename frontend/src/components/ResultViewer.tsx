import { useMemo, useState } from "react";
import { Download, FileJson, FileText, ListChecks, MessageSquareText } from "lucide-react";
import { AnalysisResult, downloadUrl } from "../api/client";

type Props = {
  result: AnalysisResult;
};

type TabKey = "speaker" | "cleaned" | "minutes" | "summary" | "json";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "speaker", label: "화자별 스크립트" },
  { key: "cleaned", label: "정리된 스크립트" },
  { key: "minutes", label: "회의록" },
  { key: "summary", label: "요약본" },
  { key: "json", label: "JSON" },
];

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
    case "json":
      return JSON.stringify(result, null, 2);
  }
}

export function ResultViewer({ result }: Props) {
  const [activeTab, setActiveTab] = useState<TabKey>("minutes");
  const activeContent = useMemo(() => contentForTab(result, activeTab), [result, activeTab]);

  return (
    <section className="tool-panel result-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Result</p>
          <h2>분석 결과</h2>
        </div>
        <ListChecks aria-hidden="true" />
      </div>

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

      <pre className="result-content">{activeContent}</pre>
    </section>
  );
}
