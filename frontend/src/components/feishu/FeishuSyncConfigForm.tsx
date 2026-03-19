"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiGet } from "@/lib/mission-control-api";

type Board = {
  id: string;
  name: string;
};

type Props = {
  onSubmit: (payload: {
    app_id: string;
    app_secret: string;
    bitable_app_token: string;
    bitable_table_id: string;
    board_id?: string;
    auto_dispatch?: boolean;
  }) => Promise<void>;
};

export function FeishuSyncConfigForm({ onSubmit }: Props) {
  const [appId, setAppId] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [appToken, setAppToken] = useState("");
  const [tableId, setTableId] = useState("");
  const [boardId, setBoardId] = useState("");
  const [autoDispatch, setAutoDispatch] = useState(false);

  const boardsQuery = useQuery({
    queryKey: ["boards"],
    queryFn: async () => {
      const res = await apiGet<{ items: Board[] }>("/api/v1/boards");
      return res.items;
    },
  });

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
          board_id: boardId || undefined,
          auto_dispatch: autoDispatch,
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
      <Select value={boardId} onValueChange={setBoardId}>
        <SelectTrigger>
          <SelectValue placeholder="选择默认看板（可选）" />
        </SelectTrigger>
        <SelectContent>
          {boardsQuery.data?.map((board) => (
            <SelectItem key={board.id} value={board.id}>
              {board.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={autoDispatch}
          onChange={(e) => setAutoDispatch(e.target.checked)}
          className="h-4 w-4 rounded border-slate-300"
        />
        同步后自动创建并下发 Mission
      </label>
      <Button type="submit">创建配置</Button>
    </form>
  );
}
