"use client";

const REQUIRED_MAPPING_TARGETS = [
  "title",
  "description",
  "priority",
  "status",
] as const;

type DiagnosticTone = "warning" | "error" | "info";

export type SyncDiagnostic = {
  title: string;
  message: string;
  tone: DiagnosticTone;
};

export function getFeishuSyncDiagnostics(lastError: string | null | undefined): SyncDiagnostic[] {
  const error = lastError?.trim();
  if (!error) {
    return [];
  }

  const normalized = error.toLowerCase();

  if (normalized.includes("403") || normalized.includes("forbidden")) {
    return [
      {
        title: "飞书权限不足",
        message: "当前应用对目标表或文档缺少读写权限。先检查 scope、应用授权和表格分享范围。",
        tone: "error",
      },
    ];
  }
  if (normalized.includes("tenant_access_token") || normalized.includes("invalid param")) {
    return [
      {
        title: "飞书应用凭据异常",
        message: "App ID 或 App Secret 可能不正确，或者应用配置还没在飞书开放平台生效。",
        tone: "error",
      },
    ];
  }
  if (normalized.includes("timed out") || normalized.includes("timeout")) {
    return [
      {
        title: "请求超时",
        message: "Mission Control 调用飞书接口超时。先检查网络连通性，再确认飞书 API 没有临时抖动。",
        tone: "warning",
      },
    ];
  }
  if (normalized.includes("connection") || normalized.includes("network")) {
    return [
      {
        title: "网络连接异常",
        message: "与飞书 API 的网络连接不稳定。建议先测外网访问，再重试同步。",
        tone: "warning",
      },
    ];
  }

  return [
    {
      title: "同步失败",
      message: error,
      tone: "error",
    },
  ];
}

export function getMissingMappingSuggestions(mapping: Record<string, string>): string[] {
  const configuredTargets = new Set(Object.values(mapping));
  return REQUIRED_MAPPING_TARGETS.filter((target) => !configuredTargets.has(target)).map((target) => {
    if (target === "title") {
      return "建议补上映射到 `title`，否则同步进来的任务标题容易退化成 `Untitled`。";
    }
    if (target === "description") {
      return "建议补上映射到 `description`，这样任务上下文不会只剩标题。";
    }
    if (target === "priority") {
      return "建议补上映射到 `priority`，便于在 Mission Control 里保留优先级语义。";
    }
    return "建议补上映射到 `status`，这样飞书和 Mission Control 的进度不会长期漂移。";
  });
}
