from services.conquistas_presenca import carregar_dados_conquistas, salvar_dados_conquistas
from services.server_config import extrair_guild_id


CONQUISTA_MENSAGEIRO_DA_NOITE = {
    "tipo": "mensageiro_da_noite",
    "nome": "Mensageiro da Noite",
    "cargo_nome": "𓆩✦ Mensageiro da Noite ✦𓆪",
    "objetivo": 5,
}


def _estado_padrao_mensageiro():
    return {
        "progresso": 0,
        "objetivo": CONQUISTA_MENSAGEIRO_DA_NOITE["objetivo"],
        "possui_cargo": False,
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


def obter_estado_mensageiro(dados, guild_ou_id, user_id, criar=False):
    guild_entry = _obter_guild_entry(dados, guild_ou_id, criar=criar)
    if guild_entry is None:
        return None

    membros = guild_entry.setdefault("membros", {})
    membro_entry = membros.get(str(user_id))
    if membro_entry is None and criar:
        membro_entry = {}
        membros[str(user_id)] = membro_entry

    if membro_entry is None:
        return _estado_padrao_mensageiro()

    estado = membro_entry.get(CONQUISTA_MENSAGEIRO_DA_NOITE["tipo"])
    if estado is None and criar:
        estado = _estado_padrao_mensageiro()
        membro_entry[CONQUISTA_MENSAGEIRO_DA_NOITE["tipo"]] = estado

    if estado is None:
        return _estado_padrao_mensageiro()

    estado.setdefault("progresso", 0)
    estado.setdefault("objetivo", CONQUISTA_MENSAGEIRO_DA_NOITE["objetivo"])
    estado.setdefault("possui_cargo", False)
    return estado


def adicionar_pontos_mensageiro(dados, guild_ou_id, user_id, quantidade):
    estado = obter_estado_mensageiro(dados, guild_ou_id, user_id, criar=True)
    objetivo = int(CONQUISTA_MENSAGEIRO_DA_NOITE["objetivo"])
    quantidade = max(0, int(quantidade or 0))
    anterior = max(0, min(int(estado.get("progresso", 0) or 0), objetivo))
    atual = min(objetivo, anterior + quantidade)
    estado["progresso"] = atual
    conquistado_agora = anterior < objetivo and atual >= objetivo
    if atual >= objetivo:
        estado["possui_cargo"] = True
    return {
        "anterior": anterior,
        "atual": atual,
        "objetivo": objetivo,
        "ganho_aplicado": max(0, atual - anterior),
        "conquistado_agora": conquistado_agora,
    }


def remover_pontos_mensageiro(dados, guild_ou_id, user_id, quantidade):
    estado = obter_estado_mensageiro(dados, guild_ou_id, user_id, criar=True)
    objetivo = int(CONQUISTA_MENSAGEIRO_DA_NOITE["objetivo"])
    quantidade = max(0, int(quantidade or 0))
    anterior = max(0, min(int(estado.get("progresso", 0) or 0), objetivo))
    atual = max(0, anterior - quantidade)
    estado["progresso"] = atual
    if atual < objetivo:
        estado["possui_cargo"] = False
    return {
        "anterior": anterior,
        "atual": atual,
        "objetivo": objetivo,
        "removido": max(0, anterior - atual),
    }


def salvar_estado_mensageiro(dados):
    salvar_dados_conquistas(dados)

