import json
import os
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

from config import ARQUIVO_XP, FUSO_HORARIO
from services.server_config import extrair_guild_id, obter_valor_config


XP_ROLE_THRESHOLDS = (
    ("corvo_noturno", 20000),
    ("corvo_lunar", 50000),
    ("corvo_celestial", 100000),
)

LINK_RE = re.compile(r"^(https?://\S+|www\.\S+)$", re.IGNORECASE)
WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def _dados_padrao():
    return {"guilds": {}}


def _estado_usuario_padrao():
    return {
        "xp_total": 0,
        "xp_diario": 0,
        "data_xp_diario": "",
        "ultimo_xp_geral": None,
        "ultimo_xp_midia": None,
        "ultimas_mensagens": [],
        "cargo_atual": None,
        "ultimo_aviso_limite_data": "",
    }


def carregar_dados_xp():
    if not os.path.exists(ARQUIVO_XP):
        return _dados_padrao()

    try:
        with open(ARQUIVO_XP, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, TypeError, json.JSONDecodeError):
        return _dados_padrao()

    if not isinstance(dados, dict):
        return _dados_padrao()

    guilds = dados.get("guilds", {})
    if not isinstance(guilds, dict):
        guilds = {}
    return {"guilds": guilds}


def salvar_dados_xp(dados):
    with open(ARQUIVO_XP, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def _obter_guild_entry(dados, guild_ou_id, criar=False):
    guild_id = extrair_guild_id(guild_ou_id)
    if guild_id is None:
        return None

    guilds = dados.setdefault("guilds", {})
    chave = str(guild_id)
    entry = guilds.get(chave)
    if entry is None and criar:
        entry = {"usuarios": {}, "message_awards": {}}
        guilds[chave] = entry

    if entry is None:
        return None

    entry.setdefault("usuarios", {})
    entry.setdefault("message_awards", {})
    return entry


def obter_estado_xp_usuario(dados, guild_ou_id, user_id, criar=False):
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=criar)
    if guild_entry is None:
        return None

    usuarios = guild_entry.setdefault("usuarios", {})
    chave = str(user_id)
    estado = usuarios.get(chave)
    if estado is None and criar:
        estado = _estado_usuario_padrao()
        usuarios[chave] = estado

    if estado is None:
        return _estado_usuario_padrao()

    for campo, valor in _estado_usuario_padrao().items():
        estado.setdefault(campo, valor if not isinstance(valor, list) else list(valor))
    return estado


def _hoje_local(agora=None):
    agora = agora or datetime.now(FUSO_HORARIO)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=FUSO_HORARIO)
    return agora.astimezone(FUSO_HORARIO).strftime("%Y-%m-%d")


def resetar_xp_diario_se_preciso(estado, agora=None):
    hoje = _hoje_local(agora)
    if str(estado.get("data_xp_diario", "")) != hoje:
        estado["xp_diario"] = 0
        estado["data_xp_diario"] = hoje
    return hoje


