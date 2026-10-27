# Nihilux: installer, GitHub Release auto-update, public repository

Status: approved direction (Owner, 2026-10-28), not started.

The app is renamed **Nihilux** (虚照). The new icon and the visible name already landed in `674910e`. This plan makes it a downloadable, self-updating Windows app. It follows Silverbench (`D:\Projects\RampageWorkbench`, `docs/plans/2026-10-27-release-and-auto-update.md`, `packaging/`, `.github/workflows/release.yml`, `apps/desktop/src-tauri/`), reusing what fits and simplifying where this app is lighter.

## Outcome

- A per-user Windows installer (NSIS, no admin) on the GitHub Releases of a new public repository `Rampageboo/Nihilux`.
- The app checks for updates at start and in Settings. One click downloads the update, verifies its signature, stops the backend, installs and restarts.
- The run computer needs no source checkout, Node, Rust or Python. `Storyboarder.vbs` and `run.bat` stay for development only.
- **Done** means:
  - pushing a tag `vX.Y.Z` produces a Release with the installer, `.sig` and `latest.json`;
  - an installed older version updates itself to the new one;
  - the installed app runs everything from the install folder: boards, PSD/Photoshop link, Blender, Comfy Cloud images and video, sequence export, and MCP.

## Decided

1. **Shell: Tauri 2, as in Silverbench.**
   - The Rust shell starts the bundled Python backend, waits for `/api/health` (add the endpoint if missing), opens the window on it, and owns the updater (`tauri-plugin-updater`, NSIS `createUpdaterArtifacts`).
   - The shell stops the backend process tree before installing an update.
   - pywebview is replaced. Backend behaviour that touched the pywebview window (`desktop.py`, and `app.state.main_window` in `backend_service` window focus/maximize for the Photoshop plugin) moves to the shell, through a Tauri command or event, or to a Win32 call from the backend. The implementer chooses.
   - The old `frontend/src-tauri` scaffold and the PyInstaller sidecar scripts (`sidecar_entry.py`, `scripts/build-sidecar.ps1`) are an abandoned approach. Delete them; don't revive them.
2. **Python: bundled CPython (python-build-standalone, the same minor version as `.venv`, pinned with SHA-256) with the dependencies pre-installed at build time.**
   - Unlike Silverbench there is no first-run pip install: the dependencies (fastapi, Pillow, opencv-headless, psd-tools, reportlab, comfy-sdk, keyring…) are small.
   - Install them from `requirements.lock.txt` into the staged Python at stage time, so the installer works offline and an update is a single download.
   - Drop pywebview from the runtime set.
3. **ffmpeg/ffprobe ship in the installer as an LGPL build** (e.g. BtbN `ffmpeg-n7.x-latest-win64-lgpl`), pinned with SHA-256. The backend prefers the bundled binaries over PATH. Add the license notice to `THIRD_PARTY_NOTICES.md`.
4. **Per-user state lives outside the install folder.**
   - Today `create_app(base_dir)` gets the repo root, so `Sessions/` (session, recents) sits next to the code. The installed app passes `%APPDATA%\StoryboardTool` instead; internal names stay, as in Silverbench.
   - The live bridge (`%LOCALAPPDATA%\StoryboardTool`), the Comfy Cloud key (Windows Credential Manager) and the projects themselves are already per user.
   - A dev checkout keeps working with its current base dir.
5. **Updater signing:**
   - A new minisign key pair from `tauri signer generate`. The private key and its password go into GitHub Actions secrets of `Rampageboo/Nihilux`.
   - The Owner keeps an offline copy. Losing it means users must reinstall manually once.
   - Endpoint: `https://github.com/Rampageboo/Nihilux/releases/latest/download/latest.json`.
