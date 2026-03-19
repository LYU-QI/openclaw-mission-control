"use client";

import { useEffect, useState } from "react";

type BoardMappingRow = {
  feishu_board_name: string;
  mc_board_id: string;
};

type Props = {
  boardMapping: Record<string, string>;
  boards: { id: string; name: string }[];
  onSave?: (mapping: Record<string, string>) => Promise<void>;
  isSaving?: boolean;
};

function toRows(mapping: Record<string, string>): BoardMappingRow[] {
  return Object.entries(mapping).map(([feishu_board_name, mc_board_id]) => ({
    feishu_board_name,
    mc_board_id,
  }));
}

export function BoardMappingEditor({ boardMapping, boards, onSave, isSaving = false }: Props) {
  const [rows, setRows] = useState<BoardMappingRow[]>(() => toRows(boardMapping));

  useEffect(() => {
    setRows(toRows(boardMapping));
  }, [boardMapping]);

  const hasRows = rows.length > 0;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">看板映射</h3>
          <p className="mt-1 text-xs text-slate-500">
            将飞书表格中的看板字段值映射到 MC 看板
          </p>
        </div>
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
          onClick={() => {
            setRows((current) => [...current, { feishu_board_name: "", mc_board_id: "" }]);
          }}
        >
          添加映射
        </button>
      </div>
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div
            key={`${index}-${row.feishu_board_name}-${row.mc_board_id}`}
            className="grid gap-2 rounded-lg bg-slate-50 px-3 py-3 md:grid-cols-[1fr_1fr_auto]"
          >
            <input
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-0"
              placeholder="飞书看板名称"
              value={row.feishu_board_name}
              onChange={(event) => {
                const value = event.target.value;
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, feishu_board_name: value } : item,
                  ),
                );
              }}
            />
            <select
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-0"
              value={row.mc_board_id}
              onChange={(event) => {
                const value = event.target.value;
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, mc_board_id: value } : item,
                  ),
                );
              }}
            >
              <option value="">选择 MC 看板</option>
              {boards.map((board) => (
                <option key={board.id} value={board.id}>
                  {board.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700"
              onClick={() => {
                setRows((current) => current.filter((_, itemIndex) => itemIndex !== index));
              }}
            >
              删除
            </button>
          </div>
        ))}
        {!hasRows ? (
          <p className="text-sm text-slate-500">
            还没有定义看板映射，同步的任务将使用默认看板。
          </p>
        ) : null}
      </div>
      {onSave ? (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            disabled={isSaving}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={async () => {
              const nextMapping = rows.reduce<Record<string, string>>((acc, row) => {
                const feishu_name = row.feishu_board_name.trim();
                const mc_board_id = row.mc_board_id.trim();
                if (!feishu_name || !mc_board_id) {
                  return acc;
                }
                acc[feishu_name] = mc_board_id;
                return acc;
              }, {});
              await onSave(nextMapping);
            }}
          >
            {isSaving ? "保存中..." : "保存看板映射"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
