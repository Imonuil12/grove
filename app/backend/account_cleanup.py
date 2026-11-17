"""
Deletes user accounts and everything that belongs to them.

Usage (from the repository root):
    python app/backend/account_cleanup.py --list
    python app/backend/account_cleanup.py --fake            # dry run
    python app/backend/account_cleanup.py --fake --yes      # delete
    python app/backend/account_cleanup.py someone@example.com --yes

"Fake" accounts are identities that are not email addresses (dev_user,
user_xxxx, pytest_...), which older builds created for anyone who wasn't
signed in, plus the retired demo-patient login.
"""
import sys
from collections import deque

from sqlalchemy import delete, select

import env_config  # noqa: F401
import models as m
from database import Base, SessionLocal

RETIRED_ACCOUNTS = {"demo.patient@example.com"}
# Tables that point at a user by email/identity string instead of users.id.
IDENTITY_COLUMNS = [("chat_messages", "session_id"), ("conversations", "username"), ("sessions", "session_id"),
                    ("intakes", "session_id"), ("mastery_records", "session_id"), ("assessment_queue", "session_id")]


def is_fake(identity: str) -> bool:
    return "@" not in (identity or "") or identity in RETIRED_ACCOUNTS


def delete_user(db, identity: str) -> int:
    """Removes one account and all rows that depend on it. Returns rows deleted."""
    tables = Base.metadata.tables
    users = tables["users"]
    user_id = db.execute(select(users.c.id).where(users.c.email == identity)).scalar_one_or_none()
    total = 0

    if user_id is not None:
        # Walk foreign keys outward from users: each dependent table gets a WHERE
        # clause selecting only rows that (indirectly) belong to this user.
        owned = {"users": users.c.id == user_id}
        order = ["users"]
        queue = deque(["users"])
        while queue:
            parent = queue.popleft()
            for table in Base.metadata.sorted_tables:
                if table.name in owned:
                    continue
                for fk in table.foreign_keys:
                    if fk.column.table.name == parent:
                        ref = fk.column
                        owned[table.name] = fk.parent.in_(select(ref).where(owned[parent]))
                        order.append(table.name)
                        queue.append(table.name)
                        break
        for name in reversed(order):  # children first
            total += db.execute(delete(tables[name]).where(owned[name])).rowcount or 0

    for table_name, column in IDENTITY_COLUMNS:
        if table_name in tables:
            table = tables[table_name]
            total += db.execute(delete(table).where(table.c[column] == identity)).rowcount or 0
    return total


def main(argv):
    yes = "--yes" in argv
    args = [a for a in argv if not a.startswith("--")]
    with SessionLocal() as db:
        every = [u.email for u in db.query(m.User).order_by(m.User.id)]
        conv_only = {c for (c,) in db.query(m.Conversation.username).distinct()} - set(every)
        if "--list" in argv:
            for email in every:
                print(("FAKE  " if is_fake(email) else "      ") + email)
            for name in sorted(conv_only):
                print(("FAKE  " if is_fake(name) else "      ") + name + "  (chats only)")
            return 0
        targets = [e for e in every + sorted(conv_only) if is_fake(e)] if "--fake" in argv else args
        if not targets:
            print("Nothing to delete.")
            return 0
        print("Accounts to delete:\n  " + "\n  ".join(targets))
        if not yes:
            print("\nDry run. Add --yes to delete them.")
            return 0
        rows = sum(delete_user(db, t) for t in targets)
        db.commit()
        print(f"Deleted {len(targets)} account(s), {rows} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
