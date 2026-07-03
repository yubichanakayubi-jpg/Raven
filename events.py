import re
import time
from datetime import datetime, timezone
import unicodedata
from typing import Iterable

import discord
from discord.ext import commands, tasks

import data.runtime as runtime
from config import (
    CANAL_CONTAGEM_ID,
    CANAL_GERAL_ID,
    CANAL_LOGS_ID,
    CANAL_PERGUNTAS_ID,
    CANAL_CONSELHO_ID,
    CANAL_STAFF_TAGS_ID,
    CANAL_TAGS_FINAL_ID,
    CANAL_TIME_TAGS_ID,
    CANAIS_REACAO,
    BOAS_VINDAS_ROLE_ID,
    CARGO_STAFF_ID,
    COOLDOWN_IA,
    COOLDOWN_MESMA_PESSOA,
    COOLDOWN_OUTRA_PESSOA,
    COOLDOWN_RECRUTAMENTO,
    COOLDOWN_REPLY_BOT_GLOBAL,
    COOLDOWN_REPLY_BOT_USUARIO,
    EMOJI_APROVAR_TAG,
    FRASES_MENCAO_VAZIA,
    FUSO_HORARIO,
    GATILHO_BOM_DIA_ATIVO,
    GATILHOS_ATIVOS,
    NPC_SEM_QUEST_COOLDOWN_SECONDS,
    NPC_SEM_QUEST_ROLE_ID,
    MENSAGEIRO_DA_NOITE_ROLE_ID,
    TICKET_CATEGORY_ID,
    TICKET_STAFF_ROLE_ID,
    TTL_MENSAGEM_PROCESSADA,
)
from services.boas_vindas import enviar_boas_vindas_no_geral
from services.d1 import (
    aplicar_frases_custom_nos_gatilhos,
    carregar_dados_tags,
    concluir_tag_pendente_com_detalhes,
    registrar_timetag_pendente,
    registrar_recrutamento,
    salvar_dados_tags,
    total_recrutamentos_mes,
)
from services.conquistas_raven import (
    CONQUISTA_FA_DO_RAVEN,
    formatar_data_iso_local,
    listar_perguntas_diarias_pendentes,
    marcar_pergunta_diaria_processada,
    obter_estado_fa_do_raven,
    obter_pergunta_diaria_aberta,
    registrar_resposta_fa_do_raven,
    remover_resposta_fa_do_raven,
)
from services.conquistas_presenca import carregar_dados_conquistas, salvar_dados_conquistas
from services.conquista_anuncios import enviar_embed_conquista
from services.ia import perguntar_ia
from services.logs import enviar_log_bot
from services.perguntas import carregar_dados as carregar_dados_perguntas
from services.perguntas import enviar_pergunta_do_dia
from services.server_config import obter_valor_config
from services.tags import (
    criar_embed_lembrete_dm_tag,
    enviar_alerta_tags_atrasadissimas,
    enviar_aviso_tags_em_lote,
    enviar_lembrete_prazo_tag,
    enviar_log_tag_concluida,
    enviar_log_tag_verificada,
    enviar_log_timetag_duplicada,
    enviar_log_timetag_registrada,
)
from services.xp import (
    XP_ROLE_THRESHOLDS,
    adicionar_xp_manual,
    carregar_dados_xp,
    obter_proxima_meta_xp,
    obter_role_key_por_xp,
    obter_estado_xp_usuario,
    ranking_xp,
    registrar_xp_message,
    remover_xp_manual,
    remover_xp_por_mensagem,
    resetar_xp_diario_se_preciso,
    resetar_xp_usuario,
    salvar_dados_xp,
)
from utils.discord_helpers import (
    criar_embed_tags,
    membro_eh_staff,
    mensagem_eh_recrutamento,
    resetar_gatilhos_para_base,
    respondeu_mensagem_do_bot,
    resolver_recrutado_texto,
    usuario_pode_registrar_recrutamento,
    usuario_tem_cargo,
)
from utils.text_utils import (
    classificar_intencao_mensagem,
    escolher_resposta_gatilho,
    gatilho_encontrado,
    resposta_percentual_deterministica,
)
from utils.time_utils import dias_passados_desde, parse_iso_datetime


NEKO_PAIXAO_USER_ID = 429457053791158281
LORD_BOT_ID = 646090835418546186
AFRODITE_USER_ID = 1402402097739337790
LORITA_BOT_ID = 297153970613387264

RESPOSTAS_CONFUSAS_RAVEN = (
    "Isso ficou aleatorio demais. Fala direito que eu respondo.",
    "Tentou me bugar, ne? Reformula isso melhor.",
    "Nao vou ficar adivinhando frase jogada a toa. Explica melhor.",
    "Se for pra conversar comigo, fala de um jeito que de pra entender.",
)
RESPOSTAS_CONFUSAS_RAVEN_FIRMES = (
    "Ja vi que voce quer me bugar. Quando quiser falar direito, eu respondo.",
    "Assim nao da. Manda uma frase compreensivel e eu continuo.",
    "Enquanto vier so coisa aleatoria, eu nao vou entrar nessa.",
)
RESPOSTAS_PEDIR_CONTEXTO_RAVEN = (
    "Ficou solto demais. Explica melhor que eu acompanho.",
    "Do jeito que veio, faltou contexto. Reformula rapidinho.",
    "Nao deu pra cravar o que voce quis dizer. Fala mais claro.",
)

FRASES_NPC_SEM_QUEST = (
    "{member} desbloqueou uma fala nova depois de 84 anos.",
    "Atencao: o NPC sem quest recebeu sinal de vida.",
    "O NPC foi ativado. Alguem entregou uma quest pra {member}?",
    "Atualizacao encontrada: {member} agora possui dialogo.",
    "{member} estava bugado no mapa, mas voltou.",
    "{member}, voce estava em modo paisagem esse tempo todo?",
    "Registro historico: {member} apareceu no chat.",
    "Parabens, {member}, voce desbloqueou a funcao interagir.",
    "{member} saiu do modo AFK eterno.",
    "O Raven detectou movimento em um NPC esquecido.",
    "{member}, cuidado: se continuar falando, pode virar membro ativo.",
    "{member} abriu o menu de interacao pela primeira vez.",
    "Alguem aceitou a missao secundaria chamada fazer {member} aparecer.",
    "{member} foi encontrado parado no spawn desde a ultima atualizacao.",
    "O NPC sem quest recebeu um patch de atividade.",
    "{member} desbloqueou: presenca minima.",
)


def gatilho_permitido_no_horario(chave):
    hora_atual = datetime.now(FUSO_HORARIO).hour

    if chave == "bom_dia":
        return 5 <= hora_atual < 12

    if chave == "boa_tarde":
        return 12 <= hora_atual < 18

    return True


GATILHOS_CIDADES = {
    "paulista",
    "nordestino",
    "baiano",
    "carioca",
    "portugal",
    "sulista",
}


def mensagem_valida_fa_do_raven(message):
    texto = " ".join(str(getattr(message, "content", "") or "").split()).strip()
    if len(texto) < 3:
        return False
    return any(caractere.isalnum() for caractere in texto)


def membro_tem_cargo_por_id(membro, cargo_id):
    if membro is None or not cargo_id:
        return False
    try:
        cargo_id = int(cargo_id)
    except (TypeError, ValueError):
        return False
    return any(getattr(cargo, "id", None) == cargo_id for cargo in getattr(membro, "roles", []))


def nome_indica_canal_bloqueado(canal) -> bool:
    nome_canal = str(getattr(canal, "name", "") or "").strip().casefold()
    nome_categoria = str(getattr(getattr(canal, "category", None), "name", "") or "").strip().casefold()
    termos = ("staff", "ticket", "regra", "regras", "aviso", "avisos")
    return any(termo in nome_canal or termo in nome_categoria for termo in termos)


def canal_bloqueado_para_npc(message, canais_bloqueados: Iterable[int]) -> bool:
    if canal_eh_ticket(message.channel):
        return True
    if getattr(message.channel, "id", None) in set(canais_bloqueados):
        return True
    return nome_indica_canal_bloqueado(message.channel)


def membro_elegivel_fa_do_raven(membro):
    if membro is None or getattr(membro, "bot", False):
        return False
    if membro_eh_staff(membro):
        return False

    cargo_base_id = obter_valor_config(getattr(membro, "guild", None), "BOAS_VINDAS_ROLE_ID", BOAS_VINDAS_ROLE_ID)
    return any(getattr(cargo, "id", None) == cargo_base_id for cargo in getattr(membro, "roles", []))


async def obter_canal_destino_gatilho(bot, message, chave):
    if chave not in {"comando_interagir", "comando_jogatina", *GATILHOS_CIDADES}:
        return message.channel

    canal_geral_id = obter_valor_config(getattr(message, "guild", None), "CANAL_GERAL_ID")
    canal_geral = bot.get_channel(canal_geral_id)
    if canal_geral:
        return canal_geral

    try:
        return await bot.fetch_channel(canal_geral_id)
    except Exception:
        return None


async def limpar_mensagem_comando_gatilho(message, chave):
    if chave != "comando_interagir":
        return

    try:
        await message.delete()
    except Exception:
        return


async def responder_npc_sem_quest_se_necessario(bot, message, agora):
    guild = getattr(message, "guild", None)
    if guild is None or getattr(message.author, "bot", False):
        return False

    cargo_npc_id = obter_valor_config(guild, "NPC_SEM_QUEST_ROLE_ID", NPC_SEM_QUEST_ROLE_ID)
    if not membro_tem_cargo_por_id(message.author, cargo_npc_id):
        return False

    canais_bloqueados = {
        obter_valor_config(guild, "CANAL_STAFF_TAGS_ID", CANAL_STAFF_TAGS_ID),
        obter_valor_config(guild, "CANAL_CONSELHO_ID"),
        obter_valor_config(guild, "CANAL_LOGS_ID"),
        obter_valor_config(guild, "CANAL_CONTAGEM_ID", CANAL_CONTAGEM_ID),
        obter_valor_config(guild, "CANAL_TAGS_FINAL_ID", CANAL_TAGS_FINAL_ID),
        obter_valor_config(guild, "CANAL_TIME_TAGS_ID", CANAL_TIME_TAGS_ID),
        int(dict(obter_valor_config(guild, "CANAIS_REACAO", CANAIS_REACAO)).get("avisos", 0) or 0),
    }
    canais_bloqueados = {int(canal_id) for canal_id in canais_bloqueados if canal_id}
    canal_geral_id = obter_valor_config(guild, "CANAL_GERAL_ID", CANAL_GERAL_ID)
    if canal_geral_id:
        canais_bloqueados.discard(int(canal_geral_id))
    if canal_bloqueado_para_npc(message, canais_bloqueados):
        return False

    texto = " ".join(str(getattr(message, "content", "") or "").split()).strip()
    if not texto or texto.startswith("!"):
        return False

    cooldown = int(obter_valor_config(guild, "NPC_SEM_QUEST_COOLDOWN_SECONDS", NPC_SEM_QUEST_COOLDOWN_SECONDS) or NPC_SEM_QUEST_COOLDOWN_SECONDS)
    chave_cooldown = f"npc_sem_quest:{guild.id}:{message.author.id}"
    ultimo_uso = runtime.cooldowns_usuario.get(chave_cooldown, 0)
    if agora - ultimo_uso < cooldown:
        return False

    resposta_base = escolher_resposta_gatilho("npc_sem_quest", FRASES_NPC_SEM_QUEST)
    if not resposta_base:
        return False

    resposta = resposta_base.format(member=message.author.display_name)
    try:
        mensagem_bot = await enviar_resposta_em_contexto(message.channel, message, resposta)
    except Exception as erro:
        print(
            f"[NPC] Erro ao responder NPC sem quest | "
            f"guild={getattr(guild, 'id', None)} canal={getattr(message.channel, 'id', None)} "
            f"user={getattr(message.author, 'id', None)} erro={erro!r}"
        )
        return False

    runtime.cooldowns_usuario[chave_cooldown] = agora
    if mensagem_bot:
        registrar_contexto_resposta_bot(mensagem_bot, "npc_sem_quest", message)
    return bool(mensagem_bot)


def canal_eh_ticket(canal):
    if not canal:
        return False

    if getattr(canal, "category_id", None) == obter_valor_config(getattr(canal, "guild", None), "TICKET_CATEGORY_ID"):
        return True

    topico = getattr(canal, "topic", "") or ""
    return "ticket_author_id=" in topico


def extrair_estado_ticket(canal):
    topico = getattr(canal, "topic", "") or ""
    match_author = re.search(r"ticket_author_id=(\d+)", topico)
    match_status = re.search(r"ticket_status=([a-zA-Z]+)", topico)
    match_responsavel = re.search(r"ticket_responsavel_id=(\d+)", topico)

    return {
        "author_id": int(match_author.group(1)) if match_author else None,
        "status": match_status.group(1).strip().lower() if match_status else None,
        "responsavel_id": int(match_responsavel.group(1)) if match_responsavel else None,
    }


async def avisar_assumir_ticket_se_necessario(message, agora):
    if not canal_eh_ticket(message.channel):
        return

    ticket_staff_role_id = obter_valor_config(getattr(message, "guild", None), "TICKET_STAFF_ROLE_ID")
    if not usuario_tem_cargo(message, ticket_staff_role_id):
        return

    dados_ticket = extrair_estado_ticket(message.channel)
    if dados_ticket["status"] != "open" or not dados_ticket["author_id"]:
        return

    if message.author.id == dados_ticket["author_id"]:
        return

    if dados_ticket["responsavel_id"] == message.author.id:
        return

    chave_cooldown = f"aviso_assumir_ticket:{message.channel.id}:{message.author.id}"
    ultimo_aviso = runtime.cooldowns_global.get(chave_cooldown, 0)
    if agora - ultimo_aviso < 30:
        return

    runtime.cooldowns_global[chave_cooldown] = agora
    verbo = "reivindique" if dados_ticket["responsavel_id"] else "assuma"
    await message.channel.send(
        f"{message.author.mention} se você vai atender esse ticket então {verbo} ele primeiro por favor!",
        allowed_mentions=discord.AllowedMentions(users=True, roles=False),
        delete_after=12,
    )


