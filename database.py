import json
import os

import dotenv
from sqlalchemy import create_engine, MetaData, Table, VARCHAR, Column, DateTime

if not os.path.exists("data"):
    os.mkdir("data")

dotenv.load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///data/waf.db"
DATABASE_CONNECT_ARGS = os.getenv("DATABASE_CONNECT_ARGS") or '{"timeout": 30}'

engine = create_engine(DATABASE_URL, connect_args=json.loads(DATABASE_CONNECT_ARGS))

md_obj = MetaData()

replied_posts = Table(
    "quoted_posts",
    md_obj,
    Column("id", VARCHAR, primary_key=True),
)

follows_table = Table(
    "follows",
    md_obj,
    Column("id", VARCHAR, primary_key=True),
    Column("acct", VARCHAR, nullable=False),
    Column("followed", DateTime, nullable=True, server_default="2026-01-28T00:00:00.000Z")
)

responded_dms = Table(
    "responded_dms",
    md_obj,
    Column("post_id", VARCHAR, primary_key=True)
)

key_value_store = Table(
    "kv_store",
    md_obj,
    Column("acct", VARCHAR, primary_key=True),
    Column("setting", VARCHAR, primary_key=True),
    Column("value", VARCHAR, nullable=False)
)

md_obj.create_all(engine, checkfirst=True)
