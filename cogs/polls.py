from __future__ import annotations

import asyncio
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

from config import FUSO_HORARIO
from services.polls import (
    atualizar_poll,
    gerar_id_poll,
    listar_polls_abertas,
    listar_polls_com_mensagem,
    obter_poll,
    obter_poll_por_message_id,
    registrar_voto_poll,
    salvar_poll,
)
from utils.discord_helpers import membro_eh_staff


POLL_COLOR = discord.Color.from_rgb(0, 255, 255)
POLL_FOOTER = "FDN • Sistema de Enquetes"
MAX_OPTIONS = 9
EMBED_TOTAL_MAX = 6000
TEMPOS_ENCERRAMENTO_HORAS = {0, 2, 4, 6, 12, 24, 48}
MESSAGE_LINK_RE = re.compile(
    r"https?://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/channels/"
    r"(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)/?"
)
DEFAULT_OPTION_EMOJIS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
BARRA_CHEIA = "▰"
BARRA_VAZIA = "▱"
BARRA_TAMANHO = 10


def limitar_texto(valor, limite):
    texto = str(valor or "").strip()
    if len(texto) <= limite:
        return texto
    return texto[: max(0, limite - 3)].rstrip() + "..."


def url_valida(valor):
    texto = str(valor or "").strip()
    if not texto:
        return True
    parsed = urlparse(texto)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def extrair_id_mensagem(valor):
    texto = str(valor or "").strip()
    match = MESSAGE_LINK_RE.search(texto)
    if match:
        return match.group("message_id")
    if texto.isdigit():
        return texto
    return None


def formatar_data_hora_iso(valor):
    if not valor:
        return ""
    try:
        data = datetime.fromisoformat(str(valor))
        return data.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        return str(valor)


def segundos_ate_data_iso(valor):
    if not valor:
        return None
    try:
        data = datetime.fromisoformat(str(valor))
    except Exception:
        return None
    return max(0, (data - datetime.now(FUSO_HORARIO)).total_seconds())


def contar_caracteres_embed(embed):
    total = len(embed.title or "") + len(embed.description or "")
    total += len(getattr(embed.footer, "text", "") or "")
    for campo in embed.fields:
        total += len(campo.name or "") + len(campo.value or "")
    return total


def obter_rotulo_opcao(opcao, indice):
    emoji = str(opcao.get("emoji") or "").strip() or DEFAULT_OPTION_EMOJIS[indice - 1]
    nome = str(opcao.get("nome") or f"Opção {indice}").strip()
    return emoji, nome


