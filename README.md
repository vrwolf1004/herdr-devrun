# herdr-devrun

[**English**](README.md) | [한국어](README.ko.md)

A herdr plugin for starting and managing a project's development services in separate panes from a single dashboard.

- Windows, Linux, and macOS
- Python 3.8+; standard library only
- herdr 0.9.0+

## Install

```sh
herdr plugin install vrwolf1004/herdrPlugin-devrun
```

Create a `.herdr-devrun.json` file in your project, then use the plugin actions or dashboard to manage its services.

## Documentation

Detailed usage guide (English):

- [Installation, configuration, actions, and dashboard](docs/usage.md)

Additional guides (Korean):

- [Troubleshooting](docs/troubleshooting.md)
- [Architecture](docs/architecture.md)
- [Design and scope](docs/start-idea.md)

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
