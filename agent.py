
import os

from langchain.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage, HumanMessage
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List
from langfuse import Langfuse
from typing_extensions import Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph.message import add_messages
from functools import partial

from datetime import datetime

def create_genealogy_vectorstore():
    """Create a vector database from all genealogy .in files"""
    print("Creating database")
    loader = DirectoryLoader('./data/horns_hj', glob="**/*.dk.in", loader_cls=TextLoader)
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    splits = text_splitter.split_documents(docs)

    embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
    vectorstore = FAISS.from_documents(splits, embeddings)
    print(vectorstore)
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
        Searches the genealogy data for relevant info.

        Args:
            query (str): The query to search for.
            vectorstore (object): The vectorstore to search in.
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
        except Exception as e:
            outputs.append(
                ToolMessage(
                    content=str(e),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )
    print(outputs)
    return {"messages": outputs}

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

def run_agent(state: ConversationState, llm: ChatOpenAI, vectorstore, tools):

    user_message = state["messages"][-1] if state["messages"] else ""

    vectorstore = state.get("vectorstore")
    if vectorstore:
        relevant_data = vectorstore.similarity_search(user_message.content, k=5)
        context = "\n\n".join([doc.page_content for doc in relevant_data])
    else:
        context = ""
    langfuse = Langfuse()
    template = langfuse.get_prompt("genealogy-prompt")
    system_prompt = template.compile(context=context)
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
        return {"messages": [result], "next_action": "tools"}
    else:
        return {"messages": [result], "next_action": "end"}

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
    try:
        existing_state = app_graph.get_state(config)
        print(f"Existing state messages count: {len(existing_state.values.get('messages', [])) if existing_state.values else 0}")
    except Exception as e:
        print(f"Could not check existing state: {e}")

    final_state = app_graph.invoke(initial_input, config)
    last_message = final_state["messages"][-1]

    ai_response = last_message.content
    return {
        "user_id": user_id,
        "response": ai_response,
    }