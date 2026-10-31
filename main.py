import asyncio
import datetime
import random
import re
from asyncio import sleep
from os import getenv
from random import randint

import html2text
import requests
from aiohttp import ClientSession
from dotenv import load_dotenv
from mastodon import Mastodon
from mastodon.return_types import StatusMention
from sqlalchemy import delete, insert, select, update

from database import (
    engine,
    follows_table,
    key_value_store,
    replied_posts,
    responded_dms,
)
from logger import wafbot_logger

mastodon = Mastodon(access_token="data/pytooter_usercred.secret")
me = mastodon.me()


def get_setting(acct: str, key: str, default_value: str = None):
    with engine.begin() as c:
        res = c.execute(
            select(key_value_store.c.value).where(
                (key_value_store.c.acct == acct) & (key_value_store.c.setting == key)
            )
        ).fetchone()

        if res is not None:
            return res[0]

    return default_value


def set_setting(acct: str, key: str, value: str):
    with engine.begin() as c:
        res = c.execute(
            select(key_value_store.c.value).where(
                (key_value_store.c.acct == acct) & (key_value_store.c.setting == key)
            )
        ).fetchone()

        if res is not None:
            c.execute(
                update(key_value_store)
                .values(value=value)
                .where(
                    (key_value_store.c.acct == acct)
                    & (key_value_store.c.setting == key)
                )
            )
        else:
            c.execute(
                insert(key_value_store).values(acct=acct, setting=key, value=value)
            )


def get_mentions(reply_to: str, mentions: list[StatusMention]):
    mentions = [i for i in mentions if i.acct != me.acct]
    return f"@{reply_to} " + " ".join([f"@{j.acct}" for j in mentions])


def post_waf():

    mastodon.status_post(
        random.choice(
            [
                "waf",
                "waff",
                ":neofox_floof:",
                ":neofox_pat_floof:",
                ":neofox_floof_cute:",
                ":neofox_floof__w_:",
                ":neofox_floof_happy:",
            ]
        ),
        visibility="unlisted",
    )


async def waf():
    while True:
        try:
            a = randint(0, 100)
            if a == 67:
                post_waf()

            await sleep(60)
        except Exception:
            wafbot_logger.exception("exception in waf")
            break


def build_reply(text: str) -> str:
    reply = []

    for word in text.split(" "):
        if re.match(r"^wa+f$", word):
            reply.append("wa" + "f" * randint(1, 2))
        if re.match(":neofox.+:", word):
            reply.append(random.choice([":neofox_floof:", ":neofox_pat_floof:"]))

    return " ".join(reply)


async def reply(debug=False):
    while True:
        try:
            notifs = mastodon.notifications()

            for i in notifs:
                if i.status is None:
                    continue
                if i.status.account.acct == me.acct:
                    continue

                if i.status.account.bot:
                    continue

                # Check reply state
                with engine.begin() as c:
                    if (
                        c.execute(
                            select(replied_posts).where(
                                replied_posts.c.id == str(i.status.id)
                            )
                        ).fetchone()
                        is not None
                    ):
                        continue

                # Handle replying
                reply_text = build_reply(html2text.html2text(i.status.content).lower())

                if len(reply_text.strip()) > 0:
                    if get_setting(i.status.account.acct, "boosting", "false"):
                        mastodon.status_reblog(
                            i.status.id,
                            visibility=i.status.visibility
                            if i.status.visibility != "public"
                            else "unlisted",
                        )
                        await sleep(0.1)
                    if get_setting(i.status.account.acct, "replying", "false"):
                        mastodon.status_post(
                            get_mentions(i.status.account.acct, i.status.mentions)
                            + " "
                            + random.choice(
                                [
                                    "waf",
                                    "waff",
                                    ":neofox_floof:",
                                    ":neofox_pat_floof:",
                                    ":neofox_floof_cute:",
                                    ":neofox_floof__w_:",
                                    ":neofox_floof_happy:",
                                ]
                            ),
                            in_reply_to_id=i.status.id,
                            visibility="unlisted"
                            if i.status.visibility == "public"
                            else i.status.visibility,
                        )
                        await sleep(0.1)
                    emoji = random.choice([":neofox_floof:", ":neofox_pat_floof:"])
                    # Reaction
                    requests.put(
                        f"{mastodon.api_base_url}/api/v1/pleroma/statuses/{i.status.id}/reactions/:{emoji}:",
                        headers={"Authorization": f"Bearer {mastodon.access_token}"},
                    )
                    await sleep(0.1)

                    with engine.begin() as c:
                        c.execute(insert(replied_posts).values(id=str(i.status.id)))

                    await sleep(0.5)

            await asyncio.sleep(30)
        except Exception:
            wafbot_logger.exception("exception in reply")
            break


