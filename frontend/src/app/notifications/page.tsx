"use client";

export const dynamic = "force-dynamic";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { NotificationConfigForm } from "@/components/notifications/NotificationConfigForm";
import { NotificationLogViewer } from "@/components/notifications/NotificationLogViewer";
import { NotificationTemplatePreview } from "@/components/notifications/NotificationTemplatePreview";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost, apiDelete } from "@/lib/mission-control-api";

type NotificationConfig = {
  id: string;
  organization_id: string;
  board_id: string | null;
  name: string;
  channel_type: string;
  enabled: boolean;
};

type NotificationLog = {
  id: string;
  event_type: string;
  status: string;
  error_message?: string | null;
  created_at: string;
};

type Board = {
  id: string;
  name: string;
};

const DEMO_ORG_ID = "ee32b8b7-fe7a-49bd-881d-b69b8dcc9a4e"; // RQI organization

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const configsQuery = useQuery({
    queryKey: ["notification-configs"],
    queryFn: () => apiGet<NotificationConfig[]>("/api/v1/notifications/configs"),
  });
  const logsQuery = useQuery({
    queryKey: ["notification-logs"],
    queryFn: () => apiGet<NotificationLog[]>("/api/v1/notifications/logs"),
    refetchInterval: 15_000,
  });
  const boardsQuery = useQuery({
    queryKey: ["boards"],
    queryFn: async () => {
      const res = await apiGet<{ items: Board[] }>("/api/v1/boards");
      return res.items;
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: {
      name: string;
      board_id: string | null;
      channel_type: string;
      channel_config: { webhook_url: string; webhook_secret?: string };
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

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiDelete(`/api/v1/notifications/configs/${id}`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notification-configs"] });
    },
  });

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="space-y-4 p-6">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold text-slate-900">通知管理 / Notifications</h1>
              <p className="mt-1 text-sm text-slate-500">
                管理通知渠道配置，查看事件分布和投递日志。
              </p>
            </div>
            <NotificationTemplatePreview />
          </div>
          <NotificationConfigForm
            boards={boardsQuery.data ?? []}
            onSubmit={async (payload) => {
              await createMutation.mutateAsync(payload);
            }}
          />
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">
              通知渠道
            </h3>
            <div className="space-y-2">
              {(configsQuery.data ?? []).map((config) => (
                <div
                  key={config.id}
                  className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
                >
                  <div className="flex flex-col">
                    <span className="font-medium">{config.name || "未命名"}</span>
                    <span className="text-xs text-slate-500">
                      {config.board_id
                        ? `看板: ${boardsQuery.data?.find((b) => b.id === config.board_id)?.name || config.board_id}`
                        : "全局渠道"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">
                      {config.enabled ? "已启用" : "已禁用"}
                    </span>
                    <Button size="sm" variant="outline" onClick={() => testMutation.mutate(config.id)}>
                      测试
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => {
                        if (confirm(`确定要删除渠道 "${config.name || '未命名'}" 吗？`)) {
                          deleteMutation.mutate(config.id);
                        }
                      }}
                    >
                      删除
                    </Button>
                  </div>
                </div>
              ))}
              {(configsQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">暂无通知渠道配置。</p>
              ) : null}
            </div>
          </div>
          <NotificationLogViewer logs={logsQuery.data ?? []} />
        </div>
      </main>
    </DashboardShell>
  );
}
