"use client";

export const dynamic = "force-dynamic";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { MissionDetailPanel } from "@/components/missions/MissionDetailPanel";
import { MissionTimeline } from "@/components/missions/MissionTimeline";
import { SubtaskList } from "@/components/missions/SubtaskList";
import { apiGet, apiPost } from "@/lib/mission-control-api";

type MissionDetail = {
  id: string;
  goal: string;
  status: string;
  approval_policy?: string | null;
  approval_id?: string | null;
  result_summary?: string | null;
  result_evidence?: {
    stats?: {
      total?: number;
      completed?: number;
      pending?: number;
      failed?: number;
      high_risk?: number;
    };
    anomalies?: unknown[];
  } | null;
  result_risk?: string | null;
  result_next_action?: string | null;
  error_message?: string | null;
  updated_at?: string | null;
};

type SubtaskItem = {
  id: string;
  label: string;
  status: string;
  expected_output?: string | null;
  assigned_subagent_id?: string | null;
  result_summary?: string | null;
  result_risk?: string | null;
  error_message?: string | null;
  updated_at?: string | null;
};

type TimelineEntry = {
  timestamp: string;
  event_type: string;
  stage: string;
  stage_label: string;
  tone: "info" | "success" | "warning" | "danger" | "muted";
  status_hint?: string | null;
  message?: string | null;
};

export default function MissionDetailPage() {
  const params = useParams<{ id: string }>();
  const missionId = params.id;
  const queryClient = useQueryClient();

  const missionQuery = useQuery({
    queryKey: ["mission", missionId],
    queryFn: () => apiGet<MissionDetail>(`/api/v1/missions/${missionId}`),
    refetchInterval: 5_000,
  });
  const subtasksQuery = useQuery({
    queryKey: ["mission", missionId, "subtasks"],
    queryFn: () => apiGet<SubtaskItem[]>(`/api/v1/missions/${missionId}/subtasks`),
    refetchInterval: 5_000,
  });
  const timelineQuery = useQuery({
    queryKey: ["mission", missionId, "timeline"],
    queryFn: () => apiGet<TimelineEntry[]>(`/api/v1/missions/${missionId}/timeline`),
    refetchInterval: 5_000,
  });
  const redispatchMutation = useMutation({
    mutationFn: (subtaskId: string) =>
      apiPost<SubtaskItem>(`/api/v1/missions/subtasks/${subtaskId}/redispatch`, undefined),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["mission", missionId] }),
        queryClient.invalidateQueries({ queryKey: ["mission", missionId, "subtasks"] }),
        queryClient.invalidateQueries({ queryKey: ["mission", missionId, "timeline"] }),
      ]);
    },
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
            approvalPolicy={mission?.approval_policy}
            approvalId={mission?.approval_id}
            summary={mission?.result_summary}
            evidenceStats={mission?.result_evidence?.stats}
            anomaliesCount={mission?.result_evidence?.anomalies?.length ?? 0}
            risk={mission?.result_risk}
            nextAction={mission?.result_next_action}
            errorMessage={mission?.error_message}
            updatedAt={mission?.updated_at}
          />
          <div className="grid gap-4 lg:grid-cols-2">
            <SubtaskList
              subtasks={subtasksQuery.data ?? []}
              onRedispatch={(subtaskId) => redispatchMutation.mutateAsync(subtaskId).then(() => undefined)}
            />
            <MissionTimeline entries={timelineQuery.data ?? []} />
          </div>
        </div>
      </main>
    </DashboardShell>
  );
}
