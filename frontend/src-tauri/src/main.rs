use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{Manager, State};

struct EngineProcess {
    origin: String,
    bootstrap_secret: String,
    child: Mutex<Option<Child>>,
}

impl Drop for EngineProcess {
    fn drop(&mut self) {
        if let Ok(child) = self.child.get_mut() {
            if let Some(mut process) = child.take() {
                let _ = process.kill();
                let _ = process.wait();
            }
        }
    }
}

#[tauri::command]
fn local_api_origin(engine: State<'_, EngineProcess>) -> String {
    engine.origin.clone()
}

#[tauri::command]
fn local_api_bootstrap_secret(engine: State<'_, EngineProcess>) -> String {
    engine.bootstrap_secret.clone()
}

fn create_bootstrap_secret() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    getrandom::fill(&mut bytes).map_err(|error| error.to_string())?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

fn reserve_loopback_port() -> Result<u16, String> {
    let listener = TcpListener::bind(("127.0.0.1", 0)).map_err(|error| error.to_string())?;
    listener
        .local_addr()
        .map(|address| address.port())
        .map_err(|error| error.to_string())
}

fn project_root() -> Result<PathBuf, String> {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|frontend| frontend.parent())
        .map(PathBuf::from)
        .ok_or_else(|| "Racine du projet introuvable".to_string())
}

fn spawn_engine(app: &tauri::AppHandle, port: u16, bootstrap_secret: &str) -> Result<Child, String> {
    let (program, args, working_directory) = if cfg!(debug_assertions) {
        let python = std::env::var("VALORIA_PYTHON_BIN").unwrap_or_else(|_| "python".to_string());
        (
            PathBuf::from(python),
            vec!["-m".to_string(), "app.api.run".to_string()],
            project_root()?,
        )
    } else {
        let executable = if cfg!(target_os = "windows") {
            "valoria-engine.exe"
        } else {
            "valoria-engine"
        };
        let resource_dir = app.path().resource_dir().map_err(|error| error.to_string())?;
        (
            resource_dir.join("bin").join(executable),
            Vec::new(),
            resource_dir,
        )
    };

    Command::new(program)
        .args(args)
        .current_dir(working_directory)
        .env("VALORIA_API_PORT", port.to_string())
        .env("VALORIA_API_BOOTSTRAP_SECRET", bootstrap_secret)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("Impossible de démarrer le moteur Python : {error}"))
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            local_api_origin,
            local_api_bootstrap_secret
        ])
        .setup(|app| {
            let port = reserve_loopback_port().map_err(std::io::Error::other)?;
            let bootstrap_secret = create_bootstrap_secret().map_err(std::io::Error::other)?;
            let child = spawn_engine(app.handle(), port, &bootstrap_secret)
                .map_err(std::io::Error::other)?;
            app.manage(EngineProcess {
                origin: format!("http://127.0.0.1:{port}"),
                bootstrap_secret,
                child: Mutex::new(Some(child)),
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("échec de l’enveloppe desktop Valoria Vision");
}
