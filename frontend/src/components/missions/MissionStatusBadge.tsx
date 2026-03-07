"use client";

import { cn } from "@/lib/utils";

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
      {status}
    </span>
  );
}

