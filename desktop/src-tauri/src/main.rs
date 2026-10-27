#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! Nihilux desktop shell: starts the Python backend and shows the app.
//!
//! The window first shows the bundled start-up page (`desktop/splash`). The shell
//! starts `python -m storyboard_tool.server` with a per-launch API token, reads the
//! `PORT:<n>` line it prints, waits for `GET /api/health`, then points the window at
//! the backend, which serves the React app.
//!
//! Two layouts:
//! - **Installed** (`<install>/app/storyboard_tool/server.py`): the bundled CPython in
//!   `<install>/python`, per-user state in `%APPDATA%\StoryboardTool`, logs in
//!   `%LOCALAPPDATA%\StoryboardTool\logs`. An update replaces the install folder.
//! - **Source checkout** (development, `npm run dev` in `desktop/`): the repository's
//!   `.venv` (or `NIHILUX_PYTHON`), state in the checkout as before.
//!
//! The backend is stopped with `POST /api/app/shutdown` so its own cleanup runs; it is
//! killed only if it does not exit in time. The shell does not end the backend's whole
//! process tree: Photoshop and Blender, opened from the app, are children of the
//! backend and may hold unsaved work. Before an update, every process running from the
//! install folder (the backend, its ffmpeg, MCP servers on the bundled Python) is
//! stopped so the installer can replace the files.

use std::{
    collections::hash_map::RandomState,
    hash::{BuildHasher, Hasher},
    io::{BufRead, BufReader, Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{mpsc, Mutex, OnceLock},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tauri::{AppHandle, Manager, Url};
use tauri_plugin_window_state::{AppHandleExt, StateFlags, WindowExt};

#[cfg(windows)]
use std::os::windows::process::CommandExt;
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

const PORT_TIMEOUT: Duration = Duration::from_secs(120);
const HEALTH_TIMEOUT: Duration = Duration::from_secs(60);
const SHUTDOWN_GRACE: Duration = Duration::from_secs(8);

#[derive(Default)]
struct Backend {
    child: Option<Child>,
    port: u16,
    token: String,
}

struct BackendState(Mutex<Backend>);

#[derive(Clone)]
struct RuntimeInfo {
    packaged: bool,
    /// starting | running | failed | stopped-for-update
    phase: String,
    error: Option<String>,
    log_dir: Option<PathBuf>,
    /// The start-up page's own address, to return to while the backend restarts.
    splash_url: Option<Url>,
}

struct Runtime(Mutex<RuntimeInfo>);

#[derive(Clone)]
enum Layout {
    Installed { root: PathBuf, app: PathBuf, python: PathBuf, data: PathBuf, logs: PathBuf },
    Checkout { root: PathBuf },
}

impl Layout {
    fn code_root(&self) -> &Path {
        match self {
            Layout::Installed { app, .. } => app,
            Layout::Checkout { root } => root,
        }
    }

    fn base_dir(&self) -> PathBuf {
        match self {
            Layout::Installed { data, .. } => data.clone(),
            Layout::Checkout { root } => root.clone(),
        }
    }

    fn log_dir(&self) -> PathBuf {
        match self {
            Layout::Installed { logs, .. } => logs.clone(),
            Layout::Checkout { root } => root.join("logs"),
        }
    }
}

static STARTED: OnceLock<Instant> = OnceLock::new();

fn main() {
    STARTED.get_or_init(Instant::now);
    tauri::Builder::default()
        // First: a second launch focuses the running window instead of starting a second backend.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(BackendState(Mutex::new(Backend::default())))
        .manage(Runtime(Mutex::new(RuntimeInfo {
            packaged: false,
            phase: "starting".into(),
            error: None,
            log_dir: None,
            splash_url: None,
        })))
        .invoke_handler(tauri::generate_handler![
            app_info,
            runtime_status,
            retry_backend,
            prepare_for_update,
            open_log_folder
        ])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.restore_state(StateFlags::all() & !StateFlags::VISIBLE);
                if let Ok(url) = window.url() {
                    app.state::<Runtime>().0.lock().expect("runtime lock").splash_url = Some(url);
                }
                let _ = window.show();
            }
            start_backend(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build the Nihilux shell")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                let _ = app_handle.save_window_state(StateFlags::all());
                stop_backend(app_handle);
            }
        });
}

