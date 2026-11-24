export const TASK_STATES = [
  "queued",
  "running",
  "completed",
  "insufficient_evidence",
  "failed",
  "timed_out",
] as const;

export type TaskStatus = (typeof TASK_STATES)[number];

export interface ResearchScope {
  geography: string | null;
  category: string | null;
  time_scope: string | null;
  competitors: string[];
}

export interface ResearchInput {
  question: string;
  scope: ResearchScope;
}

export interface ResearchTask extends ResearchInput {
  id: string;
  status: TaskStatus;
  current_stage: string | null;
  error_category: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ResearchAccepted {
  task_id: string;
  status: TaskStatus;
  status_url: string;
}

export interface ResearchHistory {
  items: ResearchTask[];
  next_cursor: string | null;
}

export const STATUS_LABELS: Record<TaskStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  insufficient_evidence: "Insufficient evidence",
  failed: "Failed",
  timed_out: "Timed out",
};

export function isTerminal(status: TaskStatus): boolean {
  return status !== "queued" && status !== "running";
}

export function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return typeof value === "object"
    && value !== null
    && !Array.isArray(value);
}

export function isTaskStatus(value: unknown): value is TaskStatus {
  return typeof value === "string"
    && TASK_STATES.some((status) => status === value);
}

export function isTaskId(value: unknown): value is string {
  return typeof value === "string"
    && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}

function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function timestamp(value: unknown): value is string {
  return typeof value === "string"
    && Number.isFinite(Date.parse(value));
}

function nullableTimestamp(value: unknown): boolean {
  return value === null || timestamp(value);
}

export function isResearchScope(value: unknown): value is ResearchScope {
  return isRecord(value)
    && nullableString(value.geography)
    && nullableString(value.category)
    && nullableString(value.time_scope)
    && Array.isArray(value.competitors)
    && value.competitors.every(
      (item: unknown) => typeof item === "string",
    );
}

export function isResearchTask(value: unknown): value is ResearchTask {
  return isRecord(value)
    && isTaskId(value.id)
    && typeof value.question === "string"
    && isResearchScope(value.scope)
    && isTaskStatus(value.status)
    && nullableString(value.current_stage)
    && nullableString(value.error_category)
    && timestamp(value.created_at)
    && timestamp(value.updated_at)
    && nullableTimestamp(value.started_at)
    && nullableTimestamp(value.completed_at);
}

export function isResearchAccepted(
  value: unknown,
): value is ResearchAccepted {
  return isRecord(value)
    && isTaskId(value.task_id)
    && isTaskStatus(value.status)
    && value.status_url === `/api/v1/research/tasks/${value.task_id}`;
}

export function isResearchHistory(
  value: unknown,
): value is ResearchHistory {
  return isRecord(value)
    && Array.isArray(value.items)
    && value.items.length <= 100
    && value.items.every(isResearchTask)
    && (
      value.next_cursor === null
      || (
        typeof value.next_cursor === "string"
        && value.next_cursor.length > 0
        && value.next_cursor.length <= 256
      )
    );
}
