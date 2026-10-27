fn main() {
    // Declaring the shell's own commands makes them subject to capabilities, which is
    // what lets the app page (served by the local backend, a remote origin to Tauri)
    // call them: see capabilities/app.json.
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "app_info",
            "runtime_status",
            "retry_backend",
            "prepare_for_update",
            "open_log_folder",
        ]),
    ))
    .expect("failed to run tauri-build");
}
