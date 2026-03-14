
import asyncio
import sys
from pathlib import Path
from sqlmodel import select, delete

# 设置路径
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

async def main():
    from app.db.session import async_session_maker
    from app.models.tasks import Task
    from app.models.missions import Mission, MissionSubtask
    from app.models.boards import Board
    from app.models.activity_events import ActivityEvent
    from app.models.approvals import Approval
    from app.models.task_dependencies import TaskDependency
    from app.models.task_custom_fields import TaskCustomFieldValue
    from app.models.approval_task_links import ApprovalTaskLink
    from app.models.feishu_sync import FeishuTaskMapping

    async with async_session_maker() as session:
        # 1. 获取第一个看板
        result = await session.exec(select(Board))
        board = result.first()
        if not board:
            print("❌ 未找到任何看板。")
            return
        
        print(f"正在执行终极清空 (含飞书同步数据): {board.name} (ID: {board.id})...")

        # 2. 查找该看板下的所有任务 ID
        stmt = select(Task.id).where(Task.board_id == board.id)
        task_ids_result = await session.exec(stmt)
        task_ids = task_ids_result.all()

        if not task_ids:
            print("看板中已经没有任务。")
            return

        print(f"找到 {len(task_ids)} 个任务，正在清理全量关联链...")

        for tid in task_ids:
            # A. 清理飞书映射
            await session.exec(delete(FeishuTaskMapping).where(FeishuTaskMapping.task_id == tid))

            # B. 找到关联的 Mission 并清理子任务
            m_stmt = select(Mission.id).where(Mission.task_id == tid)
            m_ids = (await session.exec(m_stmt)).all()
            for mid in m_ids:
                await session.exec(delete(MissionSubtask).where(MissionSubtask.mission_id == mid))
            
            # C. 删除 Mission (解除对 Approval 的引用)
            await session.exec(delete(Mission).where(Mission.task_id == tid))

            # D. 清理审批相关数据 (ApprovalTaskLink 依赖 Approval, Approval 依赖 Task/Board)
            a_stmt = select(Approval.id).where(Approval.task_id == tid)
            a_ids = (await session.exec(a_stmt)).all()
            for aid in a_ids:
                await session.exec(delete(ApprovalTaskLink).where(ApprovalTaskLink.approval_id == aid))
            await session.exec(delete(Approval).where(Approval.task_id == tid))

            # E. 清理其他边缘关联
            await session.exec(delete(ActivityEvent).where(ActivityEvent.task_id == tid))
            await session.exec(delete(TaskDependency).where((TaskDependency.task_id == tid) | (TaskDependency.depends_on_task_id == tid)))
            await session.exec(delete(TaskCustomFieldValue).where(TaskCustomFieldValue.task_id == tid))

        # F. 最后删除看板下所有 Task
        await session.exec(delete(Task).where(Task.board_id == board.id))

        await session.commit()
        print(f"✅ 看板 '{board.name}' 及其所有关联同步数据已彻底清空。")

if __name__ == "__main__":
    asyncio.run(main())
