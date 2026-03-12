"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { MissionCard } from "@/components/missions/MissionCard";
import { apiGet } from "@/lib/mission-control-api";

type MissionRow = {
  id: string;
  goal: string;
  status: string;
  updated_at: string;
};

type SubtaskSummary = {
  id: string;
  status: string;
  error_message?: string | null;
};

export default function MissionsPage() {
  const [showNeedsAttentionOnly, setShowNeedsAttentionOnly] = useState(false);
  const missionsQuery = useQuery({
    queryKey: ["missions"],
    queryFn: () => apiGet<MissionRow[]>("/api/v1/missions"),
    refetchInterval: 10_000,
  });

  const missions = useMemo(() => missionsQuery.data ?? [], [missionsQuery.data]);
  const subtaskOverviewQuery = useQuery({
    queryKey: ["missions", "subtask-overview", missions.map((mission) => mission.id).join(",")],
    queryFn: async () => {
      const entries = await Promise.all(
        missions.map(async (mission) => {
          const subtasks = await apiGet<SubtaskSummary[]>(`/api/v1/missions/${mission.id}/subtasks`);
          return [mission.id, subtasks] as const;
        }),
      );
      return Object.fromEntries(entries);
    },
    enabled: missions.length > 0,
    refetchInterval: 10_000,
  });

  const missionCards = useMemo(() => {
    const subtaskMap = subtaskOverviewQuery.data ?? {};
    return missions.map((mission) => {
      const subtasks = subtaskMap[mission.id] ?? [];
      const failedSubtasks = subtasks.filter((item) => item.status === "failed").length;
      const needsAttention =
        failedSubtasks > 0 ||
        subtasks.some((item) => item.status === "failed" && item.error_message);
      return {
        ...mission,
        failedSubtasks,
        needsAttention,
      };
    });
  }, [missions, subtaskOverviewQuery.data]);

  const visibleMissions = showNeedsAttentionOnly
    ? missionCards.filter((mission) => mission.needsAttention)
    : missionCards;

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="p-6">
          <h1 className="text-xl font-semibold text-slate-900">Missions / 执行任务</h1>
          <p className="mt-1 text-sm text-slate-500">
            查看 mission 生命周期、执行状态，并快速定位需要处理的项。
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setShowNeedsAttentionOnly((value) => !value)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                showNeedsAttentionOnly
                  ? "bg-amber-600 text-white"
                  : "bg-white text-slate-700 ring-1 ring-slate-200 hover:ring-slate-300"
              }`}
            >
              {showNeedsAttentionOnly ? "仅显示需处理" : "需处理"}
            </button>
            <span className="text-xs text-slate-500">
              {missionCards.filter((mission) => mission.needsAttention).length} 条 mission 需要处理
            </span>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visibleMissions.map((mission) => (
              <MissionCard key={mission.id} mission={mission} />
            ))}
          </div>
          {visibleMissions.length === 0 ? (
            <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">
              {missions.length === 0 ? "当前没有 mission。" : "当前没有需要处理的 mission。"}
            </div>
          ) : null}
        </div>
      </main>
    </DashboardShell>
  );
}
