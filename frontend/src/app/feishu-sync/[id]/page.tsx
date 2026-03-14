"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { FieldMappingEditor } from "@/components/feishu/FieldMappingEditor";
import { SyncHistoryTable } from "@/components/feishu/SyncHistoryTable";
import {
  getFeishuSyncDiagnostics,
  getMissingMappingSuggestions,
} from "@/lib/feishu-sync-diagnostics";
import { apiGet, apiPatch, apiPost } from "@/lib/mission-control-api";

type SyncConfig = {
  id: string;
  board_id?: string | null;
  app_id: string;
  bitable_app_token: string;
  bitable_table_id: string;
  field_mapping: Record<string, string>;
  sync_status: string;
  sync_direction?: string;
  last_sync_at?: string | null;
  last_error?: string | null;
  enabled?: boolean;
};

type MappingItem = {
  id: string;
  feishu_record_id: string;
  task_id: string;
  task_title?: string | null;
  sync_hash?: string | null;
  last_feishu_update?: string | null;
  last_mc_update?: string | null;
  updated_at?: string | null;
  has_conflict?: boolean;
  conflict_at?: string | null;
  conflict_message?: string | null;
};

type SyncHistory = {
  timestamp: string;
  direction: string;
  status: string;
  records_processed?: number;
  error?: string | null;
};

type TriggerResult = {
  ok: boolean;
  message: string;
  records_processed: number;
  records_created: number;
  records_updated: number;
  records_skipped: number;
  conflicts_count: number;
};

