# herdr-devrun

[**English**](README.md) | [한국어](README.ko.md)

UI languages: English · Korean · Russian · French · Spanish · German · Japanese

Start and manage a project's development services in separate panes from one herdr dashboard.

## Dashboard design

The dashboard shows service status, ports, and recent logs, and lets you start, stop, restart, or open a service URL. It opens to the right of the current pane; Ctrl+C returns to the shell.

## Installation

```sh
herdr plugin install vrwolf1004/herdr-devrun
```

## Actions

| Action | What it does |
| --- | --- |
| `up` | Start services that are not running, respecting `depends_on` |
| `down` | Stop services and close their tab |
| `restart` | Stop and start the services |
| `panel` | Open the project dashboard |
| `init` | Create a draft `.herdr-devrun.json` |

On Windows, append `-windows` to each action ID. The action uses the focused pane's project; see the [usage guide](docs/usage.md) for configuration and examples.

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
