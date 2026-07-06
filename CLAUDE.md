# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

VeighNa (vnpy) is a Python framework for building quantitative trading systems. **This repo is the core framework only** — broker connections, strategy engines, databases, and data services are *separate* pip packages named `vnpy_<name>` (e.g. `vnpy_ctp`, `vnpy_ctastrategy`, `vnpy_sqlite`, `vnpy_rqdata`). They are not vendored here; they are loaded dynamically at runtime via `import_module(f"vnpy_{name}")`. When adding functionality, first check whether it belongs in the core or in a sibling `vnpy_*` package.

## Commands

The project targets Python 3.10+ (target/CI uses 3.13) and uses `uv` + `hatchling`.

```bash
# Lint (config in pyproject.toml; rules B,E,F,UP,W; E501 ignored)
ruff check .

# Static type check (strict mypy; full annotations required, target py310)
mypy vnpy

# Build wheel/sdist
uv build

# Editable dev install (mirrors CI)
uv pip install -e .[alpha,dev] --system

# Alpha ML extras (polars, scipy, lightgbm, torch, alphalens-reloaded, pyarrow, sklearn)
uv pip install -e .[alpha]
```

**CI gates are `ruff check .`, `mypy vnpy`, and `uv build` only — there is no test step in CI.** Tests exist (pytest) under [tests/](tests/) and [tests/alpha/](tests/alpha/) but are run manually:

```bash
pytest tests/test_alpha101.py                      # whole file
pytest tests/alpha/test_dataproxy.py -k <name>     # single test
```

`ta-lib` (the C library + Python binding) is a hard dependency of [vnpy/trader/utility.py](vnpy/trader/utility.py) and must be installed first. On Linux it is compiled from source (see [install.sh](install.sh)); on Windows use a prebuilt wheel from the vnpy PyPI mirror (`https://pypi.vnpy.com`). The alpha extras additionally require `torch`.

Version is defined by `__version__` in [vnpy/__init__.py](vnpy/__init__.py) and read by hatch.

## Architecture

### Event-driven core
- [vnpy/event/engine.py](vnpy/event/engine.py) — `EventEngine`: a single-threaded queue + worker thread that dispatches `Event(type, data)` to registered handlers, plus a timer thread emitting `EVENT_TIMER` every second. This is the message bus everything else hangs off.
- [vnpy/trader/engine.py](vnpy/trader/engine.py) — `MainEngine` is the platform hub. It owns the `EventEngine`, all gateways, all function engines, and all apps. Gateways push events in; engines/apps consume them. `MainEngine.init_engines()` always wires up three core engines: `OmsEngine` (in-memory cache of ticks/orders/trades/positions/accounts/contracts/quotes, updated by event handlers), `LogEngine`, `EmailEngine`, and `WechatEngine`. Convenience getters on `MainEngine` (e.g. `get_contract`, `send_order`) are delegated to `OmsEngine`/gateways.

Events come in two scopes: a generic type (`EVENT_TICK`) and a symbol/order-scoped type (`EVENT_TICK + vt_symbol`) so handlers can subscribe to one instrument. See [vnpy/trader/event.py](vnpy/trader/event.py) and the `on_*` callbacks in [vnpy/trader/gateway.py](vnpy/trader/gateway.py).

### Extension points (base classes)
All extensibility is via subclassing ABCs. The framework instantiates and wires them; concrete impls live in `vnpy_*` packages.

- `BaseGateway` ([gateway.py](vnpy/trader/gateway.py)) — broker/API connections. Must be thread-safe, non-blocking, and auto-reconnect. Subclasses implement `connect/subscribe/send_order/cancel_order/query_account/query_position` and call `on_tick/on_order/on_trade/on_position/on_account/on_contract` to push data. Class attrs `default_name`, `default_setting`, `exchanges` drive the connect dialog.
- `BaseApp` ([app.py](vnpy/trader/app.py)) — a strategy/function module. Declares `app_name`, `engine_class`, `widget_name`, etc. `MainEngine.add_app(AppClass)` registers it and spins up its engine.
- `BaseEngine` ([engine.py](vnpy/trader/engine.py)) — function engines that register event handlers.
- `BaseDatabase` / `BaseDatafeed` ([database.py](vnpy/trader/database.py), [datafeed.py](vnpy/trader/datafeed.py)) — storage and historical-data backends. Loaded lazily through module-level singletons `get_database()` / `get_datafeed()` from `vnpy_{SETTINGS["database.name"]}` / `vnpy_{SETTINGS["datafeed.name"]}`, falling back to `vnpy_sqlite` / a no-op stub.

### Data model
[vnpy/trader/object.py](vnpy/trader/object.py) defines `@dataclass` objects: market data (`TickData`, `BarData`), order lifecycle (`OrderData`, `TradeData`, `QuoteData`), state (`PositionData`, `AccountData`, `ContractData`, `LogData`), and request objects (`OrderRequest`, `SubscribeRequest`, etc.). Conventions:
- `vt_symbol` is always `"{symbol}.{exchange.value}"` (set in `__post_init__`).
- `vt_orderid`/`vt_tradeid`/`vt_accountid` are prefixed with `gateway_name` to be globally unique.
- Enums live in [vnpy/trader/constant.py](vnpy/trader/constant.py) (`Direction`, `Offset`, `Status`, `Exchange`, `Interval`, `OrderType`, `Product`, `OptionType`).

