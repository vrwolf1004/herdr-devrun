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
| `herdr-devrun.run` | `herdr-devrun.run-windows` | Start services (same behavior as `up`) |
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
- To run an action without a shortcut: `herdr plugin action invoke up --plugin herdr-devrun` or `herdr plugin action invoke run --plugin herdr-devrun` (Windows: `up-windows` or `run-windows`). Both use the currently focused pane's project.
- `run` is an additional action ID for the same start operation as `up`; both
  invoke the `up` implementation. `run` is not a separate CLI subcommand.

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

- Place the file in the project root, or in any folder above the folder you run actions from. Keeping it in a `.run` folder is one option, not a requirement.
- In JSON strings, escape `\` as `\\` and `"` as `\"`. For example: `".\\gradlew.bat bootRun"`.
- Join multiple commands with `;` (supported by PowerShell, bash, and zsh). For example: `"pnpm install; pnpm run dev"`.
- If commands differ by OS, put one in `command` and the other in `command_windows` or `command_unix`. If they are the same, use only `command`.
- Do not put secrets such as encryption keys or passwords in `env`. Use OS environment variables instead. Configuration files may be committed to Git.
- To keep the configuration out of a shared repository, add `.herdr-devrun.json` to the project's `.gitignore`.
- Validation reports non-numeric `stop_timeout`/`start_timeout`, unknown `depends_on` services, and dependency cycles (including self-dependencies).
- Before starting, the configuration is checked for a JSON object containing a
  non-empty `services` list; each service must have a unique `name` and a
  command. A configured `port` must be an integer from 1 through 65535;
  timeouts must be non-negative numbers; `depends_on` must be a list of
  existing service names with no dependency cycle. Invalid configuration is
  reported by the action (including its file path and the validation problem).

> **Security:** `command` is entered directly into a shell. Running `up` on an untrusted repository executes commands defined by that repository, similar to running its npm scripts or Makefile. Review `.herdr-devrun.json` before running an unfamiliar project.

## 5. Start and stop services

| Goal | Action | Behavior |
|---|---|---|
| Start services | `up` (or `run`, same action) | Start services that are not running, in `depends_on` order. If all are running, switch to their tab |
| Stop services | `down` | Send Ctrl+C to each pane, wait for processes to exit (up to `stop_timeout`), close the project tab, and close the `devrun` space if no other tab is left |
| Restart | `restart` | Run down, then up. Also use it to apply configuration changes |

- Actions search for the configuration file by walking **up** from the folder of the pane where the action was run. They can be run from a subfolder within the project.
- `down` (the action) closes the project's tab. The dashboard's Stop and Stop all keep the tab and panes (section 6).

### Layout

The services of a project run in one tab named after the project (or `tab` in the configuration). The tab is in a shared space (herdr workspace) named `devrun`; each project adds its own tab to that space. The first pane of the tab is the dashboard (`control-box`), and service panes are placed to its right.
- `up` starts only services that are not already running. If some are running, the remaining ones are added to the same tab.
- Starting from the dashboard (the Start button or `a`) follows the same rule: if the control box is missing, it is created in the `devrun` space first. If the control box cannot be created, nothing is started and an error is shown. Restart does not follow this rule yet.
- Use the dashboard (section 6) to manage an individual service.
- You can close a tab or pane manually. The next run detects removed panes and cleans up the state.

### Start order (`depends_on`)

