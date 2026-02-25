## eink-cal

Run this project with `uv`.

### Prerequisites

- Install `uv`: <https://docs.astral.sh/uv/>

### Setup

From the project root:

```bash
uv sync
```

This creates/updates `.venv` and installs dependencies from `pyproject.toml`.

### Run

```bash
uv run main.py
```

### Add dependencies

```bash
uv add <package>
```

### Optional: activate shell manually

```bash
source .venv/bin/activate
python main.py
```

