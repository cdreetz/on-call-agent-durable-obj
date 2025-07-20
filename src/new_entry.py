from workers import DurableObject, Response, handler
from urllib.parse import urlparse
import json

class OnCallEnvironment(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self._init_db()
        self.tool_calls_made = 0
        self.max_tool_calls = 10
        self.completed = False
        self.incident_data = self._generate_incident()
        self._populate_logs()
        self.system_prompt = self._get_default_system_prompt()
    
    def _init_db(self):
        self.ctx.storage.sql.exec("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                level TEXT,
                service TEXT,
                message TEXT,
                metadata TEXT
            )
        """)
    
    def _populate_logs(self):
        logs = self.incident_data["environment"]["logs"]
        for log in logs:
            self.ctx.storage.sql.exec(
                "INSERT INTO logs (timestamp, level, service, message, metadata) VALUES (?, ?, ?, ?, ?)",
                log.get("timestamp", ""),
                log.get("level", ""),
                log.get("service", ""),
                log.get("message", ""),
                json.dumps(log.get("metadata", {}))
            )

    
    async def on_fetch(self, request):
        """Entry point for the DO
        Single RPC invocation for the Worker handler that takes the
        full request and parses it to call internal methods
        """

        data = await request.json()
        action = data.get("action")
        
        if action == "get_initial_state":
            return await self.get_initial_state()
        elif action == "get_tools":
            return await self.get_tools()
        elif action == "get_system_prompt":
            return await self.get_system_prompt()
        elif action == "update_system_prompt":
            return await self.update_system_prompt(data.get("system_prompt"))
        elif action == "use_tool":
            return await self.use_tool(data)
        elif action == "submit_diagnosis":
            return await self.submit_diagnosis(data.get("diagnosis"))

    async def get_system_prompt(self):
        tools = self._get_tools_definitions()
        tool_definitions = json.dumps(tools, indent=2)
        formatted_prompt = self.system_prompt.replace("{TOOL_DEFINITIONS}", tool_definitions)

        return Response(json.dumps({
            "system_prompt": formatted_prompt
        }))

    async def update_system_prompt(self, new_prompt):
        if new_prompt:
            self.system_prompt = new_prompt
            return Response(json.dumps({"status": "System prompt udpated"}))
        else:
            return Response(json.dumps({"error": "No system prompt provided"}), status=400)

    
    async def get_initial_state(self):
        return Response(json.dumps({
            "incident_alert": self.incident_data["alert"],
            "max_tool_calls": self.max_tool_calls,
            "calls_remaining": self.max_tool_calls - self.tool_calls_made
        }))

    async def get_tools(self):
        return Response(json.dumps({
            "tools": self._get_tools_definitions()
        }))

    async def use_tool(self, data):
        if self.completed:
            return Response(json.dumps({"error": "Environment completed"}), status=400)
        
        if self.tool_calls_made >= self.max_tool_calls:
            return Response(json.dumps({"error": "Max tool calls exceeded"}), status=400)
        
        tool_call = data.get("tool_call", {})
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("arguments", {})
        
        if not tool_name:
            return Response(json.dumps({"error": "Missing tool name"}), status=400)
        
        self.tool_calls_made += 1
        tool_response = self._execute_tool(tool_name, tool_args)
        
        return Response(json.dumps({
            "tool_response": tool_response,
            "calls_remaining": self.max_tool_calls - self.tool_calls_made,
            "call_number": self.tool_calls_made
        }))
    
    async def submit_diagnosis(self, diagnosis):
        if self.completed:
            return Response(json.dumps({"error": "Already completed"}), status=400)
        
        self.completed = True
        
        correct = diagnosis.lower() == self.incident_data["correct_diagnosis"].lower()
        primary_reward = 2.0 if correct else 0.0
        efficiency_reward = max(0.0, 1.0 - (0.15 * (self.tool_calls_made - 1))) if correct else 0.0
        total_reward = primary_reward + efficiency_reward
        
        return Response(json.dumps({
            "correct": correct,
            "correct_diagnosis": self.incident_data["correct_diagnosis"],
            "agent_diagnosis": diagnosis,
            "primary_reward": primary_reward,
            "efficiency_reward": efficiency_reward,
            "total_reward": total_reward,
            "tool_calls_used": self.tool_calls_made,
            "completed": True
        }))

    def _get_tools_definitions(self):
        return [
            {
                "type": "function",
                "name": "check_dependencies",
                "description": "Check status of service dependencies",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional: filter by service name"
                        }
                    }
                }
            },
            {
                "type": "function",
                "name": "check_slack", 
                "description": "Search recent Slack messages from team members",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional: search term to filter messages"
                        }
                    }
                }
            },
            {
                "type": "function",
                "name": "check_deployments",
                "description": "Check recent deployment status and history",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional: filter by service name"
                        }
                    }
                }
            },
            {
                "type": "function",
                "name": "query_logs",
                "description": "Execute SQL query on logs database. Table schema: logs(id INTEGER, timestamp TEXT, level TEXT, service TEXT, message TEXT, metadata TEXT)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "SQL SELECT query to execute against logs table. Use LIMIT to control result size."
                        }
                    },
                    "required": ["sql_query"]
                }
            }
        ]
    
    def _get_default_system_prompt(self):
        return """You are an expert on-call engineer responsible for diagnosing production incidents quickly and accurately.

Your goal is to identify the root cause of incidents using the available tools with maximum efficiency.

AVAILABLE TOOLS:
- check_dependencies: Check status of service dependencies  
- check_slack: Search recent team Slack messages for context
- check_deployments: Check recent deployment history
- query_logs: Execute SQL queries on the observability logs database

{TOOL_DEFINITIONS}

CONSTRAINTS:
- You have a maximum of 10 tool calls to make your diagnosis
- You must submit a diagnosis before running out of tool calls
- Be efficient - you get bonus rewards for correct diagnoses with fewer tool calls

Your diagnosis should be concise and specific (e.g., "database connection pool exhausted", "memory leak in web service", "network timeout to payment API").

Remember: Accuracy is more important than speed, but efficiency is rewarded."""

    
    def _execute_tool(self, tool_name, args):
        env_state = self.incident_data["environment"]
        
        if tool_name == "check_dependencies":
            query = args.get("query", "")
            deps = env_state["dependencies"]
            if query:
                deps = [d for d in deps if query.lower() in d["name"].lower()]
            return {"dependencies": deps}
        
        elif tool_name == "check_slack":
            query = args.get("query", "")
            messages = env_state["slack_messages"]
            if query:
                messages = [m for m in messages if query.lower() in m["content"].lower()]
            return {"messages": messages}
        
        elif tool_name == "check_deployments":
            query = args.get("query", "")
            deployments = env_state["deployments"]
            if query:
                deployments = [d for d in deployments if query.lower() in d["service"].lower()]
            return {"deployments": deployments}
        
        elif tool_name == "query_logs":
            return self._query_logs_db(args.get("sql_query", ""))
        
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    def _query_logs_db(self, sql_query):
        """Execute SQL query on logs table"""
        if not sql_query:
            return {"error": "No SQL query provided"}

        try:
            if not sql_query.strip().upper().startswith("SELECT"):
                return {"error": "Only SELECT queries are allowed"}

            results = self.ctx.storage.sql.exec(sql_query).all()

            logs = []
            for row in results:
                logs.append({
                    "timestamp": row.timestamp,
                    "level": row.level,
                    "service": row.service,
                    "message": row.message,
                    "metadata": json.loads(row.metadata) if row.metadata else {},
                })

            total_found = len(logs)
            if len(logs) > 50:
                logs = logs[:50]
                return {
                    "logs": logs,
                    "total_found": total_found,
                    "query_executed": sql_query,
                    "warning": f"Query returned {total_found} results, showing first 50. Consider adding additional filters (WHERE, LIMIT) to narrow results."
                }

            return {
                "logs": logs,
                "total_found": len(logs),
                "query_executed": sql_query
            }

        except Exception as e:
            return {"error": f"SQL execution failed: {str(e)}"}

    
    def _generate_incident(self):
        return {
            "alert": "High database response times detected. Users reporting slow page loads.",
            "correct_diagnosis": "database connection pool exhausted",
            "environment": {
                "dependencies": [
                    {"name": "postgres-primary", "status": "degraded", "response_time": "5000ms"},
                    {"name": "redis", "status": "healthy", "response_time": "10ms"}
                ],
                "slack_messages": [
                    {"user": "alice", "content": "Seeing timeouts on checkout", "timestamp": "10:30"},
                    {"user": "bob", "content": "DB connections maxed out", "timestamp": "10:32"}
                ],
                "deployments": [
                    {"service": "web-app", "status": "success", "timestamp": "09:00"}
                ],
                "logs": [
                    {"timestamp": "2025-07-20T10:31:00Z", "level": "ERROR", "service": "postgres", "message": "Connection pool exhausted", "metadata": {"pool_size": 20, "active_connections": 20}},
                    {"timestamp": "2025-07-20T10:30:30Z", "level": "WARN", "service": "postgres", "message": "High response time: 4500ms", "metadata": {"query": "SELECT * FROM users"}},
                    {"timestamp": "2025-07-20T10:30:00Z", "level": "ERROR", "service": "web-app", "message": "Database timeout after 5000ms", "metadata": {"endpoint": "/checkout"}},
                    {"timestamp": "2025-07-20T10:29:45Z", "level": "INFO", "service": "postgres", "message": "Connection pool at 95% capacity", "metadata": {"pool_size": 20, "active_connections": 19}},
                    {"timestamp": "2025-07-20T10:29:00Z", "level": "WARN", "service": "web-app", "message": "Slow query detected: 3200ms", "metadata": {"query_id": "q123"}}
                ]
            }
        }

@handler
async def on_fetch(request, env, ctx):
    url = urlparse(request.url)
    #data = await request.json()
    #agent_id = data.get("agent_id")
    id = env.ONCALL_ENV.idFromName(url.path)
    stub = env.ONCALL_ENV.get(id)

    res = await stub.fetch(
        request.url,
        method=request.method,
        body=await request.text() if request.method in ["POST", "PATCH", "PUT"] else None,
        headers=dict(request.headers)
    )

    return res

    #id = env.ONCALL_ENV.idFromName(f"agent-{agent_id}")
    #stub = env.ONCALL_ENV.get(id)

    #return await stub.fetch(request)
    #return await stub.fetch(request_url, {
    #    "method": request.method,
    #    "body": await request.text(),
    #    "headers": dict(request.headers)
    #})
