import json
from copy import deepcopy
from pathlib import Path

from config import ARQUIVO_CONFIG_SERVIDORES, SERVER_CONFIG_DEFAULTS


_CACHE = None
_CACHE_MTIME = None


def _caminho_config_servidores():
    return Path(__file__).resolve().parent.parent / ARQUIVO_CONFIG_SERVIDORES


def _dados_padrao():
    return {"_default": deepcopy(SERVER_CONFIG_DEFAULTS)}


def _normalizar_secao_config(secao):
    base = deepcopy(SERVER_CONFIG_DEFAULTS)
    if not isinstance(secao, dict):
        return base

    for chave, valor in secao.items():
        if chave not in base:
            continue
        base[chave] = deepcopy(valor)

    return base


def carregar_configs_servidores():
    global _CACHE, _CACHE_MTIME

    caminho = _caminho_config_servidores()
    try:
        mtime = caminho.stat().st_mtime
    except OSError:
        mtime = None

    if _CACHE is not None and _CACHE_MTIME == mtime:
        return deepcopy(_CACHE)

    dados = _dados_padrao()
    if caminho.exists():
        try:
            with caminho.open("r", encoding="utf-8") as arquivo:
                bruto = json.load(arquivo)
        except (json.JSONDecodeError, OSError, TypeError):
            bruto = {}

        if isinstance(bruto, dict):
            if "_default" in bruto:
                dados["_default"] = _normalizar_secao_config(bruto.get("_default"))

            for guild_id, secao in bruto.items():
                if guild_id == "_default":
                    continue
                dados[str(guild_id)] = _normalizar_secao_config(secao)

    _CACHE = deepcopy(dados)
    _CACHE_MTIME = mtime
    return dados


def salvar_configs_servidores(dados):
    global _CACHE, _CACHE_MTIME

    caminho = _caminho_config_servidores()
    dados_salvos = {}

    for chave, valor in (dados or {}).items():
        if chave == "_default":
            dados_salvos["_default"] = _normalizar_secao_config(valor)
            continue
        dados_salvos[str(chave)] = _normalizar_secao_config(valor)

    if "_default" not in dados_salvos:
        dados_salvos["_default"] = deepcopy(SERVER_CONFIG_DEFAULTS)

    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(dados_salvos, arquivo, ensure_ascii=False, indent=4)

    _CACHE = deepcopy(dados_salvos)
    try:
        _CACHE_MTIME = caminho.stat().st_mtime
    except OSError:
        _CACHE_MTIME = None


def garantir_arquivo_config_servidores():
    caminho = _caminho_config_servidores()
    if caminho.exists():
        return
    salvar_configs_servidores(_dados_padrao())


def extrair_guild_id(guild_ou_id=None):
    if guild_ou_id is None:
        return None

    if isinstance(guild_ou_id, int):
        return guild_ou_id

    guild = getattr(guild_ou_id, "guild", None)
    if guild is not None and getattr(guild, "id", None):
        return guild.id

    if getattr(guild_ou_id, "id", None) and getattr(guild_ou_id, "name", None) is not None:
        return guild_ou_id.id

    return None


def obter_config_servidor(guild_ou_id=None):
    dados = carregar_configs_servidores()
    base = _normalizar_secao_config(dados.get("_default", {}))
    guild_id = extrair_guild_id(guild_ou_id)
    if guild_id is None:
        return base

    config_especifica = dados.get(str(guild_id))
    if not isinstance(config_especifica, dict):
        return base

    for chave, valor in config_especifica.items():
        if chave not in base:
            continue
        base[chave] = deepcopy(valor)

    return base


def obter_valor_config(guild_ou_id, chave, padrao=None):
    config = obter_config_servidor(guild_ou_id)
    return deepcopy(config.get(chave, padrao))


garantir_arquivo_config_servidores()
