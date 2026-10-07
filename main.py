from fastapi import FastAPI
import uvicorn
from base.agent import root_agent
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    query: str

@app.post("/chat")
async def chat(request: ChatRequest):
    result = await root_agent.ainvoke(
        {"messages": [{"role": "user", "content": request.query}]}
    )
    return {"response": result["messages"][-1].content}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000 , reload=True)