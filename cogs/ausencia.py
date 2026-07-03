import io
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    FUSO_HORARIO,
)
from services.advertencias import (
    adicionar_advertencia_manual,
    aplicar_advertencia_automatica,
    confirmar_visualizacao_advertencia,
    obter_advertencias_ativas,
    obter_advertencia_por_mensagem,
    remover_advertencia_manual,
    salvar_mensagem_advertencia,
    zerar_advertencia_por_resposta,
)
from services.ausencias import (
    atualizar_resposta_evento_staff,
    buscar_registro_membro_eventos,
    carregar_dados_ausencias,
    contar_respostas_evento,
    definir_reset_contagens,
    encerrar_evento_ausencia,
    evento_permite_advertencia_automatica,
    obter_evento_ausencia,
    obter_reset_contagens,
    registrar_resposta_evento,
    remover_resposta_evento_staff,
    salvar_mensagens_lista_staff_evento,
    salvar_evento_ausencia,
    atualizar_sem_resposta_evento,
)
from services.conquistas_presenca import (
    carregar_dados_conquistas,
    evento_conquista_ja_processado,
    formatar_tipo_evento,
    marcar_evento_conquista_processado,
    normalizar_tipo_evento,
    obter_estado_conquista,
    obter_meta_conquista,
    obter_progresso_exibicao,
    salvar_dados_conquistas,
)
from services.conquista_anuncios import enviar_embed_conquista
from services.server_config import obter_valor_config
from utils.discord_helpers import membro_eh_staff


AUSENCIA_COLOR = discord.Color.from_rgb(0, 255, 255)
AUSENCIA_FOOTER = "FDN • Controle de Presença"
AUSENCIA_FOOTER_SISTEMA = "FDN • Sistema de Presença"
AUSENCIA_EMOJI_EVENTO = "<:moonfdn:1501329435222216857>"
AUSENCIA_EMOJI_HORA = "<:334clock:1502706512597090456>"
AUSENCIA_EMOJI_OBSERVACAO = "<:chatFDN:1501711909601153024>"
AUSENCIA_EMOJI_STATUS = "<:pinfdn:1495890637961302086>"
AUSENCIA_PANEL_TITLE = "☾ Painel de Presença — FDN"
ADVERTENCIA_AUTOMATICA_PAUSADA = False
RANKING_AUSENCIA_IGNORAR_IDS = {
    1273671698255839315,  # Fundadora Akayubi
    451928629035794463,  # Lider Vituw
}
ADVERTENCIA_CORES = {
    1: discord.Color(0xFFF176),
    2: discord.Color(0xFFD54F),
    3: discord.Color(0xFF9800),
    4: discord.Color(0xFF5722),
    5: discord.Color(0xD50000),
}
ADVERTENCIA_QUANTIDADE_CHOICES = [
    app_commands.Choice(name=f"{numero} de 5", value=numero)
    for numero in range(1, 6)
]
CRIAR_EVENTO_ADVERTENCIA_CHOICES = [
    app_commands.Choice(name="Sim", value="sim"),
    app_commands.Choice(name="Nao", value="nao"),
]
CRIAR_EVENTO_TIPO_CHOICES = [
    app_commands.Choice(name="Invasao", value="invasao"),
    app_commands.Choice(name="Jogatina", value="jogatina"),
    app_commands.Choice(name="Cinema", value="cinema"),
    app_commands.Choice(name="Outro", value="outro"),
]

CONQUISTA_PRESENCA_KEYS = {
    "invasao": "invasor_noturno",
    "jogatina": "jogador_abissal",
    "cinema": "cinefilo_estelar",
}
PRESENCA_REMOVER_RESPOSTA_CHOICES = [
    app_commands.Choice(name="Presença", value="presente"),
    app_commands.Choice(name="Ausência", value="ausente"),
    app_commands.Choice(name="Talvez", value="talvez"),
]
FORMATOS_IMAGEM_EVENTO = (".png", ".jpg", ".jpeg", ".gif", ".webp")
PRESENCA_EVENTO_CARGO_MEMBRO_ID = 1461789054986223650
PRESENCA_EVENTO_CARGO_MEMBRO_CREPUSCULO_ID = 1482879631458828338
PRESENCA_RELATORIO_MAX_DIAS = 90


def membro_eh_staff_ausencia(membro):
    cargo_staff_id = obter_valor_config(getattr(membro, "guild", None), "AUSENCIA_STAFF_ROLE_ID")
    if hasattr(membro, "roles") and cargo_staff_id:
        for cargo in membro.roles:
            if cargo.id == cargo_staff_id:
                return True

    return membro_eh_staff(membro)


def ranking_deve_ignorar_usuario(user_id) -> bool:
    try:
        return int(user_id) in RANKING_AUSENCIA_IGNORAR_IDS
    except (TypeError, ValueError):
        return False


def membro_pode_ver_ranking_presenca(membro):
    if membro_eh_staff_ausencia(membro):
        return True

    if not hasattr(membro, "roles"):
        return False

    cargos_permitidos = {
        cargo_id
        for cargo_id in (
            obter_valor_config(getattr(membro, "guild", None), "CARGO_AVISO_REACAO_ID"),
            obter_valor_config(getattr(membro, "guild", None), "CARGO_MEMBRO_ID"),
        )
        if cargo_id
    }
    if not cargos_permitidos:
        return False

    return any(cargo.id in cargos_permitidos for cargo in membro.roles)


def formatar_status_resposta(status):
    mapa = {
        "presente": "Presente",
        "ausente": "Ausente",
        "talvez": "Talvez",
    }
    return mapa.get(status, status.title())


def extrair_user_id_termo_membro(termo):
    termo_limpo = str(termo or "").strip()
    if not termo_limpo:
        return None

    if termo_limpo.startswith("<@") and termo_limpo.endswith(">"):
        termo_limpo = termo_limpo[2:-1].strip()
        if termo_limpo.startswith("!"):
            termo_limpo = termo_limpo[1:].strip()

    return termo_limpo if termo_limpo.isdigit() else None


def obter_termos_busca_membro(termo, membro=None):
    termos = set()
    termo_limpo = str(termo or "").strip()
    if termo_limpo:
        termos.add(termo_limpo.casefold())

    if membro is None:
        return termos

    for valor in (
        str(membro),
        getattr(membro, "name", None),
        getattr(membro, "display_name", None),
        getattr(membro, "global_name", None),
    ):
        if valor:
            termos.add(str(valor).strip().casefold())

    return termos


async def resolver_membro_por_termo(guild, termo):
    if guild is None:
        return None

    user_id = extrair_user_id_termo_membro(termo)
    if user_id:
        membro = guild.get_member(int(user_id))
        if membro is not None:
            return membro

        try:
            return await guild.fetch_member(int(user_id))
        except Exception:
            return None

    termo_normalizado = str(termo or "").strip().casefold()
    if not termo_normalizado:
        return None

    membros = list(getattr(guild, "members", []) or [])
    for membro in membros:
        for valor in (
            str(membro),
            getattr(membro, "name", None),
            getattr(membro, "display_name", None),
            getattr(membro, "global_name", None),
        ):
            if valor and termo_normalizado == str(valor).strip().casefold():
                return membro

    for membro in membros:
        for valor in (
            str(membro),
            getattr(membro, "name", None),
            getattr(membro, "display_name", None),
            getattr(membro, "global_name", None),
        ):
            if valor and termo_normalizado in str(valor).strip().casefold():
                return membro

    return None


async def obter_membros_ausencia_automatica(guild):
    cargo_membro_id = PRESENCA_EVENTO_CARGO_MEMBRO_ID
    if guild is None or not cargo_membro_id:
        return []

    cargo_membro_id = int(cargo_membro_id)
    cargo = guild.get_role(int(cargo_membro_id)) if hasattr(guild, "get_role") else None
    if cargo is not None:
        membros = list(getattr(cargo, "members", []) or [])
    else:
        membros = [
            membro
            for membro in list(getattr(guild, "members", []) or [])
            if any(getattr(role, "id", None) == cargo_membro_id for role in getattr(membro, "roles", []))
        ]

    if hasattr(guild, "fetch_members"):
        try:
            async for membro in guild.fetch_members(limit=None):
                if any(getattr(role, "id", None) == cargo_membro_id for role in getattr(membro, "roles", [])):
                    membros.append(membro)
        except Exception as erro:
            print(f"[EVENTO] Não consegui buscar membros do cargo de ausência automática | guild={getattr(guild, 'id', None)} cargo={cargo_membro_id} erro={erro}")

    elegiveis = []
    vistos = set()
    for membro in membros:
        user_id = getattr(membro, "id", None)
        if (
            not user_id
            or user_id in vistos
            or getattr(membro, "bot", False)
            or membro_eh_staff_ausencia(membro)
        ):
            continue

        vistos.add(user_id)
        elegiveis.append(
            {
                "user_id": user_id,
                "user_name": str(membro),
            }
        )

    print(
        f"[EVENTO] Membros elegíveis para ausência automática | guild={getattr(guild, 'id', None)} "
        f"cargo={cargo_membro_id} encontrados={len(elegiveis)}"
    )
    return elegiveis


def normalizar_dias_relatorio(dias):
    try:
        dias = int(dias or 14)
    except (TypeError, ValueError):
        dias = 14
    return min(PRESENCA_RELATORIO_MAX_DIAS, max(1, dias))


def obter_data_referencia_evento(evento):
    for campo in ("encerrado_em", "created_at"):
        valor = str(evento.get(campo) or "").strip()
        if not valor:
            continue

        try:
            data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            continue

        if data.tzinfo is None:
            data = data.replace(tzinfo=FUSO_HORARIO)
        return data.astimezone(FUSO_HORARIO)

    return None


def parse_data_reset_contagens(guild_ou_id):
    valor = obter_reset_contagens(guild_ou_id)
    if not valor:
        return None

    try:
        data = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None

    if data.tzinfo is None:
        data = data.replace(tzinfo=FUSO_HORARIO)
    return data.astimezone(FUSO_HORARIO)


def evento_deve_contar_pos_reset(evento, guild_ou_id):
    reset_em = parse_data_reset_contagens(guild_ou_id)
    if reset_em is None:
        return True

    data_evento = obter_data_referencia_evento(evento)
    if data_evento is None:
        return False

    return data_evento >= reset_em


def evento_pertence_ao_servidor(evento, guild):
    guild_id = getattr(guild, "id", guild)
    evento_guild_id = str(evento.get("guild_id") or "").strip()
    if not guild_id or not evento_guild_id:
        return True
    return evento_guild_id == str(guild_id)


def obter_eventos_encerrados_periodo(guild, dias):
    dias = normalizar_dias_relatorio(dias)
    limite = datetime.now(FUSO_HORARIO) - timedelta(days=dias)
    dados = carregar_dados_ausencias()
    eventos = []

    for evento in dados.get("eventos", {}).values():
        if str(evento.get("status", "")).strip().lower() != "encerrado":
            continue
        if not evento_pertence_ao_servidor(evento, guild):
            continue

        data_referencia = obter_data_referencia_evento(evento)
        if data_referencia is None or data_referencia < limite:
            continue
        if not evento_deve_contar_pos_reset(evento, guild):
            continue

        eventos.append((data_referencia, evento))

    eventos.sort(key=lambda item: item[0])
    return [evento for _, evento in eventos]


def obter_status_resposta_relatorio(resposta):
    if not resposta or resposta.get("registrado_automaticamente"):
        return "sem_resposta"

    status = str(resposta.get("status", "")).strip().lower()
    if status in {"presente", "ausente", "talvez"}:
        return status
    return "sem_resposta"


def formatar_data_evento_relatorio(evento):
    data_evento = str(evento.get("data") or "").strip()
    if data_evento:
        return data_evento

    data_referencia = obter_data_referencia_evento(evento)
    if data_referencia is None:
        return "Data nao informada"
    return data_referencia.strftime("%d/%m/%Y")


def nome_relatorio_membro(analise):
    nome = str(analise.get("display_name") or analise.get("user_name") or analise.get("user_id") or "Membro").strip()
    return nome or f"ID {analise.get('user_id')}"


async def analisar_atividade_presenca(guild, dias):
    dias = normalizar_dias_relatorio(dias)
    agora = datetime.now(FUSO_HORARIO)
    inicio_periodo = agora - timedelta(days=dias)
    reset_em = parse_data_reset_contagens(guild)
    if reset_em is not None and reset_em > inicio_periodo:
        inicio_periodo = reset_em
    eventos = obter_eventos_encerrados_periodo(guild, dias)
    dados = carregar_dados_ausencias()
    eventos_historico = []
    for evento in dados.get("eventos", {}).values():
        if str(evento.get("status", "")).strip().lower() != "encerrado":
            continue
        if not evento_pertence_ao_servidor(evento, guild):
            continue
        if not evento_deve_contar_pos_reset(evento, guild):
            continue

        data_referencia = obter_data_referencia_evento(evento)
        if data_referencia is None:
            continue
        eventos_historico.append((data_referencia, evento))

    eventos_historico.sort(key=lambda item: item[0])
    membros = await obter_membros_ausencia_automatica(guild)
    analises = {}

    for membro in membros:
        user_id = str(membro.get("user_id"))
        if not user_id:
            continue

        membro_obj = guild.get_member(int(user_id)) if guild is not None else None
        display_name = (
            getattr(membro_obj, "display_name", None)
            or membro.get("user_name")
            or user_id
        )
        analises[user_id] = {
            "user_id": int(user_id),
            "user_name": membro.get("user_name") or user_id,
            "display_name": str(display_name),
            "presente": 0,
            "ausente": 0,
            "talvez": 0,
            "sem_resposta": 0,
            "participacoes": 0,
            "respostas_sem_presenca": 0,
            "ultima_presenca": None,
            "ultima_presenca_dt": None,
            "dias_sem_presenca": None,
            "eventos": [],
        }

    for data_referencia, evento in eventos_historico:
        respostas = evento.get("respostas", {})
        data_evento = formatar_data_evento_relatorio(evento)
        for user_id, analise in analises.items():
            resposta = respostas.get(user_id)
            if obter_status_resposta_relatorio(resposta) != "presente":
                continue
            analise["ultima_presenca"] = data_evento
            analise["ultima_presenca_dt"] = data_referencia

    for evento in eventos:
        respostas = evento.get("respostas", {})
        for user_id, analise in analises.items():
            resposta = respostas.get(user_id)
            status = obter_status_resposta_relatorio(resposta)
            analise[status] += 1

            data_evento = formatar_data_evento_relatorio(evento)
            if status == "presente":
                analise["participacoes"] += 1
            elif status in {"ausente", "talvez"}:
                analise["respostas_sem_presenca"] += 1

            analise["eventos"].append(
                {
                    "nome": str(evento.get("nome_evento") or "Evento"),
                    "data": data_evento,
                    "status": status,
                }
            )

    for analise in analises.values():
        ultima_presenca_dt = analise.get("ultima_presenca_dt")
        if ultima_presenca_dt is not None:
            analise["dias_sem_presenca"] = max(0, (agora.date() - ultima_presenca_dt.date()).days)

    ativos = []
    responderam_sem_participar = []
    sem_atividade = []
    for analise in analises.values():
        if analise["presente"] > 0:
            ativos.append(analise)
        elif analise["ausente"] + analise["talvez"] > 0:
            responderam_sem_participar.append(analise)
        else:
            sem_atividade.append(analise)

    def chave_ordenacao_nome(item):
        return str(item.get("display_name") or item.get("user_name") or "").casefold()

    def chave_ordenacao_inatividade(item):
        dias_sem_presenca = item.get("dias_sem_presenca")
        peso = dias_sem_presenca if dias_sem_presenca is not None else 10**6
        return (-peso, chave_ordenacao_nome(item))

    return {
        "dias": dias,
        "eventos": eventos,
        "total_eventos": len(eventos),
        "data_inicio": inicio_periodo.strftime("%d/%m/%Y"),
        "data_fim": agora.strftime("%d/%m/%Y"),
        "ativos": sorted(ativos, key=chave_ordenacao_nome),
        "responderam_sem_participar": sorted(responderam_sem_participar, key=chave_ordenacao_inatividade),
        "sem_atividade": sorted(sem_atividade, key=chave_ordenacao_inatividade),
        "analises": analises,
    }

def formatar_ultima_presenca_texto(analise):
    return analise.get("ultima_presenca") or "não encontrada"

def formatar_dias_sem_presenca_texto(analise, dias_periodo=None):
    dias_sem_presenca = analise.get("dias_sem_presenca")
    if dias_sem_presenca is None:
        if dias_periodo:
            return f"{dias_periodo}+ dias sem presença"
        return "não encontrada"
    if dias_periodo and dias_sem_presenca >= dias_periodo:
        return f"{dias_periodo}+ dias sem presença"
    return f"{dias_sem_presenca} dias sem presença"

def linha_observacao_relatorio(analise, total_eventos):
    return (
        f"• {nome_relatorio_membro(analise)} — respondeu {analise['respostas_sem_presenca']}x | "
        f"última presença: {formatar_ultima_presenca_texto(analise)}"
    )

def linha_remocao_relatorio(analise, total_eventos, dias_periodo):
    return (
        f"• {nome_relatorio_membro(analise)} — 0/{total_eventos} presenças no período | "
        f"ignorou {analise['sem_resposta']}/{total_eventos}"
    )

def montar_bloco_linhas(linhas, vazio="Nenhum membro nesta categoria.", limite=900):
    if not linhas:
        return vazio, False

    bloco = []
    tamanho = 0
    truncado = False
    for indice, linha in enumerate(linhas):
        incremento = len(linha) + (1 if bloco else 0)
        if bloco and tamanho + incremento > limite:
            restante = len(linhas) - indice
            bloco.append(f"... e mais {restante} no arquivo.")
            truncado = True
            break
        bloco.append(linha)
        tamanho += incremento

    return "\n".join(bloco), truncado

def criar_arquivo_texto_presenca(nome_arquivo, conteudo, encoding="utf-8-sig"):
    buffer = io.BytesIO(str(conteudo).encode(encoding))
    return discord.File(buffer, filename=nome_arquivo)


def criar_texto_relatorio_presenca(resultado):
    linhas = [
        f"RELATÓRIO DE ATIVIDADE — {resultado['dias']} DIAS",
        "",
        f"Período: {resultado['data_inicio']} até {resultado['data_fim']}",
        f"Eventos analisados: {resultado['total_eventos']}",
        "",
        "ATIVOS",
    ]

    if resultado["ativos"]:
        for item in resultado["ativos"]:
            linhas.append(
                f"- {nome_relatorio_membro(item)} | Presenças: {item['presente']} | "
                f"Ausências: {item['ausente']} | Talvez: {item['talvez']} | "
                f"Sem resposta: {item['sem_resposta']} | Última presença: {formatar_ultima_presenca_texto(item)}"
            )
    else:
        linhas.append("- Nenhum membro")

    linhas.extend(["", "EM OBSERVAÇÃO"])
    if resultado["responderam_sem_participar"]:
        for item in resultado["responderam_sem_participar"]:
            linhas.append(
                f"- {nome_relatorio_membro(item)} | Presenças: {item['presente']} | "
                f"Respondeu: {item['respostas_sem_presenca']} | Última presença: {formatar_ultima_presenca_texto(item)}"
            )
    else:
        linhas.append("- Nenhum membro")

    linhas.extend(["", "SEM PRESENÇA NO PERÍODO"])
    if resultado["sem_atividade"]:
        for item in resultado["sem_atividade"]:
            linhas.append(
                f"- {nome_relatorio_membro(item)} | 0/{resultado['total_eventos']} presenças no período | "
                f"Ignorou: {item['sem_resposta']}/{resultado['total_eventos']} | "
                f"Última presença registrada: {formatar_ultima_presenca_texto(item)}"
            )
    else:
        linhas.append("- Nenhum membro")

    return "\n".join(linhas)