fn layout(app: &AppHandle) -> Result<Layout, String> {
    // An exe built inside a checkout also gets the bundle resources copied next to it;
    // it keeps using the checkout, so the exe's location decides first.
    if let Ok(exe) = std::env::current_exe() {
        if let Some(root) = exe.ancestors().skip(1).find(|dir| is_code_root(dir)) {
            return Ok(Layout::Checkout { root: root.to_path_buf() });
        }
    }
    if let Ok(resources) = app.path().resource_dir().map(plain_path) {
        let bundled = resources.join("app");
        if is_code_root(&bundled) {
            let roaming = std::env::var_os("APPDATA").map(PathBuf::from).ok_or("APPDATA is not set")?;
            let local = std::env::var_os("LOCALAPPDATA").map(PathBuf::from).ok_or("LOCALAPPDATA is not set")?;
            return Ok(Layout::Installed {
                root: resources.clone(),
                app: bundled,
                python: resources.join("python").join("python.exe"),
                data: roaming.join("StoryboardTool"),
                logs: local.join("StoryboardTool").join("logs"),
            });
        }
    }
    if let Ok(cwd) = std::env::current_dir() {
        if let Some(root) = cwd.ancestors().find(|dir| is_code_root(dir)) {
            return Ok(Layout::Checkout { root: root.to_path_buf() });
        }
    }
    Err("Could not find the Nihilux backend (storyboard_tool/server.py).".into())
}

/// `\\?\C:\...` -> `C:\...`: the resource dir comes back as a verbatim path, which
/// would leak into sys.executable and the MCP config the app hands out.
fn plain_path(path: PathBuf) -> PathBuf {
    let text = path.to_string_lossy().into_owned();
    match text.strip_prefix(r"\\?\") {
        Some(rest) if !rest.starts_with(r"UNC\") => PathBuf::from(rest),
        _ => path,
    }
}

fn is_code_root(dir: &Path) -> bool {
    dir.join("storyboard_tool").join("server.py").is_file()
}

fn set_phase(app: &AppHandle, phase: &str, error: Option<String>) {
    let runtime = app.state::<Runtime>();
    let mut info = runtime.0.lock().expect("runtime lock");
    info.phase = phase.into();
    info.error = error;
}

/// Start (or restart) the backend off the UI thread and point the window at it.
fn start_backend(app: AppHandle) {
    {
        let runtime = app.state::<Runtime>();
        let info = runtime.0.lock().expect("runtime lock").clone();
        if let (Some(url), Some(window)) = (info.splash_url, app.get_webview_window("main")) {
            if window.url().map(|current| current.origin() != url.origin()).unwrap_or(false) {
                let _ = window.navigate(url);
            }
        }
    }
    set_phase(&app, "starting", None);
    std::thread::spawn(move || {
        let result = (|| -> Result<String, String> {
            let layout = layout(&app)?;
            shell_log(&layout, "starting the backend");
            {
                let runtime = app.state::<Runtime>();
                let mut info = runtime.0.lock().expect("runtime lock");
                info.packaged = matches!(layout, Layout::Installed { .. });
                info.log_dir = Some(layout.log_dir());
            }
            let token = random_token();
            let (child, port) = spawn_backend(&layout, &token)?;
            shell_log(&layout, &format!("backend listening on port {port}"));
            {
                let state = app.state::<BackendState>();
                let mut backend = state.0.lock().expect("backend lock");
                *backend = Backend { child: Some(child), port, token };
            }
            wait_for_health(port)?;
            shell_log(&layout, "backend healthy");
            Ok(format!("http://127.0.0.1:{port}/"))
        })();
        match result {
            Ok(url) => {
                set_phase(&app, "running", None);
                if let (Some(window), Ok(url)) = (app.get_webview_window("main"), Url::parse(&url)) {
                    let _ = window.navigate(url);
                }
            }
            Err(error) => {
                stop_backend(&app);
                set_phase(&app, "failed", Some(error));
            }
        }
    });
}

fn spawn_backend(layout: &Layout, token: &str) -> Result<(Child, u16), String> {
    let logs = layout.log_dir();
    let _ = std::fs::create_dir_all(&logs);
    let log_path = logs.join("backend.log");
    // Keep one session's worth plus the previous one.
    if std::fs::metadata(&log_path).map(|m| m.len() > 5 * 1024 * 1024).unwrap_or(false) {
        let _ = std::fs::rename(&log_path, logs.join("backend.previous.log"));
    }
    let root = layout.code_root();
    let base_dir = layout.base_dir();
    let _ = std::fs::create_dir_all(&base_dir);
    let (program, prefix) = python_command(layout)?;

    let mut command = Command::new(&program);
    command
        .args(&prefix)
        .arg("-m")
        .arg("storyboard_tool.server")
        .arg("--base-dir")
        .arg(&base_dir)
        .current_dir(root)
        .env("PYTHONPATH", root)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUNBUFFERED", "1")
        .env("STORYBOARDER_LAUNCH_TOKEN", token)
        .env("STORYBOARDER_WINDOW_PID", std::process::id().to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(log_sink(&log_path));
    if let Layout::Installed { .. } = layout {
        // The bundled Python must not pick up packages from the user's own Python.
        command.env("PYTHONNOUSERSITE", "1").env_remove("PYTHONHOME");
    }
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    let mut child = command
        .spawn()
        .map_err(|err| format!("Could not start Python ({}): {err}", program.display()))?;

    // The first stdout line is PORT:<n>; everything after it goes to the log.
    let stdout = child.stdout.take().ok_or("backend stdout unavailable")?;
    let (sender, receiver) = mpsc::channel::<u16>();
    let log_for_reader = log_path.clone();
    std::thread::spawn(move || {
        let mut sink = std::fs::OpenOptions::new().create(true).append(true).open(&log_for_reader).ok();
        let mut sent = false;
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if !sent {
                if let Some(port) = line.trim().strip_prefix("PORT:").and_then(|p| p.parse::<u16>().ok()) {
                    let _ = sender.send(port);
                    sent = true;
                    continue;
                }
            }
            if let Some(file) = sink.as_mut() {
                let _ = writeln!(file, "{line}");
            }
        }
    });

    let deadline = Instant::now() + PORT_TIMEOUT;
    loop {
        match receiver.recv_timeout(Duration::from_millis(200)) {
            Ok(port) => return Ok((child, port)),
            Err(mpsc::RecvTimeoutError::Timeout) => {
                if let Ok(Some(status)) = child.try_wait() {
                    return Err(format!(
                        "The backend stopped during start-up ({status}). Details: {}",
                        log_path.display()
                    ));
                }
                if Instant::now() > deadline {
                    let _ = child.kill();
                    return Err(format!("The backend did not start in time. Details: {}", log_path.display()));
                }
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                let _ = child.wait();
                return Err(format!("The backend stopped during start-up. Details: {}", log_path.display()));
            }
        }
    }
}

/// Start-up milestones in `<logs>/shell.log`, to tell a slow start from a failed one.
fn shell_log(layout: &Layout, message: &str) {
    let dir = layout.log_dir();
    let _ = std::fs::create_dir_all(&dir);
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(dir.join("shell.log")) {
        let secs = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0);
        let since_start = STARTED.get().map(|t| t.elapsed().as_secs_f64()).unwrap_or(0.0);
        let _ = writeln!(file, "{secs:.3} [{}] +{since_start:.2}s {message}", std::process::id());
    }
}

