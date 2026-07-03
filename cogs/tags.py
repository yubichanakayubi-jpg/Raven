import re
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config import (
    CARGO_RECRUTAMENTO_ID,
    TAG_PANEL_CHANNEL_ID,
    TAG_PANEL_EMOJI_DONE,
    TAG_PANEL_EMOJI_LATE,
    TAG_PANEL_EMOJI_PENDING,
    TAG_PANEL_EMOJI_SEARCH,
    TAG_PANEL_EMOJI_TITLE,
    TAG_PANEL_EMOJI_UPDATE,
)
from services.d1 import (
    buscar_registro_tag_por_usuario,
    carregar_dados_tags,
    concluir_tag_pendente,
    listar_tags_concluidas,
    registrar_ou_atualizar_tag_pendente,
    registrar_ou_atualizar_tag_pendente_com_data,
)
from services.logs import enviar_log_bot
from services.tags import (
    formatar_membro_objeto_tag,
    formatar_membro_registro_tag,
    formatar_link_mensagem,
    obter_link_print_original,
    obter_prazo_troca_iso,
    resolver_pendente_tag,
)
from utils.discord_helpers import criar_embed_tags, membro_eh_staff, procurar_membro_por_texto
from utils.time_utils import data_iso_manual, dias_passados_desde, formatar_data_br, parse_iso_datetime


TAG_PANEL_COLOR = discord.Color.from_rgb(0, 255, 255)
TAG_PANEL_TITLE_TEXT = "Painel de Tags — FDN"
TAG_PANEL_FOOTER = "FDN • Controle de Tags"
TAG_PANEL_DESCRIPTION = (
    "Use este painel para acompanhar as pendências de timetag e confirmações de tag.\n\n"
    "O sistema principal continua funcionando por reação:\n"
    "No canal de timetag, a staff reage com ✅ para registrar uma pendência.\n"
    "No canal de tags, a staff reage com ✅ para concluir uma pendência.\n\n"
    "Status disponíveis:\n"
    "Pendente — membro aguardando o prazo de 7 dias.\n"
    "Concluído — membro já realizou a troca de tag.\n"
    "Atrasado — membro passou do prazo e ainda não concluiu.\n"
    "Verificado — print de tag validado sem pendência ativa."
)


def resolver_emoji_painel_tags(emoji_config, fallback):
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


def resolver_emoji_texto_painel_tags(emoji_config, fallback):
    emoji = resolver_emoji_painel_tags(emoji_config, fallback)
    emoji_texto = str(emoji).strip()
    return emoji_texto or fallback


def membro_eh_recrutamento(membro):
    if not hasattr(membro, "roles"):
        return False

    for cargo in membro.roles:
        if cargo.id == CARGO_RECRUTAMENTO_ID:
            return True

    return False


def criar_embed_painel_tags():
    embed = discord.Embed(
        title=f"{resolver_emoji_texto_painel_tags(TAG_PANEL_EMOJI_TITLE, '🌙')} {TAG_PANEL_TITLE_TEXT}",
        description=TAG_PANEL_DESCRIPTION,
        color=TAG_PANEL_COLOR,
    )
    embed.set_footer(text=TAG_PANEL_FOOTER)
    return embed


def criar_embed_painel_resultado(titulo, descricao, linhas=None, mensagem_vazia=None):
    corpo = descricao
    if linhas:
        linhas_visiveis = linhas[:10]
        corpo += "\n\n" + "\n".join(linhas_visiveis)
        if len(linhas) > 10:
            corpo += "\n\nMostrando os 10 primeiros resultados."
    elif mensagem_vazia:
        corpo += "\n\n" + mensagem_vazia

    embed = discord.Embed(title=titulo, description=corpo, color=TAG_PANEL_COLOR)
    embed.set_footer(text=TAG_PANEL_FOOTER)
    return embed


def extrair_id_membro(texto):
    match = re.search(r"\d{15,25}", texto or "")
    if not match:
        return None
    return match.group(0)


