import { describe, expect, it } from "vitest";

import {
  getFeishuSyncDiagnostics,
  getMissingMappingSuggestions,
} from "@/lib/feishu-sync-diagnostics";

describe("feishu-sync-diagnostics", () => {
  it("maps forbidden errors to permission guidance", () => {
    expect(getFeishuSyncDiagnostics("HTTP 403 Forbidden")).toEqual([
      expect.objectContaining({
        title: "飞书权限不足",
        tone: "error",
      }),
    ]);
  });

  it("maps token errors to credential guidance", () => {
    expect(getFeishuSyncDiagnostics("Failed to get tenant_access_token: invalid param")).toEqual([
      expect.objectContaining({
        title: "飞书应用凭据异常",
      }),
    ]);
  });

  it("returns missing mapping hints for core fields", () => {
    expect(getMissingMappingSuggestions({ "任务名称": "title" })).toEqual([
      "建议补上映射到 `description`，这样任务上下文不会只剩标题。",
      "建议补上映射到 `priority`，便于在 Mission Control 里保留优先级语义。",
      "建议补上映射到 `status`，这样飞书和 Mission Control 的进度不会长期漂移。",
    ]);
  });
});
