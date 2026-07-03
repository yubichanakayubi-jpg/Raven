from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from config import FUSO_HORARIO


ARQUIVO_POLLS = "dados_polls.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOCK_POLLS = threading.RLock()


def _caminho_polls():
    return PROJECT_ROOT / ARQUIVO_POLLS


def _dados_base():
    return {
        "proximo_id": 1,
        "polls": {},
    }


def _normalizar_dados(dados):
    if not isinstance(dados, dict):
        return _dados_base()

    dados.setdefault("proximo_id", 1)
    dados.setdefault("polls", {})
    if not isinstance(dados["polls"], dict):
        dados["polls"] = {}

    return dados


def carregar_dados_polls():
    caminho = _caminho_polls()
    if not caminho.exists():
        return _dados_base()

    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            return _normalizar_dados(json.load(arquivo))
    except (json.JSONDecodeError, OSError, TypeError) as erro:
        print(f"[POLLS] Erro ao carregar dados de enquetes: {erro!r}")
        return _dados_base()


def salvar_dados_polls(dados):
    caminho = _caminho_polls()
    temporario = caminho.with_suffix(f"{caminho.suffix}.tmp")
    dados = _normalizar_dados(dados)

    try:
        with temporario.open("w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        os.replace(temporario, caminho)
    except OSError as erro:
        print(f"[POLLS] Erro ao salvar dados de enquetes: {erro!r}")
        try:
            if temporario.exists():
                temporario.unlink()
        except OSError:
            pass


def gerar_id_poll():
    with _LOCK_POLLS:
        dados = carregar_dados_polls()
        proximo_id = int(dados.get("proximo_id") or 1)
        dados["proximo_id"] = proximo_id + 1
        salvar_dados_polls(dados)
        return f"poll-{proximo_id:04d}"


def salvar_poll(registro):
    with _LOCK_POLLS:
        dados = carregar_dados_polls()
        poll_id = str(registro["poll_id"])
        dados["polls"][poll_id] = deepcopy(registro)
        salvar_dados_polls(dados)
        return deepcopy(registro)


def obter_poll(poll_id):
    with _LOCK_POLLS:
        dados = carregar_dados_polls()
        registro = dados["polls"].get(str(poll_id))
        return deepcopy(registro) if registro else None


def obter_poll_por_message_id(message_id):
    if not message_id:
        return None

    message_id = str(message_id)
    with _LOCK_POLLS:
        dados = carregar_dados_polls()
        for registro in dados["polls"].values():
            if str(registro.get("message_id") or "") == message_id:
                return deepcopy(registro)
    return None


def listar_polls_abertas():
    with _LOCK_POLLS:
        dados = carregar_dados_polls()
        return [
            deepcopy(registro)
            for registro in dados["polls"].values()
            if registro.get("status") == "aberta" and registro.get("message_id")
        ]


def listar_polls_com_mensagem():
    with _LOCK_POLLS:
        dados = carregar_dados_polls()
        return [
            deepcopy(registro)
            for registro in dados["polls"].values()
            if registro.get("message_id")
        ]


def atualizar_poll(poll_id, **alteracoes):
    with _LOCK_POLLS:
        dados = carregar_dados_polls()
        poll_id = str(poll_id)
        registro = dados["polls"].get(poll_id)
        if not registro:
            return None

        registro.update(alteracoes)
        registro["atualizado_em"] = datetime.now(FUSO_HORARIO).isoformat()
        dados["polls"][poll_id] = registro
        salvar_dados_polls(dados)
        return deepcopy(registro)


def registrar_voto_poll(poll_id, user_id, opcao_id):
    with _LOCK_POLLS:
        dados = carregar_dados_polls()
        poll_id = str(poll_id)
        registro = dados["polls"].get(poll_id)
        if not registro:
            return None, False, "Enquete não encontrada."

        if registro.get("status") != "aberta":
            return deepcopy(registro), False, "Essa enquete não está aberta para votação."

        opcoes_validas = {str(opcao.get("id")) for opcao in registro.get("opcoes", [])}
        opcao_id = str(opcao_id)
        if opcao_id not in opcoes_validas:
            return deepcopy(registro), False, "Opção inválida para esta enquete."

        votos = registro.setdefault("votos", {})
        user_id = str(user_id)
        voto_anterior = votos.get(user_id)
        votos[user_id] = opcao_id
        registro["atualizado_em"] = datetime.now(FUSO_HORARIO).isoformat()
        dados["polls"][poll_id] = registro
        salvar_dados_polls(dados)
        return deepcopy(registro), voto_anterior is not None and voto_anterior != opcao_id, None
