"use client";

// Restored from master 599ed0a (same markup and CSS classes); data now comes from /api/v5/events.
import { useEffect, useRef } from "react";
import { History, Play } from "lucide-react";
import { HANDOFF_LABEL, isLive, summarizeActivity } from "../../lib/run-activity";
import { label } from "../../lib/labels";
import type { RunEvent } from "../../lib/run-events";

export function ActivitySummary({ events, running = false }: { events: RunEvent[]; running?: boolean }) {
  const items = summarizeActivity(events);
  const liveRef = useRef<HTMLLIElement | null>(null);
  const live = items.find((i) => isLive(i, running));
  useEffect(() => {
    liveRef.current?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [live?.key]);
  if (!items.length) return null;
  return (
    <ul className="activity-summary" aria-label="各分工活动概览" data-testid="activity-summary">
      {items.map((item) => {
        const tone = item.handoff === "ok" ? "ok" : item.handoff === "err" ? "fail" : item.turnEnded ? "warn" : "off";
        const active = isLive(item, running);
        return (
          <li
            key={item.key}
            ref={active ? liveRef : undefined}
            className={active ? "activity-chip is-live" : "activity-chip"}
            title={item.note || undefined}
            data-testid={`activity-chip-${item.key}`}
          >
            <span className="activity-chip-head">
              <span className="activity-chip-mark" role="img" aria-label={active ? "正在执行" : "历史记录"}>
                {active ? <Play size={13} strokeWidth={1.75} /> : <History size={13} strokeWidth={1.75} />}
              </span>
              <strong>{item.stage}</strong>
              <small>
                {label(item.role)}
                {item.attempt ? ` · 第 ${item.attempt} 轮` : ""}
              </small>
            </span>
            <span className="activity-chip-body">
              <span>
                {item.retries ? `${item.retries} 次模型重试` : "无模型重试"}
                {item.rejections ? <em className="activity-chip-err"> · 被拒 {item.rejections} 次</em> : null}
                {item.nudges ? <em className="activity-chip-err"> · 提醒 {item.nudges} 次</em> : null}
              </span>
              {active ? (
                <span className="activity-chip-running">
                  <span className="agent-spinner" aria-hidden="true" />
                  执行中
                </span>
              ) : null}
              <span className={`badge badge-${tone}`}>
                {item.verdict ? label(item.verdict) : HANDOFF_LABEL[item.handoff]}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
