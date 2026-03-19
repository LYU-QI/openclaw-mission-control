import asyncio
import sys
import time
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

    async with async_session_maker() as session:
        user = (await session.exec(select(User))).first()
        if not user:
            print("No user found for testing context.")
            return
        
        orchestrator = MissionOrchestrator(session)

        print("Step 1: Creating 'Snake Game' task...")
        task = Task(
            title="使用python代码来写个贪吃蛇的游戏",
            description="请帮我写一个可在终端或者简易UI(Tkinter/Pygame)运行的Python贪吃蛇游戏代码，并保证完整可用。注意尽量使用完整的Python脚本文档。",
            organization_id=user.active_organization_id,
            board_id=BOARD_ID,
            status="inbox",
            priority="routine",
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        print(f"Task created with ID: {task.id}")

        print("\nStep 2: Creating a mission...")
        mission = await orchestrator.create_mission(
            task_id=task.id,
            board_id=BOARD_ID,
            goal="协助用户使用Python编写一个完整的贪吃蛇游戏代码并执行验证。",
            approval_policy="auto",
        )
        print(f"Mission ID: {mission.id}")

        print("\nStep 3: Dispatching mission...")
        mission = await orchestrator.dispatch_mission(mission.id)

        # Handle Pending Approval
        if getattr(mission, 'status', None) == MISSION_STATUS_PENDING_APPROVAL:
            from app.services.missions.status_machine import MISSION_STATUS_PENDING, ensure_mission_transition
            from app.core.time import utcnow
            ensure_mission_transition(mission.status, MISSION_STATUS_PENDING)
            mission.status = MISSION_STATUS_PENDING
            mission.approval_policy = "auto"
            mission.updated_at = utcnow()
            session.add(mission)
            await session.commit()
            mission = await orchestrator.dispatch_mission(mission.id)

        print(f"\nMission dispatched! Now monitoring the execution process for 60 seconds (checking every 5 seconds).")
        
        for _ in range(15):
            await asyncio.sleep(5)
            # Fetch events
            events = (await session.exec(
                select(ActivityEvent).where(ActivityEvent.task_id == task.id).order_by(ActivityEvent.created_at)
            )).all()
            
            # Fetch subtasks
            subtasks = (await session.exec(
                select(MissionSubtask).where(MissionSubtask.mission_id == mission.id)
            )).all()
            
            print(f"\n--- Current Subtasks ({len(subtasks)}) ---")
            for i, st in enumerate(subtasks):
                print(f"  [{st.status}] Subtask {st.id}: {st.label}")
                if st.result_summary:
                    print(f"    Result: {st.result_summary[:100]}...")
            
            print(f"\n--- Latest 3 Events ---")
            for ev in events[-3:]:
                print(f"  [{ev.event_type}] {ev.message[:150]}")
                
            # If mission is completed or failed, we can stop
            await session.refresh(mission)
            if mission.status in ['completed', 'failed']:
                print(f"\nMission finished with status: {mission.status}")
                if mission.result_summary:
                    print(f"Final Summary: {mission.result_summary}")
                break

if __name__ == "__main__":
    asyncio.run(main())
