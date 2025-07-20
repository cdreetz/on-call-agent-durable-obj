#!/usr/bin/env python3
import requests
import json
import os
from openai import OpenAI

# Configuration
WORKER_BASE_URL = "http://localhost:64666"  # Update to match your wrangler port
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY environment variable not set")
    print("Set it with: export OPENAI_API_KEY=your_key_here")
    exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

def send_request(agent_id, action, **kwargs):
    """Send request to the OnCall environment"""
    worker_url = f"{WORKER_BASE_URL}/{agent_id}"
    payload = {"action": action, **kwargs}
    
    try:
        response = requests.post(worker_url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return None

def call_llm(messages, tools=None):
    """Call OpenAI LLM with messages and optional tools"""
    try:
        params = {
            "model": "gpt-4",
            "messages": messages,
            "temperature":0.1,
            "max_tokens":500
        }
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        
        response = client.chat.completions.create(**params)
        return response.choices[0].message
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None

def convert_tools_to_openai_format(oncall_tools):
    """Convert OnCall tools format to OpenAI tools format"""
    openai_tools = []
    for tool in oncall_tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        }
        openai_tools.append(openai_tool)
    return openai_tools

def parse_tool_calls(llm_message):
    """Extract tool calls from LLM message"""
    if hasattr(llm_message, 'tool_calls') and llm_message.tool_calls:
        tool_calls = []
        for tool_call in llm_message.tool_calls:
            tool_calls.append({
                "name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments)
            })
        return tool_calls
    return None

def test_llm_oncall_integration():
    """Test LLM integration with OnCall environment"""
    agent_id = f"llm-agent-{int(os.urandom(4).hex(), 16)}"  # Random agent ID
    
    print("Testing LLM Integration with OnCall Environment")
    print("=" * 60)
    print(f"Agent ID: {agent_id}")
    
    # Step 1: Initialize environment and get system prompt
    print("\n1. Initializing OnCall environment...")
    initial_state = send_request(agent_id, "get_initial_state")
    if not initial_state:
        print("Failed to initialize environment")
        return
    
    print(f"Environment initialized")
    print(f"   Incident: {initial_state['incident_alert']}")
    print(f"   Tool calls available: {initial_state['calls_remaining']}")
    
    # Step 2: Get system prompt and tools
    print("\n2. Getting system prompt and tools...")
    prompt_response = send_request(agent_id, "get_system_prompt")
    tools_response = send_request(agent_id, "get_tools")
    
    if not prompt_response or not tools_response:
        print("Failed to get system prompt or tools")
        return
    
    system_prompt = prompt_response['system_prompt']
    oncall_tools = tools_response['tools']
    openai_tools = convert_tools_to_openai_format(oncall_tools)
    
    print(f"System prompt retrieved ({len(system_prompt)} chars)")
    print(f"Tools converted: {len(openai_tools)} tools available")
    
    # Step 3: Call LLM with tools
    print("\n3. Calling LLM for initial analysis...")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "I need you to help diagnose this incident. Start by checking the dependency statuses to understand what services might be affected."}
    ]
    
    llm_message = call_llm(messages, tools=openai_tools)
    if not llm_message:
        print("LLM call failed")
        return
    
    print(f"LLM Response: {llm_message.content or 'No content, tool call made'}")
    
    # Step 4: Parse and execute tool calls
    tool_calls = parse_tool_calls(llm_message)
    if not tool_calls:
        print("No tool calls detected in LLM response")
        return
    
    print(f"\n4. Processing {len(tool_calls)} tool call(s)...")
    
    tool_results = []
    for i, tool_call in enumerate(tool_calls):
        print(f"Executing tool {i+1}: {tool_call['name']}")
        
        tool_response = send_request(agent_id, "use_tool", tool_call=tool_call)
        if not tool_response:
            print(f"Tool execution failed for {tool_call['name']}")
            continue
        
        tool_results.append({
            "tool_call": tool_call,
            "response": tool_response['tool_response']
        })
        
        print(f"   Calls remaining: {tool_response['calls_remaining']}")
        
        # Display specific tool results
        if tool_call['name'] == 'check_dependencies':
            deps = tool_response['tool_response']['dependencies']
            print(f"   Dependencies found: {len(deps)}")
            for dep in deps:
                print(f"     - {dep['name']}: {dep['status']} ({dep['response_time']})")
        
        elif tool_call['name'] == 'query_logs':
            logs = tool_response['tool_response'].get('logs', [])
            print(f"   Logs found: {len(logs)}")
            for log in logs[:3]:  # Show first 3
                print(f"     - {log['timestamp']}: {log['level']} - {log['message']}")
        
        elif tool_call['name'] == 'check_slack':
            messages_found = tool_response['tool_response']['messages']
            print(f"   Slack messages: {len(messages_found)}")
            for msg in messages_found:
                print(f"     - {msg['user']}: {msg['content']}")
        
        elif tool_call['name'] == 'check_deployments':
            deployments = tool_response['tool_response']['deployments']
            print(f"   Deployments: {len(deployments)}")
            for dep in deployments:
                print(f"     - {dep['service']}: {dep['status']} at {dep['timestamp']}")
    
    # Step 5: Get LLM analysis of results
    print("\n5. Getting LLM analysis of tool results...")
    
    # Add the assistant's message with tool calls
    messages.append({
        "role": "assistant", 
        "content": llm_message.content,
        "tool_calls": [
            {
                "id": f"call_{i}",
                "type": "function", 
                "function": {
                    "name": tc["tool_call"]["name"],
                    "arguments": json.dumps(tc["tool_call"]["arguments"])
                }
            }
            for i, tc in enumerate(tool_results)
        ]
    })
    
    # Add tool results
    for i, result in enumerate(tool_results):
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_{i}",
            "content": json.dumps(result["response"])
        })
    
    final_analysis = call_llm(messages)
    if final_analysis:
        print("LLM Analysis:")
        print(f"   {final_analysis.content}")
    
    print(f"\nTest completed. Tool calls used: {len(tool_calls)}")

if __name__ == "__main__":
    print("Starting LLM OnCall Integration Test...")
    print("Make sure your worker is running and OPENAI_API_KEY is set")
    print()
    
    test_llm_oncall_integration()
    
    print("\nLLM integration test completed!")
