import { ChangeEvent, DragEvent, useState } from "react";
import { FileAudio, UploadCloud } from "lucide-react";

type FileUploadProps = {
  disabled?: boolean;
  onUpload: (file: File) => Promise<void>;
};

export function FileUpload({ disabled = false, onUpload }: FileUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const pickFile = (file: File | undefined) => {
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleInput = (event: ChangeEvent<HTMLInputElement>) => {
    pickFile(event.target.files?.[0]);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    pickFile(event.dataTransfer.files?.[0]);
  };

  return (
    <section className="tool-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Meeting Minutes AI</p>
          <h1>회의 녹음 파일 업로드</h1>
        </div>
        <FileAudio aria-hidden="true" />
      </div>

      <label
        className={`drop-zone ${isDragging ? "is-dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".mp3,.wav,.m4a,.aac,.flac,.mp4,.webm,audio/*,video/mp4,video/webm"
          onChange={handleInput}
          disabled={disabled}
        />
        <UploadCloud aria-hidden="true" />
        <span>{selectedFile ? selectedFile.name : "파일을 끌어오거나 선택하세요"}</span>
        <small>.mp3, .wav, .m4a, .aac, .flac, .mp4, .webm</small>
      </label>

      <div className="notice-list">
        <p>회의 상대방 소리까지 분석하려면, 업로드하는 녹음 파일에 내 목소리와 상대방 목소리가 모두 포함되어 있어야 합니다.</p>
        <p>업로드 전 파일을 재생해 상대방 음성이 포함되어 있는지 확인해주세요.</p>
        <p>회의 녹음 파일은 서버로 업로드됩니다. 참가자 동의와 내부 보안 정책을 먼저 확인해주세요.</p>
      </div>

      <button
        className="primary-button"
        type="button"
        disabled={!selectedFile || disabled}
        onClick={() => selectedFile && onUpload(selectedFile)}
      >
        <UploadCloud size={18} aria-hidden="true" />
        업로드 시작
      </button>
    </section>
  );
}
