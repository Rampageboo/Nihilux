@echo off
rem Nihilux MCP server (stdio). It is an HTTP client of the running app:
rem start Nihilux and open a project first. Tools: see docs/agent_mcp.md.
setlocal
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  >&2 echo Nihilux MCP needs the project virtual environment. Run Nihilux once to create it.
  exit /b 1
)
".venv\Scripts\python.exe" -m storyboard_tool.mcp_server %*