- A dependent service starts when its dependencies are **ready**. If a dependency has a `port`, readiness means that port is open (a server started elsewhere also qualifies); without a port, readiness means the service is running.
- If a dependency exits (✕), a waiting service is not started and is reported as "dependency failed". A service just started by the current plan is given a 5-second grace period before it can be considered failed.
- If a dependency is not ready within `start_timeout` (default: 120 seconds), the dependent service is not started and is reported as timed out, with the name of the dependency it was waiting for (for example, `frontend (timed out waiting for backend)`). For a slow backend such as Spring Boot, a value of 300 or more is suggested. `docs/examples/ex_react_spring.json` uses 300; this is an example value, not a measured startup time.
- Services that could not start are reported in a notification (and in the dashboard's message line), for example: `web (dependency failed), late (timed out waiting for dependencies)`.
- A service whose process is still running is skipped by start-all and listed as "Already running" in the completion message, separately from the services that failed.
- Starting a **single** service from the dashboard does not wait for its dependencies; the user explicitly selected it.

### Port conflicts

- If another process already uses a configured `port`, that service is not started. Otherwise the attempted launch may fail while the open port makes the service appear to be running.
- During start-all, only the service with the conflict is skipped (`port in use`); other services continue starting.
- If herdr rejects the command before it can be entered into a newly created
  service pane, devrun rolls back that pane: it closes the new tab and removes
  the project state if this was the first service, or closes only the added
  pane and removes it from state if the service tab already existed. This
  rollback covers command-entry failures; a command that starts and then exits
  remains in its pane so its output can be inspected.

### Stop timeout

- After sending Ctrl+C, the plugin checks every 0.2 seconds whether the process beneath the pane shell has exited. It stops waiting as soon as the process exits, or after `stop_timeout` (default: 10 seconds). Remaining processes are then closed with their pane.
- Increase `stop_timeout` for services that need more time for a graceful shutdown, such as Spring Boot.
- While a stop waits, a Windows batch prompt such as "Terminate batch job (Y/N)?" is answered with `Y` and Enter, so `.bat` services such as `gradlew.bat` stop cleanly. Only a prompt that appears during the wait is answered.

## 6. Dashboard

Run the `panel` action to open the dashboard in the project's tab, as the first pane (`control-box`) to the left of the services. If a dashboard for the same project is already in that tab, the action focuses it instead of opening another one.

The dashboard runs as a command in the pane's shell. Pressing Ctrl+C stops it and returns to the shell prompt; it does not close the pane. The next `panel` action opens a fresh dashboard.

```text
 ▣ devrun · my-project                                  2/3 running

   Status      Service                                    Port
 ▸ ● Running   backend                                    :8080
   ◐ Starting  frontend                                   :5173
   ○ Stopped   worker

  Start all   Stop all   Browser   Config   + Add   Close

─ Logs · backend ──────────────────────────────────────────────
 Started Application in 4.2 seconds
```

Each service row ends with `▶ Start` or `■ Stop`, `✎ Edit`, `✕ Delete`, and `⊗` (close the pane). Below 72 columns these show as icons only (`▶ ■ ✎ ✕ ⊗`).

### Status

| Indicator | Meaning | Detection |
|---|---|---|
| ● Running | Active | A process is running under the pane shell and, if configured, `port` is open. Without a port, only the process is checked |
| ◐ Starting | Starting up | A process exists, but the configured `port` is not open yet |
| ✕ Exited | Command finished | The pane remains, but only its shell is running. Check the logs for failure or completion |
| ○ Stopped | Not running | No process under the pane. After a stop, the pane may remain at the shell prompt, marked stopped |
| ◔ Waiting | Waiting for `depends_on` during start-all | |
| … Working | Dashboard is starting or stopping a service | |

### Controls

| Goal | Mouse | Key |
|---|---|---|
| Select a service | Click a row or use the wheel | `↑` `↓` `Home` `End` |
| Start/stop selected service | Double-click a row, or the Start/Stop button on its row | `Enter` |
| Restart selected service | none | `r` |
| Edit a service | `✎ Edit` on its row | none |
| Delete a service | `✕ Delete` on its row | none |
| Close a service pane | `⊗` on its row | none |
| Start all / stop all | Buttons on the bottom line | `a` / `x` |
| Open the service URL | Browser button | `o` |
| Open the configuration file | Config button | `e` |
| Close dashboard | Close button | `q`, `Esc`, `Ctrl+C` |

- Shortcuts also work while a Korean keyboard layout is active (`ㄱ=r`, `ㅁ=a`, `ㅌ=x`, `ㅐ=o`, `ㄷ=e`, `ㅂ=q`). In a confirmation box, `ㅛ=y` and `ㅜ=n`.
- Status and log previews refresh every second. The log preview shows the selected service's recent output; wrapped pane lines are displayed as their original single lines.
- Start-all accepts input while it waits. Selecting Stop all during startup cancels remaining starts.
- If the service list exceeds the screen, it scrolls with the selected row and shows `▲ n more` / `▼ n more` indicators.
- The port column is hidden when the service name would not fit beside the `Service` header with a space to spare. In English this happens at 43 columns or less, so the port column appears from 44 columns; other languages switch at a different width because their header text is longer or shorter. Below 30 columns, status names are replaced by icons.
- Row buttons show words at 72 columns or wider, and icons below that. If the window is too narrow to fit them, they are hidden. Edit and Delete have no keyboard shortcut, so widen the window to use them.
- Unexpected errors do not close the dashboard. A summary appears on the message line, with details in `panel.log` in the state directory.
- Saving the configuration reloads it automatically. If it is invalid, an error appears and the previous configuration remains active.
- The configuration opens in Notepad on Windows (`notepad.exe`), with `open` on macOS, and with `xdg-open` on Linux.
- Stop (`Enter`, or the Start/Stop button) stops that service's process and keeps its pane at the shell prompt, marked stopped. If the process does not exit within `stop_timeout`, the pane is closed. Stop all (`x`) does the same for every running service and keeps the tab and the control box.
- Restart (`r`) stops the service and starts it again. A stopped or exited pane is reused: the command is entered again in the same pane. If the process did not exit within `stop_timeout`, the pane is closed and a new one is created.
- Close (`⊗`) closes the service's pane after you confirm. A running process is stopped first. The tab and the control box stay.
- Closing the dashboard does not stop services.

### Add, edit, delete, and close services

**Add** is on the bottom line. **Edit**, **Delete**, and **Close** (`⊗`) are on each service row, and none of them has a keyboard shortcut. Add and Edit open a step-by-step form on the message line; the log preview is replaced by the choice list while you choose.

**Add** asks these steps in order:

1. **Category**: Frontend, Backend, Middleware, Database, or Other. Move with `↑` `↓`, then press `Enter`.
2. **Technology**: the presets of that category (table below). Other has only "Enter manually".
3. **Name, Folder, Command, Port, URL, Depends on**: Choosing a technology fills in its command and port. `Enter` keeps the value shown in brackets, and `-` clears the field. Change any value before saving.

The whole configuration is validated after the last step. If validation fails (for example, port `99999` or an empty command), the file is not changed. The message line shows the error and the form starts again at the first step with your entries kept as the defaults.

**Edit** asks the same fields, starting from the current values. Settings the form does not show (for example `env` and timeouts) are kept as they are.

**Delete** opens a confirmation box, "Delete '<name>'?". Press `y` or click **Delete** to remove the service; press `n`, `Esc`, click **Cancel**, or click outside the box to keep it. The service is also removed from the `depends_on` lists of other services. A running service is not deleted; the bottom line says to stop it first.

**Close** (`⊗`) opens a confirmation box, "Close '<name>' window?". Press `y` or click **Close** to close the service's pane; a running process is stopped first. The tab and the control box stay, so you can start the service again later.

Presets are defined in `src/presets.py`. A preset's values are written as you see them, so check them before saving. When the Windows and Unix commands differ (for example Gradle's `gradlew.bat` and `./gradlew`), the service is saved with `command_windows` and `command_unix`. The command for the OS you are on comes from your edit; the other OS keeps the preset command.

