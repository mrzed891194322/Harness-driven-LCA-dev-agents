"use client";

import { Fragment, type ReactNode } from "react";

type MarkdownViewProps = {
  source: string;
  onOpen?: (href: string) => void;
};

export function MarkdownView({ source, onOpen }: MarkdownViewProps) {
  const body = source.replace(/^(?:[ \t]*\r?\n)*#\s+[^\n]*(?:\n|$)/, "");
  return <div className="harness-doc">{renderBlocks(body, onOpen)}</div>;
}

function renderBlocks(source: string, onOpen?: (href: string) => void) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const language = line.slice(3).trim();
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        body.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push(
        <pre key={blocks.length} data-language={language || undefined}>
          <code>{body.join("\n")}</code>
        </pre>,
      );
      continue;
    }
    if (isTableRow(line) && index + 1 < lines.length && isTableDivider(lines[index + 1])) {
      const rows = [splitTable(line)];
      index += 2;
      while (index < lines.length && isTableRow(lines[index])) {
        rows.push(splitTable(lines[index]));
        index += 1;
      }
      const [head, ...body] = rows;
      blocks.push(
        <div key={blocks.length} className="harness-table-wrap">
          <table>
            <thead>
              <tr>
                {head.map((cell, cellIndex) => (
                  <th key={cellIndex}>{renderInline(cell, onOpen)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{renderInline(cell, onOpen)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const Tag = `h${Math.min(level + 1, 4)}` as "h2" | "h3" | "h4";
      blocks.push(<Tag key={blocks.length}>{renderInline(heading[2], onOpen)}</Tag>);
      index += 1;
      continue;
    }
    if (/^>\s?/.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push(<blockquote key={blocks.length}>{renderInline(quote.join(" "), onOpen)}</blockquote>);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*]\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ul key={blocks.length}>
          {items.map((item, itemIndex) => (
            <li key={itemIndex}>{renderInline(item, onOpen)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*\d+[.)]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+[.)]\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ol key={blocks.length}>
          {items.map((item, itemIndex) => (
            <li key={itemIndex}>{renderInline(item, onOpen)}</li>
          ))}
        </ol>,
      );
      continue;
    }
    const paragraph: string[] = [line];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].startsWith("```") &&
      !/^(#{1,4})\s+/.test(lines[index]) &&
      !/^\s*[-*]\s+/.test(lines[index]) &&
      !/^\s*\d+[.)]\s+/.test(lines[index]) &&
      !/^>\s?/.test(lines[index]) &&
      !isTableRow(lines[index])
    ) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push(<p key={blocks.length}>{renderInline(paragraph.join(" "), onOpen)}</p>);
  }
  return blocks;
}

function isTableRow(line: string) {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.includes("|", 1);
}

function isTableDivider(line: string) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function splitTable(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderInline(text: string, onOpen?: (href: string) => void): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\[[^\]]+\]\([^)]+\))/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > cursor) nodes.push(text.slice(cursor, start));
    const token = match[0];
    if (token.startsWith("`")) {
      nodes.push(<code key={start}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      nodes.push(<strong key={start}>{token.slice(2, -2)}</strong>);
    } else {
      const linked = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      if (linked) nodes.push(<Fragment key={start}>{renderLink(linked[1], linked[2], onOpen)}</Fragment>);
    }
    cursor = start + token.length;
  }
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

function renderLink(label: string, href: string, onOpen?: (href: string) => void) {
  const target = href.trim();
  if (target.startsWith("https://") || target.startsWith("http://")) {
    return (
      <a href={target} target="_blank" rel="noreferrer">
        {label}
      </a>
    );
  }
  if (onOpen && isRelativeDoc(target)) {
    return (
      <a
        href={target}
        onClick={(event) => {
          event.preventDefault();
          onOpen(target);
        }}
      >
        {label}
      </a>
    );
  }
  return <span>{label}</span>;
}

function isRelativeDoc(href: string) {
  if (!href || href.startsWith("#") || href.startsWith("/") || /^[a-z]+:/i.test(href)) return false;
  const clean = href.split("#")[0].split("?")[0];
  return /\.(md|ya?ml|json)$/i.test(clean);
}
