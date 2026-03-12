"use client";

import Link from "next/link";

import { MissionStatusBadge } from "@/components/missions/MissionStatusBadge";

type MissionItem = {
  id: string;
  goal: string;
  status: string;
  updated_at: string;
  needsAttention?: boolean;
  failedSubtasks?: number;
};

export function MissionCard({ mission }: { mission: MissionItem }) {
  return (
    <Link
      href={`/missions/${mission.id}`}
      className={`block rounded-xl border bg-white p-4 transition hover:shadow-sm ${
        mission.needsAttention
          ? "border-amber-300 hover:border-amber-400"
          : "border-slate-200 hover:border-slate-300"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="line-clamp-2 font-semibold text-slate-900">{mission.goal}</h3>
        <MissionStatusBadge status={mission.status} />
      </div>
      {mission.needsAttention ? (
        <p className="mt-2 text-xs font-medium text-amber-700">
          需要处理
          {mission.failedSubtasks ? ` · 失败子任务 ${mission.failedSubtasks}` : ""}
        </p>
      ) : null}
      <p className="mt-2 text-xs text-slate-500">
        更新时间：{new Date(mission.updated_at).toLocaleString()}
      </p>
    </Link>
  );
}
