#!/usr/bin/env node
// Stop the control panel started by `npm start` / `npm run dev` (ISSUES #15/#22/#23).
//
//   npm run stop               backend first (its lifespan and workflow.py children
//                              release their sessions/MCP), then the project's single
//                              pi-runtime (disposes what is left), then web; then sweep
//                              any pi-runtime / MCP / orchestrator / backend / next
//                              process of THIS checkout that is still alive.
//   npm run stop -- --dry-run  only list what would be stopped.
import path from "node:path";
import { root as defaultRoot } from "./service_files.mjs";
import { stopAll } from "./stop_lib.mjs";

const dryRun = process.argv.includes("--dry-run");
const rootArg = process.argv.indexOf("--root");
const repoRoot = rootArg > 0 ? path.resolve(process.argv[rootArg + 1]) : defaultRoot;

const stopped = await stopAll({ dryRun, repoRoot });
if (!dryRun) console.log(stopped ? "stopped." : "nothing was running.");
