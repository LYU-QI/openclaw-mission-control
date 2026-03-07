"use client";

type Entry = {
  timestamp: string;
  direction: string;
  status: string;
};

export function SyncHistoryTable({ entries }: { entries: Entry[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-900">Sync history</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="py-1">Time</th>
            <th className="py-1">Direction</th>
            <th className="py-1">Status</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, idx) => (
            <tr key={`${entry.timestamp}-${idx}`} className="border-t border-slate-100">
              <td className="py-2">{new Date(entry.timestamp).toLocaleString()}</td>
              <td className="py-2">{entry.direction}</td>
              <td className="py-2">{entry.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {entries.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No history yet.</p>
      ) : null}
    </div>
  );
}

