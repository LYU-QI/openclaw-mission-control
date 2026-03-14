"use client";

import { MissionStatusBadge } from "@/components/missions/MissionStatusBadge";

type EvidenceStats = {
  total?: number;
  completed?: number;
  pending?: number;
  failed?: number;
  high_risk?: number;
};

type Props = {
  goal: string;
  status: string;
  approvalPolicy?: string | null;
  approvalId?: string | null;
  summary?: string | null;
  risk?: string | null;
  nextAction?: string | null;
  evidenceStats?: EvidenceStats | null;
  anomaliesCount?: number;
  errorMessage?: string | null;
  updatedAt?: string | null;
};

const approvalPolicyLabels: Record<string, string> = {
  auto: "自动收口",
  pre_approve: "派发前审批",
  post_review: "结果复核审批",
};

const missionStatusNotes: Record<string, string> = {
  pending: "Mission 已创建，等待派发。",
  dispatched: "Mission 已下发，等待执行引擎开始处理。",
  running: "Mission 正在执行或等待子任务回写。",
  aggregating: "所有子任务已进入终态，系统正在聚合结果。",
  pending_approval: "Mission 已被审批门拦住，等待人工决策。",
  completed: "Mission 已完成，可以继续回写或关闭任务。",
  failed: "Mission 已失败，需要查看失败原因或重新派发。",
  cancelled: "Mission 已取消，不会继续推进。",
};

function approvalStateLabel(status: string, approvalId?: string | null): string {
  if (status === "pending_approval") {
    return "待人工审批";
  }
  if (approvalId) {
    return "已有审批记录";
  }
  return "当前无需审批";
}

export function MissionDetailPanel({
  goal,
  status,
  approvalPolicy,
  approvalId,
  summary,
  risk,
  nextAction,
  evidenceStats,
  anomaliesCount = 0,
  errorMessage,
  updatedAt,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-900">{goal}</h2>
        <MissionStatusBadge status={status} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>每 5 秒自动刷新</span>
        <span>
          最近更新时间：
          {updatedAt ? new Date(updatedAt).toLocaleString() : "-"}
        </span>
      </div>
      <p className="mt-3 text-sm text-slate-600">{missionStatusNotes[status] ?? "Mission 状态未知。"}</p>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">审批策略</p>
          <p className="mt-1 text-sm font-medium text-slate-900">
            {approvalPolicy ? approvalPolicyLabels[approvalPolicy] ?? approvalPolicy : "-"}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">审批状态</p>
          <p className="mt-1 text-sm font-medium text-slate-900">
            {approvalStateLabel(status, approvalId)}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">审批单</p>
          <p className="mt-1 break-all text-sm font-medium text-slate-900">
            {approvalId ?? "当前无审批单"}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">异常数量</p>
          <p className="mt-1 text-sm font-medium text-slate-900">{anomaliesCount}</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">高风险子任务</p>
          <p className="mt-1 text-sm font-medium text-slate-900">{evidenceStats?.high_risk ?? 0}</p>
        </div>
      </div>
      {summary ? <p className="mt-3 text-sm text-slate-700">{summary}</p> : null}
      {(risk || nextAction) && (
        <div className="mt-3 grid gap-2 text-sm text-slate-600 md:grid-cols-2">
          <p>风险：{risk ?? "-"}</p>
          <p>下一步：{nextAction ?? "-"}</p>
        </div>
      )}
      {errorMessage ? (
        <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          失败原因：{errorMessage}
        </div>
      ) : null}
      {evidenceStats ? (
        <div className="mt-4 grid gap-2 text-sm text-slate-600 md:grid-cols-4">
          <p>总子任务：{evidenceStats.total ?? 0}</p>
          <p>已完成：{evidenceStats.completed ?? 0}</p>
          <p>待处理：{evidenceStats.pending ?? 0}</p>
          <p>失败：{evidenceStats.failed ?? 0}</p>
        </div>
      ) : null}
    </div>
  );
}