def criar_embed_relatorio_presenca(resultado):
    embed = discord.Embed(
        title="📊・Relatório de Atividade",
        description=(
            f"Período: {resultado['data_inicio']} até {resultado['data_fim']}\n"
            f"Eventos analisados: {resultado['total_eventos']}\n\n"
            f"✅ Ativos: {len(resultado['ativos'])}\n"
            f"🟡 Em observação: {len(resultado['responderam_sem_participar'])}\n"
            f"❌ Sem presença no período: {len(resultado['sem_atividade'])}\n\n"
            "📌 Presença = participação ativa\n"
            "Ausência/Talvez = resposta, mas não presença\n"
            "Decisão final: staff"
        ),
        color=AUSENCIA_COLOR,
    )

    principais = resultado["sem_atividade"][:5]
    if principais:
        linhas = [
            f"• {nome_relatorio_membro(item)} — 0/{resultado['total_eventos']} presenças | "
            f"ignorou {item['sem_resposta']}/{resultado['total_eventos']}"
            for item in principais
        ]
        embed.add_field(
            name="❌ Principais sem presença no período",
            value="\n".join(linhas),
            inline=False,
        )
    else:
        embed.add_field(
            name="❌ Principais sem presença no período",
            value="Nenhum membro entrou nessa categoria no período.",
            inline=False,
        )

    embed.add_field(
        name="📎 Arquivo completo",
        value="Relatório completo disponível em arquivo.",
        inline=False,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed, True

def criar_texto_inativos_presenca(resultado):
    linhas = [
        f"POSSÍVEIS INATIVOS — {resultado['dias']} DIAS",
        "",
        f"Período: {resultado['data_inicio']} até {resultado['data_fim']}",
        f"Eventos analisados: {resultado['total_eventos']}",
        "",
        "EM OBSERVAÇÃO",
    ]

    if resultado["responderam_sem_participar"]:
        for item in resultado["responderam_sem_participar"]:
            linhas.append(
                f"- {nome_relatorio_membro(item)} | Presenças: {item['presente']} | "
                f"Respondeu: {item['respostas_sem_presenca']} | Última presença: {formatar_ultima_presenca_texto(item)}"
            )
    else:
        linhas.append("- Nenhum membro")

    linhas.extend(["", "SEM PRESENÇA NO PERÍODO"])
    if resultado["sem_atividade"]:
        for item in resultado["sem_atividade"]:
            linhas.append(
                f"- {nome_relatorio_membro(item)} | 0/{resultado['total_eventos']} presenças no período | "
                f"Ignorou: {item['sem_resposta']}/{resultado['total_eventos']} | "
                f"Última presença registrada: {formatar_ultima_presenca_texto(item)}"
            )
    else:
        linhas.append("- Nenhum membro")

    return "\n".join(linhas)

def criar_embed_inativos_presenca(resultado):
    embed = discord.Embed(
        title="❌・Possíveis Inativos",
        description=(
            "Membros sem presença registrada no período analisado. "
            "A remoção deve ser avaliada manualmente pela staff.\n\n"
            f"Período: {resultado['data_inicio']} até {resultado['data_fim']}\n"
            f"Eventos analisados: {resultado['total_eventos']}"
        ),
        color=AUSENCIA_COLOR,
    )

    principais = resultado["sem_atividade"][:10]
    if principais:
        linhas = [
            (
                f"• {nome_relatorio_membro(item)} — 0/{resultado['total_eventos']} presenças no período | Ignorou: {item['sem_resposta']}/{resultado['total_eventos']}\n"
                f"  Última presença registrada: {formatar_ultima_presenca_texto(item)}"
            )
            for item in principais
        ]
        embed.add_field(name="❌ Principais inativos", value="\n".join(linhas), inline=False)
    else:
        embed.add_field(
            name="❌ Principais inativos",
            value="Nenhum membro entrou nessa categoria no período.",
            inline=False,
        )

    if resultado["responderam_sem_participar"]:
        embed.add_field(
            name="🟡 Em observação",
            value=(
                f"{len(resultado['responderam_sem_participar'])} membros responderam ausência/talvez "
                "e ficaram fora da lista principal de possível remoção."
            ),
            inline=False,
        )

    precisa_arquivo = len(resultado["sem_atividade"]) > 10 or len(resultado["responderam_sem_participar"]) > 0
    if precisa_arquivo:
        embed.add_field(
            name="📎 Arquivo completo",
            value="Relatório completo disponível em arquivo.",
            inline=False,
        )

    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed, precisa_arquivo

def obter_sugestao_atividade(analise):
    if analise["presente"] > 0:
        return "Ativo"
    if analise["ausente"] + analise["talvez"] > 0:
        return "Observação"
    return "Possível remoção"

def criar_embed_historico_membro_presenca(membro, analise, dias, total_eventos):
    status_nomes = {
        "presente": "Presença",
        "ausente": "Ausência",
        "talvez": "Talvez",
        "sem_resposta": "Sem resposta",
    }
    embed = discord.Embed(
        title=f"📌・Histórico de Presença — {getattr(membro, 'display_name', str(membro))}",
        color=AUSENCIA_COLOR,
    )
    embed.description = (
        f"Período analisado: últimos {dias} dias\n"
        f"Total de eventos encerrados: {total_eventos}\n\n"
        "Este relatório é apenas para análise da staff."
    )
    embed.add_field(name="Eventos no período", value=str(total_eventos), inline=True)
    embed.add_field(name="Participações", value=f"{analise['presente']}/{total_eventos}", inline=True)
    embed.add_field(name="Respostas", value=f"{analise['ausente']} ausência | {analise['talvez']} talvez", inline=False)
    embed.add_field(name="Ignoradas", value=str(analise["sem_resposta"]), inline=True)
    embed.add_field(name="Última presença", value=formatar_ultima_presenca_texto(analise), inline=True)
    embed.add_field(name="Dias sem presença", value=formatar_dias_sem_presenca_texto(analise, dias), inline=True)
    embed.add_field(name="Sugestão", value=obter_sugestao_atividade(analise), inline=True)

    linhas_eventos = [
        f"{evento['data']} - {evento['nome']}: {status_nomes.get(evento['status'], evento['status'])}"
        for evento in analise["eventos"]
    ]
    bloco, truncado = montar_bloco_linhas(linhas_eventos, vazio="Nenhum evento encerrado no período.", limite=900)
    if truncado:
        bloco += "\nUse o relatório geral em arquivo para ver tudo."
    embed.add_field(name="Histórico do período", value=bloco, inline=False)
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed

def criar_embed_painel_atividade_presenca(atualizado_em=None):
    descricao = (
        "Acompanhe a presença dos membros nos eventos do clã.\n\n"
        "📌 Período padrão: últimos 14 dias\n"
        "⚠️ Uso interno da staff\n"
        "🌙 Decisões de remoção continuam sendo manuais.\n\n"
        "O bot não aplica advertências, não remove membros e não pune automaticamente.\n"
        "Os relatórios servem apenas para análise manual da staff."
    )
    if atualizado_em is not None:
        descricao += f"\n\n🕒 Última atualização: {atualizado_em.strftime('%d/%m/%Y às %H:%M')}"

    embed = discord.Embed(
        title="📊・Painel de Atividade FDN",
        description=descricao,
        color=AUSENCIA_COLOR,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed

def calcular_contagens_evento(evento, membros_elegiveis=None):
    contagens = contar_respostas_evento(evento)
    respostas = evento.get("respostas", {})
    ids_esperados = {
        str(membro.get("user_id"))
        for membro in (membros_elegiveis or [])
        if membro.get("user_id")
    }

    if str(evento.get("status", "")).strip().lower() == "encerrado" and "sem_resposta" in evento:
        sem_resposta = int(evento.get("sem_resposta") or 0)
    elif ids_esperados:
        ids_respondidos = set(respostas.keys()) & ids_esperados
        sem_resposta = len(ids_esperados - ids_respondidos)
    else:
        sem_resposta = int(evento.get("sem_resposta", 0) or 0)

    contagens["sem_resposta"] = max(0, sem_resposta)
    return contagens


def filtrar_membros_sem_resposta(evento, membros_elegiveis):
    respostas = evento.get("respostas", {})
    sem_resposta = []

    for membro in membros_elegiveis or []:
        user_id = membro.get("user_id")
        if not user_id:
            continue
        if str(user_id) in respostas:
            continue
        sem_resposta.append(membro)

    return sem_resposta


async def obter_contagens_evento(guild, evento, membros_elegiveis=None):
    if membros_elegiveis is None:
        membros_elegiveis = await obter_membros_ausencia_automatica(guild)
    return calcular_contagens_evento(evento, membros_elegiveis)


def normalizar_resposta_advertencia(valor):
    texto = str(valor or "").strip().casefold()
    return texto not in {"n", "nao", "não", "no", "false", "0", "desativada", "desativado"}


def anexo_eh_imagem_evento(anexo):
    if anexo is None:
        return True

    content_type = str(getattr(anexo, "content_type", "") or "").casefold()
    if content_type.startswith("image/"):
        return True

    filename = str(getattr(anexo, "filename", "") or "").casefold()
    return filename.endswith(FORMATOS_IMAGEM_EVENTO)


def formatar_status_advertencias(valor):
    mapa = {
        "aplicadas": "Aplicadas",
        "parciais": "Aplicadas parcialmente",
        "nao_aplicadas": "Não aplicadas",
        "desativadas": "Desativadas",
    }
    return mapa.get(valor, str(valor or "Não aplicadas"))


def obter_cargo_conquista_evento(guild, tipo_evento):
    meta = obter_meta_conquista(tipo_evento)
    if guild is None or not meta:
        return None
    return discord.utils.get(getattr(guild, "roles", []), name=meta.get("cargo_nome"))


def membro_tem_cargo_conquista(membro, cargo):
    if membro is None or cargo is None:
        return False
    return any(getattr(role, "id", None) == getattr(cargo, "id", None) for role in getattr(membro, "roles", []))


def membro_elegivel_conquista_presenca(membro):
    if membro is None or getattr(membro, "bot", False) or membro_eh_staff_ausencia(membro):
        return False
    return any(getattr(role, "id", None) == PRESENCA_EVENTO_CARGO_MEMBRO_ID for role in getattr(membro, "roles", []))


def obter_sufixo_conquista_presenca(guild, evento, user_id):
    meta = obter_meta_conquista(evento.get("tipo_evento"))
    if not meta or guild is None or not user_id:
        return None

    dados_conquistas = carregar_dados_conquistas()
    cargo = obter_cargo_conquista_evento(guild, meta["tipo"])
    membro = guild.get_member(int(user_id)) if hasattr(guild, "get_member") else None
    possui_cargo = membro_tem_cargo_conquista(membro, cargo)
    confirmado = (
        str(evento.get("status", "")).strip().lower() == "encerrado"
        and evento_conquista_ja_processado(dados_conquistas, getattr(guild, "id", None), evento.get("event_id"))
    )
    progresso = obter_progresso_exibicao(
        dados_conquistas,
        getattr(guild, "id", None),
        user_id,
        meta["tipo"],
        confirmado=confirmado,
        possui_cargo=possui_cargo,
    )
    if not progresso:
        return None

    return f"{progresso['progresso']}/{progresso['objetivo']} para {progresso['nome']}"


def formatar_membro_resposta_evento(guild, resposta):
    user_id = resposta.get("user_id")
    if not user_id:
        return "Membro desconhecido"

    nome = str(resposta.get("display_name") or resposta.get("user_name") or "").strip()

    membro = None
    if guild is not None and hasattr(guild, "get_member"):
        try:
            membro = guild.get_member(int(user_id))
        except (TypeError, ValueError):
            membro = None

    if membro is not None:
        nome = str(
            getattr(membro, "display_name", None)
            or getattr(membro, "global_name", None)
            or getattr(membro, "name", None)
            or nome
        ).strip()

    if nome:
        return f"{nome} (<@{user_id}>)"

    return f"<@{user_id}>"


def formatar_nome_evento_exibicao(nome_evento, tipo_evento="outro"):
    nome = str(nome_evento or "").strip()
    if not nome:
        return "Evento"

    tipo_normalizado = normalizar_tipo_evento(nome)
    if tipo_normalizado:
        return formatar_tipo_evento(tipo_normalizado)

    return nome


def obter_linhas_presentes_evento(guild, evento):
    respostas = list((evento.get("respostas") or {}).values()) if evento else []
    linhas = []

    for resposta in respostas:
        if str(resposta.get("status", "")).strip().lower() != "presente":
            continue

        user_id = resposta.get("user_id")
        if not user_id:
            continue

        membro = formatar_membro_resposta_evento(guild, resposta)
        sufixo = obter_sufixo_conquista_presenca(guild, evento, user_id) if guild and evento else None
        linhas.append(f"{membro} — {sufixo}" if sufixo else membro)

    if not linhas:
        return "Ninguém marcou presença ainda."

    return "\n".join(linhas[:10] + (["Mostrando os primeiros 10 presentes."] if len(linhas) > 10 else []))


def criar_embed_evento(
    nome_evento,
    data_evento,
    horario_evento,
    observacao,
    tipo_evento="outro",
    status_evento="aberto",
    contagens=None,
    imagem_url=None,
    guild=None,
    evento=None,
):
    contagens = contagens or {"presentes": 0, "ausentes": 0, "talvez": 0, "sem_resposta": 0}
    contagens.setdefault("sem_resposta", 0)
    encerrado = str(status_evento).strip().lower() == "encerrado"
    embed = discord.Embed(
        title="🌙 CHAMADO DA NOITE",
        color=AUSENCIA_COLOR,
    )
    meta = obter_meta_conquista(tipo_evento)
    evento_ref = evento or {
        "tipo_evento": tipo_evento,
        "status": status_evento,
        "respostas": {},
    }

    embed.add_field(
        name="📌 Evento",
        value=formatar_nome_evento_exibicao(nome_evento, tipo_evento),
        inline=False,
    )
    embed.add_field(
        name="📅 Data e horário",
        value=f"{data_evento} • {horario_evento}",
        inline=False,
    )
    if meta:
        embed.add_field(
            name="🏆 Conquista vinculada",
            value=f"{meta['cargo_nome']}\nObjetivo: {meta['objetivo']} presenças",
            inline=False,
        )
    embed.add_field(
        name="📊 Parcial",
        value=(
            f"✅ Presenças: {contagens['presentes']}      ❌ Ausências: {contagens['ausentes']}\n"
            f"⚠️ Talvez: {contagens['talvez']}      ⏳ Sem resposta: {contagens['sem_resposta']}"
        ),
        inline=False,
    )
    embed.add_field(
        name="Status",
        value="🟢 Aberto" if not encerrado else "🔒 Encerrado",
        inline=False,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    if imagem_url:
        embed.set_image(url=str(imagem_url).strip())
    return embed

def obter_mencoes_evento(guild_ou_id=None):
    cargo_ids = obter_valor_config(guild_ou_id, "AUSENCIA_MENTION_ROLE_IDS", [])
    mencoes = [f"<@&{cargo_id}>" for cargo_id in cargo_ids if cargo_id]
    return " ".join(mencoes).strip()


def criar_embed_resumo_evento(evento):
    contagens = contar_respostas_evento(evento)
    embed = discord.Embed(
        title="☾ Resumo do Evento — FDN",
        description=(
            "Resumo das respostas registradas para este evento.\n\n"
            f"🌙 Evento:\n{evento.get('nome_evento', 'Evento')}\n\n"
            f"🕒 Quando:\n{evento.get('data', 'Data não informada')} às {evento.get('horario', 'Horário não informado')}\n\n"
            "📊 Respostas:\n"
            f"Presentes: {contagens['presentes']}\n"
            f"Ausentes: {contagens['ausentes']}\n"
            f"Talvez: {contagens['talvez']}"
        ),
        color=AUSENCIA_COLOR,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def dividir_linhas_embed(linhas, limite=1000):
    blocos = []
    bloco_atual = []
    tamanho_atual = 0

    for linha in linhas:
        linha = str(linha or "").strip()
        if not linha:
            continue

        if len(linha) > limite:
            linha = linha[: limite - 3].rstrip() + "..."

        incremento = len(linha) + (1 if bloco_atual else 0)
        if bloco_atual and tamanho_atual + incremento > limite:
            blocos.append("\n".join(bloco_atual))
            bloco_atual = [linha]
            tamanho_atual = len(linha)
            continue

        bloco_atual.append(linha)
        tamanho_atual += incremento

    if bloco_atual:
        blocos.append("\n".join(bloco_atual))

    return blocos


def criar_embed_lista_respostas(titulo, descricao, respostas, vazio, formato="membros", guild=None, evento=None):
    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=AUSENCIA_COLOR,
    )

    linhas = []
    for resposta in respostas[:20]:
        user_id = resposta.get("user_id")
        if not user_id:
            continue

        membro = formatar_membro_resposta_evento(guild, resposta)
        if formato == "ausente":
            motivo = resposta.get("motivo") or "Não informado"
            retorno = resposta.get("retorno") or "Não informado"
            linhas.append(f"{membro} — Motivo: {motivo} — Retorno: {retorno}")
        elif formato == "talvez":
            motivo = resposta.get("motivo") or "Não informado"
            linhas.append(f"{membro} — Motivo: {motivo}")
        else:
            sufixo_conquista = obter_sufixo_conquista_presenca(guild, evento, user_id) if guild and evento else None
            linhas.append(f"{membro} — {sufixo_conquista}" if sufixo_conquista else membro)

    blocos_membros = dividir_linhas_embed(linhas) if linhas else [vazio]
    if len(respostas) > 20:
        blocos_membros.append("Mostrando os primeiros 20 membros.")

    for indice, bloco in enumerate(blocos_membros):
        nome = "Membros" if indice == 0 else "Continuacao"
        embed.add_field(name=nome, value=bloco, inline=False)

    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embeds_lista_respostas_paginadas(
    titulo,
    descricao,
    respostas,
    vazio,
    formato="membros",
    guild=None,
    evento=None,
):
    linhas = []
    for resposta in respostas or []:
        user_id = resposta.get("user_id")
        if not user_id:
            continue

        membro = formatar_membro_resposta_evento(guild, resposta)
        if formato == "ausente":
            motivo = resposta.get("motivo") or "Não informado"
            retorno = resposta.get("retorno") or "Não informado"
            linhas.append(f"{membro} — Motivo: {motivo} — Retorno: {retorno}")
        elif formato == "talvez":
            motivo = resposta.get("motivo") or "Não informado"
            linhas.append(f"{membro} — Motivo: {motivo}")
        else:
            sufixo_conquista = obter_sufixo_conquista_presenca(guild, evento, user_id) if guild and evento else None
            linhas.append(f"{membro} — {sufixo_conquista}" if sufixo_conquista else membro)

    if not linhas:
        return [
            criar_embed_lista_respostas(
                titulo,
                descricao,
                [],
                vazio,
                formato=formato,
                guild=guild,
                evento=evento,
            )
        ]

    embeds = []
    total_paginas = max(1, (len(linhas) + RESPOSTAS_EVENTO_POR_PAGINA - 1) // RESPOSTAS_EVENTO_POR_PAGINA)
    for indice_pagina in range(total_paginas):
        inicio = indice_pagina * RESPOSTAS_EVENTO_POR_PAGINA
        fim = inicio + RESPOSTAS_EVENTO_POR_PAGINA
        linhas_pagina = linhas[inicio:fim]

        embed = discord.Embed(
            title=titulo,
            description=descricao,
            color=AUSENCIA_COLOR,
        )
        for indice_bloco, bloco in enumerate(dividir_linhas_embed(linhas_pagina)):
            embed.add_field(
                name="Membros" if indice_bloco == 0 else "Continuação",
                value=bloco,
                inline=False,
            )
        if total_paginas > 1:
            embed.add_field(name="Página", value=f"{indice_pagina + 1}/{total_paginas}", inline=False)
        embed.set_footer(text=AUSENCIA_FOOTER)
        embeds.append(embed)

    return embeds


async def listar_respostas_presentes_por_cargo(guild, respostas, cargo_id):
    if guild is None or not cargo_id:
        return []

    try:
        cargo_id = int(cargo_id)
    except (TypeError, ValueError):
        return []

    ids_presentes = []
    vistos = set()
    for resposta in respostas or []:
        try:
            user_id = int(resposta.get("user_id"))
        except (TypeError, ValueError):
            continue

        if user_id in vistos:
            continue

        vistos.add(user_id)
        ids_presentes.append(user_id)

    if not ids_presentes:
        return []

    ids_com_cargo = set()
    cargo = guild.get_role(cargo_id) if hasattr(guild, "get_role") else None
    if cargo is not None:
        ids_com_cargo.update(
            int(membro.id)
            for membro in (getattr(cargo, "members", []) or [])
            if getattr(membro, "id", None)
        )

    for user_id in ids_presentes:
        if user_id in ids_com_cargo:
            continue

        membro = guild.get_member(user_id)
        if membro is None and hasattr(guild, "fetch_member"):
            try:
                membro = await guild.fetch_member(user_id)
            except Exception:
                membro = None

        if membro is None:
            continue

        if any(getattr(role, "id", None) == cargo_id for role in getattr(membro, "roles", [])):
            ids_com_cargo.add(user_id)

    return [
        resposta
        for resposta in respostas or []
        if str(resposta.get("user_id") or "").isdigit()
        and int(resposta.get("user_id")) in ids_com_cargo
    ]


def criar_embed_confirmar_encerramento(evento, contagens):
    embed = discord.Embed(
        title="☾ Encerrar Evento",
        color=AUSENCIA_COLOR,
    )
    embed.add_field(name="Evento", value=evento.get("nome_evento", "Evento"), inline=False)
    embed.add_field(name="Presentes", value=str(contagens["presentes"]), inline=True)
    embed.add_field(name="Ausentes", value=str(contagens["ausentes"]), inline=True)
    embed.add_field(name="Talvez", value=str(contagens["talvez"]), inline=True)
    embed.add_field(name="Sem resposta", value=str(contagens["sem_resposta"]), inline=True)
    embed.add_field(
        name="Confirmação",
        value=(
            "Deseja encerrar este evento?\n"
            "O bot vai salvar as listas e o log, sem aplicar advertência ou remover membros."
        ),
        inline=False,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embed_log_evento_encerrado(evento, contagens, advertencias_status, encerrado_por_id):
    embed = discord.Embed(
        title="☾ Evento Encerrado — FDN",
        color=AUSENCIA_COLOR,
    )
    embed.add_field(name="Evento", value=evento.get("nome_evento", "Evento"), inline=False)
    embed.add_field(
        name="Data e horário",
        value=f"{evento.get('data', 'Data não informada')} às {evento.get('horario', 'Horário não informado')}",
        inline=False,
    )
    embed.add_field(name="Presentes", value=str(contagens["presentes"]), inline=True)
    embed.add_field(name="Ausentes", value=str(contagens["ausentes"]), inline=True)
    embed.add_field(name="Talvez", value=str(contagens["talvez"]), inline=True)
    embed.add_field(name="Sem resposta", value=str(contagens["sem_resposta"]), inline=True)
    embed.add_field(name="Advertências", value=formatar_status_advertencias(advertencias_status), inline=True)
    embed.add_field(name="Encerrado por", value=f"<@{encerrado_por_id}>", inline=False)
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embed_advertencia_aplicada(registro):
    quantidade = int(registro.get("quantidade_advertencias") or 0)
    cor = discord.Color.red() if quantidade >= 5 else discord.Color.orange()
    motivo = str(registro.get("motivo") or "").strip() or "Não informado"
    embed = discord.Embed(
        title="☾ Advertência Aplicada",
        description=(
            f"<@{registro.get('user_id')}> foi advertido por não justificar ausência em convocação.\n\n"
            "A advertência será zerada apenas quando o membro marcar presença no próximo evento."
        ),
        color=cor,
    )
    embed.add_field(name="Advertência", value=f"{quantidade} de 5", inline=False)
    embed.add_field(name="Evento", value=registro.get("nome_evento", "Evento"), inline=False)
    embed.add_field(name="Data", value=registro.get("data_evento", "Data não informada"), inline=False)
    embed.add_field(name="Motivo", value=motivo, inline=False)
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed

def criar_embed_advertencia_zerada(user_id, nome_evento, resposta_marcada):
    embed = discord.Embed(
        title="☾ Advertência Zerada",
        description=f"<@{user_id}> teve suas advertências zeradas por marcar presença na convocação do evento.",
        color=AUSENCIA_COLOR,
    )
    embed.add_field(name="Evento", value=nome_evento or "Evento", inline=False)
    embed.add_field(name="Resposta marcada", value=formatar_status_resposta(resposta_marcada), inline=False)
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embed_advertencia_aplicada(registro):
    quantidade = int(registro.get("quantidade_advertencias") or 0)
    cor = discord.Color.red() if quantidade >= 5 else discord.Color.orange()
    motivo = str(registro.get("motivo") or "").strip() or "Não informado"
    embed = discord.Embed(
        title="⚠️・Advertência de Presença",
        description=f"<@{registro.get('user_id')}> recebeu uma advertência por não responder à convocação do evento.",
        color=cor,
    )
    embed.add_field(name="📌 Evento", value=registro.get("nome_evento", "Evento"), inline=False)
    embed.add_field(name="📅 Data", value=registro.get("data_evento", "Data não informada"), inline=False)
    embed.add_field(name="📊 Advertência", value=f"{quantidade} de 5", inline=False)
    embed.add_field(name="📝 Motivo", value=motivo, inline=False)
    embed.add_field(
        name="✅ Como zerar",
        value="A advertência será zerada apenas quando o membro marcar presença no próximo evento.",
        inline=False,
    )
    embed.add_field(
        name="⚠️ Atenção",
        value="Responder as convocações ajuda a staff a organizar os eventos e manter o clã ativo.",
        inline=False,
    )
    if registro.get("visualizada_pelo_membro"):
        embed.add_field(name="✅ Confirmação", value="Membro visualizou o aviso.", inline=False)
    embed.set_footer(text="FDN • Controle de Presença")
    return embed


def criar_embed_advertencia_zerada(user_id, nome_evento, resposta_marcada):
    embed = discord.Embed(
        title="✅・Advertência Zerada",
        description=f"<@{user_id}> teve suas advertências zeradas por marcar presença na convocação do evento.",
        color=AUSENCIA_COLOR,
    )
    embed.add_field(name="📌 Evento", value=nome_evento or "Evento", inline=False)
    embed.add_field(name="📍 Resposta marcada", value=formatar_status_resposta(resposta_marcada), inline=False)
    embed.set_footer(text="FDN • Controle de Presença")
    return embed


def criar_embeds_lista_ausentes_evento(membros_ausentes):
    titulo = "📋 LISTA DOS AUSENTES DE HOJE"
    descricao = "O evento foi encerrado e a lista de presença foi atualizada."

    if not membros_ausentes:
        embed = discord.Embed(
            title=titulo,
            description=descricao,
            color=AUSENCIA_COLOR,
        )
        embed.add_field(
            name="🌙 Membros ausentes",
            value="✅ Todos os membros registraram presença ou justificaram ausência.",
            inline=False,
        )
        embed.set_footer(text=AUSENCIA_FOOTER_SISTEMA)
        return [embed]

    blocos = []
    bloco_atual = []
    tamanho_atual = 0

    for membro in membros_ausentes:
        user_id = membro.get("user_id")
        if not user_id:
            continue

        linha = f"• <@{user_id}>"
        incremento = len(linha) + (1 if bloco_atual else 0)
        if bloco_atual and tamanho_atual + incremento > 1000:
            blocos.append("\n".join(bloco_atual))
            bloco_atual = [linha]
            tamanho_atual = len(linha)
            continue

        bloco_atual.append(linha)
        tamanho_atual += incremento

    if bloco_atual:
        blocos.append("\n".join(bloco_atual))

    embeds = []
    for indice, bloco in enumerate(blocos):
        if indice % 10 == 0:
            embeds.append(
                discord.Embed(
                    title=titulo,
                    description=descricao,
                    color=AUSENCIA_COLOR,
                )
            )

        embed = embeds[-1]
        nome_campo = "🌙 Membros ausentes" if indice == 0 else "Continuação"
        embed.add_field(name=nome_campo, value=bloco, inline=False)

    embeds[-1].add_field(
        name="Aviso",
        value="⚠️ Quem não puder comparecer aos eventos deve justificar ausência. A falta de resposta pode contar como inatividade dentro do clã.",
        inline=False,
    )

    for embed in embeds:
        embed.set_footer(text=AUSENCIA_FOOTER_SISTEMA)

    return embeds


def criar_embeds_lista_sem_resposta_evento(membros_sem_resposta):
    titulo = "📋 LISTA DOS MEMBROS SEM RESPOSTA"
    descricao = "Membros com o cargo Filhos da Noite que não marcaram nada na convocação."

    if not membros_sem_resposta:
        embed = discord.Embed(
            title=titulo,
            description=descricao,
            color=AUSENCIA_COLOR,
        )
        embed.add_field(
            name="🌙 Membros sem resposta",
            value="✅ Todos os membros responderam à convocação.",
            inline=False,
        )
        embed.set_footer(text=AUSENCIA_FOOTER_SISTEMA)
        return [embed]

    blocos = []
    bloco_atual = []
    tamanho_atual = 0

    for membro in membros_sem_resposta:
        user_id = membro.get("user_id")
        if not user_id:
            continue

        linha = f"• <@{user_id}>"
        incremento = len(linha) + (1 if bloco_atual else 0)
        if bloco_atual and tamanho_atual + incremento > 1000:
            blocos.append("\n".join(bloco_atual))
            bloco_atual = [linha]
            tamanho_atual = len(linha)
            continue

        bloco_atual.append(linha)
        tamanho_atual += incremento

    if bloco_atual:
        blocos.append("\n".join(bloco_atual))

    embeds = []
    for indice, bloco in enumerate(blocos or ["Nenhum membro sem resposta."]):
        if indice % 10 == 0:
            embeds.append(
                discord.Embed(
                    title=titulo,
                    description=descricao,
                    color=AUSENCIA_COLOR,
                )
            )

        nome_campo = "🌙 Membros sem resposta" if indice == 0 else "Continuação"
        embeds[-1].add_field(name=nome_campo, value=bloco, inline=False)

    embeds[-1].add_field(
        name="Aviso",
        value="⚠️ Esta lista mostra apenas quem não marcou presença, ausência ou talvez.",
        inline=False,
    )

    for embed in embeds:
        embed.set_footer(text=AUSENCIA_FOOTER_SISTEMA)

    return embeds


async def criar_embeds_presentes_staff_evento(guild, evento):
    respostas_presentes = listar_respostas_por_status(evento, "presente")
    cargo_filhos_id = PRESENCA_EVENTO_CARGO_MEMBRO_ID
    presentes_filhos = await listar_respostas_presentes_por_cargo(
        guild,
        respostas_presentes,
        cargo_filhos_id,
    )

    try:
        cargo_filhos_id = int(cargo_filhos_id)
    except (TypeError, ValueError):
        cargo_filhos_id = None

    cargo_filhos = guild.get_role(cargo_filhos_id) if guild and cargo_filhos_id else None
    nome_cargo_filhos = getattr(cargo_filhos, "name", "Filhos da Noite")
    nome_evento = evento.get("nome_evento", "Evento")

    return [
        criar_embed_lista_respostas(
            f"✅ Presentes com cargo {nome_cargo_filhos} — FDN",
            f"Lista dos membros com o cargo {nome_cargo_filhos} que marcaram presença no evento {nome_evento}.",
            presentes_filhos,
            f"Nenhum membro com o cargo {nome_cargo_filhos} confirmou presença.",
            guild=guild,
            evento=evento,
        )
    ]

    presentes_membro = await listar_respostas_presentes_por_cargo(
        guild,
        respostas_presentes,
        PRESENCA_EVENTO_CARGO_MEMBRO_ID,
    )
    presentes_crepusculo = await listar_respostas_presentes_por_cargo(
        guild,
        respostas_presentes,
        PRESENCA_EVENTO_CARGO_MEMBRO_CREPUSCULO_ID,
    )

    cargo_membro = guild.get_role(PRESENCA_EVENTO_CARGO_MEMBRO_ID) if guild else None
    cargo_crepusculo = guild.get_role(PRESENCA_EVENTO_CARGO_MEMBRO_CREPUSCULO_ID) if guild else None
    nome_cargo_membro = getattr(cargo_membro, "name", "Membro")
    nome_cargo_crepusculo = getattr(cargo_crepusculo, "name", "Membro Crepusculo")
    nome_evento = evento.get("nome_evento", "Evento")

    return [
        criar_embed_lista_respostas(
            "âœ… Presentes â€” FDN",
            f"Lista dos membros que marcaram presenÃ§a no evento {nome_evento}.",
            respostas_presentes,
            "Nenhum membro confirmou presenÃ§a.",
        ),
        criar_embed_lista_respostas(
            f"âœ… Presentes com cargo {nome_cargo_membro} â€” FDN",
            f"Lista dos presentes que tÃªm o cargo {nome_cargo_membro}.",
            presentes_membro,
            f"Nenhum presente tem o cargo {nome_cargo_membro}.",
        ),
        criar_embed_lista_respostas(
            f"âœ… Presentes com cargo {nome_cargo_crepusculo} â€” FDN",
            f"Lista dos presentes que tÃªm o cargo {nome_cargo_crepusculo}.",
            presentes_crepusculo,
            f"Nenhum presente tem o cargo {nome_cargo_crepusculo}.",
        ),
    ]


async def obter_canal_listas_staff(client, guild):
    channel_id = obter_valor_config(guild, "CANAL_CONSELHO_ID") or 1462901201069932544
    if not channel_id:
        return None

    canal = client.get_channel(int(channel_id))
    if canal is not None:
        return canal

    try:
        return await client.fetch_channel(int(channel_id))
    except Exception:
        return None


async def obter_membros_ausentes_staff_evento(guild, evento):
    respostas = evento.get("respostas", {})
    membros_salvos = evento.get("membros_sem_resposta")
    candidatos = list(membros_salvos) if isinstance(membros_salvos, list) else []
    candidatos.extend(
        filtrar_membros_sem_resposta(
            evento,
            await obter_membros_ausencia_automatica(guild),
        )
    )
    for resposta in respostas.values():
        status = str(resposta.get("status", "")).strip().lower()
        if status == "ausente" and resposta.get("registrado_automaticamente"):
            candidatos.append(resposta)

    membros = []
    vistos = set()
    for membro in candidatos:
        user_id = membro.get("user_id")
        if not user_id or str(user_id) in vistos:
            continue

        resposta_atual = respostas.get(str(user_id))
        if resposta_atual:
            status_atual = str(resposta_atual.get("status", "")).strip().lower()
            if not (status_atual == "ausente" and resposta_atual.get("registrado_automaticamente")):
                continue

        vistos.add(str(user_id))
        membros.append(
            {
                "user_id": user_id,
                "user_name": membro.get("user_name")
                or (resposta_atual or {}).get("user_name")
                or str(user_id),
            }
        )

    return membros

    membros = []
    vistos = set()
    for resposta in listar_respostas_por_status(evento, "ausente"):
        user_id = resposta.get("user_id")
        if not user_id or str(user_id) in vistos:
            continue
        vistos.add(str(user_id))
        membros.append(resposta)

    membros_sem_resposta = filtrar_membros_sem_resposta(
        evento,
        await obter_membros_ausencia_automatica(guild),
    )
    for membro in membros_sem_resposta:
        user_id = membro.get("user_id")
        if not user_id or str(user_id) in vistos:
            continue
        vistos.add(str(user_id))
        membros.append(membro)

    return membros


async def editar_ou_enviar_lista_staff_evento(
    client,
    guild,
    evento,
    tipo,
    embeds,
    criar_se_ausente=False,
    mencionar_staff=False,
    forcar_nova=False,
    apagar_antigas=False,
):
    canal = await obter_canal_listas_staff(client, guild)
    if not canal:
        return []

    lotes = [embeds[indice:indice + 10] for indice in range(0, len(embeds), 10)]
    registros = (
        evento.get("mensagens_lista_staff", {}).get(str(tipo), [])
        if isinstance(evento.get("mensagens_lista_staff"), dict)
        else []
    )

    if forcar_nova:
        if apagar_antigas:
            for registro in registros:
                try:
                    canal_antigo = client.get_channel(int(registro.get("channel_id")))
                    if canal_antigo is None:
                        canal_antigo = await client.fetch_channel(int(registro.get("channel_id")))
                    mensagem_antiga = await canal_antigo.fetch_message(int(registro.get("message_id")))
                    await mensagem_antiga.delete()
                except Exception:
                    pass
        registros = []

    if not registros and not criar_se_ausente:
        return []

    cargo_mencao_id = (
        obter_valor_config(getattr(canal, "guild", None), "AUSENCIA_STAFF_ROLE_ID")
        or obter_valor_config(getattr(canal, "guild", None), "CARGO_STAFF_ID")
    )
    mencao_cargo = f"<@&{cargo_mencao_id}>" if cargo_mencao_id else None
    mensagens_salvas = []

    for indice, lote in enumerate(lotes):
        mensagem = None
        registro = registros[indice] if indice < len(registros) else None
        if registro:
            try:
                mensagem = await canal.fetch_message(int(registro.get("message_id")))
            except Exception:
                mensagem = None

        if mensagem:
            try:
                await mensagem.edit(embeds=lote)
                mensagens_salvas.append(mensagem)
                continue
            except Exception:
                pass

        if not criar_se_ausente:
            continue

        try:
            mensagem = await canal.send(
                content=mencao_cargo if mencionar_staff and indice == 0 else None,
                embeds=lote,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            mensagens_salvas.append(mensagem)
        except Exception:
            continue

    for registro_extra in registros[len(lotes):]:
        try:
            mensagem_extra = await canal.fetch_message(int(registro_extra.get("message_id")))
            await mensagem_extra.delete()
        except Exception:
            pass

    evento_atualizado = salvar_mensagens_lista_staff_evento(evento.get("event_id"), tipo, mensagens_salvas)
    if evento_atualizado:
        evento["mensagens_lista_staff"] = evento_atualizado.get("mensagens_lista_staff", {})
    return mensagens_salvas


async def atualizar_listas_staff_evento(client, guild, evento):
    if not evento:
        return

    evento_atual = obter_evento_ausencia(evento.get("event_id")) or evento
    listas = evento_atual.get("mensagens_lista_staff")
    if not isinstance(listas, dict) or not listas:
        return

    embeds_presentes = await criar_embeds_presentes_staff_evento(guild, evento_atual)
    await editar_ou_enviar_lista_staff_evento(
        client,
        guild,
        evento_atual,
        "presentes",
        embeds_presentes,
        criar_se_ausente=False,
    )

    embeds_ausentes = criar_embeds_lista_sem_resposta_evento(
        await obter_membros_ausentes_staff_evento(guild, evento_atual)
    )
    await editar_ou_enviar_lista_staff_evento(
        client,
        guild,
        evento_atual,
        "ausentes",
        embeds_ausentes,
        criar_se_ausente=False,
    )


async def obter_canal_advertencia(client, guild_ou_id=None):
    advertencia_channel_id = obter_valor_config(guild_ou_id, "ADVERTENCIA_CHANNEL_ID")
    if not advertencia_channel_id:
        return None

    canal = client.get_channel(int(advertencia_channel_id))
    if canal is not None:
        return canal

    try:
        return await client.fetch_channel(int(advertencia_channel_id))
    except Exception:
        return None


async def enviar_embed_advertencia(client, guild_ou_id, embed):
    canal = await obter_canal_advertencia(client, guild_ou_id)
    if canal is None:
        return False

    try:
        return await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    except Exception:
        return False


async def enviar_dm_advertencia(client, guild_ou_id, registro):
    user_id = registro.get("user_id")
    if not user_id:
        return False

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False

    guild = guild_ou_id if isinstance(guild_ou_id, discord.Guild) else None
    if guild is None:
        guild_id = getattr(guild_ou_id, "id", guild_ou_id)
        try:
            guild = client.get_guild(int(guild_id))
        except (TypeError, ValueError):
            guild = None

    membro = guild.get_member(user_id) if guild is not None else None
    if membro is None:
        membro = client.get_user(user_id)
    if membro is None:
        try:
            membro = await client.fetch_user(user_id)
        except Exception:
            membro = None

    nome_membro = str(membro) if membro is not None else f"<@{user_id}>"
    if membro is None:
        print(f"Não foi possível enviar DM para {nome_membro}.")
        return False

    evento = str(registro.get("nome_evento") or "Evento")
    data_evento = str(registro.get("data_evento") or "Data não informada")
    motivo = str(registro.get("motivo") or "Não informado")
    quantidade = int(registro.get("quantidade_advertencias") or 0)
    mensagem = (
        "⚠️ Você recebeu uma advertência de presença na FDN.\n\n"
        f"Evento: {evento}\n"
        f"Data: {data_evento}\n"
        f"Motivo: {motivo}\n\n"
        f"Sua advertência atual: {quantidade} de 5.\n\n"
        "Para zerar, responda a próxima convocação marcando presença.\n\n"
        "A staff entende que todos têm vida fora do clã, mas é importante avisar quando não puder participar."
    )

    try:
        await membro.send(mensagem)
        return True
    except Exception:
        print(f"Não foi possível enviar DM para {nome_membro}.")
        return False


async def editar_ou_enviar_embed_advertencia(client, guild_ou_id, registro, embed):
    canal = await obter_canal_advertencia(client, guild_ou_id)
    if canal is None:
        return False

    user_id = registro.get("user_id")
    channel_id = registro.get("advertencia_channel_id")
    message_id = registro.get("advertencia_message_id")

    if user_id:
        try:
            await canal.send(
                f"⚠️ <@{user_id}> você recebeu uma advertência de presença. Leia as informações abaixo.",
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
        except Exception as erro:
            print(f"[ADVERTENCIA] Não consegui mencionar o membro {user_id}: {erro}")

    if channel_id and message_id:
        canal_salvo = canal
        if int(channel_id) != int(getattr(canal, "id", 0)):
            canal_salvo = client.get_channel(int(channel_id))
            if canal_salvo is None:
                try:
                    canal_salvo = await client.fetch_channel(int(channel_id))
                except Exception:
                    canal_salvo = None

        if canal_salvo is not None and hasattr(canal_salvo, "fetch_message"):
            try:
                mensagem = await canal_salvo.fetch_message(int(message_id))
                await mensagem.edit(
                    embed=embed,
                    view=AdvertenciaEntendiView(),
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
                salvar_mensagem_advertencia(user_id, mensagem.channel.id, mensagem.id)
                return mensagem
            except Exception:
                pass

    if user_id and hasattr(canal, "history"):
        mencao_usuario = f"<@{user_id}>"
        try:
            async for mensagem in canal.history(limit=100):
                for embed_salva in mensagem.embeds:
                    texto_embed = " ".join(
                        [
                            str(embed_salva.title or ""),
                            str(embed_salva.description or ""),
                            " ".join(str(campo.value or "") for campo in embed_salva.fields),
                        ]
                    )
                    if mencao_usuario not in texto_embed:
                        continue

                    await mensagem.edit(
                        embed=embed,
                        view=AdvertenciaEntendiView(),
                        allowed_mentions=discord.AllowedMentions(users=True),
                    )
                    salvar_mensagem_advertencia(user_id, mensagem.channel.id, mensagem.id)
                    return mensagem
        except Exception:
            pass

    try:
        mensagem = await canal.send(
            embed=embed,
            view=AdvertenciaEntendiView(),
            allowed_mentions=discord.AllowedMentions(users=True),
        )
    except Exception:
        return False

    salvar_mensagem_advertencia(
        registro.get("user_id"),
        mensagem.channel.id,
        mensagem.id,
    )
    return mensagem


async def processar_zeramento_advertencia(client, guild_ou_id, evento, user_id, user_name, status_resposta):
    if not evento:
        return False

    if str(status_resposta or "").strip().lower() != "presente":
        return False

    registro, zerada = zerar_advertencia_por_resposta(
        user_id=user_id,
        user_name=user_name,
        event_id=evento.get("event_id"),
        nome_evento=evento.get("nome_evento"),
        data_evento=evento.get("data"),
        resposta_marcada=status_resposta,
    )
    if not zerada:
        return False

    embed = criar_embed_advertencia_zerada(
        user_id=user_id,
        nome_evento=evento.get("nome_evento"),
        resposta_marcada=status_resposta,
    )
    await enviar_embed_advertencia(client, guild_ou_id, embed)
    return True


def listar_respostas_por_status(evento, status):
    respostas = evento.get("respostas", {})
    filtradas = []

    for resposta in respostas.values():
        if str(resposta.get("status", "")).strip().lower() == status:
            filtradas.append(resposta)

    return filtradas


def obter_todos_eventos_ausencia(guild_ou_id=None):
    dados = carregar_dados_ausencias()
    eventos = dados.get("eventos", {})
    if not isinstance(eventos, dict):
        return []

    guild_id = getattr(guild_ou_id, "id", guild_ou_id)
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


def listar_eventos_por_status(status, limite=10, guild_ou_id=None):
    status_normalizado = str(status).strip().lower()
    eventos = [
        evento
        for evento in obter_todos_eventos_ausencia(guild_ou_id)
        if str(evento.get("status", "")).strip().lower() == status_normalizado
    ]

    campo_ordenacao = "encerrado_em" if status_normalizado == "encerrado" else "created_at"
    return ordenar_eventos_por_campo(eventos, campo_ordenacao)[:limite]


def obter_evento_aberto_referencia(guild_ou_id=None):
    eventos_abertos = listar_eventos_por_status("aberto", limite=1, guild_ou_id=guild_ou_id)
    return eventos_abertos[0] if eventos_abertos else None


def buscar_evento_por_termo(termo, guild_ou_id=None):
    termo_limpo = str(termo or "").strip()
    if not termo_limpo:
        return None

    termo_normalizado = termo_limpo.casefold()
    eventos = obter_todos_eventos_ausencia(guild_ou_id)

    for evento in eventos:
        if str(evento.get("event_id", "")).strip() == termo_limpo:
            return evento

    encontrados = [
        evento
        for evento in eventos
        if termo_normalizado in str(evento.get("nome_evento", "")).casefold()
    ]
    if not encontrados:
        return None

    return ordenar_eventos_por_campo(encontrados, "created_at")[0]


def criar_embed_painel_ausencia():
    embed = discord.Embed(
        title=AUSENCIA_PANEL_TITLE,
        description=(
            "Use este painel para acompanhar os eventos, presenças e ausências registradas no sistema.\n\n"
            "A staff pode consultar eventos ativos, eventos encerrados e respostas dos membros.\n\n"
            "Horário de funcionamento do bot nesse canal: das 10h às 1h."
        ),
        color=AUSENCIA_COLOR,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embed_eventos_ativos(eventos):
    if not eventos:
        descricao = "Nenhum evento ativo no momento."
    else:
        linhas = ["Eventos que ainda estão abertos para respostas.\n"]
        for indice, evento in enumerate(eventos, start=1):
            contagens = contar_respostas_evento(evento)
            linhas.append(
                f"{indice}. {evento.get('nome_evento', 'Evento')} — {evento.get('data', 'Data não informada')} às {evento.get('horario', 'Horário não informado')}\n"
                f"Presentes: {contagens['presentes']} | Ausentes: {contagens['ausentes']} | Talvez: {contagens['talvez']}"
            )
        descricao = "\n\n".join(linhas)

    embed = discord.Embed(
        title="☾ Eventos Ativos — FDN",
        description=descricao,
        color=AUSENCIA_COLOR,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embed_eventos_encerrados(eventos):
    if not eventos:
        descricao = "Nenhum evento encerrado registrado ainda."
    else:
        linhas = ["Últimos eventos encerrados no sistema.\n"]
        for indice, evento in enumerate(eventos, start=1):
            contagens = contar_respostas_evento(evento)
            encerrado_por_id = evento.get("encerrado_por_id")
            encerrado_por = f"<@{encerrado_por_id}>" if encerrado_por_id else evento.get("encerrado_por_nome", "Não informado")
            linhas.append(
                f"{indice}. {evento.get('nome_evento', 'Evento')} — {evento.get('data', 'Data não informada')} às {evento.get('horario', 'Horário não informado')}\n"
                f"Presentes: {contagens['presentes']} | Ausentes: {contagens['ausentes']} | Talvez: {contagens['talvez']}\n"
                f"Encerrado por: {encerrado_por}"
            )
        descricao = "\n\n".join(linhas)

    embed = discord.Embed(
        title="☾ Eventos Encerrados — FDN",
        description=descricao,
        color=AUSENCIA_COLOR,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embed_evento_encontrado(evento, guild_id=None):
    contagens = calcular_contagens_evento(evento)
    status = "Encerrado" if str(evento.get("status", "")).strip().lower() == "encerrado" else "Aberto"
    criado_por_id = evento.get("criado_por_id")
    criado_por = f"<@{criado_por_id}>" if criado_por_id else evento.get("criado_por_nome", "Não informado")

    embed = discord.Embed(
        title="☾ Evento Encontrado — FDN",
        color=AUSENCIA_COLOR,
    )
    embed.add_field(name="Evento", value=evento.get("nome_evento", "Evento"), inline=False)
    embed.add_field(name="Data", value=evento.get("data", "Data não informada"), inline=True)
    embed.add_field(name="Horário", value=evento.get("horario", "Horário não informado"), inline=True)
    embed.add_field(name="Observação", value=evento.get("observacao") or "Nenhuma observação", inline=False)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Presentes", value=str(contagens["presentes"]), inline=True)
    embed.add_field(name="Ausentes", value=str(contagens["ausentes"]), inline=True)
    embed.add_field(name="Talvez", value=str(contagens["talvez"]), inline=True)
    embed.add_field(name="Sem resposta", value=str(contagens["sem_resposta"]), inline=True)
    embed.add_field(name="Criado por", value=criado_por, inline=True)

    if status == "Encerrado":
        encerrado_por_id = evento.get("encerrado_por_id")
        encerrado_por = f"<@{encerrado_por_id}>" if encerrado_por_id else evento.get("encerrado_por_nome", "Não informado")
        embed.add_field(name="Encerrado por", value=encerrado_por, inline=True)

    channel_id = evento.get("channel_id")
    message_id = evento.get("message_id")
    if guild_id and channel_id and message_id:
        link = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        embed.add_field(name="Mensagem", value=f"[Abrir evento]({link})", inline=False)

    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def obter_historico_membro_eventos(user_id, guild_ou_id=None, limite=5):
    if not user_id:
        return []

    user_id_str = str(user_id)
    historico = []
    eventos = ordenar_eventos_por_campo(obter_todos_eventos_ausencia(guild_ou_id), "created_at")

    for evento in eventos[:limite]:
        resposta = evento.get("respostas", {}).get(user_id_str)
        status = "Sem resposta"
        if resposta:
            status = formatar_status_resposta(str(resposta.get("status", "")).strip().lower() or "Sem resposta")

        historico.append(
            {
                "evento": evento,
                "status": status,
            }
        )

    return historico


def formatar_historico_membro_eventos(historico):
    if not historico:
        return "Nenhum evento encontrado."

    linhas = []
    for indice, item in enumerate(historico, start=1):
        evento = item.get("evento", {})
        linhas.append(f"{indice}. {evento.get('nome_evento', 'Evento')} — {item.get('status', 'Sem resposta')}")

    return "\n".join(linhas)


def criar_embed_registro_membro(evento, resposta, historico=None, advertencias_ativas=0, membro=None, termo=None):
    status_evento = "Encerrado" if evento and str(evento.get("status", "")).strip().lower() == "encerrado" else "Aberto"
    user_id = resposta.get("user_id") if resposta else getattr(membro, "id", None)
    membro_valor = f"<@{user_id}>" if user_id else (termo or "Membro não informado")

    embed = discord.Embed(
        title="☾ Registro de Presença — FDN",
        description="Informações encontradas sobre este membro nos eventos registrados.",
        color=AUSENCIA_COLOR,
    )
    embed.add_field(name="Membro", value=membro_valor, inline=False)
    if evento and resposta:
        embed.add_field(name="Último evento em que respondeu", value=evento.get("nome_evento", "Evento"), inline=False)
        embed.add_field(name="Data", value=evento.get("data", "Data não informada"), inline=True)
        embed.add_field(name="Horário", value=evento.get("horario", "Horário não informado"), inline=True)
        embed.add_field(
            name="Resposta marcada",
            value=formatar_status_resposta(str(resposta.get("status", "")).strip().lower() or "Não informado"),
            inline=True,
        )
        embed.add_field(name="Motivo", value=resposta.get("motivo") or "Não se aplica", inline=False)
        embed.add_field(name="Retorno", value=resposta.get("retorno") or "Não se aplica", inline=False)
        embed.add_field(name="Status do evento", value=status_evento, inline=True)
    else:
        embed.add_field(name="Último evento em que respondeu", value="Nenhum registro encontrado.", inline=False)

    embed.add_field(name="Últimos eventos", value=formatar_historico_membro_eventos(historico or []), inline=False)
    embed.add_field(
        name="Advertências ativas",
        value=f"{advertencias_ativas} de 5" if advertencias_ativas else "Nenhuma advertência ativa.",
        inline=False,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def obter_data_referencia_evento(evento):
    encerrado_em = str(evento.get("encerrado_em", "")).strip()
    if encerrado_em:
        try:
            data = datetime.fromisoformat(encerrado_em.replace("Z", "+00:00"))
            if data.tzinfo is None:
                data = data.replace(tzinfo=FUSO_HORARIO)
            return data.astimezone(FUSO_HORARIO)
        except ValueError:
            pass

    data_evento = str(evento.get("data", "")).strip()
    for formato in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(data_evento, formato).replace(tzinfo=FUSO_HORARIO)
        except ValueError:
            continue

    created_at = str(evento.get("created_at", "")).strip()
    if not created_at:
        return None

    try:
        return datetime.fromisoformat(created_at).astimezone(FUSO_HORARIO)
    except ValueError:
        return None


def calcular_ranking_presenca(periodo, guild_ou_id=None):
    agora = datetime.now(FUSO_HORARIO)
    ranking = {}

    for evento in obter_todos_eventos_ausencia(guild_ou_id):
        data_referencia = obter_data_referencia_evento(evento)
        if not data_referencia:
            continue
        if not evento_deve_contar_pos_reset(evento, guild_ou_id):
            continue

        if periodo == "semana":
            semana_atual = agora.isocalendar()
            semana_evento = data_referencia.isocalendar()
            if semana_evento.year != semana_atual.year or semana_evento.week != semana_atual.week:
                continue
        elif periodo == "mes":
            if data_referencia.year != agora.year or data_referencia.month != agora.month:
                continue

        for resposta in evento.get("respostas", {}).values():
            if str(resposta.get("status", "")).strip().lower() != "presente":
                continue

            user_id = resposta.get("user_id")
            if not user_id:
                continue
            if ranking_deve_ignorar_usuario(user_id):
                continue

            chave = str(user_id)
            item = ranking.setdefault(
                chave,
                {
                    "user_id": user_id,
                    "user_name": resposta.get("user_name", ""),
                    "presencas": 0,
                },
            )
            item["presencas"] += 1

    return sorted(
        ranking.values(),
        key=lambda item: (-item["presencas"], str(item.get("user_name", "")).casefold()),
    )[:10]


def calcular_ranking_ausencia_mes(guild_ou_id=None):
    agora = datetime.now(FUSO_HORARIO)
    ranking = {}

    for evento in obter_todos_eventos_ausencia(guild_ou_id):
        data_referencia = obter_data_referencia_evento(evento)
        if not data_referencia:
            continue
        if not evento_deve_contar_pos_reset(evento, guild_ou_id):
            continue

        if data_referencia.year != agora.year or data_referencia.month != agora.month:
            continue

        for resposta in evento.get("respostas", {}).values():
            if str(resposta.get("status", "")).strip().lower() != "ausente":
                continue

            user_id = resposta.get("user_id")
            if not user_id:
                continue
            if ranking_deve_ignorar_usuario(user_id):
                continue

            chave = str(user_id)
            item = ranking.setdefault(
                chave,
                {
                    "user_id": user_id,
                    "user_name": resposta.get("user_name", ""),
                    "ausencias": 0,
                },
            )
            item["ausencias"] += 1

    return sorted(
        ranking.values(),
        key=lambda item: (-item["ausencias"], str(item.get("user_name", "")).casefold()),
    )[:10]


def criar_embed_ranking_presenca_periodo():
    embed = discord.Embed(
        title="☾ Ranking de Presença — FDN",
        description="Escolha o período que deseja consultar.",
        color=AUSENCIA_COLOR,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embed_ranking_ausencia_mes(ranking):
    if not ranking:
        descricao = "Nenhuma ausência registrada neste mês."
    else:
        linhas = ["Membros que mais registraram ausência nos eventos deste mês.", ""]
        for indice, item in enumerate(ranking, start=1):
            linhas.append(f"{indice}º — <@{item['user_id']}> — {item['ausencias']} ausências")
        descricao = "\n".join(linhas)

    embed = discord.Embed(
        title="📉 Ausências do Mês — FDN",
        description=descricao,
        color=AUSENCIA_COLOR,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


def criar_embed_ranking_presenca(periodo, ranking):
    if periodo == "semana":
        titulo = "🏆 Presença da Semana — FDN"
        descricao_base = "Membros que mais confirmaram presença nos eventos desta semana."
        vazio = "Nenhuma presença registrada nesta semana."
    else:
        titulo = "🏆 Presença do Mês — FDN"
        descricao_base = "Membros que mais confirmaram presença nos eventos deste mês."
        vazio = "Nenhuma presença registrada neste mês."

    if not ranking:
        descricao = vazio
    else:
        linhas = [descricao_base, ""]
        for indice, item in enumerate(ranking, start=1):
            linhas.append(f"{indice}º — <@{item['user_id']}> — {item['presencas']} presenças")
        descricao = "\n".join(linhas)

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=AUSENCIA_COLOR,
    )
    embed.set_footer(text=AUSENCIA_FOOTER)
    return embed


class EventoListaRespostasPaginadaView(discord.ui.View):
    def __init__(self, embeds, autor_id):
        super().__init__(timeout=300)
        self.embeds = embeds or []
        self.autor_id = int(autor_id)
        self.pagina = 0
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        total = len(self.embeds)
        if hasattr(self, "anterior"):
            self.anterior.disabled = total <= 1 or self.pagina <= 0
        if hasattr(self, "proxima"):
            self.proxima.disabled = total <= 1 or self.pagina >= total - 1

    async def _validar(self, interaction: discord.Interaction):
        if interaction.user.id == self.autor_id:
            return True
        await EventoRespostaView.responder_ephemeral(
            interaction,
            "Apenas quem abriu essa lista pode trocar de página.",
        )
        return False

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._validar(interaction):
            return
        self.pagina = max(0, self.pagina - 1)
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self.embeds[self.pagina], view=self)

    @discord.ui.button(label="Próxima", style=discord.ButtonStyle.secondary)
    async def proxima(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._validar(interaction):
            return
        self.pagina = min(len(self.embeds) - 1, self.pagina + 1)
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self.embeds[self.pagina], view=self)


class EventoResumoRespostasView(discord.ui.View):
    def __init__(self, event_id):
        super().__init__(timeout=300)
        self.event_id = str(event_id)

    @staticmethod
    async def responder_ephemeral(interaction, mensagem=None, embed=None, view=None, **extras):
        kwargs = dict(extras)
        if interaction.guild is not None:
            kwargs["ephemeral"] = True
        if mensagem is not None:
            kwargs["content"] = mensagem
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view

        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)

    async def validar_staff_e_evento(self, interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode ver as respostas deste evento.",
            )
            return None

        evento = obter_evento_ausencia(self.event_id)
        if not evento:
            await self.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return None

        return evento

    async def enviar_lista_paginada(
        self,
        interaction,
        titulo,
        descricao,
        respostas,
        vazio,
        formato="membros",
        guild=None,
        evento=None,
    ):
        embeds = criar_embeds_lista_respostas_paginadas(
            titulo,
            descricao,
            respostas,
            vazio,
            formato=formato,
            guild=guild,
            evento=evento,
        )
        view = EventoListaRespostasPaginadaView(embeds, interaction.user.id) if len(embeds) > 1 else None
        await self.responder_ephemeral(interaction, embed=embeds[0], view=view)

    @discord.ui.button(
        label="Ver Presentes",
        emoji="✅",
        style=discord.ButtonStyle.secondary,
    )
    async def ver_presentes(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento = await self.validar_staff_e_evento(interaction)
        if not evento:
            return

        respostas = listar_respostas_por_status(evento, "presente")
        await self.enviar_lista_paginada(
            interaction,
            "✅ Presentes — FDN",
            "Lista de membros que confirmaram presença.",
            respostas,
            "Nenhum membro confirmou presença.",
            guild=interaction.guild,
            evento=evento,
        )

    @discord.ui.button(
        label="Ver Ausentes",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
    )
    async def ver_ausentes(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento = await self.validar_staff_e_evento(interaction)
        if not evento:
            return

        respostas = listar_respostas_por_status(evento, "ausente")
        await self.enviar_lista_paginada(
            interaction,
            "❌ Ausentes — FDN",
            "Lista de membros que informaram ausência.",
            respostas,
            "Nenhum membro informou ausência.",
            formato="ausente",
            guild=interaction.guild,
        )

    @discord.ui.button(
        label="Ver Talvez",
        emoji="⚠️",
        style=discord.ButtonStyle.secondary,
    )
    async def ver_talvez(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento = await self.validar_staff_e_evento(interaction)
        if not evento:
            return

        respostas = listar_respostas_por_status(evento, "talvez")
        await self.enviar_lista_paginada(
            interaction,
            "⚠️ Talvez — FDN",
            "Lista de membros que responderam talvez.",
            respostas,
            "Nenhum membro marcou talvez.",
            formato="talvez",
            guild=interaction.guild,
        )


class AusenciaBuscarMembroResultadoView(discord.ui.View):
    def __init__(self, event_id, user_id, user_name):
        super().__init__(timeout=300)
        self.event_id = str(event_id)
        self.user_id = int(user_id)
        self.user_name = str(user_name)

    @staticmethod
    async def responder_ephemeral(interaction, mensagem=None, embed=None, view=None, **extras):
        await EventoRespostaView.responder_ephemeral(
            interaction,
            mensagem=mensagem,
            embed=embed,
            view=view,
            **extras,
        )

    async def validar_staff_e_evento(self, interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "âŒ Apenas a staff pode usar esta funÃ§Ã£o.",
            )
            return None, None

        evento = obter_evento_ausencia(self.event_id)
        if not evento:
            await self.responder_ephemeral(
                interaction,
                "âŒ NÃ£o consegui encontrar este evento no sistema.",
            )
            return None, None

        resposta = evento.get("respostas", {}).get(str(self.user_id))
        return evento, resposta

        if str(evento.get("status", "")).strip().lower() == "encerrado":
            await self.responder_ephemeral(
                interaction,
                "âš ï¸ Este evento jÃ¡ foi encerrado.",
            )
            return None, None

        resposta = evento.get("respostas", {}).get(str(self.user_id))
        return evento, resposta

    async def validar_staff_e_registro(self, interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar esta função.",
            )
            return None, None

        evento = obter_evento_ausencia(self.event_id)
        if not evento:
            await self.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return None, None

        resposta = evento.get("respostas", {}).get(str(self.user_id))
        if not resposta:
            await self.responder_ephemeral(
                interaction,
                "❌ Nenhum registro encontrado para este membro.",
            )
            return None, None

        return evento, resposta

    @discord.ui.button(
        label="Marcar Presença",
        emoji="✅",
        style=discord.ButtonStyle.secondary,
    )
    async def marcar_presenca(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento_atual, resposta_atual = await self.validar_staff_e_evento(interaction)
        if not evento_atual:
            return

        user_name = (resposta_atual or {}).get("user_name") or self.user_name
        evento, status_anterior = atualizar_resposta_evento_staff(
            self.event_id,
            self.user_id,
            user_name,
            "presente",
            alterado_por_id=interaction.user.id,
            alterado_por_nome=str(interaction.user),
        )
        if not evento:
            await self.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        await EventoRespostaView.editar_mensagem_evento(interaction, evento)
        await atualizar_listas_staff_evento(interaction.client, interaction.guild, evento)
        await self.responder_ephemeral(
            interaction,
            "✅ Presença marcada pela staff com sucesso.",
        )

    @discord.ui.button(
        label="Marcar Ausência",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
    )
    async def marcar_ausencia(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento_atual, resposta_atual = await self.validar_staff_e_evento(interaction)
        if not evento_atual:
            return

        user_name = (resposta_atual or {}).get("user_name") or self.user_name
        await interaction.response.send_modal(
            AusenciaStaffMarcarAusenciaModal(
                self.event_id,
                self.user_id,
                user_name,
            )
        )

    @discord.ui.button(
        label="Remover",
        emoji="🗑️",
        style=discord.ButtonStyle.secondary,
    )
    async def remover(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento_atual, resposta_atual = await self.validar_staff_e_registro(interaction)
        if not evento_atual:
            return

        embed = discord.Embed(
            title="Remover Registro — FDN",
            description=(
                f"Membro: <@{self.user_id}>\n"
                f"Evento: {evento_atual.get('nome_evento', 'Evento')}\n\n"
                "Escolha qual registro deseja remover."
            ),
            color=AUSENCIA_COLOR,
        )
        embed.set_footer(text=AUSENCIA_FOOTER)
        await self.responder_ephemeral(
            interaction,
            embed=embed,
            view=AusenciaRemoverRegistroView(
                self.event_id,
                self.user_id,
                resposta_atual.get("user_name") or self.user_name,
            ),
        )


class AusenciaRemoverRegistroView(discord.ui.View):
    def __init__(self, event_id, user_id, user_name):
        super().__init__(timeout=300)
        self.event_id = str(event_id)
        self.user_id = int(user_id)
        self.user_name = str(user_name)

    async def remover_status(self, interaction: discord.Interaction, status):
        if not membro_eh_staff_ausencia(interaction.user):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar esta função.",
            )
            return

        evento_atual = obter_evento_ausencia(self.event_id)
        if not evento_atual:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        resposta_atual = evento_atual.get("respostas", {}).get(str(self.user_id))
        if not resposta_atual:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Nenhum registro encontrado para este membro.",
            )
            return

        status_atual = str(resposta_atual.get("status", "")).strip().lower()
        if status_atual != status:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                f"❌ Este membro não está marcado como {formatar_status_resposta(status)}.",
            )
            return

        evento, resposta_removida = remover_resposta_evento_staff(
            self.event_id,
            self.user_id,
            status=status,
        )
        if not evento or not resposta_removida:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui remover este registro.",
            )
            return

        if str(evento.get("status", "")).strip().lower() == "encerrado":
            membros_elegiveis = await obter_membros_ausencia_automatica(interaction.guild)
            evento = atualizar_sem_resposta_evento(
                self.event_id,
                len(filtrar_membros_sem_resposta(evento, membros_elegiveis)),
            ) or evento

        await atualizar_listas_staff_evento(interaction.client, interaction.guild, evento)
        await EventoRespostaView.editar_mensagem_evento(interaction, evento)
        mensagem = f"✅ Registro de {formatar_status_resposta(status)} removido de <@{self.user_id}>."
        if interaction.response.is_done():
            await interaction.followup.send(mensagem, ephemeral=True)
        else:
            await interaction.response.edit_message(content=mensagem, embed=None, view=None)

    @discord.ui.button(
        label="Remover Presença",
        emoji="✅",
        style=discord.ButtonStyle.secondary,
    )
    async def remover_presenca(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.remover_status(interaction, "presente")

    @discord.ui.button(
        label="Remover Ausência",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
    )
    async def remover_ausencia(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.remover_status(interaction, "ausente")

    @discord.ui.button(
        label="Remover Talvez",
        emoji="⚠️",
        style=discord.ButtonStyle.secondary,
    )
    async def remover_talvez(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.remover_status(interaction, "talvez")


class AusenciaStaffMarcarAusenciaModal(discord.ui.Modal):
    def __init__(self, event_id, user_id, user_name):
        super().__init__(title="Marcar Ausência")
        self.event_id = str(event_id)
        self.user_id = int(user_id)
        self.user_name = str(user_name)

        self.motivo = discord.ui.TextInput(
            label="Motivo da ausência",
            placeholder="Informe o motivo da ausência.",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500,
        )
        self.tipo_evento = discord.ui.TextInput(
            label="Tipo do evento",
            placeholder="invasao, jogatina, cinema ou outro",
            required=True,
            max_length=20,
            default="outro",
        )
        self.retorno = discord.ui.TextInput(
            label="Previsão de retorno",
            placeholder="Exemplo: volta mais tarde, amanhã, sem previsão...",
            required=False,
            max_length=200,
        )

        self.add_item(self.motivo)
        self.add_item(self.retorno)

    async def on_submit(self, interaction: discord.Interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar esta função.",
            )
            return

        evento_atual = obter_evento_ausencia(self.event_id)
        if not evento_atual:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        if str(self.user_id) not in evento_atual.get("respostas", {}):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Nenhum registro encontrado para este membro.",
            )
            return

        evento, status_anterior = atualizar_resposta_evento_staff(
            self.event_id,
            self.user_id,
            self.user_name,
            "ausente",
            alterado_por_id=interaction.user.id,
            alterado_por_nome=str(interaction.user),
            motivo=self.motivo.value.strip(),
            retorno=self.retorno.value.strip(),
        )
        await atualizar_listas_staff_evento(interaction.client, interaction.guild, evento)
        if not evento:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        await EventoRespostaView.editar_mensagem_evento(interaction, evento)
        await EventoRespostaView.responder_ephemeral(
            interaction,
            "❌ Ausência marcada pela staff com sucesso.",
        )


class AusenciaBuscarMembroModal(discord.ui.Modal):
    def __init__(self, event_id=None):
        super().__init__(title="Buscar Membro")
        self.event_id = str(event_id) if event_id else None

        self.termo = discord.ui.TextInput(
            label="Nome, menção ou ID do membro",
            placeholder="Exemplo: @membro, nome ou ID",
            required=True,
            max_length=100,
        )
        self.add_item(self.termo)

    async def on_submit(self, interaction: discord.Interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar esta função.",
            )
            return

        termo = self.termo.value.strip()
        membro = await resolver_membro_por_termo(interaction.guild, termo)
        user_id = membro.id if membro else extrair_user_id_termo_membro(termo)
        termos_busca = obter_termos_busca_membro(termo, membro)

        evento = obter_evento_ausencia(self.event_id) if self.event_id else obter_evento_aberto_referencia(interaction.guild)
        resposta = None

        if evento:
            respostas_evento = evento.get("respostas", {})
            if user_id:
                resposta = respostas_evento.get(str(user_id))

            if resposta is None and termos_busca:
                for item in respostas_evento.values():
                    nome_normalizado = str(item.get("user_name", "")).strip().casefold()
                    if nome_normalizado in termos_busca or any(termo in nome_normalizado for termo in termos_busca):
                        resposta = item
                        break

        if not evento or (resposta is None and membro is None and not user_id):
            evento, resposta = buscar_registro_membro_eventos(
                user_id=user_id,
                termos_nome=termos_busca,
                guild_ou_id=interaction.guild,
            )

        user_id_historico = user_id or (resposta.get("user_id") if resposta else None)
        historico = obter_historico_membro_eventos(user_id_historico, interaction.guild)
        advertencias_ativas, _ = obter_advertencias_ativas(user_id_historico)

        if not evento and not historico and not advertencias_ativas:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Nenhum registro encontrado para este membro.",
            )
            return

        embed = criar_embed_registro_membro(
            evento,
            resposta,
            historico=historico,
            advertencias_ativas=advertencias_ativas,
            membro=membro,
            termo=termo,
        )
        view = None
        user_id_view = user_id or (resposta.get("user_id") if resposta else None)
        user_name_view = (
            getattr(membro, "display_name", None)
            or getattr(membro, "name", None)
            or (resposta.get("user_name") if resposta else None)
            or termo
        )
        if evento and user_id_view:
            view = AusenciaBuscarMembroResultadoView(
                evento.get("event_id"),
                user_id_view,
                user_name_view,
            )

        await EventoRespostaView.responder_ephemeral(
            interaction,
            embed=embed,
            view=view,
        )


class EventoAusenciaModal(discord.ui.Modal):
    def __init__(self, event_id):
        super().__init__(title="Registrar Ausência")
        self.event_id = str(event_id)

        self.motivo = discord.ui.TextInput(
            label="Motivo da ausência",
            placeholder="Explique brevemente o motivo da ausência.",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500,
        )
        self.retorno = discord.ui.TextInput(
            label="Previsão de retorno",
            placeholder="Exemplo: volto mais tarde, volto amanhã, sem previsão...",
            required=False,
            max_length=200,
        )

        self.add_item(self.motivo)
        self.add_item(self.retorno)

    async def on_submit(self, interaction: discord.Interaction):
        evento_atual = obter_evento_ausencia(self.event_id)
        if not evento_atual:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        if str(evento_atual.get("status", "")).strip().lower() == "encerrado":
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "⚠️ Este evento já foi encerrado. Não é mais possível alterar sua resposta.",
            )
            return

        evento, status_anterior = registrar_resposta_evento(
            self.event_id,
            interaction.user.id,
            str(interaction.user),
            "ausente",
            motivo=self.motivo.value.strip(),
            retorno=self.retorno.value.strip(),
        )
        if not evento:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        await EventoRespostaView.editar_mensagem_evento(interaction, evento)

        if status_anterior:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "🔄 Sua resposta foi atualizada para: Ausente.",
            )
            return

        await EventoRespostaView.responder_ephemeral(
            interaction,
            "❌ Sua ausência foi registrada para este evento.",
        )


class EventoTalvezModal(discord.ui.Modal):
    def __init__(self, event_id):
        super().__init__(title="Registrar Talvez")
        self.event_id = str(event_id)

        self.motivo = discord.ui.TextInput(
            label="Motivo",
            placeholder="Explique brevemente por que talvez participe.",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500,
        )
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        evento_atual = obter_evento_ausencia(self.event_id)
        if not evento_atual:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        if str(evento_atual.get("status", "")).strip().lower() == "encerrado":
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "⚠️ Este evento já foi encerrado. Não é mais possível alterar sua resposta.",
            )
            return

        evento, status_anterior = registrar_resposta_evento(
            self.event_id,
            interaction.user.id,
            str(interaction.user),
            "talvez",
            motivo=self.motivo.value.strip(),
        )
        if not evento:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        await EventoRespostaView.editar_mensagem_evento(interaction, evento)

        if status_anterior:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "🔄 Sua resposta foi atualizada para: Talvez.",
            )
            return

        await EventoRespostaView.responder_ephemeral(
            interaction,
            "⚠️ Sua resposta foi registrada como talvez.",
        )


class AdvertenciaEntendiView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @staticmethod
    async def responder_ephemeral(interaction, mensagem):
        if interaction.response.is_done():
            await interaction.followup.send(mensagem, ephemeral=True)
        else:
            await interaction.response.send_message(mensagem, ephemeral=True)

    @discord.ui.button(
        label="Entendi",
        emoji="✅",
        style=discord.ButtonStyle.secondary,
        custom_id="advertencia_presenca_entendi",
    )
    async def confirmar_visualizacao(self, interaction: discord.Interaction, button: discord.ui.Button):
        mensagem = getattr(interaction, "message", None)
        if mensagem is None:
            await self.responder_ephemeral(interaction, "Não consegui encontrar este aviso.")
            return

        registro = obter_advertencia_por_mensagem(mensagem.id)
        if not registro:
            await self.responder_ephemeral(interaction, "Este aviso não está mais disponível.")
            return

        try:
            user_id = int(registro.get("user_id"))
        except (TypeError, ValueError):
            await self.responder_ephemeral(interaction, "Não consegui identificar o membro deste aviso.")
            return

        if interaction.user.id != user_id:
            await self.responder_ephemeral(interaction, "Esse aviso não é para você.")
            return

        quantidade = int(registro.get("quantidade_advertencias") or 0)
        if str(registro.get("status", "")).strip().lower() != "ativa" or quantidade <= 0:
            await self.responder_ephemeral(interaction, "Este aviso não está mais ativo.")
            return

        registro, confirmada = confirmar_visualizacao_advertencia(user_id, mensagem.id)
        if not confirmada or not registro:
            await self.responder_ephemeral(interaction, "Não consegui salvar sua confirmação.")
            return

        try:
            await mensagem.edit(
                embed=criar_embed_advertencia_aplicada(registro),
                view=AdvertenciaEntendiView(),
            )
        except Exception as erro:
            print(f"[ADVERTENCIA] Erro ao atualizar confirmação | membro={user_id} erro={erro}")

        await self.responder_ephemeral(
            interaction,
            "✅ Obrigado por confirmar. Não esqueça de responder a próxima convocação.",
        )


class EventoRespostaView(discord.ui.View):
    def __init__(self, encerrado=False):
        super().__init__(timeout=None)
        if encerrado:
            for child in self.children:
                if getattr(child, "custom_id", None) in {
                    "ausencia_evento_participar",
                    "ausencia_evento_ausente",
                    "ausencia_evento_talvez",
                    "ausencia_evento_encerrar",
                }:
                    child.disabled = True

    @staticmethod
    async def responder_ephemeral(interaction, mensagem=None, embed=None, view=None, **extras):
        kwargs = dict(extras)
        if interaction.guild is not None:
            kwargs["ephemeral"] = True
        if mensagem is not None:
            kwargs["content"] = mensagem
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view

        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)

    @staticmethod
    async def editar_mensagem_evento(interaction, evento):
        channel_id = evento.get("channel_id")
        message_id = evento.get("message_id")
        if not channel_id or not message_id:
            return

        canal = interaction.client.get_channel(int(channel_id))
        if canal is None:
            try:
                canal = await interaction.client.fetch_channel(int(channel_id))
            except Exception:
                return

        try:
            mensagem_evento = await canal.fetch_message(int(message_id))
        except Exception:
            return

        status_evento = evento.get("status", "aberto")
        encerrado = str(status_evento).strip().lower() == "encerrado"
        contagens = await obter_contagens_evento(interaction.guild, evento)
        embed = criar_embed_evento(
            evento.get("nome_evento", "Evento"),
            evento.get("data", "Data não informada"),
            evento.get("horario", "Horário não informado"),
            evento.get("observacao", ""),
            tipo_evento=evento.get("tipo_evento", "outro"),
            status_evento=status_evento,
            contagens=contagens,
            imagem_url=evento.get("imagem_url"),
            guild=interaction.guild,
            evento=evento,
        )

        try:
            await mensagem_evento.edit(embed=embed, view=EventoRespostaView(encerrado=encerrado))
        except Exception:
            return

    async def registrar_resposta(self, interaction, status, mensagem_inicial, motivo=None, retorno=None):
        evento_atual = obter_evento_ausencia(interaction.message.id)
        if not evento_atual:
            await self.responder_ephemeral(interaction, "❌ Não consegui encontrar este evento no sistema.")
            return

        if str(evento_atual.get("status", "")).strip().lower() == "encerrado":
            await self.responder_ephemeral(
                interaction,
                "⚠️ Este evento já foi encerrado. Não é mais possível alterar sua resposta.",
            )
            return

        evento, status_anterior = registrar_resposta_evento(
            interaction.message.id,
            interaction.user.id,
            str(interaction.user),
            status,
            motivo=motivo,
            retorno=retorno,
        )
        if not evento:
            await self.responder_ephemeral(interaction, "❌ Não consegui encontrar este evento no sistema.")
            return

        await self.editar_mensagem_evento(interaction, evento)

        if status_anterior:
            await self.responder_ephemeral(
                interaction,
                f"🔄 Sua resposta foi atualizada para: {formatar_status_resposta(status)}.",
            )
            return

        await self.responder_ephemeral(interaction, mensagem_inicial)

    @discord.ui.button(
        label="Presença",
        emoji="✅",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="ausencia_evento_participar",
    )
    async def vou_participar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.registrar_resposta(
            interaction,
            "presente",
            "✅ Sua presença foi registrada para este evento.",
        )

    @discord.ui.button(
        label="Ausência",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="ausencia_evento_ausente",
    )
    async def estarei_ausente(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento_atual = obter_evento_ausencia(interaction.message.id)
        if not evento_atual:
            await self.responder_ephemeral(interaction, "❌ Não consegui encontrar este evento no sistema.")
            return

        if str(evento_atual.get("status", "")).strip().lower() == "encerrado":
            await self.responder_ephemeral(
                interaction,
                "⚠️ Este evento já foi encerrado. Não é mais possível alterar sua resposta.",
            )
            return

        try:
            await interaction.response.send_modal(EventoAusenciaModal(interaction.message.id))
        except Exception as erro:
            print(f"[EVENTO] Erro ao abrir modal de ausência | evento={interaction.message.id} usuario={interaction.user.id} erro={erro}")
            await self.responder_ephemeral(
                interaction,
                "❌ Não consegui abrir o formulário de ausência agora.",
            )

    @discord.ui.button(
        label="Talvez",
        emoji="⚠️",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="ausencia_evento_talvez",
    )
    async def talvez_participe(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento_atual = obter_evento_ausencia(interaction.message.id)
        if not evento_atual:
            await self.responder_ephemeral(interaction, "❌ Não consegui encontrar este evento no sistema.")
            return

        if str(evento_atual.get("status", "")).strip().lower() == "encerrado":
            await self.responder_ephemeral(
                interaction,
                "⚠️ Este evento já foi encerrado. Não é mais possível alterar sua resposta.",
            )
            return

        try:
            await interaction.response.send_modal(EventoTalvezModal(interaction.message.id))
        except Exception as erro:
            print(f"[EVENTO] Erro ao abrir modal de talvez | evento={interaction.message.id} usuario={interaction.user.id} erro={erro}")
            await self.responder_ephemeral(
                interaction,
                "❌ Não consegui abrir o formulário de talvez agora.",
            )

    @discord.ui.button(
        label="Respostas",
        emoji="📋",
        style=discord.ButtonStyle.secondary,
        row=1,
        custom_id="ausencia_evento_ver_respostas",
    )
    async def ver_respostas(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode ver as respostas deste evento.",
            )
            return

        evento = obter_evento_ausencia(interaction.message.id)
        if not evento:
            await self.responder_ephemeral(interaction, "❌ Não consegui encontrar este evento no sistema.")
            return

        embed = criar_embed_resumo_evento(evento)
        await self.responder_ephemeral(
            interaction,
            embed=embed,
            view=EventoResumoRespostasView(interaction.message.id),
        )

    @discord.ui.button(
        label="Encerrar",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        row=1,
        custom_id="ausencia_evento_encerrar",
    )
    async def encerrar_evento(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode encerrar este evento.",
            )
            return

        evento = obter_evento_ausencia(interaction.message.id)
        if not evento:
            await self.responder_ephemeral(interaction, "❌ Não consegui encontrar este evento no sistema.")
            return

        if str(evento.get("status", "")).strip().lower() == "encerrado":
            await self.responder_ephemeral(interaction, "⚠️ Este evento já foi encerrado.")
            return

        membros_elegiveis = await obter_membros_ausencia_automatica(interaction.guild)
        contagens = calcular_contagens_evento(evento, membros_elegiveis)
        await self.responder_ephemeral(
            interaction,
            embed=criar_embed_confirmar_encerramento(evento, contagens),
            view=EventoEncerrarConfirmView(
                interaction.message.id,
                advertencia_automatica=(
                    evento_permite_advertencia_automatica(evento)
                    and not ADVERTENCIA_AUTOMATICA_PAUSADA
                ),
            ),
        )


MOTIVOS_ADVERTENCIA_ENCERRAMENTO = {
    "nao_respondeu": "Nao respondeu a convocacao.",
    "nao_justificou": "Nao justificou ausencia.",
    "foi_nao_marcou": "Foi ao evento, mas nao marcou presenca.",
}
MOTIVO_ADVERTENCIA_OUTRO = "outro"
MOTIVO_ADVERTENCIA_NAO_APLICAR = "nao_aplicar"
REVISAO_ADVERTENCIA_POR_PAGINA = 15
RESPOSTAS_EVENTO_POR_PAGINA = 20


def limitar_texto_revisao_advertencia(valor, limite=100):
    texto = str(valor or "").strip()
    if len(texto) <= limite:
        return texto
    if limite <= 3:
        return texto[:limite]
    return texto[: limite - 3].rstrip() + "..."


def obter_user_id_revisao_advertencia(membro):
    try:
        return str(int(membro.get("user_id")))
    except (TypeError, ValueError, AttributeError):
        return ""


def obter_nome_revisao_advertencia(membro):
    user_id = obter_user_id_revisao_advertencia(membro)
    nome = str(membro.get("user_name") or "").strip()
    return nome or f"Membro {user_id}"


class EventoAdvertenciaMembroSelect(discord.ui.Select):
    def __init__(self, view_ref):
        self.view_ref = view_ref
        options = []
        for membro in view_ref.membros_pagina_atual():
            user_id = obter_user_id_revisao_advertencia(membro)
            if not user_id:
                continue
            decisao = view_ref.decisoes.get(user_id, {})
            options.append(
                discord.SelectOption(
                    label=limitar_texto_revisao_advertencia(obter_nome_revisao_advertencia(membro), 100),
                    value=user_id,
                    description=limitar_texto_revisao_advertencia(view_ref.resumo_decisao(user_id), 100),
                    default=user_id == view_ref.user_id_selecionado,
                )
            )
        super().__init__(
            placeholder="Selecione um membro para revisar",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.user_id_selecionado = self.values[0]
        await self.view_ref.atualizar_interacao(interaction)


class EventoAdvertenciaMotivoSelect(discord.ui.Select):
    def __init__(self, view_ref):
        self.view_ref = view_ref
        decisao = view_ref.decisoes.get(view_ref.user_id_selecionado, {})
        acao_atual = decisao.get("acao")
        options = [
            discord.SelectOption(
                label="Nao respondeu a convocacao",
                value="nao_respondeu",
                description="Advertir por nao responder ao evento.",
                default=acao_atual == "nao_respondeu",
            ),
            discord.SelectOption(
                label="Nao justificou ausencia",
                value="nao_justificou",
                description="Advertir por nao justificar a ausencia.",
                default=acao_atual == "nao_justificou",
            ),
            discord.SelectOption(
                label="Foi, mas nao marcou presenca",
                value="foi_nao_marcou",
                description="Advertir porque participou e nao marcou presenca.",
                default=acao_atual == "foi_nao_marcou",
            ),
            discord.SelectOption(
                label="Outro motivo",
                value=MOTIVO_ADVERTENCIA_OUTRO,
                description="Escrever um motivo individual.",
                default=acao_atual == MOTIVO_ADVERTENCIA_OUTRO,
            ),
            discord.SelectOption(
                label="Nao aplicar advertencia",
                value=MOTIVO_ADVERTENCIA_NAO_APLICAR,
                description="Manter sem advertencia neste encerramento.",
                default=acao_atual == MOTIVO_ADVERTENCIA_NAO_APLICAR,
            ),
        ]
        super().__init__(
            placeholder="Escolha o motivo para o membro selecionado",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        valor = self.values[0]
        user_id = self.view_ref.user_id_selecionado
        if not user_id:
            await interaction.response.send_message("Selecione um membro primeiro.", ephemeral=True)
            return

        if valor == MOTIVO_ADVERTENCIA_OUTRO:
            await interaction.response.send_modal(EventoAdvertenciaOutroMotivoModal(self.view_ref, user_id))
            return

        if valor == MOTIVO_ADVERTENCIA_NAO_APLICAR:
            self.view_ref.definir_decisao(user_id, MOTIVO_ADVERTENCIA_NAO_APLICAR, None)
        else:
            self.view_ref.definir_decisao(user_id, valor, MOTIVOS_ADVERTENCIA_ENCERRAMENTO[valor])

        await self.view_ref.atualizar_interacao(interaction)


class EventoAdvertenciaOutroMotivoModal(discord.ui.Modal):
    def __init__(self, view_ref, user_id):
        super().__init__(title="Motivo da advertencia")
        self.view_ref = view_ref
        self.user_id = str(user_id)
        self.motivo = discord.ui.TextInput(
            label="Motivo individual",
            placeholder="Exemplo: Foi ao evento, mas nao marcou presenca.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500,
        )
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        motivo = str(self.motivo.value or "").strip()
        self.view_ref.definir_decisao(self.user_id, MOTIVO_ADVERTENCIA_OUTRO, motivo)
        await self.view_ref.atualizar_interacao(interaction)


class EventoAdvertenciaPaginaButton(discord.ui.Button):
    def __init__(self, view_ref, delta):
        self.view_ref = view_ref
        self.delta = int(delta)
        proxima = delta > 0
        disabled = (
            view_ref.total_paginas() <= 1
            or (not proxima and view_ref.pagina <= 0)
            or (proxima and view_ref.pagina >= view_ref.total_paginas() - 1)
        )
        super().__init__(
            label="Proxima" if proxima else "Anterior",
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.pagina = max(0, min(self.view_ref.total_paginas() - 1, self.view_ref.pagina + self.delta))
        await self.view_ref.atualizar_interacao(interaction)


class EventoAdvertenciaConfirmarButton(discord.ui.Button):
    def __init__(self, view_ref):
        self.view_ref = view_ref
        super().__init__(
            label="Confirmar aplicacao",
            style=discord.ButtonStyle.success,
            disabled=view_ref.tem_pendentes(),
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.tem_pendentes():
            await interaction.response.send_message(
                f"Ainda existem {self.view_ref.quantidade_pendentes()} membro(s) pendente(s) de revisao.",
                ephemeral=True,
            )
            return

        self.view_ref.desabilitar_componentes()
        await interaction.response.defer(ephemeral=True)
        try:
            if interaction.message:
                await interaction.message.edit(embed=self.view_ref.criar_embed(finalizando=True), view=self.view_ref)
        except Exception:
            pass

        finalizador = EventoEncerrarConfirmView(self.view_ref.event_id, advertencia_automatica=True)
        await finalizador.finalizar_encerramento(
            interaction,
            aplicar_advertencias=True,
            motivos_advertencias=self.view_ref.motivos_para_finalizacao(),
        )
        self.view_ref.stop()


class EventoAdvertenciaCancelarButton(discord.ui.Button):
    def __init__(self, view_ref):
        self.view_ref = view_ref
        super().__init__(
            label="Cancelar",
            style=discord.ButtonStyle.secondary,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.stop()
        await interaction.response.edit_message(content="Revisao de advertencias cancelada.", embed=None, view=None)


class EventoAdvertenciaRevisaoView(discord.ui.View):
    def __init__(self, event_id, membros_sem_resposta):
        super().__init__(timeout=600)
        self.event_id = str(event_id)
        self.membros_sem_resposta = [
            membro for membro in (membros_sem_resposta or []) if obter_user_id_revisao_advertencia(membro)
        ]
        self.decisoes = {
            obter_user_id_revisao_advertencia(membro): {"acao": "pendente", "motivo": None}
            for membro in self.membros_sem_resposta
        }
        self.user_id_selecionado = None
        self.pagina = 0
        self.mensagem = None
        self.montar_componentes()

    def total_paginas(self):
        if not self.membros_sem_resposta:
            return 1
        return max(1, (len(self.membros_sem_resposta) + REVISAO_ADVERTENCIA_POR_PAGINA - 1) // REVISAO_ADVERTENCIA_POR_PAGINA)

    def membros_pagina_atual(self):
        inicio = self.pagina * REVISAO_ADVERTENCIA_POR_PAGINA
        fim = inicio + REVISAO_ADVERTENCIA_POR_PAGINA
        return self.membros_sem_resposta[inicio:fim]

    def quantidade_pendentes(self):
        return sum(1 for decisao in self.decisoes.values() if decisao.get("acao") == "pendente")

    def tem_pendentes(self):
        return self.quantidade_pendentes() > 0

    def definir_decisao(self, user_id, acao, motivo):
        self.decisoes[str(user_id)] = {"acao": acao, "motivo": motivo}

    def resumo_decisao(self, user_id):
        decisao = self.decisoes.get(str(user_id), {})
        acao = decisao.get("acao")
        if acao == "pendente":
            return "Pendente"
        if acao == MOTIVO_ADVERTENCIA_NAO_APLICAR:
            return "Nao aplicar advertencia"
        return f"Advertir: {limitar_texto_revisao_advertencia(decisao.get('motivo'), 70)}"

    def motivos_para_finalizacao(self):
        motivos = {}
        for user_id, decisao in self.decisoes.items():
            if decisao.get("acao") == MOTIVO_ADVERTENCIA_NAO_APLICAR:
                motivos[str(user_id)] = None
            else:
                motivos[str(user_id)] = decisao.get("motivo") or MOTIVOS_ADVERTENCIA_ENCERRAMENTO["nao_respondeu"]
        return motivos

    def montar_componentes(self):
        self.clear_items()
        if self.membros_pagina_atual():
            self.add_item(EventoAdvertenciaMembroSelect(self))
        if self.user_id_selecionado:
            self.add_item(EventoAdvertenciaMotivoSelect(self))
        if self.total_paginas() > 1:
            self.add_item(EventoAdvertenciaPaginaButton(self, -1))
            self.add_item(EventoAdvertenciaPaginaButton(self, 1))
        self.add_item(EventoAdvertenciaConfirmarButton(self))
        self.add_item(EventoAdvertenciaCancelarButton(self))

    def desabilitar_componentes(self):
        for item in self.children:
            item.disabled = True

    def criar_embed(self, finalizando=False):
        evento = obter_evento_ausencia(self.event_id) or {}
        pendentes = self.quantidade_pendentes()
        aplicar = sum(
            1
            for decisao in self.decisoes.values()
            if decisao.get("acao") not in {"pendente", MOTIVO_ADVERTENCIA_NAO_APLICAR}
        )
        ignorar = sum(1 for decisao in self.decisoes.values() if decisao.get("acao") == MOTIVO_ADVERTENCIA_NAO_APLICAR)
        embed = discord.Embed(
            title="Revisao de Advertencias",
            description=(
                "Revise cada membro antes de encerrar o evento.\n"
                "Escolha um motivo individual ou marque para nao aplicar advertencia."
            ),
            color=AUSENCIA_COLOR,
        )
        embed.add_field(name="Evento", value=str(evento.get("nome_evento") or "Evento"), inline=False)
        embed.add_field(
            name="Resumo",
            value=f"Pendentes: {pendentes}\nAdvertir: {aplicar}\nNao aplicar: {ignorar}",
            inline=True,
        )
        embed.add_field(name="Pagina", value=f"{self.pagina + 1}/{self.total_paginas()}", inline=True)

        linhas = []
        for membro in self.membros_pagina_atual():
            user_id = obter_user_id_revisao_advertencia(membro)
            if not user_id:
                continue
            linhas.append(f"<@{user_id}> - {self.resumo_decisao(user_id)}")
        embed.add_field(
            name="Membros desta pagina",
            value=limitar_texto_revisao_advertencia("\n".join(linhas), 1024) or "Nenhum membro pendente.",
            inline=False,
        )
        if self.user_id_selecionado:
            embed.add_field(
                name="Selecionado",
                value=f"<@{self.user_id_selecionado}>\n{self.resumo_decisao(self.user_id_selecionado)}",
                inline=False,
            )
        if finalizando:
            embed.add_field(name="Status", value="Finalizando encerramento e aplicando as decisoes.", inline=False)
        elif pendentes:
            embed.add_field(
                name="Proxima etapa",
                value="Defina uma decisao para todos os membros pendentes para liberar a confirmacao.",
                inline=False,
            )
        else:
            embed.add_field(name="Proxima etapa", value="Todos revisados. Clique em Confirmar aplicacao.", inline=False)
        embed.set_footer(text=AUSENCIA_FOOTER)
        return embed

    async def atualizar_interacao(self, interaction: discord.Interaction):
        self.mensagem = getattr(interaction, "message", None) or self.mensagem
        self.montar_componentes()
        embed = self.criar_embed()
        if not interaction.response.is_done():
            try:
                await interaction.response.edit_message(embed=embed, view=self)
                return
            except Exception:
                pass
            if self.mensagem:
                try:
                    await interaction.response.defer(ephemeral=True)
                    await self.mensagem.edit(embed=embed, view=self)
                    return
                except Exception:
                    pass
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
                return
        if self.mensagem:
            try:
                await self.mensagem.edit(embed=embed, view=self)
                return
            except Exception:
                pass
        await interaction.followup.send(embed=embed, view=self, ephemeral=True)


class EventoEncerrarConfirmView(discord.ui.View):
    def __init__(self, event_id, advertencia_automatica=True):
        super().__init__(timeout=180)
        self.event_id = str(event_id)
        self.advertencia_automatica = bool(advertencia_automatica)
        for item in list(self.children):
            if getattr(item, "label", None) == "Encerrar sem advertir":
                self.remove_item(item)

    async def abrir_revisao_advertencias(self, interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "âŒ Apenas a staff pode encerrar este evento.",
            )
            return

        evento_atual = obter_evento_ausencia(self.event_id)
        if not evento_atual:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "âŒ NÃ£o consegui encontrar este evento no sistema.",
            )
            return

        if str(evento_atual.get("status", "")).strip().lower() == "encerrado":
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "âš ï¸ Este evento jÃ¡ foi encerrado.",
            )
            return

        membros_elegiveis = await obter_membros_ausencia_automatica(interaction.guild)
        membros_sem_resposta = filtrar_membros_sem_resposta(evento_atual, membros_elegiveis)
        if not membros_sem_resposta:
            await self.finalizar_encerramento(interaction, aplicar_advertencias=True, motivos_advertencias={})
            return

        view = EventoAdvertenciaRevisaoView(self.event_id, membros_sem_resposta)
        view.mensagem = getattr(interaction, "message", None)
        await interaction.response.edit_message(embed=view.criar_embed(), view=view)

    async def editar_mensagem_evento_encerrado(self, interaction, evento):
        channel_id = evento.get("channel_id")
        message_id = evento.get("message_id")
        if not channel_id or not message_id:
            return

        canal = interaction.client.get_channel(int(channel_id))
        if canal is None:
            try:
                canal = await interaction.client.fetch_channel(int(channel_id))
            except Exception:
                return

        try:
            mensagem_evento = await canal.fetch_message(int(message_id))
        except Exception:
            return

        embed = criar_embed_evento(
            evento.get("nome_evento", "Evento"),
            evento.get("data", "Data não informada"),
            evento.get("horario", "Horário não informado"),
            evento.get("observacao", ""),
            tipo_evento=evento.get("tipo_evento", "outro"),
            status_evento="encerrado",
            contagens=await obter_contagens_evento(interaction.guild, evento),
            imagem_url=evento.get("imagem_url"),
            guild=interaction.guild,
            evento=evento,
        )

        try:
            await mensagem_evento.edit(embed=embed, view=EventoRespostaView(encerrado=True))
        except Exception:
            return

    async def enviar_lista_ausentes_evento_encerrado(self, interaction, evento, membros_ausentes):
        membros_lista = await obter_membros_ausentes_staff_evento(interaction.guild, evento)
        embeds = criar_embeds_lista_sem_resposta_evento(membros_lista)
        await editar_ou_enviar_lista_staff_evento(
            interaction.client,
            interaction.guild,
            evento,
            "ausentes",
            embeds,
            criar_se_ausente=True,
            mencionar_staff=True,
        )

    async def enviar_lista_presentes_evento_encerrado(self, interaction, evento):
        embeds = await criar_embeds_presentes_staff_evento(interaction.guild, evento)
        await editar_ou_enviar_lista_staff_evento(
            interaction.client,
            interaction.guild,
            evento,
            "presentes",
            embeds,
            criar_se_ausente=True,
        )
        return

    async def reenviar_listas_evento_encerrado(self, interaction, evento, apagar_antigas=False):
        embeds_presentes = await criar_embeds_presentes_staff_evento(interaction.guild, evento)
        mensagens_presentes = await editar_ou_enviar_lista_staff_evento(
            interaction.client,
            interaction.guild,
            evento,
            "presentes",
            embeds_presentes,
            criar_se_ausente=True,
            forcar_nova=True,
            apagar_antigas=apagar_antigas,
        )

        membros_sem_resposta = await obter_membros_ausentes_staff_evento(interaction.guild, evento)
        embeds_sem_resposta = criar_embeds_lista_sem_resposta_evento(membros_sem_resposta)
        mensagens_sem_resposta = await editar_ou_enviar_lista_staff_evento(
            interaction.client,
            interaction.guild,
            evento,
            "ausentes",
            embeds_sem_resposta,
            criar_se_ausente=True,
            mencionar_staff=True,
            forcar_nova=True,
            apagar_antigas=apagar_antigas,
        )

        return len(mensagens_presentes), len(mensagens_sem_resposta), len(membros_sem_resposta)

        channel_id = obter_valor_config(interaction.guild, "CANAL_CONSELHO_ID") or 1462901201069932544
        if not channel_id:
            return

        canal = interaction.client.get_channel(int(channel_id))
        if canal is None:
            try:
                canal = await interaction.client.fetch_channel(int(channel_id))
            except Exception:
                return

        respostas_presentes = listar_respostas_por_status(evento, "presente")
        presentes_membro = await listar_respostas_presentes_por_cargo(
            interaction.guild,
            respostas_presentes,
            PRESENCA_EVENTO_CARGO_MEMBRO_ID,
        )
        presentes_crepusculo = await listar_respostas_presentes_por_cargo(
            interaction.guild,
            respostas_presentes,
            PRESENCA_EVENTO_CARGO_MEMBRO_CREPUSCULO_ID,
        )

        cargo_membro = interaction.guild.get_role(PRESENCA_EVENTO_CARGO_MEMBRO_ID) if interaction.guild else None
        cargo_crepusculo = (
            interaction.guild.get_role(PRESENCA_EVENTO_CARGO_MEMBRO_CREPUSCULO_ID)
            if interaction.guild else None
        )
        nome_cargo_membro = getattr(cargo_membro, "name", "Membro")
        nome_cargo_crepusculo = getattr(cargo_crepusculo, "name", "Membro Crepusculo")
        nome_evento = evento.get("nome_evento", "Evento")

        embeds = [
            criar_embed_lista_respostas(
                "✅ Presentes — FDN",
                f"Lista dos membros que marcaram presença no evento {nome_evento}.",
                respostas_presentes,
                "Nenhum membro confirmou presença.",
                guild=interaction.guild,
                evento=evento,
            ),
            criar_embed_lista_respostas(
                f"✅ Presentes com cargo {nome_cargo_membro} — FDN",
                f"Lista dos presentes que têm o cargo {nome_cargo_membro}.",
                presentes_membro,
                f"Nenhum presente tem o cargo {nome_cargo_membro}.",
                guild=interaction.guild,
                evento=evento,
            ),
            criar_embed_lista_respostas(
                f"✅ Presentes com cargo {nome_cargo_crepusculo} — FDN",
                f"Lista dos presentes que têm o cargo {nome_cargo_crepusculo}.",
                presentes_crepusculo,
                f"Nenhum presente tem o cargo {nome_cargo_crepusculo}.",
                guild=interaction.guild,
                evento=evento,
            ),
        ]

        try:
            await canal.send(
                embed=embeds[0],
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except Exception:
            return

    async def aplicar_advertencias_evento_encerrado(self, interaction, evento, membros_ausentes, motivos_por_usuario=None):
        aplicadas = 0
        if isinstance(motivos_por_usuario, dict):
            motivos_por_usuario = {str(user_id): motivo for user_id, motivo in motivos_por_usuario.items()}
        else:
            motivos_por_usuario = None

        for membro in membros_ausentes or []:
            user_id = membro.get("user_id")
            user_name = membro.get("user_name")
            if not user_id or not user_name:
                continue

            resposta = evento.get("respostas", {}).get(str(user_id))
            if not resposta or not resposta.get("registrado_automaticamente"):
                continue

            motivo = None
            if motivos_por_usuario is not None:
                motivo = motivos_por_usuario.get(str(user_id))
                if not motivo:
                    continue

            argumentos_advertencia = {}
            if motivo:
                argumentos_advertencia["motivo"] = motivo

            registro, aplicada = aplicar_advertencia_automatica(
                user_id=user_id,
                user_name=user_name,
                event_id=evento.get("event_id"),
                nome_evento=evento.get("nome_evento"),
                data_evento=evento.get("data"),
                **argumentos_advertencia,
            )
            if not aplicada or not registro:
                continue

            embed = criar_embed_advertencia_aplicada(registro)
            await editar_ou_enviar_embed_advertencia(interaction.client, interaction.guild, registro, embed)
            # Advertencias nao sao mais enviadas por DM; o aviso fica apenas no canal configurado.
            aplicadas += 1

        return aplicadas

    async def enviar_log_evento_encerrado(self, interaction, evento, contagens, advertencias_status):
        canal_logs_id = obter_valor_config(interaction.guild, "CANAL_LOGS_ID")
        if not canal_logs_id:
            return False

        canal_logs = interaction.client.get_channel(int(canal_logs_id))
        if canal_logs is None:
            try:
                canal_logs = await interaction.client.fetch_channel(int(canal_logs_id))
            except Exception:
                return False

        embed = criar_embed_log_evento_encerrado(
            evento,
            contagens,
            advertencias_status,
            interaction.user.id,
        )
        try:
            await canal_logs.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
            return True
        except Exception:
            return False

    async def finalizar_encerramento(self, interaction, aplicar_advertencias, motivos_advertencias=None):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True, thinking=True)
            except discord.HTTPException:
                pass

        if not membro_eh_staff_ausencia(interaction.user):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode encerrar este evento.",
            )
            return

        evento_atual = obter_evento_ausencia(self.event_id)
        if not evento_atual:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        if str(evento_atual.get("status", "")).strip().lower() == "encerrado":
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "⚠️ Este evento já foi encerrado.",
            )
            return

        membros_elegiveis = await obter_membros_ausencia_automatica(interaction.guild)
        membros_sem_resposta = filtrar_membros_sem_resposta(evento_atual, membros_elegiveis)
        contagens_antes = calcular_contagens_evento(evento_atual, membros_elegiveis)
        advertencias_status = "desativadas"

        evento, ja_encerrado, ausencias_automaticas = encerrar_evento_ausencia(
            self.event_id,
            interaction.user.id,
            str(interaction.user),
            membros_ausentes_automaticos=membros_sem_resposta,
            registrar_ausencias_automaticas=False,
            advertencias_aplicadas=False,
            sem_resposta=contagens_antes["sem_resposta"],
        )
        if not evento:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar este evento no sistema.",
            )
            return

        if ja_encerrado:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "⚠️ Este evento já foi encerrado.",
            )
            return

        await self.editar_mensagem_evento_encerrado(interaction, evento)
        resultado_conquistas = await self.processar_conquistas_evento_encerrado(interaction.guild, evento)
        await self.enviar_lista_presentes_evento_encerrado(interaction, evento)
        await self.enviar_lista_ausentes_evento_encerrado(
            interaction,
            evento,
            listar_respostas_por_status(evento, "ausente"),
        )
        await self.enviar_resumo_conquistas_evento(interaction.guild, evento, resultado_conquistas)
        await self.enviar_log_evento_encerrado(interaction, evento, contagens_antes, advertencias_status)
        await EventoRespostaView.responder_ephemeral(
            interaction,
            "✅ Evento encerrado com sucesso.",
        )

    @discord.ui.button(
        label="Confirmar encerramento",
        emoji="✅",
        style=discord.ButtonStyle.secondary,
    )
    async def confirmar_encerramento(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finalizar_encerramento(interaction, aplicar_advertencias=False)

    @discord.ui.button(
        label="Encerrar sem advertir",
        emoji="⚠️",
        style=discord.ButtonStyle.secondary,
    )
    async def encerrar_sem_advertir(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finalizar_encerramento(interaction, aplicar_advertencias=False)

    @discord.ui.button(
        label="Cancelar",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
    )
    async def cancelar_encerramento(self, interaction: discord.Interaction, button: discord.ui.Button):
        await EventoRespostaView.responder_ephemeral(
            interaction,
            "Encerramento cancelado.",
        )


class AusenciaBuscarEventoModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Buscar Evento")
        self.termo = discord.ui.TextInput(
            label="Nome ou ID do evento",
            placeholder="Exemplo: Invasão, Treino, Jogatina ou ID do evento",
            required=True,
            max_length=120,
        )
        self.add_item(self.termo)

    async def on_submit(self, interaction: discord.Interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar este painel.",
            )
            return

        evento = buscar_evento_por_termo(self.termo.value.strip(), interaction.guild)
        if not evento:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Nenhum evento encontrado com esse termo.",
            )
            return

        guild_id = interaction.guild.id if interaction.guild else None
        embed = criar_embed_evento_encontrado(evento, guild_id=guild_id)
        await EventoRespostaView.responder_ephemeral(
            interaction,
            embed=embed,
            view=EventoResumoRespostasView(evento.get("event_id")),
        )


class AusenciaRankingPresencaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @staticmethod
    async def responder_ephemeral(interaction, mensagem=None, embed=None, view=None, **extras):
        await EventoRespostaView.responder_ephemeral(
            interaction,
            mensagem=mensagem,
            embed=embed,
            view=view,
            **extras,
        )

    async def validar_permissao_ranking(self, interaction):
        if not membro_pode_ver_ranking_presenca(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar este painel.",
            )
            return False
        return True

    @discord.ui.button(
        label="Semana",
        emoji="📅",
        style=discord.ButtonStyle.secondary,
    )
    async def ranking_semana(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_permissao_ranking(interaction):
            return

        embed = criar_embed_ranking_presenca("semana", calcular_ranking_presenca("semana", interaction.guild))
        await self.responder_ephemeral(interaction, embed=embed)

    @discord.ui.button(
        label="Mês",
        emoji="🌙",
        style=discord.ButtonStyle.secondary,
    )
    async def ranking_mes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_permissao_ranking(interaction):
            return

        embed = criar_embed_ranking_presenca("mes", calcular_ranking_presenca("mes", interaction.guild))
        await self.responder_ephemeral(interaction, embed=embed)


class AusenciaPanelSelect(discord.ui.Select):
    def __init__(self, panel_view):
        self.panel_view = panel_view
        options = [
            discord.SelectOption(
                label="Criar Evento",
                value="criar_evento",
                emoji="➕",
                description="Abrir o formulário para criar um evento.",
            ),
            discord.SelectOption(
                label="Eventos Ativos",
                value="eventos_ativos",
                emoji="📅",
                description="Ver os eventos abertos para respostas.",
            ),
            discord.SelectOption(
                label="Eventos Encerrados",
                value="eventos_encerrados",
                emoji="🔒",
                description="Ver os últimos eventos encerrados.",
            ),
            discord.SelectOption(
                label="Buscar Evento",
                value="buscar_evento",
                emoji="🔎",
                description="Procurar um evento pelo nome ou ID.",
            ),
            discord.SelectOption(
                label="Buscar Membro",
                value="buscar_membro",
                emoji="👤",
                description="Consultar o último registro de um membro.",
            ),
            discord.SelectOption(
                label="Atualizar Painel",
                value="atualizar_painel",
                emoji="🔄",
                description="Atualizar a embed principal do painel.",
            ),
        ]
        super().__init__(
            placeholder="Selecione uma ação do painel.",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ausencia_painel_menu",
        )

    async def callback(self, interaction: discord.Interaction):
        acoes = {
            "criar_evento": self.panel_view.acao_criar_evento,
            "eventos_ativos": self.panel_view.acao_eventos_ativos,
            "eventos_encerrados": self.panel_view.acao_eventos_encerrados,
            "buscar_evento": self.panel_view.acao_buscar_evento,
            "buscar_membro": self.panel_view.acao_buscar_membro,
            "atualizar_painel": self.panel_view.acao_atualizar_painel,
        }

        acao = acoes.get(self.values[0])
        if acao is None:
            await self.panel_view.responder_ephemeral(
                interaction,
                "❌ Não consegui processar esta opção.",
            )
            return

        await acao(interaction)


class AusenciaPanelView(discord.ui.View):
    def __init__(self, cog=None):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(AusenciaPanelSelect(self))

    @staticmethod
    async def responder_ephemeral(interaction, mensagem=None, embed=None, view=None, **extras):
        await EventoRespostaView.responder_ephemeral(
            interaction,
            mensagem=mensagem,
            embed=embed,
            view=view,
            **extras,
        )

    async def validar_staff(self, interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar este painel.",
            )
            return False
        return True

    async def acao_criar_evento(self, interaction: discord.Interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode criar eventos.",
            )
            return

        await interaction.response.send_modal(EventoCreateModal(self.cog))

    async def acao_eventos_ativos(self, interaction: discord.Interaction):
        if not await self.validar_staff(interaction):
            return

        embed = criar_embed_eventos_ativos(listar_eventos_por_status("aberto", limite=10, guild_ou_id=interaction.guild))
        await self.responder_ephemeral(interaction, embed=embed)

    async def acao_eventos_encerrados(self, interaction: discord.Interaction):
        if not await self.validar_staff(interaction):
            return

        embed = criar_embed_eventos_encerrados(listar_eventos_por_status("encerrado", limite=10, guild_ou_id=interaction.guild))
        await self.responder_ephemeral(interaction, embed=embed)

    async def acao_buscar_evento(self, interaction: discord.Interaction):
        if not await self.validar_staff(interaction):
            return

        await interaction.response.send_modal(AusenciaBuscarEventoModal())

    async def acao_buscar_membro(self, interaction: discord.Interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar esta função.",
            )
            return

        evento_referencia = obter_evento_aberto_referencia(interaction.guild)
        await interaction.response.send_modal(
            AusenciaBuscarMembroModal(
                evento_referencia.get("event_id") if evento_referencia else None
            )
        )

    async def acao_ranking_presenca(self, interaction: discord.Interaction):
        if not membro_pode_ver_ranking_presenca(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar este painel.",
            )
            return

        await self.responder_ephemeral(
            interaction,
            embed=criar_embed_ranking_presenca_periodo(),
            view=AusenciaRankingPresencaView(),
        )

    async def acao_ranking_ausencia(self, interaction: discord.Interaction):
        if not membro_pode_ver_ranking_presenca(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar este painel.",
            )
            return

        embed = criar_embed_ranking_ausencia_mes(calcular_ranking_ausencia_mes(interaction.guild))
        await self.responder_ephemeral(interaction, embed=embed)

    async def acao_atualizar_painel(self, interaction: discord.Interaction):
        if not await self.validar_staff(interaction):
            return

        try:
            await interaction.message.edit(
                embed=criar_embed_painel_ausencia(),
                view=AusenciaPanelLegacyView(self.cog),
            )
        except Exception:
            pass

        await self.responder_ephemeral(
            interaction,
            "✅ Painel atualizado.",
        )


class AusenciaPanelLegacyView(discord.ui.View):
    def __init__(self, cog=None):
        super().__init__(timeout=None)
        self.cog = cog

    async def _delegar(self, interaction, nome_acao):
        painel_atual = AusenciaPanelView(self.cog)
        acao = getattr(painel_atual, nome_acao)
        await acao(interaction)

    @discord.ui.button(
        label="Criar Evento",
        emoji="➕",
        style=discord.ButtonStyle.secondary,
        custom_id="ausencia_painel_criar_evento",
    )
    async def criar_evento(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._delegar(interaction, "acao_criar_evento")

    @discord.ui.button(
        label="Eventos Ativos",
        emoji="📅",
        style=discord.ButtonStyle.secondary,
        custom_id="ausencia_painel_ativos",
    )
    async def eventos_ativos(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._delegar(interaction, "acao_eventos_ativos")

    @discord.ui.button(
        label="Eventos Encerrados",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="ausencia_painel_encerrados",
    )
    async def eventos_encerrados(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._delegar(interaction, "acao_eventos_encerrados")

    @discord.ui.button(
        label="Buscar Evento",
        emoji="🔎",
        style=discord.ButtonStyle.secondary,
        custom_id="ausencia_painel_buscar",
    )
    async def buscar_evento(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._delegar(interaction, "acao_buscar_evento")

    @discord.ui.button(
        label="Buscar Membro",
        emoji="🔎",
        style=discord.ButtonStyle.secondary,
        custom_id="ausencia_painel_buscar_membro",
    )
    async def buscar_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._delegar(interaction, "acao_buscar_membro")

    @discord.ui.button(
        label="Atualizar Painel",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="ausencia_painel_atualizar",
    )
    async def atualizar_painel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._delegar(interaction, "acao_atualizar_painel")


class EventoCreateModal(discord.ui.Modal):
    def __init__(self, cog, mensagem_prompt=None):
        super().__init__(title="Criar Evento")
        self.cog = cog
        self.mensagem_prompt = mensagem_prompt

        self.nome_evento = discord.ui.TextInput(
            label="Nome do evento",
            placeholder="Exemplo: Invasão, Jogatina, Treino, Reunião",
            required=True,
            max_length=100,
        )
        self.data_evento = discord.ui.TextInput(
            label="Data",
            placeholder="Exemplo: 13/05/2026",
            required=True,
            max_length=20,
        )
        self.horario_evento = discord.ui.TextInput(
            label="Horário",
            placeholder="Exemplo: 21h30",
            required=True,
            max_length=20,
        )
        self.observacao = discord.ui.TextInput(
            label="Observação",
            placeholder="Informações extras sobre o evento, se houver.",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500,
        )

        self.add_item(self.nome_evento)
        self.add_item(self.data_evento)
        self.add_item(self.horario_evento)
        self.add_item(self.observacao)
        self.add_item(self.tipo_evento)

    async def on_submit(self, interaction: discord.Interaction):
        criado = await self.cog.publicar_evento(
            interaction,
            nome_evento=self.nome_evento.value,
            data_evento=self.data_evento.value,
            horario_evento=self.horario_evento.value,
            observacao=self.observacao.value,
            tipo_evento=self.tipo_evento.value,
            advertencia_automatica=False,
        )

        if criado and self.mensagem_prompt:
            try:
                await self.mensagem_prompt.delete()
            except Exception:
                pass
        return

        canal_destino = await self.cog.obter_canal_evento(interaction.channel)
        if not canal_destino or not hasattr(canal_destino, "send"):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui encontrar o canal configurado para enviar o evento.",
            )
            return

        membros_elegiveis = await obter_membros_ausencia_automatica(interaction.guild)
        contagens_iniciais = calcular_contagens_evento({"respostas": {}}, membros_elegiveis)
        embed = criar_embed_evento(
            self.nome_evento.value.strip(),
            self.data_evento.value.strip(),
            self.horario_evento.value.strip(),
            self.observacao.value.strip(),
            contagens=contagens_iniciais,
            guild=interaction.guild,
            evento={"tipo_evento": "outro", "status": "aberto", "respostas": {}},
        )

        try:
            mensagem_evento = await canal_destino.send(
                content=obter_mencoes_evento(interaction.guild) or None,
                embed=embed,
                view=EventoRespostaView(),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except Exception as erro:
            print(f"[EVENTO] Erro ao enviar registro de presença: {erro}")
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui enviar o registro de presença agora.",
            )
            return

        try:
            salvar_evento_ausencia(
                event_id=mensagem_evento.id,
                nome_evento=self.nome_evento.value.strip(),
                data_evento=self.data_evento.value.strip(),
                horario_evento=self.horario_evento.value.strip(),
                observacao=self.observacao.value.strip(),
                message_id=mensagem_evento.id,
                channel_id=mensagem_evento.channel.id,
                criado_por_id=interaction.user.id,
                criado_por_nome=str(interaction.user),
                guild_id=getattr(interaction.guild, "id", None),
                advertencia_automatica=False,
            )
        except Exception as erro:
            print(f"[EVENTO] Erro ao salvar evento no JSON: {erro}")
            try:
                await mensagem_evento.delete()
            except Exception:
                pass
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "❌ Não consegui salvar este evento no sistema.",
            )
            return

        await EventoRespostaView.responder_ephemeral(
            interaction,
            "✅ Registro de presença enviado.",
        )

        if self.mensagem_prompt:
            try:
                await self.mensagem_prompt.delete()
            except Exception:
                pass


class EventoCreateLauncherView(discord.ui.View):
    def __init__(self, cog, solicitante_id, mensagem_prompt=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.solicitante_id = solicitante_id
        self.mensagem_prompt = mensagem_prompt

    @staticmethod
    async def responder_ephemeral(interaction, mensagem=None, embed=None, view=None, **extras):
        await EventoRespostaView.responder_ephemeral(
            interaction,
            mensagem=mensagem,
            embed=embed,
            view=view,
            **extras,
        )

    @discord.ui.button(
        label="Criar Evento",
        emoji="📝",
        style=discord.ButtonStyle.secondary,
    )
    async def criar_evento(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not membro_eh_staff_ausencia(interaction.user):
            await self.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode criar registros de presença/ausência.",
            )
            return

        if interaction.user.id != self.solicitante_id:
            await self.responder_ephemeral(
                interaction,
                "❌ Este formulário foi aberto para outro membro da staff.",
            )
            return

        await interaction.response.send_modal(EventoCreateModal(self.cog, self.mensagem_prompt))


class PresenceMemberLookupModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Consultar membro")
        self.cog = cog
        self.termo = discord.ui.TextInput(
            label="ID ou menção do membro",
            placeholder="Ex: 1234567890 ou @Membro",
            required=True,
            max_length=100,
        )
        self.add_item(self.termo)

    async def on_submit(self, interaction: discord.Interaction):
        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message(
                "Você não tem permissão para usar este painel.",
                ephemeral=True,
            )
            return

        membro = await resolver_membro_por_termo(interaction.guild, self.termo.value)
        if membro is None:
            await interaction.response.send_message(
                "Não encontrei esse membro. Use o ID ou uma menção válida.",
                ephemeral=True,
            )
            return

        await self.cog.enviar_historico_presenca_interacao(interaction, membro, dias=14)


class PresenceActivityPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def validar_staff(self, interaction: discord.Interaction):
        if membro_eh_staff_ausencia(interaction.user):
            return True

        await interaction.response.send_message(
            "Você não tem permissão para usar este painel.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Relatório 14 dias",
        emoji="📊",
        style=discord.ButtonStyle.primary,
        custom_id="presenca_painel_relatorio_14",
    )
    async def relatorio_14(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return
        await self.cog.enviar_relatorio_presenca_interacao(interaction, dias=14)

    @discord.ui.button(
        label="Ver inativos",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="presenca_painel_inativos_14",
    )
    async def ver_inativos(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return
        await self.cog.enviar_inativos_presenca_interacao(interaction, dias=14)

    @discord.ui.button(
        label="Consultar membro",
        emoji="👤",
        style=discord.ButtonStyle.secondary,
        custom_id="presenca_painel_consultar_membro",
    )
    async def consultar_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return
        await interaction.response.send_modal(PresenceMemberLookupModal(self.cog))

    @discord.ui.button(
        label="Atualizar painel",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="presenca_painel_atualizar",
    )
    async def atualizar_painel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        embed = criar_embed_painel_atividade_presenca(datetime.now(FUSO_HORARIO))
        await interaction.response.edit_message(embed=embed, view=self)


class AusenciaCog(commands.Cog):
    presenca = app_commands.Group(name="presenca", description="Relatorios de atividade de presenca da FDN.")

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(AdvertenciaEntendiView())
        self.bot.add_view(EventoRespostaView())
        self.bot.add_view(AusenciaPanelView(self))
        self.bot.add_view(AusenciaPanelLegacyView(self))
        self.bot.add_view(PresenceActivityPanelView(self))

    async def obter_canal_evento(self, canal_atual=None):
        guild_ref = getattr(canal_atual, "guild", None)
        ausencia_channel_id = obter_valor_config(guild_ref, "AUSENCIA_CHANNEL_ID")
        if ausencia_channel_id == 0:
            return canal_atual

        canal = self.bot.get_channel(ausencia_channel_id)
        if canal:
            return canal

        try:
            return await self.bot.fetch_channel(ausencia_channel_id)
        except Exception:
            return None

    async def obter_canal_conquistas(self, guild):
        channel_id = obter_valor_config(guild, "ACHIEVEMENTS_CHANNEL_ID")
        if not channel_id:
            return None

        canal = self.bot.get_channel(int(channel_id))
        if canal:
            return canal

        try:
            return await self.bot.fetch_channel(int(channel_id))
        except Exception:
            return None

    async def obter_membro_evento(self, guild, user_id):
        if guild is None or not user_id:
            return None

        membro = guild.get_member(int(user_id))
        if membro is not None:
            return membro

        if hasattr(guild, "fetch_member"):
            try:
                return await guild.fetch_member(int(user_id))
            except Exception:
                return None
        return None

    async def processar_conquistas_evento_encerrado(self, guild, evento):
        meta = obter_meta_conquista(evento.get("tipo_evento"))
        if guild is None or not meta:
            return None

        dados_conquistas = carregar_dados_conquistas()
        event_id = str(evento.get("event_id") or "")
        if not event_id or evento_conquista_ja_processado(dados_conquistas, guild.id, event_id):
            return None

        cargo = obter_cargo_conquista_evento(guild, meta["tipo"])
        resultado = {
            "meta": meta,
            "tipo_evento": meta["tipo"],
            "avancos": [],
            "conquistas": [],
            "resetes": [],
            "perdas": [],
            "observacoes": [],
        }

        for resposta in list((evento.get("respostas") or {}).values()):
            try:
                user_id = int(resposta.get("user_id"))
            except (TypeError, ValueError):
                continue

            status = str(resposta.get("status", "")).strip().lower()
            if status not in {"presente", "ausente"}:
                continue

            membro = await self.obter_membro_evento(guild, user_id)
            if membro is None or not membro_elegivel_conquista_presenca(membro):
                continue

            estado = obter_estado_conquista(dados_conquistas, guild.id, user_id, meta["tipo"], criar=True)
            if estado is None:
                continue

            possui_cargo_real = membro_tem_cargo_conquista(membro, cargo)
            if possui_cargo_real and not bool(estado.get("possui_cargo")):
                estado["possui_cargo"] = True
                estado["progresso"] = max(int(estado.get("progresso", 0) or 0), meta["objetivo"])

            mencao = membro.mention

            if status == "presente":
                estado["ausencias_seguidas"] = 0
                estado["ausencias_com_cargo"] = 0

                if bool(estado.get("possui_cargo")) or possui_cargo_real:
                    estado["possui_cargo"] = True
                    estado["progresso"] = max(int(estado.get("progresso", 0) or 0), meta["objetivo"])
                    continue

                novo_progresso = min(meta["objetivo"], int(estado.get("progresso", 0) or 0) + 1)
                estado["progresso"] = novo_progresso

                if novo_progresso >= meta["objetivo"]:
                    cargo_aplicado = False
                    if cargo is not None:
                        try:
                            if not membro_tem_cargo_conquista(membro, cargo):
                                await membro.add_roles(cargo, reason=f"Conquista de presença: {meta['nome']}")
                            cargo_aplicado = True
                        except Exception as erro:
                            print(
                                f"[CONQUISTAS] Nao consegui adicionar cargo | guild={guild.id} "
                                f"membro={user_id} tipo={meta['tipo']} erro={erro}"
                            )
                            resultado["observacoes"].append(
                                f"{mencao} atingiu {meta['objetivo']}/{meta['objetivo']}, mas o cargo {meta['cargo_nome']} nao foi aplicado."
                            )
                    else:
                        resultado["observacoes"].append(
                            f"{mencao} atingiu {meta['objetivo']}/{meta['objetivo']}, mas o cargo {meta['cargo_nome']} nao foi encontrado."
                        )

                    if cargo_aplicado:
                        estado["possui_cargo"] = True
                        estado["progresso"] = meta["objetivo"]
                        resultado["conquistas"].append(
                            f"{mencao} conquistou {meta['cargo_nome']}!"
                        )
                        cargo_key = CONQUISTA_PRESENCA_KEYS.get(meta["tipo"])
                        if cargo_key:
                            await enviar_embed_conquista(
                                self.bot,
                                membro,
                                cargo_key,
                                progresso=f"{meta['objetivo']}/{meta['objetivo']}",
                            )
                else:
                    resultado["avancos"].append(
                        f"{mencao} avançou para {novo_progresso}/{meta['objetivo']} em {meta['nome']}."
                    )
                continue

            if bool(estado.get("possui_cargo")) or possui_cargo_real:
                estado["possui_cargo"] = True
                estado["ausencias_com_cargo"] = int(estado.get("ausencias_com_cargo", 0) or 0) + 1
                estado["ausencias_seguidas"] = 0

                if estado["ausencias_com_cargo"] >= meta["perda_depois_ganhar"]:
                    if cargo is not None and membro_tem_cargo_conquista(membro, cargo):
                        try:
                            await membro.remove_roles(cargo, reason=f"Perda de conquista de presença: {meta['nome']}")
                        except Exception as erro:
                            print(
                                f"[CONQUISTAS] Nao consegui remover cargo | guild={guild.id} "
                                f"membro={user_id} tipo={meta['tipo']} erro={erro}"
                            )
                    estado["progresso"] = 0
                    estado["ausencias_seguidas"] = 0
                    estado["ausencias_com_cargo"] = 0
                    estado["possui_cargo"] = False
                    resultado["perdas"].append(
                        f"{mencao} acumulou {meta['perda_depois_ganhar']} ausências e perdeu o cargo {meta['cargo_nome']}."
                    )
                continue

            estado["ausencias_seguidas"] = int(estado.get("ausencias_seguidas", 0) or 0) + 1
            if estado["ausencias_seguidas"] >= meta["reset_antes_ganhar"] and int(estado.get("progresso", 0) or 0) > 0:
                estado["progresso"] = 0
                estado["ausencias_seguidas"] = 0
                estado["ausencias_com_cargo"] = 0
                resultado["resetes"].append(
                    f"{mencao} teve {meta['reset_antes_ganhar']} ausências seguidas e voltou para 0/{meta['objetivo']} em {meta['nome']}."
                )

        marcar_evento_conquista_processado(dados_conquistas, guild.id, event_id)
        salvar_dados_conquistas(dados_conquistas)
        return resultado

    async def enviar_resumo_conquistas_evento(self, guild, evento, resultado):
        if guild is None or not resultado:
            return

        canal = await self.obter_canal_conquistas(guild)
        if canal is None:
            return

        meta = resultado["meta"]
        embed = discord.Embed(
            title="🏆 Progresso de Conquista Atualizado",
            description="A presença do evento foi confirmada pela staff.",
            color=AUSENCIA_COLOR,
        )
        embed.add_field(name="Evento", value=formatar_nome_evento_exibicao(evento.get("nome_evento", "Evento"), resultado["tipo_evento"]), inline=False)
        embed.add_field(name="Tipo", value=formatar_tipo_evento(resultado["tipo_evento"]), inline=False)
        embed.add_field(name="Conquista", value=meta["cargo_nome"], inline=False)

        blocos = [
            ("Lista", (resultado.get("avancos") or []) + (resultado.get("conquistas") or [])),
            ("🔄 Progressos resetados", resultado.get("resetes") or []),
            ("💔 Cargos perdidos", resultado.get("perdas") or []),
            ("⚠️ Observações", resultado.get("observacoes") or []),
        ]

        adicionou_algo = False
        for nome, linhas in blocos:
            if not linhas:
                continue
            adicionou_algo = True
            for indice, bloco in enumerate(dividir_linhas_embed(linhas, limite=1000)):
                embed.add_field(
                    name=nome if indice == 0 else "Continuação",
                    value=bloco,
                    inline=False,
                )

        if not adicionou_algo:
            embed.add_field(
                name="Resumo",
                value="Nenhuma alteração de conquista foi registrada neste evento.",
                inline=False,
            )

        embed.set_footer(text=AUSENCIA_FOOTER)
        try:
            await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as erro:
            print(
                f"[CONQUISTAS] Nao consegui enviar resumo no canal | guild={guild.id} "
                f"evento={evento.get('event_id')} erro={erro}"
            )

    async def publicar_evento(
        self,
        interaction,
        nome_evento,
        data_evento,
        horario_evento,
        observacao="",
        tipo_evento="outro",
        advertencia_automatica=False,
        imagem_url=None,
    ):
        nome_evento = str(nome_evento or "").strip()
        data_evento = str(data_evento or "").strip()
        horario_evento = str(horario_evento or "").strip()
        observacao = str(observacao or "").strip()
        tipo_evento = normalizar_tipo_evento(tipo_evento)
        imagem_url = str(imagem_url or "").strip() or None

        if not nome_evento or not data_evento or not horario_evento:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "Preencha titulo, data e horario do evento.",
            )
            return False

        if not tipo_evento:
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "Tipo de evento invalido. Use invasao, jogatina, cinema ou outro.",
            )
            return False

        canal_destino = await self.obter_canal_evento(interaction.channel)
        if not canal_destino or not hasattr(canal_destino, "send"):
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "Nao consegui encontrar o canal configurado para enviar o evento.",
            )
            return False

        membros_elegiveis = await obter_membros_ausencia_automatica(interaction.guild)
        contagens_iniciais = calcular_contagens_evento({"respostas": {}}, membros_elegiveis)
        embed = criar_embed_evento(
            nome_evento,
            data_evento,
            horario_evento,
            observacao,
            tipo_evento=tipo_evento,
            contagens=contagens_iniciais,
            imagem_url=imagem_url,
            guild=interaction.guild,
            evento={"tipo_evento": tipo_evento, "status": "aberto", "respostas": {}},
        )

        try:
            mensagem_evento = await canal_destino.send(
                content=obter_mencoes_evento(interaction.guild) or None,
                embed=embed,
                view=EventoRespostaView(),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except Exception as erro:
            print(f"[EVENTO] Erro ao enviar registro de presenca: {erro}")
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "Nao consegui enviar o registro de presenca agora.",
            )
            return False

        try:
            salvar_evento_ausencia(
                event_id=mensagem_evento.id,
                nome_evento=nome_evento,
                data_evento=data_evento,
                horario_evento=horario_evento,
                observacao=observacao,
                message_id=mensagem_evento.id,
                channel_id=mensagem_evento.channel.id,
                criado_por_id=interaction.user.id,
                criado_por_nome=str(interaction.user),
                guild_id=getattr(interaction.guild, "id", None),
                advertencia_automatica=bool(advertencia_automatica),
                imagem_url=imagem_url,
                tipo_evento=tipo_evento,
            )
        except Exception as erro:
            print(f"[EVENTO] Erro ao salvar evento no JSON: {erro}")
            try:
                await mensagem_evento.delete()
            except Exception:
                pass
            await EventoRespostaView.responder_ephemeral(
                interaction,
                "Nao consegui salvar este evento no sistema.",
            )
            return False

        await EventoRespostaView.responder_ephemeral(
            interaction,
            "Registro de presenca enviado.",
        )
        return True

    async def reenviar_listas_evento_encerrado(self, interaction, evento, apagar_antigas=False):
        embeds_presentes = await criar_embeds_presentes_staff_evento(interaction.guild, evento)
        mensagens_presentes = await editar_ou_enviar_lista_staff_evento(
            interaction.client,
            interaction.guild,
            evento,
            "presentes",
            embeds_presentes,
            criar_se_ausente=True,
            forcar_nova=True,
            apagar_antigas=apagar_antigas,
        )

        membros_sem_resposta = await obter_membros_ausentes_staff_evento(interaction.guild, evento)
        embeds_sem_resposta = criar_embeds_lista_sem_resposta_evento(membros_sem_resposta)
        mensagens_sem_resposta = await editar_ou_enviar_lista_staff_evento(
            interaction.client,
            interaction.guild,
            evento,
            "ausentes",
            embeds_sem_resposta,
            criar_se_ausente=True,
            mencionar_staff=True,
            forcar_nova=True,
            apagar_antigas=apagar_antigas,
        )

        return len(mensagens_presentes), len(mensagens_sem_resposta), len(membros_sem_resposta)

    async def obter_canal_painel_ausencia(self, canal_atual=None):
        guild_ref = getattr(canal_atual, "guild", None)
        ausencia_panel_channel_id = obter_valor_config(guild_ref, "AUSENCIA_PANEL_CHANNEL_ID")
        if ausencia_panel_channel_id == 0:
            return canal_atual

        canal = self.bot.get_channel(ausencia_panel_channel_id)
        if canal:
            return canal

        try:
            return await self.bot.fetch_channel(ausencia_panel_channel_id)
        except Exception:
            return None

    async def localizar_painel_ausencia(self, canal):
        if not canal or not hasattr(canal, "history"):
            return None

        try:
            async for mensagem in canal.history(limit=50):
                if mensagem.author.id != self.bot.user.id:
                    continue
                if not mensagem.embeds:
                    continue

                titulo = mensagem.embeds[0].title or ""
                if titulo == AUSENCIA_PANEL_TITLE:
                    return mensagem
        except Exception:
            return None

        return None

    async def enviar_ou_atualizar_painel_ausencia(self, canal):
        embed = criar_embed_painel_ausencia()
        view = AusenciaPanelLegacyView(self)
        mensagem_existente = await self.localizar_painel_ausencia(canal)

        if mensagem_existente:
            await mensagem_existente.edit(embed=embed, view=view)
            return mensagem_existente, False

        mensagem = await canal.send(embed=embed, view=view)
        return mensagem, True

    async def enviar_relatorio_presenca_interacao(self, interaction: discord.Interaction, dias: int = 14):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando só pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Você não tem permissão para usar este painel.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        resultado = await analisar_atividade_presenca(interaction.guild, dias)
        if not resultado["eventos"]:
            await interaction.followup.send("Não há eventos encerrados no período analisado.", ephemeral=True)
            return

        embed, precisa_arquivo = criar_embed_relatorio_presenca(resultado)
        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        if precisa_arquivo:
            await interaction.followup.send(
                content="📎 Relatório completo:",
                file=criar_arquivo_texto_presenca(
                    f"relatorio_presenca_{resultado['dias']}_dias.txt",
                    criar_texto_relatorio_presenca(resultado),
                ),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def enviar_inativos_presenca_interacao(self, interaction: discord.Interaction, dias: int = 14):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando só pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Você não tem permissão para usar este painel.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        resultado = await analisar_atividade_presenca(interaction.guild, dias)
        if not resultado["eventos"]:
            await interaction.followup.send("Não há eventos encerrados no período analisado.", ephemeral=True)
            return

        embed, precisa_arquivo = criar_embed_inativos_presenca(resultado)
        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        if precisa_arquivo:
            await interaction.followup.send(
                content="📎 Relatório completo:",
                file=criar_arquivo_texto_presenca(
                    f"inativos_presenca_{resultado['dias']}_dias.txt",
                    criar_texto_inativos_presenca(resultado),
                ),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def enviar_historico_presenca_interacao(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        dias: int = 14,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando só pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Você não tem permissão para usar este painel.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        resultado = await analisar_atividade_presenca(interaction.guild, dias)
        if not resultado["eventos"]:
            await interaction.followup.send("Não há eventos encerrados no período analisado.", ephemeral=True)
            return

        analise = resultado["analises"].get(str(usuario.id))
        if analise is None:
            await interaction.followup.send(
                "Esse membro não está no cargo analisado pelo relatório de presença.",
                ephemeral=True,
            )
            return

        embed = criar_embed_historico_membro_presenca(
            usuario,
            analise,
            resultado["dias"],
            resultado["total_eventos"],
        )
        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def resolver_membro_advertencia(self, interaction, termo):
        membro = await resolver_membro_por_termo(interaction.guild, termo)
        if membro is None:
            return None
        return membro

    @app_commands.command(name="criarevento", description="Cria um evento de presenca com os botoes do painel.")
    @app_commands.describe(
        titulo="Titulo do evento.",
        tipo="Tipo do evento para as conquistas.",
        horario="Horario do evento. Exemplo: 21h30.",
        observacao="Informacoes extras sobre o evento.",
        data="Data do evento. Se nao informar, sera usada a data atual.",
        imagem="Imagem opcional para exibir na embed do evento.",
    )
    @app_commands.choices(tipo=CRIAR_EVENTO_TIPO_CHOICES)
    async def slash_criar_evento(
        self,
        interaction: discord.Interaction,
        titulo: str,
        tipo: app_commands.Choice[str],
        horario: str,
        observacao: str | None = None,
        data: str | None = None,
        imagem: discord.Attachment | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Esse comando so pode ser usado em servidor.",
                ephemeral=True,
            )
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message(
                "Apenas a staff pode criar eventos.",
                ephemeral=True,
            )
            return

        if not anexo_eh_imagem_evento(imagem):
            await interaction.response.send_message(
                "O anexo precisa ser uma imagem PNG, JPG, GIF ou WEBP.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.publicar_evento(
            interaction,
            nome_evento=titulo,
            data_evento=data or datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y"),
            horario_evento=horario,
            observacao=observacao,
            tipo_evento=tipo.value,
            advertencia_automatica=False,
            imagem_url=getattr(imagem, "url", None),
        )

    @app_commands.command(name="reenviarlistas", description="Reenvia as listas de presentes e sem resposta de um evento encerrado.")
    @app_commands.describe(
        evento="ID da mensagem do evento ou parte do titulo. Se vazio, usa o ultimo encerrado.",
        apagar_antigas="Se ativar, apaga as listas antigas salvas antes de reenviar.",
    )
    async def slash_reenviarlistas(
        self,
        interaction: discord.Interaction,
        evento: str | None = None,
        apagar_antigas: bool = False,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Esse comando so pode ser usado em servidor.",
                ephemeral=True,
            )
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message(
                "Apenas a staff pode reenviar listas de eventos.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        if evento:
            evento_alvo = buscar_evento_por_termo(evento, interaction.guild)
        else:
            eventos_encerrados = listar_eventos_por_status("encerrado", limite=1, guild_ou_id=interaction.guild)
            evento_alvo = eventos_encerrados[0] if eventos_encerrados else None

        if not evento_alvo:
            await interaction.followup.send(
                "Nao encontrei esse evento. Use o ID da mensagem do evento ou parte do titulo.",
                ephemeral=True,
            )
            return

        if str(evento_alvo.get("status", "")).strip().lower() != "encerrado":
            await interaction.followup.send(
                "Esse evento ainda nao esta encerrado. As listas finais so podem ser reenviadas depois do encerramento.",
                ephemeral=True,
            )
            return

        total_presentes, total_sem_resposta, membros_sem_resposta = await self.reenviar_listas_evento_encerrado(
            interaction,
            evento_alvo,
            apagar_antigas=apagar_antigas,
        )

        if total_presentes <= 0 and total_sem_resposta <= 0:
            await interaction.followup.send(
                "Nao consegui reenviar as listas. Confira se o canal da staff esta configurado.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            (
                "Listas reenviadas no canal da staff.\n"
                f"Evento: {evento_alvo.get('nome_evento', 'Evento')}\n"
                f"Mensagens de presentes: {total_presentes}\n"
                f"Mensagens de sem resposta: {total_sem_resposta}\n"
                f"Membros sem resposta listados: {membros_sem_resposta}"
            ),
            ephemeral=True,
        )

    @app_commands.command(name="atualizarevento", description="Atualiza a embed de um evento ja criado.")
    @app_commands.describe(
        evento="ID da mensagem do evento ou parte do titulo. Se vazio, usa o evento aberto mais recente.",
    )
    async def slash_atualizar_evento(
        self,
        interaction: discord.Interaction,
        evento: str | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Esse comando so pode ser usado em servidor.",
                ephemeral=True,
            )
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message(
                "Apenas a staff pode atualizar eventos.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        if evento:
            evento_alvo = buscar_evento_por_termo(evento, interaction.guild)
        else:
            evento_alvo = obter_evento_aberto_referencia(interaction.guild)

        if not evento_alvo:
            await interaction.followup.send(
                "Nao encontrei esse evento. Use o ID da mensagem do evento ou parte do titulo.",
                ephemeral=True,
            )
            return

        await EventoRespostaView.editar_mensagem_evento(interaction, evento_alvo)
        await atualizar_listas_staff_evento(interaction.client, interaction.guild, evento_alvo)

        await interaction.followup.send(
            (
                "✅ Embed do evento atualizada com sucesso.\n"
                f"Evento: {evento_alvo.get('nome_evento', 'Evento')}\n"
                f"ID: {evento_alvo.get('event_id', 'Nao informado')}"
            ),
            ephemeral=True,
        )

    @presenca.command(name="painel", description="Envia um painel visual para consultar a atividade dos membros.")
    async def presenca_painel(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando só pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Apenas a staff pode usar este painel.", ephemeral=True)
            return

        canal = interaction.channel
        if canal is None or not hasattr(canal, "send"):
            await interaction.response.send_message("Não consegui enviar o painel neste canal.", ephemeral=True)
            return

        embed = criar_embed_painel_atividade_presenca(datetime.now(FUSO_HORARIO))
        view = PresenceActivityPanelView(self)
        await canal.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message("Painel de atividade enviado neste canal.", ephemeral=True)

    @presenca.command(name="relatorio", description="Mostra o relatorio geral de atividade dos membros.")
    @app_commands.describe(dias="Periodo analisado em dias. Padrao: 14.")
    async def presenca_relatorio(self, interaction: discord.Interaction, dias: int = 14):
        await self.enviar_relatorio_presenca_interacao(interaction, dias=dias)

    @presenca.command(name="inativos", description="Lista possiveis inativos no periodo analisado.")
    @app_commands.describe(dias="Periodo analisado em dias. Padrao: 14.")
    async def presenca_inativos(self, interaction: discord.Interaction, dias: int = 14):
        await self.enviar_inativos_presenca_interacao(interaction, dias=dias)

    @presenca.command(name="membro", description="Consulta o historico de presenca de um membro.")
    @app_commands.describe(
        usuario="Membro que sera analisado.",
        dias="Periodo analisado em dias. Padrao: 14.",
    )
    async def presenca_membro(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        dias: int = 14,
    ):
        await self.enviar_historico_presenca_interacao(interaction, usuario, dias=dias)

    @presenca.command(name="resetarcontagens", description="Reinicia as contagens de presenca a partir de agora.")
    async def presenca_resetarcontagens(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando so pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Apenas a staff pode resetar as contagens.", ephemeral=True)
            return

        reset_iso = definir_reset_contagens(interaction.guild)
        if not reset_iso:
            await interaction.response.send_message(
                "Nao consegui salvar o reset das contagens.",
                ephemeral=True,
            )
            return

        try:
            reset_em = datetime.fromisoformat(reset_iso).astimezone(FUSO_HORARIO)
            reset_formatado = reset_em.strftime("%d/%m/%Y às %H:%M")
        except ValueError:
            reset_formatado = reset_iso

        await interaction.response.send_message(
            (
                f"✅ Contagens de presença resetadas a partir de {reset_formatado}.\n"
                "O histórico antigo foi mantido, mas não entra mais nos relatórios e rankings."
            ),
            ephemeral=True,
        )

    @presenca.command(name="removerresposta", description="Remove uma resposta registrada em um evento.")
    @app_commands.describe(
        evento="ID da mensagem do evento ou parte do titulo.",
        usuario="Membro que tera a resposta removida.",
        status="Tipo de resposta que deseja remover.",
    )
    @app_commands.choices(status=PRESENCA_REMOVER_RESPOSTA_CHOICES)
    async def presenca_removerresposta(
        self,
        interaction: discord.Interaction,
        evento: str,
        usuario: discord.Member,
        status: app_commands.Choice[str],
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando so pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Apenas a staff pode corrigir respostas de eventos.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        evento_alvo = buscar_evento_por_termo(evento, interaction.guild)
        if not evento_alvo:
            await interaction.followup.send(
                "Nao encontrei esse evento. Use o ID da mensagem do evento ou parte do titulo.",
                ephemeral=True,
            )
            return

        resposta_atual = evento_alvo.get("respostas", {}).get(str(usuario.id))
        if not resposta_atual:
            await interaction.followup.send(
                f"{usuario.mention} nao tem resposta registrada nesse evento.",
                ephemeral=True,
            )
            return

        status_atual = str(resposta_atual.get("status", "")).strip().lower()
        if status_atual != status.value:
            await interaction.followup.send(
                (
                    f"{usuario.mention} esta marcado como {formatar_status_resposta(status_atual)}, "
                    f"nao como {formatar_status_resposta(status.value)}."
                ),
                ephemeral=True,
            )
            return

        evento_atualizado, resposta_removida = remover_resposta_evento_staff(
            evento_alvo.get("event_id"),
            usuario.id,
            status=status.value,
        )
        if not evento_atualizado or not resposta_removida:
            await interaction.followup.send(
                "Nao consegui remover essa resposta.",
                ephemeral=True,
            )
            return

        if str(evento_atualizado.get("status", "")).strip().lower() == "encerrado":
            membros_elegiveis = await obter_membros_ausencia_automatica(interaction.guild)
            evento_atualizado = atualizar_sem_resposta_evento(
                evento_atualizado.get("event_id"),
                len(filtrar_membros_sem_resposta(evento_atualizado, membros_elegiveis)),
            ) or evento_atualizado

        await EventoRespostaView.editar_mensagem_evento(interaction, evento_atualizado)
        await atualizar_listas_staff_evento(interaction.client, interaction.guild, evento_atualizado)
        await interaction.followup.send(
            (
                f"✅ Removi {formatar_status_resposta(status.value)} de {usuario.mention}.\n"
                f"Evento: {evento_atualizado.get('nome_evento', 'Evento')}\n"
                "As listas e a embed do evento foram atualizadas quando possível."
            ),
            ephemeral=True,
        )

    @presenca.command(name="adicionarresposta", description="Adiciona ou corrige uma resposta em um evento.")
    @app_commands.describe(
        evento="ID da mensagem do evento ou parte do titulo.",
        usuario="Membro que tera a resposta registrada.",
        status="Tipo de resposta que deseja registrar.",
        motivo="Motivo da ausencia ou talvez, quando necessario.",
        retorno="Previsao de retorno, usada para ausencia.",
    )
    @app_commands.choices(status=PRESENCA_REMOVER_RESPOSTA_CHOICES)
    async def presenca_adicionarresposta(
        self,
        interaction: discord.Interaction,
        evento: str,
        usuario: discord.Member,
        status: app_commands.Choice[str],
        motivo: str | None = None,
        retorno: str | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando so pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Apenas a staff pode corrigir respostas de eventos.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        evento_alvo = buscar_evento_por_termo(evento, interaction.guild)
        if not evento_alvo:
            await interaction.followup.send(
                "Nao encontrei esse evento. Use o ID da mensagem do evento ou parte do titulo.",
                ephemeral=True,
            )
            return

        status_valor = str(status.value).strip().lower()
        motivo_limpo = str(motivo or "").strip()
        retorno_limpo = str(retorno or "").strip()

        if status_valor == "ausente" and not motivo_limpo:
            await interaction.followup.send(
                "Para marcar Ausencia, informe tambem o motivo.",
                ephemeral=True,
            )
            return

        if status_valor == "talvez" and not motivo_limpo:
            await interaction.followup.send(
                "Para marcar Talvez, informe tambem o motivo.",
                ephemeral=True,
            )
            return

        if status_valor == "presente":
            motivo_limpo = None
            retorno_limpo = None
        elif status_valor == "talvez":
            retorno_limpo = None

        evento_atualizado, status_anterior = atualizar_resposta_evento_staff(
            evento_alvo.get("event_id"),
            usuario.id,
            str(usuario),
            status_valor,
            alterado_por_id=interaction.user.id,
            alterado_por_nome=str(interaction.user),
            motivo=motivo_limpo,
            retorno=retorno_limpo,
        )
        if not evento_atualizado:
            await interaction.followup.send(
                "Nao consegui atualizar esse evento.",
                ephemeral=True,
            )
            return

        if str(evento_atualizado.get("status", "")).strip().lower() == "encerrado":
            membros_elegiveis = await obter_membros_ausencia_automatica(interaction.guild)
            evento_atualizado = atualizar_sem_resposta_evento(
                evento_atualizado.get("event_id"),
                len(filtrar_membros_sem_resposta(evento_atualizado, membros_elegiveis)),
            ) or evento_atualizado

        await EventoRespostaView.editar_mensagem_evento(interaction, evento_atualizado)
        await atualizar_listas_staff_evento(interaction.client, interaction.guild, evento_atualizado)

        if status_anterior:
            mensagem = (
                f"✅ Resposta de {usuario.mention} atualizada para {formatar_status_resposta(status_valor)}.\n"
                f"Antes: {formatar_status_resposta(status_anterior)}\n"
                f"Evento: {evento_atualizado.get('nome_evento', 'Evento')}"
            )
        else:
            mensagem = (
                f"✅ Resposta de {usuario.mention} registrada como {formatar_status_resposta(status_valor)}.\n"
                f"Evento: {evento_atualizado.get('nome_evento', 'Evento')}"
            )

        await interaction.followup.send(
            f"{mensagem}\nAs listas e a embed do evento foram atualizadas quando possivel.",
            ephemeral=True,
        )

    @app_commands.command(name="adicionaradv", description="Adiciona uma advertencia manual a um membro.")
    @app_commands.describe(
        membro="Mencao ou ID do membro que vai receber a advertencia.",
        evento="Nome do evento em que o membro nao registrou.",
        data="Data do evento em que o membro nao registrou.",
        motivo="Motivo da advertencia, se quiser informar.",
    )
    async def slash_adicionaradv(
        self,
        interaction: discord.Interaction,
        membro: str,
        evento: str | None = None,
        data: str | None = None,
        motivo: str | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando so pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Apenas a staff pode usar este comando.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        membro_alvo = await self.resolver_membro_advertencia(interaction, membro)
        if membro_alvo is None:
            await interaction.followup.send("Nao consegui encontrar esse membro no servidor.", ephemeral=True)
            return

        registro, aplicada, _ = adicionar_advertencia_manual(
            user_id=membro_alvo.id,
            user_name=str(membro_alvo),
            staff_id=interaction.user.id,
            staff_name=str(interaction.user),
            quantidade=1,
            motivo=motivo or "Advertencia manual aplicada pela staff.",
            nome_evento=evento,
            data_evento=data,
        )
        if not aplicada or not registro:
            await interaction.followup.send(
                f"{membro_alvo.mention} ja esta com 5 de 5 advertencias ativas.",
                ephemeral=True,
            )
            return

        embed = criar_embed_advertencia_aplicada(registro)
        enviado = await editar_ou_enviar_embed_advertencia(interaction.client, interaction.guild, registro, embed)
        # Advertencias nao sao mais enviadas por DM; o aviso fica apenas no canal configurado.
        quantidade_atual = int(registro.get("quantidade_advertencias") or 0)
        mensagem = (
            f"Advertencia adicionada para {membro_alvo.mention}. "
            f"Atual: {quantidade_atual} de 5."
        )
        if not enviado:
            mensagem += " Nao consegui enviar a embed no canal de advertencias configurado."

        await interaction.followup.send(mensagem, ephemeral=True)

    @app_commands.command(name="removeradv", description="Remove advertencias ativas de um membro.")
    @app_commands.describe(
        membro="Mencao ou ID do membro.",
        quantidade="Quantidade de advertencias para remover.",
    )
    @app_commands.choices(quantidade=ADVERTENCIA_QUANTIDADE_CHOICES)
    async def slash_removeradv(
        self,
        interaction: discord.Interaction,
        membro: str,
        quantidade: app_commands.Choice[int],
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando so pode ser usado em servidor.", ephemeral=True)
            return

        if not membro_eh_staff_ausencia(interaction.user):
            await interaction.response.send_message("Apenas a staff pode usar este comando.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        membro_alvo = await self.resolver_membro_advertencia(interaction, membro)
        if membro_alvo is None:
            await interaction.followup.send("Nao consegui encontrar esse membro no servidor.", ephemeral=True)
            return

        registro, removida, quantidade_removida = remover_advertencia_manual(
            user_id=membro_alvo.id,
            user_name=str(membro_alvo),
            staff_id=interaction.user.id,
            staff_name=str(interaction.user),
            quantidade=quantidade.value,
        )
        if not removida or not registro:
            await interaction.followup.send(
                f"{membro_alvo.mention} nao tem advertencia ativa para remover.",
                ephemeral=True,
            )
            return

        quantidade_atual = int(registro.get("quantidade_advertencias") or 0)
        await interaction.followup.send(
            f"Removi {quantidade_removida} advertencia(s) de {membro_alvo.mention}. "
            f"Atual: {quantidade_atual} de 5.",
            ephemeral=True,
        )

    @commands.command(name="evento")
    async def evento(self, ctx):
        await ctx.send("⚠️ A criação de eventos agora é feita pelo painel de presença. Use o botão ➕ Criar Evento.")

    @commands.command(name="ausenciapainel")
    async def ausenciapainel(self, ctx):
        if not membro_eh_staff_ausencia(ctx.author):
            await ctx.send("❌ Apenas a staff pode usar este painel.")
            return

        canal_destino = await self.obter_canal_painel_ausencia(ctx.channel)
        if not canal_destino or not hasattr(canal_destino, "send"):
            await ctx.send("❌ Não consegui encontrar o canal configurado para o painel de presença.")
            return

        _, criado = await self.enviar_ou_atualizar_painel_ausencia(canal_destino)

        if canal_destino.id != ctx.channel.id:
            await ctx.send("✅ Painel enviado." if criado else "✅ Painel atualizado.")
        elif not criado:
            await ctx.send("✅ Painel atualizado.")


async def setup(bot):
    await bot.add_cog(AusenciaCog(bot))
