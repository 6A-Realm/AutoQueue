from __future__ import annotations

from asyncio import StreamReader, StreamWriter, open_connection, sleep
from binascii import unhexlify
from contextlib import suppress
from dataclasses import dataclass
from io import BytesIO
from logging import basicConfig, getLogger
from os import environ
from re import compile

import disnake
from disnake.ext import commands
from dotenv import load_dotenv
from rich.logging import RichHandler

with suppress(Exception):
    from uvloop import install

    install()

with open("config.json", "r") as file:
    config_data = disnake.utils._from_json(file.read())
ip_address = config_data["IP"]
prefix = config_data["prefix"]
log_level = config_data["log_level"]

basicConfig(
    level=log_level, format="%(message)s", datefmt="[X]", handlers=[RichHandler()]
)

log = getLogger("rich")
load_dotenv()

wait_pattern = compile(r"^W(\d*)$")


@dataclass
class SbbConnection:
    ip: str
    connected: bool = False
    reader: StreamReader = None
    writer: StreamWriter = None
    overworld_pointer = ["0x43A7848", "0x348", "0x10", "0xD8", "0x28"]
    connected_pointer = ["0x437E280", "0x30"]

    async def _connect(self) -> None:
        log.info(f"connecting to {self.ip}")
        self.reader, self.writer = await open_connection(
            self.ip, port=6000, limit=(1024 * 1024)
        )
        self.connected = True
        await self.send("configure echoCommands 1")
        await self.send("detatchController")

    async def send(self, command: str) -> str:
        log.info(f">> {command}")
        command += "\r\n"
        if not self.connected:
            await self._connect()
        self.writer.write(command.encode())
        await self.writer.drain()
        res = []
        while True:
            r = await self.reader.readline()
            if r == command.encode():
                log.info("<< echo")
                break
            else:
                result = r[:-1].decode()
                log.info(f"<< {len(result)} bytes")
                res.append(result)
            await sleep(0)
        if res:
            return res[0]

    async def send_seq(self, command: str) -> None:
        _, args_str = command.split(" ")
        cmds = args_str.split(",")
        for cmd in cmds:
            if wait_pattern.match(cmd):
                t = int(wait_pattern.findall(cmd)[0])
                log.info(f"sleeping for {t}")
                await sleep(float(t))
            else:
                await self.send(f"click {cmd}")

    async def pointer_peek(self, pointer, length) -> str:
        request = "pointerRelative"
        for jump in pointer:
            request += f" {jump}"
        addr = await self.send(request)
        return await self.send(f"peek 0x{int(addr, 16):X} 0x{length}")

    async def is_on_overworld(self) -> bool:
        on_overworld = await self.pointer_peek(self.overworld_pointer, 1)
        return on_overworld == "11"

    async def is_connected(self) -> bool:
        connected = await self.pointer_peek(self.connected_pointer, 1)
        return connected == "01"

    async def going_online(self) -> None:
        online = False
        while not online:
            await sleep(1)
            online = await self.is_on_overworld()
        await self.send_seq("clickSeq X,W1,L")

        connected = False
        while not connected:
            await sleep(2)
            connected = await self.is_connected()
        await self.send_seq("clickSeq W2,A,W1,A,W1,B,W1,B,W1")

    async def raid_battle(self) -> None:
        in_raid = True
        while in_raid:
            await self.send_seq(
                "clickSeq A,W1,A,W1,A,W1,A,W1,A,W1,A,W1,B,W1,B,W1,B,W1,B,W1,B,W1,B,W1"
            )
            in_raid = not await self.is_on_overworld()
            await sleep(5)

    async def quit_game(self) -> None:
        await self.send_seq("clickSeq B,W1,HOME,W1,X,W1,X,W1,A,W1,A,W3")

    async def start_game(self) -> None:
        await self.send_seq("clickSeq A,W1,A,W1,A,W1,A,W1")
        await sleep(16)
        await self.send_seq("clickSwq A,W1,A,W1")


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs) -> None:
        self.sbbcon = SbbConnection(ip=ip_address)
        super().__init__(*args, **kwargs)


bot = Bot(intents=disnake.Intents.all(), asyncio_debug=True, command_prefix=prefix)
bot.load_extensions("cogs")


async def pixelpeek_callback(ctx):
    if ctx.author.id != bot.owner_id:
        return
    image_hold = await bot.sbbcon.send("pixelPeek")
    await ctx.send(file=disnake.File(BytesIO(unhexlify(image_hold)), "peek.jpg"))


@bot.slash_command(name="pixelpeek")
async def _pixelpeek(inter) -> None:
    await pixelpeek_callback(inter)


@bot.command()
async def pixelpeek(ctx) -> None:
    await pixelpeek_callback(ctx)


bot.run(environ["DISCORD_TOKEN"])
