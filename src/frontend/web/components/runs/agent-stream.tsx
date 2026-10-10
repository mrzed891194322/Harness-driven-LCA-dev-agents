"use client";

import { Fragment, type ReactNode, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Bot,
  Check,
  ChevronRight,
  FileText,
  Folder,
  PenLine,
  Search,
  Send,
  Terminal,
  Wrench,
} from "lucide-react";

export type AgentItem =
  | { type: "system"; time: string; text: string; count: number }
  | {
      type: "turn";
      key: string;
      stage: string;
      role: string;
      attempt: string;
      worker: string;
      time: string;
    }
  | { type: "text"; time: string; text: string }
  | {
      type: "tool";
      time: string;
      name: string;
      detail: string;
      state: "run" | "ok" | "err";
      message: string;
    }
  | { type: "error"; time: string; text: string; count: number };

const ROLE_LABEL: Record<string, string> = {
  reviewer: "审查",
  executor: "执行",
  reviser: "修订",
};

const TOOL_ICON = {
  bash: Terminal,
  shell: Terminal,
  read: FileText,
  write: PenLine,
  edit: PenLine,
  grep: Search,
  find: Folder,
  ls: Folder,
} as const;

export function parseAgentLog(raw: string): AgentItem[] {
  const items: AgentItem[] = [];
  let turnKey = "";
  let seenText = new Set<string>();

  for (const block of blocksOf(raw)) {
    const meta = parseTag(block.tag);
    if (!meta) continue;
    const body = block.body.trim();
    if (!body) continue;

    if (meta.kind === "orchestrator") {
      pushSystem(items, meta.time, systemText(body));
      continue;
    }

    const nextTurn = `${meta.stage}|${meta.role}|${meta.attempt}|${meta.worker}`;
    if (nextTurn !== turnKey) {
      turnKey = nextTurn;
      seenText = new Set();
      items.push({
        type: "turn",
        key: nextTurn,
        stage: meta.stage,
        role: meta.role,
        attempt: meta.attempt,
        worker: meta.worker,
        time: meta.time,
      });
    }

    const toolStart = /^→\s+(\S+)(?:\s+([\s\S]*))?$/.exec(body);
    if (toolStart) {
      items.push({
        type: "tool",
        time: meta.time,
        name: toolStart[1],
        detail: (toolStart[2] || "").trim(),
        state: "run",
        message: "",
      });
      continue;
    }

    const toolEnd = /^([✓✗])\s+(\S+)(?:\s+([\s\S]*))?$/.exec(body);
    if (toolEnd) {
      const failed = toolEnd[1] === "✗";
      const detail = (toolEnd[3] || "").replace(/^:\s*/, "").trim();
      const name = toolEnd[2].replace(/:$/, "");
      closeTool(items, name, failed ? "err" : "ok", failed ? detail : "", meta.time);
      continue;
    }

    const error = /^error:\s*([\s\S]*)$/i.exec(body);
    if (error) {
      pushError(items, meta.time, error[1].trim() || body);
      continue;
    }

    const text = body.trim();
    if (seenText.has(text)) continue;
    const last = items[items.length - 1];
    if (last?.type === "text" && text.startsWith(last.text)) {
      last.text = text;
      seenText.add(text);
      continue;
    }
    seenText.add(text);
    items.push({ type: "text", time: meta.time, text });
  }

  return items;
}

