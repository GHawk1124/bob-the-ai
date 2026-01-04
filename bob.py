import uvicorn
import server
import config

if __name__ == "__main__":
    print("=" * 60)
    print("BOB - Cognitive Loop AI Agent")
    print("=" * 60)
    print(f"Model: {config.MODEL_NAME}")
    print(f"API Base: {config.OPENAI_BASE_URL}")
    print(f"HTTP Port: {config.HTTP_PORT}")
    print("=" * 60)
    
    uvicorn.run(server.app, host="0.0.0.0", port=config.HTTP_PORT)
