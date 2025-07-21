# Agentic Durable Environments

The new standard for agentic evaluation and environments

## About

This is an example of a stateful and actionable agent environment with Cloudflare Durable Objects. The DO can be found at src/new_entry.py and contains things like the environment state, ways to initialize state in a way that attempts to resemble a real world state, an entry point defined by an on_fetch(), and a series of tools that allow for interacting with different components of the state and environment data.

Why Durable Objects? As LLM agents become increasingly popular, there lacks a standard way to evaluate and train these agents given this requires a full, stateful environment rather than the simple eval set of QA pairs. Also due to the fact that in order to properly observe these agents, the agents must be able to perform long tasked sequences of actions with a state it can interact and get responses from, these environments have to be sandboxed but also easily replicable.

Consider in previous cases of evaluating LLMs, one might have thousands or tens of thousands of eval QA pairs, and to evaluate at any point you have to run all of those thousands of Q inputs to compare against ground truth As. This alone can be a bit time consuming but is pretty manageable since parallelization of single turn generation is relatively easy. Now imagine having tens of thousands of eval scenarios for an agent, where every scenario requires a stateful and actionable environment. These individual scenarios alone can be timely to run since they are almost always multi turn and long horizon tasks that require many generations per scenario. But that doesn't even begin to consider how to manage the environment for each.

So we use Durable Objects and Workers to enable the unlimited scaling of DO. As long as we have enough GPUs, we can initiate 1000s of parallel agent/llm generations along with the 1000s of corresponding DOs for each agent to interact with.

<img src="https://github.com/cdreetz/on-call-agent-durable-obj/blob/master/public/dur-obj.png" width="600">

## Local Usage

Start the Durable Object and Worker handler locally:

```bash
npm i
npm run dev
```

Then test it by running(first change the localhost:port in test.py):

```bash
uv run test_scripts/test.py
```

And you can even see how an agent uses the environment with(first change the localhost:port in test_agent.py):

```bash
uv run test_scripts/test_agent.py
```

You should see something like:

```
Starting LLM OnCall Integration Test...
Make sure your worker is running and OPENAI_API_KEY is set

Testing LLM Integration with OnCall Environment
============================================================
Agent ID: llm-agent-3475940632

1. Initializing OnCall environment...
Environment initialized
   Incident: High database response times detected. Users reporting slow page loads.
   Tool calls available: 10

2. Getting system prompt...
System prompt retrieved (2340 chars)

3. Calling LLM for initial analysis...
LLM Response:
   Let's use the "check_dependencies" tool to understand the status of the service dependencies. No need to filter by service name at this point, as we want to get an overview of all services.

4. Parsing tool call from LLM response...
Detected tool call: check_dependencies

5. Executing tool call...
Tool executed successfully
   Calls remaining: 9
   Dependencies found: 2
     - postgres-primary: degraded (5000ms)
     - redis: healthy (10ms)

6. Getting LLM analysis of tool results...
LLM Analysis:
   The "postgres-primary" service is showing a degraded status with a high response time. This could be the root cause of the incident. Let's use the "query_logs" tool to check the logs of the "postgres-primary" service for any errors or unusual activity. The SQL query should filter for logs related to "postgres-primary".

Test completed. Tool calls used: 2/10

LLM integration test completed!
```

Or with the OpenAI compatible tools API:

```bash
uv run test_scripts/test_agent_openai.py
```

Should return something like:

```
Starting LLM OnCall Integration Test...
Make sure your worker is running and OPENAI_API_KEY is set

Testing LLM Integration with OnCall Environment
============================================================
Agent ID: llm-agent-1459023789

1. Initializing OnCall environment...
Environment initialized
   Incident: High database response times detected. Users reporting slow page loads.
   Tool calls available: 10

2. Getting system prompt and tools...
System prompt retrieved (2436 chars)
Tools converted: 4 tools available

3. Calling LLM for initial analysis...
LLM Response: No content, tool call made

4. Processing 1 tool call(s)...
Executing tool 1: check_dependencies
   Calls remaining: 9
   Dependencies found: 2
     - postgres-primary: degraded (5000ms)
     - redis: healthy (10ms)

5. Getting LLM analysis of tool results...
LLM Analysis:
   The status of the "postgres-primary" dependency is degraded with a high response time of 5000ms. This could be the cause of the incident. Let's check the logs for any related errors.

Test completed. Tool calls used: 1

LLM integration test completed!
```

### Other Dependencies

You'll need `uv`, which you can install by following
https://docs.astral.sh/uv/getting-started/installation/.