6. **CI builds releases:**
   - The `release.yml` mirrors Silverbench: tag `v*` → check the tag equals the app version → frontend checks → backend tests → stage → `tauri-action` build, sign and publish, with notes from `docs/releases/vX.Y.Z.md`.
   - Add `scripts/release.ps1` to bump the version in every place, commit, tag and push.
7. **Bundled integrations:**
   - The Photoshop plugin `.ccx` (rebuilt at the current version) and the Blender add-on ship in the install folder.
   - Settings gets "Install Photoshop plugin" (opens the `.ccx`), "Blender add-on folder", and "Copy MCP config". The last gives a ready `mcpServers` JSON whose command is the bundled `python.exe -m storyboard_tool.mcp_server`, so Claude Code or Codex can drive the installed app.
   - The repo's `.mcp.json` stays for development.
8. **Public repository with cleaned history:**
   - Create `Rampageboo/Nihilux` from history rewritten with `git filter-repo`. Remove `Sessions/`, `.qa-native-server/`, `graphify-out/`, generated `web/dist` bundles if large, and anything a secret scan (gitleaks or trufflehog over the full history) flags.
   - Verify the rewritten repo builds and tests pass before pushing.
   - The old `Rampageboo/Storyboarder` becomes private as the archive.
   - Both visibility steps (create public, make the old one private) are executed only after the Owner confirms the scan result.
9. **Version:** start at `0.1.0`. English UI, as now.

## Order (each step is one commit and passes `scripts/verify_dev.py`)

1. **Per-user state and bundled tools:**
   - `base_dir` selection;
   - `/api/health`;
   - ffmpeg/ffprobe lookup (bundled first);
   - window-focus behaviour without pywebview.
2. **Tauri shell:**
   - `src-tauri` with backend start/stop, the window, the updater UI (Settings: "Check for updates", plus a start-up notice);
   - the dev-run instructions.
3. **Packaging:**
   - `packaging/stage.ps1` (bundled Python with the deps installed, app code, built frontend, ffmpeg, the `.ccx`, the Blender add-on);
   - `tauri.release.conf.json`.
   - Then a local build: install into a clean folder, run, uninstall keeps user data.
4. **CI and release script:** `release.yml`, `scripts/release.ps1`, `docs/releases/v0.1.0.md`.
5. **Public repository:**
   - secret scan, `filter-repo`, verify, and the Owner's confirmation;
   - create `Rampageboo/Nihilux`, set the secrets, make the old repo private;
   - tag `v0.1.0`.
6. **Update proof:** bump to `0.1.1`, release, and confirm an installed `0.1.0` updates itself.
7. **Docs:** README (download and install, first run, SmartScreen note), `docs/current_architecture.md`, `DECISIONS.md`, `OWNER_HANDBOOK.md`.

## Risks

- **Unsigned installer:** SmartScreen warns on first install. A code-signing certificate is a separate purchase decision.
- **Name and icon:**
  - "Nihilux" and the icon art are derived from HoYoverse's Honkai: Star Rail character 虚照. The Owner chose this knowing HoYoverse could ask for removal or a rename.
  - Keep the icon pipeline (`storyboard_tool/assets/build_icon.py` + `icon_master.png`) so a replacement is a one-file swap.
- **Windows WebView2:** Tauri needs it. It ships with Windows 11; the NSIS installer should use the bootstrapper mode for older systems.
- **Antivirus false positives** on an unsigned app bundling Python. Mitigate with a clean, reproducible build in CI.
- **Photoshop plugin:** the `.ccx` must match backend protocol v2; the packaging step rebuilds it from the repo version.

## Verify

- Local:
  - stage and build the installer;
  - install to a clean folder, then open, create a project, add a board, set an image, run a Comfy image and a video take, render a sequence, export a PDF and open Blender;
  - call the MCP from "Copy MCP config";
  - uninstall keeps `%APPDATA%\StoryboardTool` and projects.
- CI: a tag build produces the installer, `.sig` and `latest.json`; the in-app updater moves `0.1.0` to `0.1.1`.
