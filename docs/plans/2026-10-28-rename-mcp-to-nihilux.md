# To-do: rename the agent MCP surface to Nihilux

Status: source implemented and validated locally on 2026-10-30; full gate has one documented environment-dependent failure, passing in an isolated normal-path rerun. Shared skill synchronized and pushed; publication paused by Owner; installed-app acceptance pending. Baseline: 42a68a8; branch: codex/nihilux-mcp-rename.

Original problem (before this change): the app is called Nihilux, but its MCP still presented the old name.
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

## Implementation evidence (2026-10-30)

- Updated server identity, 23 tool names, instructions, descriptions and errors; old names have no aliases.
- Updated repository registrations and portable Windows launcher, CLI examples, agent docs and generated handoff prompts in `generation_service.py`.
- Preserved internal package/class names, data and bridge filenames, .sbd and the authentication header.
- MCP, integration and generation-handoff regression suite: 65 passed; `mcp-tests.log` (ignored local evidence).
- The actual `.mcp.json` command launched successfully from this checkout (including its space in the path): initialize reports nihilux; tools/list has 23 nihilux_* names. Evidence: `test-results/mcp-launch.json`.
- Shared skill changes against ai-dotfiles a34ee61 are preserved in `nihilux-filmmaking-rename.patch`; patch reverse-check passed. With explicit Owner approval, the patch was applied and committed as ai-dotfiles 834b791f316d09a9a2f48656b1538a3d8da692bf, synchronized to local Codex/Claude, and pushed. Remote main SHA matches. No NEEDS OWNER conflicts; sync backups retained.
- Draft patch-release notes: `docs/releases/v0.1.1.md`; version files and release tags have not been changed.
- Global sync initially failed automatic approval. Owner then explicitly approved sync and publication; sync completed. Owner subsequently paused publication: no Nihilux push, tag, release or installation has run. v0.1.1 notes remain a draft.

## Final verification and release hold

- Notion tracking: DEV-9, https://app.notion.com/p/408a5c61cbf3814f910bc160ad211107.
- `scripts/verify_dev.py --continue-on-fail`: syntax, migration, 40 frontend tests, lint and build passed. Backend: 1169 passed, 1 failed, 3 skipped, 41 subtests passed. Full gate exit 1; evidence `verify-dev-final.log`.
- Remaining failure: `test_real_blender_save_reaches_project_with_preview_and_manifest`. Blender 5.2's glTF exporter rejects the extended-length Windows path mixed with a trailing `/` (WinError 123). The same test passed using an ordinary isolated temporary path; evidence `test-results/blender-plainpath-recheck.log`. This is not a single all-green full-suite run.
- Other first-run failures were resolved by using the repository-pinned ffmpeg (SHA256 verified) and isolated temporary directories. Four scene-storage cases also failed on the unmodified 42a68a8 baseline and all passed with extended-length paths; evidence `test-results/baseline-recheck.log` and `test-results/longpath-recheck.log`.
- No backend or Blender storage behavior was changed to hide environment failures. Follow-up: make the Windows verification environment compatible with both deep storage paths and Blender's exporter.
- Owner's final direction: do not publish. Changes remain on the local branch; no Nihilux push, release tag, Release or app installation performed.
