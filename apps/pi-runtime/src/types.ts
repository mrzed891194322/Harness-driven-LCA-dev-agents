/** Mirrors contracts/session_launch_spec.schema.json (schema_version 1). */

export interface SessionLaunchSpec {
  schema_version: 1;
  run_id: string;
  stage_id: string;
  assignment_id: string;
  role: string;
  attempt: number;
  session_key: string;
  execution_id: string;
  bundle_hash: string;
  input_snapshot_hash: string;
  model_profile: ModelProfile;
  system_sections: SystemSection[];
  turn_context: Record<string, unknown>;
  knowledge_bindings: KnowledgeBinding[];
  resource_bindings: ResourceBindings;
  mcp_bindings: Record<string, McpBinding>;
  permission_policy: PermissionPolicy;
  session_storage: SessionStorage;
  handoff_binding?: HandoffBinding;
}

export interface ModelProfile {
  profile_id: string;
  display_name?: string;
  provider: string;
  model_id: string;
  api_type?: string;
  base_url?: string;
  parameters?: Record<string, unknown>;
}

export interface SystemSection {
  id: string;
  content: string;
  source_hash: string;
}

export interface KnowledgeBinding {
  id: string;
  root_path: string;
  content_hash: string;
  summary?: string;
}

export interface ResourceBindings {
  project_root?: string;
  workspace_root?: string;
  host_python?: string;
  credentials_dir?: string;
}

export interface McpBinding {
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  timeout_ms?: number;
  exposure?: "direct" | "deferred" | "codemode" | "hidden";
}

export interface PermissionPolicy {
  allowed_tools: string[];
  allowed_read_globs: string[];
  allowed_write_globs: string[];
  deny_shell?: boolean;
}

export interface SessionStorage {
  agent_dir: string;
  session_file: string;
}

export interface HandoffBinding {
  relative_path?: string;
  schema_path?: string;
}

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
