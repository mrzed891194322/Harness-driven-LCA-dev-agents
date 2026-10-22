// SessionLaunchSpec and its parts are generated from the Python contract (schema_version 2).
export type {
  KnowledgeBinding,
  McpBinding,
  ModelProfile,
  PermissionPolicy,
  ResourceBindings,
  SessionLaunchSpec,
  SessionStorage,
  SystemSection,
} from "./spec.generated.js";

export interface ProtocolRequest {
  type: "req";
  id: string;
  method: string;
  params?: Record<string, unknown>;
}

export interface ProtocolResponse {
  type: "res";
  id: string;
  ok: boolean;
  result?: unknown;
  error?: { code: string; message: string };
}

export interface ProtocolEvent {
  type: "event";
  event: string;
  data?: Record<string, unknown>;
}
