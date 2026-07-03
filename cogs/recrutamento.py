import re

import discord
from discord.ext import commands

from config import (
    CANAL_CONTAGEM_ID,
    CARGO_RECRUTAMENTO_ID,
    REC_EMOJI_ADD,
    REC_EMOJI_INFO,
    REC_EMOJI_RANKING,
    REC_EMOJI_REMOVE,
    REC_EMOJI_TITLE,
    REC_EMOJI_UPDATE,
    REC_PANEL_CHANNEL_ID,
)
from services.d1 import (
    buscar_recrutamentos_do_recrutador,
    ranking_recrutadores_mes,
    registrar_recrutamento,
    remover_ultimo_recrutamento_do_recrutador,
    resetar_recrutamentos_mes,
    total_recrutamentos_mes,
)
from services.logs import enviar_log_bot
from services.server_config import obter_valor_config
from utils.discord_helpers import (
    buscar_mensagem_recrutamento_por_id,
    criar_embed_tags,
    extrair_recrutado_de_mensagem_antiga,
    membro_eh_staff,
    mensagem_eh_recrutamento,
    procurar_membro_por_texto,
)
from utils.time_utils import formatar_data_br, mes_referencia_atual


REC_PANEL_COLOR = discord.Color.from_rgb(0, 255, 255)
REC_PANEL_TITLE_TEXT = "Painel de Recrutamento — FDN"
REC_PANEL_FOOTER = "FDN • Sistema de Recrutamento"
REC_MANAGE_ROLE_ID = 1478800416945995849
REC_PANEL_DESCRIPTION = (
    "Acompanhe e gerencie os recrutamentos registrados no mês atual.\n\n"
    "Os pontos são contabilizados automaticamente pelo fluxo de +1 no canal de contagem "
    "ou adicionados manualmente pela staff.\n\n"
    "Use os botões abaixo para consultar o ranking, verificar um recrutador ou registrar ajustes."
)


def criar_embed_rec(titulo, descricao=None):
    embed = discord.Embed(
        title=titulo,
        description=descricao or "",
        color=REC_PANEL_COLOR,
    )
    embed.set_footer(text=REC_PANEL_FOOTER)
    return embed


def criar_embed_painel_rec():
    return criar_embed_rec(
        f"{resolver_emoji_texto_painel_rec(REC_EMOJI_TITLE, '🌙')} {REC_PANEL_TITLE_TEXT}",
        REC_PANEL_DESCRIPTION,
    )


def resolver_emoji_painel_rec(emoji_config, fallback):
    emoji_texto = (emoji_config or "").strip()
    if not emoji_texto:
        return fallback

    try:
        emoji = discord.PartialEmoji.from_str(emoji_texto)
    except Exception:
        return fallback

    if getattr(emoji, "id", None):
        return emoji

    if emoji.is_unicode_emoji():
        emoji_unicode = str(emoji).strip()
        return emoji_unicode or fallback

    return fallback


def resolver_emoji_texto_painel_rec(emoji_config, fallback):
    emoji = resolver_emoji_painel_rec(emoji_config, fallback)
    emoji_texto = str(emoji).strip()
    return emoji_texto or fallback


def extrair_id_discord(texto):
    match = re.search(r"\d{15,25}", texto or "")
    if not match:
        return None
    return match.group(0)


def formatar_posicao(numero):
    return f"{numero}º" if numero else "Sem posição"