### Runtime config
[utility.py](vnpy/trader/utility.py) sets `TRADER_DIR` to a `.vntrader` folder (cwd if present, else the user's home) and adds it to `sys.path`. Global settings default in [setting.py](vnpy/trader/setting.py) (`SETTINGS` dict) and are overridden by `vt_setting.json` in `TRADER_DIR`. JSON helpers `load_json`/`save_json` read/write there.

### Trading utilities ([utility.py](vnpy/trader/utility.py))
- `BarGenerator` — synthesizes minute bars from ticks, and N-minute / N-hour / daily bars from minute bars.
- `ArrayManager` — rolling window of `size` bars exposing ~40 TA-Lib indicators. Each indicator has `@overload`s returning either the latest scalar (`array=False`) or the full `np.ndarray` (`array=True`).
- `round_to` / `floor_to` / `ceil_to` — snap prices to a tick.

### vnpy.alpha — AI/ML multi-factor pipeline (4.0 headline feature, inspired by Microsoft Qlib)
Polars-first (not pandas) end-to-end factor research stack:

- `AlphaDataset` ([dataset/template.py](vnpy/alpha/dataset/template.py)) — holds a long-format `pl.DataFrame` keyed by `(datetime, vt_symbol)`, feature expressions, train/valid/test periods (`Segment` enum). `prepare_data()` evaluates every feature expression **in parallel** via a `multiprocessing` spawn pool; `process_data()` runs infer- then learn-side processors (NaN fill, cross-sectional/robust normalization, inf replacement, feature dropping — see [dataset/processor.py](vnpy/alpha/dataset/processor.py)). Built-in factor sets: [Alpha101](vnpy/alpha/dataset/datasets/alpha_101.py), [Alpha158](vnpy/alpha/dataset/datasets/alpha_158.py).
- **Expression engine** ([dataset/utility.py](vnpy/alpha/dataset/utility.py)) — feature expressions are **strings evaluated with `eval()`**. Each feature column is exposed to the namespace as a `DataProxy` (operator-overloaded wrapper around one column); available functions are `ts_*` (time-series, per-symbol), `cs_*` (cross-sectional, per-datetime), `ta_*`, and `math` helpers. Custom functions are registered globally via `register_functions([...])`, which adds them to the `EXPRESSION_FUNCTIONS` dict the eval namespace reads from.
- `AlphaModel` ([model/template.py](vnpy/alpha/model/template.py)) — abstract `fit(dataset)` / `predict(dataset, segment) -> np.ndarray`. Built-ins: Lasso, LightGBM, MLP ([model/models/](vnpy/alpha/model/models/)).
- `AlphaStrategy` ([strategy/template.py](vnpy/alpha/strategy/template.py)) — abstract `on_init/on_bars/on_trade`. Target-based: call `set_target(vt_symbol, n)` then `execute_trading(bars, price_add)` auto-derives the buy/sell/short/cover orders. Supports both cross-sectional (multi-symbol) and time-series strategies; backtested with `BacktestingEngine` ([strategy/backtesting.py](vnpy/alpha/strategy/backtesting.py)).
- `AlphaLab` ([alpha/lab.py](vnpy/alpha/lab.py)) — orchestrates the whole workflow and persists artifacts: bar data as parquet (`daily/`, `minute/`), index components via `shelve`, datasets/models via `pickle`, signals as parquet.
- See [examples/alpha_research/](examples/alpha_research/) notebooks for the end-to-end research workflow.

### Other packages
- [vnpy/chart/](vnpy/chart/) — pyqtgraph candlestick charting (`Item`/`Widget`/`Manager`/`Axis`/`Base`).
- [vnpy/rpc/](vnpy/rpc/) — ZMQ request/reply RPC for distributed, cross-process trading.
- [vnpy/trader/ui/](vnpy/trader/ui/) — PySide6 GUI; entry points `create_qapp()` and `MainWindow(main_engine, event_engine)`.

### Internationalization
`_()` from [vnpy/trader/locale/](vnpy/trader/locale/) wraps gettext. Source/UI strings are Chinese; an English `.po` is compiled to `.mo` by a babel build hook (`locale/build_hook.py`) at wheel build time. Wrap any user-facing string in `_()`.

## Conventions

- **Branching**: feature PRs target the `dev` branch (not `master`), per the README contribution guide.
- **Types**: full annotations are mandatory (`disallow_untyped_defs`); use `X | Y` union syntax (py310+), not `typing.Union` in new code.
- **Bilingual**: identifiers/docstrings are English; user-facing strings, log messages, and many inline comments are Chinese — match the surrounding file.
- **Naming**: gateways/engines/apps use `XxxGateway`/`XxxEngine`/`XxxApp`; extension classes follow the existing `Base*` template patterns.
- **Threading**: gateways run on their own threads and must be thread-safe; all event dispatch happens on the single `EventEngine` worker thread.
- **Async**: gateway/network code in `vnpy_*` packages uses asyncio; the core framework here is synchronous + threading.