| Category | Technology | Command (Windows / Unix) | Port | Source |
|---|---|---|---|---|
| Frontend | React (Vite) | `npm run dev` | none (not fixed) | docs |
| Frontend | Next.js | `npm run dev` | 3000 | docs |
| Frontend | Vue | `npm run dev` | 5173 | estimate (create-vue on Vite) |
| Frontend | Angular | `npx ng serve` | 4200 | docs |
| Frontend | Vite (other build tools) | `npm run dev` | 5173 | docs |
| Backend | Spring Boot (Gradle) | `gradlew.bat bootRun` / `./gradlew bootRun` | 8080 | docs |
| Backend | Spring Boot (Maven) | `mvnw.cmd spring-boot:run` / `./mvnw spring-boot:run` | 8080 | docs |
| Backend | ASP.NET Core | `dotnet run` | 5000 | estimate (Kestrel fallback; `launchSettings.json` overrides it) |
| Backend | PHP (built-in server) | `php -S localhost:8000` | 8000 | estimate (manual example, not a default) |
| Backend | PHP (Laravel) | `php artisan serve` | 8000 | estimate (secondary sources only) |
| Backend | Node.js (Express) | `npm start` | 3000 | estimate (common convention, not a framework default) |
| Backend | Django | `python manage.py runserver` / `python3 manage.py runserver` | 8000 | docs |
| Backend | FastAPI | `uvicorn main:app --reload` | 8000 | estimate (uvicorn default is 8000; `main:app` is an assumption) |
| Middleware | Redis | `redis-server` | 6379 | estimate (not checked against docs) |
| Database | PostgreSQL | `postgres -D data` | 5432 | estimate (`data` is a placeholder for your data directory) |
| Database | MySQL | `mysqld --console` / `mysqld` | 3306 | estimate (not checked against docs) |
| Other | Enter manually | empty | empty | — |

- **docs**: the default was confirmed against the tool's documentation or default source.
- **estimate**: the value is commonly used but was not confirmed. Check it for your project before relying on it.
- Folder has no preset: it stays empty (project root) unless you type one.

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

### Example files (`docs/examples/`)

Copy a file to your project folder as `.herdr-devrun.json`, then change the `C:/path/to/...` folders and the `<DUMMY_...>` values. Items marked **추정** (estimate) were not confirmed for your project; check them before relying on them.

| File | Services | Estimated items |
|---|---|---|
| `ex_react_spring.json` | Spring Boot (Gradle, 8080) and React (pnpm, 5173) | none |
| `ex_nextjs_php.json` | PHP built-in server (`php -S localhost:8000`) and Next.js (`pnpm run dev`, 3000, starts after php) | the PHP command and port are **추정** (use `php artisan serve` for Laravel) |
| `ex_vue_aspnet.json` | ASP.NET Core (`dotnet run`, 5000) and Vue (`npm run dev`, 5173, starts after aspnet) | the ASP.NET port is **추정**: check `Properties/launchSettings.json`. 5173 is Vite's default |
| `ex_django_db.json` | Redis (`redis-server`, 6379) and Django (`python manage.py runserver 8000`, starts after redis) | the Redis command and port are **추정** |
| `ex_spring_only.json` | Spring Boot alone with Maven (`mvnw`, 8080) | 8080 is Spring's default: change it if `server.port` is set |

Gradle instead of Maven for `ex_spring_only.json`: put these in the two command keys:

```json
"command_windows": ".\\gradlew.bat bootRun",
"command_unix": "./gradlew bootRun"
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