def extrair_nome_curto_opcao(nome):
    texto = " ".join(str(nome or "").split())
    if not texto:
        return "Opção"

    match_horario = re.search(r"\b(?:[01]?\d|2[0-3])\s*h(?:\s*[0-5]\d)?\b", texto, flags=re.IGNORECASE)
    if match_horario:
        return re.sub(r"\s+", "", match_horario.group(0)).lower()

    match_hora_extenso = re.search(
        r"\b((?:[01]?\d|2[0-3]))\s*horas?\b",
        texto,
        flags=re.IGNORECASE,
    )
    if match_hora_extenso:
        return f"{match_hora_extenso.group(1)}h"

    match_relogio = re.search(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", texto)
    if match_relogio:
        return match_relogio.group(0)

    return limitar_texto(texto, 24)


def obter_rotulo_curto_opcao(opcao, indice):
    emoji, nome = obter_rotulo_opcao(opcao, indice)
    return emoji, extrair_nome_curto_opcao(nome)


def criar_label_voto_opcao(opcao, indice, limite=32):
    emoji, nome_curto = obter_rotulo_curto_opcao(opcao, indice)
    return limitar_texto(f"{emoji} {nome_curto}", limite)


def criar_barra_progresso(percentual):
    preenchidos = round((max(0, min(100, percentual)) / 100) * BARRA_TAMANHO)
    return (BARRA_CHEIA * preenchidos) + (BARRA_VAZIA * (BARRA_TAMANHO - preenchidos))


def contar_votos_por_opcao(registro):
    contagem = {str(opcao.get("id")): 0 for opcao in registro.get("opcoes", [])}
    for opcao_id in (registro.get("votos") or {}).values():
        opcao_id = str(opcao_id)
        if opcao_id in contagem:
            contagem[opcao_id] += 1
    return contagem


def formatar_votante_embed(user_id, guild):
    try:
        member = guild.get_member(int(user_id)) if guild else None
    except (TypeError, ValueError):
        member = None

    if member:
        return f"{member.mention} (`{member.id}`)"
    return f"<@{user_id}> (`{user_id}`)"


def formatar_votante_txt(user_id, guild):
    try:
        member = guild.get_member(int(user_id)) if guild else None
    except (TypeError, ValueError):
        member = None

    if member:
        return f"{member.display_name} (@{member.name}) - {member.id}"
    return f"Usuario nao encontrado - {user_id}"


def criar_relatorio_votantes(registro, guild):
    votos = {str(user_id): str(opcao_id) for user_id, opcao_id in (registro.get("votos") or {}).items()}
    titulo = limitar_texto(registro.get("titulo") or "Enquete", 220)
    poll_id = str(registro.get("poll_id") or "sem-id")

    grupos = {}
    for indice, opcao in enumerate(registro.get("opcoes", []), start=1):
        opcao_id = str(opcao.get("id"))
        emoji, nome = obter_rotulo_opcao(opcao, indice)
        grupos[opcao_id] = {
            "rotulo": f"{emoji} {nome}",
            "votantes": [],
        }

    for user_id, opcao_id in votos.items():
        if opcao_id not in grupos:
            grupos[opcao_id] = {
                "rotulo": f"Opção removida/desconhecida ({opcao_id})",
                "votantes": [],
            }
        grupos[opcao_id]["votantes"].append(user_id)

    embed = discord.Embed(
        title="🗳️・Votantes da Enquete",
        description=f"**{titulo}**\nID: `{poll_id}`\nTotal de votos: `{len(votos)}`",
        color=POLL_COLOR,
    )

    linhas_txt = [
        f"Votantes da enquete: {titulo}",
        f"ID: {poll_id}",
        f"Total de votos: {len(votos)}",
        "",
    ]
    lista_truncada = False

    for grupo in grupos.values():
        votantes = sorted(grupo["votantes"], key=lambda item: int(item) if str(item).isdigit() else str(item))
        linhas_txt.append(f"{grupo['rotulo']} - {len(votantes)} voto(s)")

        if votantes:
            linhas_embed = []
            for user_id in votantes:
                linha = formatar_votante_embed(user_id, guild)
                valor_teste = "\n".join([*linhas_embed, linha])
                if len(valor_teste) > 900:
                    lista_truncada = True
                    break
                linhas_embed.append(linha)
                linhas_txt.append(f"- {formatar_votante_txt(user_id, guild)}")

            restantes = len(votantes) - len(linhas_embed)
            if restantes > 0:
                linhas_embed.append(f"... e mais {restantes} votante(s). Veja o arquivo anexado.")
                for user_id in votantes[len(linhas_embed) - 1 :]:
                    linhas_txt.append(f"- {formatar_votante_txt(user_id, guild)}")
        else:
            linhas_embed = ["Nenhum voto."]

        embed.add_field(
            name=limitar_texto(f"{grupo['rotulo']} — {len(votantes)} voto(s)", 256),
            value=limitar_texto("\n".join(linhas_embed), 1024),
            inline=False,
        )
        linhas_txt.append("")

    arquivo = None
    if votos and (lista_truncada or len(votos) > 15):
        conteudo = "\n".join(linhas_txt).encode("utf-8")
        arquivo = discord.File(io.BytesIO(conteudo), filename=f"votantes_{poll_id}.txt")
        embed.set_footer(text=f"{POLL_FOOTER} • Lista completa no arquivo anexado")
    else:
        embed.set_footer(text=POLL_FOOTER)

    return embed, arquivo


def calcular_resultado_vencedor(registro):
    contagem = contar_votos_por_opcao(registro)
    resultados = []
    for indice, opcao in enumerate(registro.get("opcoes", []), start=1):
        emoji, nome = obter_rotulo_opcao(opcao, indice)
        votos = contagem.get(str(opcao.get("id")), 0)
        resultados.append(
            {
                "indice": indice,
                "emoji": emoji,
                "nome": nome,
                "votos": votos,
            }
        )

    total_votos = sum(item["votos"] for item in resultados)
    maior_votacao = max((item["votos"] for item in resultados), default=0)
    vencedores = [item for item in resultados if total_votos > 0 and item["votos"] == maior_votacao]
    return {
        "total_votos": total_votos,
        "maior_votacao": maior_votacao,
        "vencedores": vencedores,
        "resultados": resultados,
    }


def criar_embed_resultado_vencedor(registro):
    resultado = calcular_resultado_vencedor(registro)
    titulo = limitar_texto(registro.get("titulo") or "Enquete", 220)
    status = str(registro.get("status") or "aberta").strip().capitalize()

    embed = discord.Embed(
        title="🏆・Resultado da Enquete",
        description=f"**{titulo}**",
        color=POLL_COLOR,
    )

    if resultado["total_votos"] <= 0:
        embed.add_field(
            name="📌 Resultado",
            value="Nenhum voto foi registrado nessa enquete.",
            inline=False,
        )
    elif len(resultado["vencedores"]) == 1:
        vencedor = resultado["vencedores"][0]
        embed.add_field(
            name="🏆 Vencedor",
            value=f"{vencedor['emoji']} **{vencedor['nome']}**\nVotos: `{vencedor['votos']}`",
            inline=False,
        )
    else:
        linhas_empate = [
            f"{item['emoji']} **{item['nome']}** - `{item['votos']}` voto(s)"
            for item in resultado["vencedores"]
        ]
        embed.add_field(
            name="🏆 Empate",
            value=limitar_texto("\n".join(linhas_empate), 1024),
            inline=False,
        )

    linhas_resultado = [
        f"{item['emoji']} **{item['nome']}** - `{item['votos']}` voto(s)"
        for item in resultado["resultados"]
    ]
    embed.add_field(
        name="📊 Resultado completo",
        value=limitar_texto("\n".join(linhas_resultado) or "Sem opções registradas.", 1024),
        inline=False,
    )
    embed.add_field(name="🧾 Total de votos", value=str(resultado["total_votos"]), inline=True)
    embed.add_field(name="📍 Status", value=status, inline=True)

    imagem = str(registro.get("imagem") or "").strip()
    if imagem and url_valida(imagem):
        embed.set_thumbnail(url=imagem)
    embed.set_footer(text=POLL_FOOTER)
    return embed


def criar_conteudo_enquete(registro):
    return ""


def criar_conteudo_previa(registro, prefixo):
    conteudo_enquete = criar_conteudo_enquete(registro)
    if not prefixo:
        return conteudo_enquete
    if not conteudo_enquete:
        return limitar_texto(prefixo, 2000)
    return limitar_texto(f"{prefixo}\n\n{conteudo_enquete}", 2000)


def criar_embed_imagem_principal(registro):
    imagem = str(registro.get("imagem") or "").strip()
    if not imagem or not url_valida(imagem):
        return None

    embed = discord.Embed(color=POLL_COLOR)
    embed.set_image(url=imagem)
    return embed


def criar_embed_opcao(registro, opcao, indice):
    contagem = contar_votos_por_opcao(registro)
    emoji, nome = obter_rotulo_opcao(opcao, indice)
    votos = contagem.get(str(opcao.get("id")), 0)
    total_votos = sum(contagem.values())
    percentual = (votos / total_votos * 100) if total_votos else 0
    barra = criar_barra_progresso(percentual)
    descricao_opcao = str(opcao.get("descricao") or "").strip()
    imagem_opcao = str(opcao.get("imagem") or "").strip()
    link_opcao = str(opcao.get("link") or "").strip()

    linhas = []
    if descricao_opcao:
        linhas.append(limitar_texto(descricao_opcao, 1100))
    if link_opcao:
        linhas.append(f"[Link da opção]({link_opcao})")
    linhas.append(f"`{barra}` {votos} voto(s) • {percentual:.0f}%")

    embed = discord.Embed(
        title=limitar_texto(f"{emoji} {nome}", 256),
        description=limitar_texto("\n\n".join(linhas), 4096),
        color=POLL_COLOR,
    )
    if imagem_opcao and url_valida(imagem_opcao):
        embed.set_image(url=imagem_opcao)
    return embed


def criar_embed_imagem_opcao(opcao, indice):
    imagem_opcao = str(opcao.get("imagem") or "").strip()
    if not imagem_opcao or not url_valida(imagem_opcao):
        return None

    emoji, nome = obter_rotulo_opcao(opcao, indice)
    descricao_opcao = str(opcao.get("descricao") or "").strip()
    link_opcao = str(opcao.get("link") or "").strip()

    linhas = []
    if descricao_opcao:
        linhas.append(limitar_texto(descricao_opcao, 1100))
    if link_opcao and url_valida(link_opcao):
        linhas.append(f"🔗 [Abrir link]({link_opcao})")

    embed = discord.Embed(
        title=limitar_texto(f"{emoji} {nome}", 256),
        description="\n\n".join(linhas) or None,
        color=POLL_COLOR,
    )
    embed.set_image(url=imagem_opcao)
    return embed


def criar_embeds_opcoes(registro):
    embeds = []
    for indice, opcao in enumerate(registro.get("opcoes", []), start=1):
        embeds.append(criar_embed_opcao(registro, opcao, indice))
    return embeds


def criar_embed_enquete_publica(registro):
    status = registro.get("status") or "aberta"
    titulo = limitar_texto(registro.get("titulo") or "Enquete", 240)
    descricao = limitar_texto(registro.get("descricao") or "", 900)
    encerrar_em = registro.get("encerrar_em")
    encerramento_horas = int(registro.get("encerramento_horas") or 0)

    linhas = []
    if descricao:
        linhas.append(descricao)

    if status == "encerrada":
        if linhas:
            linhas.append("")
        linhas.append("🔒 **Status:** Encerrada")
    elif status == "cancelada":
        if linhas:
            linhas.append("")
        linhas.append("🚫 **Status:** Cancelada")

    if encerrar_em:
        rotulo_encerramento = "Encerra em" if status == "aberta" else "Encerramento"
        linhas.append(f"⏳ **{rotulo_encerramento}:** {formatar_data_hora_iso(encerrar_em)}")
    elif status == "rascunho" and encerramento_horas:
        linhas.append(f"⏳ **Encerramento automático:** {encerramento_horas} hora(s) após publicar")
    elif status == "aberta":
        linhas.append("⏳ **Encerra em:** Sem encerramento automático")

    embed = discord.Embed(
        title=limitar_texto(f"📊 {titulo}", 256),
        description=limitar_texto("\n".join(linhas), 4096),
        color=POLL_COLOR,
    )

    imagem = str(registro.get("imagem") or "").strip()
    if imagem and url_valida(imagem):
        embed.set_image(url=imagem)
    embed.set_footer(text=POLL_FOOTER)
    return embed

def criar_embeds_enquete(registro):
    return [criar_embed_enquete_publica(registro), *criar_embeds_opcoes(registro)]

def validar_registro_enquete(registro):
    erros = []
    titulo = str(registro.get("titulo") or "").strip()
    descricao = str(registro.get("descricao") or "").strip()
    imagem = str(registro.get("imagem") or "").strip()
    opcoes = registro.get("opcoes") or []

    if not titulo:
        erros.append("Informe um título para a enquete.")
    if len(titulo) > 250:
        erros.append("O título da enquete pode ter no máximo 250 caracteres.")
    if len(descricao) > 3900:
        erros.append("A descrição da enquete pode ter no máximo 3900 caracteres.")
    if imagem and not url_valida(imagem):
        erros.append("A URL da imagem principal precisa começar com http:// ou https://.")
    if len(opcoes) < 2:
        erros.append("Adicione pelo menos 2 opções antes de publicar.")
    if len(opcoes) > MAX_OPTIONS:
        erros.append(f"A enquete pode ter no máximo {MAX_OPTIONS} opções.")

    for indice, opcao in enumerate(opcoes, start=1):
        nome = str(opcao.get("nome") or "").strip()
        descricao_opcao = str(opcao.get("descricao") or "").strip()
        imagem_opcao = str(opcao.get("imagem") or "").strip()
        link_opcao = str(opcao.get("link") or "").strip()
        if not nome:
            erros.append(f"A opção {indice} precisa ter nome.")
        if len(nome) > 90:
            erros.append(f"O nome da opção {indice} pode ter no máximo 90 caracteres.")
        if len(descricao_opcao) > 820:
            erros.append(f"A descrição da opção {indice} pode ter no máximo 820 caracteres.")
        if imagem_opcao and not url_valida(imagem_opcao):
            erros.append(f"A URL da imagem da opção {indice} precisa começar com http:// ou https://.")
        if link_opcao and not url_valida(link_opcao):
            erros.append(f"O link da opção {indice} precisa começar com http:// ou https://.")

    try:
        total = sum(contar_caracteres_embed(item) for item in criar_embeds_enquete(registro))
        if total > EMBED_TOTAL_MAX:
            erros.append(f"A embed ficaria com {total} caracteres. O limite do Discord é {EMBED_TOTAL_MAX}.")
    except Exception as erro:
        erros.append(f"Não consegui montar a embed da enquete: {erro}")

    return erros


@dataclass
class PollBuilderSession:
    cog: "PollsCog"
    guild_id: int
    author_id: int
    channel_id: int
    tempo_encerramento_horas: int = 0
    titulo: str = ""
    descricao: str = ""
    imagem: str = ""
    opcoes: list[dict] = field(default_factory=list)

    def criar_registro(self, poll_id=None, message_id=None, status="rascunho"):
        agora = datetime.now(FUSO_HORARIO)
        encerrar_em = None
        if status == "aberta" and self.tempo_encerramento_horas > 0:
            encerrar_em = (agora + timedelta(hours=self.tempo_encerramento_horas)).isoformat()

        return {
            "poll_id": poll_id or "preview",
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": message_id,
            "autor_id": self.author_id,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "imagem": self.imagem,
            "opcoes": list(self.opcoes),
            "votos": {},
            "status": status,
            "encerramento_horas": self.tempo_encerramento_horas,
            "encerrar_em": encerrar_em,
            "data_criacao": agora.isoformat(),
        }


async def responder_ephemeral(interaction, conteudo=None, **kwargs):
    if interaction.response.is_done():
        await interaction.followup.send(conteudo, ephemeral=True, **kwargs)
    else:
        await interaction.response.send_message(conteudo, ephemeral=True, **kwargs)


class PollInitialModal(discord.ui.Modal):
    def __init__(self, cog, interaction, tempo_encerramento_horas=0):
        super().__init__(title="Criar enquete")
        self.cog = cog
        self.guild_id = interaction.guild.id
        self.author_id = interaction.user.id
        self.default_channel_id = interaction.channel.id
        self.tempo_encerramento_horas = int(tempo_encerramento_horas or 0)
        self.titulo = discord.ui.TextInput(label="Título da enquete", max_length=250, required=True)
        self.descricao = discord.ui.TextInput(
            label="Descrição da enquete (opcional)",
            max_length=1200,
            required=False,
            style=discord.TextStyle.paragraph,
        )
        self.canal = discord.ui.TextInput(
            label="Canal de envio (opcional)",
            placeholder="Cole o ID ou mencione o canal. Vazio = canal atual.",
            max_length=100,
            required=False,
        )
        self.imagem = discord.ui.TextInput(
            label="Imagem principal URL (opcional)",
            placeholder="https://...",
            max_length=300,
            required=False,
        )
        self.add_item(self.titulo)
        self.add_item(self.descricao)
        self.add_item(self.canal)
        self.add_item(self.imagem)

    async def on_submit(self, interaction):
        canal = await self.cog.resolver_canal(interaction, str(self.canal.value), self.default_channel_id)
        if not canal:
            await responder_ephemeral(interaction, "Não consegui encontrar esse canal. Use ID, menção ou deixe vazio.")
            return

        imagem = str(self.imagem.value or "").strip()
        if imagem and not url_valida(imagem):
            await responder_ephemeral(interaction, "A URL da imagem principal precisa começar com http:// ou https://.")
            return

        session = PollBuilderSession(
            cog=self.cog,
            guild_id=self.guild_id,
            author_id=self.author_id,
            channel_id=canal.id,
            tempo_encerramento_horas=self.tempo_encerramento_horas,
            titulo=str(self.titulo.value).strip(),
            descricao=str(self.descricao.value).strip(),
            imagem=imagem,
        )
        registro = session.criar_registro()
        await interaction.response.send_message(
            content=criar_conteudo_previa(registro, f"Prévia da enquete. Canal de envio: {canal.mention}"),
            embeds=criar_embeds_enquete(registro),
            view=PollBuilderView(session),
            ephemeral=True,
        )


class PollOptionModal(discord.ui.Modal):
    def __init__(self, session, indice_opcao=None):
        self.indice_opcao = indice_opcao
        editando = indice_opcao is not None
        opcao = session.opcoes[indice_opcao] if editando else {}
        super().__init__(title="Editar opção" if editando else "Adicionar opção")
        self.session = session
        self.nome = discord.ui.TextInput(
            label="Nome da opção",
            max_length=90,
            required=True,
            default=str(opcao.get("nome") or ""),
        )
        self.descricao = discord.ui.TextInput(
            label="Descrição da opção (opcional)",
            max_length=820,
            required=False,
            style=discord.TextStyle.paragraph,
            default=str(opcao.get("descricao") or ""),
        )
        self.emoji = discord.ui.TextInput(
            label="Emoji ou letra (opcional)",
            max_length=20,
            required=False,
            default=str(opcao.get("emoji") or ""),
        )
        self.imagem = discord.ui.TextInput(
            label="Imagem da opção URL (opcional)",
            max_length=300,
            required=False,
            default=str(opcao.get("imagem") or ""),
        )
        self.link = discord.ui.TextInput(
            label="Link da opção URL (opcional)",
            max_length=300,
            required=False,
            default=str(opcao.get("link") or ""),
        )
        self.add_item(self.nome)
        self.add_item(self.descricao)
        self.add_item(self.emoji)
        self.add_item(self.imagem)
        self.add_item(self.link)

    async def on_submit(self, interaction):
        editando = self.indice_opcao is not None
        if not editando and len(self.session.opcoes) >= MAX_OPTIONS:
            await responder_ephemeral(interaction, f"A enquete já tem o limite de {MAX_OPTIONS} opções.")
            return

        imagem = str(self.imagem.value or "").strip()
        if imagem and not url_valida(imagem):
            await responder_ephemeral(interaction, "A URL da imagem da opção precisa começar com http:// ou https://.")
            return

        link = str(self.link.value or "").strip()
        if link and not url_valida(link):
            await responder_ephemeral(interaction, "O link da opção precisa começar com http:// ou https://.")
            return

        dados_opcao = {
            "id": self.session.opcoes[self.indice_opcao]["id"] if editando else f"opcao-{len(self.session.opcoes) + 1}",
            "nome": str(self.nome.value).strip(),
            "descricao": str(self.descricao.value).strip(),
            "emoji": str(self.emoji.value or "").strip(),
            "imagem": imagem,
            "link": link,
        }
        if editando:
            self.session.opcoes[self.indice_opcao] = dados_opcao
            mensagem = "Opção editada."
        else:
            self.session.opcoes.append(dados_opcao)
            mensagem = f"Opção adicionada. Total: {len(self.session.opcoes)}/{MAX_OPTIONS}."

        registro = self.session.criar_registro()
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, mensagem),
            embeds=criar_embeds_enquete(registro),
            view=PollBuilderView(self.session),
        )


