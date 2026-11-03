export type PinMode = "off" | "warn" | "enforce";
export type ScanMode = "off" | "log" | "redact" | "block";
export type ToolStatus = "pending" | "approved" | "drifted" | "blocked";

export interface McpServer {
  id: string;
  name: string;
  url: string;
  is_active: boolean;
  has_auth: boolean;
  pin_mode: PinMode;
  scan_mode: ScanMode;
  created_at: string;
}

export interface McpTool {
  id: string;
  server_id: string;
  name: string;
  status: ToolStatus;
  definition: Record<string, unknown>;
  approved_snapshot: Record<string, unknown> | null;
  current_hash: string;
  approved_hash: string | null;
  first_seen_at: string;
  last_seen_at: string;
  approved_at: string | null;
}

export interface CreateMcpServerRequest {
  name: string;
  url: string;
  auth_header?: string;
  pin_mode: PinMode;
  scan_mode: ScanMode;
}

export interface UpdateMcpServerRequest {
  is_active?: boolean;
  pin_mode?: PinMode;
  scan_mode?: ScanMode;
}
