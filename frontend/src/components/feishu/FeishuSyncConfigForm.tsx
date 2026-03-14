"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Props = {
  onSubmit: (payload: {
    app_id: string;
    app_secret: string;
    bitable_app_token: string;
    bitable_table_id: string;
  }) => Promise<void>;
};

export function FeishuSyncConfigForm({ onSubmit }: Props) {
  const [appId, setAppId] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [appToken, setAppToken] = useState("");
  const [tableId, setTableId] = useState("");

  return (
    <form
      className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4"
      onSubmit={async (event) => {
        event.preventDefault();
        await onSubmit({
          app_id: appId.trim(),
          app_secret: appSecret.trim(),
          bitable_app_token: appToken.trim(),
          bitable_table_id: tableId.trim(),
        });
      }}
    >
      <h3 className="text-sm font-semibold text-slate-900">新建同步配置</h3>
      <Input value={appId} onChange={(e) => setAppId(e.target.value)} placeholder="Feishu App ID" />
      <Input
        value={appSecret}
        onChange={(e) => setAppSecret(e.target.value)}
        placeholder="Feishu App Secret"
      />
      <Input
        value={appToken}
        onChange={(e) => setAppToken(e.target.value)}
        placeholder="Bitable app token"
      />
      <Input
        value={tableId}
        onChange={(e) => setTableId(e.target.value)}
        placeholder="Bitable table id"
      />
      <Button type="submit">创建配置</Button>
    </form>
  );
}
