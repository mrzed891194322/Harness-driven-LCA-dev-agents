// Helpers over the run's activity events (no persistence).
// The run page intentionally shows no openLCA connection notice (Du Yuan 2026-10-16);
// `openlca_unresponsive` events stay in the backend log only.

export type ActivityEvent = {
  kind?: string;
  ts?: string;
  tool?: string;
  summary?: string;
  stage?: string;
};

export function lastStageFromEvents(previous: string, events: ActivityEvent[]): string {
  let stage = previous;
  for (const event of events) if (event.stage) stage = event.stage;
  return stage;
}
