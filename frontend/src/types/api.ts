export interface ApiError {
  code: string;
  message: string;
  details: unknown | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
  request_id: string;
}

export interface HealthData {
  status: "ok";
  service: string;
  version: string;
  environment: string;
}

export type HealthResponse = ApiResponse<HealthData>;
