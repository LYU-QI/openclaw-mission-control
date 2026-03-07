"use client";

import { MissionStatusBadge } from "@/components/missions/MissionStatusBadge";

type SubtaskItem = {
  id: string;
  label: string;
  status: string;
  expected_output?: string | null;
};

export function SubtaskList({ subtasks }: { subtasks: SubtaskItem[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-900">Subtasks</h3>
      <div className="space-y-2">
        {subtasks.map((subtask) => (
          <div
            key={subtask.id}
            className="flex items-start justify-between rounded-lg bg-slate-50 px-3 py-2"
          >
            <div>
              <p className="text-sm font-medium text-slate-900">{subtask.label}</p>
              {subtask.expected_output ? (
                <p className="text-xs text-slate-500">{subtask.expected_output}</p>
              ) : null}
            </div>
            <MissionStatusBadge status={subtask.status} />
          </div>
        ))}
        {subtasks.length === 0 ? (
          <p className="text-sm text-slate-500">No subtasks yet.</p>
        ) : null}
      </div>
    </div>
  );
}

