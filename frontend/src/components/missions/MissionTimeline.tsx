"use client";

type TimelineEntry = {
  timestamp: string;
  event_type: string;
  stage: string;
  stage_label: string;
  tone: "info" | "success" | "warning" | "danger" | "muted";
  status_hint?: string | null;
  message?: string | null;
};

const toneClasses: Record<TimelineEntry["tone"], string> = {
  info: "border-sky-200 bg-sky-50 text-sky-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  danger: "border-rose-200 bg-rose-50 text-rose-700",
  muted: "border-slate-200 bg-slate-50 text-slate-600",
};

export function MissionTimeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-900">时间线</h3>
      <div className="space-y-2">
        {entries.map((entry, idx) => (
          <div key={`${entry.timestamp}-${idx}`} className="rounded-lg bg-slate-50 px-3 py-2">
            <div className="mb-1 flex items-center gap-2">
              <span
                className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${toneClasses[entry.tone]}`}
              >
                {entry.stage_label}
              </span>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                {entry.event_type}
              </p>
            </div>
            <p className="text-sm text-slate-800">{entry.message ?? "-"}</p>
            {entry.status_hint ? (
              <p className="mt-1 text-xs text-slate-500">状态提示：{entry.status_hint}</p>
            ) : null}
            <p className="text-xs text-slate-500">
              {new Date(entry.timestamp).toLocaleString()}
            </p>
          </div>
        ))}
        {entries.length === 0 ? (
          <p className="text-sm text-slate-500">暂无时间线事件。</p>
        ) : null}
      </div>
    </div>
  );
}
