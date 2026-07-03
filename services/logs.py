from datetime import datetime, timezone

import discord

from services.bot_context import get_bot
from services.server_config import obter_valor_config


def _resumir_texto(texto, limite=220):
    texto = " ".join(str(texto or "").split()).strip()
    if not texto:
        return "Nao informado."
    if len(texto) <= limite:
        return texto
    return f"{texto[:limite - 3].rstrip()}..."


def _formatar_usuario(usuario):
    if usuario is None:
        return "Nao informado"
    usuario_id = getattr(usuario, "id", None)
    if usuario_id:
        return f"{getattr(usuario, 'mention', str(usuario))} (`{usuario_id}`)"
    return str(usuario)


def _formatar_canal(canal):
    if canal is None:
        return "Nao informado"
    canal_id = getattr(canal, "id", None)
    if canal_id:
        return f"{getattr(canal, 'mention', '#' + str(canal_id))} (`{canal_id}`)"
    return str(canal)


async def enviar_log_bot(titulo, descricao, guild_ou_id=None):
    bot = get_bot()
    if not bot:
        print(f"[LOG BOT] {titulo} | {descricao}")
        return

    canal_logs_id = obter_valor_config(guild_ou_id, "CANAL_LOGS_ID")
    if not canal_logs_id:
        print(f"[LOG BOT] {titulo} | {descricao}")
        return

    canal_logs = bot.get_channel(canal_logs_id)

    if not canal_logs:
        try:
            canal_logs = await bot.fetch_channel(canal_logs_id)
        except Exception:
            print(f"[LOG BOT] {titulo} | {descricao}")
            return

    try:
        embed = discord.Embed(
            title=titulo,
            description=descricao,
            color=discord.Color.from_rgb(69, 211, 232),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(name="Raven Logs")
        await canal_logs.send(embed=embed)
    except Exception as erro:
        print(f"[LOG BOT] Erro ao enviar log: {erro}")
        print(f"[LOG BOT] {titulo} | {descricao}")


async def registrar_uso_comando(nome_comando, *, autor=None, canal=None, guild_ou_id=None, origem="desconhecida", conteudo=None):
    await enviar_log_bot(
        "🧾 Comando usado",
        (
            f"**Origem:** {origem}\n"
            f"**Comando:** `{nome_comando or 'desconhecido'}`\n"
            f"**Usuario:** {_formatar_usuario(autor)}\n"
            f"**Canal:** {_formatar_canal(canal)}\n"
            f"**Conteudo:** {_resumir_texto(conteudo)}"
        ),
        guild_ou_id=guild_ou_id,
    )


async def registrar_mencao_raven(message, *, motivo="mencao"):
    await enviar_log_bot(
        "👁️ Raven mencionado",
        (
            f"**Motivo:** {motivo}\n"
            f"**Usuario:** {_formatar_usuario(getattr(message, 'author', None))}\n"
            f"**Canal:** {_formatar_canal(getattr(message, 'channel', None))}\n"
            f"**Mensagem:** {_resumir_texto(getattr(message, 'content', ''))}"
        ),
        guild_ou_id=getattr(message, "guild", None),
    )


async def registrar_exclusao_temporaria(
    *,
    origem,
    canal=None,
    guild_ou_id=None,
    autor=None,
    delay=None,
    mensagem_id=None,
    conteudo=None,
    alvo="mensagem",
):
    detalhes_delay = f"{int(delay)}s" if isinstance(delay, (int, float)) else str(delay or "Nao informado")
    mensagem_id_texto = f"`{mensagem_id}`" if mensagem_id else "Nao informado"
    await enviar_log_bot(
        "🗑️ Exclusao temporaria agendada",
        (
            f"**Origem:** {origem}\n"
            f"**Alvo:** {alvo}\n"
            f"**Usuario:** {_formatar_usuario(autor)}\n"
            f"**Canal:** {_formatar_canal(canal)}\n"
            f"**Delay:** {detalhes_delay}\n"
            f"**Mensagem ID:** {mensagem_id_texto}\n"
            f"**Conteudo:** {_resumir_texto(conteudo)}"
        ),
        guild_ou_id=guild_ou_id,
    )
