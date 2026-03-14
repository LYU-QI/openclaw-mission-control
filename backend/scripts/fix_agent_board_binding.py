
import asyncio
from sqlmodel import select
from app.db.session import async_session_maker
from app.models.boards import Board
from app.models.agents import Agent

async def fix_agent_bindings():
    async with async_session_maker() as session:
        # 1. 获取目标看板
        board_stmt = select(Board).where(Board.name == "RIQIFirstBoard")
        board = (await session.exec(board_stmt)).first()
        if not board:
            print("❌ 错误: 未找到名为 'RIQIFirstBoard' 的看板")
            return
        
        print(f"🎯 目标看板: {board.name} (ID: {board.id})")

        # 2. 获取未绑定且在线的 Agent
        agent_stmt = select(Agent).where(Agent.board_id == None)
        unbound_agents = (await session.exec(agent_stmt)).all()
        
        if not unbound_agents:
            print("✅ 没有发现需要绑定的未关联 Agent。")
            return

        print(f"发现 {len(unbound_agents)} 个待绑定 Agent，正在执行关联...")
        
        for agent in unbound_agents:
            print(f"   -> 正在绑定 Agent: {agent.name}")
            agent.board_id = board.id
            session.add(agent)
        
        await session.commit()
        print("🎉 修复完成！所有常驻 Agent 现已成功归入看板。")

if __name__ == "__main__":
    asyncio.run(fix_agent_bindings())
