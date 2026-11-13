# herdr-devrun

[**English**](README.md) | [한국어](README.ko.md)

UI languages: English · Korean · Russian · French · Spanish · German · Japanese

Start and manage a project's development services in separate panes from one herdr dashboard.

## Dashboard design

The dashboard shows service status, ports, and recent logs. Each service row has Start/Stop, Edit, Delete, and Close buttons. The bottom button row has Start all, Stop all, Browser, and + Add. The bottom line shows `Ctrl+H help`. The dashboard opens in the project's tab in a shared `devrun` space, to the left of the services.

```text
 ▣ devrun · my-project                                  2/3 running

   Status      Service                                    Port
 ▸ ● Running   backend                                    :8080     ■ Stop   ✎ Edit   ✕ Delete   ⊗
   ◐ Starting  frontend                                   :5173
   ○ Stopped   worker

  Start all   Stop all   Browser   + Add

─ Log · backend ───────────────────────────────────────────────
 Started Application in 4.2 seconds
                                                 Ctrl+H help
```

Press `Ctrl+H` to open the help popup over the dashboard. Press any key or click to close it:

```text
        ╭───────────────────────────────────────╮
        │              Ctrl+H help              │
        ├───────────────────────────────────────┤
        │ ↑ ↓  select service                   │
        │ Enter  start / stop                   │
        │ Ctrl+S  start all   Ctrl+X  stop all  │
        │ Ctrl+R  restart all   Ctrl+O  browser │
        │ Ctrl+E  config   Ctrl+L  language     │
        │ Ctrl+C  quit                          │
        ╰───────────────────────────────────────╯
```

### Keys

| Key | Action |
| --- | --- |
| `↑` `↓` | Select a service |
| `Enter` | Start or stop the selected service |
| `Ctrl+S` | Start all services |
| `Ctrl+X` | Stop all services |
| `Ctrl+R` | Restart all services (stop, then start) |
| `Ctrl+O` | Open the browser for the selected service |
| `Ctrl+E` | Open the configuration |
| `Ctrl+L` | Change the language: System → English → … → Japanese → System (saved to `config.json`) |
| `Ctrl+H` | Show or hide the help popup |
| `Ctrl+C` | Close the dashboard and return to the shell |

This plugin shows a project dashboard, not a block in the Agents sidebar.

## Installation

```sh
herdr plugin install vrwolf1004/herdr-devrun
```

## Actions

| Action | What it does |
| --- | --- |
| `up` | Start services that are not running, respecting `depends_on` |
| `run` | Start services, same behavior as `up` |
| `down` | Stop services, close their tab, and close the `devrun` space if no other project tab is left |
| `restart` | Stop and start the services |
| `panel` | Open the project dashboard |
| `init` | Create a draft `.herdr-devrun.json` |

On Windows, append `-windows` to each action ID. Each action uses the project of the focused pane. See the [usage guide](docs/usage.md) for configuration and examples.

`run` is a separate herdr action ID that runs the same start behavior as
`up`. An invalid project configuration is reported as an action error. If herdr
fails to run a new service command, devrun closes the new tab and removes its
saved state (or closes only the newly added pane in an existing tab). See the
[usage guide](docs/usage.md) for validation rules and recovery.

## Requirements

- Windows, Linux, or macOS
- herdr 0.9.0 or later
- Python 3.8 or later; standard library only

## Documentation

- [Usage (English)](docs/usage.md)
- [사용법 (한국어)](docs/usage.ko.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Architecture](docs/architecture.md)
- [Development and tests](docs/development.md)
- [Design and scope](docs/start-idea.md)
- [TODO](docs/todo.md)
- [Additional sections](docs/readme-extras.md): sections moved out of this README

## Support the project

If this project is useful to you, consider buying the developer a coffee.

[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?style=for-the-badge&logo=buymeacoffee&logoColor=white)](https://ko-fi.com/dev_ohyt)
