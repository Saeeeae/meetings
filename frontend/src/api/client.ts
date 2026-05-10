export type UploadResponse = {
  job_id: string;
  status: string;
  filename: string;
};

export type JobStatus = {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  current_step: string;
  created_at: string;
  updated_at: string;
  error_message: string | null;
};

export type ResultSegment = {
  start: number;
  end: number;
  speaker: string;
  text: string;
};

export type AnalysisResult = {
  job_id: string;
  status: string;
  raw_transcript: string;
  speaker_transcript: string;
  cleaned_transcript: string;
  meeting_minutes: string;
  summary: string;
  segments: ResultSegment[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const error = await response.json();
      message = typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail ?? error);
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function uploadRecording(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/uploads`, {
    method: "POST",
    body: formData,
  });
  return parseResponse<UploadResponse>(response);
}

export async function fetchJob(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
  return parseResponse<JobStatus>(response);
}

export async function fetchResult(jobId: string): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE_URL}/api/results/${jobId}`);
  return parseResponse<AnalysisResult>(response);
}

export function downloadUrl(jobId: string, type: "minutes" | "summary" | "transcript" | "cleaned_transcript" | "json") {
  return `${API_BASE_URL}/api/results/${jobId}/download?type=${type}`;
}
