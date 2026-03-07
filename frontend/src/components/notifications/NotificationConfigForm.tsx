"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Props = {
  onSubmit: (payload: {
    channel_type: string;
    channel_config: { webhook_url: string };
  }) => Promise<void>;
};

export function NotificationConfigForm({ onSubmit }: Props) {
  const [webhookUrl, setWebhookUrl] = useState("");

  return (
    <form
      className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4"
      onSubmit={async (event) => {
        event.preventDefault();
        await onSubmit({
          channel_type: "feishu_bot",
          channel_config: { webhook_url: webhookUrl.trim() },
        });
      }}
    >
      <h3 className="text-sm font-semibold text-slate-900">Create notification channel</h3>
      <Input
        value={webhookUrl}
        onChange={(e) => setWebhookUrl(e.target.value)}
        placeholder="Feishu bot webhook URL"
      />
      <Button type="submit">Create</Button>
    </form>
  );
}

