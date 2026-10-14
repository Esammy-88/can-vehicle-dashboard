export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  can_mode: "auto" | "socketcan" | "virtual";
}
