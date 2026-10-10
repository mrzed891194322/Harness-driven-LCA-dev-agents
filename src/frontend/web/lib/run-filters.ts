/** Runs used only for doctor/inspect self-check; hide from user-facing lists. */
export function isHiddenDoctorRun(runId: string): boolean {
  const id = runId.trim();
  return id === "doctor-selfcheck" || id.startsWith("doctor-");
}

export function filterVisibleRuns<T extends { run_id: string }>(runs: T[]): T[] {
  return runs.filter((r) => !isHiddenDoctorRun(r.run_id));
}
