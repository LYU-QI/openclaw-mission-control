"use client";

export const dynamic = "force-dynamic";

import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { FeishuSyncConfigForm } from "@/components/feishu/FeishuSyncConfigForm";
import { FieldMappingEditor } from "@/components/feishu/FieldMappingEditor";
import { SyncHistoryTable } from "@/components/feishu/SyncHistoryTable";
import { apiGet, apiPost } from "@/lib/mission-control-api";

type SyncConfig = {
  id: string;
  organization_id: string;
  app_id: string;
  bitable_app_token: string;
  bitable_table_id: string;
  field_mapping: Record<string, string>;
  sync_status: string;
};

type SyncHistory = {
  timestamp: string;
  direction: string;
  status: string;
};

const DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001";

export default function FeishuSyncPage() {
  const queryClient = useQueryClient();
  const configsQuery = useQuery({
    queryKey: ["feishu-sync-configs"],
    queryFn: () => apiGet<SyncConfig[]>("/api/v1/feishu-sync/configs"),
  });
  const firstConfig = configsQuery.data?.[0];
  const historyQuery = useQuery({
    queryKey: ["feishu-sync-history", firstConfig?.id],
    enabled: Boolean(firstConfig?.id),
    queryFn: () =>
      apiGet<SyncHistory[]>(`/api/v1/feishu-sync/configs/${firstConfig?.id}/history`),
  });

  const createMutation = useMutation({
    mutationFn: (payload: {
      app_id: string;
      app_secret: string;
      bitable_app_token: string;
      bitable_table_id: string;
    }) =>
      apiPost<SyncConfig>("/api/v1/feishu-sync/configs", {
        organization_id: DEMO_ORG_ID,
        ...payload,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-configs"] });
    },
  });

  const triggerMutation = useMutation({
    mutationFn: (configId: string) =>
      apiPost<{ ok: boolean }>(`/api/v1/feishu-sync/configs/${configId}/trigger`, {}),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-configs"] });
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-history"] });
    },
  });

  const mapping = useMemo(
    () => firstConfig?.field_mapping ?? {},
    [firstConfig?.field_mapping],
  );

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="space-y-4 p-6">
          <h1 className="text-xl font-semibold text-slate-900">Feishu Sync</h1>
          <FeishuSyncConfigForm
            onSubmit={async (payload) => {
              await createMutation.mutateAsync(payload);
            }}
          />
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">Configs</h3>
            <div className="space-y-2">
              {(configsQuery.data ?? []).map((config) => (
                <button
                  key={config.id}
                  className="w-full rounded-lg bg-slate-50 px-3 py-2 text-left text-sm"
                  onClick={() => triggerMutation.mutate(config.id)}
                  type="button"
                >
                  {config.app_id} / {config.bitable_table_id} / {config.sync_status}
                </button>
              ))}
              {(configsQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">No sync config yet.</p>
              ) : null}
            </div>
          </div>
          <FieldMappingEditor mapping={mapping} />
          <SyncHistoryTable entries={historyQuery.data ?? []} />
        </div>
      </main>
    </DashboardShell>
  );
}
