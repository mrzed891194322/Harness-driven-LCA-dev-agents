// Helpers over the run's activity events (no persistence).
// The run page intentionally shows no openLCA connection notice (Du Yuan 2026-10-16);
// `openlca_unresponsive` events stay in the backend log only.

export type ActivityEvent = {
  kind?: string;
  ts?: string;
  tool?: string;
  summary?: string;
  node?: string;
};

export function lastNodeFromEvents(previous: string, events: ActivityEvent[]): string {
  let node = previous;
  for (const event of events) if (event.node) node = event.node;
  return node;
}