class PollOptionActionSelect(discord.ui.Select):
    def __init__(self, session, action):
        self.session = session
        self.action = action
        options = []
        for indice, opcao in enumerate(session.opcoes, start=1):
            emoji, nome = obter_rotulo_opcao(opcao, indice)
            options.append(
                discord.SelectOption(
                    label=limitar_texto(f"{emoji} {nome}", 100),
                    value=str(indice - 1),
                    description="Editar esta opção." if action == "edit" else "Remover esta opção.",
                )
            )
        super().__init__(
            placeholder="Escolha a opção.",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        indice = int(self.values[0])
        if self.action == "edit":
            await interaction.response.send_modal(PollOptionModal(self.session, indice_opcao=indice))
            return

        removida = self.session.opcoes.pop(indice)
        registro = self.session.criar_registro()
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, f"Opção removida: {limitar_texto(removida.get('nome'), 100)}"),
            embeds=criar_embeds_enquete(registro),
            view=PollBuilderView(self.session),
        )


class PollOptionActionView(discord.ui.View):
    def __init__(self, session, action):
        super().__init__(timeout=180)
        self.session = session
        self.add_item(PollOptionActionSelect(session, action))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.session.author_id:
            await responder_ephemeral(interaction, "Essa edição de enquete não é sua.")
            return False
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode configurar enquetes.")
            return False
        return True


class PollEditContentModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Editar título e descrição")
        self.session = session
        self.titulo = discord.ui.TextInput(
            label="Título da enquete",
            max_length=250,
            required=True,
            default=session.titulo,
        )
        self.descricao = discord.ui.TextInput(
            label="Descrição da enquete (opcional)",
            max_length=1200,
            required=False,
            default=session.descricao,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.titulo)
        self.add_item(self.descricao)

    async def on_submit(self, interaction):
        self.session.titulo = str(self.titulo.value).strip()
        self.session.descricao = str(self.descricao.value).strip()
        registro = self.session.criar_registro()
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, "Título e descrição atualizados."),
            embeds=criar_embeds_enquete(registro),
            view=PollBuilderView(self.session),
        )


class PollEditImageModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Editar imagem")
        self.session = session
        self.imagem = discord.ui.TextInput(
            label="Imagem principal URL",
            placeholder="Deixe vazio para remover.",
            max_length=300,
            required=False,
            default=session.imagem,
        )
        self.add_item(self.imagem)

    async def on_submit(self, interaction):
        imagem = str(self.imagem.value or "").strip()
        if imagem and not url_valida(imagem):
            await responder_ephemeral(interaction, "A URL da imagem principal precisa começar com http:// ou https://.")
            return
        self.session.imagem = imagem
        registro = self.session.criar_registro()
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, "Imagem atualizada."),
            embeds=criar_embeds_enquete(registro),
            view=PollBuilderView(self.session),
        )


class PollPublishedEditContentModal(discord.ui.Modal):
    def __init__(self, cog, registro):
        super().__init__(title="Editar enquete publicada")
        self.cog = cog
        self.poll_id = registro["poll_id"]
        self.titulo = discord.ui.TextInput(
            label="Título da enquete",
            max_length=250,
            required=True,
            default=str(registro.get("titulo") or ""),
        )
        self.descricao = discord.ui.TextInput(
            label="Descrição da enquete (opcional)",
            max_length=1200,
            required=False,
            default=str(registro.get("descricao") or ""),
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.titulo)
        self.add_item(self.descricao)

    async def on_submit(self, interaction):
        await self.cog.aplicar_edicao_enquete_publicada(
            interaction,
            self.poll_id,
            "Título e descrição atualizados.",
            titulo=str(self.titulo.value).strip(),
            descricao=str(self.descricao.value).strip(),
        )


class PollPublishedEditImageModal(discord.ui.Modal):
    def __init__(self, cog, registro):
        super().__init__(title="Editar imagem da enquete")
        self.cog = cog
        self.poll_id = registro["poll_id"]
        self.imagem = discord.ui.TextInput(
            label="Imagem principal URL",
            placeholder="Deixe vazio para remover.",
            max_length=300,
            required=False,
            default=str(registro.get("imagem") or ""),
        )
        self.add_item(self.imagem)

    async def on_submit(self, interaction):
        imagem = str(self.imagem.value or "").strip()
        if imagem and not url_valida(imagem):
            await responder_ephemeral(interaction, "A URL da imagem principal precisa começar com http:// ou https://.")
            return
        await self.cog.aplicar_edicao_enquete_publicada(
            interaction,
            self.poll_id,
            "Imagem principal atualizada.",
            imagem=imagem,
        )


