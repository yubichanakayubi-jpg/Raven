import random
from datetime import timedelta

import discord

from config import (
    CANAL_STAFF_TAGS_ID,
    CARGO_STAFF_ID,
    FRASES_TAG_10_DIAS,
    FRASES_TAG_7_DIAS,
    TAG_LOG_CHANNEL_ID,
)
from services.d1 import carregar_dados_tags
from services.logs import enviar_log_bot
from utils.discord_helpers import criar_embed_tags, procurar_membro_por_texto
from utils.time_utils import dias_passados_desde, formatar_data_br, parse_iso_datetime


async def resolver_pendente_tag(guild, texto):
    texto = (texto or "").strip()
    if not texto:
        return None

    membro = procurar_membro_por_texto(guild, texto)

    if not membro and texto.isdigit() and guild:
        try:
            membro = await guild.fetch_member(int(texto))
        except Exception:
            membro = None

    if membro:
        return {
            "user_id": str(membro.id),
            "nome": str(membro),
            "mention": membro.mention
        }

    dados = await carregar_dados_tags()
    pendentes = dados.get("pendentes", {})

    if texto.isdigit():
        registro = pendentes.get(texto)
        if registro:
            return {
                "user_id": str(registro.get("user_id")),
                "nome": registro.get("nome") or str(registro.get("user_id")),
                "mention": f"<@{registro.get('user_id')}>"
            }

    texto_casefold = texto.casefold()
    correspondencias = []

    for registro in pendentes.values():
        nome_registro = str(registro.get("nome", "")).strip()
        if not nome_registro:
            continue

        nome_casefold = nome_registro.casefold()
        if texto_casefold == nome_casefold:
            return {
                "user_id": str(registro.get("user_id")),
                "nome": nome_registro,
                "mention": f"<@{registro.get('user_id')}>"
            }

        if texto_casefold in nome_casefold:
            correspondencias.append(registro)

    if len(correspondencias) == 1:
        registro = correspondencias[0]
        return {
            "user_id": str(registro.get("user_id")),
            "nome": registro.get("nome") or str(registro.get("user_id")),
            "mention": f"<@{registro.get('user_id')}>"
        }

    return None


async def obter_canal_logs_tags(bot, guild):
    canal_logs_id = TAG_LOG_CHANNEL_ID or CANAL_STAFF_TAGS_ID
    if not canal_logs_id:
        return None

    canal = bot.get_channel(canal_logs_id)
    if canal:
        return canal

    try:
        canal = await bot.fetch_channel(canal_logs_id)
    except Exception:
        canal = None

    if canal and getattr(canal, "guild", None) and canal.guild.id != guild.id:
        return None

    return canal


def construir_link_mensagem(guild_id, canal_id, message_id):
    if not guild_id or not canal_id or not message_id:
        return None
    return f"https://discord.com/channels/{guild_id}/{canal_id}/{message_id}"


def formatar_link_mensagem(url):
    if not url:
        return "Não disponível"
    return f"[Abrir mensagem]({url})"


async def formatar_membro_registro_tag(guild, registro):
    user_id = str(registro.get("user_id") or "").strip()
    nome_salvo = str(registro.get("nome") or "").strip()
    membro = None

    if guild and user_id.isdigit():
        membro = guild.get_member(int(user_id))
        if not membro:
            try:
                membro = await guild.fetch_member(int(user_id))
            except Exception:
                membro = None

    nome = getattr(membro, "display_name", None) or nome_salvo or (f"ID {user_id}" if user_id else "Membro desconhecido")
    if user_id:
        return f"**{nome}** (<@{user_id}>)"
    return f"**{nome}**"


def formatar_membro_objeto_tag(membro):
    nome = getattr(membro, "display_name", None) or getattr(membro, "name", None) or str(membro)
    mencao = getattr(membro, "mention", None) or str(membro)
    return f"**{nome}** ({mencao})"


def obter_prazo_troca_iso(registro):
    prazo_troca = registro.get("prazo_troca")
    if prazo_troca:
        return prazo_troca

    data_registro = parse_iso_datetime(registro.get("data_envio", ""))
    if not data_registro:
        return ""

    return (data_registro + timedelta(days=7)).isoformat()


def obter_link_print_original(registro, guild_id=None):
    link = registro.get("message_link")
    if link:
        return link
    return construir_link_mensagem(
        guild_id,
        registro.get("canal_origem_id"),
        registro.get("message_id"),
    )


