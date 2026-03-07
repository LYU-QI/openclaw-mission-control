"use client";

export const dynamic = "force-dynamic";

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

export default function MissionsPage() {
  const missionsQuery = useQuery({
    queryKey: ["missions"],
    queryFn: () => apiGet<MissionRow[]>("/api/v1/missions"),
    refetchInterval: 10_000,
  });

  const missions = missionsQuery.data ?? [];

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="p-6">
          <h1 className="text-xl font-semibold text-slate-900">Missions</h1>
          <p className="mt-1 text-sm text-slate-500">
            Monitor mission lifecycle, execution status, and drill into details.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {missions.map((mission) => (
              <MissionCard key={mission.id} mission={mission} />
            ))}
          </div>
          {missions.length === 0 ? (
            <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">
              No missions found.
            </div>
          ) : null}
        </div>
      </main>
    </DashboardShell>
  );
}