def formatar_mencao_staff(staff_id, staff_nome=""):
    if staff_id:
        return f"<@{staff_id}>"
    return staff_nome or "Não informado"


def calcular_dias_atraso(registro):
    prazo = parse_iso_datetime(obter_prazo_troca_iso(registro))
    if not prazo:
        return 0

    agora = datetime.now(timezone.utc)
    if prazo.tzinfo is None:
        prazo = prazo.replace(tzinfo=timezone.utc)

    delta = agora - prazo.astimezone(timezone.utc)
    return max(delta.days, 0)


def registro_esta_atrasado(registro):
    prazo = parse_iso_datetime(obter_prazo_troca_iso(registro))
    if not prazo:
        return False

    if prazo.tzinfo is None:
        prazo = prazo.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) > prazo.astimezone(timezone.utc)


class TagSearchModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Buscar Membro")
        self.cog = cog
        self.busca = discord.ui.TextInput(
            label="ID ou menção do membro",
            placeholder="Exemplo: @usuário ou 123456789",
            required=True,
            max_length=100,
        )
        self.add_item(self.busca)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            embed = await self.cog.criar_embed_status_membro(interaction.guild, str(self.busca.value))
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as erro:
            print(f"[TAG PAINEL] Erro ao buscar membro: {erro}")
            await interaction.followup.send("❌ Não consegui buscar esse membro agora.", ephemeral=True)


class TagRemoveModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Remover da Lista")
        self.cog = cog
        self.alvo = discord.ui.TextInput(
            label="Nome ou ID do membro",
            placeholder="Exemplo: nome do membro ou 123456789",
            required=True,
            max_length=100,
        )
        self.add_item(self.alvo)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            resultado = await self.cog.remover_pendente_sem_concluir(
                interaction.guild,
                str(self.alvo.value),
                autor=interaction.user,
                canal=interaction.channel,
            )
            status = resultado.get("status")
            alvo = resultado.get("alvo")

            if status == "nao_encontrado":
                await interaction.followup.send("❌ Não consegui encontrar esse membro.", ephemeral=True)
                return

            if status == "removido":
                await interaction.followup.send(
                    f'{alvo["mention"]} foi removido da lista de pendentes sem concluir a tag.',
                    ephemeral=True,
                )
                return

            await interaction.followup.send(
                f'{alvo["mention"]} não estava na lista de pendentes.',
                ephemeral=True,
            )
        except Exception as erro:
            print(f"[TAG PAINEL] Erro ao remover membro da lista: {erro}")
            await interaction.followup.send("❌ Não consegui remover esse membro agora.", ephemeral=True)


