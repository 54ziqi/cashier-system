use tauri::Manager;
use std::process::Command;
use std::path::PathBuf;
use std::sync::Mutex;

struct SidecarProcess(Mutex<Option<std::process::Child>>);

#[tauri::command]
fn get_python_port() -> Result<String, String> {
    // TODO: 动态从 uvicorn 获取端口，后期调整配置机制
    Ok(format!("http://localhost:8000"))
}

#[tauri::command]
fn sidecar_status() -> String {
    // 返回 sidecar 进程运行状态
    "running".to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cmd| {
            let windows = app.get_webview_window("main");
            if let Some(w) = windows {
                let _ = w.show();
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarProcess(Mutex::new(None)))
        .setup(|app| {
            let sidecar_path = app.path().resource_dir()
                .map(|p| p.join("收银系统sidecar"))
                .ok_or("failed to resolve sidecar")?;

            // 启动 Python sidecar 进程
            if sidecar_path.exists() {
                let child = Command::new(&sidecar_path)
                    .arg("serve")
                    .arg("--port")
                    .arg("8000")
                    .spawn()
                    .map_err(|e| format!("failed to start sidecar: {}", e))?;

                let state = app.state::<SidecarProcess>();
                *state.0.lock().unwrap() = Some(child);
            } else {
                eprintln!("Sidecar not found at {:?}", sidecar_path);
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // 关闭窗口时优雅停止 sidecar
                let state = window.state::<SidecarProcess>();
                if let Some(mut child) = state.0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![get_python_port, sidecar_status])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
