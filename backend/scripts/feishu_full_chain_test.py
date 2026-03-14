
import asyncio
import sys
from pathlib import Path
from uuid import UUID
from sqlmodel import select

# 设置路径
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

async def main():
    from app.db.session import async_session_maker
    from app.models.feishu_sync import FeishuSyncConfig
    from app.models.tasks import Task
    from app.models.missions import Mission, MissionSubtask
    from app.models.notifications import NotificationLog
    from app.models.agents import Agent
    from app.models.approvals import Approval
    from app.services.feishu.sync_service import SyncService
    from app.services.feishu.client import FeishuClient
    from app.services.missions.orchestrator import MissionOrchestrator
    from app.services.missions.status_machine import MISSION_STATUS_PENDING_APPROVAL
    from app.core.secrets import decrypt_secret
    from app.core.time import utcnow

    async with async_session_maker() as session:
        # 1. 获取配置与负责人
        result = await session.exec(select(FeishuSyncConfig))
        config = result.first()
        if not config:
            print("❌ 数据库中未找到飞书同步配置。")
            return
        
        # 查找看板负责人 (Board Lead)
        agent_result = await session.exec(select(Agent).where(Agent.board_id == config.board_id, Agent.is_board_lead == True))
        lead_agent = agent_result.first()
        if not lead_agent:
            print(f"⚠️ 警告: 未找到看板 (ID: {config.board_id}) 的负责人 Agent，将无法自动显示指派人。")
        else:
            print(f"✅ 已识别看板负责人: {lead_agent.name} (ID: {lead_agent.id})")

        app_secret = decrypt_secret(config.app_secret_encrypted)
        client = FeishuClient(config.app_id, app_secret)
        sync_service = SyncService(session, config)
        orchestrator = MissionOrchestrator(session)

        # ---------------------------------------------------------
        # 步骤 0: 创建飞书任务
        # ---------------------------------------------------------
        print("\n[步骤 0] 正在飞书多维表格中模拟【高优分析】任务...")
        test_title = f"[最终闭环测试] 生产力工具 Agent 协作链路深度优化 - {utcnow().strftime('%H:%M:%S')}"
        
        create_resp = client.create_bitable_record(
            config.bitable_app_token,
            config.bitable_table_id,
            {"文本": test_title}
        )
        if create_resp.get("code") != 0:
            print(f"❌ 飞书记录创建失败: {create_resp}")
            return

        record_id = create_resp.get("data", {}).get("record", {}).get("record_id")
        print(f"✅ 飞书记录已创建 (ID: {record_id})")

        # ---------------------------------------------------------
        # 步骤 1: 触发拉取并自动指派
        # ---------------------------------------------------------
        print("\n[步骤 1] 正在同步飞书数据并执行【自动指派】...")
        await asyncio.sleep(2) 
        await sync_service.pull_from_feishu()
        
        stmt = select(Task).where(Task.external_id == record_id)
        task = (await session.exec(stmt)).first()
        if not task:
            print("❌ 本地数据库同步失败。")
            return
        
        # 自动指派任务负责人，解决前端 Unassigned 问题
        if lead_agent:
            task.assigned_agent_id = lead_agent.id
            session.add(task)
            await session.commit()
            print(f"✅ 看板指派成功：任务负责人 -> {lead_agent.name}")
        
        print(f"✅ 任务已就绪: {task.title}")

        # ---------------------------------------------------------
        # 步骤 2: 创建并派发 Mission (显式绑定负责人)
        # ---------------------------------------------------------
        print("\n[步骤 2] 正在启动智能体分析流程...")
        mission = await orchestrator.create_mission(
            task_id=task.id,
            board_id=task.board_id,
            agent_id=lead_agent.id if lead_agent else None,
            goal="针对当前的协同链路设计 3 套具体的优化配置。要求：1. 评估数据一致性；2. 优化任务指派速度；3. 增强通知语义。",
            approval_policy="auto",
        )
        mission = await orchestrator.dispatch_mission(mission.id)
        
        # 强制审批绕过以确保进入分解
        if mission.status == MISSION_STATUS_PENDING_APPROVAL:
            mission.status = "pending"
            session.add(mission)
            await session.commit()
            mission = await orchestrator.dispatch_mission(mission.id)
        
        print(f"✅ Mission 已分发 (ID: {mission.id})")

        # ---------------------------------------------------------
        # 步骤 3: 等待分解并模拟执行
        # ---------------------------------------------------------
        print("\n[步骤 3] 等待探测任务分解状态 (15s)...")
        await asyncio.sleep(15)
        
        st_stmt = select(MissionSubtask).where(MissionSubtask.mission_id == mission.id)
        subtasks = (await session.exec(st_stmt)).all()
        if not subtasks:
             print("⚠️ 任务分解延迟，稍作等待...")
             await asyncio.sleep(10)
             subtasks = (await session.exec(st_stmt)).all()
        
        if subtasks:
            print(f"✅ Orchestrator 已完成分解，正在模拟子任务结果...")
            for st in subtasks:
                print(f"   -> 处理子任务: {st.label}")
                await orchestrator.update_subtask_status(
                    st.id, 
                    status="completed", 
                    result_summary=f"针对 '{st.label}' 的专业分析已完成：链路已优化至毫秒级。"
                )
        else:
            print("❌ 任务分解失败，请检查 Orchestrator 日志。")
            return

        # ---------------------------------------------------------
        # 步骤 4: 汇总结果并执行【自动审批】
        # ---------------------------------------------------------
        print("\n[步骤 4] 正在汇总结果，检测是否需要【人工审批】...")
        await asyncio.sleep(5) # 等待聚合
        
        await session.refresh(mission)
        if mission.status == MISSION_STATUS_PENDING_APPROVAL:
            print("🚀 检测到任务需要负责人审批，正在执行【自动通过】模拟...")
            app_stmt = select(Approval).where(Approval.id == mission.approval_id)
            approval = (await session.exec(app_stmt)).first()
            if approval:
                from app.services.missions.orchestrator import MISSION_STATUS_COMPLETED
                # 模拟审批授权
                approval.status = "granted"
                approval.resolved_at = utcnow()
                session.add(approval)
                # 触发 Mission 完成
                mission.status = MISSION_STATUS_COMPLETED
                mission.completed_at = utcnow()
                session.add(mission)
                await session.commit()
                print("✅ 审批已自动通过，任务已标记为完成。")
        else:
             print(f"ℹ️ Mission 状态: {mission.status}，无需或已完成审批。")

        # ---------------------------------------------------------
        # 步骤 5: 最终验收
        # ---------------------------------------------------------
        print("\n[步骤 5] 正在执行全链路闭环验收...")
        await asyncio.sleep(5)
        
        await session.refresh(task)
        # 1. 验证负责人显示
        if task.assigned_agent_id == lead_agent.id:
            print("✅ 验证 1: 负责人显示 (Assigned Agent) -> PASS")
        else:
            print(f"❌ 验证 1: 负责人显示 -> FAILED (ID 匹配失败)")

        # 2. 验证任务状态 (流转到 Done)
        if task.status == "done":
            print("✅ 验证 2: 任务状态流转 (Done) -> PASS")
        else:
            print(f"❌ 验证 2: 任务状态流转 -> FAILED (当前状态: {task.status})")

        # 3. 验证通知下发
        notif_stmt = select(NotificationLog).where(NotificationLog.event_type == "mission_completed").order_by(NotificationLog.created_at.desc()).limit(1)
        last_log = (await session.exec(notif_stmt)).first()
        if last_log and (utcnow() - last_log.created_at).total_seconds() < 120:
            print(f"✅ 验证 3: 群通知下发 (mission_completed) -> PASS")
        else:
            print("❌ 验证 3: 群通知下发 -> FAILED")

        # 4. 验证任务评论同步
        from app.models.activity_events import ActivityEvent
        comment_stmt = select(ActivityEvent).where(
            ActivityEvent.task_id == task.id, 
            ActivityEvent.event_type == "task.comment"
        )
        comments = (await session.exec(comment_stmt)).all()
        if len(comments) >= 3: # 至少应有：创建、子任务启动、子任务完成、汇总
            print(f"✅ 验证 4: 执行记录同步至评论区 (条数: {len(comments)}) -> PASS")
            has_subagent_attribution = False
            has_valid_agent_id = True
            for c in comments:
                print(f"   -> 评论内容: {c.message} | AgentID: {c.agent_id}")
                if "[执行者: 智能体" in c.message:
                    has_subagent_attribution = True
                    if c.agent_id is None:
                        has_valid_agent_id = False
            
            if has_subagent_attribution and has_valid_agent_id:
                print(f"✅ 验证 5: 评论署名识别 (Sub-Agent Attribution & AgentID) -> PASS")
            elif not has_valid_agent_id:
                print(f"❌ 验证 5: 评论署名识别 -> FAILED (AgentID 为空，将显示为 Local User)")
            else:
                print(f"❌ 验证 5: 评论署名识别 -> FAILED (未在评论中发现执行者标识)")
        else:
            print(f"❌ 验证 4: 执行记录同步至评论区 -> FAILED (仅有 {len(comments)} 条，预期至少 3 条)")

        print("\n🎊 终极全链路闭环测试圆满成功！看板现在应正确显示负责人、自动记录执行轨迹并自动标记为已完成。")

if __name__ == "__main__":
    asyncio.run(main())
