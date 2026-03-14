"use client";

export const dynamic = "force-dynamic";

import { useCallback, useMemo, useState } from "react";

import { SignedIn, SignedOut, SignInButton, useAuth } from "@/auth/clerk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiError } from "@/api/mutator";
import {
  useCreateApprovalApiV1BoardsBoardIdApprovalsPost,
  listApprovalsApiV1BoardsBoardIdApprovalsGet,
  updateApprovalApiV1BoardsBoardIdApprovalsApprovalIdPatch,
} from "@/api/generated/approvals/approvals";
import { useListBoardsApiV1BoardsGet } from "@/api/generated/boards/boards";
import type { ApprovalRead, BoardRead, TaskRead } from "@/api/generated/model";
import {
  getListTasksApiV1BoardsBoardIdTasksGetQueryKey,
  useListTasksApiV1BoardsBoardIdTasksGet,
} from "@/api/generated/tasks/tasks";
import { BoardApprovalsPanel } from "@/components/BoardApprovalsPanel";
import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type GlobalApprovalsData = {
  approvals: ApprovalRead[];
  warnings: string[];
};

function GlobalApprovalsInner() {
  const { isSignedIn } = useAuth();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedBoardId, setSelectedBoardId] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [leadReasoning, setLeadReasoning] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const boardsQuery = useListBoardsApiV1BoardsGet(undefined, {
    query: {
      enabled: Boolean(isSignedIn),
      refetchInterval: 30_000,
      refetchOnMount: "always",
      retry: false,
    },
    request: { cache: "no-store" },
  });

  const boards = useMemo(() => {
    if (boardsQuery.data?.status !== 200) return [];
    return boardsQuery.data.data.items ?? [];
  }, [boardsQuery.data]);

  const boardLabelById = useMemo(() => {
    const entries = boards.map((board: BoardRead) => [board.id, board.name]);
    return Object.fromEntries(entries) as Record<string, string>;
  }, [boards]);

  const boardIdsKey = useMemo(() => {
    const ids = boards.map((board) => board.id);
    ids.sort();
    return ids.join(",");
  }, [boards]);

  const approvalsKey = useMemo(
    () => ["approvals", "global", boardIdsKey] as const,
    [boardIdsKey],
  );

  const approvalsQuery = useQuery<GlobalApprovalsData, ApiError>({
    queryKey: approvalsKey,
    enabled: Boolean(isSignedIn && boards.length > 0),
    refetchInterval: 15_000,
    refetchOnMount: "always",
    retry: false,
    queryFn: async () => {
      const results = await Promise.allSettled(
        boards.map(async (board) => {
          const response = await listApprovalsApiV1BoardsBoardIdApprovalsGet(
            board.id,
            { limit: 200 },
            { cache: "no-store" },
          );
          if (response.status !== 200) {
            throw new Error(
              `Failed to load approvals for ${board.name} (status ${response.status}).`,
            );
          }
          return { boardId: board.id, approvals: response.data.items ?? [] };
        }),
      );

      const approvals: ApprovalRead[] = [];
      const warnings: string[] = [];

      for (const result of results) {
        if (result.status === "fulfilled") {
          approvals.push(...result.value.approvals);
        } else {
          warnings.push(result.reason?.message ?? "Unable to load approvals.");
        }
      }

      return { approvals, warnings };
    },
  });

  const effectiveBoardId = selectedBoardId || boards[0]?.id || "";

  const tasksQuery = useListTasksApiV1BoardsBoardIdTasksGet(
    effectiveBoardId,
    { limit: 200 },
    {
      query: {
        enabled: Boolean(isSignedIn && effectiveBoardId),
        refetchOnMount: "always",
        retry: false,
      },
      request: { cache: "no-store" },
    },
  );

  const tasks = useMemo(() => {
    if (tasksQuery.data?.status !== 200) return [];
    return (tasksQuery.data.data.items ?? []).filter(
      (task: TaskRead) => task.status !== "done",
    );
  }, [tasksQuery.data]);

  const effectiveTaskId = useMemo(() => {
    if (tasks.length === 0) return "";
    const hasSelectedTask = tasks.some((task) => task.id === selectedTaskId);
    return hasSelectedTask ? selectedTaskId : (tasks[0]?.id ?? "");
  }, [selectedTaskId, tasks]);

  const updateApprovalMutation = useMutation<
    Awaited<
      ReturnType<
        typeof updateApprovalApiV1BoardsBoardIdApprovalsApprovalIdPatch
      >
    >,
    ApiError,
    { boardId: string; approvalId: string; status: "approved" | "rejected" }
  >({
    mutationFn: ({ boardId, approvalId, status }) =>
      updateApprovalApiV1BoardsBoardIdApprovalsApprovalIdPatch(
        boardId,
        approvalId,
        { status },
        { cache: "no-store" },
      ),
  });

  const createApprovalMutation =
    useCreateApprovalApiV1BoardsBoardIdApprovalsPost({
      request: { cache: "no-store" },
    });

  const approvals = useMemo(
    () => approvalsQuery.data?.approvals ?? [],
    [approvalsQuery.data],
  );
  const warnings = useMemo(
    () => approvalsQuery.data?.warnings ?? [],
    [approvalsQuery.data],
  );
  const errorText = approvalsQuery.error?.message ?? null;

  const handleDecision = useCallback(
    (approvalId: string, status: "approved" | "rejected") => {
      const approval = approvals.find((item) => item.id === approvalId);
      const boardId = approval?.board_id;
      if (!boardId) return;

      updateApprovalMutation.mutate(
        { boardId, approvalId, status },
        {
          onSuccess: (result) => {
            if (result.status !== 200) return;
            queryClient.setQueryData<GlobalApprovalsData>(
              approvalsKey,
              (prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  approvals: prev.approvals.map((item) =>
                    item.id === approvalId ? result.data : item,
                  ),
                };
              },
            );
          },
          onSettled: () => {
            queryClient.invalidateQueries({ queryKey: approvalsKey });
          },
        },
      );
    },
    [approvals, approvalsKey, queryClient, updateApprovalMutation],
  );

  const combinedError = useMemo(() => {
    const parts: string[] = [];
    if (errorText) parts.push(errorText);
    if (warnings.length > 0) parts.push(warnings.join(" "));
    return parts.length > 0 ? parts.join(" ") : null;
  }, [errorText, warnings]);

  const isCreateDisabled =
    createApprovalMutation.isPending ||
    !effectiveBoardId ||
    !effectiveTaskId ||
    !leadReasoning.trim();

  const resetCreateForm = useCallback(() => {
    setSelectedBoardId("");
    setSelectedTaskId("");
    setLeadReasoning("");
    setCreateError(null);
  }, []);

  const handleCreateApproval = useCallback(() => {
    const trimmedReasoning = leadReasoning.trim();
    if (!effectiveBoardId || !effectiveTaskId || !trimmedReasoning) {
      setCreateError("Board, task, and review reason are required.");
      return;
    }

    setCreateError(null);
    createApprovalMutation.mutate(
      {
        boardId: effectiveBoardId,
        data: {
          action_type: "mission_result_review",
          confidence: 100,
          lead_reasoning: trimmedReasoning,
          task_id: effectiveTaskId,
        },
      },
      {
        onSuccess: (result) => {
          if (result.status !== 200) {
            setCreateError("Unable to create approval.");
            return;
          }

          setCreateOpen(false);
          resetCreateForm();
          void queryClient.invalidateQueries({ queryKey: approvalsKey });
          void queryClient.invalidateQueries({
            queryKey: getListTasksApiV1BoardsBoardIdTasksGetQueryKey(
              effectiveBoardId,
              { limit: 200 },
            ),
          });
        },
        onError: (error) => {
          setCreateError((error as Error).message ?? "Unable to create approval.");
        },
      },
    );
  }, [
    approvalsKey,
    createApprovalMutation,
    effectiveBoardId,
    effectiveTaskId,
    leadReasoning,
    queryClient,
    resetCreateForm,
  ]);

  const handleDialogOpenChange = useCallback(
    (open: boolean) => {
      setCreateOpen(open);
      if (!open) {
        resetCreateForm();
      }
    },
    [resetCreateForm],
  );

  return (
    <main className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="p-6">
        <div className="mb-4 flex items-center justify-end">
          <Dialog open={createOpen} onOpenChange={handleDialogOpenChange}>
            <DialogTrigger asChild>
              <Button>Create approval</Button>
            </DialogTrigger>
            <DialogContent aria-label="Create approval">
              <DialogHeader>
                <DialogTitle>Create approval</DialogTitle>
                <DialogDescription>
                  Link a task to a new approval request so a lead can review it
                  and move it toward done.
                </DialogDescription>
              </DialogHeader>

              <div className="mt-4 space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-wide text-muted">
                    Board
                  </label>
                  <Select
                    value={effectiveBoardId}
                    onValueChange={(value) => {
                      setSelectedBoardId(value);
                      setSelectedTaskId("");
                      setCreateError(null);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a board" />
                    </SelectTrigger>
                    <SelectContent>
                      {boards.map((board) => (
                        <SelectItem key={board.id} value={board.id}>
                          {board.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-wide text-muted">
                    Task
                  </label>
                  <Select
                    value={effectiveTaskId}
                    onValueChange={(value) => {
                      setSelectedTaskId(value);
                      setCreateError(null);
                    }}
                    disabled={!effectiveBoardId || tasksQuery.isLoading}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={
                          effectiveBoardId
                            ? "Select a task"
                            : "Select a board first"
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {tasks.map((task) => (
                        <SelectItem key={task.id} value={task.id}>
                          {task.title} ({task.status ?? "inbox"})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {effectiveBoardId && !tasksQuery.isLoading && tasks.length === 0 ? (
                    <p className="text-sm text-muted">
                      No open tasks available on this board.
                    </p>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <label
                    htmlFor="approval-lead-reasoning"
                    className="text-xs font-semibold uppercase tracking-wide text-muted"
                  >
                    Review reason
                  </label>
                  <Textarea
                    id="approval-lead-reasoning"
                    placeholder="This task is ready for final review-to-done approval."
                    value={leadReasoning}
                    onChange={(event) => setLeadReasoning(event.target.value)}
                  />
                </div>

                {createError ? (
                  <p className="text-sm text-rose-500">{createError}</p>
                ) : null}
              </div>

              <DialogFooter className="mt-6">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setCreateOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={handleCreateApproval}
                  disabled={isCreateDisabled}
                >
                  {createApprovalMutation.isPending
                    ? "Creating..."
                    : "Create approval"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
        <div className="h-[calc(100vh-160px)] min-h-[520px]">
          <BoardApprovalsPanel
            boardId="global"
            approvals={approvals}
            isLoading={boardsQuery.isLoading || approvalsQuery.isLoading}
            error={combinedError}
            onDecision={handleDecision}
            scrollable
            boardLabelById={boardLabelById}
          />
        </div>
      </div>
    </main>
  );
}

export default function GlobalApprovalsPage() {
  return (
    <DashboardShell>
      <SignedOut>
        <div className="flex h-full flex-col items-center justify-center gap-4 rounded-2xl surface-panel p-10 text-center">
          <p className="text-sm text-muted">Sign in to view approvals.</p>
          <SignInButton
            mode="modal"
            forceRedirectUrl="/approvals"
            signUpForceRedirectUrl="/approvals"
          >
            <Button>Sign in</Button>
          </SignInButton>
        </div>
      </SignedOut>
      <SignedIn>
        <DashboardSidebar />
        <GlobalApprovalsInner />
      </SignedIn>
    </DashboardShell>
  );
}
