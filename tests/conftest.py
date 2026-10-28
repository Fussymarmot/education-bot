"""Test environment: fake token/admin/group and a temporary DB - before config is imported."""
import os
import tempfile

_DB = os.path.join(tempfile.mkdtemp(prefix="edubot-"), "test.db")
os.environ["BOT_TOKEN"] = "123456:TEST"
os.environ["ADMIN_IDS"] = "111"
os.environ["GROUP_CHAT_ID"] = "-1001"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB}"
