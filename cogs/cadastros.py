from datetime import datetime

import discord
from discord.ext import commands

from config import (
    CADASTRO_CHANNEL_ID,
    CADASTRO_LOG_CHANNEL_ID,
    CADASTRO_OLD_CHANNEL_ID,
    CADASTRO_PANEL_EMOJI_APPROVED,
    CADASTRO_PANEL_EMOJI_IMPORTED,
    CADASTRO_PANEL_EMOJI_REJECTED,
    CADASTRO_PANEL_EMOJI_TITLE,
    CADASTRO_PANEL_EMOJI_UPDATE,
    CADASTRO_PANEL_CHANNEL_ID,
    EMOJI_APROVAR_TAG,
)
from services.cadastros import (
    NAO_IDENTIFICADO,
    carregar_dados_cadastros,
    extrair_ficha_recrutamento,
    normalizar_chave,
    salvar_cadastro_importado,
    salvar_ficha_recrutamento,
)
from services.logs import enviar_log_bot
from utils.discord_helpers import membro_eh_staff


CADASTRO_COLOR = discord.Color.from_rgb(0, 255, 255)
CADASTRO_FOOTER = "FDN • Cadastros"
CADASTRO_PANEL_TITLE_TEXT = "Painel de Cadastros — FDN"
CADASTRO_PANEL_DESCRIPTION = (
    "Use este painel para consultar fichas de recrutamento salvas no sistema.\n\n"
    "Por aqui, a staff pode buscar membros, ver os últimos cadastros e acompanhar fichas "
    "aprovadas, reprovadas ou importadas."
)


def resolver_emoji_painel_cadastro(emoji_config, fallback):
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


def resolver_emoji_texto_painel_cadastro(emoji_config, fallback):
    emoji = resolver_emoji_painel_cadastro(emoji_config, fallback)
    emoji_texto = str(emoji).strip()
    return emoji_texto or fallback


def criar_embed_painel_cadastros():
    embed = discord.Embed(
        title=f"{resolver_emoji_texto_painel_cadastro(CADASTRO_PANEL_EMOJI_TITLE, '☾')} {CADASTRO_PANEL_TITLE_TEXT}",
        description=CADASTRO_PANEL_DESCRIPTION,
        color=CADASTRO_COLOR,
    )
    embed.set_footer(text=CADASTRO_FOOTER)
    return embed


def criar_embed_resultado_cadastros(titulo, linhas, vazio, descricao=None):
    embed = discord.Embed(
        title=titulo,
        description=descricao or ("\n".join(linhas[:10]) if linhas else vazio),
        color=CADASTRO_COLOR,
    )
    embed.set_footer(text=CADASTRO_FOOTER)
    return embed


def valor_registro(registro, *chaves, default=NAO_IDENTIFICADO):
    campos = registro.get("campos", {})

    for chave in chaves:
        valor = registro.get(chave)
        if valor not in {None, ""}:
            return str(valor)

        valor = campos.get(chave)
        if valor not in {None, ""}:
            return str(valor)

    return default


def parse_data_iso(valor):
    if not valor:
        return None

    try:
        return datetime.fromisoformat(str(valor))
    except ValueError:
        return None


def formatar_data_cadastro(valor, incluir_hora=True):
    data = parse_data_iso(valor)
    if not data:
        return "Data não informada"

    return data.strftime("%d/%m/%Y %H:%M" if incluir_hora else "%d/%m/%Y")


def valor_ordenacao_data(valor):
    data = parse_data_iso(valor)
    if not data:
        return float("-inf")

    return data.timestamp()


def obter_nome_registro(registro):
    return valor_registro(
        registro,
        "member_name",
        "nick_discord",
        "nome_atual_roblox",
        "username_roblox",
        "autor_nome",
    )


def obter_membro_referencia(registro):
    member_id = valor_registro(registro, "member_id", "autor_id", default="")
    if member_id.isdigit():
        return f"<@{member_id}>"

    return obter_nome_registro(registro)


def obter_link_ficha(registro):
    return valor_registro(
        registro,
        "cadastro_message_link",
        "message_link",
        default="",
    )


