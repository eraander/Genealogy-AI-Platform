
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Form
import gradio as gr
from dotenv import load_dotenv
import logging
import os
import redis
from langfuse import Langfuse
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from agent import create_agent_graph, run_agent_assessment, create_genealogy_vectorstore

vector_folder = 'family_vectorstore'

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
    vectorstore = None
    if os.path.exists(vector_folder):
        vectorstore = FAISS.load_local(vector_folder, OpenAIEmbeddings(), allow_dangerous_deserialization=True)
    else:
        vectorstore = create_genealogy_vectorstore()
    app_graph = create_agent_graph(llm=llm, redis_client=REDIS_CLIENT, vectorstore=vectorstore)
    yield
    langfuse_client.flush()

app = FastAPI(lifespan=lifespan)

@app.post("/search_session")
async def search_session(user_query: str = Form(...), thread_id: str = Form(...)):
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

async def chat_response(message, history):
    response = await search_session(message, '1234567')
    print(response)
    return response['content']

chat_ui = gr.ChatInterface(fn=chat_response, title="Genealogy Search")
    
app = gr.mount_gradio_app(app, chat_ui, path='/chat')