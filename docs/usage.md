# Usage

## 1. Install

Requirements:

- herdr 0.9.0 or later
- Python 3.8 or later; no third-party packages required. `python` must be on `PATH` on Windows; `python3` must be on `PATH` on Linux/macOS.

### Install from GitHub

```sh
herdr plugin install vrwolf1004/herdr-devrun
herdr plugin list                                 # Confirm herdr-devrun is enabled
```

- Run the same command again to update. Pin a version with `--ref <tag-or-commit>`.
- There is no build step; the downloaded files are used as-is.

### Link a local folder (development)

```sh
herdr plugin link C:\work\app\herdr-devrun   # On Linux/macOS, use the clone path
```

- `link` registers the folder without copying it. Changes are picked up the next time an action runs.
- If you change `herdr-plugin.toml` (for example, add an action), unlink and link the plugin again.

### Manage the plugin

- Unlink: `herdr plugin unlink herdr-devrun` (linked plugin) / uninstall: `herdr plugin uninstall herdr-devrun` (installed plugin)
- Temporarily disable: `herdr plugin disable herdr-devrun` / re-enable: `herdr plugin enable herdr-devrun`

## Display language

The dashboard and notifications support `en`, `ko`, `ru`, `fr`, `es`, `de`, and `ja`. The language is selected in this order:

1. `HERDR_DEVRUN_LANG` environment variable
2. `"lang"` in `HERDR_PLUGIN_CONFIG_DIR/config.json`
3. OS language (Windows user-interface language, or `LC_ALL`, `LC_MESSAGES`, then `LANG` on Linux/macOS)
4. English (`en`) if the OS language is unsupported or cannot be detected

For example, set `HERDR_DEVRUN_LANG=ko` to use Korean. Locale values such as `ko-KR` and `ko_KR.UTF-8` are recognized. An explicitly configured language takes precedence over the OS language. Missing translations fall back to English.

### Action IDs

herdr does not allow duplicate action IDs. The plugin declares the same behavior separately for each OS to use the appropriate executable (`python` or `python3`), and adds `-windows` to Windows action IDs. This follows conventions used by plugins such as herdr-file-viewer and herdr-sidebar.

The table uses Linux/macOS IDs. **On Windows, append `-windows`.**

| Linux / macOS | Windows | Description |
|---|---|---|
| `herdr-devrun.init` | `herdr-devrun.init-windows` | Create a draft configuration file |
| `herdr-devrun.up` | `herdr-devrun.up-windows` | Start services |
| `herdr-devrun.run` | `herdr-devrun.run-windows` | Start services (same behavior as `up`; not yet in `herdr-plugin.toml`) |
| `herdr-devrun.down` | `herdr-devrun.down-windows` | Stop services |
| `herdr-devrun.restart` | `herdr-devrun.restart-windows` | Restart services |
| `herdr-devrun.panel` | `herdr-devrun.panel-windows` | Open the dashboard |

## 2. Configure shortcuts

Add shortcuts to herdr's `config.toml` (on Windows: `%APPDATA%\herdr\config.toml`). This example is for Windows; omit `-windows` on Linux/macOS.

```toml
[[keys.command]]
key = "prefix+r"
type = "plugin_action"
command = "herdr-devrun.up-windows"
description = "devrun: start services"

[[keys.command]]
key = "prefix+d"
type = "plugin_action"
command = "herdr-devrun.panel-windows"
description = "devrun: dashboard"

[[keys.command]]
key = "prefix+shift+r"
type = "plugin_action"
command = "herdr-devrun.down-windows"
description = "devrun: stop services"
```

```sh
herdr config check          # Confirm the configuration is valid
herdr server reload-config  # Apply it to the running server
```

- Check that the keys do not conflict with existing bindings or other plugins.
- To run an action without a shortcut: `herdr plugin action invoke herdr-devrun.up` (uses the currently focused pane).

## 3. Create a project configuration

