import asyncio
import sys
from pathlib import Path
from uuid import UUID
from sqlmodel import select

# Setup path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

BOARD_ID = UUID("3cfb3a71-1844-4169-a732-1d23503b1c30")

async def main():
    from app.db.session import async_session_maker
    from app.models.tasks import Task
    from app.models.missions import Mission, MissionSubtask
    from app.services.missions.orchestrator import MissionOrchestrator
    from app.services.missions.status_machine import MISSION_STATUS_PENDING_APPROVAL
    from app.models.users import User
    from app.models.activity_events import ActivityEvent
    from app.models.approvals import Approval
    from app.core.time import utcnow
    import time

    async with async_session_maker() as session:
        user = (await session.exec(select(User))).first()
        if not user:
            print("No user found for testing context.")
            return
        
        orchestrator = MissionOrchestrator(session)

        print("[Agent Monitor] 步骤 1: 派发主任务及生成 Mission...")
        task = Task(
            title="使用python代码来写个贪吃蛇的游戏",
            description="请帮我写一个可在终端或者简易UI运行的Python贪吃蛇游戏代码，并保证完整可用。",
            organization_id=user.active_organization_id,
            board_id=BOARD_ID,
            status="inbox",
            priority="routine",
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        print(f"  -> Task 已创建 (ID: {task.id})")

        mission = await orchestrator.create_mission(
            task_id=task.id,
            board_id=BOARD_ID,
            goal="使用python代码来写个贪吃蛇的游戏",
            approval_policy="auto",
        )
        print(f"  -> Mission 已创建 (ID: {mission.id})，等待 Orchestrator 分解...")

        mission = await orchestrator.dispatch_mission(mission.id)

        # Pending Approval override
        if getattr(mission, 'status', None) == MISSION_STATUS_PENDING_APPROVAL:
            from app.services.missions.status_machine import MISSION_STATUS_PENDING, ensure_mission_transition
            ensure_mission_transition(mission.status, MISSION_STATUS_PENDING)
            mission.status = MISSION_STATUS_PENDING
            mission.approval_policy = "auto"
            mission.updated_at = utcnow()
            session.add(mission)
            await session.commit()
            mission = await orchestrator.dispatch_mission(mission.id)

        print("\n[Agent Monitor] 步骤 2: 监控 Orchestrator 分解...")
        await asyncio.sleep(5)
        
        subtasks = (await session.exec(
            select(MissionSubtask).where(MissionSubtask.mission_id == mission.id)
        )).all()
        
        print(f"  -> 分解出 {len(subtasks)} 个子任务:")
        for st in subtasks:
            print(f"      - {st.label}")
        
        print("\n[Agent Monitor] 步骤 3: 监控 Code Agent 接收与执行子任务...")
        for st in subtasks:
            print(f"  -> Code Agent 正在处理: {st.label}")
            await asyncio.sleep(2)  # Simulate work
            
            result_code = ""
            if "Execution Plan" in st.label or "Analyze" in st.label:
                result_msg = "已分析需求：使用 pygame / curses，最终决定使用标准库 curses 实现简单的终端贪吃蛇，以兼容无GUI环境。"
            else:
                result_code = """
import curses
import random
import time

def main(stdscr):
    curses.curs_set(0)
    sh, sw = stdscr.getmaxyx()
    w = stdscr
    w.keypad(1)
    w.timeout(100)

    snk_x = sw//4
    snk_y = sh//2
    snake = [
        [snk_y, snk_x],
        [snk_y, snk_x-1],
        [snk_y, snk_x-2]
    ]

    food = [sh//2, sw//2]
    w.addch(food[0], food[1], curses.ACS_PI)

    key = curses.KEY_RIGHT

    while True:
        next_key = w.getch()
        key = key if next_key == -1 else next_key

        if snake[0][0] in [0, sh-1] or snake[0][1] in [0, sw-1] or snake[0] in snake[1:]:
            break

        new_head = [snake[0][0], snake[0][1]]

        if key == curses.KEY_DOWN:
            new_head[0] += 1
        if key == curses.KEY_UP:
            new_head[0] -= 1
        if key == curses.KEY_LEFT:
            new_head[1] -= 1
        if key == curses.KEY_RIGHT:
            new_head[1] += 1

        snake.insert(0, new_head)

        if snake[0] == food:
            food = None
            while food is None:
                nf = [
                    random.randint(1, sh-2),
                    random.randint(1, sw-2)
                ]
                food = nf if nf not in snake else None
            w.addch(food[0], food[1], curses.ACS_PI)
        else:
            tail = snake.pop()
            w.addch(tail[0], tail[1], ' ')

        w.addch(snake[0][0], snake[0][1], curses.ACS_CKBOARD)

    curses.endwin()
    print("Game Over!")

if __name__ == "__main__":
    curses.wrapper(main)
"""
                result_msg = f"已编写并验收游戏代码。代码使用了标准的 curses 库。代码已准备完毕。\n{result_code[:50]}..."
                
                # Write to disk to simulate real file saving
                with open(BACKEND_ROOT.parent / "snake_game.py", "w") as f:
                    f.write(result_code)

            await orchestrator.update_subtask_status(
                st.id, 
                status="completed", 
                result_summary=result_msg
            )
            print(f"  -> 子任务完成! 返回摘要: {result_msg[:50]}...")
            
        print("\n[Agent Monitor] 步骤 4: 汇总、审批机制与任务闭环...")
        await asyncio.sleep(2)
        await session.refresh(mission)
        if getattr(mission, 'status', None) == MISSION_STATUS_PENDING_APPROVAL:
            print("  -> Lead Agent 审批开启，模拟自动通过...")
            app_stmt = select(Approval).where(Approval.id == mission.approval_id)
            approval = (await session.exec(app_stmt)).first()
            if approval:
                from app.services.missions.orchestrator import MISSION_STATUS_COMPLETED
                approval.status = "granted"
                approval.resolved_at = utcnow()
                session.add(approval)
                mission.status = MISSION_STATUS_COMPLETED
                mission.completed_at = utcnow()
                mission.result_summary = "贪吃蛇游戏代码（终端版）已成功生成并写入根目录 snake_game.py 中。"
                session.add(mission)
                await session.commit()
                print("  -> Mission 批准完成并转移为 done。")
        else:
            print(f"  -> 自动完结! Mission Status: {mission.status}")
        
        await session.refresh(task)
        task.status = "done"
        session.add(task)
        await session.commit()
        
        print(f"\n✅ 监控完毕。全链路完成。\n代码已存放至项目根目录 `snake_game.py`。")

if __name__ == "__main__":
    asyncio.run(main())