def normalizar_id_config(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def obter_cargo_recrutamento_id(guild=None):
    return normalizar_id_config(obter_valor_config(guild, "CARGO_RECRUTAMENTO_ID", CARGO_RECRUTAMENTO_ID))


def membro_tem_cargo_id(membro, cargo_id):
    if not hasattr(membro, "roles"):
        return False

    return any(cargo.id == cargo_id for cargo in membro.roles)


def membro_eh_recrutamento(membro):
    if not hasattr(membro, "roles"):
        return False

    cargo_recrutamento_id = obter_cargo_recrutamento_id(getattr(membro, "guild", None))
    for cargo in membro.roles:
        if cargo.id == cargo_recrutamento_id:
            return True

    return False


def listar_membros_recrutamento(guild):
    cargo_recrutamento_id = obter_cargo_recrutamento_id(guild)
    if not guild or not cargo_recrutamento_id:
        return []

    cargo = guild.get_role(cargo_recrutamento_id)
    if cargo is not None:
        membros = list(cargo.members)
    else:
        membros = [
            membro
            for membro in getattr(guild, "members", [])
            if any(cargo.id == cargo_recrutamento_id for cargo in getattr(membro, "roles", []))
        ]

    membros_unicos = {membro.id: membro for membro in membros}
    return sorted(
        membros_unicos.values(),
        key=lambda membro: (membro.display_name or membro.name or str(membro.id)).casefold(),
    )


class RecInfoModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Buscar Recrutador")
        self.cog = cog
        self.membro = discord.ui.TextInput(
            label="Membro",
            placeholder="Informe a menção, ID ou nome do recrutador.",
            required=True,
            max_length=100,
        )
        self.add_item(self.membro)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.cog.responder_info_recrutador(interaction, str(self.membro.value))


class RecAddManualModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Adicionar Recrutamentos")
        self.cog = cog
        self.recrutador = discord.ui.TextInput(
            label="Recrutador",
            placeholder="menção, ID ou nome",
            required=True,
            max_length=100,
        )
        self.quantidade = discord.ui.TextInput(
            label="Quantidade",
            placeholder="número de 1 a 100",
            required=True,
            max_length=3,
        )
        self.recrutado = discord.ui.TextInput(
            label="Nome do recrutado",
            placeholder="opcional — nome do recrutado",
            required=False,
            max_length=100,
        )
        self.add_item(self.recrutador)
        self.add_item(self.quantidade)
        self.add_item(self.recrutado)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.cog.responder_add_manual(
            interaction,
            str(self.recrutador.value),
            str(self.quantidade.value),
            str(self.recrutado.value).strip() or None,
        )


class RecRemoveUltimoModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Remover Último Registro")
        self.cog = cog
        self.recrutador = discord.ui.TextInput(
            label="Recrutador",
            placeholder="Informe a menção, ID ou nome do recrutador.",
            required=True,
            max_length=100,
        )
        self.add_item(self.recrutador)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.cog.responder_remove_ultimo(interaction, str(self.recrutador.value))


class RecRegistrarMensagemModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Registrar Mensagem Antiga")
        self.cog = cog
        self.message_id = discord.ui.TextInput(
            label="ID da mensagem",
            placeholder="Cole o ID da mensagem antiga de +1.",
            required=True,
            max_length=30,
        )
        self.add_item(self.message_id)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.cog.responder_registrar_mensagem(interaction, str(self.message_id.value))


class RecPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @staticmethod
    async def responder_ephemeral(interaction, conteudo=None, embed=None):
        if interaction.response.is_done():
            await interaction.followup.send(content=conteudo, embed=embed, ephemeral=True)
            return
        await interaction.response.send_message(content=conteudo, embed=embed, ephemeral=True)

    async def validar_staff(self, interaction):
        if membro_eh_staff(interaction.user):
            return True

        await self.responder_ephemeral(interaction, "❌ Apenas a staff pode usar este painel.")
        return False

    async def validar_staff_gerenciar_ranking(self, interaction):
        if membro_tem_cargo_id(interaction.user, REC_MANAGE_ROLE_ID):
            return True

        await self.responder_ephemeral(
            interaction,
            "Apenas a staff pode adicionar ou remover recrutamentos neste painel.",
        )
        return False

    async def validar_ranking(self, interaction):
        if membro_eh_staff(interaction.user) or membro_eh_recrutamento(interaction.user):
            return True

        await self.responder_ephemeral(interaction, "❌ Apenas a staff e recrutadores podem ver este ranking.")
        return False

    @discord.ui.button(
        label="Ranking do Mês",
        emoji=resolver_emoji_painel_rec(REC_EMOJI_RANKING, "🏆"),
        style=discord.ButtonStyle.secondary,
        custom_id="rec_painel_ranking",
    )
    async def ranking_mes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_ranking(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.cog.responder_ranking_mes(interaction)

    @discord.ui.button(
        label="Info Recrutador",
        emoji=resolver_emoji_painel_rec(REC_EMOJI_INFO, "🔎"),
        style=discord.ButtonStyle.secondary,
        custom_id="rec_painel_info",
    )
    async def info_recrutador(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        await interaction.response.send_modal(RecInfoModal(self.cog))

    @discord.ui.button(
        label="Adicionar Manual",
        emoji=resolver_emoji_painel_rec(REC_EMOJI_ADD, "➕"),
        style=discord.ButtonStyle.secondary,
        custom_id="rec_painel_add_manual",
    )
    async def adicionar_manual(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff_gerenciar_ranking(interaction):
            return

        await interaction.response.send_modal(RecAddManualModal(self.cog))

    @discord.ui.button(
        label="Remover Último",
        emoji=resolver_emoji_painel_rec(REC_EMOJI_REMOVE, "➖"),
        style=discord.ButtonStyle.secondary,
        custom_id="rec_painel_remove_ultimo",
    )
    async def remover_ultimo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff_gerenciar_ranking(interaction):
            return

        await interaction.response.send_modal(RecRemoveUltimoModal(self.cog))

    @discord.ui.button(
        label="Atualizar Painel",
        emoji=resolver_emoji_painel_rec(REC_EMOJI_UPDATE, "🔄"),
        style=discord.ButtonStyle.secondary,
        custom_id="rec_painel_atualizar",
    )
    async def atualizar_painel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        try:
            await interaction.response.edit_message(
                embed=criar_embed_painel_rec(),
                view=RecPanelView(self.cog),
            )
            await interaction.followup.send("✅ Painel atualizado.", ephemeral=True)
        except Exception as erro:
            print(f"[REC PAINEL] Erro ao atualizar painel: {erro}")
            await self.responder_ephemeral(interaction, "❌ Não consegui atualizar o painel agora.")


class RecrutamentoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(RecPanelView(self))

    async def resolver_membro_recrutador(self, guild, texto):
        membro = procurar_membro_por_texto(guild, texto)
        if membro:
            return membro

        user_id = extrair_id_discord(texto)
        if user_id and guild:
            try:
                return await guild.fetch_member(int(user_id))
            except Exception:
                return None

        return None

    async def obter_canal_painel_rec(self, ctx):
        rec_panel_channel_id = normalizar_id_config(
            obter_valor_config(getattr(ctx, "guild", None), "REC_PANEL_CHANNEL_ID", REC_PANEL_CHANNEL_ID)
        )
        if not rec_panel_channel_id:
            return None

        canal = self.bot.get_channel(rec_panel_channel_id)
        if canal:
            return canal

        try:
            return await self.bot.fetch_channel(rec_panel_channel_id)
        except Exception:
            return None

    async def obter_ranking_mes_com_recrutadores(self, guild):
        ranking_banco = await ranking_recrutadores_mes()
        ranking_por_id = {}

        for item in ranking_banco:
            recrutador_id = str(item.get("recrutador_id") or "").strip()
            if not recrutador_id:
                continue

            membro = None
            if guild and recrutador_id.isdigit():
                membro = guild.get_member(int(recrutador_id))

            nome = item.get("recrutador_nome") or "Desconhecido"
            if membro:
                nome = membro.display_name

            ranking_por_id[recrutador_id] = {
                "recrutador_id": recrutador_id,
                "recrutador_nome": nome,
                "total": int(item.get("total") or 0),
                "mencao": membro.mention if membro else f"<@{recrutador_id}>",
            }

        for membro in listar_membros_recrutamento(guild):
            recrutador_id = str(membro.id)
            if recrutador_id not in ranking_por_id:
                ranking_por_id[recrutador_id] = {
                    "recrutador_id": recrutador_id,
                    "recrutador_nome": membro.display_name,
                    "total": 0,
                    "mencao": membro.mention,
                }
                continue

            ranking_por_id[recrutador_id]["recrutador_nome"] = membro.display_name
            ranking_por_id[recrutador_id]["mencao"] = membro.mention

        return sorted(
            ranking_por_id.values(),
            key=lambda item: (-int(item.get("total") or 0), str(item.get("recrutador_nome") or "").casefold()),
        )

    def montar_linhas_ranking(self, ranking, usar_mencao=True, limite_chars=3900):
        linhas = []
        tamanho = 0

        for i, item in enumerate(ranking, start=1):
            total = int(item.get("total") or 0)
            nome = item.get("mencao") if usar_mencao else item.get("recrutador_nome")
            nome = nome or f"<@{item.get('recrutador_id')}>"
            texto_total = "1 recrutamento" if total == 1 else f"{total} recrutamentos"
            linha = f"{i}o - {nome} - {texto_total}"

            if tamanho + len(linha) + 1 > limite_chars:
                restantes = len(ranking) - len(linhas)
                if restantes > 0:
                    linhas.append(f"... e mais {restantes} recrutadores.")
                break

            linhas.append(linha)
            tamanho += len(linha) + 1

        return linhas

    async def enviar_ou_atualizar_painel_rec(self, canal):
        embed = criar_embed_painel_rec()
        view = RecPanelView(self)

        try:
            async for mensagem in canal.history(limit=30):
                if mensagem.author.id != self.bot.user.id:
                    continue
                if not mensagem.embeds:
                    continue
                if mensagem.embeds[0].title == embed.title:
                    await mensagem.edit(embed=embed, view=view)
                    return "atualizado"
        except Exception:
            pass

        await canal.send(embed=embed, view=view)
        return "enviado"

    async def responder_ranking_mes(self, interaction):
        try:
            ranking = await self.obter_ranking_mes_com_recrutadores(interaction.guild)

            if not ranking:
                await interaction.followup.send(
                    embed=criar_embed_rec(
                        "🏆 Ranking de Recrutadores — Mês Atual",
                        "Nenhum recrutamento registrado neste mês ainda.",
                    ),
                    ephemeral=True,
                )
                return

            linhas = self.montar_linhas_ranking(ranking, usar_mencao=True)

            await interaction.followup.send(
                embed=criar_embed_rec(
                    "🏆 Ranking de Recrutadores — Mês Atual",
                    "\n".join(linhas),
                ),
                ephemeral=True,
            )
        except Exception as erro:
            print(f"[REC PAINEL] Erro ao carregar ranking: {erro}")
            await interaction.followup.send("❌ Não consegui carregar o ranking agora.", ephemeral=True)

    async def responder_info_recrutador(self, interaction, texto_membro):
        try:
            membro = await self.resolver_membro_recrutador(interaction.guild, texto_membro)
            if not membro:
                await interaction.followup.send("❌ Não consegui encontrar esse recrutador.", ephemeral=True)
                return

            recrutamentos = await buscar_recrutamentos_do_recrutador(membro.id)
            ranking = await self.obter_ranking_mes_com_recrutadores(interaction.guild)
            posicao = None
            for i, item in enumerate(ranking, start=1):
                if str(item.get("recrutador_id")) == str(membro.id):
                    posicao = i
                    break

            total_mes = len(recrutamentos)
            linhas = []
            for item in recrutamentos[:10]:
                recrutado = item.get("recrutado_texto") or "Não informado"
                data_br = formatar_data_br(item.get("data_criacao", ""))
                origem = item.get("origem", "chat")
                linhas.append(f"• {data_br} — {recrutado} — origem: `{origem}`")

            if not linhas:
                linhas.append("Nenhum recrutamento registrado neste mês.")

            descricao = (
                f"**Recrutador:** {membro.mention}\n"
                f"**Total no mês atual:** {total_mes}\n"
                f"**Posição no ranking:** {formatar_posicao(posicao)}\n\n"
                f"**Últimos recrutamentos registrados:**\n" + "\n".join(linhas)
            )
            await interaction.followup.send(
                embed=criar_embed_rec("📌 Info de Recrutamento", descricao),
                ephemeral=True,
            )
        except Exception as erro:
            print(f"[REC PAINEL] Erro ao buscar info: {erro}")
            await interaction.followup.send("❌ Não consegui carregar as informações agora.", ephemeral=True)

    async def responder_add_manual(self, interaction, texto_recrutador, texto_quantidade, recrutado_texto):
        try:
            membro = await self.resolver_membro_recrutador(interaction.guild, texto_recrutador)
            if not membro:
                await interaction.followup.send("❌ Não consegui encontrar esse recrutador.", ephemeral=True)
                return

            try:
                quantidade = int(texto_quantidade.strip())
            except ValueError:
                await interaction.followup.send("❌ A quantidade precisa ser um número de 1 a 100.", ephemeral=True)
                return

            if quantidade < 1 or quantidade > 100:
                await interaction.followup.send("❌ A quantidade precisa estar entre 1 e 100.", ephemeral=True)
                return

            adicionados = 0
            for i in range(quantidade):
                message_id_manual = f"manual-painel-{interaction.id}-{membro.id}-{i}"
                salvo = await registrar_recrutamento(
                    message_id=message_id_manual,
                    recrutador_id=membro.id,
                    recrutador_nome=str(membro),
                    canal_id=interaction.channel.id,
                    recrutado_texto=recrutado_texto,
                    origem="manual",
                )
                if salvo:
                    adicionados += 1

            total_mes = await total_recrutamentos_mes(membro.id)
            await interaction.followup.send(
                (
                    "✅ Recrutamento registrado com sucesso.\n\n"
                    "Detalhes:\n"
                    f"Recrutador: {membro.mention}\n"
                    f"Quantidade: {adicionados}\n"
                    f"Recrutado: {recrutado_texto or 'Não informado'}"
                ),
                ephemeral=True,
            )
            await enviar_log_bot(
                "➕ Recrutamentos manuais adicionados pelo painel",
                (
                    f"**Staff:** {interaction.user.mention}\n"
                    f"**Recrutador:** {membro.mention}\n"
                    f"**Quantidade:** {adicionados}\n"
                    f"**Recrutado:** {recrutado_texto or 'Não informado'}\n"
                    f"**Canal:** {interaction.channel.mention}\n"
                    f"**Total no mês:** {total_mes}"
                ),
            )
        except Exception as erro:
            print(f"[REC PAINEL] Erro ao adicionar manual: {erro}")
            await interaction.followup.send("❌ Não consegui registrar esse recrutamento agora.", ephemeral=True)

    async def responder_remove_ultimo(self, interaction, texto_recrutador):
        try:
            membro = await self.resolver_membro_recrutador(interaction.guild, texto_recrutador)
            if not membro:
                await interaction.followup.send("❌ Não consegui encontrar esse recrutador.", ephemeral=True)
                return

            removido = await remover_ultimo_recrutamento_do_recrutador(membro.id)
            if not removido:
                await interaction.followup.send("⚠️ Este recrutador não possui registros neste mês.", ephemeral=True)
                return

            total_mes = await total_recrutamentos_mes(membro.id)
            await interaction.followup.send("✅ Último recrutamento removido com sucesso.", ephemeral=True)
            await enviar_log_bot(
                "➖ Recrutamento removido pelo painel",
                (
                    f"**Staff:** {interaction.user.mention}\n"
                    f"**Recrutador:** {membro.mention}\n"
                    f"**Canal:** {interaction.channel.mention}\n"
                    f"**Total no mês agora:** {total_mes}"
                ),
            )
        except Exception as erro:
            print(f"[REC PAINEL] Erro ao remover ultimo: {erro}")
            await interaction.followup.send("❌ Não consegui remover o último recrutamento agora.", ephemeral=True)

    async def responder_registrar_mensagem(self, interaction, texto_message_id):
        try:
            message_id = texto_message_id.strip()
            if not message_id.isdigit():
                await interaction.followup.send(
                    "❌ A mensagem informada não é válida para registro de recrutamento.",
                    ephemeral=True,
                )
                return

            canal_contagem_id = normalizar_id_config(
                obter_valor_config(interaction.guild, "CANAL_CONTAGEM_ID", CANAL_CONTAGEM_ID)
            )
            mensagem_antiga = await buscar_mensagem_recrutamento_por_id(canal_contagem_id, message_id)
            if not mensagem_antiga:
                await interaction.followup.send(
                    "❌ A mensagem informada não é válida para registro de recrutamento.",
                    ephemeral=True,
                )
                return
            if mensagem_antiga.author.bot or not mensagem_eh_recrutamento(mensagem_antiga.content):
                await interaction.followup.send(
                    "❌ A mensagem informada não é válida para registro de recrutamento.",
                    ephemeral=True,
                )
                return

            recrutado_texto = extrair_recrutado_de_mensagem_antiga(interaction.guild, mensagem_antiga)
            if not recrutado_texto:
                await interaction.followup.send(
                    "❌ A mensagem informada não é válida para registro de recrutamento.",
                    ephemeral=True,
                )
                return

            message_id_manual = f"addmsg-{mensagem_antiga.id}"
            salvo = await registrar_recrutamento(
                message_id=message_id_manual,
                recrutador_id=mensagem_antiga.author.id,
                recrutador_nome=str(mensagem_antiga.author),
                canal_id=mensagem_antiga.channel.id,
                recrutado_texto=recrutado_texto,
                origem="addmsg",
            )

            if not salvo:
                await interaction.followup.send("⚠️ Esta mensagem já foi registrada anteriormente.", ephemeral=True)
                return

            total_mes = await total_recrutamentos_mes(mensagem_antiga.author.id)
            await interaction.followup.send("✅ Mensagem registrada com sucesso.", ephemeral=True)
            await enviar_log_bot(
                "➕ Recrutamento adicionado por ID de mensagem pelo painel",
                (
                    f"**Staff:** {interaction.user.mention}\n"
                    f"**Recrutador:** {mensagem_antiga.author.mention}\n"
                    f"**Recrutado:** {recrutado_texto}\n"
                    f"**Mensagem usada:** `{mensagem_antiga.id}`\n"
                    f"**Canal:** {mensagem_antiga.channel.mention}\n"
                    f"**Total no mês:** {total_mes}"
                ),
            )
        except Exception as erro:
            print(f"[REC PAINEL] Erro ao registrar mensagem antiga: {erro}")
            await interaction.followup.send(
                "❌ A mensagem informada não é válida para registro de recrutamento.",
                ephemeral=True,
            )

    @commands.command(name="rec", aliases=["recrutamento", "recrutador"])
    async def rec(self, ctx, acao=None, *args):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags(
                "❌ Sem permissão",
                "Você não tem permissão pra usar esse comando."
            ))
            return

        if acao is None:
            await ctx.send(embed=criar_embed_tags(
                "📘 Comandos de recrutamento",
                (
                    "`!rec ranking` — mostra o ranking do mês\n"
                    "`!rec info nome` — mostra os recrutamentos do membro\n"
                    "`!rec add nome 5` — adiciona recrutamentos manualmente\n"
                    "`!rec add nome 5 nome do recrutado` — adiciona com recrutado\n"
                    "`!rec addmsg ID_DA_MENSAGEM` — adiciona usando uma mensagem antiga de +1\n"
                    "`!rec remove nome` — remove o último +1 do membro\n"
                    "`!rec painel` — envia ou atualiza o painel fixo de recrutamento\n"
                    "`!rec resetmes` — reseta os recrutamentos do mês atual"
                )
            ))
            return

        acao = acao.lower()

        if acao == "painel":
            canal = await self.obter_canal_painel_rec(ctx)
            if not canal:
                await ctx.send(embed=criar_embed_tags(
                    "❌ Canal não encontrado",
                    "Não consegui encontrar o canal configurado para o painel de recrutamento."
                ))
                return

            resultado = await self.enviar_ou_atualizar_painel_rec(canal)
            await ctx.send(embed=criar_embed_tags(
                "✅ Painel de recrutamento",
                f"Painel {resultado} em {canal.mention}."
            ))
            return

        if acao == "ranking":
            ranking = await self.obter_ranking_mes_com_recrutadores(ctx.guild)

            if not ranking:
                await ctx.send(embed=criar_embed_tags(
                    "🏆 Ranking de recrutadores",
                    "Ainda não há recrutamentos registrados neste mês."
                ))
                return

            linhas = self.montar_linhas_ranking(ranking, usar_mencao=True)

            await ctx.send(embed=criar_embed_tags("🏆 Ranking de recrutadores", "\n".join(linhas)))
            return

        if acao == "info":
            if not args:
                await ctx.send(embed=criar_embed_tags("📌 Info de recrutamento", "Use assim: `!rec info nome`"))
                return

            membro = procurar_membro_por_texto(ctx.guild, " ".join(args))
            if not membro:
                await ctx.send(embed=criar_embed_tags("❌ Membro não encontrado", "Não consegui encontrar esse membro."))
                return

            recrutamentos = await buscar_recrutamentos_do_recrutador(membro.id)
            total_mes = len(recrutamentos)

            if total_mes == 0:
                await ctx.send(embed=criar_embed_tags(
                    "📌 Info de recrutamento",
                    f"{membro.mention} não tem recrutamentos registrados neste mês."
                ))
                return

            linhas = []
            for item in recrutamentos[:10]:
                recrutado = item.get("recrutado_texto") or "Não informado"
                data_br = formatar_data_br(item.get("data_criacao", ""))
                origem = item.get("origem", "chat")
                linhas.append(f"• **{recrutado}** — {data_br} — `{origem}`")

            descricao = (
                f"**Recrutador:** {membro.mention}\n"
                f"**Total no mês:** {total_mes}\n\n"
                f"**Últimos recrutamentos:**\n" + "\n".join(linhas)
            )
            await ctx.send(embed=criar_embed_tags("📌 Info de recrutamento", descricao))
            return

        if acao == "addmsg":
            if not args:
                await ctx.send(embed=criar_embed_tags("➕ Adicionar por mensagem", "Use assim: `!rec addmsg ID_DA_MENSAGEM`"))
                return

            message_id = args[0].strip()
            if not message_id.isdigit():
                await ctx.send(embed=criar_embed_tags("❌ ID inválido", "O ID da mensagem precisa ser numérico."))
                return

            canal_contagem_id = normalizar_id_config(
                obter_valor_config(ctx.guild, "CANAL_CONTAGEM_ID", CANAL_CONTAGEM_ID)
            )
            mensagem_antiga = await buscar_mensagem_recrutamento_por_id(canal_contagem_id, message_id)
            if not mensagem_antiga:
                await ctx.send(embed=criar_embed_tags("❌ Mensagem não encontrada", "Não consegui encontrar essa mensagem no canal de contagem."))
                return
            if mensagem_antiga.author.bot:
                await ctx.send(embed=criar_embed_tags("❌ Mensagem inválida", "Essa mensagem foi enviada por bot."))
                return
            if not mensagem_eh_recrutamento(mensagem_antiga.content):
                await ctx.send(embed=criar_embed_tags(
                    "❌ Formato inválido",
                    "A mensagem encontrada não está no formato de recrutamento.\nUse uma mensagem tipo `+1 nome_do_discord`."
                ))
                return

            recrutador = mensagem_antiga.author
            recrutado_texto = extrair_recrutado_de_mensagem_antiga(ctx.guild, mensagem_antiga)
            if not recrutado_texto:
                await ctx.send(embed=criar_embed_tags("❌ Recrutado inválido", "Não consegui identificar o recrutado nessa mensagem."))
                return

            message_id_manual = f"addmsg-{mensagem_antiga.id}"

            try:
                salvo = await registrar_recrutamento(
                    message_id=message_id_manual,
                    recrutador_id=recrutador.id,
                    recrutador_nome=str(recrutador),
                    canal_id=mensagem_antiga.channel.id,
                    recrutado_texto=recrutado_texto,
                    origem="addmsg"
                )

                if not salvo:
                    await ctx.send(embed=criar_embed_tags("⚠️ Já registrado", "Essa mensagem já foi usada para registrar recrutamento."))
                    return

                total_mes = await total_recrutamentos_mes(recrutador.id)
                await ctx.send(embed=criar_embed_tags(
                    "✅ Recrutamento adicionado pela mensagem",
                    (
                        f"**Recrutador:** {recrutador.mention}\n"
                        f"**Recrutado:** {recrutado_texto}\n"
                        f"**Mensagem usada:** `{mensagem_antiga.id}`\n"
                        f"**Total no mês:** {total_mes}"
                    )
                ))

                await enviar_log_bot(
                    "➕ Recrutamento adicionado por ID de mensagem",
                    (
                        f"**Staff:** {ctx.author.mention}\n"
                        f"**Recrutador:** {recrutador.mention}\n"
                        f"**Recrutado:** {recrutado_texto}\n"
                        f"**Mensagem usada:** `{mensagem_antiga.id}`\n"
                        f"**Canal:** {mensagem_antiga.channel.mention}\n"
                        f"**Total no mês:** {total_mes}"
                    )
                )
            except Exception as erro:
                await ctx.send(embed=criar_embed_tags("❌ Erro", "Não consegui adicionar esse recrutamento pela mensagem."))
                await enviar_log_bot(
                    "❌ Erro ao adicionar recrutamento por mensagem",
                    (
                        f"**Staff:** {ctx.author.mention}\n"
                        f"**Mensagem usada:** `{mensagem_antiga.id}`\n"
                        f"```{erro}```"
                    )
                )
            return

        if acao == "add":
            if len(args) < 2:
                await ctx.send(embed=criar_embed_tags(
                    "➕ Adicionar recrutamento",
                    (
                        "Use assim:\n"
                        "`!rec add @membro 5`\n"
                        "`!rec add ID 5`\n"
                        "`!rec add nome 5`\n"
                        "`!rec add @membro 5 nome do recrutado`"
                    )
                ))
                return

            membro = procurar_membro_por_texto(ctx.guild, args[0])
            if not membro:
                await ctx.send(embed=criar_embed_tags("❌ Membro não encontrado", "Não consegui encontrar esse membro."))
                return

            try:
                quantidade = int(args[1])
            except ValueError:
                await ctx.send(embed=criar_embed_tags(
                    "❌ Quantidade inválida",
                    "A quantidade precisa ser um número.\nExemplo: `!rec add @Lilly 5`"
                ))
                return

            if quantidade <= 0:
                await ctx.send(embed=criar_embed_tags("❌ Quantidade inválida", "A quantidade precisa ser maior que 0."))
                return
            if quantidade > 100:
                await ctx.send(embed=criar_embed_tags("❌ Quantidade muito alta", "Por segurança, o máximo por comando é **100**."))
                return

            recrutado_texto = None
            if len(args) > 2:
                recrutado_texto = " ".join(args[2:]).strip() or None

            adicionados = 0
            try:
                for i in range(quantidade):
                    message_id_manual = f"manual-{ctx.message.id}-{membro.id}-{i}"
                    salvo = await registrar_recrutamento(
                        message_id=message_id_manual,
                        recrutador_id=membro.id,
                        recrutador_nome=str(membro),
                        canal_id=ctx.channel.id,
                        recrutado_texto=recrutado_texto,
                        origem="manual"
                    )
                    if salvo:
                        adicionados += 1

                total_mes = await total_recrutamentos_mes(membro.id)
                descricao = (
                    f"**Recrutador:** {membro.mention}\n"
                    f"**Adicionados agora:** {adicionados}\n"
                    f"**Total no mês:** {total_mes}"
                )
                if recrutado_texto:
                    descricao += f"\n**Recrutado:** {recrutado_texto}"

                await ctx.send(embed=criar_embed_tags("✅ Recrutamentos adicionados", descricao))
                await enviar_log_bot(
                    "➕ Recrutamentos manuais adicionados",
                    (
                        f"**Staff:** {ctx.author.mention}\n"
                        f"**Recrutador:** {membro.mention}\n"
                        f"**Quantidade:** {adicionados}\n"
                        f"**Recrutado:** {recrutado_texto or 'Não informado'}\n"
                        f"**Canal:** {ctx.channel.mention}\n"
                        f"**Total no mês:** {total_mes}"
                    )
                )
            except Exception as erro:
                await ctx.send(embed=criar_embed_tags("❌ Erro", "Não consegui adicionar esses recrutamentos."))
                await enviar_log_bot(
                    "❌ Erro ao adicionar recrutamentos manuais",
                    (
                        f"**Staff:** {ctx.author.mention}\n"
                        f"**Recrutador:** {membro.mention}\n"
                        f"**Quantidade tentada:** {quantidade}\n"
                        f"```{erro}```"
                    )
                )
            return

        if acao == "remove":
            if not args:
                await ctx.send(embed=criar_embed_tags("➖ Remover recrutamento", "Use assim: `!rec remove nome`"))
                return

            membro = procurar_membro_por_texto(ctx.guild, " ".join(args))
            if not membro:
                await ctx.send(embed=criar_embed_tags("❌ Membro não encontrado", "Não consegui encontrar esse membro."))
                return

            removido = await remover_ultimo_recrutamento_do_recrutador(membro.id)
            if not removido:
                await ctx.send(embed=criar_embed_tags(
                    "📌 Remover recrutamento",
                    f"{membro.mention} não tem recrutamentos registrados neste mês."
                ))
                return

            total_mes = await total_recrutamentos_mes(membro.id)
            await ctx.send(embed=criar_embed_tags(
                "✅ Recrutamento removido",
                f"**Recrutador:** {membro.mention}\n**Total no mês agora:** {total_mes}"
            ))
            await enviar_log_bot(
                "➖ Recrutamento removido",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Recrutador:** {membro.mention}\n"
                    f"**Canal:** {ctx.channel.mention}\n"
                    f"**Total no mês agora:** {total_mes}"
                )
            )
            return

        if acao == "resetmes":
            try:
                mes_atual = mes_referencia_atual()
                ranking_antes = await ranking_recrutadores_mes(mes_atual)

                total_registros = 0
                for item in ranking_antes:
                    total_registros += int(item.get("total", 0))

                if total_registros == 0:
                    await ctx.send(embed=criar_embed_tags("📌 Reset do mês", "Não há recrutamentos registrados neste mês para resetar."))
                    return

                await resetar_recrutamentos_mes(mes_atual)
                await ctx.send(embed=criar_embed_tags(
                    "✅ Reset do mês concluído",
                    (
                        f"Os recrutamentos de **{mes_atual}** foram resetados com sucesso.\n"
                        f"**Registros removidos:** {total_registros}"
                    )
                ))
                await enviar_log_bot(
                    "🗑️ Reset de recrutamentos do mês",
                    (
                        f"**Staff:** {ctx.author.mention}\n"
                        f"**Mês:** {mes_atual}\n"
                        f"**Registros removidos:** {total_registros}\n"
                        f"**Canal:** {ctx.channel.mention}"
                    )
                )
            except Exception as erro:
                await ctx.send(embed=criar_embed_tags("❌ Erro no reset", "Não consegui resetar os recrutamentos deste mês."))
                await enviar_log_bot(
                    "❌ Erro ao resetar recrutamentos do mês",
                    (
                        f"**Staff:** {ctx.author.mention}\n"
                        f"**Canal:** {ctx.channel.mention}\n"
                        f"```{erro}```"
                    )
                )
            return

        await ctx.send(embed=criar_embed_tags(
            "❌ Ação inválida",
            "Use `!rec ranking`, `!rec info nome`, `!rec add nome`, `!rec add nome recrutado`, `!rec remove nome` ou `!rec resetmes`."
        ))


async def setup(bot):
    await bot.add_cog(RecrutamentoCog(bot))
