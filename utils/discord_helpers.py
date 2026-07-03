import asyncio
import json
from datetime import datetime, timedelta, timezone

import discord

import data.runtime as runtime
from config import COOLDOWN_RECRUTAMENTO
from services.bot_context import get_bot
from services.server_config import obter_valor_config


def usuario_tem_cargo(message, cargo_id):
    if not hasattr(message.author, "roles"):
        return False

    for cargo in message.author.roles:
        if cargo.id == cargo_id:
            return True

    return False


def membro_eh_staff(membro):
    if not hasattr(membro, "roles"):
        return False

    cargo_staff_id = obter_valor_config(getattr(membro, "guild", None), "CARGO_STAFF_ID")
    for cargo in membro.roles:
        if cargo.id == cargo_staff_id:
            return True

    return False


def membro_pode_pedir_feedback(membro):
    if not hasattr(membro, "roles"):
        return False

    guild = getattr(membro, "guild", None)
    cargos_permitidos = {
        obter_valor_config(guild, "CARGO_STAFF_ID"),
        obter_valor_config(guild, "CARGO_RECRUTAMENTO_ID"),
    }

    for cargo in membro.roles:
        if cargo.id in cargos_permitidos:
            return True

    return False


def membro_eh_lideranca(membro):
    if not hasattr(membro, "roles"):
        return False

    cargos_lideranca_ids = set(obter_valor_config(getattr(membro, "guild", None), "CARGOS_LIDERANCA_IDS", []))
    for cargo in membro.roles:
        if cargo.id in cargos_lideranca_ids:
            return True

    return False


async def respondeu_mensagem_do_bot(message):
    bot = get_bot()
    if not bot or not message.reference or not message.reference.message_id:
        return False, None

    try:
        mensagem_respondida = await message.channel.fetch_message(message.reference.message_id)
        return mensagem_respondida.author.id == bot.user.id, mensagem_respondida
    except Exception:
        return False, None


def procurar_membro_por_texto(guild, texto):
    if not guild or not texto:
        return None

    texto = texto.strip()
    if not texto:
        return None

    texto_limpo = texto
    if texto.startswith("<@") and texto.endswith(">"):
        texto_limpo = texto.replace("<@", "").replace("<@!", "").replace(">", "").strip()
        if texto_limpo.isdigit():
            return guild.get_member(int(texto_limpo))

    if texto.isdigit():
        membro = guild.get_member(int(texto))
        if membro:
            return membro

    texto_casefold = texto.casefold()

    for membro in guild.members:
        if membro.name.casefold() == texto_casefold:
            return membro
        if membro.display_name.casefold() == texto_casefold:
            return membro
        if str(membro).casefold() == texto_casefold:
            return membro

    correspondencias = []

    for membro in guild.members:
        if texto_casefold in membro.name.casefold():
            correspondencias.append(membro)
            continue
        if texto_casefold in membro.display_name.casefold():
            correspondencias.append(membro)
            continue
        if texto_casefold in str(membro).casefold():
            correspondencias.append(membro)

    if len(correspondencias) == 1:
        return correspondencias[0]

    return None


def criar_embed_tags(titulo, descricao=None):
    embed = discord.Embed(
        title=titulo,
        description=descricao or "",
        color=discord.Color.from_rgb(69, 211, 232),
    )
    embed.set_author(name="Raven Tags")
    return embed


def gerar_mensagem_reacao(destino, canal_id, guild_ou_id=None):
    cargo_aviso_reacao_id = obter_valor_config(guild_ou_id, "CARGO_AVISO_REACAO_ID")
    mensagens = {
        "jogatina": (
            f"<@&{cargo_aviso_reacao_id}> deixa a reação em <#{canal_id}> "
            f"só pra gente saber que vocês têm visão."
        ),
        "invasão": (
            f"<@&{cargo_aviso_reacao_id}> deixa tua reação em <#{canal_id}> "
            f"e mostra que tu não tá dormindo."
        ),
        "invasao": (
            f"<@&{cargo_aviso_reacao_id}> deixa tua reação em <#{canal_id}> "
            f"e mostra que tu não tá dormindo."
        ),
        "cronograma": (
            f"<@&{cargo_aviso_reacao_id}> quem viu o cronograma reage em <#{canal_id}> "
            f"pra não sobrar o clássico \"nem vi\"."
        ),
        "avisos": (
            f"<@&{cargo_aviso_reacao_id}> reage em <#{canal_id}> "
            f"pra não dizer depois que foi pego de surpresa."
        ),
    }

    return mensagens.get(destino.lower())


def extrair_recrutado_texto(message):
    if message.mentions:
        primeiro = message.mentions[0]
        return f"{primeiro.mention}"

    partes = message.content.strip().split(maxsplit=1)
    if len(partes) > 1:
        resto = partes[1].strip()
        if resto:
            return resto

    return None


