
import asyncio
import json
from sqlmodel import select
from app.db.session import async_session_maker
from app.models.gateways import Gateway
from app.services.openclaw.admin_service import GatewayAdminLifecycleService

async def main():
    async with async_session_maker() as session:
        result = await session.execute(select(Gateway))
        gateway = result.scalars().first()
        if not gateway:
            print("No gateway found.")
            return
            
        svc = GatewayAdminLifecycleService(session)
        status = await svc.check_gateway_health(gateway)
        print(f"HEALTH_STATUS_JSON: {status.model_dump_json()}")

if __name__ == "__main__":
    asyncio.run(main())
