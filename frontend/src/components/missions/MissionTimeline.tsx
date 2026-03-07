"use client";

type TimelineEntry = {
  timestamp: string;
  event_type: string;
  message?: string | null;
};

export function MissionTimeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-900">Timeline</h3>
      <div className="space-y-2">
        {entries.map((entry, idx) => (
          <div key={`${entry.timestamp}-${idx}`} className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              {entry.event_type}
            </p>
            <p className="text-sm text-slate-800">{entry.message ?? "-"}</p>
            <p className="text-xs text-slate-500">
              {new Date(entry.timestamp).toLocaleString()}
            </p>
          </div>
        ))}
        {entries.length === 0 ? (
          <p className="text-sm text-slate-500">No timeline events yet.</p>
        ) : null}
      </div>
    </div>
  );
}