async def timeline():
    while True:
        try:
            posts = mastodon.timeline_home()

            for post in posts:
                if post.reblog is not None:
                    continue

                # Check author
                if post.account.acct == me.acct:
                    continue

                # Check reply state
                with engine.begin() as c:
                    if (
                        c.execute(
                            select(replied_posts).where(
                                replied_posts.c.id == str(post.id)
                            )
                        ).fetchone()
                        is not None
                    ):
                        continue

                # Handle replying
                reply_text = build_reply(html2text.html2text(post.content).lower())
                if len(reply_text.strip()) > 0:
                    if get_setting(post.account.acct, "boosting", "false"):
                        mastodon.status_reblog(
                            post.id,
                            visibility=post.visibility
                            if post.visibility != "public"
                            else "unlisted",
                        )
                        await sleep(0.1)
                    if get_setting(post.account.acct, "replying", "false"):
                        mastodon.status_post(
                            get_mentions(post.account.acct, post.mentions)
                            + " "
                            + random.choice(
                                ["waf", "waff", ":neofox_floof:", ":neofox_pat_floof:"]
                            ),
                            in_reply_to_id=post.id,
                            visibility=post.visibility
                            if post.visibility != "public"
                            else "unlisted",
                        )
                        await sleep(0.1)
                    emoji = random.choice([":neofox_floof:", ":neofox_pat_floof:"])
                    requests.put(
                        f"{mastodon.api_base_url}/api/v1/pleroma/statuses/{post.id}/reactions/:{emoji}:",
                        headers={"Authorization": f"Bearer {mastodon.access_token}"},
                    )
                    await sleep(0.1)

                    with engine.begin() as c:
                        c.execute(insert(replied_posts).values(id=str(post.id)))

                    await sleep(0.5)

                await asyncio.sleep(0.5)

            await asyncio.sleep(20)
        except Exception:
            wafbot_logger.exception("exception in timeline")
            break


async def check_followers():
    while True:
        try:
            for i in mastodon.account_followers(me):
                try:
                    with engine.begin() as c:
                        a = c.execute(
                            select(follows_table).where(follows_table.c.id == i.id)
                        ).fetchone()

                    if a is not None:
                        continue

                    rel = mastodon.account_relationships(i)
                    if len(rel) == 0:
                        continue

                    if (
                        not rel[0].following
                        and not rel[0].requested_by
                        and not rel[0].blocked_by
                    ):
                        print(f"follow {i.acct}")
                        while True:
                            follow = mastodon.account_follow(i.id)
                            if follow:
                                with engine.begin() as c:
                                    c.execute(
                                        insert(follows_table).values(
                                            id=i.id,
                                            acct=i.acct,
                                            followed=datetime.datetime.now(),
                                        )
                                    )
                                break
                            await asyncio.sleep(4)
                except Exception:
                    print("fail to follow", i.acct)
                    break

            with engine.begin() as c:
                a = c.execute(select(follows_table.c.id, follows_table.c.acct)).all()

            for i in a:
                rel = mastodon.account_relationships(i[0])
                if len(rel) == 0:
                    continue

                if not rel[0].followed_by and rel[0].following:
                    print(f"unfollow {i[0]}")
                    try:
                        unfollow_ok = mastodon.account_unfollow(i[0])
                        if unfollow_ok:
                            with engine.begin() as c:
                                c.execute(
                                    delete(follows_table).where(
                                        follows_table.c.id == i[0]
                                    )
                                )

                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"failed to unfollow {i[0]}: {e!s}")

            await asyncio.sleep(180)
        except Exception:
            wafbot_logger.exception("error in check_followers")
            break


