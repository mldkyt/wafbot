import asyncio
import datetime
import random
import re
import typing
from asyncio import sleep
from os import getenv
from random import randint

import bs4
import requests
from aiohttp import ClientSession
from dotenv import load_dotenv
from mastodon import Mastodon
from mastodon.return_types import StatusMention
from sqlalchemy import select, insert, delete

from database import replied_posts, engine, follows_table
from logger import wafbot_logger

mastodon = Mastodon(access_token="data/pytooter_usercred.secret")
me = mastodon.me()

# borrowed from https://stackoverflow.com/questions/30337528/make-beautifulsoup-handle-line-breaks-as-a-browser-would
def get_text(tag: bs4.Tag) -> str:
    _inline_elements = {"a","span","em","strong","u","i","font","mark","label",
    "s","sub","sup","tt","bdo","button","cite","del","b","a","font",}

    def _get_text(tag: bs4.Tag) -> typing.Generator:
        for child in tag.children:
            if isinstance(child, bs4.Tag):
                # if the tag is a block type tag then yield new lines before after
                is_block_element = child.name not in _inline_elements
                if is_block_element:
                    yield "\n"
                yield from ["\n"] if child.name == "br" else _get_text(child)
                if is_block_element:
                    yield "\n"
            elif isinstance(child, bs4.NavigableString):
                yield child.string

    return "".join(_get_text(tag))

def get_mentions(reply_to: str, mentions: list[StatusMention]):
    mentions = [i for i in mentions if i.acct != me.acct]
    return f"@{reply_to} " + " ".join([f"@{j.acct}" for j in mentions])

def post_waf():

    mastodon.toot(random.choice(["waf", "waff", ":neofox_floof:", ":neofox_pat_floof:", ":neofox_floof_cute:", ":neofox_floof__w_:", ":neofox_floof_happy:"]))

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
                    if (c.execute(select(replied_posts).where(
                            (replied_posts.c.id == str(i.status.id)))).fetchone() is not None):
                        continue

                # Handle replying
                reply_text = build_reply(get_text(bs4.BeautifulSoup(i.status.content)).lower())

                if len(reply_text.strip()) > 0:
                    mastodon.status_reblog(i.status.id)
                    await sleep(0.1)
                    mastodon.status_post(get_mentions(i.status.account.acct, i.status.mentions) + " " + random.choice(
                        ["waf", "waff", ":neofox_floof:", ":neofox_pat_floof:", ":neofox_floof_cute:",
                         ":neofox_floof__w_:", ":neofox_floof_happy:"]), in_reply_to_id=i.status.id, visibility=i.status.visibility)
                    await sleep(0.1)
                    emoji = random.choice([":neofox_floof:", ":neofox_pat_floof:"])
                    # Reaction
                    requests.put(f"{mastodon.api_base_url}/api/v1/pleroma/statuses/{i.status.id}/reactions/:{emoji}:", headers={
                        "Authorization": f"Bearer {mastodon.access_token}"
                    })
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
                    if (c.execute(select(replied_posts).where(
                            (replied_posts.c.id == str(post.id)))).fetchone() is not None):
                        continue

                # Handle replying
                reply_text = build_reply(get_text(bs4.BeautifulSoup(post.content)).lower())
                if len(reply_text.strip()) > 0:
                    mastodon.status_reblog(post.id)
                    await sleep(0.1)
                    mastodon.status_post(get_mentions(post.account.acct, post.mentions) + " " + random.choice(
                        ["waf", "waff", ":neofox_floof:", ":neofox_pat_floof:"]), in_reply_to_id=post.id, visibility=post.visibility)
                    await sleep(0.1)
                    emoji = random.choice([":neofox_floof:", ":neofox_pat_floof:"])
                    requests.put(f"{mastodon.api_base_url}/api/v1/pleroma/statuses/{post.id}/reactions/:{emoji}:", headers={
                        "Authorization": f"Bearer {mastodon.access_token}"
                    })
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
                            select(follows_table)
                            .where(follows_table.c.id == i.id)
                        ).fetchone()

                    if a is not None:
                        continue

                    rel = mastodon.account_relationships(i)
                    if len(rel) == 0:
                        continue

                    if not rel[0].following and not rel[0].requested_by and not rel[0].blocked_by:
                        print(f"follow {i.acct}")
                        while True:
                            follow = mastodon.account_follow(i.id)
                            if follow:
                                with engine.begin() as c:
                                    c.execute(insert(follows_table).values(
                                        id=i.id,
                                        acct=i.acct,
                                        followed=datetime.datetime.now())
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
                                c.execute(delete(follows_table).where((follows_table.c.id == i[0])))

                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"failed to unfollow {i[0]}: {str(e)}")
                        pass

            await asyncio.sleep(180)
        except Exception:
            wafbot_logger.exception("error in check_followers")
            break


async def status():
    HEARTBEAT_URL = getenv("HEARTBEAT_URL", "")

    if len(HEARTBEAT_URL.strip()) == 0:
        return

    while True:
        async with ClientSession() as session:
            async with session.post(HEARTBEAT_URL, timeout=5):
                pass

        await asyncio.sleep(60)


async def wafin():

    await asyncio.gather(
        waf(),
        reply(),
        timeline(),
        check_followers(),
        status()
    )


if __name__ == '__main__':

    load_dotenv()
    asyncio.run(wafin())
