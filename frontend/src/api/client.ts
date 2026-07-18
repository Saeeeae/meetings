export type UploadResponse = {
  job_id: string;
  status: string;
  filename: string;
};

export type JobStatus = {
  job_id: string;
  filename: string;
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
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

function authHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {};
  if (extra) {
    new Headers(extra).forEach((value, key) => {
      headers[key] = value;
    });
  }
  if (API_KEY) headers["X-API-Key"] = API_KEY;
  return headers;
}

function withApiKey(url: string): string {
  if (!API_KEY) return url;
  const join = url.includes("?") ? "&" : "?";
  return `${url}${join}api_key=${encodeURIComponent(API_KEY)}`;
}

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

export type UploadProgressCallback = (percent: number) => void;

function parseXhrError(xhr: XMLHttpRequest): string {
  try {
    const data = JSON.parse(xhr.responseText);
    if (typeof data.detail === "string") return data.detail;
    if (data.detail) return JSON.stringify(data.detail);
  } catch {
    // fall through
  }
  return xhr.responseText || `${xhr.status} ${xhr.statusText}`;
}

export function uploadRecording(file: File, onProgress?: UploadProgressCallback): Promise<UploadResponse> {
  return new Promise<UploadResponse>((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/uploads`);
    if (API_KEY) xhr.setRequestHeader("X-API-Key", API_KEY);

    if (onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as UploadResponse);
        } catch (error) {
          reject(error instanceof Error ? error : new Error("응답 파싱에 실패했습니다."));
        }
      } else {
        reject(new Error(parseXhrError(xhr)));
      }
    };
    xhr.onerror = () => reject(new Error("네트워크 오류로 업로드에 실패했습니다."));
    xhr.onabort = () => reject(new Error("업로드가 취소되었습니다."));

    xhr.send(formData);
  });
}

export async function fetchJob(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`, { headers: authHeaders() });
  return parseResponse<JobStatus>(response);
}

export async function fetchJobs(limit = 50): Promise<JobStatus[]> {
  const response = await fetch(`${API_BASE_URL}/api/jobs?limit=${limit}`, { headers: authHeaders() });
  return parseResponse<JobStatus[]>(response);
}

export async function retryJob(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/retry`, {
    method: "POST",
    headers: authHeaders(),
  });
  return parseResponse<JobStatus>(response);
}

export async function fetchResult(jobId: string): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE_URL}/api/results/${jobId}`, { headers: authHeaders() });
  return parseResponse<AnalysisResult>(response);
}

export function downloadUrl(jobId: string, type: "minutes" | "summary" | "transcript" | "cleaned_transcript" | "json") {
  return withApiKey(`${API_BASE_URL}/api/results/${jobId}/download?type=${type}`);
}

export function audioUrl(jobId: string) {
  return withApiKey(`${API_BASE_URL}/api/jobs/${jobId}/audio`);
}

export function jobEventsUrl(jobId: string) {
  return withApiKey(`${API_BASE_URL}/api/jobs/${jobId}/events`);
}
