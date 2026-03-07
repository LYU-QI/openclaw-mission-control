"use client";

export const dynamic = "force-dynamic";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { NotificationConfigForm } from "@/components/notifications/NotificationConfigForm";
import { NotificationLogViewer } from "@/components/notifications/NotificationLogViewer";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost } from "@/lib/mission-control-api";

type NotificationConfig = {
  id: string;
  organization_id: string;
  channel_type: string;
  enabled: boolean;
};

type NotificationLog = {
  id: string;
  event_type: string;
  status: string;
  created_at: string;
};

const DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001";

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const configsQuery = useQuery({
    queryKey: ["notification-configs"],
    queryFn: () => apiGet<NotificationConfig[]>("/api/v1/notifications/configs"),
  });
  const logsQuery = useQuery({
    queryKey: ["notification-logs"],
    queryFn: () => apiGet<NotificationLog[]>("/api/v1/notifications/logs"),
  });

  const createMutation = useMutation({
    mutationFn: (payload: {
      channel_type: string;
      channel_config: { webhook_url: string };
    }) =>
      apiPost<NotificationConfig>("/api/v1/notifications/configs", {
        organization_id: DEMO_ORG_ID,
        notify_on_events: ["mission_completed", "mission_failed", "approval_requested"],
        ...payload,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notification-configs"] });
    },
  });

  const testMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost<{ ok: boolean }>(`/api/v1/notifications/configs/${id}/test`, {}),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notification-logs"] });
    },
  });

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="space-y-4 p-6">
          <h1 className="text-xl font-semibold text-slate-900">Notifications</h1>
          <NotificationConfigForm
            onSubmit={async (payload) => {
              await createMutation.mutateAsync(payload);
            }}
          />
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">
              Notification channels
            </h3>
            <div className="space-y-2">
              {(configsQuery.data ?? []).map((config) => (
                <div
                  key={config.id}
                  className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
                >
                  <span>
                    {config.channel_type} / {config.enabled ? "enabled" : "disabled"}
                  </span>
                  <Button size="sm" onClick={() => testMutation.mutate(config.id)}>
                    Test
                  </Button>
                </div>
              ))}
              {(configsQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">No notification config yet.</p>
              ) : null}
            </div>
          </div>
          <NotificationLogViewer logs={logsQuery.data ?? []} />
        </div>
      </main>
    </DashboardShell>
  );
}