fn python_command(layout: &Layout) -> Result<(PathBuf, Vec<String>), String> {
    match layout {
        Layout::Installed { python, .. } => {
            if python.is_file() {
                Ok((python.clone(), Vec::new()))
            } else {
                Err(format!("The bundled Python is missing: {}. Reinstall Nihilux.", python.display()))
            }
        }
        Layout::Checkout { root } => {
            if let Some(custom) = std::env::var_os("NIHILUX_PYTHON") {
                return Ok((PathBuf::from(custom), Vec::new()));
            }
            let venv = root.join(".venv").join("Scripts").join("python.exe");
            if venv.is_file() {
                return Ok((venv, Vec::new()));
            }
            for (program, prefix) in [("py", vec!["-3".to_string()]), ("python", Vec::new())] {
                let ok = Command::new(program)
                    .args(&prefix)
                    .arg("--version")
                    .stdin(Stdio::null())
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .status()
                    .map(|s| s.success())
                    .unwrap_or(false);
                if ok {
                    return Ok((PathBuf::from(program), prefix));
                }
            }
            Err("No Python found: create .venv (run.bat) or set NIHILUX_PYTHON.".into())
        }
    }
}

fn log_sink(path: &Path) -> Stdio {
    std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map(Stdio::from)
        .unwrap_or_else(|_| Stdio::null())
}

