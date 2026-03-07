"use client";

import { MissionStatusBadge } from "@/components/missions/MissionStatusBadge";

type Props = {
  goal: string;
  status: string;
  summary?: string | null;
  risk?: string | null;
  nextAction?: string | null;
};

export function MissionDetailPanel({
  goal,
  status,
  summary,
  risk,
  nextAction,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-900">{goal}</h2>
        <MissionStatusBadge status={status} />
      </div>
      {summary ? <p className="mt-3 text-sm text-slate-700">{summary}</p> : null}
      {(risk || nextAction) && (
        <div className="mt-3 grid gap-2 text-sm text-slate-600 md:grid-cols-2">
          <p>Risk: {risk ?? "-"}</p>
          <p>Next action: {nextAction ?? "-"}</p>
        </div>
      )}
    </div>
  );
}