export function AgentStream({
  text,
  running,
  model = "",
}: {
  text: string;
  running: boolean;
  model?: string;
}) {
  const items = parseAgentLog(text);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  useEffect(() => {
    const node = scroller.current;
    if (!node || !stick.current) return;
    node.scrollTop = node.scrollHeight;
  }, [text, running]);

  return (
    <div
      ref={scroller}
      className="agent-stream"
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      onScroll={() => {
        const node = scroller.current;
        if (!node) return;
        stick.current = node.scrollHeight - node.scrollTop - node.clientHeight < 64;
      }}
    >
      {items.length === 0 ? (
        <p className="settings-help">
          {running ? "正在等待 agent 输出…" : "还没有运行记录。工作流开始后，这里会按 agent 的输出逐段出现。"}
        </p>
      ) : (
        items.map((item, index) => (
          <AgentRow key={`${item.type}-${index}`} item={item} model={model} />
        ))
      )}
      {running ? (
        <p className="agent-live">
          <span className="agent-caret" aria-hidden="true" />
          正在输出
        </p>
      ) : null}
    </div>
  );
}

function AgentRow({ item, model }: { item: AgentItem; model: string }) {
  if (item.type === "system") {
    return (
      <p className="agent-system">
        <span className="agent-system-mark" aria-hidden="true">
          <Terminal size={13} strokeWidth={1.75} />
        </span>
        <time>{item.time}</time>
        <span className="agent-system-text">
          <SystemText text={item.text} />
          {item.count > 1 ? <em> ×{item.count}</em> : null}
        </span>
      </p>
    );
  }
  if (item.type === "turn") {
    const role = ROLE_LABEL[item.role] || item.role;
    const attempt = item.attempt ? `第 ${item.attempt} 次` : "";
    return (
      <h3 className="agent-turn" data-role={item.role}>
        <span className="agent-turn-mark" aria-hidden="true">
          <Bot size={16} strokeWidth={1.75} />
        </span>
        <span className="agent-turn-stage">{item.stage}</span>
        {role ? <span className="agent-turn-role">{role}</span> : null}
        {attempt ? <span className="agent-turn-attempt">{attempt}</span> : null}
        <span className="agent-turn-side">
          {model || item.worker ? (
            <span className="agent-turn-model" title={model || item.worker}>
              {model || item.worker}
            </span>
          ) : null}
          {item.time ? <time>{item.time}</time> : null}
        </span>
      </h3>
    );
  }
  if (item.type === "tool") return <ToolRow item={item} />;
  if (item.type === "error") {
    return (
      <p className="agent-error">
        <AlertCircle size={15} strokeWidth={1.75} aria-hidden="true" />
        <span>
          {item.text}
          {item.count > 1 ? <em> ×{item.count}</em> : null}
        </span>
        <time>{item.time}</time>
      </p>
    );
  }
  return (
    <div className="agent-prose">
      <AgentProse text={item.text} />
    </div>
  );
}

function ToolRow({ item }: { item: Extract<AgentItem, { type: "tool" }> }) {
  const handoff = /(^|__|\.)submit_handoff$/.test(item.name);
  const Icon = handoff ? Send : TOOL_ICON[item.name as keyof typeof TOOL_ICON] ?? Wrench;
  const preview = item.detail.split("\n")[0] || item.message;
  const stateLabel = handoff
    ? item.state === "ok"
      ? "已交卷"
      : item.state === "err"
        ? "交卷失败"
        : "交卷中"
    : item.state === "ok"
      ? "完成"
      : item.state === "err"
        ? "失败"
        : "进行中";
  const [open, setOpen] = useState(item.detail.length > 0 && item.detail.length < 160);
  return (
    <details
      className="agent-tool"
      data-state={item.state}
      data-handoff={handoff ? "true" : undefined}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <ChevronRight className="agent-tool-chevron" size={14} strokeWidth={1.75} aria-hidden="true" />
        <Icon size={15} strokeWidth={1.75} aria-hidden="true" />
        <span className="agent-tool-name">{item.name}</span>
        {preview ? <span className="agent-tool-preview">{preview}</span> : null}
        <span className="agent-tool-state">
          {item.state === "ok" ? <Check size={13} strokeWidth={2} aria-hidden="true" /> : null}
          {item.state === "err" ? <AlertCircle size={13} strokeWidth={1.75} aria-hidden="true" /> : null}
          {item.state === "run" ? <span className="agent-spinner" aria-hidden="true" /> : null}
          {stateLabel}
        </span>
        <time>{item.time}</time>
      </summary>
      {item.detail ? <pre>{item.detail}</pre> : null}
      {item.message ? <p className="agent-tool-message">{item.message}</p> : null}
    </details>
  );
}

