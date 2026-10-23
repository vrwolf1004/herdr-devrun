# herdr-devrun

[**English**](README.md) | [한국어](README.ko.md)

UI languages: English · Korean · Russian · French · Spanish · German · Japanese

Start and manage a project's development services in separate panes from one herdr dashboard.

## Dashboard design

The dashboard shows service status, ports, and recent logs. Each service row has Start/Stop, Edit, Delete, and Close buttons; the bottom line has Start all, Stop all, Browser, Config, Add, and Close. Restart is the `r` key. It opens in the project's tab in a shared `devrun` space, to the left of the services; Ctrl+C returns to the shell.

```text
 ▣ devrun · my-project                                  2/3 running

   Status      Service                                    Port
 ▸ ● Running   backend                                    :8080     ■ Stop   ✎ Edit   ✕ Delete   ⊗
   ◐ Starting  frontend                                   :5173
   ○ Stopped   worker

  Start all   Stop all   Browser   Config   + Add   Close

─ Logs · backend ──────────────────────────────────────────────
 Started Application in 4.2 seconds
```

This plugin uses a project dashboard rather than an Agents-sidebar block.

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

On Windows, append `-windows` to each action ID. The action uses the focused pane's project; see the [usage guide](docs/usage.md) for configuration and examples.

`run` is a separate herdr action ID that invokes the same start behavior as
`up`. Invalid project configuration is reported as an action error; if herdr
cannot enter a newly created service command, devrun closes the new tab and
removes its saved state (or closes only the newly added pane in an existing
tab). See the [usage guide](docs/usage.md) for validation rules and recovery.

## Release notes

### 0.5.5

- Dashboard buttons: each service row has Start/Stop, Edit, Delete, and Close (`⊗`); the bottom line has Start all, Stop all, Browser, Config, Add, and Close. Restart is the `r` key.
- Layout: services run in a tab of a shared `devrun` space, with the dashboard (`control-box`) as the tab's first pane.
- Stop (and Stop all) stops the process and keeps its pane, marked as stopped; Start reuses that pane. `devrun down` still closes the tab.
- Delete and Close ask for confirmation in a dialog; press `y` to confirm.
- Windows batch prompts "(Y/N)" are answered with `Y` during a stop and before a start.
- Start all lists services that were already running separately from the ones that failed.
- The configuration opens in Notepad on Windows.

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

## Development

```sh
python -m unittest discover -s tests
```

## License

[MIT](LICENSE)

## Support the project

If this project is useful to you, consider buying the developer a coffee.

[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?style=for-the-badge&logo=buymeacoffee&logoColor=white)](https://ko-fi.com/dev_ohyt)
