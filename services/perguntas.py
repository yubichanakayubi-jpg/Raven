import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path

import discord

from config import ARQUIVO_DADOS, FUSO_HORARIO, PERGUNTAS_DIARIAS
from services.bot_context import get_bot
from services.conquistas_raven import registrar_pergunta_diaria_fa_do_raven
from services.server_config import extrair_guild_id, obter_valor_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOCKS_PERGUNTAS = {}


def _caminho_dados_perguntas():
    return PROJECT_ROOT / ARQUIVO_DADOS


def _canal_pertence_ao_guild(canal, guild_id):
    if canal is None or guild_id is None:
        return True
    guild_canal = getattr(canal, "guild", None)
    return getattr(guild_canal, "id", None) == guild_id


def _obter_lock_pergunta(guild_id):
    chave = str(guild_id) if guild_id is not None else "_default"
    lock = _LOCKS_PERGUNTAS.get(chave)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS_PERGUNTAS[chave] = lock
    return lock


def _formatar_mencoes_lideranca(guild_ou_id=None):
    cargos_lideranca_ids = obter_valor_config(guild_ou_id, "CARGOS_LIDERANCA_IDS", [])
    mencoes = []
    for cargo_id in cargos_lideranca_ids or []:
        try:
            cargo_id = int(cargo_id)
        except (TypeError, ValueError):
            continue
        mencoes.append(f"<@&{cargo_id}>")
    return " ".join(mencoes)


def _dados_padrao_guild():
    return {
        "perguntas_usadas": [],
        "ultima_mensagem_id": None,
        "ultima_data": "",
    }


def _dados_padrao():
    return {"guilds": {}}


def carregar_todos_dados():
    caminho = _caminho_dados_perguntas()
    if not caminho.exists():
        return _dados_padrao()

    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError, TypeError):
        return _dados_padrao()

    if not isinstance(dados, dict):
        return _dados_padrao()

    if "guilds" in dados and isinstance(dados.get("guilds"), dict):
        guilds = {}
        for guild_id, dados_guild in dados["guilds"].items():
            if not isinstance(dados_guild, dict):
                continue
            guilds[str(guild_id)] = {
                "perguntas_usadas": dados_guild.get("perguntas_usadas", []),
                "ultima_mensagem_id": dados_guild.get("ultima_mensagem_id"),
                "ultima_data": dados_guild.get("ultima_data", ""),
            }
        return {"guilds": guilds}

    return {
        "guilds": {
            "_default": {
                "perguntas_usadas": dados.get("perguntas_usadas", []),
                "ultima_mensagem_id": dados.get("ultima_mensagem_id"),
                "ultima_data": dados.get("ultima_data", ""),
            }
        }
    }


def salvar_todos_dados(dados):
    caminho = _caminho_dados_perguntas()
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def carregar_dados(guild_ou_id=None):
    todos = carregar_todos_dados()
    guild_id = extrair_guild_id(guild_ou_id)
    chave = str(guild_id) if guild_id is not None else "_default"
    dados_guild = todos.get("guilds", {}).get(chave, _dados_padrao_guild())
    return {
        "perguntas_usadas": list(dados_guild.get("perguntas_usadas", [])),
        "ultima_mensagem_id": dados_guild.get("ultima_mensagem_id"),
        "ultima_data": dados_guild.get("ultima_data", ""),
    }


def salvar_dados(guild_ou_id, dados_guild):
    todos = carregar_todos_dados()
    guild_id = extrair_guild_id(guild_ou_id)
    chave = str(guild_id) if guild_id is not None else "_default"
    todos.setdefault("guilds", {})[chave] = {
        "perguntas_usadas": list(dados_guild.get("perguntas_usadas", [])),
        "ultima_mensagem_id": dados_guild.get("ultima_mensagem_id"),
        "ultima_data": dados_guild.get("ultima_data", ""),
    }
    salvar_todos_dados(todos)


async def enviar_pergunta_do_dia(forcar=False, guild_ou_id=None):
    bot = get_bot()
    if not bot:
        return False, "Não consegui encontrar o bot para enviar a pergunta."

    guild_id = extrair_guild_id(guild_ou_id)
    lock = _obter_lock_pergunta(guild_id)

    async with lock:
        agora = datetime.now(FUSO_HORARIO)
        dados = carregar_dados(guild_ou_id)
        data_hoje = agora.strftime("%Y-%m-%d")

        if not forcar and dados.get("ultima_data") == data_hoje:
            return False, "A pergunta da noite de hoje já foi enviada."

        canal_perguntas_id = obter_valor_config(guild_ou_id, "CANAL_PERGUNTAS_ID")
        canal_logs_id = obter_valor_config(guild_ou_id, "CANAL_LOGS_ID")

        canal = bot.get_channel(canal_perguntas_id)
        canal_logs = bot.get_channel(canal_logs_id)

        if canal is None and canal_perguntas_id:
            try:
                canal = await bot.fetch_channel(canal_perguntas_id)
            except Exception:
                canal = None

        if canal_logs is None and canal_logs_id:
            try:
                canal_logs = await bot.fetch_channel(canal_logs_id)
            except Exception:
                canal_logs = None

        if not _canal_pertence_ao_guild(canal, guild_id):
            return False, "O canal de perguntas configurado não pertence a este servidor."

        if not _canal_pertence_ao_guild(canal_logs, guild_id):
            canal_logs = None

        if not canal:
            return False, "Não consegui encontrar o canal de perguntas."

        perguntas_restantes = [
            pergunta
            for pergunta in PERGUNTAS_DIARIAS
            if pergunta not in dados["perguntas_usadas"]
        ]

        if not perguntas_restantes:
            if canal_logs:
                mencao_lideranca = _formatar_mencoes_lideranca(guild_ou_id)
                await canal_logs.send(
                    (
                        f"{mencao_lideranca}\n\n"
                        "⚠️ **Acabaram as perguntas automáticas.**\n"
                        "O bot tentou enviar a pergunta diária, mas não existe mais pergunta disponível na lista.\n\n"
                        "Adicione novas perguntas em `PERGUNTAS_DIARIAS` ou resete a lista de perguntas usadas."
                    ).strip(),
                    allowed_mentions=discord.AllowedMentions(roles=True),
                )
            dados["ultima_data"] = data_hoje
            salvar_dados(guild_ou_id, dados)
            return False, "Não há mais perguntas disponíveis na lista."

        pergunta = random.choice(perguntas_restantes)

        mensagem = await canal.send(
            f"@everyone\n\n{pergunta}",
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )

        if pergunta not in dados["perguntas_usadas"]:
            dados["perguntas_usadas"].append(pergunta)
        dados["ultima_mensagem_id"] = mensagem.id
        dados["ultima_data"] = data_hoje

        salvar_dados(guild_ou_id, dados)
        registrar_pergunta_diaria_fa_do_raven(
            guild_ou_id,
            mensagem.id,
            canal.id,
            enviada_em=agora,
            pergunta_texto=pergunta,
        )
        return True, None
