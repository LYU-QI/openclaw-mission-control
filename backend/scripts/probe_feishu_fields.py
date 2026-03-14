
import asyncio
import sys
from pathlib import Path

# 设置路径
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

async def main():
    from app.db.session import async_session_maker
    from app.models.feishu_sync import FeishuSyncConfig
    from app.services.feishu.client import FeishuClient
    from app.core.secrets import decrypt_secret
    from sqlmodel import select

    async with async_session_maker() as session:
        result = await session.exec(select(FeishuSyncConfig))
        config = result.first()
        if not config:
            return
        
        app_secret = decrypt_secret(config.app_secret_encrypted)
        client = FeishuClient(config.app_id, app_secret)
        
        # 探测字段
        resp = client.list_bitable_fields(config.bitable_app_token, config.bitable_table_id)
        if resp.get("code") == 0:
            fields = resp.get("data", {}).get("items", [])
            print("AVAILABLE_FIELDS:")
            for f in fields:
                print(f"  - {f['field_name']} ({f['type']})")
        else:
            print(f"ERROR_GETTING_FIELDS: {resp}")

if __name__ == "__main__":
    asyncio.run(main())
