pip install -q pytest pytest-asyncio hypothesis ruff >/dev/null 2>&1
ruff check --no-cache app tests --output-format=concise | tail -5
python -m pytest "$@" -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|passed|failed|^E  " | head -40
