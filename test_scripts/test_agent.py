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

def call_llm(messages):
    """Call OpenAI LLM with messages"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.1,
            max_tokens=500
        )
        print("full llm response: ", response)
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None

def parse_tool_call(llm_response):
    """Extract tool call from LLM response"""
    print("llm response try to parse tool call: ", llm_response)
    # Look for tool call patterns in the response
    lines = llm_response.lower().split('\n')
    
    for line in lines:
        if 'check_dependencies' in line:
            return {
                "name": "check_dependencies",
                "arguments": {}
            }
        elif 'check_slack' in line:
            return {
                "name": "check_slack", 
                "arguments": {}
            }
        elif 'check_deployments' in line:
            return {
                "name": "check_deployments",
                "arguments": {}
            }
        elif 'query_logs' in line:
            # Simple SQL query extraction
            return {
                "name": "query_logs",
                "arguments": {
                    "sql_query": "SELECT * FROM logs WHERE level = 'ERROR' ORDER BY timestamp DESC LIMIT 5"
                }
            }
    
    # Default to checking dependencies if no clear tool call found
    return {
        "name": "check_dependencies",
        "arguments": {}
    }

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
    
    # Step 2: Get system prompt
    print("\n2. Getting system prompt...")
    prompt_response = send_request(agent_id, "get_system_prompt")
    if not prompt_response:
        print("Failed to get system prompt")
        return
    
    system_prompt = prompt_response['system_prompt']
    print(f"System prompt retrieved ({len(system_prompt)} chars)")
    
    # Step 3: Prepare LLM conversation
    print("\n3. Calling LLM for initial analysis...")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "I need you to help diagnose this incident. Start by checking the dependency statuses to understand what services might be affected. Please tell me which tool you want to use and I'll execute it for you."}
    ]
    
    llm_response = call_llm(messages)
    if not llm_response:
        print("LLM call failed")
        return
    
    print(f"LLM Response:")
    print(f"   {llm_response}")
    
    # Step 4: Parse and execute tool call
    print("\n4. Parsing tool call from LLM response...")
    tool_call = parse_tool_call(llm_response)
    print(f"Detected tool call: {tool_call['name']}")
    
    # Step 5: Execute the tool
    print("\n5. Executing tool call...")
    tool_response = send_request(agent_id, "use_tool", tool_call=tool_call)
    if not tool_response:
        print("Tool execution failed")
        return
    
    print(f"Tool executed successfully")
    print(f"   Calls remaining: {tool_response['calls_remaining']}")
    
    # Display tool results
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
    
    # Step 6: Get LLM analysis of results
    print("\n6. Getting LLM analysis of tool results...")
    messages.append({"role": "assistant", "content": llm_response})
    messages.append({
        "role": "user", 
        "content": f"Here are the results from the {tool_call['name']} tool: {json.dumps(tool_response['tool_response'], indent=2)}. Based on this information, what should be our next step in diagnosing the incident?"
    })
    
    final_analysis = call_llm(messages)
    if final_analysis:
        print("LLM Analysis:")
        print(f"   {final_analysis}")
    
    print(f"\nTest completed. Tool calls used: {11 - tool_response['calls_remaining']}/10")

if __name__ == "__main__":
    print("Starting LLM OnCall Integration Test...")
    print("Make sure your worker is running and OPENAI_API_KEY is set")
    print()
    
    test_llm_oncall_integration()
    
    print("\nLLM integration test completed!")