def formatar_tempo_ate_conclusao(data_inicio_iso, data_fim_iso):
    inicio = parse_iso_datetime(data_inicio_iso)
    fim = parse_iso_datetime(data_fim_iso)
    if not inicio or not fim:
        return "Não foi possível calcular"

    delta = fim - inicio
    if delta.total_seconds() < 0:
        delta = -delta

    dias = delta.days
    horas = delta.seconds // 3600
    minutos = (delta.seconds % 3600) // 60

    partes = []
    if dias:
        partes.append(f"{dias} dia(s)")
    if horas:
        partes.append(f"{horas} hora(s)")
    if minutos and not dias:
        partes.append(f"{minutos} minuto(s)")

    if not partes:
        return "Menos de 1 minuto"
    return " e ".join(partes[:2])


async def enviar_embed_logs_tags(bot, guild, embed):
    canal_logs = await obter_canal_logs_tags(bot, guild)
    if canal_logs and hasattr(canal_logs, "send"):
        try:
            await canal_logs.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True, roles=True),
            )
            return
        except Exception as erro:
            print(f"[TAGS] Erro ao enviar embed no canal de logs: {erro}")

    descricao = embed.description or "Sem descrição."
    await enviar_log_bot(embed.title or "Log de Tags", descricao)


async def enviar_log_timetag_registrada(bot, guild, membro, staff, registro):
    embed = discord.Embed(
        title="☾ Timetag Registrada",
        description="Um membro foi adicionado à lista de pendentes para troca de tag.",
        color=discord.Color.from_rgb(0, 255, 255),
    )
    embed.add_field(name="Membro", value=formatar_membro_objeto_tag(membro), inline=False)
    embed.add_field(name="Status", value="Pendente", inline=False)
    embed.add_field(name="Registrado por", value=staff.mention, inline=False)
    embed.add_field(name="Data de registro", value=formatar_data_br(registro.get("data_envio", "")), inline=False)
    embed.add_field(name="Prazo para troca", value=formatar_data_br(obter_prazo_troca_iso(registro)), inline=False)
    embed.add_field(
        name="Print",
        value=formatar_link_mensagem(obter_link_print_original(registro, guild.id)),
        inline=False,
    )
    embed.set_footer(text="FDN • Controle de Tags")
    await enviar_embed_logs_tags(bot, guild, embed)


async def enviar_log_timetag_duplicada(bot, guild, membro, registro_existente, message):
    embed = discord.Embed(
        title="☾ Timetag Já Registrada",
        description="Este membro já possui uma pendência ativa de troca de tag.",
        color=discord.Color.from_rgb(0, 255, 255),
    )
    embed.add_field(name="Membro", value=formatar_membro_objeto_tag(membro), inline=False)
    embed.add_field(name="Status atual", value="Pendente", inline=False)
    embed.add_field(name="Registrado em", value=formatar_data_br(registro_existente.get("data_envio", "")), inline=False)
    embed.add_field(name="Prazo", value=formatar_data_br(obter_prazo_troca_iso(registro_existente)), inline=False)
    embed.add_field(name="Nova mensagem", value=formatar_link_mensagem(message.jump_url), inline=False)
    embed.set_footer(text="FDN • Controle de Tags")
    await enviar_embed_logs_tags(bot, guild, embed)


async def enviar_log_tag_concluida(bot, guild, membro, staff, registro_concluido, message):
    embed = discord.Embed(
        title="☾ Tag Concluída",
        description="Um membro pendente concluiu a troca de tag.",
        color=discord.Color.from_rgb(0, 255, 255),
    )
    embed.add_field(name="Membro", value=formatar_membro_objeto_tag(membro), inline=False)
    embed.add_field(name="Status", value="Concluído", inline=False)
    embed.add_field(name="Registrado em", value=formatar_data_br(registro_concluido.get("data_envio", "")), inline=False)
    embed.add_field(name="Concluído em", value=formatar_data_br(registro_concluido.get("data_conclusao", "")), inline=False)
    embed.add_field(
        name="Tempo até conclusão",
        value=formatar_tempo_ate_conclusao(
            registro_concluido.get("data_envio", ""),
            registro_concluido.get("data_conclusao", ""),
        ),
        inline=False,
    )
    embed.add_field(name="Concluído por", value=staff.mention, inline=False)
    embed.add_field(name="Print da tag", value=formatar_link_mensagem(message.jump_url), inline=False)
    embed.set_footer(text="FDN • Controle de Tags")
    await enviar_embed_logs_tags(bot, guild, embed)


