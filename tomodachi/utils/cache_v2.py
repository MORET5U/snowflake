from dataclasses import dataclass, fields
from typing import Optional

import aioredis
import orjson
from loguru import logger

from tomodachi.src.exceptions import CacheException, CacheMiss
from tomodachi.src.singleton import MetaSingleton
from tomodachi.utils.decos import executor
from .sql import psql

SETTINGS_PREFIX = "S-"  # S-{GUILD}


@dataclass(init=False)
class GuildSettings:
    prefix: Optional[str]
    tz: str = "UTC"

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)

    def __repr__(self):
        return "<GuildSettings {0}>".format(" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()))


class cachemanager(metaclass=MetaSingleton):  # noqa
    def __init__(self) -> None:
        self._blacklist = set()
        self._redis: Optional[aioredis.Redis] = None

    async def connect_redis(self, uri: str):
        if not self._redis:
            self._redis = await aioredis.create_redis_pool(uri, encoding="utf-8")
            logger.info("Redis connection pool created")

        elif isinstance(self._redis, aioredis.Redis):
            raise CacheException(
                "You have to destroy previously create Redis connection first before creating a new one!"
            ) from None

    @property
    def blacklist(self):
        return self._blacklist

    @property
    def redis(self):
        return self._redis

    async def get(self, guild_id: int) -> GuildSettings:
        exists = await self.redis.exists(f"{SETTINGS_PREFIX}{guild_id}")
        if not exists:
            try:
                await self.refresh(guild_id)
            except CacheException as e:
                raise CacheMiss(*e.args) from None

        jsonified = await self.redis.get(f"{SETTINGS_PREFIX}{guild_id}")

        # must run orjson in the executor since non-async
        aioloads = executor(lambda: orjson.loads(jsonified))
        data = await aioloads()
        return GuildSettings(**data)

    async def refresh(self, guild_id: int):
        query = "SELECT * FROM guilds WHERE guild_id = $1;", guild_id
        row = await psql().pool.fetchrow(*query)

        if not row:
            raise CacheException(f"Couldn't find any data for {guild_id}.") from None

        data = dict(row)

        # must run orjson in the executor since non-async
        aiodumps = executor(lambda: orjson.dumps(data).decode(encoding="utf-8"))
        jsonified = await aiodumps()

        # 172800 is 2 days
        await self.redis.setex(f"{SETTINGS_PREFIX}{guild_id}", 172800, jsonified)

    async def blacklist_refresh(self):
        query = "SELECT * FROM blacklisted;"
        rows = await psql().pool.fetch(query)

        for row in rows:
            self._blacklist.add(row["user_id"])

        logger.info("Blacklist cache is now fresh")