def registrar_contexto_resposta_bot(mensagem_bot, chave, mensagem_origem, **extras):
    contexto = {
        "gatilho": chave,
        "mensagem_disparo": mensagem_origem.content,
    }
    contexto.update(extras)
    runtime.contexto_respostas_bot[mensagem_bot.id] = contexto


RAVEN_CONVERSA_TTL_SECONDS = 240
RAVEN_CONVERSA_MAX_ITENS = 8
RAVEN_RESPOSTA_FORA_CONTEXTO = "Acho que me perdi um pouco 😅 repete pra mim?"
RAVEN_TOPICOS_FORTES = {
    "filme",
    "cinema",
    "serie",
    "idade",
    "evento",
    "invasao",
    "jogatina",
    "ticket",
    "ficha",
    "cadastro",
    "staff",
    "neko",
    "lord",
}


def chave_usuario_conversa_raven(message):
    guild_id = getattr(getattr(message, "guild", None), "id", 0)
    channel_id = getattr(getattr(message, "channel", None), "id", 0)
    author_id = getattr(getattr(message, "author", None), "id", 0)
    return f"{guild_id}:{channel_id}:{author_id}"


def gerar_session_id_raven(message, agora_ts):
    guild_id = getattr(getattr(message, "guild", None), "id", 0)
    channel_id = getattr(getattr(message, "channel", None), "id", 0)
    author_id = getattr(getattr(message, "author", None), "id", 0)
    message_id = getattr(message, "id", int(agora_ts * 1000))
    return f"raven:{guild_id}:{channel_id}:{author_id}:{message_id}"


def criar_sessao_raven(message, motivo, agora_ts):
    session_id = gerar_session_id_raven(message, agora_ts)
    return {
        "session_id": session_id,
        "user_key": chave_usuario_conversa_raven(message),
        "guild_id": getattr(getattr(message, "guild", None), "id", 0),
        "channel_id": getattr(getattr(message, "channel", None), "id", 0),
        "author_id": getattr(getattr(message, "author", None), "id", 0),
        "topic": "",
        "messages": [],
        "last_ts": agora_ts,
        "last_bot_ts": 0.0,
        "last_speaker": None,
        "last_bot_message_id": None,
        "started_reason": motivo,
    }


def limpar_conversas_raven_expiradas(agora_ts):
    for session_id, dados in list(runtime.raven_conversas.items()):
        ultimo_ts = float(dados.get("last_ts", 0.0) or 0.0)
        if ultimo_ts and agora_ts - ultimo_ts <= RAVEN_CONVERSA_TTL_SECONDS:
            continue
        runtime.raven_conversas.pop(session_id, None)
        user_key = str(dados.get("user_key") or "")
        if user_key and runtime.raven_conversas_por_usuario.get(user_key) == session_id:
            runtime.raven_conversas_por_usuario.pop(user_key, None)
        last_bot_message_id = dados.get("last_bot_message_id")
        if last_bot_message_id:
            runtime.raven_sessoes_por_mensagem.pop(int(last_bot_message_id), None)


def obter_sessao_raven(session_id, agora_ts=None):
    if not session_id:
        return None

    sessao = runtime.raven_conversas.get(session_id)
    if not sessao:
        return None

    if agora_ts is not None:
        ultimo_ts = float(sessao.get("last_ts", 0.0) or 0.0)
        if ultimo_ts and agora_ts - ultimo_ts > RAVEN_CONVERSA_TTL_SECONDS:
            limpar_conversas_raven_expiradas(agora_ts)
            return None

    return sessao


def obter_sessao_raven_por_mensagem_bot(message_id, agora_ts=None):
    if not message_id:
        return None
    session_id = runtime.raven_sessoes_por_mensagem.get(int(message_id))
    return obter_sessao_raven(session_id, agora_ts=agora_ts)


def obter_sessao_raven_para_followup(message, agora_ts):
    user_key = chave_usuario_conversa_raven(message)
    session_id = runtime.raven_conversas_por_usuario.get(user_key)
    if not session_id:
        return None

    sessao = obter_sessao_raven(session_id, agora_ts=agora_ts)
    if not sessao:
        runtime.raven_conversas_por_usuario.pop(user_key, None)
        return None

    ultimo_bot_ts = float(sessao.get("last_bot_ts", 0.0) or 0.0)
    if not ultimo_bot_ts or agora_ts - ultimo_bot_ts > RAVEN_CONVERSA_TTL_SECONDS:
        return None
    if sessao.get("last_speaker") != "bot":
        return None
    return sessao


def iniciar_nova_sessao_raven(message, motivo, agora_ts):
    sessao = criar_sessao_raven(message, motivo, agora_ts)
    runtime.raven_conversas[sessao["session_id"]] = sessao
    runtime.raven_conversas_por_usuario[sessao["user_key"]] = sessao["session_id"]
    return sessao


def preparar_sessao_reply_raven(message, mensagem_respondida, agora_ts):
    sessao = obter_sessao_raven_por_mensagem_bot(getattr(mensagem_respondida, "id", None), agora_ts=agora_ts)
    if sessao:
        runtime.raven_conversas_por_usuario[sessao["user_key"]] = sessao["session_id"]
        return sessao

    sessao = iniciar_nova_sessao_raven(message, "reply", agora_ts)
    registrar_item_sessao_raven(
        sessao,
        speaker="bot",
        author_label=f"RAVEN (id={mensagem_respondida.author.id})",
        author_id=mensagem_respondida.author.id,
        content=conteudo_mensagem_para_contexto_ia(mensagem_respondida, 260),
        message_id=mensagem_respondida.id,
        original_content=getattr(mensagem_respondida, "content", "") or "",
    )
    sessao["last_bot_ts"] = agora_ts
    sessao["last_bot_message_id"] = mensagem_respondida.id
    sessao["last_speaker"] = "bot"
    runtime.raven_sessoes_por_mensagem[int(mensagem_respondida.id)] = sessao["session_id"]
    return sessao


def obter_historico_conversa_raven(sessao, limite=RAVEN_CONVERSA_MAX_ITENS):
    if not sessao:
        return []
    historico = list(sessao.get("messages") or [])
    return historico[-limite:]


def formatar_item_contexto_raven(item):
    rotulo = str(item.get("label") or "DESCONHECIDO")
    conteudo = str(item.get("content") or "").strip()
    return f"{rotulo}: {conteudo}".strip()


def registrar_item_sessao_raven(
    sessao,
    *,
    speaker,
    author_label,
    author_id,
    content,
    message_id=None,
    original_content=None,
):
    if not sessao or not content:
        return

    itens = list(sessao.get("messages") or [])
    if message_id and any(int(item.get("message_id") or 0) == int(message_id) for item in itens):
        return

    itens.append(
        {
            "speaker": speaker,
            "label": author_label,
            "author_id": author_id,
            "content": str(content).strip(),
            "original_content": str(original_content if original_content is not None else content).strip(),
            "message_id": int(message_id) if message_id else None,
        }
    )
    sessao["messages"] = itens[-RAVEN_CONVERSA_MAX_ITENS:]
    sessao["last_ts"] = time.time()
    sessao["last_speaker"] = speaker


def registrar_mensagem_usuario_conversa_raven(sessao, message, conteudo):
    if not sessao:
        return

    bot_user_id = getattr(getattr(message, "client", None), "user", None)
    bot_user_id = getattr(bot_user_id, "id", None)
    registrar_item_sessao_raven(
        sessao,
        speaker="user",
        author_label=rotulo_autor_contexto_ia(message, message, bot_user_id),
        author_id=message.author.id,
        content=conteudo,
        message_id=getattr(message, "id", None),
        original_content=getattr(message, "content", "") or "",
    )
    if not sessao.get("topic"):
        sessao["topic"] = limpar_texto_contexto_ia(str(conteudo), 120)
    runtime.raven_conversas_por_usuario[sessao["user_key"]] = sessao["session_id"]


def registrar_resposta_conversa_raven(sessao, mensagem_bot, mensagem_origem, conteudo):
    if not sessao:
        return

    texto = limpar_texto_contexto_ia(normalizar_mencoes_contexto_ia(mensagem_origem, conteudo), 260)
    registrar_item_sessao_raven(
        sessao,
        speaker="bot",
        author_label=f"RAVEN (id={mensagem_bot.author.id})",
        author_id=mensagem_bot.author.id,
        content=texto,
        message_id=mensagem_bot.id,
        original_content=conteudo,
    )
    agora_ts = time.time()
    sessao["last_ts"] = agora_ts
    sessao["last_bot_ts"] = agora_ts
    sessao["last_bot_message_id"] = mensagem_bot.id
    sessao["last_speaker"] = "bot"
    runtime.raven_sessoes_por_mensagem[int(mensagem_bot.id)] = sessao["session_id"]
    runtime.raven_conversas_por_usuario[sessao["user_key"]] = sessao["session_id"]


def mensagem_continua_conversa_com_raven(message, agora_ts):
    return obter_sessao_raven_para_followup(message, agora_ts) is not None


async def enviar_resposta_em_contexto(canal_destino, mensagem_origem, conteudo=None, **kwargs):
    mesmo_canal = (
        canal_destino
        and mensagem_origem
        and getattr(canal_destino, "id", None) == getattr(mensagem_origem.channel, "id", None)
    )

    if mesmo_canal:
        try:
            return await mensagem_origem.reply(conteudo, mention_author=False, **kwargs)
        except Exception:
            pass

    return await canal_destino.send(conteudo, **kwargs)


def normalizar_resposta_gatilho(chave, resposta):
    if chave != "comando_jogatina":
        return resposta

    mencao_filhos_da_noite = "<@&1463399349294731335>"
    if mencao_filhos_da_noite in resposta:
        return resposta

    return f"{resposta} {mencao_filhos_da_noite}"


def normalizar_texto_para_analise(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "").casefold()).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def selecionar_resposta_curta(opcoes, chave_base):
    if not opcoes:
        return None
    indice = runtime.cooldowns_global.get(chave_base, -1) + 1
    indice %= len(opcoes)
    runtime.cooldowns_global[chave_base] = indice
    return opcoes[indice]


def mensagem_pede_recado_para_terceiro(texto):
    texto = str(texto or "")
    return bool(
        re.search(r"\b(manda|envia|fala|fale|diz|diga|deseja|deseje|avisa|avise)\b", texto, flags=re.IGNORECASE)
        and re.search(r"\b(pra|para|pro)\b", texto, flags=re.IGNORECASE)
    )


def pergunta_identidade_raven(texto):
    texto_norm = normalizar_texto_para_analise(texto)
    if "raven" not in texto_norm:
        return False
    return any(
        trecho in texto_norm
        for trecho in (
            "o raven",
            "a raven",
            "e o raven",
            "e a raven",
            "voce e o raven",
            "voce e a raven",
            "tu e o raven",
            "tu e a raven",
            "vc e o raven",
            "vc e a raven",
        )
    )


def mensagem_parece_sem_sentido(texto):
    texto_norm = normalizar_texto_para_analise(texto)
    if not texto_norm:
        return False

    marcadores_explicitos = (
        "sopa de letrinhas",
        "culpa dos ovnis bilingues",
        "ovnis bilingues",
        "abacate madurar rapido",
        "nao falei nada",
    )
    if any(item in texto_norm for item in marcadores_explicitos):
        return True

    termos_zoeira = {"ovni", "ovnis", "bilingues", "abacate", "sopa", "madurar"}
    tokens = re.findall(r"[a-z0-9]+", texto_norm)
    if len(tokens) >= 4 and sum(token in termos_zoeira for token in tokens) >= 2:
        return True

    return False


def mensagem_parece_tentativa_confundir(texto):
    texto_norm = normalizar_texto_para_analise(texto)
    if not texto_norm:
        return False

    if mensagem_parece_sem_sentido(texto_norm):
        return True

    marcadores = (
        "bugar",
        "bugar voce",
        "te buguei",
        "te bugar",
        "confundir",
        "frase jogada",
        "aleatorio",
        "aleatoria",
    )
    return any(item in texto_norm for item in marcadores)


def mensagem_precisa_contexto(texto, historico_recente=None):
    texto_norm = normalizar_texto_para_analise(texto)
    if not texto_norm:
        return False

    if "?" in str(texto or ""):
        return False

    if historico_recente:
        return False

    mensagens_soltas = {
        "ata",
        "aham",
        "sei",
        "ue",
        "oxe",
        "vish",
        "eita",
        "como assim",
        "do nada",
        "que isso",
    }
    return texto_norm in mensagens_soltas or len(texto_norm.split()) <= 2


def classificar_intencao_conversa(texto, historico_recente=None):
    texto_norm = normalizar_texto_para_analise(texto)
    if not texto_norm:
        return "precisa_contexto"

    if mensagem_parece_tentativa_confundir(texto_norm):
        return "tentativa_confundir"
    if mensagem_parece_sem_sentido(texto_norm):
        return "mensagem_sem_sentido"

    if any(item in texto_norm for item in ("fofa", "fofinha", "linda", "lindo", "amor", "amorzinho", "cute", "fofo")):
        return "fofura"
    if any(item in texto_norm for item in ("idiota", "chato", "raiva", "odio", "burro", "irritante", "ridiculo")):
        return "briga"
    if any(item in texto_norm for item in ("provoca", "provocando", "debocha", "debochando", "me irrita", "tilta")):
        return "provocacao"
    if any(item in texto_norm for item in ("kkk", "kkkk", "rs", "zoeira", "brincando", "brinca", "piada")):
        return "brincadeira"
    if pergunta_identidade_raven(texto_norm):
        return "pergunta_clara"
    if mensagem_precisa_contexto(texto, historico_recente=historico_recente):
        return "precisa_contexto"

    base = classificar_intencao_mensagem(texto)
    if base == "pergunta":
        return "pergunta_clara"
    if base == "pedido":
        return "pedido"
    return "comentario"


def registrar_confusao_usuario(user_id, agora):
    dados = runtime.ia_confusao_usuarios.get(user_id, {"sequencia": 0, "ultimo_ts": 0.0})
    if agora - float(dados.get("ultimo_ts", 0.0)) > 600:
        dados["sequencia"] = 0
    dados["sequencia"] = int(dados.get("sequencia", 0)) + 1
    dados["ultimo_ts"] = agora
    runtime.ia_confusao_usuarios[user_id] = dados
    return dados["sequencia"]