class TagPanelView(discord.ui.View):
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

        await self.responder_ephemeral(
            interaction,
            "❌ Apenas a staff pode usar este painel.",
        )
        return False

    async def validar_staff_ou_recrutamento(self, interaction):
        if membro_eh_staff(interaction.user) or membro_eh_recrutamento(interaction.user):
            return True

        await self.responder_ephemeral(
            interaction,
            "❌ Apenas a staff e recrutadores podem usar esta consulta.",
        )
        return False

    @discord.ui.button(
        label="Ver Pendentes",
        emoji=resolver_emoji_painel_tags(TAG_PANEL_EMOJI_PENDING, "📋"),
        style=discord.ButtonStyle.secondary,
        custom_id="tag_painel_pendentes",
    )
    async def ver_pendentes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff_ou_recrutamento(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            embed = await self.cog.criar_embed_pendentes(interaction.guild)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as erro:
            print(f"[TAG PAINEL] Erro ao listar pendentes: {erro}")
            await interaction.followup.send("❌ Não consegui carregar os pendentes agora.", ephemeral=True)

    @discord.ui.button(
        label="Ver Atrasados",
        emoji=resolver_emoji_painel_tags(TAG_PANEL_EMOJI_LATE, "⏰"),
        style=discord.ButtonStyle.secondary,
        custom_id="tag_painel_atrasados",
    )
    async def ver_atrasados(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff_ou_recrutamento(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            embed = await self.cog.criar_embed_atrasados(interaction.guild)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as erro:
            print(f"[TAG PAINEL] Erro ao listar atrasados: {erro}")
            await interaction.followup.send("❌ Não consegui carregar os atrasados agora.", ephemeral=True)

    @discord.ui.button(
        label="Ver Concluídos",
        emoji=resolver_emoji_painel_tags(TAG_PANEL_EMOJI_DONE, "✅"),
        style=discord.ButtonStyle.secondary,
        custom_id="tag_painel_concluidos",
    )
    async def ver_concluidos(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff_ou_recrutamento(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            embed = await self.cog.criar_embed_concluidos(interaction.guild)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as erro:
            print(f"[TAG PAINEL] Erro ao listar concluidos: {erro}")
            await interaction.followup.send("❌ Não consegui carregar os concluídos agora.", ephemeral=True)

    @discord.ui.button(
        label="Buscar Membro",
        emoji=resolver_emoji_painel_tags(TAG_PANEL_EMOJI_SEARCH, "🔎"),
        style=discord.ButtonStyle.secondary,
        custom_id="tag_painel_buscar",
    )
    async def buscar_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        try:
            await interaction.response.send_modal(TagSearchModal(self.cog))
        except Exception as erro:
            print(f"[TAG PAINEL] Erro ao abrir modal de busca: {erro}")
            await self.responder_ephemeral(interaction, "❌ Não consegui abrir a busca agora.")

    @discord.ui.button(
        label="Remover da Lista",
        emoji="➖",
        style=discord.ButtonStyle.secondary,
        custom_id="tag_painel_remover",
    )
    async def remover_da_lista(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        try:
            await interaction.response.send_modal(TagRemoveModal(self.cog))
        except Exception as erro:
            print(f"[TAG PAINEL] Erro ao abrir modal de remoção: {erro}")
            await self.responder_ephemeral(interaction, "❌ Não consegui abrir a remoção agora.")

    @discord.ui.button(
        label="Atualizar Painel",
        emoji=resolver_emoji_painel_tags(TAG_PANEL_EMOJI_UPDATE, "🔄"),
        style=discord.ButtonStyle.secondary,
        custom_id="tag_painel_atualizar",
    )
    async def atualizar_painel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        try:
            await interaction.response.edit_message(
                embed=criar_embed_painel_tags(),
                view=TagPanelView(self.cog),
            )
        except Exception as erro:
            print(f"[TAG PAINEL] Erro ao atualizar painel: {erro}")
            await self.responder_ephemeral(interaction, "❌ Não consegui atualizar o painel agora.")


class TagsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TagPanelView(self))

    async def obter_canal_painel_tags(self, ctx):
        if TAG_PANEL_CHANNEL_ID == 0:
            return ctx.channel

        canal = self.bot.get_channel(TAG_PANEL_CHANNEL_ID)
        if canal:
            return canal

        try:
            return await self.bot.fetch_channel(TAG_PANEL_CHANNEL_ID)
        except Exception:
            return None

    async def enviar_ou_atualizar_painel_tags(self, canal):
        embed = criar_embed_painel_tags()
        view = TagPanelView(self)

        try:
            async for mensagem in canal.history(limit=30):
                if mensagem.author.id != self.bot.user.id:
                    continue
                if not mensagem.embeds:
                    continue
                if mensagem.embeds[0].title == embed.title:
                    await mensagem.edit(embed=embed, view=view)
                    return mensagem, "atualizado"
        except Exception:
            pass

        mensagem = await canal.send(embed=embed, view=view)
        return mensagem, "enviado"

    async def criar_embed_pendentes(self, guild=None):
        dados = await carregar_dados_tags()
        pendentes = [
            registro
            for registro in dados.get("pendentes", {}).values()
            if not registro_esta_atrasado(registro)
        ]
        pendentes.sort(key=lambda registro: registro.get("data_envio", ""))

        linhas = []
        guild = guild or (self.bot.guilds[0] if self.bot.guilds else None)
        for registro in pendentes:
            membro_texto = await formatar_membro_registro_tag(guild, registro)
            linhas.append(
                f"{membro_texto} - registrado em {formatar_data_br(registro.get('data_envio', ''))} "
                f"- prazo em {formatar_data_br(obter_prazo_troca_iso(registro))}"
            )

        return criar_embed_painel_resultado(
            "☾ Pendências de Tag",
            "Lista de membros aguardando a troca de tag.",
            linhas,
            "Nenhuma pendência ativa no momento.",
        )

    async def criar_embed_atrasados(self, guild=None):
        dados = await carregar_dados_tags()
        pendentes = list(dados.get("pendentes", {}).values())
        atrasados = [registro for registro in pendentes if registro_esta_atrasado(registro)]
        atrasados.sort(key=calcular_dias_atraso, reverse=True)

        linhas = []
        guild = guild or (self.bot.guilds[0] if self.bot.guilds else None)
        for registro in atrasados:
            dias_atraso = calcular_dias_atraso(registro)
            membro_texto = await formatar_membro_registro_tag(guild, registro)
            linhas.append(
                f"{membro_texto} - prazo atingido em "
                f"{formatar_data_br(obter_prazo_troca_iso(registro))} - atrasado ha {dias_atraso} dias"
            )

        return criar_embed_painel_resultado(
            "☾ Tags Atrasadas",
            "Membros que passaram do prazo de 7 dias e ainda não concluíram.",
            linhas,
            "Nenhuma tag atrasada no momento.",
        )

    async def criar_embed_concluidos(self, guild=None):
        concluidos = await listar_tags_concluidas(10)

        linhas = []
        guild = guild or (self.bot.guilds[0] if self.bot.guilds else None)
        for registro in concluidos:
            membro_texto = await formatar_membro_registro_tag(guild, registro)
            linhas.append(
                f"{membro_texto} - concluido em "
                f"{formatar_data_br(registro.get('data_conclusao', ''))} - concluido por "
                f"{formatar_mencao_staff(registro.get('staff_conclusao_id'), registro.get('staff_conclusao_nome', ''))}"
            )

        return criar_embed_painel_resultado(
            "☾ Tags Concluídas",
            "Últimos membros que concluíram a troca de tag.",
            linhas,
            "Nenhuma conclusão registrada ainda.",
        )

    async def resolver_busca_membro(self, guild, texto):
        membro = procurar_membro_por_texto(guild, texto)
        if membro:
            return membro, str(membro.id)

        user_id = extrair_id_membro(texto)
        if user_id and guild:
            try:
                membro = await guild.fetch_member(int(user_id))
            except Exception:
                membro = None

        return membro, user_id

    async def criar_embed_status_membro(self, guild, texto):
        membro, user_id = await self.resolver_busca_membro(guild, texto)
        registro = None

        if user_id:
            registro = await buscar_registro_tag_por_usuario(user_id)

        if not registro and membro:
            registro = await buscar_registro_tag_por_usuario(membro.id)

        mencao_membro = formatar_membro_objeto_tag(membro) if membro else (f"<@{user_id}>" if user_id else "Não encontrado")
        status = "Não encontrado"

        if registro:
            status_registro = str(registro.get("status", "")).lower()
            if status_registro == "pendente":
                status = "Atrasado" if registro_esta_atrasado(registro) else "Pendente"
            elif status_registro == "concluido":
                status = "Concluído"
            elif status_registro == "verificado":
                status = "Verificado"

            mencao_membro = await formatar_membro_registro_tag(guild, registro)

        embed = discord.Embed(title="☾ Status de Tag", color=TAG_PANEL_COLOR)
        embed.add_field(name="Membro", value=mencao_membro, inline=False)
        embed.add_field(name="Status", value=status, inline=False)

        if registro:
            embed.add_field(name="Registrado em", value=formatar_data_br(registro.get("data_envio", "")), inline=False)
            embed.add_field(name="Prazo", value=formatar_data_br(obter_prazo_troca_iso(registro)), inline=False)

            if registro.get("data_conclusao"):
                embed.add_field(
                    name="Concluído em",
                    value=formatar_data_br(registro.get("data_conclusao", "")),
                    inline=False,
                )

            if registro.get("staff_registro_id") or registro.get("staff_registro_nome"):
                embed.add_field(
                    name="Registrado por",
                    value=formatar_mencao_staff(
                        registro.get("staff_registro_id"),
                        registro.get("staff_registro_nome", ""),
                    ),
                    inline=False,
                )

            if registro.get("staff_conclusao_id") or registro.get("staff_conclusao_nome"):
                embed.add_field(
                    name="Concluído por",
                    value=formatar_mencao_staff(
                        registro.get("staff_conclusao_id"),
                        registro.get("staff_conclusao_nome", ""),
                    ),
                    inline=False,
                )

            print_original = obter_link_print_original(registro, getattr(guild, "id", None))
            if print_original:
                embed.add_field(
                    name="Print original",
                    value=formatar_link_mensagem(print_original),
                    inline=False,
                )

            if registro.get("conclusao_message_link"):
                embed.add_field(
                    name="Print da tag",
                    value=formatar_link_mensagem(registro.get("conclusao_message_link")),
                    inline=False,
                )

        embed.set_footer(text=TAG_PANEL_FOOTER)
        return embed

    async def remover_pendente_sem_concluir(self, guild, texto, autor=None, canal=None):
        alvo = await resolver_pendente_tag(guild, texto)
        if not alvo:
            return {"status": "nao_encontrado", "alvo": None}

        if await concluir_tag_pendente(alvo["user_id"]):
            if autor:
                canal_texto = getattr(canal, "mention", None) or "Não informado"
                await enviar_log_bot(
                    "🗑️ Tag removida da lista de pendentes",
                    (
                        f"**Staff:** {autor.mention}\n"
                        f'**Membro:** {alvo["mention"]}\n'
                        f"**Canal:** {canal_texto}\n"
                        f"**Status:** removido sem conclusão"
                    )
                )

            return {"status": "removido", "alvo": alvo}

        return {"status": "nao_pendente", "alvo": alvo}

    @commands.command(name="tagpainel")
    async def tagpainel(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send("Você não tem permissão pra usar esse comando.")
            return

        canal = await self.obter_canal_painel_tags(ctx)
        if not canal:
            await ctx.send("Não consegui encontrar o canal configurado para o painel de tags.", delete_after=10)
            return

        mensagem, acao = await self.enviar_ou_atualizar_painel_tags(canal)
        _ = mensagem

        await ctx.send(
            f"✅ Painel de tags {acao} em {canal.mention}.",
            delete_after=10,
        )

    @commands.command(name="tag", aliases=["tags"])
    async def tag(self, ctx, acao=None, *args):
        if not membro_eh_staff(ctx.author):
            await ctx.send("Você não tem permissão pra usar esse comando.")
            return

        if acao is None:
            await ctx.send(
                "**Comandos de tag:**\n"
                "`!tag lista` — mostra quem está pendente\n"
                "`!tag atrasados` — mostra quem está com 7+ dias\n"
                "`!tag atrasados 10` — mostra quem está com 10+ dias\n"
                "`!tag info nome` — mostra detalhes de um membro\n"
                "`!tag concluir nome` — remove da lista\n"
                "`!tag remover nome ou ID` — remove da lista sem concluir\n"
                "`!tag adicionar nome` — adiciona manualmente\n"
                "`!tag adicionar nome DD/MM/AAAA` — adiciona com data manual"
            )
            return

        acao = acao.lower()

        if acao == "lista":
            dados = await carregar_dados_tags()
            pendentes = list(dados["pendentes"].values())

            if not pendentes:
                await ctx.send(embed=criar_embed_tags(
                    "📋 Pendentes de tags",
                    "Não tem ninguém pendente no time tags no momento."
                ))
                return

            pendentes.sort(key=lambda x: x.get("data_envio", ""))

            linhas = []
            for registro in pendentes:
                dias = dias_passados_desde(registro.get("data_envio", ""))
                data_br = formatar_data_br(registro.get("data_envio", ""))
                membro_texto = await formatar_membro_registro_tag(ctx.guild, registro)
                linhas.append(f"{membro_texto} - **{dias} dias** - enviado em {data_br}")

            partes = [linhas[i:i + 15] for i in range(0, len(linhas), 15)]
            total = len(partes)

            for i, parte in enumerate(partes, start=1):
                titulo = "📋 Pendentes do time tags"
                if total > 1:
                    titulo += f" ({i}/{total})"

                await ctx.send(embed=criar_embed_tags(titulo=titulo, descricao="\n".join(parte)))

            return

        if acao == "concluir":
            if not args:
                await ctx.send("Use assim: `!tag concluir nome`")
                return

            alvo = await resolver_pendente_tag(ctx.guild, " ".join(args))
            if not alvo:
                await ctx.send("Não consegui encontrar esse membro.")
                return

            if await concluir_tag_pendente(alvo["user_id"]):
                await ctx.send(f'{alvo["mention"]} foi removido da lista de pendentes da tag.')
                await enviar_log_bot(
                    "✅ Tag concluída manualmente",
                    (
                        f"**Staff:** {ctx.author.mention}\n"
                        f'**Membro:** {alvo["mention"]}\n'
                        f"**Canal:** {ctx.channel.mention}"
                    )
                )
            else:
                await ctx.send(f'{alvo["mention"]} não estava na lista de pendentes.')
            return

        if acao == "remover":
            if not args:
                await ctx.send("Use assim: `!tag remover nome` ou `!tag remover ID`")
                return

            resultado = await self.remover_pendente_sem_concluir(
                ctx.guild,
                " ".join(args),
                autor=ctx.author,
                canal=ctx.channel,
            )
            status = resultado.get("status")
            alvo = resultado.get("alvo")

            if status == "nao_encontrado":
                await ctx.send("Não consegui encontrar esse membro.")
                return

            if status == "removido":
                await ctx.send(f'{alvo["mention"]} foi removido da lista de pendentes sem concluir a tag.')
            else:
                await ctx.send(f'{alvo["mention"]} não estava na lista de pendentes.')
            return

        if acao == "adicionar":
            if not args:
                await ctx.send("Use assim: `!tag adicionar nome` ou `!tag adicionar nome DD/MM/AAAA`")
                return

            data_manual = None
            nome_membro = " ".join(args)

            if args:
                ultima_parte = args[-1]
                data_teste = data_iso_manual(ultima_parte)
                if data_teste:
                    data_manual = ultima_parte
                    nome_membro = " ".join(args[:-1]).strip()

            if not nome_membro:
                await ctx.send("Use assim: `!tag adicionar nome` ou `!tag adicionar nome DD/MM/AAAA`")
                return

            membro = procurar_membro_por_texto(ctx.guild, nome_membro)
            if not membro:
                await ctx.send("Não consegui encontrar esse membro.")
                return

            if data_manual:
                data_iso = data_iso_manual(data_manual)
                if not data_iso:
                    await ctx.send("Data inválida. Use assim: `!tag adicionar nome DD/MM/AAAA`")
                    return

                await registrar_ou_atualizar_tag_pendente_com_data(membro.id, str(membro), data_iso, None)
                membro_texto = formatar_membro_objeto_tag(membro)
                await ctx.send(f"{membro_texto} foi adicionado à lista de pendentes da tag com a data {data_manual}.")
                await enviar_log_bot(
                    "➕ Tag adicionada manualmente",
                    (
                        f"**Staff:** {ctx.author.mention}\n"
                        f"**Membro:** {membro_texto}\n"
                        f"**Data manual:** {data_manual}\n"
                        f"**Canal:** {ctx.channel.mention}"
                    )
                )
                return

            await registrar_ou_atualizar_tag_pendente(membro.id, str(membro), None)
            membro_texto = formatar_membro_objeto_tag(membro)
            await ctx.send(f"{membro_texto} foi adicionado à lista de pendentes da tag.")
            await enviar_log_bot(
                "➕ Tag adicionada manualmente",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Membro:** {membro_texto}\n"
                    f"**Canal:** {ctx.channel.mention}"
                )
            )
            return

        if acao == "atrasados":
            dados = await carregar_dados_tags()
            pendentes = list(dados["pendentes"].values())

            dias_minimos = 7
            if args:
                try:
                    dias_minimos = int(args[0])
                except ValueError:
                    await ctx.send("Use assim: `!tag atrasados` ou `!tag atrasados 10`")
                    return

            atrasados = []
            for registro in pendentes:
                dias = dias_passados_desde(registro.get("data_envio", ""))
                if dias >= dias_minimos:
                    atrasados.append((registro, dias))

            if not atrasados:
                await ctx.send(embed=criar_embed_tags(
                    "📋 Tags atrasadas",
                    f"Ninguém está com **{dias_minimos}+ dias** de atraso no momento."
                ))
                return

            atrasados.sort(key=lambda item: item[1], reverse=True)

            linhas = []
            for registro, dias in atrasados:
                data_br = formatar_data_br(registro.get("data_envio", ""))
                membro_texto = await formatar_membro_registro_tag(ctx.guild, registro)
                linhas.append(f"{membro_texto} - **{dias} dias** - enviado em {data_br}")

            partes = [linhas[i:i + 15] for i in range(0, len(linhas), 15)]
            total = len(partes)

            for i, parte in enumerate(partes, start=1):
                titulo = f"⚠️ Tags com {dias_minimos}+ dias"
                if total > 1:
                    titulo += f" ({i}/{total})"

                await ctx.send(embed=criar_embed_tags(titulo, "\n".join(parte)))

            return

        if acao == "info":
            if not args:
                await ctx.send("Use assim: `!tag info nome`")
                return

            membro = procurar_membro_por_texto(ctx.guild, " ".join(args))
            if not membro:
                await ctx.send("Não consegui encontrar esse membro.")
                return

            dados = await carregar_dados_tags()
            registro = dados["pendentes"].get(str(membro.id))
            membro_texto = formatar_membro_objeto_tag(membro)

            if not registro:
                await ctx.send(embed=criar_embed_tags(
                    "📌 Info da tag",
                    f"{membro_texto} não está na lista de pendentes."
                ))
                return

            dias = dias_passados_desde(registro.get("data_envio", ""))
            data_br = formatar_data_br(registro.get("data_envio", ""))
            avisou_7 = "Sim" if registro.get("avisou_7_dias", False) else "Não"
            avisou_10 = "Sim" if registro.get("avisou_10_dias", False) else "Não"
            message_id = registro.get("message_id") or "Não salvo"
            _ = message_id

            descricao = (
                f"**Membro:** {membro_texto}\n"
                f"**Desde:** {data_br}\n"
                f"**Tempo pendente:** {dias} dias\n"
                f"**Aviso de 7 dias:** {avisou_7}\n"
                f"**Aviso de 10 dias:** {avisou_10}"
            )

            await ctx.send(embed=criar_embed_tags("📌 Info da tag", descricao))
            return

        await ctx.send(
            "Ação inválida.\n"
            "Use `!tag lista`, `!tag atrasados [dias]`, `!tag info nome`, "
            "`!tag concluir nome`, `!tag remover nome/ID` ou `!tag adicionar nome [DD/MM/AAAA]`."
        )


async def setup(bot):
    await bot.add_cog(TagsCog(bot))
