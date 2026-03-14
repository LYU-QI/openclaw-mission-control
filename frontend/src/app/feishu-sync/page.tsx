"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { FeishuSyncConfigForm } from "@/components/feishu/FeishuSyncConfigForm";
import { FieldMappingEditor } from "@/components/feishu/FieldMappingEditor";
import { SyncHistoryTable } from "@/components/feishu/SyncHistoryTable";
import { apiGet, apiPatch, apiPost } from "@/lib/mission-control-api";

type SyncConfig = {
  id: string;
  organization_id: string;
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

type SyncHistory = {
  timestamp: string;
  direction: string;
  status: string;
  records_processed?: number;
  error?: string | null;
};

type SyncMapping = {
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

type TriggerResult = {
  ok: boolean;
  message: string;
  records_processed: number;
  records_created: number;
  records_updated: number;
  records_skipped: number;
  conflicts_count: number;
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
  const mappingsQuery = useQuery({
    queryKey: ["feishu-sync-mappings", firstConfig?.id],
    enabled: Boolean(firstConfig?.id),
    queryFn: () =>
      apiGet<SyncMapping[]>(`/api/v1/feishu-sync/configs/${firstConfig?.id}/mappings`),
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
      apiPost<TriggerResult>(`/api/v1/feishu-sync/configs/${configId}/trigger`, {}),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-configs"] });
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-history"] });
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-mappings"] });
    },
  });
  const updateMappingMutation = useMutation({
    mutationFn: ({
      configId,
      fieldMapping,
    }: {
      configId: string;
      fieldMapping: Record<string, string>;
    }) =>
      apiPatch<SyncConfig>(`/api/v1/feishu-sync/configs/${configId}`, {
        field_mapping: fieldMapping,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-configs"] });
    },
  });
  const resolveConflictMutation = useMutation({
    mutationFn: ({
      configId,
      mappingId,
      resolution,
    }: {
      configId: string;
      mappingId: string;
      resolution: "keep_local" | "accept_feishu";
    }) =>
      apiPost<SyncMapping>(
        `/api/v1/feishu-sync/configs/${configId}/mappings/${mappingId}/resolve`,
        { resolution },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-mappings"] });
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-history"] });
      await queryClient.invalidateQueries({ queryKey: ["feishu-sync-configs"] });
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
          <h1 className="text-xl font-semibold text-slate-900">飞书同步</h1>
          <FeishuSyncConfigForm
            onSubmit={async (payload) => {
              await createMutation.mutateAsync(payload);
            }}
          />
          {firstConfig ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-slate-900">当前配置概览</h3>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    firstConfig.enabled === false
                      ? "bg-slate-100 text-slate-600"
                      : firstConfig.sync_status === "error"
                        ? "bg-rose-50 text-rose-700"
                        : "bg-emerald-50 text-emerald-700"
                  }`}
                >
                  {firstConfig.enabled === false
                    ? "已停用"
                    : firstConfig.sync_status === "error"
                      ? "异常"
                      : "启用中"}
                </span>
              </div>
              <div className="mt-4 grid gap-3 text-sm text-slate-700 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Board</p>
                  <p className="mt-1 break-all font-medium">{firstConfig.board_id ?? "-"}</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">同步方向</p>
                  <p className="mt-1 font-medium">{firstConfig.sync_direction ?? "-"}</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">最近同步</p>
                  <p className="mt-1 font-medium">
                    {firstConfig.last_sync_at
                      ? new Date(firstConfig.last_sync_at).toLocaleString()
                      : "还没有"}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">映射数</p>
                  <p className="mt-1 font-medium">{Object.keys(firstConfig.field_mapping ?? {}).length}</p>
                </div>
              </div>
              {firstConfig.last_error ? (
                <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  最近失败原因：{firstConfig.last_error}
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">同步配置</h3>
            <div className="space-y-2">
              {(configsQuery.data ?? []).map((config) => (
                <div
                  key={config.id}
                  className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm"
                >
                  <div>
                    <p className="font-medium text-slate-900">{config.app_id}</p>
                    <p className="text-xs text-slate-500">
                      {config.bitable_table_id} / {config.sync_status}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/feishu-sync/${config.id}`}
                      className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
                    >
                      查看详情
                    </Link>
                    <button
                      className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white"
                      onClick={() => triggerMutation.mutate(config.id)}
                      type="button"
                    >
                      立即同步
                    </button>
                  </div>
                </div>
              ))}
              {(configsQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">还没有同步配置。</p>
              ) : null}
            </div>
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
            mapping={mapping}
            isSaving={updateMappingMutation.isPending}
            onSave={
              firstConfig
                ? async (nextMapping) => {
                    await updateMappingMutation.mutateAsync({
                      configId: firstConfig.id,
                      fieldMapping: nextMapping,
                    });
                  }
                : undefined
            }
          />
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">最近映射记录</h3>
            <div className="space-y-2">
              {(mappingsQuery.data ?? []).slice(0, 5).map((mappingItem) => (
                <div
                  key={mappingItem.id}
                  className={`rounded-lg px-3 py-2 text-sm ${
                    mappingItem.has_conflict
                      ? "border border-amber-200 bg-amber-50"
                      : "bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-900">
                        {mappingItem.task_title ?? mappingItem.feishu_record_id}
                      </p>
                      <p className="text-xs text-slate-500">{mappingItem.feishu_record_id}</p>
                    </div>
                    <div className="text-right">
                      {mappingItem.has_conflict ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                          有冲突
                        </span>
                      ) : (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                          正常
                        </span>
                      )}
                      <p className="mt-1 text-xs text-slate-500">{mappingItem.task_id}</p>
                    </div>
                  </div>
                  <div className="mt-2 grid gap-1 text-xs text-slate-500 md:grid-cols-3">
                    <p>
                      飞书更新时间：
                      {mappingItem.last_feishu_update
                        ? new Date(mappingItem.last_feishu_update).toLocaleString()
                        : "-"}
                    </p>
                    <p>
                      本地更新时间：
                      {mappingItem.last_mc_update
                        ? new Date(mappingItem.last_mc_update).toLocaleString()
                        : "-"}
                    </p>
                    <p>Hash：{mappingItem.sync_hash ?? "-"}</p>
                  </div>
                  {mappingItem.has_conflict ? (
                    <div className="mt-3 space-y-2 rounded-lg border border-amber-200 bg-white px-3 py-2">
                      <p className="text-xs font-medium text-amber-800">
                        冲突时间：
                        {mappingItem.conflict_at
                          ? new Date(mappingItem.conflict_at).toLocaleString()
                          : "-"}
                      </p>
                      <p className="text-xs text-amber-700">
                        {mappingItem.conflict_message ?? "本地任务和飞书记录都发生了变更。"}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                          disabled={
                            resolveConflictMutation.isPending || !firstConfig?.id
                          }
                          onClick={() => {
                            if (!firstConfig?.id) {
                              return;
                            }
                            resolveConflictMutation.mutate({
                              configId: firstConfig.id,
                              mappingId: mappingItem.id,
                              resolution: "keep_local",
                            });
                          }}
                        >
                          保留本地
                        </button>
                        <button
                          type="button"
                          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 disabled:opacity-50"
                          disabled={
                            resolveConflictMutation.isPending || !firstConfig?.id
                          }
                          onClick={() => {
                            if (!firstConfig?.id) {
                              return;
                            }
                            resolveConflictMutation.mutate({
                              configId: firstConfig.id,
                              mappingId: mappingItem.id,
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
              {(mappingsQuery.data ?? []).length === 0 ? (
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
