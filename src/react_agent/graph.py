"""Flexible RAG + ORM agent for Ambac Tracker manufacturing system.

This agent uses a simple ReAct pattern, letting the LLM decide which tools to use
and when to use them, rather than forcing a rigid workflow.
"""

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from react_agent.configuration import Configuration
from react_agent.state import InputState, State
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model


async def agent_node(state: State) -> Dict[str, List[AIMessage]]:
    """
    Main agent node that decides what to do based on the conversation state.
    
    The agent can:
    - Use document search tools to find procedures and specifications
    - Use database query tools to get current operational data
    - Combine information from multiple sources
    - Provide final answers to the user
    """
    configuration = Configuration.from_context()
    model = load_chat_model(configuration.model).bind_tools(TOOLS)
    
    # Use the main system prompt from prompts.py
    from react_agent.prompts import SYSTEM_PROMPT
    system_prompt = SYSTEM_PROMPT.format(system_time=datetime.now(tz=UTC).isoformat())

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and len(state.messages) > 0:
        last_message = state.messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return {
                "messages": [
                    AIMessage(
                        content="I've reached the step limit, but based on the information I've gathered, let me provide you with what I found so far."
                    )
                ]
            }

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke([
            SystemMessage(content=system_prompt),
            *state.messages
        ])
    )

    return {"messages": [response]}


def should_continue(state: State) -> Literal["tools", "__end__"]:
    """
    Determine whether to continue using tools or end the conversation.
    
    This follows the standard ReAct pattern:
    - If the last message has tool calls, execute them
    - Otherwise, we're done
    """
    last_message = state.messages[-1]
    
    # If there are tool calls, continue to tools
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    # Otherwise we're done
    return "__end__"


# Build the graph with a simple ReAct pattern
builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Add nodes
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(TOOLS))

# Set entry point
builder.add_edge("__start__", "agent")

# Add conditional routing from agent
builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "__end__": "__end__"
    }
)

# After using tools, go back to agent for reasoning loops
builder.add_edge("tools", "agent")

# Compile the graph
graph = builder.compile(name="Manufacturing RAG Agent")