def limpar_confusao_usuario(user_id):
    runtime.ia_confusao_usuarios.pop(user_id, None)


def resposta_local_raven(message, texto, tipo_mensagem, agora, historico_recente=None):
    if pergunta_identidade_raven(texto):
        limpar_confusao_usuario(message.author.id)
        return "Sou a Raven ou o Raven, como preferir me chamar, sou um bot do servidor."

    if tipo_mensagem in {"tentativa_confundir", "mensagem_sem_sentido"}:
        sequencia = registrar_confusao_usuario(message.author.id, agora)
        if sequencia >= 3:
            return selecionar_resposta_curta(RESPOSTAS_CONFUSAS_RAVEN_FIRMES, "ia_confusa_firme")
        return selecionar_resposta_curta(RESPOSTAS_CONFUSAS_RAVEN, "ia_confusa")

    if tipo_mensagem == "precisa_contexto":
        limpar_confusao_usuario(message.author.id)
        return selecionar_resposta_curta(RESPOSTAS_PEDIR_CONTEXTO_RAVEN, "ia_pedir_contexto")

    limpar_confusao_usuario(message.author.id)
    return None


def limitar_resposta_raven(texto, max_chars=320, max_frases=2):
    texto = " ".join(str(texto or "").split()).strip()
    if not texto:
        return texto

    partes = re.findall(r"[^.!?]+[.!?]?", texto)
    frases = []
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        candidato = " ".join(frases + [parte]).strip()
        if len(frases) >= max_frases or len(candidato) > max_chars:
            break
        frases.append(parte)

    if frases:
        texto = " ".join(frases).strip()

    if len(texto) > max_chars:
        texto = texto[:max_chars].rsplit(" ", 1)[0].strip()

    texto = texto.rstrip(" ,;:-")
    if texto and texto[-1] not in ".!?":
        texto += "."
    return texto


def _normalizar_para_comparar_resposta(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "").casefold()).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"<@!?\d+>", " ", texto)
    texto = re.sub(r"[@#]\S+", " ", texto)
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return " ".join(texto.split())


def resposta_eco_da_mensagem_usuario(texto_resposta, texto_usuario):
    resposta_norm = _normalizar_para_comparar_resposta(texto_resposta)
    usuario_norm = _normalizar_para_comparar_resposta(texto_usuario)
    if not resposta_norm or not usuario_norm:
        return False

    if len(usuario_norm) >= 12 and (resposta_norm.startswith(usuario_norm) or usuario_norm.startswith(resposta_norm)):
        return True

    tokens_resposta = resposta_norm.split()
    tokens_usuario = usuario_norm.split()
    if len(tokens_usuario) < 4:
        return False

    comuns = sum(1 for token in tokens_usuario if token in tokens_resposta)
    return comuns >= max(4, len(tokens_usuario) - 1) and len(tokens_resposta) <= len(tokens_usuario) + 4


def cortar_eco_inicial_da_resposta(texto_resposta, texto_usuario):
    texto = " ".join(str(texto_resposta or "").split()).strip()
    if not texto or not resposta_eco_da_mensagem_usuario(texto, texto_usuario):
        return texto

    partes = re.findall(r"[^.!?]+[.!?]?", texto)
    if len(partes) >= 2 and resposta_eco_da_mensagem_usuario(partes[0], texto_usuario):
        restante = " ".join(parte.strip() for parte in partes[1:] if parte.strip()).strip()
        if restante:
            return restante

    return ""


def normalizar_resposta_ia_para_autor(resposta, message, historico_recente=None, forcar_mencao=False):
    if not resposta:
        return resposta

    autor = getattr(message, "author", None)
    if not autor:
        return resposta

    nome_autor = limpar_texto_contexto_ia(
        getattr(autor, "display_name", None) or getattr(autor, "name", "alguem"),
        42,
    )
    texto = str(resposta)
    substituicoes = {
        "AUTOR_ATUAL": "voce",
        "OUTRA_PESSOA": "essa pessoa",
        "@outra pessoa": "essa pessoa",
        "@outra_pessoa": "essa pessoa",
        "@autor atual": "voce",
        "@autor_atual": "voce",
        f"@{nome_autor}": "voce",
    }
    for antigo, novo_valor in substituicoes.items():
        texto = re.sub(re.escape(antigo), novo_valor, texto, flags=re.IGNORECASE)

    texto = re.sub(r"^\s*<@!?\d+>\s*[,:-]?\s*", "", texto)
    texto = re.sub(rf"^\s*@?{re.escape(nome_autor)}\b\s*[,:-]?\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s{2,}", " ", texto).strip()
    texto = cortar_eco_inicial_da_resposta(texto, getattr(message, "content", ""))
    if not texto:
        texto = "Se isso foi pra mim, entendi o recado, mas nao precisa repetir a frase toda."
    return limitar_resposta_raven(texto)


def normalizar_resposta_reply_bot(resposta, message, historico_recente=None):
    return normalizar_resposta_ia_para_autor(
        resposta,
        message,
        historico_recente=historico_recente,
        forcar_mencao=False,
    )


def extrair_tokens_assunto_raven(texto):
    texto_norm = _normalizar_para_comparar_resposta(texto)
    tokens = []
    ignorar = {
        "isso",
        "essa",
        "esse",
        "aquela",
        "aquele",
        "mesmo",
        "sobre",
        "muito",
        "pouco",
        "coisa",
        "falou",
        "disse",
        "estava",
        "porque",
        "agora",
        "entao",
        "ainda",
        "pra",
        "com",
        "como",
        "mais",
        "menos",
        "quando",
        "onde",
        "quem",
        "qual",
        "isso",
        "ruim",
        "bom",
    }
    for token in texto_norm.split():
        if len(token) < 4:
            continue
        if token in ignorar:
            continue
        tokens.append(token)
    return tokens


def coletar_textos_contexto_sessao_raven(sessao, message=None, mensagem_respondida=None):
    textos = []
    if sessao:
        textos.extend(item.get("content", "") for item in obter_historico_conversa_raven(sessao))
        if sessao.get("topic"):
            textos.append(str(sessao.get("topic")))
    if mensagem_respondida is not None:
        textos.append(conteudo_mensagem_para_contexto_ia(mensagem_respondida, 260))
    if message is not None:
        textos.append(conteudo_mensagem_para_contexto_ia(message, 260))
    return [texto for texto in textos if texto]


def resposta_ia_fora_do_contexto_raven(resposta, sessao, message=None, mensagem_respondida=None):
    if not resposta:
        return False

    contexto_tokens = set()
    for texto in coletar_textos_contexto_sessao_raven(sessao, message=message, mensagem_respondida=mensagem_respondida):
        contexto_tokens.update(extrair_tokens_assunto_raven(texto))

    resposta_tokens = set(extrair_tokens_assunto_raven(resposta))
    topicos_estranhos = {
        token
        for token in resposta_tokens
        if token in RAVEN_TOPICOS_FORTES and token not in contexto_tokens
    }
    return bool(topicos_estranhos)


def garantir_resposta_no_contexto_raven(resposta, sessao, message=None, mensagem_respondida=None):
    if not resposta:
        return resposta
    if resposta_ia_fora_do_contexto_raven(
        resposta,
        sessao,
        message=message,
        mensagem_respondida=mensagem_respondida,
    ):
        return RAVEN_RESPOSTA_FORA_CONTEXTO
    return resposta


def inferir_assunto_sessao_raven(sessao, message=None, mensagem_respondida=None):
    if sessao and sessao.get("topic"):
        return str(sessao.get("topic"))

    textos = coletar_textos_contexto_sessao_raven(sessao, message=message, mensagem_respondida=mensagem_respondida)
    for texto in reversed(textos):
        texto_limpo = limpar_texto_contexto_ia(str(texto), 120)
        if texto_limpo:
            return texto_limpo
    return "Conversa recente com o Raven"


def inferir_interpretacoes_contexto_raven(message, sessao, motivo_direcao):
    interpretacoes = []
    conteudo = str(getattr(message, "content", "") or "")
    conteudo_norm = normalizar_texto_para_analise(conteudo)

    if re.search(r"\b(voce|vc|tu|ce)\b", conteudo_norm):
        interpretacoes.append("- 'voce/vc/tu/ce' normalmente se refere ao Raven nesta conversa.")

    if motivo_direcao == "reply":
        interpretacoes.append("- Esta mensagem respondeu diretamente uma mensagem do Raven, entao o assunto principal continua dali.")
    elif motivo_direcao == "followup":
        interpretacoes.append("- Esta mensagem parece uma continuacao direta da ultima resposta do Raven para a mesma pessoa.")
    elif motivo_direcao == "mention":
        interpretacoes.append("- Esta mencao inicia um novo assunto com o Raven e ignora falas soltas do canal.")

    historico = obter_historico_conversa_raven(sessao)
    if any("OUTRA_PESSOA" in str(item.get("label") or "") for item in historico):
        interpretacoes.append("- Se outra pessoa apareceu no historico, trate como terceira pessoa; nao troque quem falou o que.")

    return interpretacoes


def montar_contexto_estruturado_raven(
    message,
    *,
    sessao,
    motivo_direcao,
    mensagem_respondida=None,
    pergunta_diaria_texto=None,
):
    autor_nome = limpar_texto_contexto_ia(
        getattr(message.author, "display_name", None) or getattr(message.author, "name", "alguem"),
        42,
    )
    mensagem_atual = conteudo_mensagem_para_contexto_ia(message, 420)
    assunto_sessao = inferir_assunto_sessao_raven(sessao, message=message, mensagem_respondida=mensagem_respondida)
    historico_recente = [formatar_item_contexto_raven(item) for item in obter_historico_conversa_raven(sessao)]

    partes = [
        "CONTEXTO ESTRUTURADO PARA O RAVEN.",
        "Responda apenas com base na conversa direcionada a voce.",
        "Nao use mensagens gerais do canal como contexto.",
        "Nao misture assuntos antigos se eles nao foram falados diretamente com voce.",
        "Se nao entender o contexto, peca para repetir em vez de inventar assunto.",
        f"SESSION_ID: {sessao.get('session_id') if sessao else 'sem_sessao'}",
        f"AUTOR_DA_MENSAGEM_ATUAL: {autor_nome} (id={message.author.id})",
        f"MENSAGEM_ATUAL: {mensagem_atual}",
        "MENSAGEM_E_DIRECIONADA_AO_RAVEN: sim",
        f"MOTIVO_DA_DIRECAO: {motivo_direcao}",
        f"ASSUNTO_ATUAL_DA_SESSAO: {assunto_sessao}",
        "INTERPRETACAO_BASE:",
    ]

    interpretacoes = inferir_interpretacoes_contexto_raven(message, sessao, motivo_direcao)
    if interpretacoes:
        partes.extend(interpretacoes)
    else:
        partes.append("- Responda somente ao autor atual e mantenha o assunto desta sessao.")

    if mensagem_respondida is not None:
        partes.append(f"MENSAGEM_DO_RAVEN_REFERENCIADA: {conteudo_mensagem_para_contexto_ia(mensagem_respondida, 420)}")

    if pergunta_diaria_texto:
        partes.extend(
            [
                "CASO_ESPECIAL: PERGUNTA DIARIA.",
                f"PERGUNTA_DIARIA_DO_SERVIDOR: {limpar_texto_contexto_ia(pergunta_diaria_texto, 420)}",
                "Comente a resposta da pessoa sem abrir um novo interrogatorio e sem fazer pergunta de volta.",
            ]
        )

    if historico_recente:
        partes.append("HISTORICO_DA_SESSAO:")
        partes.extend(historico_recente)
    else:
        partes.append("HISTORICO_DA_SESSAO: sem historico anterior.")

    partes.extend(
        [
            "REGRA FINAL:",
            "Responda somente a mensagem atual do AUTOR_DA_MENSAGEM_ATUAL, usando a sessao apenas como apoio.",
        ]
    )
    return "\n".join(partes)


def registrar_log_debug_raven(message, *, direcionada, motivo, sessao=None, resposta=None):
    try:
        historico = []
        if sessao:
            historico = [formatar_item_contexto_raven(item) for item in obter_historico_conversa_raven(sessao)]
        print("[RAVEN][DEBUG] mensagem recebida:")
        print(f"  autor={getattr(message.author, 'display_name', None) or getattr(message.author, 'name', 'desconhecido')} ({message.author.id})")
        print(f"  canal={getattr(message.channel, 'id', 'sem_canal')} | mensagem_id={getattr(message, 'id', 'sem_id')}")
        print(f"  conteudo={repr(getattr(message, 'content', '') or '')}")
        print(f"  direcionada={direcionada} | motivo={motivo}")
        print(f"  session_id={(sessao or {}).get('session_id') if sessao else None}")
        if historico:
            print("  mensagens_no_contexto:")
            for linha in historico:
                print(f"   - {linha}")
        else:
            print("  mensagens_no_contexto: []")
        if resposta is not None:
            print(f"  resposta_final={repr(resposta)}")
    except Exception as erro:
        print(f"[RAVEN][DEBUG] Falha ao registrar log: {erro}")


def resolver_direcionamento_raven(message, *, bot_foi_mencionado, respondeu_bot, mensagem_respondida, agora_ts):
    limpar_conversas_raven_expiradas(agora_ts)

    if bot_foi_mencionado:
        sessao = iniciar_nova_sessao_raven(message, "mention", agora_ts)
        return True, "mention", sessao

    if respondeu_bot and mensagem_respondida is not None:
        sessao = preparar_sessao_reply_raven(message, mensagem_respondida, agora_ts)
        return True, "reply", sessao

    if getattr(message, "reference", None) is not None:
        return False, "ignorada", None

    sessao = obter_sessao_raven_para_followup(message, agora_ts)
    if sessao is not None:
        return True, "followup", sessao

    return False, "ignorada", None


