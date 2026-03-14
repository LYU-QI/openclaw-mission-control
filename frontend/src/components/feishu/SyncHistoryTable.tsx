"use client";

type Entry = {
  timestamp: string;
  direction: string;
  status: string;
  records_processed?: number;
  error?: string | null;
};

export function SyncHistoryTable({ entries }: { entries: Entry[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-900">同步历史</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="py-1">时间</th>
            <th className="py-1">方向</th>
            <th className="py-1">状态</th>
            <th className="py-1">记录数</th>
            <th className="py-1">错误</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, idx) => (
            <tr key={`${entry.timestamp}-${idx}`} className="border-t border-slate-100">
              <td className="py-2">{new Date(entry.timestamp).toLocaleString()}</td>
              <td className="py-2">{entry.direction}</td>
              <td className="py-2">{entry.status}</td>
              <td className="py-2">{entry.records_processed ?? 0}</td>
              <td className="py-2 text-xs text-slate-500">{entry.error ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {entries.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">还没有同步历史。</p>
      ) : null}
    </div>
  );
}
