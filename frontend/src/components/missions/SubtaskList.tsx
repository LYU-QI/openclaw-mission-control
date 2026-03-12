"use client";

import { useState } from "react";

import { MissionStatusBadge } from "@/components/missions/MissionStatusBadge";

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

type Props = {
  subtasks: SubtaskItem[];
  onRedispatch?: (subtaskId: string) => Promise<void>;
};

export function SubtaskList({ subtasks, onRedispatch }: Props) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const running = subtasks.filter((item) => item.status === "running");
  const failed = subtasks.filter((item) => item.status === "failed");
  const pending = subtasks.filter((item) => item.status === "pending");
  const completed = subtasks.filter((item) => item.status === "completed");

  async function handleRedispatch(subtaskId: string) {
    if (!onRedispatch) {
      return;
    }
    setBusyId(subtaskId);
    try {
      await onRedispatch(subtaskId);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">子任务</h3>
        <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.2em] text-slate-400">
          <span>待执行 {pending.length}</span>
          <span>执行中 {running.length}</span>
          <span>失败 {failed.length}</span>
          <span>完成 {completed.length}</span>
        </div>
      </div>
      {failed.length > 0 ? (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          当前有 {failed.length} 条失败子任务，可直接在这里重新派发。
        </div>
      ) : null}
      <div className="space-y-2">
        {subtasks.map((subtask) => (
          <div
            key={subtask.id}
            className={`rounded-lg px-3 py-2 ${
              subtask.status === "failed"
                ? "bg-rose-50"
                : subtask.status === "running"
                  ? "bg-sky-50"
                  : subtask.status === "completed"
                    ? "bg-emerald-50"
                    : "bg-slate-50"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-900">{subtask.label}</p>
                {subtask.assigned_subagent_id ? (
                  <p className="mt-1 break-all text-[11px] text-slate-500">
                    Session：{subtask.assigned_subagent_id}
                  </p>
                ) : null}
              </div>
              <MissionStatusBadge status={subtask.status} />
            </div>
            <div className="mt-2 space-y-1">
              {subtask.expected_output ? (
                <p className="text-xs text-slate-500">{subtask.expected_output}</p>
              ) : null}
              {subtask.result_summary ? (
                <p className="text-xs text-slate-600">结果：{subtask.result_summary}</p>
              ) : null}
              {subtask.result_risk ? (
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
                  风险 {subtask.result_risk}
                </p>
              ) : null}
              {subtask.error_message ? (
                <p className="text-xs text-rose-700">失败原因：{subtask.error_message}</p>
              ) : null}
              {subtask.updated_at ? (
                <p className="text-[11px] text-slate-400">
                  更新时间 {new Date(subtask.updated_at).toLocaleString()}
                </p>
              ) : null}
            </div>
            {subtask.status === "failed" && onRedispatch ? (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => handleRedispatch(subtask.id)}
                  disabled={busyId === subtask.id}
                  className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {busyId === subtask.id ? "重新派发中..." : "重新派发"}
                </button>
              </div>
            ) : null}
          </div>
        ))}
        {subtasks.length === 0 ? (
          <p className="text-sm text-slate-500">当前还没有子任务。</p>
        ) : null}
      </div>
    </div>
  );
}
