import json
import os
from datetime import datetime, timezone

from config import ARQUIVO_AUSENCIAS, FUSO_HORARIO
from services.server_config import extrair_guild_id


def carregar_dados_ausencias():
    dados_padrao = {"eventos": {}, "reset_contagens_por_guild": {}}

    if not os.path.exists(ARQUIVO_AUSENCIAS):
        return dados_padrao

    try:
        with open(ARQUIVO_AUSENCIAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError, TypeError):
        return dados_padrao

    if not isinstance(dados, dict):
        return dados_padrao

    eventos = dados.get("eventos", {})
    if not isinstance(eventos, dict):
        eventos = {}

    reset_contagens_por_guild = dados.get("reset_contagens_por_guild", {})
    if not isinstance(reset_contagens_por_guild, dict):
        reset_contagens_por_guild = {}

    return {
        "eventos": eventos,
        "reset_contagens_por_guild": reset_contagens_por_guild,
    }


def salvar_dados_ausencias(dados):
    with open(ARQUIVO_AUSENCIAS, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def obter_reset_contagens(guild_ou_id=None):
    guild_id = extrair_guild_id(guild_ou_id)
    if guild_id is None:
        return None

    dados = carregar_dados_ausencias()
    resets = dados.get("reset_contagens_por_guild", {})
    if not isinstance(resets, dict):
        return None

    return resets.get(str(guild_id))


def definir_reset_contagens(guild_ou_id, momento=None):
    guild_id = extrair_guild_id(guild_ou_id)
    if guild_id is None:
        return None

    if momento is None:
        momento = datetime.now(FUSO_HORARIO)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=FUSO_HORARIO)

    momento_iso = momento.astimezone(FUSO_HORARIO).isoformat()
    dados = carregar_dados_ausencias()
    resets = dados.setdefault("reset_contagens_por_guild", {})
    resets[str(guild_id)] = momento_iso
    salvar_dados_ausencias(dados)
    return momento_iso


def contar_respostas_evento(evento):
    respostas = evento.get("respostas", {})
    presentes = 0
    ausentes = 0
    talvez = 0

    for resposta in respostas.values():
        status = str(resposta.get("status", "")).strip().lower()
        if status == "presente":
            presentes += 1
        elif status == "ausente":
            ausentes += 1
        elif status == "talvez":
            talvez += 1

    return {
        "presentes": presentes,
        "ausentes": ausentes,
        "talvez": talvez,
    }


def evento_permite_advertencia_automatica(evento):
    return bool(evento.get("advertencia_automatica", True))


def salvar_evento_ausencia(
    event_id,
    nome_evento,
    data_evento,
    horario_evento,
    observacao,
    message_id,
    channel_id,
    criado_por_id,
    criado_por_nome,
    guild_id=None,
    advertencia_automatica=True,
    imagem_url=None,
    tipo_evento="outro",
):
    dados = carregar_dados_ausencias()
    chave_evento = str(event_id)

    dados["eventos"][chave_evento] = {
        "event_id": chave_evento,
        "nome_evento": nome_evento,
        "data": data_evento,
        "horario": horario_evento,
        "observacao": observacao,
        "tipo_evento": str(tipo_evento or "outro").strip().lower() or "outro",
        "status": "aberto",
        "message_id": message_id,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "advertencia_automatica": bool(advertencia_automatica),
        "imagem_url": str(imagem_url or "").strip() or None,
        "criado_por_id": criado_por_id,
        "criado_por_nome": criado_por_nome,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "respostas": {},
    }

    salvar_dados_ausencias(dados)
    return dados["eventos"][chave_evento]


def obter_evento_ausencia(event_id):
    dados = carregar_dados_ausencias()
    return dados.get("eventos", {}).get(str(event_id))


