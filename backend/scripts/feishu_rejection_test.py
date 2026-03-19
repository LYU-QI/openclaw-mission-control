
import asyncio
import sys
from pathlib import Path
from sqlmodel import select

# 设置路径
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

async def main():
    from app.db.session import async_session_maker
    from app.models.feishu_sync import FeishuSyncConfig
    from app.models.tasks import Task
    from app.models.missions import Mission, MissionSubtask
    from app.models.agents import Agent
    from app.models.approvals import Approval
    from app.models.boards import Board
    from app.services.feishu.sync_service import SyncService
    from app.services.feishu.client import FeishuClient
    from app.services.missions.orchestrator import MissionOrchestrator
    from app.services.missions.status_machine import MISSION_STATUS_PENDING_APPROVAL
    from app.core.secrets import decrypt_secret
    from app.core.time import utcnow
    from app.api.approvals import _apply_mission_state_from_approval

    async with async_session_maker() as session:
        # 1. 获取配置
        result = await session.exec(select(FeishuSyncConfig))
        config = result.first()
        if not config:
            print("❌ 数据库中未找到飞书同步配置。")
            return
        
        # 获取 Lead Agent 用于审核，获取/创建一个 Worker Agent 用于执行
        lead_agent = (await session.exec(select(Agent).where(Agent.board_id == config.board_id, Agent.is_board_lead == True))).first()
        worker_agent = (await session.exec(select(Agent).where(Agent.board_id == config.board_id, Agent.is_board_lead == False))).first()
        if not worker_agent:
            worker_agent = Agent(name="Test Worker Agent", board_id=config.board_id, is_board_lead=False)
            session.add(worker_agent)
            await session.flush()
            print(f"✅ 临时创建了执行智能体 (ID: {worker_agent.id})")
        
        app_secret = decrypt_secret(config.app_secret_encrypted)
        client = FeishuClient(config.app_id, app_secret)
        sync_service = SyncService(session, config)
        orchestrator = MissionOrchestrator(session)

        # ---------------------------------------------------------
        # 步骤 0: 创建飞书任务
        # ---------------------------------------------------------
        print("\n[步骤 0] 正在飞书多维表格中模拟【待打回】任务...")
        test_title = f"[Lead 打回测试] 异常代码审计任务 - {utcnow().strftime('%H:%M:%S')}"
        
        create_resp = client.create_bitable_record(
            config.bitable_app_token,
            config.bitable_table_id,
            {"文本": test_title}
        )
        record_id = create_resp.get("data", {}).get("record", {}).get("record_id")
        print(f"✅ 飞书记录已创建 (ID: {record_id})")

        # ---------------------------------------------------------
        # 步骤 1: 同步并进入 Review 状态
        # ---------------------------------------------------------
        print("\n[步骤 1] 正在同步飞书数据并将任务置为 'review'...")
        await asyncio.sleep(2) 
        await sync_service.pull_from_feishu()
        
        stmt = select(Task).where(Task.external_id == record_id)
        task = (await session.exec(stmt)).first()
        
        # 强制将任务设为 review 状态，模拟正常执行完毕等待审核
        task.status = "review"
        if lead_agent:
            task.assigned_agent_id = lead_agent.id
        session.add(task)
        await session.commit()
        await session.refresh(task)
        print(f"✅ 任务当前状态: {task.status}")

        # ---------------------------------------------------------
        # 步骤 2: 模拟执行完毕并触发 Review 阶段评论
        # ---------------------------------------------------------
        print("\n[步骤 2] 模拟任务执行完毕并触发 Review 阶段评论...")
        mission = await orchestrator.create_mission(
            task_id=task.id,
            board_id=task.board_id,
            agent_id=worker_agent.id,
            goal="模拟打回测试 Mission",
            approval_policy="post_review"
        )
        
        # 必须先 dispatch 才能 complete
        await orchestrator.dispatch_mission(mission.id)
        
        # 调用 complete_mission 触发 Review 评论逻辑
        await orchestrator.complete_mission(mission.id, result_summary="代码分析已完成，发现部分逻辑不严谨。")
        
        # 刷新以获取关联的 Approval (由 finish_mission 的 _ensure_pending_approval 生成)
        await session.refresh(mission)
        approval = await session.get(Approval, mission.approval_id)
        if not approval:
            # 兼容性处理，如果系统没生成，手动补一个带署名的
            approval = Approval(
                board_id=task.board_id,
                task_id=task.id,
                action_type="mission_result_review",
                status="pending",
                agent_id=lead_agent.id if lead_agent else None,
                confidence=1.0,
                payload={"mission_id": str(mission.id)}
            )
            session.add(approval)
            await session.flush()
            mission.approval_id = approval.id
            session.add(mission)
            await session.commit()
        session.add(mission)
        await session.commit()
        print(f"✅ 审批已创建 (ID: {approval.id})，已关联 Mission (ID: {mission.id})")

        # ---------------------------------------------------------
        # 步骤 3: 执行 Lead 打回 (Reject)
        # ---------------------------------------------------------
        print("\n[步骤 3] Lead 做出决策: 【不通过 (Reject)】")
        approval.status = "rejected"
        approval.payload = {
            "mission_id": str(mission.id),
            "reason": "代码逻辑不清晰，请重新审计。",
            "anomalies": ["Poor documentation", "Vague results"]
        }
        approval.resolved_at = utcnow()
        session.add(approval)
        await session.commit()
        
        # 触发核心打回逻辑
        board = await session.get(Board, task.board_id)
        await _apply_mission_state_from_approval(
            session=session,
            board=board,
            approval=approval
        )
        print("✅ 审批决策已处理。")

        # ---------------------------------------------------------
        # 步骤 4: 最终核查
        # ---------------------------------------------------------
        print("\n[步骤 4] 最终状态核查...")
        from app.models.activity_events import ActivityEvent
        await session.refresh(task)
        await session.refresh(mission)
        
        print(f"   -> 任务状态 (Task Status): {task.status}")
        print(f"   -> 任务委派对象 (Task Assignee ID): {task.assigned_agent_id}")
        print(f"   -> 任务下一步建议 (Next Action): {task.result_next_action}")
        print(f"   -> Mission 状态 (Mission Status): {mission.status}")

        # 验证委派是否恢复给 Worker Agent (而不是停留在 Lead 身上)
        delegation_ok = (task.assigned_agent_id == worker_agent.id)
        if delegation_ok:
            print(f"✅ 委派成功恢复给 Worker Agent (ID: {worker_agent.id})")
        else:
            print(f"❌ 委派恢复失败！当前委派人 ID: {task.assigned_agent_id}, 期待 Worker ID: {worker_agent.id}")
            if task.assigned_agent_id == lead_agent.id:
                 print("   !!! 任务仍然被委派给 Lead")
        
        # 验证评论是否生成
        stmt = select(ActivityEvent).where(
            ActivityEvent.task_id == task.id,
            ActivityEvent.event_type == "task.comment"
        ).order_by(ActivityEvent.created_at.desc())
        comment = (await session.exec(stmt)).first()
        
        if comment:
            print(f"   -> 查找到任务评论: {comment.message}")
        else:
            print("   -> ❌ 未找到关联的任务评论")

        # 验证是否生成了新的 Mission (自动重试)
        # 注意：由于后端是异步处理，此时 Mission 可能已经处于 pending, dispatched 或 running 状态
        stmt = select(Mission).where(
            Mission.task_id == task.id,
            Mission.status.in_(["pending", "dispatched", "running"])
        ).where(Mission.id != mission.id).order_by(Mission.created_at.desc())
        new_mission = (await session.exec(stmt)).first()
        
        if new_mission:
            print(f"   -> 查找到新创建的 Mission (ID: {new_mission.id}, Status: {new_mission.status})")
        else:
            print("   -> ❌ 未找到新创建的 Mission (自动重试可能未触发)")

        status_ok = task.status in ["inbox", "in_progress"]
        if status_ok and mission.status == "failed" and comment and delegation_ok and new_mission:
            print("\n🎉 测试成功：Lead 成功打回任务，委派已恢复，自动触发了重试 (New Mission)，并发表了评论。")
        else:
            print("\n❌ 测试异常：状态流转、委派恢复、自动重试或评论生成不符合预期。")

if __name__ == "__main__":
    asyncio.run(main())
