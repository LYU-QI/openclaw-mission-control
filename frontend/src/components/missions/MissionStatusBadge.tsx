"use client";

import { cn } from "@/lib/utils";

const statusLabelMap: Record<string, string> = {
  pending: "待处理",
  dispatched: "已派发",
  running: "执行中",
  aggregating: "聚合中",
  completed: "已完成",
  failed: "失败",
  pending_approval: "待审批",
  cancelled: "已取消",
  inbox: "收件箱",
  in_progress: "进行中",
  review: "评审中",
  done: "已完成",
};

export function MissionStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-1 text-xs font-semibold",
        status === "completed" && "bg-emerald-100 text-emerald-800",
        status === "failed" && "bg-rose-100 text-rose-800",
        status === "running" && "bg-sky-100 text-sky-800",
        status !== "completed" &&
          status !== "failed" &&
          status !== "running" &&
          "bg-slate-100 text-slate-700",
      )}
    >
      {statusLabelMap[status] ?? status}
    </span>
  );
}
