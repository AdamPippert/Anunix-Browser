// Prevents an extra console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct Daemon(Mutex<Option<Child>>);

fn main() {
    tauri::Builder::default()
        .manage(Daemon(Mutex::new(None)))
        .setup(|app| {
            match Command::new("python3")
                .args(["-m", "anxbrowser.server"])
                .env("ANXB_HOST", "127.0.0.1")
                .env("ANXB_PORT", "9191")
                .spawn()
            {
                Ok(child) => {
                    *app.state::<Daemon>().0.lock().unwrap() = Some(child);
                    // Give the daemon a moment to bind before the WebView loads.
                    std::thread::sleep(std::time::Duration::from_millis(800));
                }
                Err(e) => {
                    eprintln!("anxbrowserd: failed to start: {e}");
                    eprintln!("Ensure python3 is in PATH and `anxbrowser` is installed.");
                    eprintln!("Tip: cd to repo root and run `make deps` first.");
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building Anunix Browser")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(mut child) = app_handle
                    .state::<Daemon>()
                    .0
                    .lock()
                    .unwrap()
                    .take()
                {
                    let _ = child.kill();
                }
            }
        });
}
