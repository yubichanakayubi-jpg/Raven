import atexit
import ctypes
import os
import sys
import traceback

from ctypes import wintypes

import discord
from discord.ext import commands

from config import COMMAND_PREFIX, DISCORD_TOKEN, HEARTBEAT_TIMEOUT, criar_intents
from services.bot_context import set_bot
from services.guild_identity import (
    aplicar_identidade_servidor,
    aplicar_identidade_todos_servidores,
)
from services.logs import registrar_exclusao_temporaria, registrar_uso_comando

EXTENSOES = [
    "cogs.events",
    "cogs.ausencia",
    "cogs.cadastros",
    "cogs.tags",
    "cogs.recrutamento",
    "cogs.gatilhos",
    "cogs.staff",
    "cogs.historias",
    "cogs.slash_bridge",
    "cogs.moderacao",
    "cogs.embed_manager",
    "cogs.polls",
    "cogs.applications",
    "cogs.feedback",
    "cogs.ticket",
]


def garantir_instancia_unica():
    if os.name != "nt":
        return None

    error_already_exists = 183
    nome_mutex = "Local\\BotFDN_Raven_Instance"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    handle = kernel32.CreateMutexW(None, False, nome_mutex)
    if not handle:
        raise OSError("Nao consegui criar a trava de instancia unica do bot.")

    if ctypes.get_last_error() == error_already_exists:
        kernel32.CloseHandle(handle)
        print("Ja existe uma instancia do Raven em execucao.")
        sys.exit(1)

    atexit.register(lambda: kernel32.CloseHandle(handle))
    return handle


def extrair_nome_comando_slash(interaction: discord.Interaction) -> str:
    comando = getattr(interaction, "command", None)
    if comando is not None:
        return getattr(comando, "qualified_name", None) or getattr(comando, "name", None) or "desconhecido"

    data = getattr(interaction, "data", None) or {}
    partes = []
    nome = data.get("name")
    if nome:
        partes.append(str(nome))

    opcoes = data.get("options") or []
    while opcoes:
        primeira = opcoes[0]
        if not isinstance(primeira, dict):
            break
        if primeira.get("type") not in {1, 2}:
            break
        nome_opcao = primeira.get("name")
        if nome_opcao:
            partes.append(str(nome_opcao))
        opcoes = primeira.get("options") or []

    return " ".join(partes) if partes else "desconhecido"


class RavenBot(commands.Bot):
    async def setup_hook(self):
        for extensao in EXTENSOES:
            await self.load_extension(extensao)

    async def on_ready(self):
        await aplicar_identidade_todos_servidores(self)
        await self.sincronizar_slash_commands()

    async def sincronizar_slash_commands(self):
        if getattr(self, "_slash_commands_sincronizados", False):
            return

        self._slash_commands_sincronizados = True

        for guild in self.guilds:
            try:
                guild_obj = discord.Object(id=guild.id)
                self.tree.copy_global_to(guild=guild_obj)
                comandos = await self.tree.sync(guild=guild_obj)
                print(f"Slash commands sincronizados em {guild.name}: {len(comandos)}")
            except Exception:
                print(f"Erro ao sincronizar slash commands em {guild.name}.")
                traceback.print_exc()

    async def on_guild_join(self, guild):
        await aplicar_identidade_servidor(self, guild)

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            try:
                await registrar_uso_comando(
                    extrair_nome_comando_slash(interaction),
                    autor=getattr(interaction, "user", None),
                    canal=getattr(interaction, "channel", None),
                    guild_ou_id=getattr(interaction, "guild", None),
                    origem="slash",
                    conteudo=str(getattr(interaction, "data", {}) or {}),
                )
            except Exception:
                pass

        await super().on_interaction(interaction)

    async def process_commands(self, message):
        if message.author.bot:
            return

        ctx = None
        if message.content.lstrip().startswith(COMMAND_PREFIX):
            try:
                ctx = await self.get_context(message)
                if getattr(ctx, "command", None) is not None:
                    await registrar_uso_comando(
                        ctx.command.qualified_name,
                        autor=message.author,
                        canal=message.channel,
                        guild_ou_id=message.guild,
                        origem="prefixo",
                        conteudo=message.content,
                    )
            except Exception:
                pass

        await super().process_commands(message)

        if not message.content.lstrip().startswith(COMMAND_PREFIX):
            return

        try:
            await message.delete(delay=3)
            await registrar_exclusao_temporaria(
                origem="Auto limpeza de comando prefixado",
                canal=message.channel,
                guild_ou_id=message.guild,
                autor=message.author,
                delay=3,
                mensagem_id=message.id,
                conteudo=message.content,
                alvo="mensagem de comando",
            )
        except Exception:
            return


_mutex_handle = garantir_instancia_unica()

bot = RavenBot(
    command_prefix=COMMAND_PREFIX,
    intents=criar_intents(),
    heartbeat_timeout=HEARTBEAT_TIMEOUT,
    help_command=None,
)

set_bot(bot)

bot.run(DISCORD_TOKEN)
