use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, RunEvent,
};

/// 全局后端进程句柄
struct BackendProcess(Mutex<Option<std::process::Child>>);

/// 获取可用端口
fn find_available_port() -> u16 {
    portpicker::pick_unused_port().unwrap_or(8778)
}

/// 启动Python后端
#[tauri::command]
fn start_backend(app: tauri::AppHandle, port: u16) -> Result<String, String> {
    let state = app.state::<BackendProcess>();
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;

    // 如果已有进程在运行，先停止
    if let Some(ref mut child) = *guard {
        let _ = child.kill();
        let _ = child.wait();
        *guard = None;
    }

    // 确定后端可执行文件路径
    let backend_path = if cfg!(debug_assertions) {
        // 开发模式: 使用项目内Python直接运行
        let exe_dir = std::env::current_exe()
            .map_err(|e| e.to_string())?
            .parent()
            .map(|p| p.to_path_buf())
            .unwrap_or_default();
        // 尝试多种路径
        let candidates = vec![
            exe_dir.join("../../python/python.exe"),
            exe_dir.join("../../../python/python.exe"),
            std::path::PathBuf::from("D:/元初系统/天机v9.1/python/python.exe"),
        ];
        let mut found = std::path::PathBuf::from("python");
        for candidate in candidates {
            if candidate.exists() {
                found = candidate;
                break;
            }
        }
        found
    } else {
        // 生产模式: 使用sidecar或嵌入的后端
        let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
        let sidecar = resource_dir.join("binaries").join("tianji-backend.exe");
        if sidecar.exists() {
            sidecar
        } else {
            // 回退: 使用Python解释器
            let python_path = resource_dir.join("python").join("python.exe");
            if python_path.exists() {
                python_path
            } else {
                std::path::PathBuf::from("python")
            }
        }
    };

    let server_path = if cfg!(debug_assertions) {
        let exe_dir = std::env::current_exe()
            .map_err(|e| e.to_string())?
            .parent()
            .map(|p| p.to_path_buf())
            .unwrap_or_default();
        let candidates = vec![
            exe_dir.join("../../server/main.py"),
            exe_dir.join("../../../server/main.py"),
            std::path::PathBuf::from("D:/元初系统/天机v9.1/server/main.py"),
        ];
        let mut found = std::path::PathBuf::from("server/main.py");
        for candidate in candidates {
            if candidate.exists() {
                found = candidate;
                break;
            }
        }
        found
    } else {
        let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
        resource_dir.join("server").join("main.py")
    };

    let root_dir = server_path
        .parent()
        .and_then(|p| p.parent())
        .map(|p| p.to_path_buf())
        .unwrap_or_default();

    // 构建启动命令
    let is_compiled = backend_path
        .file_name()
        .map(|n| n.to_string_lossy().contains("tianji-backend"))
        .unwrap_or(false);

    let child = if is_compiled {
        std::process::Command::new(&backend_path)
            .env("AI_MEMORY_PORT", port.to_string())
            .env("AI_MEMORY_ROOT", &root_dir)
            .env("TIANJI_EDITION", "compiled-exe")
            .spawn()
            .map_err(|e| format!("启动后端失败: {}", e))?
    } else {
        std::process::Command::new(&backend_path)
            .arg("-m")
            .arg("uvicorn")
            .arg("server.main:app")
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg(port.to_string())
            .env("AI_MEMORY_PORT", port.to_string())
            .env("AI_MEMORY_ROOT", &root_dir)
            .current_dir(&root_dir)
            .spawn()
            .map_err(|e| format!("启动后端失败: {}", e))?
    };

    *guard = Some(child);
    Ok(format!("http://127.0.0.1:{}", port))
}

/// 停止Python后端
#[tauri::command]
fn stop_backend(app: tauri::AppHandle) -> Result<(), String> {
    let state = app.state::<BackendProcess>();
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut child) = *guard {
        let _ = child.kill();
        let _ = child.wait();
        *guard = None;
    }
    Ok(())
}

/// 获取后端状态
#[tauri::command]
fn backend_status(app: tauri::AppHandle) -> Result<bool, String> {
    let state = app.state::<BackendProcess>();
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;

    match *guard {
        Some(ref mut child) => Ok(matches!(
            child.try_wait(),
            Ok(None) // 进程仍在运行
        )),
        None => Ok(false),
    }
}

/// 获取后端端口
#[tauri::command]
fn get_backend_port() -> u16 {
    find_available_port()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            // 日志插件(仅调试模式)
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // 系统托盘
            let show_item = MenuItem::with_id(app, "show", "显示天机", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "退出天机", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("天机v9.1 · AI智能记忆平台")
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => {
                        // 停止后端进程
                        let state = app.state::<BackendProcess>();
                        if let Ok(mut guard) = state.0.lock() {
                            if let Some(ref mut child) = *guard {
                                let _ = child.kill();
                                let _ = child.wait();
                            }
                            *guard = None;
                        }
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            // 自动启动后端
            let port = find_available_port();
            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                // 等待前端加载
                std::thread::sleep(std::time::Duration::from_secs(2));
                let _ = start_backend(app_handle, port);
            });

            Ok(())
        })
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            backend_status,
            get_backend_port,
        ])
        .build(tauri::generate_context!())
        .expect("构建天机应用失败")
        .run(|_app_handle, event| {
            if let RunEvent::ExitRequested { api, .. } = event {
                // 阻止默认退出，最小化到托盘
                api.prevent_exit();
            }
        });
}
