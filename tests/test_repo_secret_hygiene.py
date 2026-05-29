import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_ROOT_SECRET_ARTIFACTS = (
    ".env",
    "kalshkey",
    "odds_api_key",
)
REPO_ROOT_SECRET_GITIGNORE_ENTRIES = (
    "kalshkey",
    "odds_api_key",
    "kalshi_private_key.pem",
)
REQUIRED_ENV_TEMPLATE_LINES = (
    "KALSHI_API_KEY_ID=your-kalshi-api-key-id",
    "KALSHI_PRIVATE_KEY_FILE=/absolute/path/to/kalshi_private_key.pem",
    "KALSHI_PRIVATE_KEY_PATH=/run/secrets/kalshi_private_key.pem",
    "ODDS_API_KEY=your-odds-api-key",
)
FORBIDDEN_ENV_TEMPLATE_TOKENS = (
    "kalshkey",
    "odds_api_key",
    "/tmp/kalshi_private_key.pem",
)


def test_repo_root_has_no_tracked_secret_artifacts():
    gitignore_entries = set(
        (REPO_ROOT / ".gitignore").read_text().splitlines()
    )
    for artifact_name in FORBIDDEN_ROOT_SECRET_ARTIFACTS:
        artifact_path = REPO_ROOT / artifact_name
        if artifact_path.exists():
            assert artifact_name in gitignore_entries, (
                f"{artifact_name} exists at repo root but is not in .gitignore"
            )


def test_gitignore_blocks_repo_root_secret_artifacts():
    gitignore_entries = set((REPO_ROOT / ".gitignore").read_text().splitlines())

    for entry in REPO_ROOT_SECRET_GITIGNORE_ENTRIES:
        assert entry in gitignore_entries


def test_env_template_documents_runtime_secret_contract_only():
    env_example = (REPO_ROOT / ".env.example").read_text()

    for required_line in REQUIRED_ENV_TEMPLATE_LINES:
        assert required_line in env_example

    for forbidden_token in FORBIDDEN_ENV_TEMPLATE_TOKENS:
        assert forbidden_token not in env_example