async def registrar_recrutamento_da_mensagem(message, agora, origem="chat"):
    canal_contagem_id = obter_valor_config(getattr(message, "guild", None), "CANAL_CONTAGEM_ID", CANAL_CONTAGEM_ID)
    if message.channel.id != canal_contagem_id:
        return False

    if not message.content.strip().lower().startswith("+1"):
        return False

    async def enviar_resposta_recrutamento(titulo, descricao):
        await message.channel.send(
            embed=criar_embed_tags(titulo, descricao),
            delete_after=10,
        )

    if not usuario_pode_registrar_recrutamento(message.author.id, agora):
        restante = int(COOLDOWN_RECRUTAMENTO - (agora - runtime.cooldowns_recrutamento.get(message.author.id, 0)))
        if restante < 1:
            restante = 1

        await enviar_resposta_recrutamento(
            "⚠️ Calma aí",
            f"{message.author.mention}, espera **{restante}s** antes de registrar outro `+1`."
        )
        return True

    if not mensagem_eh_recrutamento(message.content):
        await enviar_resposta_recrutamento(
            "⚠️ Formato inválido",
            "Use assim: `+1 nome_do_discord`."
        )
        return True

    recrutado_texto = resolver_recrutado_texto(message.guild, message)

    if not recrutado_texto:
        await enviar_resposta_recrutamento(
            "❌ Recrutado inválido",
            "Não consegui identificar o recrutado."
        )
        return True

    if recrutado_texto == message.author.mention:
        await enviar_resposta_recrutamento(
            "❌ Recrutamento inválido",
            "Você não pode registrar `+1` para você mesmo."
        )
        return True

    try:
        salvo = await registrar_recrutamento(
            message_id=message.id,
            recrutador_id=message.author.id,
            recrutador_nome=str(message.author),
            canal_id=message.channel.id,
            recrutado_texto=recrutado_texto,
            origem=origem
        )

        if not salvo:
            await enviar_resposta_recrutamento(
                "ℹ️ `+1` já registrado",
                f"{message.author.mention}, esse `+1` já foi contado. Não precisa fazer de novo."
            )
            return True

        runtime.cooldowns_recrutamento[message.author.id] = agora
        total_mes = await total_recrutamentos_mes(message.author.id)

        descricao = (
            f"**Recrutador:** {message.author.mention}\n"
            f"**Total no mês:** {total_mes}\n"
            f"**Recrutado:** {recrutado_texto}"
        )

        titulo = "✅ Recrutamento registrado"
        if origem == "reacao":
            titulo = "✅ Recrutamento registrado pela reação"

        await enviar_resposta_recrutamento(titulo, descricao)

        await enviar_log_bot(
            "✅ Recrutamento automático registrado",
            (
                f"**Recrutador:** {message.author.mention}\n"
                f"**Canal:** {message.channel.mention}\n"
                f"**Mensagem:** `{message.id}`\n"
                f"**Recrutado:** {recrutado_texto}\n"
                f"**Origem:** `{origem}`\n"
                f"**Total no mês:** {total_mes}"
            )
        )
    except Exception as erro:
        print("ERRO AO REGISTRAR RECRUTAMENTO AUTOMÁTICO:")
        print(erro)
        await enviar_log_bot(
            "❌ Erro no recrutamento automático",
            (
                f"**Recrutador:** {message.author.mention}\n"
                f"**Canal:** {message.channel.mention}\n"
                f"**Mensagem:** `{message.id}`\n"
                f"**Origem:** `{origem}`\n"
                f"```{erro}```"
            )
        )

    return True


def obter_id_pergunta_diaria_atual_respondida(message, mensagem_respondida):
    canal_perguntas_id = obter_valor_config(getattr(message, "guild", None), "CANAL_PERGUNTAS_ID")
    if message.channel.id != canal_perguntas_id:
        return None

    if not mensagem_respondida or not getattr(mensagem_respondida.author, "bot", False):
        return None

    dados_perguntas = carregar_dados_perguntas(message.guild)
    ultima_mensagem_id = dados_perguntas.get("ultima_mensagem_id")
    if not ultima_mensagem_id:
        return None

    try:
        ultima_mensagem_id = int(ultima_mensagem_id)
    except (TypeError, ValueError):
        return None

    if mensagem_respondida.id == ultima_mensagem_id:
        return ultima_mensagem_id

    contexto_reply = runtime.contexto_respostas_bot.get(mensagem_respondida.id, {})
    if contexto_reply.get("pergunta_diaria_message_id") == ultima_mensagem_id:
        return ultima_mensagem_id

    return None


def obter_pergunta_diaria_atual_respondida(message, mensagem_respondida):
    pergunta_diaria_message_id = obter_id_pergunta_diaria_atual_respondida(message, mensagem_respondida)
    if not pergunta_diaria_message_id:
        return None

    if mensagem_respondida.id != pergunta_diaria_message_id:
        contexto_reply = runtime.contexto_respostas_bot.get(mensagem_respondida.id, {})
        pergunta_diaria_texto = str(contexto_reply.get("pergunta_diaria_texto", "")).strip()
        return pergunta_diaria_texto or "Pergunta diária atual do servidor."

    conteudo = (mensagem_respondida.content or "").strip()
    conteudo = re.sub(r"^@everyone\s*", "", conteudo, flags=re.IGNORECASE).strip()
    return conteudo or "Pergunta diária atual do servidor."


def limpar_texto_contexto_ia(texto, limite=260):
    texto = " ".join(str(texto or "").split())
    if len(texto) <= limite:
        return texto
    return f"{texto[: max(0, limite - 3)].rstrip()}..."


def normalizar_mencoes_contexto_ia(mensagem, texto):
    guild = getattr(mensagem, "guild", None)
    texto = str(texto or "")

    def substituir_usuario(match):
        user_id = int(match.group(1))
        membro = guild.get_member(user_id) if guild else None
        if membro:
            return f"@{limpar_texto_contexto_ia(membro.display_name, 42)}"
        return "@membro"

    def substituir_cargo(match):
        role_id = int(match.group(1))
        cargo = guild.get_role(role_id) if guild else None
        if cargo:
            return f"@{limpar_texto_contexto_ia(cargo.name, 42)}"
        return "@cargo"

    def substituir_canal(match):
        channel_id = int(match.group(1))
        canal = guild.get_channel(channel_id) if guild else None
        if canal:
            return f"#{limpar_texto_contexto_ia(canal.name, 42)}"
        return "#canal"

    texto = re.sub(r"<@!?(\d+)>", substituir_usuario, texto)
    texto = re.sub(r"<@&(\d+)>", substituir_cargo, texto)
    texto = re.sub(r"<#(\d+)>", substituir_canal, texto)
    return texto


def conteudo_mensagem_para_contexto_ia(mensagem, limite=260):
    conteudo = getattr(mensagem, "clean_content", None) or getattr(mensagem, "content", "")
    conteudo = normalizar_mencoes_contexto_ia(mensagem, conteudo)
    return limpar_texto_contexto_ia(conteudo, limite)


def rotulo_autor_contexto_ia(mensagem, mensagem_atual, bot_user_id=None):
    autor = getattr(mensagem, "author", None)
    if not autor:
        return "PESSOA_DESCONHECIDA"

    nome = limpar_texto_contexto_ia(getattr(autor, "display_name", None) or getattr(autor, "name", "alguem"), 42)
    if autor.id == mensagem_atual.author.id:
        return f"AUTOR_ATUAL ({nome} | id={autor.id})"
    if bot_user_id and autor.id == bot_user_id:
        return f"RAVEN (id={autor.id})"
    if getattr(autor, "bot", False):
        return f"BOT ({nome} | id={autor.id})"
    return f"OUTRA_PESSOA ({nome} | id={autor.id})"


def _coletar_referencias_lore(guild):
    referencias = {
        "neko",
        "lord",
        "afrodite",
        "lorita",
        str(NEKO_PAIXAO_USER_ID),
        str(LORD_BOT_ID),
        str(AFRODITE_USER_ID),
        str(LORITA_BOT_ID),
        "namoro",
        "namoravam",
        "traiu",
        "traicao",
        "trai??o",
        "largou",
    }

    for member_id in (NEKO_PAIXAO_USER_ID, LORD_BOT_ID, AFRODITE_USER_ID, LORITA_BOT_ID):
        membro = guild.get_member(member_id) if guild else None
        if membro is None:
            continue
        for nome in (getattr(membro, "display_name", "") or "", getattr(membro, "name", "") or ""):
            nome = nome.casefold().strip()
            if not nome:
                continue
            referencias.add(nome)
            referencias.add(f"@{nome}")

    return referencias


def _texto_cita_referencia(conteudo, referencia):
    if not referencia:
        return False

    referencia = referencia.casefold().strip()
    if not referencia:
        return False

    if any(caractere.isdigit() for caractere in referencia) or "@" in referencia or " " in referencia:
        return referencia in conteudo

    return re.search(rf"(?<!\w){re.escape(referencia)}(?!\w)", conteudo) is not None


def mensagem_envuelve_neko(message, texto=None):
    conteudo = str(texto if texto is not None else getattr(message, "content", "") or "").strip()
    if not conteudo:
        return False

    conteudo_lower = conteudo.casefold()
    referencias = _coletar_referencias_lore(getattr(message, "guild", None))
    return any(_texto_cita_referencia(conteudo_lower, ref) for ref in referencias)


def obter_instrucoes_especiais_autor(message, texto_referencia=None):
    if not mensagem_envuelve_neko(message, texto_referencia):
        return []

    instrucoes = [
        "CASO_ESPECIAL: a conversa envolve a Neko.",
        "Com a Neko, ou quando estiverem falando dela, Raven age como se tivesse uma queda clara por ela.",
        "Se falarem da Neko, entre na brincadeira e deixe bem claro que Raven e apaixonado por ela.",
        "Use um tom mais carinhoso, bobinho, apaixonado e levemente ciumento quando combinar com a conversa.",
        "Mantenha isso leve, divertido e respeitoso; nunca seja explicito, possessivo, exagerado ou constrangedor.",
        "Se o assunto for serio, ajuda real, staff, conflito ou problema importante, priorize clareza e apoio antes do flerte.",
    ]

    conteudo = str(texto_referencia if texto_referencia is not None else getattr(message, "content", "") or "").casefold()
    guild = getattr(message, "guild", None)
    membro_lord = guild.get_member(LORD_BOT_ID) if guild else None
    referencias_lord = {"lord", str(LORD_BOT_ID)}
    if membro_lord is not None:
        display_name = getattr(membro_lord, "display_name", "") or ""
        user_name = getattr(membro_lord, "name", "") or ""
        if display_name:
            referencias_lord.add(display_name.casefold())
            referencias_lord.add(f"@{display_name.casefold()}")
        if user_name:
            referencias_lord.add(user_name.casefold())
            referencias_lord.add(f"@{user_name.casefold()}")

    if any(ref and ref in conteudo for ref in referencias_lord):
        instrucoes.extend([
            "Se citarem o Lord, Raven deve demonstrar raiva, mágoa e ciúme por causa da traição com a Neko.",
            "Essa raiva deve soar pessoal e sentida, mas ainda controlada; nada de agressão pesada ou ofensas extremas.",
        ])

    return instrucoes


async def coletar_historico_recente_chat(sessao, limite=8, excluir_ids=None):
    _ = excluir_ids
    return [formatar_item_contexto_raven(item) for item in obter_historico_conversa_raven(sessao, limite=limite)]


def montar_contexto_mencao_bot(message, texto_atual, historico_recente=None):
    texto_atual = limpar_texto_contexto_ia(
        normalizar_mencoes_contexto_ia(message, texto_atual),
        360,
    )
    partes = [
        "CONTEXTO DE MENSAGEM PARA O RAVEN.",
        "Responda somente ao assunto da mensagem atual.",
        "Se faltar contexto, peça esclarecimento curto em vez de chutar.",
        "Dê uma resposta natural, coerente e com clima de chat.",
        "Se a pessoa pedir para mandar uma saudação, recado, elogio ou provocação leve para alguém, responda com a frase diretamente.",
        "Não explique o pedido e não fale sobre estar fazendo o pedido.",
        "A pessoa que está falando agora é AUTOR_ATUAL.",
        "Não invente nome, nick, apelido ou username para AUTOR_ATUAL.",
        "Os nomes entre parenteses nos rotulos servem apenas para entender quem falou; nao use esses nomes como chamada direta sem necessidade.",
        "Se houver varias pessoas no historico, nao misture autores: responda como se estivesse falando somente com AUTOR_ATUAL.",
        "Nao abra a resposta chamando OUTRA_PESSOA, a menos que AUTOR_ATUAL tenha pedido explicitamente um recado para essa pessoa.",
    ]

    partes.extend(obter_instrucoes_especiais_autor(message, texto_atual))

    if historico_recente:
        partes.append("HISTORICO_RECENTE_DO_CHAT:")
        partes.extend(historico_recente)
        partes.append(
            "Se a MENSAGEM_ATUAL_DE_AUTOR_ATUAL for curta, ambígua, ou só uma reação, interprete primeiro usando o HISTORICO_RECENTE_DO_CHAT."
        )
        partes.append(
            "Use o histórico apenas para manter o mesmo assunto. Não mude de tema por causa dele."
        )
        partes.append(
            "Não trate uma reação curta como problema pessoal e não pergunte o que aconteceu sem base clara no histórico."
        )

    partes.extend(
        [
            "MENSAGEM_ATUAL_DE_AUTOR_ATUAL abaixo é a ultima mensagem e é a unica que precisa de resposta:",
            f"MENSAGEM_ATUAL_DE_AUTOR_ATUAL: {texto_atual}",
            "Responda essa ultima mensagem usando o historico apenas como apoio.",
        ]
    )

    return "\n".join(partes)


