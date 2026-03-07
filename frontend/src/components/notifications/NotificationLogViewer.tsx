"use client";

type LogItem = {
  id: string;
  event_type: string;
  status: string;
  created_at: string;
};

export function NotificationLogViewer({ logs }: { logs: LogItem[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-900">Notification logs</h3>
      <div className="space-y-2">
        {logs.map((log) => (
          <div key={log.id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
            <p className="font-medium text-slate-800">{log.event_type}</p>
            <p className="text-slate-500">status: {log.status}</p>
            <p className="text-slate-500">
              {new Date(log.created_at).toLocaleString()}
            </p>
          </div>
        ))}
        {logs.length === 0 ? <p className="text-sm text-slate-500">No logs yet.</p> : null}
      </div>
    </div>
  );
}