class PollPublishedOptionEditModal(discord.ui.Modal):
    def __init__(self, cog, registro, indice_opcao):
        self.cog = cog
        self.poll_id = registro["poll_id"]
        self.indice_opcao = indice_opcao
        opcao = registro["opcoes"][indice_opcao]
        super().__init__(title="Editar opção publicada")
        self.nome = discord.ui.TextInput(
            label="Nome da opção",
            max_length=90,
            required=True,
            default=str(opcao.get("nome") or ""),
        )
        self.descricao = discord.ui.TextInput(
            label="Descrição da opção (opcional)",
            max_length=820,
            required=False,
            style=discord.TextStyle.paragraph,
            default=str(opcao.get("descricao") or ""),
        )
        self.emoji = discord.ui.TextInput(
            label="Emoji ou letra (opcional)",
            max_length=20,
            required=False,
            default=str(opcao.get("emoji") or ""),
        )
        self.imagem = discord.ui.TextInput(
            label="Imagem da opção URL (opcional)",
            max_length=300,
            required=False,
            default=str(opcao.get("imagem") or ""),
        )
        self.link = discord.ui.TextInput(
            label="Link da opção URL (opcional)",
            max_length=300,
            required=False,
            default=str(opcao.get("link") or ""),
        )
        self.add_item(self.nome)
        self.add_item(self.descricao)
        self.add_item(self.emoji)
        self.add_item(self.imagem)
        self.add_item(self.link)

    async def on_submit(self, interaction):
        imagem = str(self.imagem.value or "").strip()
        if imagem and not url_valida(imagem):
            await responder_ephemeral(interaction, "A URL da imagem da opção precisa começar com http:// ou https://.")
            return

        link = str(self.link.value or "").strip()
        if link and not url_valida(link):
            await responder_ephemeral(interaction, "O link da opção precisa começar com http:// ou https://.")
            return

        registro = obter_poll(self.poll_id)
        if not registro:
            await responder_ephemeral(interaction, "Não encontrei essa enquete nos dados salvos.")
            return
        opcoes = list(registro.get("opcoes") or [])
        if self.indice_opcao >= len(opcoes):
            await responder_ephemeral(interaction, "Essa opção não existe mais.")
            return

        opcoes[self.indice_opcao] = {
            "id": opcoes[self.indice_opcao]["id"],
            "nome": str(self.nome.value).strip(),
            "descricao": str(self.descricao.value).strip(),
            "emoji": str(self.emoji.value or "").strip(),
            "imagem": imagem,
            "link": link,
        }
        await self.cog.aplicar_edicao_enquete_publicada(
            interaction,
            self.poll_id,
            "Opção atualizada. Votos preservados.",
            opcoes=opcoes,
        )


class PollPublishedOptionSelect(discord.ui.Select):
    def __init__(self, cog, registro):
        self.cog = cog
        self.poll_id = registro["poll_id"]
        options = []
        for indice, opcao in enumerate(registro.get("opcoes", []), start=1):
            emoji, nome = obter_rotulo_opcao(opcao, indice)
            options.append(
                discord.SelectOption(
                    label=limitar_texto(f"{emoji} {nome}", 100),
                    value=str(indice - 1),
                    description="Editar texto, imagem ou link desta opção.",
                )
            )
        super().__init__(
            placeholder="Escolha a opção que deseja editar.",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        registro = obter_poll(self.poll_id)
        if not registro:
            await responder_ephemeral(interaction, "Não encontrei essa enquete nos dados salvos.")
            return
        indice = int(self.values[0])
        if indice >= len(registro.get("opcoes") or []):
            await responder_ephemeral(interaction, "Essa opção não existe mais.")
            return
        await interaction.response.send_modal(PollPublishedOptionEditModal(self.cog, registro, indice))


class PollPublishedOptionSelectView(discord.ui.View):
    def __init__(self, cog, poll_id):
        super().__init__(timeout=180)
        registro = obter_poll(poll_id)
        self.cog = cog
        self.poll_id = poll_id
        if registro and registro.get("opcoes"):
            self.add_item(PollPublishedOptionSelect(cog, registro))

    async def interaction_check(self, interaction):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode editar enquetes.")
            return False
        return True


class PollPublishedEditView(discord.ui.View):
    def __init__(self, cog, poll_id):
        super().__init__(timeout=900)
        self.cog = cog
        self.poll_id = poll_id

    async def interaction_check(self, interaction):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode editar enquetes.")
            return False
        return True

    @discord.ui.button(label="Editar título/descrição", emoji="📝", style=discord.ButtonStyle.secondary)
    async def editar_conteudo(self, interaction, button):
        registro = obter_poll(self.poll_id)
        if not registro:
            await responder_ephemeral(interaction, "Não encontrei essa enquete nos dados salvos.")
            return
        await interaction.response.send_modal(PollPublishedEditContentModal(self.cog, registro))

    @discord.ui.button(label="Editar imagem principal", emoji="🖼️", style=discord.ButtonStyle.secondary)
    async def editar_imagem(self, interaction, button):
        registro = obter_poll(self.poll_id)
        if not registro:
            await responder_ephemeral(interaction, "Não encontrei essa enquete nos dados salvos.")
            return
        await interaction.response.send_modal(PollPublishedEditImageModal(self.cog, registro))

    @discord.ui.button(label="Editar opção", emoji="✏️", style=discord.ButtonStyle.primary)
    async def editar_opcao(self, interaction, button):
        registro = obter_poll(self.poll_id)
        if not registro:
            await responder_ephemeral(interaction, "Não encontrei essa enquete nos dados salvos.")
            return
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, "Escolha a opção publicada que deseja editar."),
            embeds=criar_embeds_enquete(registro),
            view=PollPublishedOptionSelectView(self.cog, self.poll_id),
        )

    @discord.ui.button(label="Atualizar prévia", emoji="👀", style=discord.ButtonStyle.secondary, row=1)
    async def atualizar_previa(self, interaction, button):
        registro = obter_poll(self.poll_id)
        if not registro:
            await responder_ephemeral(interaction, "Não encontrei essa enquete nos dados salvos.")
            return
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, "Painel de edição da enquete publicada."),
            embeds=criar_embeds_enquete(registro),
            view=PollPublishedEditView(self.cog, self.poll_id),
        )

    @discord.ui.button(label="Fechar painel", emoji="❌", style=discord.ButtonStyle.danger, row=1)
    async def fechar(self, interaction, button):
        await interaction.response.edit_message(content="Painel de edição fechado.", embeds=[], view=None)