def _montar_resposta_evento(
    resposta_anterior,
    user_id,
    user_name,
    status,
    motivo=None,
    retorno=None,
    alterado_por_id=None,
    alterado_por_nome=None,
):
    resposta_anterior = resposta_anterior or {}
    status_anterior = str(resposta_anterior.get("status", "")).strip().lower() or None
    status_normalizado = str(status).strip().lower()
    motivo_salvo = "Não se aplica"
    retorno_salvo = "Não se aplica"

    if status_normalizado == "ausente":
        motivo_salvo = str(motivo or "").strip() or "Não informado"
        retorno_salvo = str(retorno or "").strip() or "Não informado"
    elif status_normalizado == "talvez":
        motivo_salvo = str(motivo or "").strip() or "Não informado"

    resposta = {
        "user_id": user_id,
        "user_name": user_name,
        "status": status_normalizado,
        "motivo": motivo_salvo,
        "retorno": retorno_salvo,
        "responded_at": datetime.now(FUSO_HORARIO).isoformat(),
    }

    if alterado_por_id is not None:
        resposta["alterado_por_id"] = alterado_por_id
        resposta["alterado_por_nome"] = alterado_por_nome
        resposta["alterado_em"] = datetime.now(FUSO_HORARIO).isoformat()

    return resposta, status_anterior


def _atualizar_resposta_evento(
    evento,
    user_id,
    user_name,
    status,
    motivo=None,
    retorno=None,
    alterado_por_id=None,
    alterado_por_nome=None,
):
    respostas = evento.setdefault("respostas", {})
    chave_usuario = str(user_id)
    resposta, status_anterior = _montar_resposta_evento(
        respostas.get(chave_usuario, {}),
        user_id,
        user_name,
        status,
        motivo=motivo,
        retorno=retorno,
        alterado_por_id=alterado_por_id,
        alterado_por_nome=alterado_por_nome,
    )
    respostas[chave_usuario] = resposta
    return status_anterior


def registrar_resposta_evento(event_id, user_id, user_name, status, motivo=None, retorno=None):
    dados = carregar_dados_ausencias()
    evento = dados.get("eventos", {}).get(str(event_id))
    if not evento:
        return None, None

    status_anterior = _atualizar_resposta_evento(
        evento,
        user_id,
        user_name,
        status,
        motivo=motivo,
        retorno=retorno,
    )

    salvar_dados_ausencias(dados)
    return evento, status_anterior


def atualizar_resposta_evento_staff(
    event_id,
    user_id,
    user_name,
    status,
    alterado_por_id,
    alterado_por_nome,
    motivo=None,
    retorno=None,
):
    dados = carregar_dados_ausencias()
    evento = dados.get("eventos", {}).get(str(event_id))
    if not evento:
        return None, None

    status_anterior = _atualizar_resposta_evento(
        evento,
        user_id,
        user_name,
        status,
        motivo=motivo,
        retorno=retorno,
        alterado_por_id=alterado_por_id,
        alterado_por_nome=alterado_por_nome,
    )

    salvar_dados_ausencias(dados)
    return evento, status_anterior


def remover_resposta_evento_staff(event_id, user_id, status=None):
    dados = carregar_dados_ausencias()
    evento = dados.get("eventos", {}).get(str(event_id))
    if not evento:
        return None, None

    respostas = evento.setdefault("respostas", {})
    chave_usuario = str(user_id)
    resposta = respostas.get(chave_usuario)
    if not resposta:
        return evento, None

    if status and str(resposta.get("status", "")).strip().lower() != str(status).strip().lower():
        return evento, None

    resposta_removida = respostas.pop(chave_usuario, None)
    salvar_dados_ausencias(dados)
    return evento, resposta_removida


def atualizar_sem_resposta_evento(event_id, sem_resposta):
    dados = carregar_dados_ausencias()
    evento = dados.get("eventos", {}).get(str(event_id))
    if not evento:
        return None

    evento["sem_resposta"] = max(0, int(sem_resposta or 0))
    salvar_dados_ausencias(dados)
    return evento


def salvar_mensagens_lista_staff_evento(event_id, tipo, mensagens):
    dados = carregar_dados_ausencias()
    evento = dados.get("eventos", {}).get(str(event_id))
    if not evento:
        return None

    registros = []
    for mensagem in mensagens or []:
        channel_id = getattr(getattr(mensagem, "channel", None), "id", None)
        message_id = getattr(mensagem, "id", None)
        if not channel_id or not message_id:
            continue
        registros.append(
            {
                "channel_id": int(channel_id),
                "message_id": int(message_id),
            }
        )

    listas = evento.setdefault("mensagens_lista_staff", {})
    listas[str(tipo)] = registros
    salvar_dados_ausencias(dados)
    return evento


