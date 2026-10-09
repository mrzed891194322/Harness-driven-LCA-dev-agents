#!/usr/bin/env node
// `npm run restart`: stop everything (npm run stop), verify no pi-runtime is left,
// then start again (npm start). Never stacks a second runtime.
import { spawn } from "node:child_process";
import path from "node:path";
import { repoProcesses, root, runtimeSocket, socketInUse } from "./service_files.mjs";
import { stopAll } from "./stop_lib.mjs";

await stopAll();
const runtimes = repoProcesses().filter((p) => p.kind === "pi-runtime");
if (runtimes.length || (await socketInUse(runtimeSocket()))) {
  console.error(
    `pi-runtime still running after stop (${runtimes.map((p) => p.pid).join(", ") || runtimeSocket()}); not starting a second one.`,
  );
  process.exit(1);
}
const child = spawn(process.execPath, [path.join(root, "src", "scripts", "start.mjs"), ...process.argv.slice(2)], {
  cwd: root,
  stdio: "inherit",
});
child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 1)));
