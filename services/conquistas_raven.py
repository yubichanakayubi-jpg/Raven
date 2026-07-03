from datetime import datetime, timedelta

from config import FUSO_HORARIO
from services.conquistas_presenca import carregar_dados_conquistas, salvar_dados_conquistas
from services.server_config import extrair_guild_id


CONQUISTA_FA_DO_RAVEN = {
    "tipo": "fa_do_raven",
    "nome": "Fã do Raven",
    "cargo_nome": "𓆩✦ Fã do Raven ✦𓆪",
    "objetivo": 35,
    "faltas_reset": 5,
    "faltas_perda": 7,
    "prazo_horas": 1,
}


def _estado_padrao_fa_do_raven():
    return {
        "progresso": 0,
        "objetivo": CONQUISTA_FA_DO_RAVEN["objetivo"],
        "faltas_antes_cargo": 0,
        "faltas_com_cargo": 0,
        "possui_cargo": False,
        "perguntas_respondidas": [],
        "ultima_resposta_valida": None,
    }


def _obter_guild_entry(dados, guild_ou_id, criar=False):
    guild_id = extrair_guild_id(guild_ou_id)
    if guild_id is None:
        return None

    guilds = dados.setdefault("guilds", {})
    chave = str(guild_id)
    entry = guilds.get(chave)
    if entry is None and criar:
        entry = {"membros": {}, "eventos_processados": [], "perguntas_diarias": {}}
        guilds[chave] = entry

    if entry is None:
        return None

    entry.setdefault("membros", {})
    entry.setdefault("eventos_processados", [])
    entry.setdefault("perguntas_diarias", {})
    return entry


def obter_estado_fa_do_raven(dados, guild_ou_id, user_id, criar=False):
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=criar)
    if guild_entry is None:
        return None

    membros = guild_entry.setdefault("membros", {})
    membro_entry = membros.get(str(user_id))
    if membro_entry is None and criar:
        membro_entry = {}
        membros[str(user_id)] = membro_entry

    if membro_entry is None:
        return _estado_padrao_fa_do_raven()

    estado = membro_entry.get(CONQUISTA_FA_DO_RAVEN["tipo"])
    if estado is None and criar:
        estado = _estado_padrao_fa_do_raven()
        membro_entry[CONQUISTA_FA_DO_RAVEN["tipo"]] = estado

    if estado is None:
        return _estado_padrao_fa_do_raven()

    estado.setdefault("progresso", 0)
    estado.setdefault("objetivo", CONQUISTA_FA_DO_RAVEN["objetivo"])
    estado.setdefault("faltas_antes_cargo", 0)
    estado.setdefault("faltas_com_cargo", 0)
    estado.setdefault("possui_cargo", False)
    estado.setdefault("perguntas_respondidas", [])
    estado.setdefault("ultima_resposta_valida", None)
    return estado


def registrar_pergunta_diaria_fa_do_raven(
    guild_ou_id,
    message_id,
    channel_id,
    enviada_em=None,
    pergunta_texto=None,
):
    enviada_em = enviada_em or datetime.now(FUSO_HORARIO)
    if enviada_em.tzinfo is None:
        enviada_em = enviada_em.replace(tzinfo=FUSO_HORARIO)

    dados = carregar_dados_conquistas()
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=True)
    perguntas = guild_entry.setdefault("perguntas_diarias", {})
    chave_data = enviada_em.astimezone(FUSO_HORARIO).strftime("%Y-%m-%d")
    fecha_em = enviada_em.astimezone(FUSO_HORARIO) + timedelta(hours=CONQUISTA_FA_DO_RAVEN["prazo_horas"])

    perguntas[chave_data] = {
        "message_id": str(message_id),
        "channel_id": str(channel_id),
        "enviada_em": enviada_em.astimezone(FUSO_HORARIO).isoformat(),
        "fecha_em": fecha_em.isoformat(),
        "processada": False,
        "respondentes": {},
        "pergunta_texto": str(pergunta_texto or "").strip(),
    }
    salvar_dados_conquistas(dados)
    return chave_data, perguntas[chave_data]