def normalizar_texto_xp(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def contar_palavras(texto):
    return len(WORD_RE.findall(str(texto or "")))


def _normalizar_ids_config(valor):
    if valor is None:
        return set()
    if isinstance(valor, (list, tuple, set)):
        resultado = set()
        for item in valor:
            try:
                resultado.add(int(item))
            except (TypeError, ValueError):
                continue
        return resultado
    try:
        return {int(valor)}
    except (TypeError, ValueError):
        return set()


def tem_anexo_midia(message):
    return bool(getattr(message, "attachments", None))


def texto_eh_link_somente(texto):
    texto = str(texto or "").strip()
    if not texto:
        return False
    partes = texto.split()
    return all(LINK_RE.match(parte) for parte in partes)


def texto_sem_sentido_ou_emoji(texto):
    texto = str(texto or "").strip()
    if not texto:
        return True
    return not any(ch.isalnum() for ch in texto)


def texto_parece_flood(texto):
    normalizado = re.sub(r"\s+", "", normalizar_texto_xp(texto))
    if len(normalizado) < 8:
        return False
    if len(set(normalizado)) <= 2:
        return True
    char_mais_comum = max(normalizado.count(ch) for ch in set(normalizado))
    return (char_mais_comum / max(1, len(normalizado))) >= 0.85


def mensagem_repetida(normalizado, historico):
    if not normalizado or not historico:
        return False

    for antiga in historico[-6:]:
        antiga = str(antiga or "").strip()
        if not antiga:
            continue
        if normalizado == antiga:
            return True
        if len(normalizado) >= 10 and len(antiga) >= 10:
            similaridade = SequenceMatcher(None, normalizado, antiga).ratio()
            if similaridade >= 0.92:
                return True
    return False


def mensagem_valida_geral(message):
    texto = str(getattr(message, "content", "") or "").strip()
    if not texto:
        return False, None
    if texto.startswith("!"):
        return False, None
    if texto_eh_link_somente(texto):
        return False, None
    if texto_sem_sentido_ou_emoji(texto):
        return False, None
    if texto_parece_flood(texto):
        return False, None

    palavras = contar_palavras(texto)
    if palavras < 4 and len(texto) < 20:
        return False, None

    normalizado = normalizar_texto_xp(texto)
    return True, normalizado


def legenda_valida_midia(texto):
    texto = str(texto or "").strip()
    if not texto:
        return False
    if texto_eh_link_somente(texto):
        return False
    if texto_sem_sentido_ou_emoji(texto):
        return False
    if texto_parece_flood(texto):
        return False
    return contar_palavras(texto) >= 3 or len(texto) >= 20


def calcular_xp_mensagem(message, guild):
    geral_ids = _normalizar_ids_config(obter_valor_config(guild, "XP_GENERAL_CHANNEL_IDS", []))
    media_ids = _normalizar_ids_config(obter_valor_config(guild, "XP_MEDIA_CHANNEL_IDS", []))
    channel_id = getattr(getattr(message, "channel", None), "id", None)

    if channel_id in geral_ids:
        valida, normalizado = mensagem_valida_geral(message)
        if not valida:
            return None

        palavras = contar_palavras(message.content)
        xp = 25 if palavras >= 10 else 15
        if getattr(message, "reference", None) and getattr(message.reference, "message_id", None):
            xp += 10
        return {
            "origem": "geral",
            "xp_base": xp,
            "normalizado": normalizado,
            "cooldown_field": "ultimo_xp_geral",
            "cooldown_seconds": int(obter_valor_config(guild, "XP_GENERAL_COOLDOWN_SECONDS", 60)),
        }

    if channel_id in media_ids and tem_anexo_midia(message):
        legenda = str(getattr(message, "content", "") or "").strip()
        normalizado = normalizar_texto_xp(legenda) if legenda else ""
        xp = 25 if legenda_valida_midia(legenda) else 10
        return {
            "origem": "midia",
            "xp_base": xp,
            "normalizado": normalizado,
            "cooldown_field": "ultimo_xp_midia",
            "cooldown_seconds": int(obter_valor_config(guild, "XP_MEDIA_COOLDOWN_SECONDS", 3600)),
        }

    return None


def obter_role_key_por_xp(xp_total):
    chave = None
    for role_key, meta in XP_ROLE_THRESHOLDS:
        if int(xp_total) >= int(meta):
            chave = role_key
    return chave


def obter_proxima_meta_xp(xp_total):
    for role_key, meta in XP_ROLE_THRESHOLDS:
        if int(xp_total) < int(meta):
            return role_key, meta
    return None, None


def registrar_xp_message(dados, guild, message):
    guild_entry = _obter_guild_entry(dados, guild, criar=True)
    estado = obter_estado_xp_usuario(dados, guild, message.author.id, criar=True)
    hoje = resetar_xp_diario_se_preciso(estado, message.created_at.astimezone(FUSO_HORARIO))

    info = calcular_xp_mensagem(message, guild)
    if info is None:
        return {"ganhou": False, "motivo": "canal_ou_formato_invalido"}

    award_exists = guild_entry.setdefault("message_awards", {}).get(str(message.id))
    if award_exists:
        return {"ganhou": False, "motivo": "mensagem_ja_processada"}

    normalizado = info.get("normalizado", "")
    if normalizado and mensagem_repetida(normalizado, estado.get("ultimas_mensagens", [])):
        return {"ganhou": False, "motivo": "mensagem_repetida"}

    ultimo_iso = estado.get(info["cooldown_field"])
    if ultimo_iso:
        try:
            ultimo_dt = datetime.fromisoformat(str(ultimo_iso).replace("Z", "+00:00"))
            if ultimo_dt.tzinfo is None:
                ultimo_dt = ultimo_dt.replace(tzinfo=FUSO_HORARIO)
            ultimo_dt = ultimo_dt.astimezone(FUSO_HORARIO)
            agora_dt = message.created_at.astimezone(FUSO_HORARIO)
            if (agora_dt - ultimo_dt).total_seconds() < info["cooldown_seconds"]:
                return {"ganhou": False, "motivo": "cooldown"}
        except ValueError:
            pass

    limite_diario = int(obter_valor_config(guild, "XP_DAILY_LIMIT", 700))
    restante = max(0, limite_diario - int(estado.get("xp_diario", 0) or 0))
    if restante <= 0:
        return {"ganhou": False, "motivo": "limite_diario", "limite_data": hoje}

    xp_ganho = min(restante, int(info["xp_base"]))
    if xp_ganho <= 0:
        return {"ganhou": False, "motivo": "limite_diario", "limite_data": hoje}

    xp_total_antes = int(estado.get("xp_total", 0) or 0)
    estado["xp_total"] = xp_total_antes + xp_ganho
    estado["xp_diario"] = int(estado.get("xp_diario", 0) or 0) + xp_ganho
    estado["data_xp_diario"] = hoje
    estado[info["cooldown_field"]] = message.created_at.astimezone(FUSO_HORARIO).isoformat()

    if normalizado:
        historico = list(estado.get("ultimas_mensagens", []))
        historico.append(normalizado)
        estado["ultimas_mensagens"] = historico[-8:]

    role_key_anterior = estado.get("cargo_atual")
    role_key_novo = obter_role_key_por_xp(estado["xp_total"])
    estado["cargo_atual"] = role_key_novo

    guild_entry.setdefault("message_awards", {})[str(message.id)] = {
        "user_id": int(message.author.id),
        "xp": int(xp_ganho),
        "origem": info["origem"],
        "data": hoje,
        "normalizado": normalizado,
    }

    limite_atingido = int(estado["xp_diario"]) >= limite_diario
    aviso_limite_deve_enviar = False
    if limite_atingido and str(estado.get("ultimo_aviso_limite_data", "")) != hoje:
        estado["ultimo_aviso_limite_data"] = hoje
        aviso_limite_deve_enviar = True

    return {
        "ganhou": True,
        "xp_ganho": xp_ganho,
        "xp_total": int(estado["xp_total"]),
        "xp_diario": int(estado["xp_diario"]),
        "origem": info["origem"],
        "role_key_anterior": role_key_anterior,
        "role_key_novo": role_key_novo,
        "promoveu": role_key_novo != role_key_anterior and role_key_novo is not None,
        "limite_atingido": limite_atingido,
        "enviar_aviso_limite": aviso_limite_deve_enviar,
    }


def remover_xp_por_mensagem(dados, guild_ou_id, message_id):
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=False)
    if guild_entry is None:
        return {"removeu": False, "motivo": "guild_invalida"}

    award = guild_entry.setdefault("message_awards", {}).pop(str(message_id), None)
    if not award:
        return {"removeu": False, "motivo": "mensagem_sem_xp"}

    user_id = award.get("user_id")
    estado = obter_estado_xp_usuario(dados, guild_ou_id, user_id, criar=True)
    hoje = _hoje_local()
    resetar_xp_diario_se_preciso(estado)

    xp = int(award.get("xp", 0) or 0)
    estado["xp_total"] = max(0, int(estado.get("xp_total", 0) or 0) - xp)
    if str(award.get("data", "")) == hoje:
        estado["xp_diario"] = max(0, int(estado.get("xp_diario", 0) or 0) - xp)

    role_key_anterior = estado.get("cargo_atual")
    role_key_novo = obter_role_key_por_xp(estado["xp_total"])
    estado["cargo_atual"] = role_key_novo

    return {
        "removeu": True,
        "user_id": int(user_id),
        "xp_removido": xp,
        "role_key_anterior": role_key_anterior,
        "role_key_novo": role_key_novo,
        "rebaixou": role_key_novo != role_key_anterior,
    }