class PollBuilderView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    async def interaction_check(self, interaction):
        if interaction.user.id != self.session.author_id:
            await responder_ephemeral(interaction, "Essa edição de enquete não é sua.")
            return False
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode configurar enquetes.")
            return False
        return True

    @discord.ui.button(label="Adicionar opção", emoji="➕", style=discord.ButtonStyle.primary)
    async def adicionar_opcao(self, interaction, button):
        if len(self.session.opcoes) >= MAX_OPTIONS:
            await responder_ephemeral(interaction, f"A enquete já tem o limite de {MAX_OPTIONS} opções.")
            return
        await interaction.response.send_modal(PollOptionModal(self.session))

    @discord.ui.button(label="Editar opção", emoji="✏️", style=discord.ButtonStyle.secondary)
    async def editar_opcao(self, interaction, button):
        if not self.session.opcoes:
            await responder_ephemeral(interaction, "Adicione uma opção antes de editar.")
            return
        registro = self.session.criar_registro()
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, "Escolha a opção que deseja editar."),
            embeds=criar_embeds_enquete(registro),
            view=PollOptionActionView(self.session, "edit"),
        )

    @discord.ui.button(label="Remover opção", emoji="🗑️", style=discord.ButtonStyle.secondary)
    async def remover_opcao(self, interaction, button):
        if not self.session.opcoes:
            await responder_ephemeral(interaction, "Adicione uma opção antes de remover.")
            return
        registro = self.session.criar_registro()
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, "Escolha a opção que deseja remover."),
            embeds=criar_embeds_enquete(registro),
            view=PollOptionActionView(self.session, "remove"),
        )

    @discord.ui.button(label="Editar título/descrição", emoji="📝", style=discord.ButtonStyle.secondary)
    async def editar_conteudo(self, interaction, button):
        await interaction.response.send_modal(PollEditContentModal(self.session))

    @discord.ui.button(label="Editar imagem", emoji="🖼️", style=discord.ButtonStyle.secondary, row=1)
    async def editar_imagem(self, interaction, button):
        await interaction.response.send_modal(PollEditImageModal(self.session))

    @discord.ui.button(label="Pré-visualizar", emoji="👀", style=discord.ButtonStyle.secondary, row=1)
    async def pre_visualizar(self, interaction, button):
        registro = self.session.criar_registro()
        erros = validar_registro_enquete(registro)
        content = "Prévia atualizada."
        if erros:
            content = "Prévia atualizada, mas ainda há ajustes:\n" + "\n".join(f"- {erro}" for erro in erros[:8])
        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro, content),
            embeds=criar_embeds_enquete(registro),
            view=PollBuilderView(self.session),
        )

    @discord.ui.button(label="Publicar", emoji="✅", style=discord.ButtonStyle.success, row=1)
    async def publicar(self, interaction, button):
        erros = validar_registro_enquete(self.session.criar_registro())
        if erros:
            await responder_ephemeral(interaction, "\n".join(f"- {erro}" for erro in erros[:10]))
            return

        canal = await self.session.cog.resolver_canal(interaction, str(self.session.channel_id), self.session.channel_id)
        if not canal:
            await responder_ephemeral(interaction, "Não consegui encontrar o canal de envio da enquete.")
            return

        poll_id = gerar_id_poll()
        registro = self.session.criar_registro(poll_id=poll_id, status="aberta")
        view = criar_view_votacao_publica(self.session.cog, registro)

        try:
            mensagem = await canal.send(
                content=criar_conteudo_enquete(registro),
                embeds=criar_embeds_enquete(registro),
                view=view,
            )
        except discord.HTTPException as erro:
            print(f"[POLLS] Erro ao publicar enquete | guild={interaction.guild.id} | erro={erro!r}")
            await responder_ephemeral(interaction, "Não consegui publicar a enquete por um erro do Discord.")
            return

        registro["message_id"] = mensagem.id
        registro["channel_id"] = canal.id
        salvar_poll(registro)
        self.session.cog.agendar_encerramento_poll(registro)
        await interaction.response.edit_message(
            content=(
                f"✅ Enquete publicada em {canal.mention}.\n"
                f"ID da enquete: `{poll_id}`\n"
                "Use `/enquete encerrar`, `/enquete cancelar`, `/enquete resultados` ou `/enquete vencedor` com o ID, link ou ID da mensagem."
            ),
            embeds=[],
            view=None,
        )

    @discord.ui.button(label="Cancelar", emoji="❌", style=discord.ButtonStyle.danger, row=1)
    async def cancelar(self, interaction, button):
        await interaction.response.edit_message(content="Criação da enquete cancelada.", embeds=[], view=None)


class PollVoteButton(discord.ui.Button):
    def __init__(self, cog, poll_id, opcao, indice, disabled=False):
        super().__init__(
            label=criar_label_voto_opcao(opcao, indice),
            style=discord.ButtonStyle.secondary,
            custom_id=f"poll_vote:{poll_id}:{opcao['id']}",
            disabled=disabled,
        )
        self.cog = cog
        self.poll_id = poll_id
        self.opcao_id = opcao["id"]

    async def callback(self, interaction):
        await self.cog.processar_voto(interaction, self.poll_id, self.opcao_id)


class PollVoteSelect(discord.ui.Select):
    def __init__(self, cog, registro, disabled=False):
        self.cog = cog
        self.poll_id = registro["poll_id"]
        options = []
        for indice, opcao in enumerate(registro.get("opcoes", []), start=1):
            descricao = limitar_texto(opcao.get("descricao"), 90) or None
            options.append(
                discord.SelectOption(
                    label=criar_label_voto_opcao(opcao, indice, limite=90),
                    value=str(opcao["id"]),
                    description=descricao,
                )
            )
        super().__init__(
            placeholder="Escolha seu voto",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"poll_select:{self.poll_id}",
            disabled=disabled,
        )

    async def callback(self, interaction):
        await self.cog.processar_voto(interaction, self.poll_id, self.values[0])


class PollPublicVoteView(discord.ui.View):
    def __init__(self, cog, registro, disabled=False):
        super().__init__(timeout=None)
        opcoes = registro.get("opcoes", [])
        if len(opcoes) <= 2:
            for indice, opcao in enumerate(opcoes, start=1):
                self.add_item(PollVoteButton(cog, registro["poll_id"], opcao, indice, disabled=disabled))
        else:
            self.add_item(PollVoteSelect(cog, registro, disabled=disabled))


def criar_view_votacao_publica(cog, registro):
    disabled = registro.get("status") != "aberta"
    return PollPublicVoteView(cog, registro, disabled=disabled)


