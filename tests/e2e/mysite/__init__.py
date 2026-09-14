from pathlib import Path

# Executing a script from tests/e2e makes that directory sys.path[0].
# Reuse the real project package instead of duplicating settings for browser tests.
__path__ = [str(Path(__file__).resolve().parents[3] / "mysite")]
