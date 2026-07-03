import json
import os
from datetime import datetime

from config import ARQUIVO_ADVERTENCIAS, FUSO_HORARIO


def carregar_dados_advertencias():
    dados_padrao = {"membros": {}}

    if not os.path.exists(ARQUIVO_ADVERTENCIAS):
        return dados_padrao

    try:
        with open(ARQUIVO_ADVERTENCIAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError, TypeError):
        return dados_padrao

    if not isinstance(dados, dict):
        return dados_padrao

    membros = dados.get("membros", {})
    if not isinstance(membros, dict):
        membros = {}

    return {"membros": membros}


def salvar_dados_advertencias(dados):
    with open(ARQUIVO_ADVERTENCIAS, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def obter_advertencias_ativas(user_id):
    dados = carregar_dados_advertencias()
    registro = dados.get("membros", {}).get(str(user_id))
    if not registro:
        return 0, None

    try:
        quantidade = int(registro.get("quantidade_advertencias") or 0)
    except (TypeError, ValueError):
        quantidade = 0

    if str(registro.get("status", "")).strip().lower() != "ativa":
        return 0, registro

    return max(0, quantidade), registro


def salvar_mensagem_advertencia(user_id, channel_id, message_id):
    dados = carregar_dados_advertencias()
    registro = dados.setdefault("membros", {}).get(str(user_id))
    if not registro:
        return False

    registro["advertencia_channel_id"] = int(channel_id)
    registro["advertencia_message_id"] = int(message_id)

    historico = _obter_historico(registro)
    for item in reversed(historico):
        if str(item.get("tipo", "")).strip().lower() == "advertencia":
            item["advertencia_channel_id"] = int(channel_id)
            item["advertencia_message_id"] = int(message_id)
            break

    salvar_dados_advertencias(dados)
    return True


def obter_advertencia_por_mensagem(message_id):
    dados = carregar_dados_advertencias()
    mensagem_id = str(message_id)

    for registro in dados.get("membros", {}).values():
        if str(registro.get("advertencia_message_id") or "") == mensagem_id:
            return registro

    return None


def confirmar_visualizacao_advertencia(user_id, message_id):
    dados = carregar_dados_advertencias()
    registro = dados.get("membros", {}).get(str(user_id))
    if not registro:
        return None, False

    if str(registro.get("advertencia_message_id") or "") != str(message_id):
        return registro, False

    visualizada_em = _agora_iso()
    registro["visualizada_pelo_membro"] = True
    registro["visualizada_em"] = visualizada_em

    historico = _obter_historico(registro)
    for item in reversed(historico):
        if str(item.get("tipo", "")).strip().lower() != "advertencia":
            continue
        if str(item.get("advertencia_message_id") or "") != str(message_id):
            continue

        item["visualizada_pelo_membro"] = True
        item["visualizada_em"] = visualizada_em
        break

    salvar_dados_advertencias(dados)
    return registro, True


def _agora_iso():
    return datetime.now(FUSO_HORARIO).isoformat()


def _obter_historico(registro):
    historico = registro.get("historico", [])
    if not isinstance(historico, list):
        historico = []
    registro["historico"] = historico
    return historico


def aplicar_advertencia_automatica(
    user_id,
    user_name,
    event_id,
    nome_evento,
    data_evento,
    motivo="Não justificou ausência em convocação.",
):
    dados = carregar_dados_advertencias()
    membros = dados.setdefault("membros", {})
    chave_usuario = str(user_id)

    registro = membros.get(chave_usuario, {})
    historico = _obter_historico(registro)
    if any(
        str(item.get("tipo", "")).strip().lower() == "advertencia"
        and str(item.get("event_id", "")).strip() == str(event_id)
        for item in historico
    ):
        return registro or None, False

    quantidade_atual = 0
    if str(registro.get("status", "")).strip().lower() == "ativa":
        try:
            quantidade_atual = int(registro.get("quantidade_advertencias") or 0)
        except (TypeError, ValueError):
            quantidade_atual = 0

    quantidade_nova = min(5, max(0, quantidade_atual) + 1)
    aplicada_em = _agora_iso()

    registro.update(
        {
            "user_id": user_id,
            "user_name": user_name,
            "quantidade_advertencias": quantidade_nova,
            "motivo": motivo,
            "event_id": str(event_id),
            "nome_evento": nome_evento,
            "data_evento": data_evento,
            "aplicada_em": aplicada_em,
            "status": "ativa",
        }
    )
    registro.pop("visualizada_pelo_membro", None)
    registro.pop("visualizada_em", None)
    historico.append(
        {
            "tipo": "advertencia",
            "user_id": user_id,
            "user_name": user_name,
            "quantidade_advertencias": quantidade_nova,
            "motivo": motivo,
            "event_id": str(event_id),
            "nome_evento": nome_evento,
            "data_evento": data_evento,
            "aplicada_em": aplicada_em,
            "status": "ativa",
        }
    )

    membros[chave_usuario] = registro
    salvar_dados_advertencias(dados)
    return registro, True


def adicionar_advertencia_manual(
    user_id,
    user_name,
    staff_id,
    staff_name,
    quantidade=1,
    motivo="Advertencia manual aplicada pela staff.",
    nome_evento=None,
    data_evento=None,
):
    dados = carregar_dados_advertencias()
    membros = dados.setdefault("membros", {})
    chave_usuario = str(user_id)

    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        quantidade = 1
    quantidade = min(5, max(1, quantidade))

    registro = membros.get(chave_usuario, {})
    historico = _obter_historico(registro)

    quantidade_atual = 0
    if str(registro.get("status", "")).strip().lower() == "ativa":
        try:
            quantidade_atual = int(registro.get("quantidade_advertencias") or 0)
        except (TypeError, ValueError):
            quantidade_atual = 0

    quantidade_atual = max(0, quantidade_atual)
    quantidade_adicionada = min(quantidade, max(0, 5 - quantidade_atual))
    if quantidade_adicionada <= 0:
        return registro or None, False, 0

    quantidade_nova = min(5, quantidade_atual + quantidade_adicionada)
    aplicada_em = _agora_iso()
    nome_evento = str(nome_evento or "").strip() or "Advertencia manual"
    data_evento = str(data_evento or "").strip() or datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y")
    event_id = f"manual-{user_id}-{aplicada_em}"

    registro.update(
        {
            "user_id": user_id,
            "user_name": user_name,
            "quantidade_advertencias": quantidade_nova,
            "motivo": motivo,
            "event_id": event_id,
            "nome_evento": nome_evento,
            "data_evento": data_evento,
            "aplicada_em": aplicada_em,
            "status": "ativa",
        }
    )
    registro.pop("visualizada_pelo_membro", None)
    registro.pop("visualizada_em", None)
    historico.append(
        {
            "tipo": "advertencia",
            "origem": "manual",
            "user_id": user_id,
            "user_name": user_name,
            "quantidade_adicionada": quantidade_adicionada,
            "quantidade_advertencias": quantidade_nova,
            "motivo": motivo,
            "event_id": event_id,
            "nome_evento": nome_evento,
            "data_evento": data_evento,
            "aplicada_em": aplicada_em,
            "aplicada_por_id": staff_id,
            "aplicada_por_nome": staff_name,
            "status": "ativa",
        }
    )

    membros[chave_usuario] = registro
    salvar_dados_advertencias(dados)
    return registro, True, quantidade_adicionada


def remover_advertencia_manual(
    user_id,
    user_name,
    staff_id,
    staff_name,
    quantidade=1,
    motivo="Advertencia removida manualmente pela staff.",
):
    dados = carregar_dados_advertencias()
    membros = dados.get("membros", {})
    registro = membros.get(str(user_id))
    if not registro:
        return None, False, 0

    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        quantidade = 1
    quantidade = min(5, max(1, quantidade))

    try:
        quantidade_atual = int(registro.get("quantidade_advertencias") or 0)
    except (TypeError, ValueError):
        quantidade_atual = 0

    if str(registro.get("status", "")).strip().lower() != "ativa" or quantidade_atual <= 0:
        return registro, False, 0

    quantidade_removida = min(quantidade, quantidade_atual)
    quantidade_nova = max(0, quantidade_atual - quantidade_removida)
    removida_em = _agora_iso()

    registro["user_id"] = user_id
    registro["user_name"] = user_name
    registro["quantidade_advertencias"] = quantidade_nova
    registro["status"] = "zerada" if quantidade_nova <= 0 else "ativa"
    registro["removida_em"] = removida_em
    registro["removida_por"] = "comando_manual"

    historico = _obter_historico(registro)
    historico.append(
        {
            "tipo": "remocao_manual",
            "user_id": user_id,
            "user_name": user_name,
            "quantidade_removida": quantidade_removida,
            "quantidade_advertencias": quantidade_nova,
            "motivo": motivo,
            "removida_em": removida_em,
            "removida_por_id": staff_id,
            "removida_por_nome": staff_name,
            "status": registro["status"],
        }
    )

    salvar_dados_advertencias(dados)
    return registro, True, quantidade_removida


def zerar_advertencia_por_resposta(
    user_id,
    user_name,
    event_id,
    nome_evento,
    data_evento,
    resposta_marcada,
):
    if str(resposta_marcada or "").strip().lower() != "presente":
        return None, False

    dados = carregar_dados_advertencias()
    membros = dados.get("membros", {})
    registro = membros.get(str(user_id))
    if not registro:
        return None, False

    try:
        quantidade_atual = int(registro.get("quantidade_advertencias") or 0)
    except (TypeError, ValueError):
        quantidade_atual = 0

    if str(registro.get("status", "")).strip().lower() != "ativa" or quantidade_atual <= 0:
        return registro, False

    zerada_em = _agora_iso()
    registro["user_id"] = user_id
    registro["user_name"] = user_name
    registro["quantidade_advertencias"] = 0
    registro["status"] = "zerada"
    registro["zerada_em"] = zerada_em
    registro["zerada_por"] = "resposta_em_evento"

    historico = _obter_historico(registro)
    historico.append(
        {
            "tipo": "zerada",
            "user_id": user_id,
            "user_name": user_name,
            "event_id": str(event_id),
            "nome_evento": nome_evento,
            "data_evento": data_evento,
            "resposta_marcada": resposta_marcada,
            "zerada_em": zerada_em,
            "zerada_por": "resposta_em_evento",
            "status": "zerada",
        }
    )

    salvar_dados_advertencias(dados)
    return registro, True