class PollsCog(commands.Cog):
    enquete = app_commands.Group(name="enquete", description="Sistema de enquetes da FDN.")

    def __init__(self, bot):
        self.bot = bot
        self._locks_poll = {}
        self._tasks_encerramento = {}
        self.registrar_views_persistentes()

    def registrar_views_persistentes(self):
        for registro in listar_polls_abertas():
            message_id = registro.get("message_id")
            if not message_id:
                continue
            try:
                self.bot.add_view(criar_view_votacao_publica(self, registro), message_id=int(message_id))
                self.agendar_encerramento_poll(registro)
            except Exception as erro:
                print(f"[POLLS] Erro ao registrar view persistente | poll={registro.get('poll_id')} | erro={erro!r}")

    async def _reaplicar_layout_polls_salvas(self):
        await self.bot.wait_until_ready()
        atualizadas = 0
        removidas = 0
        for registro in listar_polls_com_mensagem():
            try:
                resultado = await self.editar_mensagem_enquete(registro)
                if resultado is True:
                    atualizadas += 1
                    await asyncio.sleep(0.8)
                elif resultado == "missing":
                    removidas += 1
            except Exception as erro:
                print(f"[POLLS] Erro ao reaplicar layout da enquete | poll={registro.get('poll_id')} | erro={erro!r}")
        if atualizadas:
            print(f"[POLLS] Layout reaplicado em {atualizadas} enquete(s) salvas.")
        if removidas:
            print(f"[POLLS] {removidas} enquete(s) com mensagem inexistente foram desassociadas do arquivo.")

    def obter_lock_poll(self, poll_id):
        poll_id = str(poll_id)
        lock = self._locks_poll.get(poll_id)
        if lock is None:
            lock = self._locks_poll[poll_id] = asyncio.Lock()
        return lock

    def cancelar_agendamento_poll(self, poll_id):
        task = self._tasks_encerramento.pop(str(poll_id), None)
        if task and not task.done():
            task.cancel()

    def agendar_encerramento_poll(self, registro):
        poll_id = str(registro.get("poll_id") or "")
        if not poll_id or registro.get("status") != "aberta":
            return
        if not registro.get("encerrar_em"):
            return
        if segundos_ate_data_iso(registro.get("encerrar_em")) is None:
            return

        self.cancelar_agendamento_poll(poll_id)
        task = self.bot.loop.create_task(self._encerrar_poll_automaticamente(poll_id))
        self._tasks_encerramento[poll_id] = task
        task.add_done_callback(lambda _task, pid=poll_id: self._tasks_encerramento.pop(pid, None))

    async def _encerrar_poll_automaticamente(self, poll_id):
        try:
            while True:
                registro = obter_poll(poll_id)
                if not registro or registro.get("status") != "aberta":
                    return

                segundos = segundos_ate_data_iso(registro.get("encerrar_em"))
                if segundos is None:
                    return
                if segundos > 0:
                    await asyncio.sleep(segundos)
                    continue

                async with self.obter_lock_poll(poll_id):
                    registro = obter_poll(poll_id)
                    if not registro or registro.get("status") != "aberta":
                        return
                    segundos = segundos_ate_data_iso(registro.get("encerrar_em"))
                    if segundos is None or segundos > 0:
                        continue
                    registro = atualizar_poll(
                        poll_id,
                        status="encerrada",
                        encerrado_automaticamente=True,
                    )
                    if registro:
                        await self.editar_mensagem_enquete(registro)
                        print(f"[POLLS] Enquete encerrada automaticamente | poll={poll_id}")
                return
        except asyncio.CancelledError:
            return
        except Exception as erro:
            print(f"[POLLS] Erro no encerramento automatico | poll={poll_id} | erro={erro!r}")

    async def resolver_canal(self, interaction, texto, canal_padrao_id):
        texto = str(texto or "").strip()
        canal_id = canal_padrao_id
        if texto:
            if texto.startswith("<#") and texto.endswith(">"):
                texto = texto.replace("<#", "").replace(">", "").strip()
            if not texto.isdigit():
                return None
            canal_id = int(texto)

        canal = interaction.client.get_channel(int(canal_id))
        if canal is None:
            try:
                canal = await interaction.client.fetch_channel(int(canal_id))
            except Exception:
                canal = None

        if not canal or getattr(getattr(canal, "guild", None), "id", None) != interaction.guild.id:
            return None
        return canal

    def resolver_poll(self, identificador):
        texto = str(identificador or "").strip()
        registro = obter_poll(texto)
        if registro:
            return registro
        message_id = extrair_id_mensagem(texto)
        if message_id:
            return obter_poll_por_message_id(message_id)
        return None

    async def obter_canal_enquete(self, registro):
        canal = self.bot.get_channel(int(registro.get("channel_id") or 0))
        if canal is None:
            try:
                canal = await self.bot.fetch_channel(int(registro.get("channel_id") or 0))
            except Exception:
                canal = None
        return canal

    async def publicar_resultado_vencedor(self, registro):
        canal = await self.obter_canal_enquete(registro)
        if not canal:
            return None, "Não consegui encontrar o canal original da enquete."

        try:
            mensagem = await canal.send(
                content=f"🏆 **Resultado da enquete `{registro.get('poll_id')}`**",
                embed=criar_embed_resultado_vencedor(registro),
            )
            print(
                f"[POLLS] Resultado publicado | poll={registro.get('poll_id')} | "
                f"channel={getattr(canal, 'id', None)} | message={getattr(mensagem, 'id', None)}"
            )
            return mensagem, None
        except Exception as erro:
            print(f"[POLLS] Erro ao publicar resultado | poll={registro.get('poll_id')} | erro={erro!r}")
            return None, "Não consegui publicar o resultado por um erro do Discord."

    async def editar_mensagem_enquete(self, registro):
        canal = await self.obter_canal_enquete(registro)
        if not canal:
            return False

        try:
            mensagem = await canal.fetch_message(int(registro.get("message_id")))
            await mensagem.edit(
                content=criar_conteudo_enquete(registro),
                embeds=criar_embeds_enquete(registro),
                view=criar_view_votacao_publica(self, registro),
            )
            return True
        except discord.NotFound:
            atualizar_poll(registro.get("poll_id"), message_id=None)
            print(
                f"[POLLS] Mensagem da enquete nao encontrada | poll={registro.get('poll_id')} | "
                "message_id removido do arquivo"
            )
            return "missing"
        except discord.HTTPException as erro:
            print(f"[POLLS] Erro HTTP ao atualizar enquete | poll={registro.get('poll_id')} | erro={erro!r}")
            return False
        except Exception as erro:
            print(f"[POLLS] Erro ao atualizar mensagem da enquete | poll={registro.get('poll_id')} | erro={erro!r}")
            return False

    async def aplicar_edicao_enquete_publicada(self, interaction, poll_id, mensagem_sucesso, **alteracoes):
        async with self.obter_lock_poll(poll_id):
            registro = obter_poll(poll_id)
            if not registro:
                await responder_ephemeral(interaction, "Não encontrei essa enquete nos dados salvos.")
                return

            if int(registro.get("guild_id") or 0) != interaction.guild.id:
                await responder_ephemeral(interaction, "Essa enquete não pertence a este servidor.")
                return

            registro_teste = dict(registro)
            registro_teste.update(alteracoes)
            erros = validar_registro_enquete(registro_teste)
            if erros:
                await responder_ephemeral(interaction, "\n".join(f"- {erro}" for erro in erros[:10]))
                return

            registro_atualizado = atualizar_poll(poll_id, **alteracoes)
            if not registro_atualizado:
                await responder_ephemeral(interaction, "Não consegui salvar a edição da enquete.")
                return

            mensagem_editada = await self.editar_mensagem_enquete(registro_atualizado)

        aviso = mensagem_sucesso
        if not mensagem_editada:
            aviso += "\nA edição foi salva, mas não consegui editar a mensagem pública da enquete."

        await interaction.response.edit_message(
            content=criar_conteudo_previa(registro_atualizado, aviso),
            embeds=criar_embeds_enquete(registro_atualizado),
            view=PollPublishedEditView(self, poll_id),
        )

    async def processar_voto(self, interaction, poll_id, opcao_id):
        await interaction.response.defer(ephemeral=True)

        async with self.obter_lock_poll(poll_id):
            registro, voto_atualizado, erro = registrar_voto_poll(poll_id, interaction.user.id, opcao_id)
            if erro:
                await interaction.followup.send(f"❌ {erro}", ephemeral=True)
                return
            await self.editar_mensagem_enquete(registro)

        if voto_atualizado:
            await interaction.followup.send("🔄 Seu voto foi atualizado.", ephemeral=True)
        else:
            await interaction.followup.send("✅ Seu voto foi registrado.", ephemeral=True)

    @enquete.command(name="criar", description="Cria uma enquete personalizada.")
    @app_commands.describe(tempo_encerramento="Tempo para encerrar a enquete automaticamente.")
    @app_commands.choices(
        tempo_encerramento=[
            app_commands.Choice(name="2 horas", value=2),
            app_commands.Choice(name="4 horas", value=4),
            app_commands.Choice(name="6 horas", value=6),
            app_commands.Choice(name="12 horas", value=12),
            app_commands.Choice(name="24 horas", value=24),
            app_commands.Choice(name="48 horas", value=48),
        ]
    )
    @app_commands.guild_only()
    async def slash_criar(self, interaction, tempo_encerramento: int = 0):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode criar enquetes.")
            return
        if int(tempo_encerramento or 0) not in TEMPOS_ENCERRAMENTO_HORAS:
            await responder_ephemeral(interaction, "Escolha um tempo de encerramento válido.")
            return
        await interaction.response.send_modal(
            PollInitialModal(self, interaction, tempo_encerramento_horas=tempo_encerramento)
        )

    @enquete.command(name="editar", description="Edita uma enquete já publicada sem alterar votos.")
    @app_commands.describe(identificador="ID da enquete, ID da mensagem ou link da mensagem.")
    @app_commands.guild_only()
    async def slash_editar(self, interaction, identificador: str):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode editar enquetes.")
            return

        registro = self.resolver_poll(identificador)
        if not registro or int(registro.get("guild_id") or 0) != interaction.guild.id:
            await responder_ephemeral(interaction, "Não encontrei essa enquete neste servidor.")
            return

        mensagem_atualizada = await self.editar_mensagem_enquete(registro)
        aviso = "Painel de edição da enquete publicada. Os votos e resultados serão preservados."
        if not mensagem_atualizada:
            aviso += "\nAviso: nao consegui atualizar a mensagem publica agora."

        await interaction.response.send_message(
            content=criar_conteudo_previa(registro, aviso),
            embeds=criar_embeds_enquete(registro),
            view=PollPublishedEditView(self, registro["poll_id"]),
            ephemeral=True,
        )

    @enquete.command(name="atualizar", description="Reaplica o visual atual em uma enquete já publicada.")
    @app_commands.describe(identificador="ID da enquete, ID da mensagem ou link da mensagem.")
    @app_commands.guild_only()
    async def slash_atualizar(self, interaction, identificador: str):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode atualizar enquetes.")
            return

        registro = self.resolver_poll(identificador)
        if not registro or int(registro.get("guild_id") or 0) != interaction.guild.id:
            await responder_ephemeral(interaction, "Não encontrei essa enquete neste servidor.")
            return

        mensagem_atualizada = await self.editar_mensagem_enquete(registro)
        if not mensagem_atualizada:
            await responder_ephemeral(interaction, "Não consegui atualizar a mensagem pública dessa enquete.")
            return

        await responder_ephemeral(
            interaction,
            "✅ Enquete atualizada com o visual mais recente. Descrição, links e imagens foram reaplicados na mensagem pública.",
        )

    @enquete.command(name="resultados", description="Mostra os resultados de uma enquete.")
    @app_commands.describe(identificador="ID da enquete, ID da mensagem ou link da mensagem.")
    @app_commands.guild_only()
    async def slash_resultados(self, interaction, identificador: str):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode ver resultados por comando.")
            return

        registro = self.resolver_poll(identificador)
        if not registro or int(registro.get("guild_id") or 0) != interaction.guild.id:
            await responder_ephemeral(interaction, "Não encontrei essa enquete neste servidor.")
            return

        await interaction.response.send_message(
            content=criar_conteudo_enquete(registro),
            embeds=criar_embeds_enquete(registro),
            ephemeral=True,
        )

    @enquete.command(name="votantes", description="Mostra quem votou em uma enquete.")
    @app_commands.describe(identificador="ID da enquete, ID da mensagem ou link da mensagem.")
    @app_commands.guild_only()
    async def slash_votantes(self, interaction, identificador: str):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode ver quem votou em enquetes.")
            return

        registro = self.resolver_poll(identificador)
        if not registro or int(registro.get("guild_id") or 0) != interaction.guild.id:
            await responder_ephemeral(interaction, "Não encontrei essa enquete neste servidor.")
            return

        embed, arquivo = criar_relatorio_votantes(registro, interaction.guild)
        kwargs = {
            "embed": embed,
            "ephemeral": True,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if arquivo:
            kwargs["file"] = arquivo
        await interaction.response.send_message(**kwargs)

    @enquete.command(name="vencedor", description="Publica o vencedor de uma enquete para todos.")
    @app_commands.describe(identificador="ID da enquete, ID da mensagem ou link da mensagem.")
    @app_commands.guild_only()
    async def slash_vencedor(self, interaction, identificador: str):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode publicar o vencedor de enquetes.")
            return

        registro = self.resolver_poll(identificador)
        if not registro or int(registro.get("guild_id") or 0) != interaction.guild.id:
            await responder_ephemeral(interaction, "Não encontrei essa enquete neste servidor.")
            return

        if registro.get("status") == "aberta":
            await responder_ephemeral(interaction, "Encerre a enquete antes de publicar o vencedor.")
            return
        if registro.get("status") == "cancelada":
            await responder_ephemeral(interaction, "Essa enquete foi cancelada e não tem vencedor.")
            return

        await interaction.response.defer(ephemeral=True)
        mensagem, erro = await self.publicar_resultado_vencedor(registro)
        if erro:
            await interaction.followup.send(f"❌ {erro}", ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ Resultado publicado em {mensagem.channel.mention}.",
            ephemeral=True,
        )

    @enquete.command(name="encerrar", description="Encerra uma enquete e bloqueia novos votos.")
    @app_commands.describe(
        identificador="ID da enquete, ID da mensagem ou link da mensagem.",
        postar_resultado="Se ativar, publica o vencedor no canal da enquete.",
    )
    @app_commands.guild_only()
    async def slash_encerrar(self, interaction, identificador: str, postar_resultado: bool = False):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode encerrar enquetes.")
            return

        registro = self.resolver_poll(identificador)
        if not registro or int(registro.get("guild_id") or 0) != interaction.guild.id:
            await responder_ephemeral(interaction, "Não encontrei essa enquete neste servidor.")
            return

        if registro.get("status") != "aberta":
            await responder_ephemeral(interaction, "Essa enquete já não está aberta.")
            return

        async with self.obter_lock_poll(registro["poll_id"]):
            registro = atualizar_poll(registro["poll_id"], status="encerrada")
            await self.editar_mensagem_enquete(registro)
        self.cancelar_agendamento_poll(registro["poll_id"])

        aviso = f"🔒 Enquete `{registro['poll_id']}` encerrada."
        if postar_resultado:
            mensagem, erro = await self.publicar_resultado_vencedor(registro)
            if erro:
                aviso += f"\n❌ {erro}"
            else:
                aviso += f"\n✅ Resultado publicado em {mensagem.channel.mention}."
        await responder_ephemeral(interaction, aviso)

    @enquete.command(name="cancelar", description="Cancela uma enquete e bloqueia novos votos.")
    @app_commands.describe(identificador="ID da enquete, ID da mensagem ou link da mensagem.")
    @app_commands.guild_only()
    async def slash_cancelar(self, interaction, identificador: str):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode cancelar enquetes.")
            return

        registro = self.resolver_poll(identificador)
        if not registro or int(registro.get("guild_id") or 0) != interaction.guild.id:
            await responder_ephemeral(interaction, "Não encontrei essa enquete neste servidor.")
            return

        if registro.get("status") != "aberta":
            await responder_ephemeral(interaction, "Essa enquete já não está aberta.")
            return

        async with self.obter_lock_poll(registro["poll_id"]):
            registro = atualizar_poll(registro["poll_id"], status="cancelada")
            await self.editar_mensagem_enquete(registro)
        self.cancelar_agendamento_poll(registro["poll_id"])
        await responder_ephemeral(interaction, f"🗑️ Enquete `{registro['poll_id']}` cancelada.")


async def setup(bot):
    await bot.add_cog(PollsCog(bot))
