import json
import os
from copy import deepcopy
from datetime import datetime

from config import FUSO_HORARIO


ARQUIVO_CANDIDATURAS = "dados_candidaturas.json"


def _dados_base():
    return {
        "proximo_id": 1,
        "candidaturas": {},
    }


def carregar_dados_candidaturas():
    if not os.path.exists(ARQUIVO_CANDIDATURAS):
        return _dados_base()

    try:
        with open(ARQUIVO_CANDIDATURAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError):
        return _dados_base()

    if not isinstance(dados, dict):
        return _dados_base()

    dados.setdefault("proximo_id", 1)
    dados.setdefault("candidaturas", {})
    if not isinstance(dados["candidaturas"], dict):
        dados["candidaturas"] = {}
    return dados


def salvar_dados_candidaturas(dados):
    temporario = f"{ARQUIVO_CANDIDATURAS}.tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO_CANDIDATURAS)


def gerar_id_candidatura():
    dados = carregar_dados_candidaturas()
    proximo_id = int(dados.get("proximo_id") or 1)
    dados["proximo_id"] = proximo_id + 1
    salvar_dados_candidaturas(dados)
    return f"cand-{proximo_id:04d}"


def salvar_candidatura(registro):
    dados = carregar_dados_candidaturas()
    candidatura_id = str(registro["id"])
    dados["candidaturas"][candidatura_id] = deepcopy(registro)
    salvar_dados_candidaturas(dados)
    return deepcopy(registro)


def obter_candidatura(candidatura_id):
    dados = carregar_dados_candidaturas()
    registro = dados["candidaturas"].get(str(candidatura_id))
    return deepcopy(registro) if registro else None


def obter_candidatura_por_message_id(message_id):
    if not message_id:
        return None

    message_id = str(message_id)
    dados = carregar_dados_candidaturas()
    for registro in dados["candidaturas"].values():
        if str(registro.get("message_id") or "") == message_id:
            return deepcopy(registro)
    return None


def atualizar_candidatura(candidatura_id, **alteracoes):
    dados = carregar_dados_candidaturas()
    candidatura_id = str(candidatura_id)
    registro = dados["candidaturas"].get(candidatura_id)
    if not registro:
        return None

    registro.update(alteracoes)
    registro["atualizado_em"] = datetime.now(FUSO_HORARIO).isoformat()
    dados["candidaturas"][candidatura_id] = registro
    salvar_dados_candidaturas(dados)
    return deepcopy(registro)
