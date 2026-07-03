import json
import os

from config import ARQUIVO_CONQUISTAS
from services.server_config import extrair_guild_id


TIPO_EVENTO_OUTRO = "outro"

CONQUISTAS_PRESENCA = {
    "invasao": {
        "tipo": "invasao",
        "nome": "Invasor Noturno",
        "cargo_nome": "𓆩✦ Invasor Noturno ✦𓆪",
        "objetivo": 10,
        "reset_antes_ganhar": 2,
        "perda_depois_ganhar": 3,
    },
    "jogatina": {
        "tipo": "jogatina",
        "nome": "Jogador Abissal",
        "cargo_nome": "𓆩✦ Jogador Abissal ✦𓆪",
        "objetivo": 10,
        "reset_antes_ganhar": 2,
        "perda_depois_ganhar": 3,
    },
    "cinema": {
        "tipo": "cinema",
        "nome": "Cinéfilo Estelar",
        "cargo_nome": "𓆩✦ Cinéfilo Estelar ✦𓆪",
        "objetivo": 6,
        "reset_antes_ganhar": 3,
        "perda_depois_ganhar": 2,
    },
}

TIPOS_EVENTO_VALIDOS = set(CONQUISTAS_PRESENCA) | {TIPO_EVENTO_OUTRO}

MAPA_TIPOS_EVENTO = {
    "invasao": "invasao",
    "invasão": "invasao",
    "jogatina": "jogatina",
    "cinema": "cinema",
    "outro": "outro",
}

ROTULOS_TIPO_EVENTO = {
    "invasao": "Invasão",
    "jogatina": "Jogatina",
    "cinema": "Cinema",
    "outro": "Outro",
}


def normalizar_tipo_evento(valor):
    texto = str(valor or "").strip().casefold()
    if not texto:
        return TIPO_EVENTO_OUTRO
    return MAPA_TIPOS_EVENTO.get(texto, "")


def formatar_tipo_evento(tipo_evento):
    return ROTULOS_TIPO_EVENTO.get(str(tipo_evento or "").strip().lower(), "Outro")


def obter_meta_conquista(tipo_evento):
    tipo_normalizado = normalizar_tipo_evento(tipo_evento)
    return CONQUISTAS_PRESENCA.get(tipo_normalizado)


def _estado_padrao():
    return {
        "progresso": 0,
        "ausencias_seguidas": 0,
        "ausencias_com_cargo": 0,
        "possui_cargo": False,
    }


def _dados_padrao():
    return {"guilds": {}}


def carregar_dados_conquistas():
    if not os.path.exists(ARQUIVO_CONQUISTAS):
        return _dados_padrao()

    try:
        with open(ARQUIVO_CONQUISTAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError, TypeError):
        return _dados_padrao()

    if not isinstance(dados, dict):
        return _dados_padrao()

    guilds = dados.get("guilds", {})
    if not isinstance(guilds, dict):
        guilds = {}

    return {"guilds": guilds}


def salvar_dados_conquistas(dados):
    with open(ARQUIVO_CONQUISTAS, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def _obter_guild_entry(dados, guild_ou_id, criar=False):
    guild_id = extrair_guild_id(guild_ou_id)
    if guild_id is None:
        return None

    guilds = dados.setdefault("guilds", {})
    chave = str(guild_id)
    entry = guilds.get(chave)
    if entry is None and criar:
        entry = {"membros": {}, "eventos_processados": []}
        guilds[chave] = entry

    if entry is None:
        return None

    entry.setdefault("membros", {})
    entry.setdefault("eventos_processados", [])
    return entry


def obter_estado_conquista(dados, guild_ou_id, user_id, tipo_evento, criar=False):
    meta = obter_meta_conquista(tipo_evento)
    if not meta:
        return None

    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=criar)
    if guild_entry is None:
        return None

    membros = guild_entry.setdefault("membros", {})
    membro_entry = membros.get(str(user_id))
    if membro_entry is None and criar:
        membro_entry = {}
        membros[str(user_id)] = membro_entry

    if membro_entry is None:
        return _estado_padrao()

    tipo = meta["tipo"]
    estado = membro_entry.get(tipo)
    if estado is None and criar:
        estado = _estado_padrao()
        membro_entry[tipo] = estado

    if estado is None:
        return _estado_padrao()

    estado.setdefault("progresso", 0)
    estado.setdefault("ausencias_seguidas", 0)
    estado.setdefault("ausencias_com_cargo", 0)
    estado.setdefault("possui_cargo", False)
    return estado


def evento_conquista_ja_processado(dados, guild_ou_id, event_id):
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=False)
    if guild_entry is None:
        return False
    return str(event_id) in {str(item) for item in guild_entry.get("eventos_processados", [])}


def marcar_evento_conquista_processado(dados, guild_ou_id, event_id):
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=True)
    eventos = guild_entry.setdefault("eventos_processados", [])
    event_id = str(event_id)
    if event_id not in eventos:
        eventos.append(event_id)


def obter_progresso_exibicao(dados, guild_ou_id, user_id, tipo_evento, confirmado=False, possui_cargo=False):
    meta = obter_meta_conquista(tipo_evento)
    if not meta:
        return None

    estado = obter_estado_conquista(dados, guild_ou_id, user_id, tipo_evento, criar=False) or _estado_padrao()
    progresso_atual = int(estado.get("progresso", 0) or 0)
    possui_cargo_salvo = bool(estado.get("possui_cargo"))
    possui_cargo = bool(possui_cargo or possui_cargo_salvo)

    if confirmado or possui_cargo:
        progresso = max(progresso_atual, meta["objetivo"] if possui_cargo else progresso_atual)
    else:
        progresso = min(meta["objetivo"], progresso_atual + 1)

    return {
        "progresso": progresso,
        "objetivo": meta["objetivo"],
        "nome": meta["nome"],
        "cargo_nome": meta["cargo_nome"],
        "tipo": meta["tipo"],
    }
