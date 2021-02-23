#  Copyright (c) 2020 — present, moretzu (モーレツ)
#
#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at https://mozilla.org/MPL/2.0/.

import asyncio
import logging
from typing import Optional

import asyncpg

from .singleton import MetaSingleton

__all__ = ["pg"]


class pg(metaclass=MetaSingleton):  # noqa
    def __init__(self):
        self.__pool_: Optional[asyncpg.Pool] = None

        # this event can be used to understand when
        # the bot has a connection to the database
        self.connection_established = asyncio.Event()

    async def setup(self, dsn: str):
        try:
            self.__pool_ = await asyncpg.create_pool(dsn)
        except:  # noqa
            raise
        else:
            self.connection_established.set()
            logging.info("connection to pgsql established")

    @property
    def pool(self):
        return self.__pool_

    @pool.setter
    def pool(self, value):
        raise AttributeError("Can not set this.") from None

    async def update_prefix(self, guild_id: int, new_prefix: str):
        async with self.__pool_.acquire() as conn:
            query = "UPDATE guilds SET prefix = $1 WHERE guild_id = $2 RETURNING prefix;"
            prefix = await conn.fetchval(query, new_prefix, guild_id)
        return prefix