1. Open a pane in herdr with its working directory at the project root.
2. Run the `init` action.
3. A `.herdr-devrun.json` file is created in the project root. A notification shows how many services were detected.
4. Edit the commands, folders, ports, and environment variables to match your project.

`init` scans the project root and its immediate child folders. It creates at most one service per folder, using the first matching rule:

| Detected file | Generated command (Windows / Linux and macOS) |
|---|---|
| `gradlew.bat` or `gradlew` | `.\gradlew.bat bootRun` / `./gradlew bootRun` |
| `mvnw.cmd` or `mvnw` | `.\mvnw.cmd spring-boot:run` / `./mvnw spring-boot:run` |
| `package.json` with a `dev`, `start`, or `serve` script | `pnpm` / `yarn` / `npm run <script>` (selected using lock files) |

- `init` writes a command for the current OS. To share a configuration across operating systems, add `command_windows` and/or `command_unix` (see section 4).
- Gradle and Maven services get the Spring Boot defaults `port: 8080` and `url: http://localhost:8080`. Change them if your service uses another port.
- For multi-module Gradle projects or pnpm monorepos that need a specific app selected, edit the generated command.

## 4. Configuration format

```json
{
  "tab": "my-project",
  "services": [
    {
      "name": "backend",
      "cwd": "backend",
      "command": "./gradlew bootRun",
      "command_windows": ".\\gradlew.bat bootRun",
      "port": 8080,
      "url": "http://localhost:8080",
      "env": { "SPRING_PROFILES_ACTIVE": "local" },
      "stop_timeout": 20
    },
    {
      "name": "frontend",
      "cwd": "frontend",
      "command": "npm run dev",
      "port": 5173,
      "url": "http://localhost:5173",
      "depends_on": ["backend"]
    }
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `tab` | | Tab name; defaults to the project folder name |
| `services` | Yes | One or more services, arranged into panes in order |
| `services[].name` | Yes | Pane name. Must be unique; it is also used in notifications and state |
| `services[].command` | Yes | Command entered directly into the pane shell (PowerShell on Windows; default shell on Linux/macOS) |
| `services[].command_windows` | | Command to use instead of `command` on Windows |
| `services[].command_unix` | | Command to use instead of `command` on Linux/macOS |
| `services[].cwd` | | Path relative to the configuration file (absolute paths are also allowed). Defaults to the project root; an invalid path is an error |
| `services[].env` | | Environment variables for the pane process, as `"KEY": "VALUE"` |
| `services[].port` | | TCP port used to distinguish "starting" from "running". The service will not start if the port is already in use |
| `services[].url` | | URL opened by the dashboard's Browser button (`o`) |
| `services[].depends_on` | | Services that must be ready first; controls start-all ordering (see section 5) |
| `services[].start_timeout` | | Maximum seconds to wait for dependencies; default: 120 |
| `services[].stop_timeout` | | Maximum seconds to wait for process exit after Ctrl+C; default: 10 |

Writing tips:

- In JSON strings, escape `\` as `\\` and `"` as `\"`. For example: `".\\gradlew.bat bootRun"`.
- Join multiple commands with `;` (supported by PowerShell, bash, and zsh). For example: `"pnpm install; pnpm run dev"`.
- If commands differ by OS, put one in `command` and the other in `command_windows` or `command_unix`. If they are the same, use only `command`.
- Do not put secrets such as encryption keys or passwords in `env`. Use OS environment variables instead. Configuration files may be committed to Git.
- To keep the configuration out of a shared repository, add `.herdr-devrun.json` to the project's `.gitignore`.
- Validation reports non-numeric `stop_timeout`/`start_timeout`, unknown `depends_on` services, and dependency cycles (including self-dependencies).

> **Security:** `command` is entered directly into a shell. Running `up` on an untrusted repository executes commands defined by that repository, similar to running its npm scripts or Makefile. Review `.herdr-devrun.json` before running an unfamiliar project.

## 5. Start and stop services