def obter_pergunta_diaria_aberta(guild_ou_id, agora=None):
    agora = agora or datetime.now(FUSO_HORARIO)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=FUSO_HORARIO)

    dados = carregar_dados_conquistas()
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=False)
    if guild_entry is None:
        return None, None

    abertas = []
    for chave, pergunta in (guild_entry.get("perguntas_diarias") or {}).items():
        if bool(pergunta.get("processada")):
            continue
        try:
            fecha_em = datetime.fromisoformat(str(pergunta.get("fecha_em", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if fecha_em.tzinfo is None:
            fecha_em = fecha_em.replace(tzinfo=FUSO_HORARIO)
        fecha_em = fecha_em.astimezone(FUSO_HORARIO)
        if agora <= fecha_em:
            abertas.append((fecha_em, chave, pergunta))

    if not abertas:
        return None, None

    abertas.sort(key=lambda item: item[0], reverse=True)
    _, chave, pergunta = abertas[0]
    return chave, pergunta


def registrar_resposta_fa_do_raven(guild_ou_id, user_id, message_id, responded_at=None, content=None):
    responded_at = responded_at or datetime.now(FUSO_HORARIO)
    if responded_at.tzinfo is None:
        responded_at = responded_at.replace(tzinfo=FUSO_HORARIO)

    dados = carregar_dados_conquistas()
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=True)
    chave, pergunta = obter_pergunta_diaria_aberta(guild_ou_id, agora=responded_at)
    if not chave or not pergunta:
        return False, "sem_pergunta"

    respondentes = pergunta.setdefault("respondentes", {})
    chave_usuario = str(user_id)
    if chave_usuario in respondentes:
        return False, "duplicado"

    respondentes[chave_usuario] = {
        "message_id": str(message_id),
        "responded_at": responded_at.astimezone(FUSO_HORARIO).isoformat(),
        "content": str(content or "").strip()[:200],
    }
    guild_entry.setdefault("perguntas_diarias", {})[chave] = pergunta
    salvar_dados_conquistas(dados)
    return True, chave


def remover_resposta_fa_do_raven(guild_ou_id, user_id, message_id):
    dados = carregar_dados_conquistas()
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=False)
    if guild_entry is None:
        return False

    alterou = False
    for pergunta in (guild_entry.get("perguntas_diarias") or {}).values():
        if bool(pergunta.get("processada")):
            continue
        respondentes = pergunta.get("respondentes") or {}
        registro = respondentes.get(str(user_id))
        if not registro:
            continue
        if str(registro.get("message_id")) != str(message_id):
            continue
        respondentes.pop(str(user_id), None)
        alterou = True

    if alterou:
        salvar_dados_conquistas(dados)
    return alterou


def listar_perguntas_diarias_pendentes(guild_ou_id, agora=None):
    agora = agora or datetime.now(FUSO_HORARIO)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=FUSO_HORARIO)

    dados = carregar_dados_conquistas()
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=False)
    if guild_entry is None:
        return []

    pendentes = []
    for chave, pergunta in (guild_entry.get("perguntas_diarias") or {}).items():
        if bool(pergunta.get("processada")):
            continue
        try:
            fecha_em = datetime.fromisoformat(str(pergunta.get("fecha_em", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if fecha_em.tzinfo is None:
            fecha_em = fecha_em.replace(tzinfo=FUSO_HORARIO)
        fecha_em = fecha_em.astimezone(FUSO_HORARIO)
        if agora >= fecha_em:
            pendentes.append((chave, pergunta))

    pendentes.sort(key=lambda item: item[0])
    return pendentes


def marcar_pergunta_diaria_processada(guild_ou_id, chave_data):
    dados = carregar_dados_conquistas()
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=False)
    if guild_entry is None:
        return False

    pergunta = (guild_entry.get("perguntas_diarias") or {}).get(str(chave_data))
    if not pergunta:
        return False

    pergunta["processada"] = True
    salvar_dados_conquistas(dados)
    return True


def formatar_data_iso_local(valor):
    texto = str(valor or "").strip()
    if not texto:
        return "Não encontrada"
    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return texto
    if data.tzinfo is None:
        data = data.replace(tzinfo=FUSO_HORARIO)
    return data.astimezone(FUSO_HORARIO).strftime("%d/%m/%Y às %H:%M")