function SystemText({ text }: { text: string }) {
  const prepare = /^准备 (\S+) · (第 \d+ 次)$/.exec(text);
  if (prepare) {
    return (
      <>
        准备 <code>{prepare[1]}</code> · {prepare[2]}
      </>
    );
  }
  const start = /^开始运行 · (\S+)$/.exec(text);
  if (start) {
    return (
      <>
        开始运行 · <code>{start[1]}</code>
      </>
    );
  }
  const ended = /^运行结束 · ([\s\S]+)$/.exec(text);
  if (ended) {
    return (
      <>
        运行结束 · <code>{ended[1]}</code>
      </>
    );
  }
  return text;
}

function AgentProse({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      const Tag = heading[1].length === 1 ? "h4" : "h5";
      blocks.push(<Tag key={blocks.length}>{inline(heading[2])}</Tag>);
      index += 1;
      continue;
    }
    if (isTableRow(line)) {
      let header: string[] | null = null;
      if (isTableStart(lines, index)) {
        header = splitCells(lines[index]);
        index += 2;
      }
      const rows: string[][] = [];
      while (index < lines.length && isTableRow(lines[index]) && !isTableSep(lines[index])) {
        rows.push(splitCells(lines[index]));
        index += 1;
      }
      if (index < lines.length && /^\|?\s*…+\s*\|?$/.test(lines[index].trim())) index += 1;
      const width = Math.max(header?.length ?? 0, ...rows.map((row) => row.length), 1);
      blocks.push(
        <div className="agent-table" key={blocks.length}>
          <table>
            {header ? (
              <thead>
                <tr>
                  {padCells(header, width).map((cell, cellIndex) => (
                    <th key={cellIndex}>{inline(cell)}</th>
                  ))}
                </tr>
              </thead>
            ) : null}
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {padCells(row, width).map((cell, cellIndex) => (
                    <td key={cellIndex}>{inline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      const list: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index])) {
        list.push(lines[index].replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ol key={blocks.length}>
          {list.map((entry, entryIndex) => (
            <li key={entryIndex}>{inline(entry)}</li>
          ))}
        </ol>,
      );
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      const list: string[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index])) {
        list.push(lines[index].replace(/^[-*]\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ul key={blocks.length}>
          {list.map((entry, entryIndex) => (
            <li key={entryIndex}>{inline(entry)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    const paragraph: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,3})\s+/.test(lines[index]) &&
      !/^\d+\.\s+/.test(lines[index]) &&
      !/^[-*]\s+/.test(lines[index]) &&
      !isTableRow(lines[index])
    ) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push(<p key={blocks.length}>{inline(paragraph.join(" "))}</p>);
  }
  return <Fragment>{blocks}</Fragment>;
}

function isTableRow(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.slice(1).includes("|");
}

function isTableSep(line: string): boolean {
  const cells = splitCells(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function isTableStart(lines: string[], index: number): boolean {
  return index + 1 < lines.length && isTableRow(lines[index]) && isTableSep(lines[index + 1]);
}

function splitCells(line: string): string[] {
  let raw = line.trim();
  if (raw.startsWith("|")) raw = raw.slice(1);
  if (raw.endsWith("|")) raw = raw.slice(0, -1);
  return raw.split("|").map((cell) => cell.trim());
}

function padCells(cells: string[], width: number): string[] {
  return Array.from({ length: width }, (_, index) => cells[index] ?? "");
}

function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = pattern.exec(text))) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      parts.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    } else {
      parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    }
    key += 1;
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function blocksOf(raw: string): { tag: string; body: string }[] {
  const blocks: { tag: string; body: string }[] = [];
  let tag = "";
  let lines: string[] = [];
  const flush = () => {
    if (!tag) return;
    blocks.push({ tag, body: lines.join("\n").replace(/^\n+|\n+$/g, "") });
    tag = "";
    lines = [];
  };
  for (const line of raw.replace(/\r\n/g, "\n").split("\n")) {
    const match = /^\[([^\]]+)\](.*)$/.exec(line);
    if (match && isProgressTag(match[1])) {
      flush();
      tag = match[1];
      const inlineBody = match[2].trim();
      lines = inlineBody ? [inlineBody] : [];
    } else if (tag) {
      lines.push(line);
    }
  }
  flush();
  return blocks;
}

function isProgressTag(tag: string): boolean {
  return (
    /^orchestrator-\d{2}:\d{2}:\d{2}$/.test(tag) ||
    /^.+\([^)]+\)-[^-]+-\d{2}:\d{2}:\d{2}$/.test(tag)
  );
}

function parseTag(tag: string):
  | { kind: "orchestrator"; time: string }
  | {
      kind: "agent";
      stage: string;
      role: string;
      attempt: string;
      worker: string;
      time: string;
    }
  | null {
  const orchestrator = /^orchestrator-(\d{2}:\d{2}:\d{2})$/.exec(tag);
  if (orchestrator) return { kind: "orchestrator", time: orchestrator[1] };
  const agent = /^(.*)\(([^)]+)\)-([^-]+)-(\d{2}:\d{2}:\d{2})$/.exec(tag);
  if (!agent) return null;
  const actor = /^([^#]+)#(\d+)$/.exec(agent[2].trim());
  return {
    kind: "agent",
    stage: agent[1],
    role: actor ? actor[1] : agent[2].trim(),
    attempt: actor ? actor[2] : "",
    worker: agent[3],
    time: agent[4],
  };
}

function systemText(body: string): string {
  const start = /^start run_id=\S+\s+task=\S+\s+worker=(\S+)/.exec(body);
  if (start) return `开始运行 · ${start[1]}`;
  const prepare = /^prepare (\S+) attempt=(\d+)/.exec(body);
  if (prepare) return `准备 ${prepare[1]} · 第 ${prepare[2]} 次`;
  if (body.startsWith("worker turn done")) return "本轮结束";
  const retry = /^worker transport retry (\d+)\/(\d+) \(([^)]+)\):\s*(.*)$/.exec(body);
  if (retry) return `模型连接重试 ${retry[1]}/${retry[2]} · ${retry[4] || retry[3]}`;
  const finished = /^finished status=(\S+)\s+reason=(.*)$/.exec(body);
  if (finished) {
    return finished[1] === "completed" ? "运行完成" : `运行结束 · ${finished[2]}`;
  }
  return body;
}

function closeTool(
  items: AgentItem[],
  rawName: string,
  state: "ok" | "err",
  message: string,
  time: string,
) {
  const name = rawName === "写入" ? "write" : rawName;
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index];
    if (item.type === "tool" && item.state === "run" && item.name === name) {
      item.state = state;
      item.time = time;
      if (message) item.message = message;
      return;
    }
  }
  items.push({
    type: "tool",
    time,
    name,
    detail: "",
    state,
    message,
  });
}

function pushSystem(items: AgentItem[], time: string, text: string) {
  const last = items[items.length - 1];
  if (last?.type === "system" && last.text === text) {
    last.count += 1;
    last.time = time;
    return;
  }
  items.push({ type: "system", time, text, count: 1 });
}

function pushError(items: AgentItem[], time: string, text: string) {
  const last = items[items.length - 1];
  if (last?.type === "error" && last.text === text) {
    last.count += 1;
    last.time = time;
    return;
  }
  items.push({ type: "error", time, text, count: 1 });
}