async def enviar_log_tag_verificada(bot, guild, membro, staff, canal, message):
    embed = discord.Embed(
        title="☾ Tag Verificada",
        description="Um print de tag foi validado, mas o membro não estava na lista de pendentes.",
        color=discord.Color.from_rgb(0, 255, 255),
    )
    embed.add_field(name="Membro", value=formatar_membro_objeto_tag(membro), inline=False)
    embed.add_field(name="Verificado por", value=staff.mention, inline=False)
    embed.add_field(name="Canal", value=canal.mention, inline=False)
    embed.add_field(name="Mensagem", value=formatar_link_mensagem(message.jump_url), inline=False)
    embed.add_field(name="Resultado", value="Nenhuma pendência encontrada para este membro.", inline=False)
    embed.set_footer(text="FDN • Controle de Tags")
    await enviar_embed_logs_tags(bot, guild, embed)


def criar_embed_lembrete_dm_tag(registro):
    user_id = str(registro.get("user_id") or "").strip()
    nome = str(registro.get("nome") or "").strip() or (f"ID {user_id}" if user_id else "Membro")
    membro_texto = f"**{nome}** (<@{user_id}>)" if user_id else f"**{nome}**"
    embed = discord.Embed(
        title="🌙 Lembrete da tag FDN",
        description=(
            f"Membro: {membro_texto}\n\n"
            "Mande o print com a tag no canal de tags!"
        ),
        color=discord.Color.from_rgb(0, 255, 255),
    )
    embed.add_field(name="📁 Registrado em", value=formatar_data_br(registro.get("data_envio", "")), inline=False)
    embed.add_field(name="⏰ Prazo atingido em", value=formatar_data_br(obter_prazo_troca_iso(registro)), inline=False)
    embed.set_footer(text="FDN • Controle de Tags")
    return embed


async def enviar_lembrete_prazo_tag(canal, registro, status_aviso_privado=None):
    guild = getattr(canal, "guild", None)
    guild_id = getattr(guild, "id", None)
    embed = discord.Embed(
        title="☾ Prazo de Tag Atingido",
        description="O prazo de 7 dias para troca de tag foi atingido.",
        color=discord.Color.from_rgb(0, 255, 255),
    )
    embed.add_field(name="Membro", value=await formatar_membro_registro_tag(guild, registro), inline=False)
    embed.add_field(name="Registrado em", value=formatar_data_br(registro.get("data_envio", "")), inline=False)
    embed.add_field(name="Prazo atingido em", value=formatar_data_br(obter_prazo_troca_iso(registro)), inline=False)
    embed.add_field(name="Status", value="Pendente", inline=False)
    embed.add_field(
        name="Print original",
        value=formatar_link_mensagem(obter_link_print_original(registro, guild_id)),
        inline=False,
    )
    embed.add_field(
        name="Ação necessária",
        value="Verificar se o membro já realizou a troca de tag no Roblox.",
        inline=False,
    )
    if status_aviso_privado:
        embed.add_field(name="Aviso no privado", value=status_aviso_privado, inline=False)
    embed.set_footer(text="FDN • Controle de Tags")
    await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=True))


async def enviar_aviso_tags_em_lote(canal, registros, dias):
    if not registros:
        return

    if dias >= 10:
        cabecalho = random.choice(FRASES_TAG_10_DIAS)
        titulo = "⚠️ Lembrete de tags"
    else:
        cabecalho = random.choice(FRASES_TAG_7_DIAS)
        titulo = "🔔 Lembrete de tags"

    linhas = []
    guild = getattr(canal, "guild", None)
    for registro in registros:
        membro_texto = await formatar_membro_registro_tag(guild, registro)
        linhas.append(f"{membro_texto} - **{dias} dias**")

    embed = criar_embed_tags(
        titulo=titulo,
        descricao=f"<@&{CARGO_STAFF_ID}> {cabecalho}\n\n" + "\n".join(linhas)
    )

    await canal.send(
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True, roles=True)
    )


async def enviar_alerta_tags_atrasadissimas(canal, registros):
    if not registros:
        return

    linhas = []
    guild = getattr(canal, "guild", None)
    for registro in registros:
        dias = dias_passados_desde(registro.get("data_envio", ""))
        membro_texto = await formatar_membro_registro_tag(guild, registro)
        linhas.append(f"{membro_texto} - **{dias} dias**")

    embed = criar_embed_tags(
        titulo="🚨 Tags atrasadíssimas",
        descricao=(
            f"<@&{CARGO_STAFF_ID}> Lembrete de tags: a troca de tags segue no mesmo ritmo de fila de SUS.\n\n"
            f"**Atrasadíssimos do time tags:**\n" + "\n".join(linhas)
        )
    )

    await canal.send(
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True, roles=True)
    )