export default function FeishuSyncDetailPage() {
  const queryClient = useQueryClient();
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
  const triggerMutation = useMutation({
    mutationFn: () => apiPost<TriggerResult>(`/api/v1/feishu-sync/configs/${configId}/trigger`, {}),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["feishu-sync-config", configId] }),
        queryClient.invalidateQueries({ queryKey: ["feishu-sync-history", configId] }),
        queryClient.invalidateQueries({ queryKey: ["feishu-sync-mapping", configId] }),
      ]);
    },
  });
  const updateMappingMutation = useMutation({
    mutationFn: (fieldMapping: Record<string, string>) =>
      apiPatch<SyncConfig>(`/api/v1/feishu-sync/configs/${configId}`, {
        field_mapping: fieldMapping,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-config", configId] });
    },
  });
  const resolveConflictMutation = useMutation({
    mutationFn: ({
      mappingId,
      resolution,
    }: {
      mappingId: string;
      resolution: "keep_local" | "accept_feishu";
    }) =>
      apiPost<MappingItem>(
        `/api/v1/feishu-sync/configs/${configId}/mappings/${mappingId}/resolve`,
        { resolution },
      ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["feishu-sync-mapping", configId] }),
        queryClient.invalidateQueries({ queryKey: ["feishu-sync-history", configId] }),
        queryClient.invalidateQueries({ queryKey: ["feishu-sync-config", configId] }),
      ]);
    },
  });
  const mappingSuggestions = getMissingMappingSuggestions(configQuery.data?.field_mapping ?? {});
  const diagnostics = getFeishuSyncDiagnostics(configQuery.data?.last_error);

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="space-y-4 p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Feishu Sync</p>
              <h1 className="mt-1 text-xl font-semibold text-slate-900">
                {configQuery.data?.app_id ?? "同步配置详情"}
              </h1>
            </div>
            <Link
              href="/feishu-sync"
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700"
            >
              返回列表
            </Link>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">配置概览</h3>
                <p className="mt-1 text-sm text-slate-500">
                  这是一条单独的同步工作台，用来管理映射、冲突和同步历史。
                </p>
              </div>
              <button
                type="button"
                onClick={() => triggerMutation.mutate()}
                disabled={triggerMutation.isPending}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {triggerMutation.isPending ? "同步中..." : "立即同步"}
              </button>
            </div>
            <div className="mt-4 grid gap-3 text-sm text-slate-700 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Board</p>
                <p className="mt-1 break-all font-medium">{configQuery.data?.board_id ?? "-"}</p>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">同步方向</p>
                <p className="mt-1 font-medium">{configQuery.data?.sync_direction ?? "-"}</p>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">最近同步</p>
                <p className="mt-1 font-medium">
                  {configQuery.data?.last_sync_at
                    ? new Date(configQuery.data.last_sync_at).toLocaleString()
                    : "还没有"}
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">状态</p>
                <p className="mt-1 font-medium">{configQuery.data?.sync_status ?? "-"}</p>
              </div>
            </div>
            <div className="mt-4 grid gap-3 text-sm text-slate-700 md:grid-cols-2">
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">App ID</p>
                <p className="mt-1 break-all font-medium">{configQuery.data?.app_id ?? "-"}</p>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Bitable Table</p>
                <p className="mt-1 break-all font-medium">{configQuery.data?.bitable_table_id ?? "-"}</p>
              </div>
            </div>
            {configQuery.data?.last_error ? (
              <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                最近失败原因：{configQuery.data.last_error}
              </div>
            ) : null}
            {diagnostics.length > 0 ? (
              <div className="mt-4 space-y-2">
                {diagnostics.map((item) => (
                  <div
                    key={`${item.title}-${item.message}`}
                    className={`rounded-lg px-3 py-2 text-sm ${
                      item.tone === "error"
                        ? "border border-rose-200 bg-rose-50 text-rose-700"
                        : item.tone === "warning"
                          ? "border border-amber-200 bg-amber-50 text-amber-800"
                          : "border border-sky-200 bg-sky-50 text-sky-800"
                    }`}
                  >
                    <p className="font-medium">{item.title}</p>
                    <p className="mt-1">{item.message}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          {triggerMutation.data ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-slate-900">最近一次同步结果</h3>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    triggerMutation.data.ok
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-rose-50 text-rose-700"
                  }`}
                >
                  {triggerMutation.data.ok ? "成功" : "失败"}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-600">{triggerMutation.data.message}</p>
              <div className="mt-4 grid gap-3 text-sm text-slate-700 md:grid-cols-5">
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">处理</p>
                  <p className="mt-1 font-medium">{triggerMutation.data.records_processed}</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">新建</p>
                  <p className="mt-1 font-medium">{triggerMutation.data.records_created}</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">更新</p>
                  <p className="mt-1 font-medium">{triggerMutation.data.records_updated}</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">跳过</p>
                  <p className="mt-1 font-medium">{triggerMutation.data.records_skipped}</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">冲突</p>
                  <p className="mt-1 font-medium">{triggerMutation.data.conflicts_count}</p>
                </div>
              </div>
            </div>
          ) : null}
          <FieldMappingEditor
            mapping={configQuery.data?.field_mapping ?? {}}
            isSaving={updateMappingMutation.isPending}
            onSave={async (mapping) => {
              await updateMappingMutation.mutateAsync(mapping);
            }}
          />
          {mappingSuggestions.length > 0 ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <h3 className="text-sm font-semibold text-amber-900">字段映射建议</h3>
              <div className="mt-3 space-y-2 text-sm text-amber-800">
                {mappingSuggestions.map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
              当前核心字段映射已经齐全，常规任务同步链路不会因为缺少标题、描述、优先级或状态而退化。
            </div>
          )}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">映射与冲突</h3>
            <div className="space-y-2">
              {(mappingQuery.data ?? []).map((item) => (
                <div
                  key={item.id}
                  className={`rounded-lg px-3 py-2 text-sm ${
                    item.has_conflict ? "border border-amber-200 bg-amber-50" : "bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-900">
                        {item.task_title ?? item.feishu_record_id}
                      </p>
                      <p className="text-xs text-slate-500">{item.feishu_record_id}</p>
                    </div>
                    <div className="text-right">
                      {item.has_conflict ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                          有冲突
                        </span>
                      ) : (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                          正常
                        </span>
                      )}
                      <p className="mt-1 text-xs text-slate-500">{item.task_id}</p>
                    </div>
                  </div>
                  <div className="mt-2 grid gap-1 text-xs text-slate-500 md:grid-cols-3">
                    <p>
                      飞书更新时间：
                      {item.last_feishu_update ? new Date(item.last_feishu_update).toLocaleString() : "-"}
                    </p>
                    <p>
                      本地更新时间：
                      {item.last_mc_update ? new Date(item.last_mc_update).toLocaleString() : "-"}
                    </p>
                    <p>Hash：{item.sync_hash ?? "-"}</p>
                  </div>
                  {item.has_conflict ? (
                    <div className="mt-3 space-y-2 rounded-lg border border-amber-200 bg-white px-3 py-2">
                      <p className="text-xs font-medium text-amber-800">
                        冲突时间：
                        {item.conflict_at ? new Date(item.conflict_at).toLocaleString() : "-"}
                      </p>
                      <p className="text-xs text-amber-700">
                        {item.conflict_message ?? "本地任务和飞书记录都发生了变更。"}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                          disabled={resolveConflictMutation.isPending}
                          onClick={() => {
                            resolveConflictMutation.mutate({
                              mappingId: item.id,
                              resolution: "keep_local",
                            });
                          }}
                        >
                          保留本地
                        </button>
                        <button
                          type="button"
                          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 disabled:opacity-50"
                          disabled={resolveConflictMutation.isPending}
                          onClick={() => {
                            resolveConflictMutation.mutate({
                              mappingId: item.id,
                              resolution: "accept_feishu",
                            });
                          }}
                        >
                          接受飞书
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              ))}
              {(mappingQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">当前还没有同步映射记录。</p>
              ) : null}
            </div>
          </div>
          <SyncHistoryTable entries={historyQuery.data ?? []} />
        </div>
      </main>
    </DashboardShell>
  );
}
