import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from app.main import app

if __name__ == "__main__":
    # Create the loop BEFORE uvicorn does anything
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, loop="none")
    server = uvicorn.Server(config)
    
    loop.run_until_complete(server.serve())
