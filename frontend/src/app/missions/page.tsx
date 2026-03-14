"use client";

export const dynamic = "force-dynamic";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams, useRouter, usePathname } from "next/navigation";

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
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const activeFilters = useMemo(() => {
    const filterParam = searchParams.get("filter");
    return filterParam ? filterParam.split(",") : [];
  }, [searchParams]);

  const toggleFilter = (filterKey: string) => {
    const newFilters = new Set(activeFilters);
    if (newFilters.has(filterKey)) {
      newFilters.delete(filterKey);
    } else {
      newFilters.add(filterKey);
    }
    const params = new URLSearchParams(searchParams.toString());
    if (newFilters.size > 0) {
      params.set("filter", Array.from(newFilters).join(","));
    } else {
      params.delete("filter");
    }
    router.push(`${pathname}?${params.toString()}`);
  };
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
        
      const minutesSinceUpdate = (Date.now() - new Date(mission.updated_at).getTime()) / 60000;
      const isStale = ["pending", "in_progress"].includes(mission.status) && minutesSinceUpdate > 60;
      
      const isTimedOut = (mission.status === "failed" || mission.status === "timeout") && 
          subtasks.some((item) => item.error_message?.toLowerCase().includes("timeout") || item.status === "timeout");

      return {
        ...mission,
        failedSubtasks,
        needsAttention,
        isStale,
        isTimedOut,
      };
    });
  }, [missions, subtaskOverviewQuery.data]);

  const visibleMissions = useMemo(() => {
    if (activeFilters.length === 0) return missionCards;
    return missionCards.filter((mission) => {
      if (activeFilters.includes("attention") && mission.needsAttention) return true;
      if (activeFilters.includes("stale") && mission.isStale) return true;
      if (activeFilters.includes("timed_out") && mission.isTimedOut) return true;
      return false;
    });
  }, [missionCards, activeFilters]);

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
              onClick={() => toggleFilter("attention")}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                activeFilters.includes("attention")
                  ? "bg-amber-600 text-white"
                  : "bg-white text-slate-700 ring-1 ring-slate-200 hover:ring-slate-300"
              }`}
            >
              需处理 ({missionCards.filter((m) => m.needsAttention).length})
            </button>
            <button
              type="button"
              onClick={() => toggleFilter("stale")}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                activeFilters.includes("stale")
                  ? "bg-slate-600 text-white"
                  : "bg-white text-slate-700 ring-1 ring-slate-200 hover:ring-slate-300"
              }`}
            >
              已陈旧 ({missionCards.filter((m) => m.isStale).length})
            </button>
            <button
              type="button"
              onClick={() => toggleFilter("timed_out")}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                activeFilters.includes("timed_out")
                  ? "bg-rose-600 text-white"
                  : "bg-white text-slate-700 ring-1 ring-slate-200 hover:ring-slate-300"
              }`}
            >
              已超时 ({missionCards.filter((m) => m.isTimedOut).length})
            </button>
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
