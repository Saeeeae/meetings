import { ChangeEvent, DragEvent, useState } from "react";
import { FileAudio2, ShieldCheck, UploadCloud } from "lucide-react";

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
    <section className="upload-surface">
      <div className="upload-heading">
        <div>
          <p className="eyebrow">NEW VOICE NOTE</p>
          <h2>새 음성 노트 만들기</h2>
          <p>회의, 강의, 인터뷰 파일을 올리면 음성 기록과 요약을 생성합니다.</p>
        </div>
        <FileAudio2 aria-hidden="true" />
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
        <span>{selectedFile ? selectedFile.name : "파일을 끌어놓거나 눌러서 선택하세요"}</span>
        <small>{selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(1)} MB` : ".mp3, .wav, .m4a, .aac, .flac, .mp4, .webm"}</small>
      </label>

      <div className="upload-hint">
        <ShieldCheck size={17} aria-hidden="true" />
        <p>참가자 동의와 내부 보안 정책을 확인하고, 상대방 음성이 녹음되어 있는지 먼저 재생해 확인해주세요.</p>
      </div>

      <button
        className="primary-button"
        type="button"
        disabled={!selectedFile || disabled}
        onClick={() => selectedFile && onUpload(selectedFile)}
      >
        <UploadCloud size={18} aria-hidden="true" />
        음성 노트 만들기
      </button>
    </section>
  );
}