async def respond_dm():
    await sleep(0.1)

    while True:
        for i in mastodon.notifications():
            if i.type != "mention":
                continue
            if i.status is None:
                continue
            if i.status.visibility != "direct":
                continue

            with engine.begin() as c:
                if (
                    c.execute(
                        select(responded_dms).where(
                            responded_dms.c.post_id == i.status.id
                        )
                    ).fetchone()
                    is not None
                ):
                    continue

            text = html2text.html2text(i.status.content).strip()

            if not text.startswith(f"@{me.acct}"):
                continue

            reply = ""
            for command_candidate in text.strip().splitlines():
                params = command_candidate.split(" ")
                params = [param for param in params if len(param.strip()) > 0]

                if len(params) == 0:
                    continue

                if params[0].startswith("@"):
                    del params[0]

                if len(params) == 1:
                    if params[0] == "help":
                        reply += """Help for wafbot\n
    - `enable boosting` or `disable boosting` - Enable the behaviour of the bot boosting your post.
    - `enable replying` or `disable replying` - Enable or disable the behaviour of the bot replying to posts.
    - `get` - List current settings\n\n"""
                    elif params[0] == "get":
                        enable_replies = get_setting(
                            i.account.acct, "replying", "false"
                        )
                        enable_boosts = get_setting(i.account.acct, "boosting", "false")
                        reply += f"""Your current settings:\n
    - Enable boosting: {"yes" if enable_boosts else "no"}
    - Enable replying: {"yes" if enable_replies else "no"}\n\n"""
                    elif params[0] == "waf":
                        reply += "waf\n\n"
                elif len(params) == 2:
                    if params[0] == "enable":
                        if params[1] == "boosting":
                            set_setting(i.status.account.acct, "boosting", "true")
                            reply += "Boosting is now enabled\n\n"
                        elif params[1] == "replying":
                            set_setting(i.status.account.acct, "replying", "true")
                            reply += "Replying is now enabled\n\n"
                    elif params[0] == "disable":
                        if params[1] == "boosting":
                            set_setting(i.status.account.acct, "boosting", "false")
                            reply += "Boosting is now disabled\n\n"
                        elif params[1] == "replying":
                            set_setting(i.status.account.acct, "replying", "false")
                            reply += "Replying is now disabled\n\n"

            if len(reply.strip()) == 0:
                reply += "Unrecognized command. Please try using `help` to get help"

            mastodon.status_post(
                f"@{i.account.acct} {reply}",
                content_type="text/plain",
                visibility="direct",
                in_reply_to_id=i.status,
            )

            with engine.begin() as c:
                c.execute(insert(responded_dms).values(post_id=i.status.id))

        await asyncio.sleep(10)


async def status():
    HEARTBEAT_URL = getenv("HEARTBEAT_URL", "")

    if len(HEARTBEAT_URL.strip()) == 0:
        return

    while True:
        async with ClientSession() as session:
            async with session.post(HEARTBEAT_URL, timeout=5):
                pass

        await asyncio.sleep(60)


async def run_task(task, name: str):
    while True:
        try:
            await task()
        except Exception:
            wafbot_logger.exception(f"exception in {name}")
            await asyncio.sleep(5)


async def wafin():

    await asyncio.gather(
        run_task(waf, "waf"),
        run_task(reply, "reply"),
        run_task(timeline, "timeline"),
        run_task(check_followers, "check_followers"),
        run_task(status, "status"),
        run_task(respond_dm, "respond_dm")
    )


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(wafin())