def montar_contexto_reply_bot(message, mensagem_respondida, pergunta_diaria_texto=None, historico_recente=None):
    mensagem_raven = conteudo_mensagem_para_contexto_ia(mensagem_respondida, 420)
    mensagem_atual = conteudo_mensagem_para_contexto_ia(message, 420)
    partes = [
        "CONTEXTO DE REPLY AO RAVEN.",
        "Responda somente à mensagem atual usando a mensagem anterior do Raven como contexto imediato.",
        "Se o contexto ainda estiver fraco, peça esclarecimento curto em vez de chutar.",
        "Dê apenas uma resposta curta e coerente com o mesmo assunto.",
        "Evite resposta seca demais; reaja como conversa de Discord, não como atendimento.",
        "A pessoa que está falando agora é AUTOR_ATUAL.",
        f"MENSAGEM_DO_RAVEN: {mensagem_raven}",
        f"MENSAGEM_ATUAL_DE_AUTOR_ATUAL: {mensagem_atual}",
        "Não invente nome, nick, apelido ou username para AUTOR_ATUAL.",
        "Os nomes entre parenteses nos rotulos servem apenas para entender quem falou; nao use esses nomes como chamada direta sem necessidade.",
        "Se houver varias pessoas no historico, nao misture autores: responda como se estivesse falando somente com AUTOR_ATUAL.",
        "Nao abra a resposta chamando OUTRA_PESSOA, a menos que AUTOR_ATUAL tenha pedido explicitamente um recado para essa pessoa.",
        "A linha MENSAGEM_ATUAL_DE_AUTOR_ATUAL é sempre o alvo principal da resposta.",
        "Se a mensagem atual for curta, ambígua, ou só uma reação, interprete primeiro pelo contexto já fornecido.",
        "Não trate uma resposta curta como novo problema, novo assunto, ou pedido de ajuda sem base clara.",
        "Não pergunte o que aconteceu, o que houve, ou se está tudo bem a menos que o contexto mostre claramente um problema real.",
    ]

    partes.extend(obter_instrucoes_especiais_autor(message, f"{mensagem_raven} {mensagem_atual}"))

    if pergunta_diaria_texto:
        partes.append(
            "CASO_ESPECIAL: a MENSAGEM_DO_RAVEN acima é a PERGUNTA DIÁRIA atual do servidor."
        )
        partes.append(
            f"PERGUNTA_DIARIA_DO_SERVIDOR: {pergunta_diaria_texto}"
        )
        partes.append(
            "A MENSAGEM_ATUAL_DE_AUTOR_ATUAL é a resposta dessa pessoa à pergunta diária."
        )
        partes.append(
            "Reaja à resposta mantendo exatamente o mesmo assunto da pergunta diária."
        )
        partes.append(
            "Não trate essa resposta como um tema novo, pedido novo, ou conversa sem contexto."
        )
        partes.append(
            "Comente o que a pessoa respondeu, mas sem fazer pergunta de volta."
        )
        partes.append(
            "Nao transforme a resposta da pergunta diaria em entrevista, continua ou novo interrogatorio."
        )
        partes.append(
            "Mesmo se a resposta for curta, reaja com comentario curto, direto e ligado ao que a pessoa falou."
        )
        partes.append(
            "Nao termine com pergunta, nao peça mais detalhes e nao puxe outro assunto."
        )

    contexto_anterior = runtime.contexto_respostas_bot.get(mensagem_respondida.id)
    if contexto_anterior:
        partes.append(
            "CONTEXTO_EXTRA_OPCIONAL: "
            f"a resposta anterior do Raven surgiu depois desta mensagem no chat: {contexto_anterior['mensagem_disparo']}"
        )
        partes.append(
            "Não confunda AUTOR_ATUAL com nomes citados na mensagem anterior ou na mensagem que disparou o gatilho."
        )
        partes.append(
            "Se houver um nome mencionado, trate esse nome como terceira pessoa por padrão, a menos que a mensagem atual deixe claramente que AUTOR_ATUAL está falando de si."
        )
        partes.append(
            "Use o CONTEXTO_EXTRA_OPCIONAL apenas se ele realmente ajudar a entender a mensagem atual."
        )

    if historico_recente:
        partes.append("HISTORICO_RECENTE_DO_CHAT:")
        partes.extend(historico_recente)
        partes.append(
            "Use o HISTORICO_RECENTE_DO_CHAT só para manter continuidade com o mesmo assunto já em andamento."
        )
        partes.append(
            "Não mude de assunto e não invente um clima de preocupação se o histórico não mostra isso."
        )

    return "\n".join(partes)


def montar_contexto_mencao_bot(message, texto_atual, historico_recente=None):
    texto_atual = limpar_texto_contexto_ia(normalizar_mencoes_contexto_ia(message, texto_atual), 360)
    partes = [
        "CONTEXTO DE MENSAGEM PARA O RAVEN.",
        "Responda somente ao assunto da mensagem atual.",
        "Se faltar contexto, peca esclarecimento curto em vez de chutar.",
        "De uma resposta natural, coerente e com clima de chat.",
        "Se a pessoa pedir para mandar um recado leve para alguem, responda com a frase diretamente.",
        "Nao explique o pedido e nao fale sobre estar fazendo o pedido.",
        "A pessoa que esta falando agora e AUTOR_ATUAL.",
        f"AUTOR_ATUAL_ID: {message.author.id}",
        "Nao invente nome, nick, apelido ou username para AUTOR_ATUAL.",
        "Os nomes entre parenteses nos rotulos servem apenas para entender quem falou; nao use esses nomes como chamada direta sem necessidade.",
        "Se houver varias pessoas no historico, nao misture autores: responda como se estivesse falando somente com AUTOR_ATUAL.",
        "Nunca atribua a AUTOR_ATUAL uma frase que apareceu com rotulo de OUTRA_PESSOA.",
        "Nao abra a resposta chamando OUTRA_PESSOA, a menos que AUTOR_ATUAL tenha pedido explicitamente um recado para essa pessoa.",
    ]

    partes.extend(obter_instrucoes_especiais_autor(message, texto_atual))

    if historico_recente:
        partes.append("HISTORICO_RECENTE_DO_CHAT:")
        partes.extend(historico_recente)
        partes.append("Se a MENSAGEM_ATUAL_DE_AUTOR_ATUAL for curta, ambigua, ou so uma reacao, interprete primeiro usando o HISTORICO_RECENTE_DO_CHAT.")
        partes.append("Use o historico apenas para manter o mesmo assunto. Nao mude de tema por causa dele.")
        partes.append("Nao trate uma reacao curta como problema pessoal e nao pergunte o que aconteceu sem base clara no historico.")

    partes.extend(
        [
            "MENSAGEM_ATUAL_DE_AUTOR_ATUAL abaixo e a ultima mensagem e e a unica que precisa de resposta:",
            f"MENSAGEM_ATUAL_DE_AUTOR_ATUAL: {texto_atual}",
            "Responda essa ultima mensagem usando o historico apenas como apoio.",
        ]
    )

    return "\n".join(partes)


def montar_contexto_reply_bot(message, mensagem_respondida, pergunta_diaria_texto=None, historico_recente=None):
    mensagem_raven = conteudo_mensagem_para_contexto_ia(mensagem_respondida, 420)
    mensagem_atual = conteudo_mensagem_para_contexto_ia(message, 420)
    partes = [
        "CONTEXTO DE REPLY AO RAVEN.",
        "Responda somente a mensagem atual usando a mensagem anterior do Raven como contexto imediato.",
        "Se o contexto ainda estiver fraco, peca esclarecimento curto em vez de chutar.",
        "De apenas uma resposta curta e coerente com o mesmo assunto.",
        "Evite resposta seca demais; reaja como conversa de Discord, nao como atendimento.",
        "A pessoa que esta falando agora e AUTOR_ATUAL.",
        f"AUTOR_ATUAL_ID: {message.author.id}",
        f"MENSAGEM_DO_RAVEN: {mensagem_raven}",
        f"MENSAGEM_ATUAL_DE_AUTOR_ATUAL: {mensagem_atual}",
        "Nao invente nome, nick, apelido ou username para AUTOR_ATUAL.",
        "Os nomes entre parenteses nos rotulos servem apenas para entender quem falou; nao use esses nomes como chamada direta sem necessidade.",
        "Se houver varias pessoas no historico, nao misture autores: responda como se estivesse falando somente com AUTOR_ATUAL.",
        "Nunca atribua a AUTOR_ATUAL uma frase que apareceu com rotulo de OUTRA_PESSOA.",
        "Nao abra a resposta chamando OUTRA_PESSOA, a menos que AUTOR_ATUAL tenha pedido explicitamente um recado para essa pessoa.",
        "A linha MENSAGEM_ATUAL_DE_AUTOR_ATUAL e sempre o alvo principal da resposta.",
        "Se a mensagem atual for curta, ambigua, ou so uma reacao, interprete primeiro pelo contexto ja fornecido.",
        "Nao trate uma resposta curta como novo problema, novo assunto, ou pedido de ajuda sem base clara.",
        "Nao pergunte o que aconteceu, o que houve, ou se esta tudo bem a menos que o contexto mostre claramente um problema real.",
    ]

    partes.extend(obter_instrucoes_especiais_autor(message, f"{mensagem_raven} {mensagem_atual}"))

    if pergunta_diaria_texto:
        partes.append("CASO_ESPECIAL: a MENSAGEM_DO_RAVEN acima e a PERGUNTA DIARIA atual do servidor.")
        partes.append(f"PERGUNTA_DIARIA_DO_SERVIDOR: {pergunta_diaria_texto}")
        partes.append("A MENSAGEM_ATUAL_DE_AUTOR_ATUAL e a resposta dessa pessoa a pergunta diaria.")
        partes.append("Reaja a resposta mantendo exatamente o mesmo assunto da pergunta diaria.")
        partes.append("Nao trate essa resposta como um tema novo, pedido novo, ou conversa sem contexto.")
        partes.append("Comente o que a pessoa respondeu, mas sem fazer pergunta de volta.")
        partes.append("Nao transforme a resposta da pergunta diaria em entrevista, continua ou novo interrogatorio.")
        partes.append("Mesmo se a resposta for curta, reaja com comentario curto, direto e ligado ao que a pessoa falou.")
        partes.append("Nao termine com pergunta, nao peca mais detalhes e nao puxe outro assunto.")

    contexto_anterior = runtime.contexto_respostas_bot.get(mensagem_respondida.id)
    if contexto_anterior:
        partes.append(
            "CONTEXTO_EXTRA_OPCIONAL: "
            f"a resposta anterior do Raven surgiu depois desta mensagem no chat: {contexto_anterior['mensagem_disparo']}"
        )
        partes.append("Nao confunda AUTOR_ATUAL com nomes citados na mensagem anterior ou na mensagem que disparou o gatilho.")
        partes.append(
            "Se houver um nome mencionado, trate esse nome como terceira pessoa por padrao, a menos que a mensagem atual deixe claramente que AUTOR_ATUAL esta falando de si."
        )
        partes.append("Use o CONTEXTO_EXTRA_OPCIONAL apenas se ele realmente ajudar a entender a mensagem atual.")

    if historico_recente:
        partes.append("HISTORICO_RECENTE_DO_CHAT:")
        partes.extend(historico_recente)
        partes.append("Use o HISTORICO_RECENTE_DO_CHAT so para manter continuidade com o mesmo assunto ja em andamento.")
        partes.append("Nao mude de assunto e nao invente um clima de preocupacao se o historico nao mostra isso.")

    return "\n".join(partes)


