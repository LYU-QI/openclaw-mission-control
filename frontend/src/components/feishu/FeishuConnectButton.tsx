"use client";

import { Button } from "@/components/ui/button";

export function FeishuConnectButton({
  onClick,
  disabled = false,
}: {
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <Button type="button" onClick={onClick} disabled={disabled}>
      Test Feishu Connection
    </Button>
  );
}

