"use client";

export function SyncStatusWidget({
  configs,
  errors,
}: {
  configs: number;
  errors: number;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900">Feishu sync status</h3>
      <p className="mt-2 text-sm text-slate-600">Configs: {configs}</p>
      <p className="text-sm text-slate-600">Errored: {errors}</p>
    </div>
  );
}