fn wait_for_health(port: u16) -> Result<(), String> {
    let deadline = Instant::now() + HEALTH_TIMEOUT;
    while Instant::now() < deadline {
        if let Some((status, body)) = http_request(port, "GET", "/api/health", None) {
            if status == 200 && body.contains("\"ok\":true") {
                return Ok(());
            }
        }
        std::thread::sleep(Duration::from_millis(150));
    }
    Err("The backend started but did not answer its health check.".into())
}

/// Minimal HTTP/1.1 client for the loopback backend (health check and shutdown).
fn http_request(port: u16, method: &str, path: &str, token: Option<&str>) -> Option<(u16, String)> {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_millis(500)).ok()?;
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let mut request = format!("{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\nContent-Length: 0\r\n");
    if let Some(token) = token {
        request.push_str(&format!("x-storyboarder-token: {token}\r\n"));
    }
    request.push_str("\r\n");
    stream.write_all(request.as_bytes()).ok()?;
    let mut response = String::new();
    stream.read_to_string(&mut response).ok()?;
    let status = response.split_whitespace().nth(1)?.parse().ok()?;
    let body = response.split_once("\r\n\r\n").map(|(_, b)| b.to_string()).unwrap_or_default();
    Some((status, body))
}

/// Ask the backend to exit (its lifespan cleanup runs), then kill it if it hangs.
fn stop_backend(app: &AppHandle) {
    let backend = std::mem::take(&mut *app.state::<BackendState>().0.lock().expect("backend lock"));
    let Some(mut child) = backend.child else { return };
    if backend.port > 0 {
        let _ = http_request(backend.port, "POST", "/api/app/shutdown", Some(&backend.token));
        let deadline = Instant::now() + SHUTDOWN_GRACE;
        while Instant::now() < deadline {
            if let Ok(Some(_)) = child.try_wait() {
                return;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    }
    let _ = child.kill();
    let _ = child.wait();
}

/// Before an update: nothing may run from the install folder except this shell.
fn stop_install_folder_processes(root: &Path) {
    #[cfg(windows)]
    {
        let script = format!(
            "$root = '{}'; Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -and $_.ProcessId -ne {} -and $_.ExecutablePath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}",
            root.display().to_string().replace('\'', "''").trim_end_matches('\\'),
            std::process::id()
        );
        let _ = Command::new("powershell")
            .args(["-NoProfile", "-NonInteractive", "-Command", &script])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
    #[cfg(not(windows))]
    let _ = root;
}

fn random_token() -> String {
    // RandomState is seeded from the OS's random source; hashing a few values
    // through it gives an unguessable token without another dependency.
    let nanos = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
    let mut token = String::new();
    for round in 0..3u64 {
        let mut hasher = RandomState::new().build_hasher();
        hasher.write_u64(round);
        hasher.write_u128(nanos);
        hasher.write_u32(std::process::id());
        token.push_str(&format!("{:016x}", hasher.finish()));
    }
    token
}

#[tauri::command]
fn app_info(app: AppHandle) -> serde_json::Value {
    let packaged = app.state::<Runtime>().0.lock().expect("runtime lock").packaged;
    serde_json::json!({ "version": app.package_info().version.to_string(), "packaged": packaged })
}

#[tauri::command]
fn runtime_status(app: AppHandle) -> serde_json::Value {
    let info = app.state::<Runtime>().0.lock().expect("runtime lock").clone();
    serde_json::json!({
        "version": app.package_info().version.to_string(),
        "packaged": info.packaged,
        "phase": info.phase,
        "error": info.error,
        "logDir": info.log_dir.map(|p| p.display().to_string()),
    })
}

#[tauri::command]
fn retry_backend(app: AppHandle) {
    let phase = app.state::<Runtime>().0.lock().expect("runtime lock").phase.clone();
    // Also after an update that stopped the backend and then failed to install.
    if phase == "failed" || phase == "stopped-for-update" {
        start_backend(app);
    }
}

/// Stop the backend and everything else running from the install folder so the
/// installer can replace the files. The page stays usable for the progress display.
#[tauri::command]
async fn prepare_for_update(app: AppHandle) {
    stop_backend(&app);
    if let Ok(Layout::Installed { root, .. }) = layout(&app) {
        stop_install_folder_processes(&root);
    }
    set_phase(&app, "stopped-for-update", None);
}

#[tauri::command]
fn open_log_folder(app: AppHandle) {
    let dir = app.state::<Runtime>().0.lock().expect("runtime lock").log_dir.clone();
    if let Some(dir) = dir {
        let _ = std::fs::create_dir_all(&dir);
        let _ = Command::new("explorer").arg(dir).spawn();
    }
}
