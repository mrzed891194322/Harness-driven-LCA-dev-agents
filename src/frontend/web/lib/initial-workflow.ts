/**
 * Which workflow the /runs select should show on load: the current or latest
 * run's workflow when it is still defined, else full-lca, else the first one.
 */
export function initialWorkflow(runWorkflow: string | undefined, ids: string[], fallback = "full-lca"): string {
  if (runWorkflow && (ids.length === 0 || ids.includes(runWorkflow))) return runWorkflow;
  if (ids.includes(fallback) || ids.length === 0) return fallback;
  return ids[0];
}
