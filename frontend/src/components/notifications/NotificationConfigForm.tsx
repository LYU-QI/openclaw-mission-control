"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Board = {
  id: string;
  name: string;
};

type Props = {
  boards: Board[];
  onSubmit: (payload: {
    name: string;
    board_id: string | null;
    channel_type: string;
    channel_config: { webhook_url: string; webhook_secret?: string };
  }) => Promise<void>;
};

export function NotificationConfigForm({ boards, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [boardId, setBoardId] = useState<string>("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  return (
    <form
      className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4"
      onSubmit={async (event) => {
        event.preventDefault();
        await onSubmit({
          name: name.trim(),
          board_id: boardId || null,
          channel_type: "feishu_bot",
          channel_config: {
            webhook_url: webhookUrl.trim(),
            webhook_secret: webhookSecret.trim() || undefined,
          },
        });
      }}
    >
      <h3 className="text-sm font-semibold text-slate-900">Create notification channel</h3>
      <Input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="渠道名称 (如: 开发群通知)"
      />
      <Select value={boardId} onValueChange={setBoardId}>
        <SelectTrigger>
          <SelectValue placeholder="选择绑定的看板 (可选)" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__none__">不绑定看板 (全局)</SelectItem>
          {boards.map((board) => (
            <SelectItem key={board.id} value={board.id}>
              {board.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        value={webhookUrl}
        onChange={(e) => setWebhookUrl(e.target.value)}
        placeholder="Feishu bot webhook URL"
      />
      <Input
        value={webhookSecret}
        onChange={(e) => setWebhookSecret(e.target.value)}
        placeholder="Feishu bot webhook secret (optional)"
      />
      <Button type="submit">Create</Button>
    </form>
  );
}

