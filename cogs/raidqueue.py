from asyncio import Queue, create_task, sleep
from binascii import unhexlify
from io import BytesIO
from logging import getLogger

import disnake
from disnake.ext import commands, components


class RaidQueue(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.raid_queue = Queue()
        self.log = getLogger("rich")
        self.raidtask_running = False
        self.queue_running = False
        self.raid_counter = 0

    async def pixelpeek(self):
        holder_variable = await self.bot.sbbcon.send("pixelPeek")
        self.log.info("code logged")
        return unhexlify(holder_variable)

    async def autoraid_task(self):
        while self.raidtask_running:
            # going online
            self.log.info("raidtask started")
            await self.bot.sbbcon.going_online()
            self.log.info("connected to internet")

            # raid lobby
            await self.bot.sbbcon.send_seq("clickSeq A,W3,A,W3,A,W6")
            # await sleep(20)
            data = await self.pixelpeek()
            users = []
            while not self.raid_queue.empty() and len(users) < 3:
                user = await self.bot.getch_user(await self.raid_queue.get())
                users.append(user)
                await user.send(files=[disnake.File(BytesIO(data), "raid.jpg")])
            self.log.info("code sent")
            await sleep(150)
            await self.bot.sbbcon.send_seq("click A,W3,A")
            self.log.info("starting raid")

            # raid battle
            await self.bot.sbbcon.raid_battle()
            self.log.info("raid finished")

            # quit game
            await self.bot.sbbcon.quit_game()
            self.log.info("quit game")

            # start game
            await self.bot.sbbcon.start_game()
            self.log.info("started game")

            self.raid_counter += 1
            if not self.queue_running and self.raid_queue.empty:
                self.raidtask_running = False
        self.log.info(f"raid finished, {self.raid_counter} raids done")

    @components.button_listener()
    async def join_listener(
        self, inter: disnake.MessageInteraction, *, author: disnake.User
    ):
        if not self.queue_running:
            await inter.send("queue is closed", ephemeral=True)
            return None
        self.log.info(author)
        self.raid_queue.put_nowait(inter.author.id)
        await inter.send("joined queue!", ephemeral=True)

    async def open_queue_callback(self, inter) -> None:
        await inter.send(
            content="Raid has been started!!!",
            components=disnake.ui.Button(
                label="join",
                custom_id=await self.join_listener.build_custom_id(author=inter.author),
            ),
        )
        self.raidtask_running = True
        self.queue_running = True
        await create_task(self.autoraid_task())

    @commands.slash_command(name="open_queue")
    async def _open_queue(self, inter) -> None:
        await self.open_queue_callback(inter)

    @commands.command()
    async def open_queue(self, ctx) -> None:
        await self.open_queue_callback(ctx)

    async def show_queue_callback(self, inter) -> None:
        await inter.send(
            content="\n".join(
                [f"<@{str(user)}>" for user in list(self.raid_queue._queue)]
            ),
            ephemeral=True,
        )

        @commands.slash_command(name="show_queue")
        async def _show_queue(self, inter) -> None:
            await self.show_queue_callback(inter)

        @commands.command()
        async def show_queue(self, ctx) -> None:
            await self.show_queue_callback(ctx)

    async def close_queue_callback(self, inter) -> None:
        if inter.author.id != self.bot.owner_id:
            return None
        self.queue_running = False
        await inter.send("Raid Queue is now closed!")

    @commands.slash_command(name="close_queue")
    async def _close_queue(self, inter) -> None:
        await self.close_queue_callback(inter)

    @commands.command()
    async def close_queue(self, ctx) -> None:
        await self.close_queue_callback(ctx)


def setup(bot: commands.Bot):
    bot.add_cog(RaidQueue(bot))