def resolver_recrutado_texto(guild, message):
    partes = message.content.strip().split(maxsplit=1)

    if len(partes) < 2:
        return None

    texto_recrutado = partes[1].strip()
    if not texto_recrutado:
        return None

    membro = procurar_membro_por_texto(guild, texto_recrutado)
    if membro:
        return membro.mention

    return texto_recrutado


async def buscar_mensagem_recrutamento_por_id(canal_id, message_id):
    bot = get_bot()
    if not bot:
        return None

    canal = bot.get_channel(canal_id)
    if not canal:
        try:
            canal = await bot.fetch_channel(canal_id)
        except Exception:
            return None

    try:
        return await canal.fetch_message(int(message_id))
    except Exception:
        return None


def extrair_recrutado_de_mensagem_antiga(guild, message):
    partes = message.content.strip().split(maxsplit=1)

    if len(partes) < 2:
        return None

    texto_recrutado = partes[1].strip()
    if not texto_recrutado:
        return None

    membro = procurar_membro_por_texto(guild, texto_recrutado)
    if membro:
        return membro.mention

    return texto_recrutado


def resolver_recrutado_membro(guild, message):
    partes = message.content.strip().split(maxsplit=1)

    if len(partes) < 2:
        return None

    texto_recrutado = partes[1].strip()
    if not texto_recrutado:
        return None

    return procurar_membro_por_texto(guild, texto_recrutado)


def mensagem_eh_recrutamento(texto):
    texto = texto.strip()
    if not texto.lower().startswith("+1"):
        return False

    partes = texto.split(maxsplit=1)
    return len(partes) > 1 and bool(partes[1].strip())


def obter_gatilho(nome):
    return runtime.GATILHOS.get(nome.lower())


def listar_nomes_gatilhos():
    return sorted(runtime.GATILHOS.keys())


def resetar_gatilhos_para_base():
    runtime.GATILHOS = json.loads(json.dumps(runtime.GATILHOS_BASE))


def usuario_pode_registrar_recrutamento(user_id, agora):
    ultimo_uso = runtime.cooldowns_recrutamento.get(user_id, 0)
    return (agora - ultimo_uso) >= COOLDOWN_RECRUTAMENTO


async def buscar_mensagem_por_id_na_guild(guild, message_id):
    if not guild:
        return None

    canais = []

    for canal in guild.text_channels:
        if hasattr(canal, "fetch_message"):
            canais.append(canal)

    for canal in guild.forums:
        if hasattr(canal, "threads"):
            for thread in canal.threads:
                if hasattr(thread, "fetch_message"):
                    canais.append(thread)

    for thread in guild.threads:
        if hasattr(thread, "fetch_message"):
            canais.append(thread)

    vistos = set()

    for canal in canais:
        if canal.id in vistos:
            continue
        vistos.add(canal.id)

        try:
            mensagem = await canal.fetch_message(int(message_id))
            if mensagem:
                return mensagem
        except Exception:
            continue

    return None


async def limpar_mensagens_do_canal(canal, quantidade, ignorar_message_id=None, aviso_callback=None, retornar_detalhes=False):
    mensagens = []

    async for mensagem in canal.history(limit=None):
        if ignorar_message_id and mensagem.id == ignorar_message_id:
            continue
        if mensagem.pinned:
            continue

        mensagens.append(mensagem)
        if len(mensagens) >= quantidade:
            break

    if not mensagens:
        if retornar_detalhes:
            return {
                "removidas": 0,
                "recentes": 0,
                "antigas": 0,
            }
        return 0

    agora_utc = datetime.now(timezone.utc)
    recentes = []
    antigas = []

    for mensagem in mensagens:
        idade = agora_utc - mensagem.created_at
        if idade <= timedelta(days=14):
            recentes.append(mensagem)
        else:
            antigas.append(mensagem)

    if aviso_callback and antigas:
        try:
            await aviso_callback(len(antigas), len(mensagens))
        except Exception:
            pass

    removidas = 0

    for i in range(0, len(recentes), 100):
        lote = recentes[i:i + 100]
        try:
            if len(lote) == 1:
                await lote[0].delete()
            else:
                await canal.delete_messages(lote)
            removidas += len(lote)
        except Exception:
            for mensagem in lote:
                try:
                    await mensagem.delete()
                    removidas += 1
                    await asyncio.sleep(0.35)
                except Exception:
                    continue

    for mensagem in antigas:
        try:
            await mensagem.delete()
            removidas += 1
            await asyncio.sleep(0.35)
        except Exception:
            continue

    if retornar_detalhes:
        return {
            "removidas": removidas,
            "recentes": len(recentes),
            "antigas": len(antigas),
        }

    return removidas
