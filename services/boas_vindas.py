import asyncio
import json
import os

import discord

import data.runtime as runtime
from config import (
    ARQUIVO_DADOS_BOAS_VINDAS,
    FRASES_BEM_VINDO_MANUAL,
    FRASE_SEM_RESPOSTA_BOAS_VINDAS,
)
from services.bot_context import get_bot
from services.server_config import obter_valor_config


def registrar_contexto_boas_vindas(mensagem_bot):
    if not mensagem_bot:
        return

    runtime.contexto_respostas_bot[mensagem_bot.id] = {
        "gatilho": "boas_vindas",
        "mensagem_disparo": "mensagem de boas-vindas",
    }



def usuario_mandou_mensagem_desde(usuario_id, depois_de):
    ultima_data = runtime.ultima_mensagem_usuario.get(str(usuario_id))
    if not ultima_data:
        return False

    return ultima_data > depois_de


async def monitorar_boas_vindas_sem_resposta(mensagem_boas_vindas, usuario_id):
    if not FRASE_SEM_RESPOSTA_BOAS_VINDAS:
        return

    await asyncio.sleep(5 * 60)

    try:
        mensagem_atual = await mensagem_boas_vindas.channel.fetch_message(mensagem_boas_vindas.id)
    except Exception:
        return

    if usuario_mandou_mensagem_desde(usuario_id, mensagem_atual.created_at):
        return

    try:
        resposta = await mensagem_atual.reply(
            FRASE_SEM_RESPOSTA_BOAS_VINDAS,
            mention_author=False
        )
        registrar_contexto_boas_vindas(resposta)
    except Exception:
        return


def carregar_indice_boas_vindas():
    if not os.path.exists(ARQUIVO_DADOS_BOAS_VINDAS):
        return -1

    try:
        with open(ARQUIVO_DADOS_BOAS_VINDAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError, TypeError):
        return -1

    if not isinstance(dados, dict):
        return -1

    indice = dados.get("indice_boas_vindas", -1)
    if not isinstance(indice, int):
        return -1

    return indice


def salvar_indice_boas_vindas(indice):
    dados = {"indice_boas_vindas": indice}

    try:
        with open(ARQUIVO_DADOS_BOAS_VINDAS, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=4)
    except OSError:
        return


def escolher_frase_boas_vindas():
    if not FRASES_BEM_VINDO_MANUAL:
        return None

    if runtime.indice_boas_vindas < 0:
        runtime.indice_boas_vindas = carregar_indice_boas_vindas()

    runtime.indice_boas_vindas = (runtime.indice_boas_vindas + 1) % len(FRASES_BEM_VINDO_MANUAL)
    salvar_indice_boas_vindas(runtime.indice_boas_vindas)
    return FRASES_BEM_VINDO_MANUAL[runtime.indice_boas_vindas]


async def enviar_boas_vindas_no_geral(membro):
    bot = get_bot()
    if not bot:
        return None

    canal_geral_id = obter_valor_config(getattr(membro, "guild", None), "CANAL_GERAL_ID")
    canal_geral = bot.get_channel(canal_geral_id)
    if not canal_geral:
        try:
            canal_geral = await bot.fetch_channel(canal_geral_id)
        except Exception:
            return None

    frase_bem_vindo = escolher_frase_boas_vindas()
    if not frase_bem_vindo:
        return None

    conteudo_mensagem = frase_bem_vindo.format(membro=membro.mention)

    mensagem_enviada = await canal_geral.send(
        conteudo_mensagem,
        allowed_mentions=discord.AllowedMentions(users=True, roles=True)
    )
    registrar_contexto_boas_vindas(mensagem_enviada)

    if FRASE_SEM_RESPOSTA_BOAS_VINDAS:
        tarefa = asyncio.create_task(
            monitorar_boas_vindas_sem_resposta(mensagem_enviada, membro.id)
        )
        runtime.tarefas_background.add(tarefa)
        tarefa.add_done_callback(runtime.tarefas_background.discard)

    return mensagem_enviada
