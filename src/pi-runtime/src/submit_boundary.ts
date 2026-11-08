import type { Agent } from "@earendil-works/pi-agent-core";
import type { SettleGuard } from "./settle_guard.js";

/** Install after AgentSession has installed its persistence/boundary hooks.
 * Abort stops unstarted sibling tools, while finishTurn prevents even a further
 * provider invocation. SDK 1.3.0 abort alone still enters the next stream with an
 * already-aborted signal. Always preserve the SDK finishTurn persistence first.
 */
export function installSubmitBoundary(agent: Agent, guard: SettleGuard): void {
  agent.toolExecution = "sequential";
  const previous = agent.finishTurn;
  agent.finishTurn = async (turn, signal) => {
    const decision = await previous?.(turn, signal);
    if (guard.submitted() || signal?.aborted) return { action: "end" };
    return decision ?? undefined;
  };
}
