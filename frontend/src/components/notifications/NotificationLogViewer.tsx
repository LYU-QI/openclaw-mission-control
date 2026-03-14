"use client";

import { useMemo } from "react";

type LogItem = {
  id: string;
  event_type: string;
  status: string;
  error_message?: string | null;
  created_at: string;
};

// 事件类型到中文标签和颜色的映射
const EVENT_TYPE_LABELS: Record<string, { label: string; tone: string }> = {
  mission_created: { label: "📋 新任务已创建", tone: "bg-blue-100 text-blue-700" },
  mission_dispatched: { label: "🚀 任务已下发", tone: "bg-blue-100 text-blue-700" },
  mission_started: { label: "⚡ 任务开始执行", tone: "bg-blue-100 text-blue-700" },
  mission_completed: { label: "✅ 任务执行完成", tone: "bg-emerald-100 text-emerald-700" },
  mission_failed: { label: "❌ 任务执行失败", tone: "bg-rose-100 text-rose-700" },
  approval_requested: { label: "⚠️ 需要人工审批", tone: "bg-amber-100 text-amber-700" },
  approval_granted: { label: "✅ 审批已通过", tone: "bg-emerald-100 text-emerald-700" },
  approval_rejected: { label: "❌ 审批已拒绝", tone: "bg-rose-100 text-rose-700" },
  feishu_sync_pull: { label: "🔄 飞书同步完成", tone: "bg-blue-100 text-blue-700" },
  feishu_sync_push: { label: "📤 结果已回写飞书", tone: "bg-blue-100 text-blue-700" },
  test: { label: "🔔 测试通知", tone: "bg-slate-100 text-slate-700" },
};

function getEventLabel(eventType: string) {
  return EVENT_TYPE_LABELS[eventType] ?? { label: `📢 ${eventType}`, tone: "bg-slate-100 text-slate-700" };
}

export function NotificationLogViewer({ logs }: { logs: LogItem[] }) {
  // 按事件类型统计
  const eventTypeSummary = useMemo(() => {
    const counts: Record<string, { total: number; failed: number }> = {};
    for (const log of logs) {
      const entry = counts[log.event_type] ?? { total: 0, failed: 0 };
      entry.total += 1;
      if (log.status !== "ok" && log.status !== "sent") {
        entry.failed += 1;
      }
      counts[log.event_type] = entry;
    }
    return Object.entries(counts)
      .sort(([, a], [, b]) => b.total - a.total)
      .map(([type, stats]) => ({ type, ...stats }));
  }, [logs]);

  // 失败的日志条目
  const failedLogs = useMemo(
    () => logs.filter((log) => log.status !== "ok" && log.status !== "sent"),
    [logs],
  );

  return (
    <div className="space-y-4">
      {/* 事件类型概览 */}
      {eventTypeSummary.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">事件类型概览</h3>
          <div className="flex flex-wrap gap-2">
            {eventTypeSummary.map(({ type, total, failed }) => {
              const meta = getEventLabel(type);
              return (
                <div
                  key={type}
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${meta.tone}`}
                >
                  <span>{meta.label}</span>
                  <span className="rounded-full bg-white/60 px-1.5 py-0.5 text-[10px] font-bold">
                    {total}
                  </span>
                  {failed > 0 && (
                    <span className="rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
                      {failed} 失败
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 最近失败的通知 */}
      {failedLogs.length > 0 && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <h3 className="mb-3 text-sm font-semibold text-rose-800">
            最近失败的通知 ({failedLogs.length})
          </h3>
          <div className="space-y-2">
            {failedLogs.slice(0, 5).map((log) => {
              const meta = getEventLabel(log.event_type);
              return (
                <div
                  key={log.id}
                  className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-rose-700">{meta.label}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        状态：{log.status}
                        {log.error_message && ` — ${log.error_message}`}
                      </p>
                    </div>
                    <span className="shrink-0 text-[11px] text-slate-500">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              );
            })}
            {failedLogs.length > 5 && (
              <p className="text-xs text-rose-600">
                仅显示最近 5 条，共 {failedLogs.length} 条失败记录。
              </p>
            )}
          </div>
        </div>
      )}

      {/* 通知日志列表 */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-900">通知日志</h3>
        <div className="space-y-2">
          {logs.map((log) => {
            const meta = getEventLabel(log.event_type);
            const isFailed = log.status !== "ok" && log.status !== "sent";
            return (
              <div
                key={log.id}
                className={`rounded-lg px-3 py-2 text-sm ${isFailed ? "border border-rose-200 bg-rose-50" : "bg-slate-50"
                  }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-800">{meta.label}</p>
                    <p className={`text-xs ${isFailed ? "text-rose-600" : "text-slate-500"}`}>
                      状态：{log.status}
                      {isFailed && log.error_message && (
                        <span className="ml-1 text-rose-500">— {log.error_message}</span>
                      )}
                    </p>
                  </div>
                  <span className="shrink-0 text-[11px] text-slate-500">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>
              </div>
            );
          })}
          {logs.length === 0 ? (
            <p className="text-sm text-slate-500">暂无通知日志。</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
