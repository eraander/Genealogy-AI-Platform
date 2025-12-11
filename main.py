
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Form
from dotenv import load_dotenv
import logging
import os
import redis
from langfuse import Langfuse
from langchain_openai import ChatOpenAI

from agent import create_agent_graph, run_agent_assessment, create_genealogy_vectorstore

load_dotenv()

redis_connection_args = redis.ConnectionPool.from_url(os.getenv("REDIS_URL")).connection_kwargs

langfuse_client = Langfuse()

REDIS_CLIENT = redis.Redis(
    host=redis_connection_args.get('host'),
    port=redis_connection_args.get('port'),
    db=redis_connection_args.get('db'),
    password=redis_connection_args.get('password')
)

openai_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(api_key=openai_key, model="gpt-5", temperature=0)
vectorstore = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_graph, vectorstore

    vectorstore = create_genealogy_vectorstore()
    app_graph = create_agent_graph(llm=llm, redis_client=REDIS_CLIENT, vectorstore=vectorstore)
    yield
    langfuse_client.flush()

app = FastAPI(lifespan=lifespan)

@app.post("/search_session")
async def search_session(user_query: str = Form(...), thread_id: str = Form(...)):
    print('111')
    try:
        print(user_query)
        result = await run_agent_assessment(
            app_graph=app_graph,
            thread_id=thread_id,
            user_query=user_query,
        )
        return result
    except Exception as e:
        logging.exception("Graph execution failed.")
        print("Graph failed:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
    