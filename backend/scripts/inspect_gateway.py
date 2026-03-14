
import asyncio
from sqlmodel import select
from app.db.session import async_session_maker
from app.models.gateways import Gateway
from app.models.boards import Board
from app.models.feishu_sync import FeishuSyncConfig
from app.models.notifications import NotificationConfig

async def main():
    async with async_session_maker() as session:
        # Gateway
        result = await session.exec(select(Gateway))
        gateway = result.first()
        if gateway:
            print(f"GATEWAY_ID: {gateway.id}")
        
        # Board
        result = await session.exec(select(Board))
        board = result.first()
        if board:
            print(f"BOARD_ID: {board.id}")
            print(f"BOARD_NAME: {board.name}")

        # Feishu Config
        result = await session.exec(select(FeishuSyncConfig))
        fs = result.first()
        if fs:
            print(f"FEISHU_CONFIG_ID: {fs.id}")
            print(f"FEISHU_APP_ID: {fs.app_id}")
            print(f"FEISHU_TABLE_ID: {fs.bitable_table_id}")
            print(f"FEISHU_MAPPING: {fs.field_mapping}")
            print(f"FEISHU_ENABLED: {fs.enabled}")
        else:
            print("FEISHU_CONFIG: Not Found")

        # Notification Config
        result = await session.exec(select(NotificationConfig))
        nc_list = result.all()
        if nc_list:
            print(f"\nFOUND {len(nc_list)} NOTIFICATION CONFIGS:")
            for nc in nc_list:
                print(f"  - ID: {nc.id}, Type: {nc.channel_type}, Enabled: {nc.enabled}")
                print(f"    Events: {nc.notify_on_events}")
        else:
            print("\nNOTIFICATION_CONFIG: Not Found")

if __name__ == "__main__":
    asyncio.run(main())
