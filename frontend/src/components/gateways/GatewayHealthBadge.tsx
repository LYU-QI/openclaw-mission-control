"use client";

import { useCheckGatewayHealthApiV1GatewaysGatewayIdHealthGet } from "@/api/generated/gateways/gateways";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type GatewayHealthBadgeProps = {
  gatewayId: string;
};

export function GatewayHealthBadge({ gatewayId }: GatewayHealthBadgeProps) {
  const { data: rawHealth, isLoading, error } =
    useCheckGatewayHealthApiV1GatewaysGatewayIdHealthGet(gatewayId, {
      query: {
        refetchInterval: 15_000,
      },
    });

  if (isLoading) {
    return (
      <Badge variant="outline" className="text-slate-500 gap-1 font-normal">
        <Loader2 className="h-3 w-3 animate-spin" /> Checking
      </Badge>
    );
  }

  if (error || !rawHealth) {
    const errorMsg = (error as any)?.message || "Failed to fetch health";
    return (
      <TooltipProvider>
        <Tooltip delayDuration={300}>
          <TooltipTrigger asChild>
            <Badge variant="danger" className="gap-1 cursor-help">
              <XCircle className="h-3 w-3" /> Unknown Error
            </Badge>
          </TooltipTrigger>
          <TooltipContent className="max-w-[300px]">
            {errorMsg}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // Typecast to bypass gen types mismatch
  const health = rawHealth as any;

  // Evaluate the health object
  if (health.data?.last_error && !health.data?.session_active) {
    return (
      <TooltipProvider>
        <Tooltip delayDuration={300}>
          <TooltipTrigger asChild>
            <Badge variant="danger" className="gap-1 cursor-help">
              <AlertCircle className="h-3 w-3" /> Connection Failed
            </Badge>
          </TooltipTrigger>
          <TooltipContent className="max-w-[300px] whitespace-pre-wrap flex flex-col gap-1">
            <span className="font-semibold text-red-500">Error Details</span>
            <span>{health.data.last_error}</span>
            <div className="text-xs text-slate-400 mt-1">
              • HTTP: {health.data.http_reachable ? "OK" : "Fail"}<br />
              • RPC: {health.data.rpc_callable ? "OK" : "Fail"}<br />
              • Session: {health.data.session_active ? "OK" : "Fail"}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  if (!health.data?.agent_checked_in) {
    return (
      <TooltipProvider>
        <Tooltip delayDuration={300}>
          <TooltipTrigger asChild>
            <Badge variant="outline" className="gap-1 text-amber-600 border-amber-200 bg-amber-50 cursor-help">
              <AlertCircle className="h-3 w-3" /> Not Checked In
            </Badge>
          </TooltipTrigger>
          <TooltipContent className="max-w-[300px]">
            {health.data?.last_error || "Main agent has not checked in. Please check gateway logs or restart."}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <TooltipProvider>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <Badge variant="outline" className="gap-1 text-emerald-600 border-emerald-200 bg-emerald-50 cursor-help">
            <CheckCircle2 className="h-3 w-3" /> Healthy
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          Gateway is fully operational.
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
