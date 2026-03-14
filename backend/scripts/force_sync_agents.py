
import asyncio
import time
from sqlmodel import select
from app.db.session import async_session_maker
from app.models.gateways import Gateway
from app.models.agents import Agent
from app.services.openclaw.admin_service import GatewayAdminLifecycleService

async def sync_with_retry(svc, gateway, agent, name):
    max_retries = 3
    for i in range(max_retries):
        try:
            print(f"  Attempt {i+1} for {name}...")
            await svc.provision_main_agent_record(gateway, agent, user=None, action="provision", notify=True)
            print(f"  {name} Synced successfully.")
            return True
        except Exception as e:
            if "rate limit" in str(e).lower():
                print(f"  Rate limited! Need more time. Error: {e}")
                if i < max_retries - 1:
                    print("  Waiting 45 seconds specifically for rate limit reset...")
                    await asyncio.sleep(45)
            else:
                print(f"  Sync failed for {name}: {e}")
                return False
    return False

async def main():
    async with async_session_maker() as session:
        result = await session.execute(select(Gateway))
        gateway = result.scalars().first()
        if not gateway:
            print("No gateway found.")
            return

        print(f"Starting CONSERVATIVE Force Sync for: {gateway.name}")
        svc = GatewayAdminLifecycleService(session)
        
        # 1. Main Agent
        main_agent = await svc.find_main_agent(gateway)
        if main_agent:
            print(f"\nStep 1: Syncing Main Agent...")
            await sync_with_retry(svc, gateway, main_agent, "Main Agent")

        # 2. System Agents
        for role in ["orchestrator", "sync_agent", "comms_agent"]:
            print(f"\nPhase: {role}")
            # Global long wait between any config.patch attempt
            print("Cooling down for 45 seconds BEFORE next agent to ensure gateway write lock is clear...")
            await asyncio.sleep(45)
            
            agent, _ = await svc.upsert_system_agent_record(gateway, role)
            await sync_with_retry(svc, gateway, agent, role.upper())
            
        await session.commit()
    print("\nConservative Force sync FINISHED. This usually solves 'provisioning' hang.")

if __name__ == "__main__":
    asyncio.run(main())
