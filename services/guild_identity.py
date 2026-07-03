from pathlib import Path

import discord

from services.server_config import obter_valor_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolver_caminho_midia(caminho_midia):
    caminho_texto = str(caminho_midia or "").strip()
    if not caminho_texto:
        return None

    caminho = Path(caminho_texto)
    if not caminho.is_absolute():
        caminho = PROJECT_ROOT / caminho
    return caminho


def _carregar_bytes_midia(caminho_midia, guild_id, rotulo):
    caminho = _resolver_caminho_midia(caminho_midia)
    if caminho is None:
        return None, True

    if not caminho.exists() or not caminho.is_file():
        print(
            f"[BOT] {rotulo} por servidor não encontrado | "
            f"guild={guild_id} | caminho={caminho}"
        )
        return None, False

    try:
        return caminho.read_bytes(), False
    except OSError as erro:
        print(
            f"[BOT] Não consegui ler {rotulo.lower()} por servidor | "
            f"guild={guild_id} | caminho={caminho} | erro={erro!r}"
        )
        return None, False


async def aplicar_identidade_servidor(bot, guild):
    if bot.user is None or guild is None:
        return

    membro_bot = guild.me or guild.get_member(bot.user.id)
    if membro_bot is None:
        try:
            membro_bot = await guild.fetch_member(bot.user.id)
        except Exception:
            membro_bot = None

    if membro_bot is None:
        return

    payload = {}

    nickname_config = obter_valor_config(guild, "BOT_GUILD_NICKNAME", None)
    if nickname_config is not None:
        nickname_texto = str(nickname_config).strip()
        nick_final = nickname_texto or None
        if getattr(membro_bot, "nick", None) != nick_final:
            payload["nick"] = nick_final

    avatar_config = obter_valor_config(guild, "BOT_GUILD_AVATAR_PATH", None)
    if avatar_config is not None:
        avatar_bytes, limpar_avatar = _carregar_bytes_midia(avatar_config, guild.id, "Avatar")
        if limpar_avatar:
            payload["avatar"] = None
        elif avatar_bytes is not None:
            payload["avatar"] = avatar_bytes

    banner_config = obter_valor_config(guild, "BOT_GUILD_BANNER_PATH", None)
    if banner_config is not None:
        banner_bytes, limpar_banner = _carregar_bytes_midia(banner_config, guild.id, "Banner")
        if limpar_banner:
            payload["banner"] = None
        elif banner_bytes is not None:
            payload["banner"] = banner_bytes

    if not payload:
        return

    try:
        await membro_bot.edit(reason="Aplicando identidade configurada por servidor.", **payload)
    except discord.Forbidden as erro:
        print(
            "[BOT] Sem permissão para aplicar identidade por servidor | "
            f"guild={guild.id} | erro={erro!r}"
        )
    except discord.HTTPException as erro:
        print(
            "[BOT] HTTPException ao aplicar identidade por servidor | "
            f"guild={guild.id} | erro={erro!r}"
        )
    except ValueError as erro:
        print(
            "[BOT] Configuração inválida de identidade por servidor | "
            f"guild={guild.id} | erro={erro!r}"
        )


async def aplicar_identidade_todos_servidores(bot):
    for guild in bot.guilds:
        await aplicar_identidade_servidor(bot, guild)
