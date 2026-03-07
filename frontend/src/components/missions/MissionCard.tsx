"use client";

import Link from "next/link";

import { MissionStatusBadge } from "@/components/missions/MissionStatusBadge";

type MissionItem = {
  id: string;
  goal: string;
  status: string;
  updated_at: string;
};

export function MissionCard({ mission }: { mission: MissionItem }) {
  return (
    <Link
      href={`/missions/${mission.id}`}
      className="block rounded-xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm"
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="line-clamp-2 font-semibold text-slate-900">{mission.goal}</h3>
        <MissionStatusBadge status={mission.status} />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Updated: {new Date(mission.updated_at).toLocaleString()}
      </p>
    </Link>
  );
}

