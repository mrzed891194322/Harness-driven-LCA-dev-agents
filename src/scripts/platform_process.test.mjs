import { test } from 'node:test';
import assert from 'node:assert/strict';
import { matchRepoProcess, parseWin32ProcessList } from './platform.mjs';
test('classifies actual supported service entry points', () => {
  for (const [command, kind] of [
    ['uv run uvicorn backend.api.app:app --app-dir src', 'backend'],
    ['/r/.venv/bin/python /r/.venv/bin/uvicorn backend.api.app:app', 'backend'],
    ['python3 -m uvicorn backend.api.app:app', 'backend'],
    ['node /r/src/pi-runtime/dist/main.js --listen /r/socket', 'pi-runtime'],
    ['python3 /r/src/scripts/workflow.py', 'orchestrator'],
    ['uv run python harness/tools/mcp/submit/main.py', 'mcp'],
    ['node /r/node_modules/.bin/next dev', 'web'],
    ['next-server (v15.5.27)', 'web'],
    ['"C:\\Program Files\\node.exe" "C:\\repo\\src\\pi-runtime\\dist\\main.js"', 'pi-runtime'],
  ]) assert.equal(matchRepoProcess(command), kind, command);
});
test('never classifies service descriptions, launchers, or code arguments as services', () => {
  for (const command of [
    'codex exec --json user says uv run uvicorn backend.api.app:app --app-dir src',
    'node /tools/codex.js exec node /r/src/pi-runtime/dist/main.js',
    'node /tools/codex.js /r/src/pi-runtime/dist/main.js',
    'python3 -c "backend.api.app:app"',
    'zsh -c "node /r/src/pi-runtime/dist/main.js"',
    'python3 /r/.benchmark/serial-launch-v3.py backend.api.app:app',
    'python3 /r/.benchmark/guarded-native-batch-v3.py',
  ]) assert.equal(matchRepoProcess(command), null, command);
  assert.deepEqual(parseWin32ProcessList(JSON.stringify([
    { ProcessId: 1, CommandLine: 'codex exec -C C:\\repo backend.api.app:app' },
  ]), 'C:\\repo'), []);
});
