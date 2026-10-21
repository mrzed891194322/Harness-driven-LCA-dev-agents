/** /runs link for the plan page: new work runs full-lca, revise work runs revise-lca. */
export function runWorkflowFor(mode: "new" | "revise"): string {
  return mode === "revise" ? "revise-lca" : "full-lca";
}

export function runHref(mode: "new" | "revise"): string {
  return `/runs?workflow=${encodeURIComponent(runWorkflowFor(mode))}`;
}
