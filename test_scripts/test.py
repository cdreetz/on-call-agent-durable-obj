#!/usr/bin/env python3
import requests
import json
import time

# Your local wrangler dev URL base
WORKER_BASE_URL = "http://localhost:61825"

def send_request(agent_id, action, **kwargs):
    """Send request to the worker"""
    # Use agent-specific URL path for isolation
    worker_url = f"{WORKER_BASE_URL}/{agent_id}"
    
    payload = {
        "action": action,
        **kwargs
    }
    
    try:
        response = requests.post(worker_url, json=payload)
        print(f" Response status: {response.status_code}")
        print(f" Response text: {response.text[:200]}...")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'No response'}")
        print(f"Response text: {response.text if 'text' in locals() else 'No response'}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response text: {response.text}")
        return None

def test_oncall_environment():
    """Test the OnCall environment step by step"""
    agent_id = "test-agent-1"
    
    print("Testing OnCall Environment")
    print("=" * 50)
    
    # Test 1: Get initial state
    print("\n1️⃣ Getting initial state...")
    initial_state = send_request(agent_id, "get_initial_state")
    if initial_state:
        print(f"Incident Alert: {initial_state['incident_alert']}")
        print(f"Max tool calls: {initial_state['max_tool_calls']}")
        print(f"Calls remaining: {initial_state['calls_remaining']}")
    else:
        print("Failed to get initial state")
        return
    
    # Test 2: Get tools
    print("\n2️⃣ Getting available tools...")
    tools_response = send_request(agent_id, "get_tools")
    if tools_response:
        tools = tools_response['tools']
        print(f"Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool['name']}: {tool['description']}")
    else:
        print("Failed to get tools")
        return
    
    # Test 3: Get system prompt
    print("\n3️⃣ Getting system prompt...")
    prompt_response = send_request(agent_id, "get_system_prompt")
    if prompt_response:
        prompt = prompt_response['system_prompt']
        print(f"System prompt length: {len(prompt)} characters")
        print(f"Contains tool definitions: {'TOOL_DEFINITIONS' not in prompt}")
    else:
        print("Failed to get system prompt")
        return
    
    # Test 4: Use check_dependencies tool
    print("\n4️⃣ Testing check_dependencies tool...")
    tool_call = {
        "name": "check_dependencies",
        "arguments": {}
    }
    deps_response = send_request(agent_id, "use_tool", tool_call=tool_call)
    if deps_response:
        deps = deps_response['tool_response']['dependencies']
        print(f"Found {len(deps)} dependencies:")
        for dep in deps:
            print(f"   - {dep['name']}: {dep['status']} ({dep['response_time']})")
        print(f"Calls remaining: {deps_response['calls_remaining']}")
    else:
        print("Failed to use check_dependencies tool")
        return

def test_new_agent():
    """Test with a different agent to verify isolation"""
    print("\n🔄 Testing new agent isolation...")
    agent_id = "test-agent-2"  # Different agent ID
    
    initial_state = send_request(agent_id, "get_initial_state")
    if initial_state:
        print(f"New agent has fresh state: {initial_state['calls_remaining']} calls remaining")
        if initial_state['calls_remaining'] == 10:
            print("✅ Agent isolation working correctly!")
        else:
            print("❌ Agent isolation failed - agents sharing state")
    else:
        print("Failed to create new agent")

if __name__ == "__main__":
    print("Starting OnCall Environment Tests...")
    print("Make sure your worker is running on the correct port")
    
    test_oncall_environment()
    test_new_agent()
    
    print("\nTest script completed!")
