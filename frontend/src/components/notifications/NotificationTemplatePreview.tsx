import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

type PreviewTemplate = {
  id: string;
  label: string;
  title: string;
  templateColor: "blue" | "green" | "red" | "orange";
  content: string;
  errorMsg?: string;
};

const DEMO_TEMPLATES: PreviewTemplate[] = [
  {
    id: "created",
    label: "任务已创建",
    title: "📋 新任务已创建",
    templateColor: "blue",
    content: "**Mission**: `test-mission-001`\n**状态**: pending\n**风险**: low",
  },
  {
    id: "started",
    label: "任务执行中",
    title: "⚡ 任务开始执行",
    templateColor: "blue",
    content: "**Mission**: `test-mission-001`\n**状态**: in_progress\n**下一步**: Gathering details...",
  },
  {
    id: "completed",
    label: "任务已完成",
    title: "✅ 任务执行完成",
    templateColor: "green",
    content: "**Mission**: `test-mission-001`\n**状态**: completed",
  },
  {
    id: "failed",
    label: "任务失败",
    title: "❌ 任务执行失败",
    templateColor: "red",
    content: "**Mission**: `test-mission-001`\n**状态**: failed",
    errorMsg: "Connection timeout after 30s. Subtask 2 failed to fetch remote repository.",
  },
  {
    id: "approval",
    label: "请求人工审批",
    title: "⚠️ 需要人工审批",
    templateColor: "orange",
    content: "**Mission**: `test-mission-001`\n**Approval**: `appr-999`\n**状态**: pending_approval",
  },
];

const colorMap = {
  blue: "bg-blue-500",
  green: "bg-emerald-500",
  red: "bg-rose-500",
  orange: "bg-amber-500",
};

export function NotificationTemplatePreview() {
  const [activeId, setActiveId] = useState<string>("failed");
  const activeTemplate = DEMO_TEMPLATES.find((t) => t.id === activeId) ?? DEMO_TEMPLATES[0];

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          预览卡片消息模板
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>飞书卡片消息预览</DialogTitle>
        </DialogHeader>
        <div className="mt-4 flex flex-col gap-6">
          {/* Template Selector */}
          <div className="flex flex-wrap gap-2">
            {DEMO_TEMPLATES.map((tmpl) => (
              <button
                key={tmpl.id}
                onClick={() => setActiveId(tmpl.id)}
                className={`rounded border px-3 py-1 text-xs transition-colors ${
                  activeId === tmpl.id
                    ? "border-slate-800 bg-slate-800 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                {tmpl.label}
              </button>
            ))}
          </div>

          {/* Feishu Card Mock */}
          <div className="flex justify-center bg-slate-100 p-6 rounded-lg">
            <div className="w-full max-w-[360px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              {/* Card Header */}
              <div className={`${colorMap[activeTemplate.templateColor]} px-4 py-3 text-white`}>
                <div className="font-semibold">{activeTemplate.title}</div>
              </div>
              {/* Card Body */}
              <div className="space-y-3 p-4 text-sm text-slate-800">
                <div className="whitespace-pre-wrap leading-relaxed">
                  Mission event notification preview.
                </div>
                <div className="whitespace-pre-wrap rounded bg-slate-50 p-2 font-mono text-[13px] leading-relaxed text-slate-600">
                  {activeTemplate.content}
                </div>
                {activeTemplate.errorMsg && (
                  <div className="mt-2 rounded bg-rose-50 p-3 text-rose-800">
                    <div className="font-semibold mb-1">❌ 错误详情:</div>
                    <div className="text-xs whitespace-pre-wrap">{activeTemplate.errorMsg}</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
