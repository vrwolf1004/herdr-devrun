# herdr-devrun

[**English**](README.md) | [한국어](README.ko.md)

A herdr plugin for starting and managing a project's development services in separate panes from a single dashboard.

- Windows, Linux, and macOS
- Python 3.8+; standard library only
- herdr 0.9.0+

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

## Install

```sh
herdr plugin install vrwolf1004/herdr-devrun
```

Create a `.herdr-devrun.json` file in your project, then use the plugin actions or dashboard to manage its services.

## Documentation

Detailed usage guide:

- [Installation, configuration, actions, and dashboard (English)](docs/usage.md)
- [설치, 설정, 액션 및 대시보드 사용법 (한국어)](docs/usage.ko.md)

Additional guides:

- [Troubleshooting (Korean)](docs/troubleshooting.md)
- [Development and tests (Korean)](docs/development.md)
- [Architecture (Korean)](docs/architecture.md)
- [Design and scope (Korean)](docs/start-idea.md)

## Development

```sh
python -m unittest discover -s tests
```

## License

[MIT](LICENSE)

---

## Support the project

If this project is useful to you, consider buying the developer a coffee.

[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?style=for-the-badge&logo=buymeacoffee&logoColor=white)](https://ko-fi.com/dev_ohyt)