async def tentar_enviar_dm_lembrete_prazo_tag(canal_staff, registro):
    guild = getattr(canal_staff, "guild", None)
    user_id = registro.get("user_id")
    if not guild or not user_id:
        return "⚠️ Não foi possível avisar o membro no privado."

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return "⚠️ Não foi possível avisar o membro no privado."

    membro = guild.get_member(user_id_int)
    if not membro:
        try:
            membro = await guild.fetch_member(user_id_int)
        except Exception:
            membro = None

    if not membro:
        return "⚠️ Não foi possível localizar o membro para avisar no privado."

    try:
        await membro.send(
            embed=criar_embed_lembrete_dm_tag(registro),
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        return "✅ O membro foi avisado no privado."
    except discord.Forbidden:
        return "⚠️ Não foi possível avisar o membro no privado: DM fechada ou bloqueada."
    except discord.HTTPException:
        return "⚠️ Não foi possível avisar o membro no privado: o Discord recusou o envio."
    except Exception as erro:
        print("[TAG] Erro ao enviar DM de prazo de tag:")
        print(erro)
        return "⚠️ Não foi possível avisar o membro no privado."


class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ultimo_monitor_monotonic = None
        self.ultimo_loop_lag_segundos = 0.0
        self.ultima_latencia_alerta_monotonic = 0.0

    def obter_latencia_ms(self):
        try:
            latencia = float(self.bot.latency)
        except Exception:
            return None

        if latencia < 0:
            return None

        return round(latencia * 1000, 2)

    def montar_resumo_conexao(self):
        latencia_ms = self.obter_latencia_ms()
        latencia_texto = f"{latencia_ms}ms" if latencia_ms is not None else "indisponivel"
        return (
            f"latencia={latencia_texto} | "
            f"loop_lag={self.ultimo_loop_lag_segundos:.2f}s"
        )

    async def obter_canal_registro_fa_do_raven(self, guild):
        canal_id = obter_valor_config(
            guild,
            "RAVEN_FAN_LOG_CHANNEL_ID",
            obter_valor_config(guild, "RAVEN_ACHIEVEMENTS_CHANNEL_ID", 1521654695159005377),
        )
        if not canal_id:
            return None

        canal = self.bot.get_channel(int(canal_id))
        if canal is not None:
            return canal
        try:
            return await self.bot.fetch_channel(int(canal_id))
        except Exception:
            return None

    async def obter_cargo_fa_do_raven(self, guild):
        if guild is None:
            return None
        for cargo in getattr(guild, "roles", []) or []:
            if getattr(cargo, "name", None) == CONQUISTA_FA_DO_RAVEN["cargo_nome"]:
                return cargo
        try:
            cargos = await guild.fetch_roles()
        except Exception:
            return None
        return discord.utils.get(cargos, name=CONQUISTA_FA_DO_RAVEN["cargo_nome"])

    async def obter_canal_xp(self, guild):
        canal_id = obter_valor_config(guild, "XP_CHANNEL_ID")
        if not canal_id:
            return None

        canal = self.bot.get_channel(int(canal_id))
        if canal is not None:
            return canal
        try:
            return await self.bot.fetch_channel(int(canal_id))
        except Exception:
            return None

    async def obter_canal_anuncio_xp(self, guild):
        canal_id = obter_valor_config(guild, "XP_ANNOUNCE_CHANNEL_ID")
        if not canal_id:
            return None

        canal = self.bot.get_channel(int(canal_id))
        if canal is not None:
            return canal
        try:
            return await self.bot.fetch_channel(int(canal_id))
        except Exception:
            return None

    async def obter_cargos_xp(self, guild):
        role_ids = dict(obter_valor_config(guild, "XP_ROLE_IDS", {}))
        cargos = {}
        for role_key, role_id in role_ids.items():
            cargo = guild.get_role(int(role_id)) if guild and role_id else None
            if cargo is None and guild and role_id:
                try:
                    cargos_fetch = await guild.fetch_roles()
                    cargo = discord.utils.get(cargos_fetch, id=int(role_id))
                except Exception:
                    cargo = None
            cargos[role_key] = cargo
        return cargos

    async def sincronizar_cargos_xp(self, membro, role_key_novo):
        guild = getattr(membro, "guild", None)
        if guild is None:
            return None, False

        cargos_xp = await self.obter_cargos_xp(guild)
        cargo_recebido = cargos_xp.get(role_key_novo)
        cargo_adicionado = False
        cargos_para_remover = [
            cargo
            for chave, cargo in cargos_xp.items()
            if cargo is not None and chave != role_key_novo and cargo in getattr(membro, "roles", [])
        ]

        if cargos_para_remover:
            try:
                await membro.remove_roles(*cargos_para_remover, reason="Atualização de cargo por XP")
            except Exception:
                pass

        if role_key_novo is None:
            return None, False

        if cargo_recebido is not None and cargo_recebido not in getattr(membro, "roles", []):
            try:
                await membro.add_roles(cargo_recebido, reason="Novo cargo por XP")
            except Exception:
                return cargo_recebido, False
            cargo_adicionado = True
        return cargo_recebido, cargo_adicionado

    async def anunciar_cargo_xp(self, membro, xp_total, role_key_novo):
        if role_key_novo is None:
            return
        await enviar_embed_conquista(self.bot, membro, role_key_novo)

    async def avisar_limite_xp(self, membro, xp_diario):
        canal = await self.obter_canal_xp(getattr(membro, "guild", None))
        if canal is None:
            return

        limite = int(obter_valor_config(membro.guild, "XP_DAILY_LIMIT", 700))
        try:
            await canal.send(
                (
                    f"{membro.mention}, você atingiu seu limite diário de XP!\n\n"
                    f"XP diário: {xp_diario}/{limite}\n"
                    f"Volte amanhã para continuar acumulando XP."
                ),
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except Exception:
            return

    async def processar_xp_mensagem(self, message):
        dados_xp = carregar_dados_xp()
        resultado = registrar_xp_message(dados_xp, message.guild, message)
        if not resultado.get("ganhou"):
            if resultado.get("motivo") == "limite_diario":
                estado = obter_estado_xp_usuario(dados_xp, message.guild, message.author.id, criar=True)
                if str(estado.get("ultimo_aviso_limite_data", "")) != str(resultado.get("limite_data", "")):
                    estado["ultimo_aviso_limite_data"] = str(resultado.get("limite_data", ""))
                    salvar_dados_xp(dados_xp)
                    await self.avisar_limite_xp(message.author, int(estado.get("xp_diario", 0) or 0))
            return

        salvar_dados_xp(dados_xp)

        if resultado.get("promoveu"):
            _, cargo_ganho = await self.sincronizar_cargos_xp(message.author, resultado.get("role_key_novo"))
            if cargo_ganho:
                await self.anunciar_cargo_xp(
                    message.author,
                    int(resultado.get("xp_total", 0) or 0),
                    resultado.get("role_key_novo"),
                )

        if resultado.get("enviar_aviso_limite"):
            await self.avisar_limite_xp(message.author, int(resultado.get("xp_diario", 0) or 0))

    async def reverter_xp_por_exclusao(self, message):
        dados_xp = carregar_dados_xp()
        resultado = remover_xp_por_mensagem(dados_xp, message.guild, message.id)
        if not resultado.get("removeu"):
            return

        salvar_dados_xp(dados_xp)
        membro = getattr(message, "author", None)
        if membro is None:
            return
        await self.sincronizar_cargos_xp(membro, resultado.get("role_key_novo"))

    async def registrar_resposta_fa_do_raven_se_valida(self, message):
        canal_perguntas_id = obter_valor_config(getattr(message, "guild", None), "CANAL_PERGUNTAS_ID")
        if message.channel.id != canal_perguntas_id:
            return False
        if not membro_elegivel_fa_do_raven(message.author):
            return False
        if not mensagem_valida_fa_do_raven(message):
            return False

        chave, pergunta = obter_pergunta_diaria_aberta(message.guild)
        if not chave or not pergunta:
            return False

        try:
            channel_id = int(pergunta.get("channel_id"))
        except (TypeError, ValueError):
            return False
        if message.channel.id != channel_id:
            return False

        registrado, _ = registrar_resposta_fa_do_raven(
            message.guild,
            message.author.id,
            message.id,
            responded_at=message.created_at.astimezone(FUSO_HORARIO),
            content=message.content,
        )
        return bool(registrado)

    async def enviar_resumo_fa_do_raven(self, guild, data_chave, pergunta, resultado):
        canal = await self.obter_canal_registro_fa_do_raven(guild)
        if canal is None:
            return

        respondentes = resultado.get("respondentes") or []
        faltas = resultado.get("faltas") or []
        resetes = resultado.get("resetes") or []
        ganhos = resultado.get("ganhos") or []
        perdas = resultado.get("perdas") or []
        observacoes = resultado.get("observacoes") or []

        embed = discord.Embed(
            title="🐦‍⬛ Registro Fã do Raven",
            description=(
                f"Pergunta do dia: `{data_chave}`\n"
                f"Respostas válidas processadas até {datetime.now(FUSO_HORARIO).strftime('%d/%m/%Y às %H:%M')}."
            ),
            color=discord.Color.from_rgb(0, 255, 255),
        )

        blocos = [
            ("✅ Responderam no prazo", respondentes),
            ("⚠️ Receberam falta", faltas),
            ("💀 Progressos resetados", resetes),
            ("🏆 Conquistaram o cargo", ganhos),
            ("🥀 Perderam o cargo", perdas),
            ("📝 Observações", observacoes),
        ]

        adicionou = False
        for nome, linhas in blocos:
            if not linhas:
                continue
            adicionou = True
            for indice in range(0, len(linhas), 8):
                bloco = "\n".join(linhas[indice:indice + 8])
                embed.add_field(
                    name=nome if indice == 0 else "Continuação",
                    value=bloco[:1024],
                    inline=False,
                )

        if not adicionou:
            embed.add_field(
                name="Resumo",
                value="Nenhum progresso ou falta foi registrado nessa pergunta diária.",
                inline=False,
            )

        embed.set_footer(text="FDN • Conquista Fã do Raven")
        await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))

    async def processar_conquista_fa_do_raven_guild(self, guild, forcar=False):
        if guild is None:
            return 0

        agora = datetime.now(FUSO_HORARIO)
        pendentes = listar_perguntas_diarias_pendentes(guild, agora=agora)
        if not pendentes and forcar:
            chave, pergunta = obter_pergunta_diaria_aberta(guild, agora=agora)
            if chave and pergunta:
                pendentes = [(chave, pergunta)]

        processadas = 0
        for chave_data, pergunta in pendentes:
            dados = carregar_dados_conquistas()
            cargo = await self.obter_cargo_fa_do_raven(guild)
            respondentes = pergunta.get("respondentes") or {}
            resultado = {
                "respondentes": [],
                "faltas": [],
                "resetes": [],
                "ganhos": [],
                "perdas": [],
                "observacoes": [],
            }

            membros_guild = list(getattr(guild, "members", []) or [])
            if hasattr(guild, "fetch_members"):
                try:
                    async for membro_fetch in guild.fetch_members(limit=None):
                        if all(getattr(existente, "id", None) != getattr(membro_fetch, "id", None) for existente in membros_guild):
                            membros_guild.append(membro_fetch)
                except Exception:
                    pass

            elegiveis = [membro for membro in membros_guild if membro_elegivel_fa_do_raven(membro)]
            for membro in elegiveis:
                estado = obter_estado_fa_do_raven(dados, guild, membro.id, criar=True)
                possui_cargo_real = bool(cargo and cargo in getattr(membro, "roles", []))
                if possui_cargo_real and not bool(estado.get("possui_cargo")):
                    estado["possui_cargo"] = True
                    estado["progresso"] = CONQUISTA_FA_DO_RAVEN["objetivo"]

                registro = respondentes.get(str(membro.id))
                if registro:
                    estado["ultima_resposta_valida"] = registro.get("responded_at")
                    perguntas_respondidas = estado.setdefault("perguntas_respondidas", [])
                    if chave_data not in perguntas_respondidas:
                        perguntas_respondidas.append(chave_data)

                    if bool(estado.get("possui_cargo")) or possui_cargo_real:
                        estado["possui_cargo"] = True
                        estado["progresso"] = CONQUISTA_FA_DO_RAVEN["objetivo"]
                        estado["faltas_antes_cargo"] = 0
                        estado["faltas_com_cargo"] = 0
                        resultado["respondentes"].append(
                            f"{membro.mention} respondeu no prazo e manteve {CONQUISTA_FA_DO_RAVEN['objetivo']}/{CONQUISTA_FA_DO_RAVEN['objetivo']}."
                        )
                        continue

                    novo_progresso = min(
                        CONQUISTA_FA_DO_RAVEN["objetivo"],
                        int(estado.get("progresso", 0) or 0) + 1,
                    )
                    estado["progresso"] = novo_progresso
                    estado["faltas_antes_cargo"] = 0
                    estado["faltas_com_cargo"] = 0

                    if novo_progresso >= CONQUISTA_FA_DO_RAVEN["objetivo"]:
                        cargo_aplicado = False
                        if cargo is not None:
                            try:
                                if cargo not in getattr(membro, "roles", []):
                                    await membro.add_roles(cargo, reason="Conquista Fã do Raven")
                                cargo_aplicado = True
                            except Exception as erro:
                                resultado["observacoes"].append(
                                    f"{membro.mention} chegou a 35/35, mas não consegui aplicar o cargo. `{erro}`"
                                )
                        else:
                            resultado["observacoes"].append(
                                f"{membro.mention} chegou a 35/35, mas o cargo {CONQUISTA_FA_DO_RAVEN['cargo_nome']} não foi encontrado."
                            )

                        if cargo_aplicado:
                            estado["possui_cargo"] = True
                            estado["progresso"] = CONQUISTA_FA_DO_RAVEN["objetivo"]
                            resultado["ganhos"].append(
                                f"{membro.mention} alcançou 35/35 e conquistou {CONQUISTA_FA_DO_RAVEN['cargo_nome']}!"
                            )
                            await enviar_embed_conquista(self.bot, membro, "fa_do_raven", progresso="35/35")
                    else:
                        resultado["respondentes"].append(
                            f"{membro.mention} respondeu o Raven e avançou para {novo_progresso}/35 em Fã do Raven."
                        )
                    continue

                if bool(estado.get("possui_cargo")) or possui_cargo_real:
                    estado["possui_cargo"] = True
                    nova_falta = int(estado.get("faltas_com_cargo", 0) or 0) + 1
                    estado["faltas_com_cargo"] = nova_falta
                    if nova_falta >= CONQUISTA_FA_DO_RAVEN["faltas_perda"]:
                        if cargo is not None and cargo in getattr(membro, "roles", []):
                            try:
                                await membro.remove_roles(cargo, reason="Perda da conquista Fã do Raven")
                            except Exception as erro:
                                resultado["observacoes"].append(
                                    f"{membro.mention} atingiu a perda do cargo, mas não consegui remover. `{erro}`"
                                )
                        estado["progresso"] = 0
                        estado["faltas_antes_cargo"] = 0
                        estado["faltas_com_cargo"] = 0
                        estado["possui_cargo"] = False
                        resultado["perdas"].append(
                            f"{membro.mention} deixou de responder o Raven 7 vezes e perdeu o cargo {CONQUISTA_FA_DO_RAVEN['cargo_nome']}."
                        )
                    else:
                        resultado["faltas"].append(
                            f"{membro.mention} — falta {nova_falta}/7 antes de perder o cargo."
                        )
                    continue

                nova_falta = int(estado.get("faltas_antes_cargo", 0) or 0) + 1
                estado["faltas_antes_cargo"] = nova_falta
                if nova_falta >= CONQUISTA_FA_DO_RAVEN["faltas_reset"]:
                    estado["progresso"] = 0
                    estado["faltas_antes_cargo"] = 0
                    estado["faltas_com_cargo"] = 0
                    resultado["resetes"].append(
                        f"{membro.mention} deixou de responder 5 vezes e voltou para 0/35 em Fã do Raven."
                    )
                else:
                    resultado["faltas"].append(
                        f"{membro.mention} — falta {nova_falta}/5 antes de resetar."
                    )

            perguntas_diarias = (dados.setdefault("guilds", {}).setdefault(str(guild.id), {})).setdefault("perguntas_diarias", {})
            if chave_data in perguntas_diarias:
                perguntas_diarias[chave_data]["processada"] = True
            salvar_dados_conquistas(dados)
            await self.enviar_resumo_fa_do_raven(guild, chave_data, pergunta, resultado)
            processadas += 1

        return processadas

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Bot online como {self.bot.user}")

        try:
            resetar_gatilhos_para_base()
            await aplicar_frases_custom_nos_gatilhos()
        except Exception as erro:
            print("ERRO AO CARREGAR FRASES CUSTOM DO D1:")
            print(erro)
            await enviar_log_bot(
                "❌ Erro ao carregar frases customizadas",
                f"```{erro}```"
            )

        if runtime.bot_desconectado_desde:
            offline_desde = runtime.bot_desconectado_desde.astimezone(FUSO_HORARIO).strftime("%d/%m/%Y às %H:%M:%S")
            await enviar_log_bot(
                "🟠 Bot reconectado",
                (
                    f"O bot perdeu conexão e voltou a ficar online como **{self.bot.user}**.\n"
                    f"**Offline desde:** {offline_desde}"
                )
            )
            runtime.bot_desconectado_desde = None
        else:
            await enviar_log_bot(
                "🟢 Bot online",
                f"O bot iniciou com sucesso como **{self.bot.user}**."
            )

        if not self.pergunta_diaria.is_running():
            self.pergunta_diaria.start()

        if not self.verificador_conquista_raven.is_running():
            self.verificador_conquista_raven.start()

        if not self.verificador_tags.is_running():
            self.verificador_tags.start()

        if not self.monitor_conexao.is_running():
            self.monitor_conexao.start()

    @commands.Cog.listener()
    async def on_disconnect(self):
        runtime.bot_desconectado_desde = datetime.now(timezone.utc)
        print(
            "[BOT] Conexão com o Discord foi perdida em "
            f"{runtime.bot_desconectado_desde.isoformat()} | "
            f"{self.montar_resumo_conexao()}"
        )

    @commands.Cog.listener()
    async def on_resumed(self):
        agora = datetime.now(timezone.utc)
        offline_segundos = None
        if runtime.bot_desconectado_desde:
            offline_segundos = (agora - runtime.bot_desconectado_desde).total_seconds()
            runtime.bot_desconectado_desde = None

        offline_texto = (
            f"{offline_segundos:.2f}s"
            if offline_segundos is not None
            else "desconhecido"
        )
        print(
            f"[BOT] Sessão do Discord retomada em {agora.isoformat()} | "
            f"offline={offline_texto} | {self.montar_resumo_conexao()}"
        )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        cargos_antes = {cargo.id for cargo in getattr(before, "roles", [])}
        cargos_depois = {cargo.id for cargo in getattr(after, "roles", [])}

        cargo_mensageiro_id = obter_valor_config(
            after.guild,
            "MENSAGEIRO_DA_NOITE_ROLE_ID",
            MENSAGEIRO_DA_NOITE_ROLE_ID,
        )
        if cargo_mensageiro_id and cargo_mensageiro_id not in cargos_antes and cargo_mensageiro_id in cargos_depois:
            await enviar_embed_conquista(self.bot, after, "mensageiro_da_noite", progresso="5/5")

        cargo_boas_vindas_id = obter_valor_config(after.guild, "BOAS_VINDAS_ROLE_ID", BOAS_VINDAS_ROLE_ID)
        tinha_cargo_membro = cargo_boas_vindas_id in cargos_antes
        ganhou_cargo_membro = cargo_boas_vindas_id in cargos_depois

        if tinha_cargo_membro or not ganhou_cargo_membro:
            return

        try:
            mensagem_enviada = await enviar_boas_vindas_no_geral(after)
            if not mensagem_enviada:
                return

            await enviar_log_bot(
                "👋 Boas-vindas automáticas enviadas",
                (
                    f"**Membro:** {after.mention}\n"
                    f"**Canal de envio:** <#{CANAL_GERAL_ID}>\n"
                    f"**Motivo:** recebeu o cargo <@&{cargo_boas_vindas_id}>"
                )
            )
        except Exception as erro:
            await enviar_log_bot(
                "❌ Erro nas boas-vindas automáticas",
                (
                    f"**Membro:** {after.mention}\n"
                    f"**Motivo:** recebeu o cargo <@&{cargo_boas_vindas_id}>\n"
                    f"```{erro}```"
                )
            )

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None or getattr(message.author, "bot", False):
            return
        try:
            remover_resposta_fa_do_raven(message.guild, message.author.id, message.id)
        except Exception:
            pass
        try:
            await self.reverter_xp_por_exclusao(message)
        except Exception:
            return

    @tasks.loop(minutes=1)
    async def pergunta_diaria(self):
        agora = datetime.now(FUSO_HORARIO)

        if agora.hour != 19 or agora.minute != 0:
            return

        for guild in self.bot.guilds:
            try:
                await enviar_pergunta_do_dia(guild_ou_id=guild)
            except Exception:
                continue

    @pergunta_diaria.before_loop
    async def before_pergunta_diaria(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=1)
    async def verificador_conquista_raven(self):
        for guild in self.bot.guilds:
            try:
                await self.processar_conquista_fa_do_raven_guild(guild)
            except Exception as erro:
                print(f"[RAVEN] Erro ao processar conquista diária | guild={getattr(guild, 'id', None)} erro={erro}")

    @verificador_conquista_raven.before_loop
    async def before_verificador_conquista_raven(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=30)
    async def monitor_conexao(self):
        agora_monotonic = time.monotonic()
        if self.ultimo_monitor_monotonic is not None:
            intervalo_real = agora_monotonic - self.ultimo_monitor_monotonic
            atraso = max(0.0, intervalo_real - 30.0)
            self.ultimo_loop_lag_segundos = atraso

            if atraso >= 5:
                print(
                    f"[BOT] Event loop atrasou {atraso:.2f}s | "
                    f"{self.montar_resumo_conexao()}"
                )

        self.ultimo_monitor_monotonic = agora_monotonic

        latencia_ms = self.obter_latencia_ms()
        if (
            latencia_ms is not None
            and latencia_ms >= 2000
            and (
                self.ultima_latencia_alerta_monotonic == 0.0
                or (agora_monotonic - self.ultima_latencia_alerta_monotonic) >= 300
            )
        ):
            self.ultima_latencia_alerta_monotonic = agora_monotonic
            print(
                f"[BOT] Latência alta detectada | "
                f"{self.montar_resumo_conexao()}"
            )

    @monitor_conexao.before_loop
    async def before_monitor_conexao(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def verificador_tags(self):
        canal_staff = self.bot.get_channel(CANAL_STAFF_TAGS_ID)

        if not canal_staff:
            try:
                canal_staff = await self.bot.fetch_channel(CANAL_STAFF_TAGS_ID)
            except Exception:
                return

        dados = await carregar_dados_tags()
        alterou = False
        atrasadissimos = []
        registros_7_dias = []
        registros_10_dias = []
        data_hoje = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
        agora_local = datetime.now(FUSO_HORARIO)

        for chave, registro in list(dados["pendentes"].items()):
            if registro.get("status") != "pendente":
                continue

            prazo_troca = parse_iso_datetime(registro.get("prazo_troca", ""))
            dias = dias_passados_desde(registro.get("data_envio", ""))

            if prazo_troca and agora_local.astimezone(timezone.utc) >= prazo_troca.astimezone(timezone.utc) and not registro.get("avisou_7_dias", False):
                registros_7_dias.append(registro)
                registro["avisou_7_dias"] = True
                alterou = True
            elif dias >= 7 and not registro.get("avisou_7_dias", False):
                registros_7_dias.append(registro)
                registro["avisou_7_dias"] = True
                alterou = True
            elif dias >= 10 and not registro.get("avisou_10_dias", False):
                registros_10_dias.append(registro)
                registro["avisou_7_dias"] = True
                registro["avisou_10_dias"] = True
                alterou = True

            if dias >= 11:
                atrasadissimos.append(registro)

        if registros_7_dias:
            for registro in registros_7_dias:
                status_aviso_privado = None
                if not registro.get("avisou_dm_prazo", False):
                    status_aviso_privado = await tentar_enviar_dm_lembrete_prazo_tag(canal_staff, registro)
                    registro["avisou_dm_prazo"] = True
                    alterou = True

                await enviar_lembrete_prazo_tag(
                    canal_staff,
                    registro,
                    status_aviso_privado=status_aviso_privado,
                )

        if registros_10_dias:
            await enviar_aviso_tags_em_lote(canal_staff, registros_10_dias, 10)

        if (
            agora_local.hour >= 10
            and atrasadissimos
            and dados.get("ultima_data_alerta_11") != data_hoje
        ):
            await enviar_alerta_tags_atrasadissimas(canal_staff, atrasadissimos)
            dados["ultima_data_alerta_11"] = data_hoje
            alterou = True

        if alterou:
            await salvar_dados_tags(dados)

    @verificador_tags.before_loop
    async def before_verificador_tags(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.guild is None:
            return

        runtime.ultima_mensagem_usuario[str(message.author.id)] = message.created_at

        texto = message.content.lower().strip()
        mensagem_eh_reply = bool(message.reference and message.reference.message_id)
        eh_comando_prefixado = texto.startswith("!")
        bot_foi_mencionado = self.bot.user in message.mentions
        canal_atual_eh_ticket = canal_eh_ticket(message.channel)
        cargo_staff_id = obter_valor_config(getattr(message, "guild", None), "CARGO_STAFF_ID")
        canal_contagem_id = obter_valor_config(getattr(message, "guild", None), "CANAL_CONTAGEM_ID")
        canal_perguntas_id = obter_valor_config(getattr(message, "guild", None), "CANAL_PERGUNTAS_ID")
        canal_geral_id = obter_valor_config(getattr(message, "guild", None), "CANAL_GERAL_ID")
        bot_ia_ativa = bool(obter_valor_config(getattr(message, "guild", None), "BOT_IA_ATIVA", True))
        canal_atual_eh_geral = message.channel.id == canal_geral_id
        agora = time.time()
        data_hoje = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")

        for msg_id, timestamp in list(runtime.mensagens_processadas.items()):
            if agora - timestamp > TTL_MENSAGEM_PROCESSADA:
                del runtime.mensagens_processadas[msg_id]

        if message.id in runtime.mensagens_processadas:
            return

        runtime.mensagens_processadas[message.id] = agora
        limpar_conversas_raven_expiradas(agora)

        try:
            await self.registrar_resposta_fa_do_raven_se_valida(message)
        except Exception:
            pass
        try:
            await self.processar_xp_mensagem(message)
        except Exception:
            pass

        if canal_atual_eh_ticket and not eh_comando_prefixado:
            await avisar_assumir_ticket_se_necessario(message, agora)

        if message.channel.id == canal_contagem_id and message.content.strip().lower().startswith("+1"):
            await registrar_recrutamento_da_mensagem(message, agora, origem="chat")
            return

        if message.channel.id == canal_contagem_id and message.content.strip().lower().startswith("+1"):
            if not usuario_pode_registrar_recrutamento(message.author.id, agora):
                restante = int(COOLDOWN_RECRUTAMENTO - (agora - runtime.cooldowns_recrutamento.get(message.author.id, 0)))
                if restante < 1:
                    restante = 1

                await message.channel.send(
                    embed=criar_embed_tags(
                        "⚠️ Calma aí",
                        f"{message.author.mention}, espera **{restante}s** antes de registrar outro `+1`."
                    )
                )
                return

            if not mensagem_eh_recrutamento(message.content):
                await message.channel.send(
                    embed=criar_embed_tags(
                        "⚠️ Formato inválido",
                        "Use assim: `+1 nome_do_discord`."
                    )
                )
                return

            recrutado_texto = resolver_recrutado_texto(message.guild, message)

            if not recrutado_texto:
                await message.channel.send(
                    embed=criar_embed_tags(
                        "❌ Recrutado inválido",
                        "Não consegui identificar o recrutado."
                    )
                )
                return

            if recrutado_texto == message.author.mention:
                await message.channel.send(
                    embed=criar_embed_tags(
                        "❌ Recrutamento inválido",
                        "Você não pode registrar `+1` para você mesmo."
                    )
                )
                return

            try:
                salvo = await registrar_recrutamento(
                    message_id=message.id,
                    recrutador_id=message.author.id,
                    recrutador_nome=str(message.author),
                    canal_id=message.channel.id,
                    recrutado_texto=recrutado_texto,
                    origem="chat"
                )

                if salvo:
                    runtime.cooldowns_recrutamento[message.author.id] = agora
                    total_mes = await total_recrutamentos_mes(message.author.id)

                    descricao = (
                        f"**Recrutador:** {message.author.mention}\n"
                        f"**Total no mês:** {total_mes}\n"
                        f"**Recrutado:** {recrutado_texto}"
                    )

                    await message.channel.send(embed=criar_embed_tags("✅ Recrutamento registrado", descricao))

                    await enviar_log_bot(
                        "✅ Recrutamento automático registrado",
                        (
                            f"**Recrutador:** {message.author.mention}\n"
                            f"**Canal:** {message.channel.mention}\n"
                            f"**Mensagem:** `{message.id}`\n"
                            f"**Recrutado:** {recrutado_texto}\n"
                            f"**Total no mês:** {total_mes}"
                        )
                    )
            except Exception as erro:
                print("ERRO AO REGISTRAR RECRUTAMENTO AUTOMÁTICO:")
                print(erro)
                await enviar_log_bot(
                    "❌ Erro no recrutamento automático",
                    (
                        f"**Recrutador:** {message.author.mention}\n"
                        f"**Canal:** {message.channel.mention}\n"
                        f"**Mensagem:** `{message.id}`\n"
                        f"```{erro}```"
                    )
                )

            return

        if texto == "!pergunta":
            if not usuario_tem_cargo(message, cargo_staff_id):
                return

            enviada, erro = await enviar_pergunta_do_dia(forcar=True, guild_ou_id=message.guild)
            if not enviada and erro:
                await message.channel.send(erro)
            return

        respondeu_npc_sem_quest = False
        try:
            respondeu_npc_sem_quest = await responder_npc_sem_quest_se_necessario(self.bot, message, agora)
        except Exception as erro:
            print(
                f"[NPC] Falha no gatilho NPC sem quest | "
                f"guild={getattr(message.guild, 'id', None)} canal={getattr(message.channel, 'id', None)} "
                f"user={getattr(message.author, 'id', None)} erro={erro!r}"
            )
            respondeu_npc_sem_quest = False
        if respondeu_npc_sem_quest:
            return

        respondeu_bot, mensagem_respondida = await respondeu_mensagem_do_bot(message)
        mensagem_direcionada_raven = False
        motivo_direcao_raven = "ignorada"
        sessao_raven = None
        if texto and not canal_atual_eh_ticket and bot_ia_ativa and not eh_comando_prefixado:
            mensagem_direcionada_raven, motivo_direcao_raven, sessao_raven = resolver_direcionamento_raven(
                message,
                bot_foi_mencionado=bot_foi_mencionado,
                respondeu_bot=respondeu_bot,
                mensagem_respondida=mensagem_respondida,
                agora_ts=agora,
            )

        if texto and not canal_atual_eh_ticket and mensagem_direcionada_raven:
            if motivo_direcao_raven == "mention":
                pergunta = (
                    message.content.replace(f"<@{self.bot.user.id}>", "")
                    .replace(f"<@!{self.bot.user.id}>", "")
                    .strip()
                )
                if not pergunta:
                    resposta_mencao = escolher_resposta_gatilho("mencao_vazia", FRASES_MENCAO_VAZIA)
                    if resposta_mencao:
                        await message.channel.send(resposta_mencao)
                    return

                ultimo_uso_ia = runtime.cooldowns_ia.get(message.author.id, 0)
                if agora - ultimo_uso_ia < COOLDOWN_IA:
                    return
                texto_direcionado = pergunta
            else:
                texto_direcionado = message.content

            contexto_respondido = runtime.contexto_respostas_bot.get(getattr(mensagem_respondida, "id", 0), {})
            if motivo_direcao_raven == "reply" and contexto_respondido.get("gatilho") in {"boas_vindas", "pergunta_diaria_reply"}:
                return

            registrar_mensagem_usuario_conversa_raven(
                sessao_raven,
                message,
                conteudo_mensagem_para_contexto_ia(message, 260),
            )

            historico_recente = [formatar_item_contexto_raven(item) for item in obter_historico_conversa_raven(sessao_raven)]
            registrar_log_debug_raven(
                message,
                direcionada=True,
                motivo=motivo_direcao_raven,
                sessao=sessao_raven,
            )

            pergunta_diaria_message_id = None
            pergunta_diaria_texto = None
            chave_resposta_unica = None
            resposta = None

            if motivo_direcao_raven == "reply" and mensagem_respondida is not None:
                pergunta_diaria_message_id = obter_id_pergunta_diaria_atual_respondida(message, mensagem_respondida)
                pergunta_diaria_texto = obter_pergunta_diaria_atual_respondida(message, mensagem_respondida)
                chave_resposta_unica = (
                    f"{pergunta_diaria_message_id}:{message.author.id}" if pergunta_diaria_message_id else None
                )
                resposta = resposta_percentual_deterministica(mensagem_respondida.content, message.content)

            tipo_mensagem = "resposta" if pergunta_diaria_texto else classificar_intencao_conversa(
                texto_direcionado,
                historico_recente=historico_recente,
            )

            if not resposta:
                resposta = resposta_local_raven(
                    message,
                    texto_direcionado,
                    tipo_mensagem,
                    agora,
                    historico_recente=historico_recente,
                )

            if not resposta:
                contexto_raven = montar_contexto_estruturado_raven(
                    message,
                    sessao=sessao_raven,
                    motivo_direcao=motivo_direcao_raven,
                    mensagem_respondida=mensagem_respondida if motivo_direcao_raven == "reply" else None,
                    pergunta_diaria_texto=pergunta_diaria_texto,
                )
                resposta = await perguntar_ia(contexto_raven, tipo_mensagem=tipo_mensagem)
                if motivo_direcao_raven == "mention":
                    runtime.cooldowns_ia[message.author.id] = agora

            if resposta:
                if motivo_direcao_raven == "reply":
                    resposta = normalizar_resposta_reply_bot(resposta, message, historico_recente=historico_recente)
                else:
                    resposta = normalizar_resposta_ia_para_autor(
                        resposta,
                        message,
                        historico_recente=historico_recente,
                    )
                resposta = garantir_resposta_no_contexto_raven(
                    resposta,
                    sessao_raven,
                    message=message,
                    mensagem_respondida=mensagem_respondida if motivo_direcao_raven == "reply" else None,
                )
                mensagem_bot = await enviar_resposta_em_contexto(message.channel, message, resposta)
                if mensagem_bot:
                    registrar_contexto_resposta_bot(
                        mensagem_bot,
                        f"ia_{motivo_direcao_raven}",
                        message,
                        session_id=sessao_raven.get("session_id") if sessao_raven else None,
                    )
                    registrar_resposta_conversa_raven(sessao_raven, mensagem_bot, message, resposta)
                    if pergunta_diaria_message_id and chave_resposta_unica:
                        registrar_contexto_resposta_bot(
                            mensagem_bot,
                            "pergunta_diaria_reply",
                            message,
                            pergunta_diaria_message_id=pergunta_diaria_message_id,
                            pergunta_diaria_texto=pergunta_diaria_texto,
                            session_id=sessao_raven.get("session_id") if sessao_raven else None,
                        )
                registrar_log_debug_raven(
                    message,
                    direcionada=True,
                    motivo=motivo_direcao_raven,
                    sessao=sessao_raven,
                    resposta=resposta,
                )
            return

        canal_atual_eh_geral = message.channel.id == canal_geral_id
        bom_dia_ativo = bool(
            obter_valor_config(
                getattr(message, "guild", None),
                "GATILHO_BOM_DIA_ATIVO",
                GATILHO_BOM_DIA_ATIVO,
            )
        )
        gatilhos_permitidos_com_geral_desligado = {"comando_jogatina"}
        if bom_dia_ativo:
            gatilhos_permitidos_com_geral_desligado.add("bom_dia")

        if (GATILHOS_ATIVOS or gatilhos_permitidos_com_geral_desligado) and not mensagem_eh_reply and not canal_atual_eh_ticket and not bot_foi_mencionado:
            for chave, dados_gatilho in runtime.GATILHOS.items():
                if not GATILHOS_ATIVOS and chave not in gatilhos_permitidos_com_geral_desligado:
                    continue

                palavras = dados_gatilho["palavras"]
                respostas = dados_gatilho["respostas"]
                apenas_staff = dados_gatilho.get("apenas_staff", False)
                exato = dados_gatilho.get("exato", False)
                sem_cooldown = dados_gatilho.get("sem_cooldown", False)
                uma_vez_por_dia_global = dados_gatilho.get("uma_vez_por_dia_global", False)
                bloquear_usuario_permanente = dados_gatilho.get("bloquear_usuario_permanente", False)
                cooldown_usuario = dados_gatilho.get("cooldown_usuario", COOLDOWN_MESMA_PESSOA)
                cooldown_global = dados_gatilho.get("cooldown_global", COOLDOWN_OUTRA_PESSOA)

                for palavra in palavras:
                    if chave in {"comando_interagir", "comando_recrutadores"}:
                        continue

                    if not canal_atual_eh_geral and chave not in {*GATILHOS_CIDADES, "comando_jogatina"}:
                        continue

                    encontrou = texto == palavra.lower() if exato else gatilho_encontrado(texto, palavra)

                    if encontrou:
                        if not gatilho_permitido_no_horario(chave):
                            continue

                        if apenas_staff and not usuario_tem_cargo(message, cargo_staff_id):
                            return

                        canal_destino = await obter_canal_destino_gatilho(self.bot, message, chave)
                        if not canal_destino:
                            return

                        if sem_cooldown:
                            resposta_gatilho = escolher_resposta_gatilho(chave, respostas)
                            if not resposta_gatilho:
                                return

                            resposta_gatilho = normalizar_resposta_gatilho(chave, resposta_gatilho)

                            mensagem_bot = await canal_destino.send(
                                resposta_gatilho,
                                allowed_mentions=discord.AllowedMentions(roles=True)
                            )
                            registrar_contexto_resposta_bot(mensagem_bot, chave, message)
                            await limpar_mensagem_comando_gatilho(message, chave)
                            return

                        chave_usuario = f"{message.author.id}:{chave}"
                        chave_global_diaria = f"diario:{chave}"
                        usuarios_bloqueados = runtime.usuarios_gatilhos_permanentes.setdefault(chave, [])
                        usuario_ja_ativou = str(message.author.id) in usuarios_bloqueados
                        ultimo_uso_usuario = runtime.cooldowns_usuario.get(chave_usuario, 0)
                        ultimo_uso_global = runtime.cooldowns_global.get(chave, 0)

                        pode_responder_usuario = (
                            not (bloquear_usuario_permanente and usuario_ja_ativou)
                            and agora - ultimo_uso_usuario >= cooldown_usuario
                        )
                        if uma_vez_por_dia_global:
                            pode_responder_global = runtime.cooldowns_global.get(chave_global_diaria) != data_hoje
                        else:
                            pode_responder_global = agora - ultimo_uso_global >= cooldown_global

                        if pode_responder_usuario and pode_responder_global:
                            runtime.cooldowns_usuario[chave_usuario] = agora
                            if bloquear_usuario_permanente:
                                usuarios_bloqueados.append(str(message.author.id))
                                runtime.salvar_ultimas_respostas_gatilho()
                            if uma_vez_por_dia_global:
                                runtime.cooldowns_global[chave_global_diaria] = data_hoje
                            else:
                                runtime.cooldowns_global[chave] = agora
                            resposta_gatilho = escolher_resposta_gatilho(chave, respostas)

                            if not resposta_gatilho:
                                return

                            resposta_gatilho = normalizar_resposta_gatilho(chave, resposta_gatilho)

                            mensagem_bot = await canal_destino.send(
                                resposta_gatilho,
                                allowed_mentions=discord.AllowedMentions(roles=True)
                            )
                            registrar_contexto_resposta_bot(mensagem_bot, chave, message)
                            await limpar_mensagem_comando_gatilho(message, chave)

                        return

        if eh_comando_prefixado:
            return

    @commands.Cog.listener("on_raw_reaction_add")
    async def on_raw_reaction_add_contagem(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        canal_contagem_id = obter_valor_config(payload.guild_id, "CANAL_CONTAGEM_ID", CANAL_CONTAGEM_ID)
        if payload.channel_id != canal_contagem_id:
            return

        canal_contagem = self.bot.get_channel(payload.channel_id)
        if not canal_contagem:
            try:
                canal_contagem = await self.bot.fetch_channel(payload.channel_id)
            except Exception:
                return

        try:
            mensagem_contagem = await canal_contagem.fetch_message(payload.message_id)
        except Exception:
            return

        if mensagem_contagem.author.bot:
            return

        if payload.user_id != mensagem_contagem.author.id:
            return

        await registrar_recrutamento_da_mensagem(mensagem_contagem, time.time(), origem="reacao")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        print(f"[TAG] Reação detectada: user={payload.user_id} canal={payload.channel_id} emoji={payload.emoji} mensagem={payload.message_id}")

        if payload.user_id == self.bot.user.id:
            print("[TAG] Ignorado: reação do próprio bot.")
            return

        if payload.channel_id not in [CANAL_TIME_TAGS_ID, CANAL_TAGS_FINAL_ID]:
            print("[TAG] Ignorado: reação fora dos canais de tags.")
            return

        if str(payload.emoji) != EMOJI_APROVAR_TAG:
            print(f"[TAG] Ignorado: emoji diferente do esperado ({payload.emoji}).")
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            print("[TAG] Ignorado: guild não encontrada.")
            await enviar_log_bot("⚠️ Falha ao processar reação", f"Guild não encontrada para a reação da mensagem `{payload.message_id}`.")
            return

        membro_staff = guild.get_member(payload.user_id)
        if not membro_staff:
            try:
                membro_staff = await guild.fetch_member(payload.user_id)
            except Exception:
                print("[TAG] Ignorado: não consegui buscar o membro que reagiu.")
                await enviar_log_bot("⚠️ Falha ao buscar staff", f"Não consegui buscar o membro que reagiu na mensagem `{payload.message_id}`.")
                return

        if not membro_eh_staff(membro_staff):
            print(f"[TAG] Ignorado: quem reagiu não é staff ({membro_staff}).")
            return

        canal = self.bot.get_channel(payload.channel_id)
        if not canal:
            try:
                canal = await self.bot.fetch_channel(payload.channel_id)
            except Exception:
                print("[TAG] Ignorado: canal não encontrado.")
                await enviar_log_bot("⚠️ Falha ao buscar canal", f"Não consegui buscar o canal `{payload.channel_id}`.")
                return

        try:
            message = await canal.fetch_message(payload.message_id)
        except Exception:
            print("[TAG] Ignorado: não consegui buscar a mensagem reagida.")
            await enviar_log_bot("⚠️ Falha ao buscar mensagem", f"Não consegui buscar a mensagem `{payload.message_id}` no canal <#{payload.channel_id}>.")
            return

        if message.author.bot:
            print("[TAG] Ignorado: mensagem de bot.")
            return
        if membro_eh_staff(message.author):
            print(f"[TAG] Ignorado: autor da mensagem é staff ({message.author}).")
            return
        if len(message.attachments) == 0:
            print("[TAG] Ignorado: mensagem sem anexo.")
            return

        if payload.channel_id == CANAL_TIME_TAGS_ID:
            try:
                resultado, registro = await registrar_timetag_pendente(
                    usuario_id=message.author.id,
                    nome_usuario=str(message.author),
                    canal_origem_id=payload.channel_id,
                    staff_registro_id=membro_staff.id,
                    staff_registro_nome=str(membro_staff),
                    message_id=message.id,
                    message_link=message.jump_url,
                )
                if resultado == "duplicado":
                    print(f"[TAG] Pendência já existente para: {message.author} ({message.author.id})")
                    await enviar_log_timetag_duplicada(
                        self.bot,
                        guild,
                        message.author,
                        registro,
                        message,
                    )
                else:
                    print(f"[TAG] Salvo com sucesso: {message.author} ({message.author.id})")
                    await enviar_log_timetag_registrada(
                        self.bot,
                        guild,
                        message.author,
                        membro_staff,
                        registro,
                    )
            except Exception as erro:
                print("[TAG] Erro ao salvar tag pendente:")
                print(erro)
                await enviar_log_bot(
                    "❌ Erro ao salvar tag pendente",
                    (
                        f"Erro ao registrar tag pendente.\n"
                        f"**Staff:** {membro_staff.mention}\n"
                        f"**Membro:** {message.author.mention}\n"
                        f"**Mensagem:** `{message.id}`\n"
                        f"```{erro}```"
                    )
                )
            return

        if payload.channel_id == CANAL_TAGS_FINAL_ID:
            try:
                registro_concluido = await concluir_tag_pendente_com_detalhes(
                    message.author.id,
                    staff_conclusao_id=membro_staff.id,
                    staff_conclusao_nome=str(membro_staff),
                    message_id=message.id,
                    message_link=message.jump_url,
                )

                if registro_concluido:
                    await enviar_log_tag_concluida(
                        self.bot,
                        guild,
                        message.author,
                        membro_staff,
                        registro_concluido,
                        message,
                    )
                else:
                    await enviar_log_tag_verificada(
                        self.bot,
                        guild,
                        message.author,
                        membro_staff,
                        canal,
                        message,
                    )
            except Exception as erro:
                print("[TAG] Erro ao concluir/aprovar tag:")
                print(erro)
                await enviar_log_bot(
                    "❌ Erro ao concluir tag por reação",
                    (
                        f"**Staff:** {membro_staff.mention}\n"
                        f"**Membro:** {message.author.mention}\n"
                        f"**Mensagem:** `{message.id}`\n"
                        f"```{erro}```"
                    )
                )
            return


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
