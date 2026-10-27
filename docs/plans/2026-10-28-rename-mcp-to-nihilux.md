# To-do: rename the agent MCP surface to Nihilux

Status: to do (Owner, 2026-10-28). Do it on the development computer.

The app is called Nihilux, but its MCP still presents the old name.
- The server reports `serverInfo.name` as `storyboarder` (`storyboard_tool/mcp_server.py`, `SERVER_NAME`).
- Every tool is named `storyboard_*` (`storyboard_status`, `storyboard_grid`, `storyboard_add_board`, …).
- The server instructions start with "Storyboarder must be running".

Only the MCP-facing surface changes. Internal identifiers stay as they are, because that was the rename decision of 2026-10-27/28:
- the `storyboard_tool` package;
- `%APPDATA%\StoryboardTool` and the other data folders;
- the `.sbd` handle;
- the `X-Storyboarder-Token` header.

## Done when

- `serverInfo.name` is `nihilux`. Tools are `nihilux_*`: `nihilux_status`, `nihilux_outline`, `nihilux_grid`, `nihilux_add_board`, … — same verbs, new prefix.
- Server instructions, tool descriptions and errors say Nihilux. Errors include "Open Nihilux first".
- Every config that registers the server uses the key `nihilux`:
  - the repo's `.mcp.json`;
  - `.codex/config.toml`;
  - `integrations.mcp_config()`, which already uses `MCP_SERVER_NAME = "nihilux"`; check it still matches.
- `scripts/storyboarder-mcp.cmd` is renamed `scripts/nihilux-mcp.cmd`. `scripts/mcp_call.py` and its help text use the new tool names.
- Docs use the new names: `docs/agent_mcp.md`, the MCP parts of `docs/current_architecture.md`, and README.
- Tests:
  - `tests/test_storyboarder_mcp.py` is renamed (for example `tests/test_mcp_server.py`) and asserts the new names.
  - `scripts/verify_dev.py` passes.
- The shared skill in `Rampageboo/ai-dotfiles` is updated and synced:
  - rename `shared/skills/storyboarder-filmmaking` to `nihilux-filmmaking`;
  - update its name and description, every tool name in the SKILL.md and `references/*.md`, and the app name and paths;
  - update the README table entry;
  - follow the skill-authoring skill: run `sync.ps1`, commit, push.
- A patch release (`scripts/release.ps1`) ships it, and the installed app on the user computer updates to it.

## Notes

- **No aliases for the old tool names.** There is one user and the skill moves with the rename.
- **The user computer already has the server registered as `nihilux`.** The key is `nihilux` in user-scope `claude mcp`, with the command `D:/Apps/Nihilux/python/python.exe -m storyboard_tool.mcp_server` and `PYTHONPATH=D:/Apps/Nihilux/app`. After the update its tools show up as `mcp__nihilux__nihilux_*`, and nothing needs re-registering there.
- **Check the desktop shell's MCP launch.** Search `desktop/src-tauri` and the Settings → Integrations UI text for "storyboarder" while doing this, in case the shell or the "Copy MCP config" text mentions the server.
