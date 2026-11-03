import { apiClient } from "../../api/client";
import type { CreateMcpServerRequest, McpServer, McpTool, UpdateMcpServerRequest } from "./types";

const BASE = "/api/v1/mcp-servers";

export const mcpApi = {
  listServers: (token: string) => apiClient.get<McpServer[]>(BASE, token),
  createServer: (data: CreateMcpServerRequest, token: string) => apiClient.post<McpServer>(BASE, data, token),
  updateServer: (id: string, data: UpdateMcpServerRequest, token: string) =>
    apiClient.patch<McpServer>(`${BASE}/${id}`, data, token),
  deleteServer: (id: string, token: string) => apiClient.del<void>(`${BASE}/${id}`, token),
  listTools: (id: string, token: string) => apiClient.get<McpTool[]>(`${BASE}/${id}/tools`, token),
  syncTools: (id: string, token: string) => apiClient.post<McpTool[]>(`${BASE}/${id}/sync`, {}, token),
  reviewTool: (serverId: string, toolId: string, action: "approve" | "block", token: string) =>
    apiClient.post<McpTool>(`${BASE}/${serverId}/tools/${toolId}/${action}`, {}, token),
};