| Goal | Action | Behavior |
|---|---|---|
| Start services | `up` (or `run`, planned alias) | Start services that are not running, in `depends_on` order. If all are running, switch to their tab |
| Stop services | `down` | Send Ctrl+C to each pane, wait for processes to exit (up to `stop_timeout`), then close the tab |
| Restart | `restart` | Run down, then up. Also use it to apply configuration changes |

- Actions search for the configuration file by walking **up** from the folder of the pane where the action was run. They can be run from a subfolder within the project.
- `up` starts only services that are not already running. If some are running, the remaining ones are added to the same tab.
- Use the dashboard (section 6) to manage an individual service.
- You can close a tab or pane manually. The next run detects removed panes and cleans up the state.

### Start order (`depends_on`)

- A dependent service starts when its dependencies are **ready**. If a dependency has a `port`, readiness means that port is open (a server started elsewhere also qualifies); without a port, readiness means the service is running.
- If a dependency exits (✕), a waiting service is not started and is reported as "dependency failed". A service just started by the current plan is given a 5-second grace period before it can be considered failed.
- If a dependency is not ready within `start_timeout` (default: 120 seconds), the dependent service is not started and is reported as timed out.
- Services that could not start are reported in a notification (and in the dashboard's message line), for example: `web (dependency failed), late (timed out waiting for dependencies)`.
- Starting a **single** service from the dashboard does not wait for its dependencies; the user explicitly selected it.

### Port conflicts

- If another process already uses a configured `port`, that service is not started. Otherwise the attempted launch may fail while the open port makes the service appear to be running.
- During start-all, only the service with the conflict is skipped (`port in use`); other services continue starting.

### Stop timeout

- After sending Ctrl+C, the plugin checks every 0.2 seconds whether the process beneath the pane shell has exited. It closes the pane/tab as soon as it exits, or after `stop_timeout` (default: 10 seconds). Remaining processes are terminated with the pane.
- Increase `stop_timeout` for services that need more time for a graceful shutdown, such as Spring Boot.
- A Windows `.bat` file waiting at "Terminate batch job (Y/N)?" after Ctrl+C is treated as stopped.

## 6. Dashboard

Run the `panel` action to split a pane to the right of the current pane and run the dashboard there. The pane uses the project root as its working directory. If a dashboard for the same project is already running, the action focuses its tab instead of opening another one.

The dashboard runs as a command in the pane's shell. Pressing Ctrl+C stops it and returns to the shell prompt; it does not close the pane. The next `panel` action opens a fresh dashboard.

```text
 ▣ devrun · my-project                                  2/3 running

   Status      Service                                    Port
 ▸ ● Running   backend                                    :8080
   ◐ Starting  frontend                                   :5173
   ○ Stopped   worker

  ■ Stop   ↻ Restart   Start all   Stop all   Browser   Settings   Close

─ Logs · backend ──────────────────────────────────────────────
 Started Application in 4.2 seconds
```

### Status

| Indicator | Meaning | Detection |
|---|---|---|
| ● Running | Active | A process is running under the pane shell and, if configured, `port` is open. Without a port, only the process is checked |
| ◐ Starting | Starting up | A process exists, but the configured `port` is not open yet |
| ✕ Exited | Command finished | The pane remains, but only its shell is running. Check the logs for failure or completion |
| ○ Stopped | Not running | No pane exists |
| ◔ Waiting | Waiting for `depends_on` during start-all | |
| … Working | Dashboard is starting or stopping a service | |

### Controls

| Goal | Mouse | Key |
|---|---|---|
| Select a service | Click a row or use the wheel | `↑` `↓` `Home` `End` |
| Start/stop selected service | Double-click a row or use the Start/Stop button | `Enter` |
| Restart selected service | Restart button | `r` |
| Start all / stop all | Buttons | `a` / `x` |
| Open the service URL | Browser button | `o` |
| Open the configuration file | Settings button | `e` |
| Close dashboard | Close button | `q`, `Esc`, `Ctrl+C` |

- Shortcuts also work while a Korean keyboard layout is active (`ㄱ=r`, `ㅁ=a`, `ㅌ=x`, `ㅐ=o`, `ㄷ=e`, `ㅂ=q`).
- Status and log previews refresh every second. The log preview shows the selected service's recent output; wrapped pane lines are displayed as their original single lines.
- Start-all accepts input while it waits. Selecting Stop all during startup cancels remaining starts.
- If the service list exceeds the screen, it scrolls with the selected row and shows `▲ n more` / `▼ n more` indicators.
- At widths below 40 columns, the port column is hidden; below 30 columns, status names are replaced by icons.
- Unexpected errors do not close the dashboard. A summary appears on the message line, with details in `panel.log` in the state directory.
- Saving the configuration reloads it automatically. If it is invalid, an error appears and the previous configuration remains active.
- The configuration opens with the OS default application (Windows: file association, or Notepad; macOS: `open`; Linux: `xdg-open`).
- Stopping a service closes only its pane. Stopping the last service also closes the service tab.
- Restart closes and recreates the pane. Windows batch files such as `gradlew.bat` may prompt "Terminate batch job?" after Ctrl+C, so the command is not run again in the same pane.
- Closing the dashboard does not stop services.

## 7. Examples

### Spring Boot (Gradle multi-module) + React (pnpm monorepo)

```json
{
  "tab": "office-dev",
  "services": [
    {
      "name": "BE manager",
      "cwd": "office-be",
      "command": "./gradlew :app-manager:bootRun",
      "command_windows": ".\\gradlew.bat :app-manager:bootRun",
      "port": 5002,
      "env": { "SPRING_PROFILES_ACTIVE": "local" }
    },
    {
      "name": "FE manager",
      "cwd": "office-fe",
      "command": "pnpm --filter @office/web-manager run dev",
      "port": 6000,
      "url": "http://localhost:6000"
    }
  ]
}
```

### Multiple backends and a frontend

```json
{
  "services": [
    { "name": "api",   "cwd": "api",   "command": "./mvnw spring-boot:run", "command_windows": ".\\mvnw.cmd spring-boot:run", "port": 8080 },
    { "name": "batch", "cwd": "batch", "command": "./mvnw spring-boot:run", "command_windows": ".\\mvnw.cmd spring-boot:run", "port": 8081 },
    { "name": "web",   "cwd": "web",   "command": "npm run dev", "port": 5173 }
  ]
}
```

Layout: `api` is on the left; `batch` and `web` are stacked from top to bottom on the right.

### Passing arguments to Spring Boot

```json
{ "name": "api", "command": "./gradlew bootRun --args=\"--server.port=8081\"", "port": 8081 }
```

## 8. Manual run (without herdr actions)

```sh
# From the plugin folder. Windows: python; Linux/macOS: python3
python -X utf8 src/devrun.py up --dir <project-folder>     # up / down / restart / init
python -X utf8 src/panel.py --dir <project-folder>         # Run the dashboard in the current terminal
```

- Use this to test code changes or inspect action failures directly in the console. herdr CLI must be able to connect to the server, so run it from a pane inside herdr.
- Manual-run state is stored in `%LOCALAPPDATA%\herdr-devrun` on Windows, or `~/.local/state/herdr-devrun` (or `$XDG_STATE_HOME/herdr-devrun`) on Linux/macOS. This is separate from action state (`HERDR_PLUGIN_STATE_DIR`); stop manually started services with a manual `down`.

## Documentation

- [Usage (한국어)](usage.ko.md)
- [Troubleshooting](troubleshooting.md): common problems (Korean)
- [Architecture](architecture.md): design details (Korean)
- [Development](development.md): code layout, tests, adding config items and actions (Korean)
- [Design and scope](start-idea.md) (Korean)
- [TODO](todo.md): improvement list (Korean)
