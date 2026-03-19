
import asyncio
from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent

async def audit():
    async with async_session_maker() as session:
        # 获取最近有评论的任务 ID，直接获取标量值
        stmt = select(ActivityEvent.task_id).where(ActivityEvent.event_type == "task.comment").order_by(ActivityEvent.created_at.desc()).limit(1)
        res = await session.exec(stmt)
        # scalar() 获取第一行第一列的值
        task_id = res.scalar()
        
        if not task_id:
            print("未找到任何评论")
            return

        print(f"审计任务 ID: {task_id}")
        print("-" * 50)

        # 获取该任务的所有评论详情记录
        comment_stmt = (
            select(ActivityEvent)
            .where(ActivityEvent.task_id == task_id)
            .where(ActivityEvent.event_type == "task.comment")
            .order_by(ActivityEvent.created_at.asc())
        )
        # 直接使用 scalars() 获取模型实例列表
        res = await session.exec(comment_stmt)
        comments = res.scalars().all()

        for c in comments:
            agent_name = "Local User"
            if c.agent_id:
                agent = await session.get(Agent, c.agent_id)
                agent_name = agent.name if agent else f"Unknown Agent ({c.agent_id})"
            
            print(f"[{c.created_at}] {agent_name}: {c.message}")

if __name__ == "__main__":
    asyncio.run(audit())