def adicionar_xp_manual(dados, guild_ou_id, user_id, quantidade):
    estado = obter_estado_xp_usuario(dados, guild_ou_id, user_id, criar=True)
    resetar_xp_diario_se_preciso(estado)
    role_key_anterior = estado.get("cargo_atual")
    estado["xp_total"] = max(0, int(estado.get("xp_total", 0) or 0) + int(quantidade))
    estado["cargo_atual"] = obter_role_key_por_xp(estado["xp_total"])
    return {
        "xp_total": int(estado["xp_total"]),
        "role_key_anterior": role_key_anterior,
        "role_key_novo": estado.get("cargo_atual"),
    }


def remover_xp_manual(dados, guild_ou_id, user_id, quantidade):
    return adicionar_xp_manual(dados, guild_ou_id, user_id, -abs(int(quantidade)))


def resetar_xp_usuario(dados, guild_ou_id, user_id):
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=True)
    estado = obter_estado_xp_usuario(dados, guild_ou_id, user_id, criar=True)
    estado.update(_estado_usuario_padrao())
    awards = guild_entry.setdefault("message_awards", {})
    remover = [message_id for message_id, award in awards.items() if int(award.get("user_id", 0) or 0) == int(user_id)]
    for message_id in remover:
        awards.pop(message_id, None)
    return estado


def ranking_xp(dados, guild_ou_id, limite=10):
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=False)
    if guild_entry is None:
        return []

    ranking = []
    for user_id, estado in (guild_entry.get("usuarios") or {}).items():
        try:
            xp_total = int(estado.get("xp_total", 0) or 0)
        except (TypeError, ValueError):
            xp_total = 0
        ranking.append((int(user_id), xp_total))

    ranking.sort(key=lambda item: item[1], reverse=True)
    return ranking[:limite]