def obter_info_status(registro):
    status = valor_registro(registro, "status", default="desconhecido").casefold()

    if status == "aprovado":
        return (
            "Aprovado",
            "Aprovado por",
            valor_registro(registro, "aprovado_por_nome", "staff_validacao_nome"),
            "Data da aprovação",
            valor_registro(registro, "aprovado_em", "data_validacao", "updated_at", "created_at", default=""),
        )

    if status == "reprovado":
        return (
            "Reprovado",
            "Reprovado por",
            valor_registro(registro, "reprovado_por_nome"),
            "Data da reprovação",
            valor_registro(registro, "reprovado_em", "updated_at", "created_at", default=""),
        )

    if status == "importado":
        return (
            "Importado",
            "Importado por",
            valor_registro(registro, "importado_por_nome"),
            "Data da importação",
            valor_registro(registro, "data_importacao", "updated_at", "created_at", default=""),
        )

    return (
        status.title(),
        "Registrado por",
        valor_registro(registro, "staff_validacao_nome", "aprovado_por_nome", "importado_por_nome", default="Não informado"),
        "Data",
        valor_registro(registro, "updated_at", "created_at", "data_validacao", default=""),
    )


def obter_data_ordenacao_status(registro, status):
    if status == "aprovado":
        valor = valor_registro(registro, "aprovado_em", "data_validacao", "updated_at", "created_at", default="")
    elif status == "reprovado":
        valor = valor_registro(registro, "reprovado_em", "updated_at", "created_at", default="")
    else:
        valor = valor_registro(registro, "data_importacao", "updated_at", "created_at", default="")

    return valor_ordenacao_data(valor)


def montar_linha_lista_status(registro, status):
    nome = obter_nome_registro(registro)
    link = obter_link_ficha(registro)

    if status == "aprovado":
        data = formatar_data_cadastro(valor_registro(registro, "aprovado_em", "data_validacao", default=""))
        staff = valor_registro(registro, "aprovado_por_nome", "staff_validacao_nome")
        detalhe = f"Aprovado por {staff}"
    elif status == "reprovado":
        data = formatar_data_cadastro(valor_registro(registro, "reprovado_em", default=""))
        staff = valor_registro(registro, "reprovado_por_nome")
        detalhe = f"Reprovado por {staff}"
    else:
        data = formatar_data_cadastro(valor_registro(registro, "data_importacao", default=""))
        staff = valor_registro(registro, "importado_por_nome")
        detalhe = f"Importado por {staff}"

    link_texto = f"[Abrir ficha]({link})" if link else "Sem link da ficha"
    return f"**{nome}** — {data} — {detalhe} — {link_texto}"


class CadastroSearchModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Buscar Cadastro")
        self.cog = cog
        self.termo = discord.ui.TextInput(
            label="Nome, nick, username Roblox ou ID",
            placeholder="Exemplo: Akayubi, FDNxAkayubi, username Roblox ou ID",
            required=True,
            max_length=100,
        )
        self.add_item(self.termo)

    async def on_submit(self, interaction: discord.Interaction):
        if not membro_eh_staff(interaction.user):
            await CadastroPanelView.responder_ephemeral(
                interaction,
                "❌ Apenas a staff pode usar este painel.",
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            embed = self.cog.criar_embed_consulta_cadastro(str(self.termo.value))
        except LookupError:
            await interaction.followup.send(
                "❌ Nenhum cadastro encontrado com esse termo.",
                ephemeral=True,
            )
            return
        except Exception as erro:
            print(f"[CADASTRO PAINEL] Erro ao buscar cadastro: {erro}")
            await interaction.followup.send(
                "❌ Não consegui buscar esse cadastro agora.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(embed=embed, ephemeral=True)


class CadastroPanelView(discord.ui.View):
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

    @discord.ui.button(
        label="Buscar Membro",
        emoji="🔎",
        style=discord.ButtonStyle.secondary,
        custom_id="cadastro_painel_buscar",
    )
    async def buscar_membro(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        try:
            await interaction.response.send_modal(CadastroSearchModal(self.cog))
        except Exception as erro:
            print(f"[CADASTRO PAINEL] Erro ao abrir modal de busca: {erro}")
            await self.responder_ephemeral(interaction, "❌ Não consegui abrir a busca agora.")

    @discord.ui.button(
        label="Aprovados",
        emoji=resolver_emoji_painel_cadastro(CADASTRO_PANEL_EMOJI_APPROVED, "✅"),
        style=discord.ButtonStyle.secondary,
        custom_id="cadastro_painel_aprovados",
    )
    async def aprovados(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            embed = self.cog.criar_embed_lista_status("aprovado")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as erro:
            print(f"[CADASTRO PAINEL] Erro ao listar aprovados: {erro}")
            await interaction.followup.send("❌ Não consegui carregar os aprovados agora.", ephemeral=True)

    @discord.ui.button(
        label="Reprovados",
        emoji=resolver_emoji_painel_cadastro(CADASTRO_PANEL_EMOJI_REJECTED, "❌"),
        style=discord.ButtonStyle.secondary,
        custom_id="cadastro_painel_reprovados",
    )
    async def reprovados(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            embed = self.cog.criar_embed_lista_status("reprovado")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as erro:
            print(f"[CADASTRO PAINEL] Erro ao listar reprovados: {erro}")
            await interaction.followup.send("❌ Não consegui carregar os reprovados agora.", ephemeral=True)

    @discord.ui.button(
        label="Importados",
        emoji=resolver_emoji_painel_cadastro(CADASTRO_PANEL_EMOJI_IMPORTED, "📥"),
        style=discord.ButtonStyle.secondary,
        custom_id="cadastro_painel_importados",
    )
    async def importados(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            embed = self.cog.criar_embed_lista_status("importado")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as erro:
            print(f"[CADASTRO PAINEL] Erro ao listar importados: {erro}")
            await interaction.followup.send("❌ Não consegui carregar os importados agora.", ephemeral=True)

    @discord.ui.button(
        label="Atualizar Painel",
        emoji=resolver_emoji_painel_cadastro(CADASTRO_PANEL_EMOJI_UPDATE, "🔄"),
        style=discord.ButtonStyle.secondary,
        custom_id="cadastro_painel_atualizar",
    )
    async def atualizar_painel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.validar_staff(interaction):
            return

        try:
            await interaction.response.edit_message(
                embed=criar_embed_painel_cadastros(),
                view=CadastroPanelView(self.cog),
            )
            await interaction.followup.send("✅ Painel atualizado.", ephemeral=True)
        except Exception as erro:
            print(f"[CADASTRO PAINEL] Erro ao atualizar painel: {erro}")
            await self.responder_ephemeral(interaction, "❌ Não consegui atualizar o painel agora.")


class CadastrosCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(CadastroPanelView(self))

    async def obter_canal_logs_cadastro(self):
        canal = self.bot.get_channel(CADASTRO_LOG_CHANNEL_ID)
        if canal:
            return canal

        try:
            return await self.bot.fetch_channel(CADASTRO_LOG_CHANNEL_ID)
        except Exception:
            return None

    async def enviar_embed_log_cadastro(self, embed):
        canal_logs = await self.obter_canal_logs_cadastro()
        if canal_logs and hasattr(canal_logs, "send"):
            try:
                await canal_logs.send(
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(users=True, roles=False),
                )
                return
            except Exception as erro:
                print(f"[CADASTROS] Erro ao enviar log de cadastro: {erro}")

        await enviar_log_bot(embed.title or "Log de Cadastros", embed.description or "Sem descrição.")

    async def enviar_log_ficha_salva(self, message, staff, registro):
        campos = registro.get("campos", {})
        embed = discord.Embed(
            title="🌙 Ficha Salva",
            description="Uma ficha de recrutamento foi registrada no sistema.",
            color=CADASTRO_COLOR,
        )
        embed.add_field(name="Membro", value=message.author.mention, inline=False)
        embed.add_field(name="Nick Discord", value=campos.get("nick_discord", NAO_IDENTIFICADO), inline=False)
        embed.add_field(name="Nome atual no Roblox", value=campos.get("nome_atual_roblox", NAO_IDENTIFICADO), inline=False)
        embed.add_field(name="Idade", value=campos.get("idade", NAO_IDENTIFICADO), inline=False)
        embed.add_field(
            name="Já participou de outros clãs",
            value=campos.get("ja_foi_de_outro_cla", NAO_IDENTIFICADO),
            inline=False,
        )
        embed.add_field(name="Quais clãs", value=campos.get("quais_clas", NAO_IDENTIFICADO), inline=False)
        embed.add_field(name="Disponibilidade", value=campos.get("disponibilidade", NAO_IDENTIFICADO), inline=False)
        embed.add_field(
            name="Participa de invasões/atividades",
            value=campos.get("participa_jogatinas", NAO_IDENTIFICADO),
            inline=False,
        )
        embed.add_field(
            name="Aceita fazer parte da FDN",
            value=campos.get("aceita_cores_fdn", NAO_IDENTIFICADO),
            inline=False,
        )
        embed.add_field(name="Validado por", value=staff.mention, inline=False)
        embed.add_field(name="Ficha", value=f"[Abrir mensagem]({message.jump_url})", inline=False)
        embed.add_field(name="Status", value="Aprovado", inline=False)
        embed.add_field(name="Ficha completa", value="Salva no sistema para consulta.", inline=False)
        if registro.get("formato_diferente"):
            embed.add_field(
                name="Observação",
                value="Formato diferente detectado. A ficha completa foi salva para consulta.",
                inline=False,
            )
        embed.set_footer(text=CADASTRO_FOOTER)
        await self.enviar_embed_log_cadastro(embed)

    async def enviar_log_ficha_nao_identificada(self, message, staff):
        embed = discord.Embed(
            title="☾ Ficha Não Identificada",
            description="Uma mensagem recebeu validação, mas o bot não conseguiu identificar o formato da ficha.",
            color=CADASTRO_COLOR,
        )
        embed.add_field(name="Mensagem", value=f"[Abrir mensagem]({message.jump_url})", inline=False)
        embed.add_field(name="Validado por", value=staff.mention, inline=False)
        embed.add_field(
            name="Ação necessária",
            value="Verificar manualmente se a ficha está no padrão correto.",
            inline=False,
        )
        embed.set_footer(text=CADASTRO_FOOTER)
        await self.enviar_embed_log_cadastro(embed)

    async def obter_canal_por_id(self, channel_id):
        canal = self.bot.get_channel(channel_id)
        if canal:
            return canal

        try:
            return await self.bot.fetch_channel(channel_id)
        except Exception:
            return None

    async def buscar_mensagem_em_canal(self, canal, message_id):
        if hasattr(canal, "fetch_message"):
            try:
                return await canal.fetch_message(message_id)
            except Exception:
                pass

        if isinstance(canal, discord.ForumChannel):
            for thread in list(getattr(canal, "threads", []) or []):
                try:
                    return await thread.fetch_message(message_id)
                except Exception:
                    pass

            try:
                async for thread in canal.archived_threads(limit=100):
                    try:
                        return await thread.fetch_message(message_id)
                    except Exception:
                        pass
            except Exception:
                pass

        return None

    async def buscar_mensagem_importacao(self, message_id):
        canais_ids = []
        for channel_id in (CADASTRO_CHANNEL_ID, CADASTRO_OLD_CHANNEL_ID):
            if channel_id and channel_id not in canais_ids:
                canais_ids.append(channel_id)

        for channel_id in canais_ids:
            canal = await self.obter_canal_por_id(channel_id)
            if not canal:
                continue

            mensagem = await self.buscar_mensagem_em_canal(canal, message_id)
            if mensagem:
                return mensagem

        return None

    async def obter_canal_cadastro_reagido(self, channel_id):
        canal = self.bot.get_channel(channel_id)
        if not canal:
            try:
                canal = await self.bot.fetch_channel(channel_id)
            except Exception:
                return None

        if getattr(canal, "id", None) == CADASTRO_CHANNEL_ID:
            return canal

        if getattr(canal, "parent_id", None) == CADASTRO_CHANNEL_ID:
            return canal

        return None

    async def obter_canal_painel_cadastro(self, ctx):
        if CADASTRO_PANEL_CHANNEL_ID == 0:
            return ctx.channel

        canal = self.bot.get_channel(CADASTRO_PANEL_CHANNEL_ID)
        if canal:
            return canal

        try:
            return await self.bot.fetch_channel(CADASTRO_PANEL_CHANNEL_ID)
        except Exception:
            return None

    async def enviar_ou_atualizar_painel_cadastro(self, canal):
        embed = criar_embed_painel_cadastros()
        view = CadastroPanelView(self)

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

    def obter_registros_cadastros(self):
        dados = carregar_dados_cadastros()
        return list(dados.get("cadastros", {}).values())

    def buscar_cadastro_por_termo(self, termo):
        termo_normalizado = normalizar_chave(termo)
        if not termo_normalizado:
            return None

        registros = self.obter_registros_cadastros()
        exatos = []
        parciais = []

        for registro in registros:
            valores = [
                valor_registro(registro, "member_id", "autor_id", default=""),
                valor_registro(registro, "member_name", "autor_nome", default=""),
                valor_registro(registro, "nick_discord", default=""),
                valor_registro(registro, "username_roblox", default=""),
                valor_registro(registro, "nome_atual_roblox", default=""),
            ]

            normalizados = [normalizar_chave(valor) for valor in valores if valor]
            if termo_normalizado in normalizados:
                exatos.append(registro)
                continue

            if any(termo_normalizado in valor for valor in normalizados):
                parciais.append(registro)

        candidatos = exatos or parciais
        if not candidatos:
            return None

        candidatos.sort(
            key=lambda registro: valor_ordenacao_data(
                valor_registro(
                    registro,
                    "updated_at",
                    "aprovado_em",
                    "reprovado_em",
                    "data_importacao",
                    "created_at",
                    "data_validacao",
                    "data_envio",
                    default="",
                )
            ),
            reverse=True,
        )
        return candidatos[0]

    def criar_embed_consulta_cadastro(self, termo):
        registro = self.buscar_cadastro_por_termo(termo)
        if not registro:
            raise LookupError("Cadastro não encontrado.")

        status, rotulo_staff, staff_nome, rotulo_data, data_valor = obter_info_status(registro)
        link_ficha = obter_link_ficha(registro)

        embed = discord.Embed(
            title="☾ Ficha de Recrutamento — FDN",
            color=CADASTRO_COLOR,
        )
        embed.add_field(name="Membro", value=obter_membro_referencia(registro), inline=False)
        embed.add_field(
            name="Nome salvo",
            value=valor_registro(registro, "member_name", "autor_nome"),
            inline=False,
        )
        embed.add_field(name="Nick do Discord", value=valor_registro(registro, "nick_discord"), inline=False)
        embed.add_field(name="Username Roblox", value=valor_registro(registro, "username_roblox"), inline=False)
        embed.add_field(name="Nome atual no Roblox", value=valor_registro(registro, "nome_atual_roblox"), inline=False)
        embed.add_field(name="Idade", value=valor_registro(registro, "idade"), inline=False)
        embed.add_field(
            name="Já participou de outros clãs",
            value=valor_registro(registro, "ja_foi_de_outro_cla"),
            inline=False,
        )
        embed.add_field(name="Quais clãs", value=valor_registro(registro, "quais_clas"), inline=False)
        embed.add_field(name="Disponibilidade", value=valor_registro(registro, "disponibilidade"), inline=False)
        embed.add_field(
            name="Participa de invasões/atividades",
            value=valor_registro(registro, "participa_jogatinas_invasoes", "participa_jogatinas"),
            inline=False,
        )
        embed.add_field(
            name="Consegue colocar tag",
            value=valor_registro(registro, "consegue_colocar_tag"),
            inline=False,
        )
        embed.add_field(
            name="Aceita fazer parte da FDN",
            value=valor_registro(registro, "aceita_fazer_parte_fdn", "aceita_cores_fdn"),
            inline=False,
        )
        embed.add_field(name="Recrutado por", value=valor_registro(registro, "recrutado_por"), inline=False)
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name=rotulo_staff, value=staff_nome, inline=False)
        embed.add_field(name=rotulo_data, value=formatar_data_cadastro(data_valor), inline=False)

        if registro.get("motivo_reprovacao"):
            embed.add_field(name="Motivo da reprovação", value=str(registro.get("motivo_reprovacao")), inline=False)

        if link_ficha:
            embed.add_field(name="Link da ficha", value=f"[Abrir ficha]({link_ficha})", inline=False)
        else:
            embed.add_field(name="Link da ficha", value="Sem link da ficha salvo.", inline=False)

        embed.set_footer(text=CADASTRO_FOOTER)
        return embed

    def criar_embed_lista_status(self, status):
        configuracoes = {
            "aprovado": (
                "☾ Cadastros Aprovados",
                "Últimos cadastros com status aprovado.",
                "Nenhum cadastro aprovado encontrado.",
            ),
            "reprovado": (
                "☾ Cadastros Reprovados",
                "Últimos cadastros com status reprovado.",
                "Nenhum cadastro reprovado encontrado.",
            ),
            "importado": (
                "☾ Cadastros Importados",
                "Últimos cadastros com status importado.",
                "Nenhum cadastro importado encontrado.",
            ),
        }

        titulo, _, vazio = configuracoes[status]
        registros = [
            registro
            for registro in self.obter_registros_cadastros()
            if valor_registro(registro, "status", default="").casefold() == status
        ]
        registros.sort(key=lambda registro: obter_data_ordenacao_status(registro, status), reverse=True)

        linhas = [montar_linha_lista_status(registro, status) for registro in registros[:10]]
        return criar_embed_resultado_cadastros(titulo, linhas, vazio)

    @commands.Cog.listener("on_raw_reaction_add")
    async def on_raw_reaction_add_cadastro(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        canal = await self.obter_canal_cadastro_reagido(payload.channel_id)
        if not canal:
            return

        if str(payload.emoji) != EMOJI_APROVAR_TAG:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            await enviar_log_bot(
                "⚠️ Falha ao processar ficha",
                f"Guild não encontrada para a reação da mensagem `{payload.message_id}`.",
            )
            return

        membro_staff = guild.get_member(payload.user_id)
        if not membro_staff:
            try:
                membro_staff = await guild.fetch_member(payload.user_id)
            except Exception:
                await enviar_log_bot(
                    "⚠️ Falha ao buscar staff",
                    f"Não consegui buscar o membro que reagiu na ficha `{payload.message_id}`.",
                )
                return

        if not membro_eh_staff(membro_staff):
            return

        try:
            message = await canal.fetch_message(payload.message_id)
        except Exception:
            await enviar_log_bot(
                "⚠️ Falha ao buscar ficha",
                f"Não consegui buscar a mensagem `{payload.message_id}` no canal <#{payload.channel_id}>.",
            )
            return

        if message.author.bot:
            return

        campos = extrair_ficha_recrutamento(message.content)

        try:
            _, registro = salvar_ficha_recrutamento(message, membro_staff, campos)
        except Exception as erro:
            await enviar_log_bot(
                "❌ Erro ao salvar ficha",
                (
                    f"**Staff:** {membro_staff.mention}\n"
                    f"**Membro:** {message.author.mention}\n"
                    f"**Mensagem:** `{message.id}`\n"
                    f"```{erro}```"
                ),
            )
            return

        await self.enviar_log_ficha_salva(message, membro_staff, registro)

    @commands.command(name="cadastropainel")
    async def cadastropainel(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send("❌ Apenas a staff pode usar este comando.")
            return

        canal = await self.obter_canal_painel_cadastro(ctx)
        if not canal or not hasattr(canal, "send"):
            await ctx.send("❌ Não consegui encontrar o canal do painel de cadastros.")
            return

        try:
            _, acao = await self.enviar_ou_atualizar_painel_cadastro(canal)
        except Exception as erro:
            print(f"[CADASTRO PAINEL] Erro ao enviar painel: {erro}")
            await ctx.send("❌ Não consegui enviar o painel de cadastros agora.")
            return

        mensagem = (
            f"✅ Painel de cadastros {acao} em {canal.mention}."
            if canal.id != ctx.channel.id
            else f"✅ Painel de cadastros {acao}."
        )
        await ctx.send(mensagem, delete_after=10)

    @commands.group(name="cadastro", invoke_without_command=True)
    async def cadastro(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use: `!cadastro importar ID_DA_MENSAGEM`")

    @cadastro.command(name="importar")
    async def cadastro_importar(self, ctx, message_id: int):
        if not membro_eh_staff(ctx.author):
            await ctx.send("❌ Apenas a staff pode importar fichas.")
            return

        mensagem = await self.buscar_mensagem_importacao(message_id)
        if not mensagem:
            await ctx.send("❌ Mensagem não encontrada. Verifique o ID informado.")
            return

        campos = extrair_ficha_recrutamento(mensagem.content or "")
        try:
            salvar_cadastro_importado(mensagem, ctx.author, campos)
        except Exception as erro:
            print(f"[CADASTROS] Erro ao importar ficha antiga: {erro}")
            await ctx.send("⚠️ Ocorreu um erro ao importar a ficha antiga. Verifique o console/logs.")
            return

        await ctx.send("✅ Ficha antiga importada com sucesso.")


async def setup(bot):
    await bot.add_cog(CadastrosCog(bot))
