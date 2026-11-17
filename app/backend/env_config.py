"""
Loads environment variables from the single project-level .env file
(the .env at the repository root). Import this before reading os.getenv().

Real environment variables always win over the file, so production hosts
can set them directly.
"""
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE, override=False)
