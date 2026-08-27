
import os

from langchain.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage, HumanMessage
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from typing import List
from langfuse import Langfuse
from typing_extensions import Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph.message import add_messages

from pathlib import Path

from datetime import datetime

from eval import evaluate_invariant

def create_genealogy_vectorstore(data_dir, vector_folder):
    """Create a vector database from all genealogy .in files"""
    print("Creating database")
    loader = DirectoryLoader(data_dir, glob="**/*.dk.in", loader_cls=TextLoader)
    docs = loader.load()
    # text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=10, separators=['\n'])
    splits = []
    errors = []
    for doc in docs:
        lines = doc.page_content.split('\n')
        file_path = doc.metadata.get("source", "")
        file_name = Path(file_path).name
        linenum = 0
        for fileline in lines:
            if fileline.strip() and evaluate_invariant(errors, file_name, fileline, linenum):
                splits.append(Document(page_content=fileline.strip(), metadata=doc.metadata))
            linenum += 1
    print(len(splits))
    print(errors)
    api_key=os.getenv("OPENAI_API_KEY")
    try:
        embeddings = OpenAIEmbeddings(api_key=api_key)
        print("Embeddings created")
    except Exception as e:
        print(f"Failed to create embeddings: {e}")
        raise
    try:
        start = datetime.now()
        vectorstore = FAISS.from_documents(splits, embeddings)
        end = datetime.now()
        print(f"✓ Vectorstore created with {vectorstore.index.ntotal} vectors")
        print(f"Vectorstore created in {end - start}")
        vectorstore.save_local(vector_folder)
    except Exception as e:
        print(f"Failed to create vectorstore: {e}")
        raise
    return vectorstore




class ConversationState(TypedDict):
    # Chat history: List of messages for conversation memory
    messages: Annotated[List[dict], add_messages]
    # User ID required for tool calls
    user_id: str
    session_id: str
    timestamp: str
    next_action: str
    context: str

def create_search_tool(vectorstore):
    @tool
    def search_genealogy_data(query: str):
        """
        Searches the genealogy data for historical records.

        Use this tool when you need to retrieve specific data. 

        Args:
            query (str): The targeted search terms or individual names to look up.
        """
        results = vectorstore.similarity_search(query, k=5)
        return "\n\n".join([res.page_content for res in results])
    return search_genealogy_data

def route_next(state: ConversationState):
    next_action = state["next_action"]
    if next_action == "tools":
        return "tools"
    elif next_action == "end":
        return "end"
    else:
        raise ValueError(f"Unexpected next_action value: {next_action}")

def execute_tools(state: ConversationState, tools):
    ai_message = state["messages"][-1]
    if not ai_message.tool_calls:
        return state
    tool_calls = ai_message.tool_calls
    outputs = []
    tool_contents = []

    for tool_call in tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args")
        tool_call_id = tool_call.get("id")

        print(f"Executing tool: {tool_name} with args: {tool_args}")

        tool_func = next(t for t in tools if t.name == tool_name)
        if not tool_func:
            outputs.append(
                ToolMessage(
                    content=f"Tool not found: {tool_name}",
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )
            continue
        try:
            tool_output = tool_func.invoke(tool_args)
            outputs.append(
                ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )
            if tool_name == "search_genealogy_data":
                tool_contents.append(str(tool_output))
        except Exception as e:
            outputs.append(
                ToolMessage(
                    content=str(e),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )
    curr_context = state.get("context", "")
    updated_context = curr_context
    if tool_contents:
        new_context = "\n\n".join(tool_contents)
        updated_context = f"{curr_context}\n\n{new_context}".strip()
    return {"messages": outputs, "context": updated_context}

def create_agent_graph(llm: ChatOpenAI, redis_client, vectorstore):
    TOOLS = [create_search_tool(vectorstore)]
    workflow = StateGraph(ConversationState)
    workflow.add_node("agent", lambda state: run_agent(state, llm, vectorstore, TOOLS))
    workflow.add_node("tools", lambda state: execute_tools(state, TOOLS))

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        route_next,
        {
            "tools": "tools",
            "end": END
        }
    )
    workflow.add_edge("tools", "agent")
    checkpointer = RedisSaver(redis_client=redis_client)
    return workflow.compile(checkpointer=checkpointer)

_langfuse_cache = {}

def fetch_saved_langfuse_prompt(prompt_name):
    if prompt_name not in _langfuse_cache:
        langfuse = Langfuse()
        _langfuse_cache[prompt_name] = langfuse.get_prompt(prompt_name)
    return _langfuse_cache[prompt_name]

def run_agent(state: ConversationState, llm: ChatOpenAI, vectorstore, tools):

    user_message = state["messages"][-1] if state["messages"] else ""

    # vectorstore = state.get("vectorstore")
    if vectorstore:
        relevant_data = vectorstore.similarity_search(user_message.content, k=3)
        init_context = "\n\n".join([doc.page_content for doc in relevant_data])
    else:
        init_context = ""

    existing_context = state.get("context", "")
    full_context = f"{existing_context}\n\n{init_context}".strip() if existing_context else init_context
    # langfuse = Langfuse()
    template = fetch_saved_langfuse_prompt("genealogy-prompt")
    system_prompt = template.compile(context=full_context)
    # system_prompt = PromptTemplate.from_template(template)
    agent_llm = llm.bind_tools(tools)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            # Placeholder for history, handled by LangGraph's message mapping
            MessagesPlaceholder("messages"),
        ]
    )

    chain = prompt | agent_llm


    result = chain.invoke({"messages": state["messages"]})
    if result.tool_calls:
        return {"messages": [result], "next_action": "tools", "context": full_context}
    else:
        return {"messages": [result], "next_action": "end", "context": full_context}

async def run_agent_assessment(app_graph, user_query, thread_id, user_id='1'):
    user_message = HumanMessage(content=user_query)
    print(user_message)
    config = {"configurable": {"thread_id": thread_id}}
    initial_input = {
        "messages": [user_message],
        "context": '',
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "next_action": '',
    }
    
    final_state = app_graph.invoke(initial_input, config)
    # content = ""
    # for event in app_graph.stream(initial_input, config, stream_mode="values"):
    #    content += event["messages"][-1].content
    last_message = final_state["messages"][-1]

    ai_response = last_message.content

    retrieved_context = final_state.get("context", "")
    return {
        "user_id": user_id,
        "content": ai_response,
        "context": retrieved_context
    }