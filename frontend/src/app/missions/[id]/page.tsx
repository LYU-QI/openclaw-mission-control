"use client";

export const dynamic = "force-dynamic";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { MissionDetailPanel } from "@/components/missions/MissionDetailPanel";
import { MissionTimeline } from "@/components/missions/MissionTimeline";
import { SubtaskList } from "@/components/missions/SubtaskList";
import { apiGet } from "@/lib/mission-control-api";

type MissionDetail = {
  id: string;
  goal: string;
  status: string;
  result_summary?: string | null;
  result_risk?: string | null;
  result_next_action?: string | null;
};

type SubtaskItem = {
  id: string;
  label: string;
  status: string;
  expected_output?: string | null;
};

type TimelineEntry = {
  timestamp: string;
  event_type: string;
  message?: string | null;
};

export default function MissionDetailPage() {
  const params = useParams<{ id: string }>();
  const missionId = params.id;

  const missionQuery = useQuery({
    queryKey: ["mission", missionId],
    queryFn: () => apiGet<MissionDetail>(`/api/v1/missions/${missionId}`),
  });
  const subtasksQuery = useQuery({
    queryKey: ["mission", missionId, "subtasks"],
    queryFn: () => apiGet<SubtaskItem[]>(`/api/v1/missions/${missionId}/subtasks`),
  });
  const timelineQuery = useQuery({
    queryKey: ["mission", missionId, "timeline"],
    queryFn: () => apiGet<TimelineEntry[]>(`/api/v1/missions/${missionId}/timeline`),
    refetchInterval: 5_000,
  });

  const mission = missionQuery.data;

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="space-y-4 p-6">
          <MissionDetailPanel
            goal={mission?.goal ?? "Mission detail"}
            status={mission?.status ?? "unknown"}
            summary={mission?.result_summary}
            risk={mission?.result_risk}
            nextAction={mission?.result_next_action}
          />
          <div className="grid gap-4 lg:grid-cols-2">
            <SubtaskList subtasks={subtasksQuery.data ?? []} />
            <MissionTimeline entries={timelineQuery.data ?? []} />
          </div>
        </div>
      </main>
    </DashboardShell>
  );
}
