# Additional sections (moved from README)

## Release notes

### 0.6.6

- Dashboard keys changed to Ctrl+letter: `Ctrl+S` start all, `Ctrl+X` stop all, `Ctrl+R` restart all (stop, then start), `Ctrl+O` browser, `Ctrl+E` config. The letter keys `a`, `x`, `r`, `o`, `e`, `q` were removed.
- Ctrl+C closes the dashboard. `q` and Esc no longer close it.
- The single-service restart key was removed. Restart all with `Ctrl+R`.
- Bottom button row: Start all, Stop all, Browser, + Add. The Config, Language, and Close buttons were removed. The language is set with `HERDR_DEVRUN_LANG` or `config.json`.
- `Ctrl+H` opens a help popup; the bottom line shows `Ctrl+H help`.
- `Ctrl+L` cycles the dashboard language (System → each language → System) and saves it to `config.json`. The language list form was removed.

### 0.6.5

- Restart from the dashboard (`r`) creates the control box first, like Start, so services never open outside the `devrun` space.
- The bottom key hint is shorter so it fits narrow dashboards. Buttons still show Browser, Config, and Close; the `o`, `e`, and `q` keys still work.
- Japanese wording is consistent across messages.
- Language button in the dashboard's bottom row: pick a UI language from a list. The choice is saved to `HERDR_PLUGIN_CONFIG_DIR/config.json` when that folder is set.

### 0.5.5

- Dashboard buttons: each service row has Start/Stop, Edit, Delete, and Close (`⊗`); the bottom line has Start all, Stop all, Browser, Config, Add, and Close. Restart is the `r` key.
- Layout: services run in a tab of a shared `devrun` space, with the dashboard (`control-box`) as the tab's first pane.
- Stop (and Stop all) stops the process and keeps its pane, marked as stopped; Start reuses that pane. `devrun down` still closes the tab.
- Delete and Close ask for confirmation in a dialog; press `y` to confirm.
- Windows batch prompts "(Y/N)" are answered with `Y` during a stop and before a start.
- Start all lists services that were already running separately from the ones that failed.
- The configuration opens in Notepad on Windows.

## Development

```sh
python -m unittest discover -s tests
```

## License

[MIT](LICENSE)

