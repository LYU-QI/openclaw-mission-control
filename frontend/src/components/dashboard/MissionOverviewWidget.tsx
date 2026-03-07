"use client";

export function MissionOverviewWidget({
  total,
  running,
  pendingApproval,
}: {
  total: number;
  running: number;
  pendingApproval: number;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900">Mission overview</h3>
      <p className="mt-2 text-sm text-slate-600">Total: {total}</p>
      <p className="text-sm text-slate-600">Running: {running}</p>
      <p className="text-sm text-slate-600">Pending approval: {pendingApproval}</p>
    </div>
  );
}