def registrar_ausencias_automaticas_evento(evento, membros_ausentes_automaticos=None):
    if not evento:
        return []

    respostas = evento.setdefault("respostas", {})
    ausencias_registradas = []
    for membro in membros_ausentes_automaticos or []:
        user_id = membro.get("user_id")
        user_name = membro.get("user_name")
        if not user_id or not user_name:
            continue

        chave_usuario = str(user_id)
        if chave_usuario in respostas:
            continue

        _atualizar_resposta_evento(
            evento,
            user_id,
            user_name,
            "ausente",
            motivo="Não informado",
            retorno="Não informado",
        )
        respostas[chave_usuario]["registrado_automaticamente"] = True
        ausencias_registradas.append(
            {
                "user_id": user_id,
                "user_name": user_name,
            }
        )

    return ausencias_registradas


def obter_todos_eventos_ausencia(guild_ou_id=None):
    dados = carregar_dados_ausencias()
    eventos = dados.get("eventos", {})
    if not isinstance(eventos, dict):
        return []

    guild_id = extrair_guild_id(guild_ou_id)
    lista_eventos = list(eventos.values())
    if guild_id is None:
        return lista_eventos

    return [
        evento
        for evento in lista_eventos
        if not str(evento.get("guild_id", "")).strip() or str(evento.get("guild_id", "")).strip() == str(guild_id)
    ]


def ordenar_eventos_por_campo(eventos, campo):
    return sorted(
        eventos,
        key=lambda evento: str(evento.get(campo, "")),
        reverse=True,
    )


def buscar_registro_membro_eventos(user_id=None, termos_nome=None, guild_ou_id=None):
    eventos = ordenar_eventos_por_campo(obter_todos_eventos_ausencia(guild_ou_id), "created_at")
    user_id_str = str(user_id).strip() if user_id else ""
    termos = {
        str(termo or "").strip().casefold()
        for termo in (termos_nome or [])
        if str(termo or "").strip()
    }

    for evento in eventos:
        respostas = evento.get("respostas", {})
        for resposta in respostas.values():
            resposta_user_id = str(resposta.get("user_id", "")).strip()
            resposta_user_name = str(resposta.get("user_name", "")).strip()
            nome_normalizado = resposta_user_name.casefold()

            if user_id_str and resposta_user_id == user_id_str:
                return evento, resposta

            if not termos:
                continue

            if nome_normalizado in termos:
                return evento, resposta

            if any(termo in nome_normalizado for termo in termos):
                return evento, resposta

    return None, None


def encerrar_evento_ausencia(
    event_id,
    encerrado_por_id,
    encerrado_por_nome,
    membros_ausentes_automaticos=None,
    registrar_ausencias_automaticas=True,
    advertencias_aplicadas=None,
    sem_resposta=None,
):
    dados = carregar_dados_ausencias()
    evento = dados.get("eventos", {}).get(str(event_id))
    if not evento:
        return None, None, []

    status_atual = str(evento.get("status", "")).strip().lower()
    if status_atual == "encerrado":
        return evento, True, []

    if membros_ausentes_automaticos is not None:
        evento["membros_sem_resposta"] = [
            {
                "user_id": membro.get("user_id"),
                "user_name": membro.get("user_name"),
            }
            for membro in (membros_ausentes_automaticos or [])
            if membro.get("user_id") and membro.get("user_name")
        ]

    if registrar_ausencias_automaticas:
        ausencias_automaticas = registrar_ausencias_automaticas_evento(evento, membros_ausentes_automaticos)
    else:
        ausencias_automaticas = list(membros_ausentes_automaticos or [])

    evento["status"] = "encerrado"
    evento["encerrado_por_id"] = encerrado_por_id
    evento["encerrado_por_nome"] = encerrado_por_nome
    evento["encerrado_em"] = datetime.now(timezone.utc).isoformat()
    if advertencias_aplicadas is not None:
        evento["advertencias_aplicadas"] = bool(advertencias_aplicadas)
    if sem_resposta is not None:
        evento["sem_resposta"] = max(0, int(sem_resposta or 0))

    salvar_dados_ausencias(dados)
    return evento, False, ausencias_automaticas
