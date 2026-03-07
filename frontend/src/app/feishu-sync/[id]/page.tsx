"use client";

export const dynamic = "force-dynamic";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { FieldMappingEditor } from "@/components/feishu/FieldMappingEditor";
import { SyncHistoryTable } from "@/components/feishu/SyncHistoryTable";
import { apiGet } from "@/lib/mission-control-api";

type SyncConfig = {
  id: string;
  app_id: string;
  bitable_table_id: string;
  field_mapping: Record<string, string>;
  sync_status: string;
};

type MappingItem = {
  id: string;
  feishu_record_id: string;
  task_id: string;
};

type SyncHistory = {
  timestamp: string;
  direction: string;
  status: string;
};

export default function FeishuSyncDetailPage() {
  const params = useParams<{ id: string }>();
  const configId = params.id;
  const configQuery = useQuery({
    queryKey: ["feishu-sync-config", configId],
    queryFn: () => apiGet<SyncConfig>(`/api/v1/feishu-sync/configs/${configId}`),
  });
  const mappingQuery = useQuery({
    queryKey: ["feishu-sync-mapping", configId],
    queryFn: () => apiGet<MappingItem[]>(`/api/v1/feishu-sync/configs/${configId}/mappings`),
  });
  const historyQuery = useQuery({
    queryKey: ["feishu-sync-history", configId],
    queryFn: () => apiGet<SyncHistory[]>(`/api/v1/feishu-sync/configs/${configId}/history`),
  });

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="space-y-4 p-6">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h1 className="text-xl font-semibold text-slate-900">
              {configQuery.data?.app_id ?? "Sync config"}
            </h1>
            <p className="text-sm text-slate-500">
              table: {configQuery.data?.bitable_table_id ?? "-"} / status:{" "}
              {configQuery.data?.sync_status ?? "-"}
            </p>
          </div>
          <FieldMappingEditor mapping={configQuery.data?.field_mapping ?? {}} />
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">Task mappings</h3>
            <div className="space-y-2">
              {(mappingQuery.data ?? []).map((item) => (
                <div
                  key={item.id}
                  className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700"
                >
                  {item.feishu_record_id} → {item.task_id}
                </div>
              ))}
              {(mappingQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">No mappings yet.</p>
              ) : null}
            </div>
          </div>
          <SyncHistoryTable entries={historyQuery.data ?? []} />
        </div>
      </main>
    </DashboardShell>
  );
}

