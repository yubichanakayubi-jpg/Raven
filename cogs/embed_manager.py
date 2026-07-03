from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

from utils.discord_helpers import membro_eh_staff


EMBED_COLOR_PADRAO = discord.Color.from_rgb(0, 255, 255)
EMBED_TOTAL_MAXIMO = 6000
LINK_MENSAGEM_REGEX = re.compile(
    r"https?://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/channels/"
    r"(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)/?"
)


def limitar_texto(valor, limite):
    texto = str(valor or "").strip()
    if len(texto) <= limite:
        return texto
    return texto[: max(0, limite - 3)] + "..."


def copiar_embed(embed):
    return discord.Embed.from_dict(embed.to_dict())


def copiar_embeds(embeds):
    return [copiar_embed(embed) for embed in embeds]


def obter_url_proxy(proxy, atributo):
    valor = getattr(proxy, atributo, None)
    return str(valor) if valor else ""


def url_valida(valor):
    texto = str(valor or "").strip()
    if not texto:
        return True

    url = urlparse(texto)
    return url.scheme in {"http", "https"} and bool(url.netloc)


def converter_cor_hex(valor):
    texto = str(valor or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", texto):
        raise ValueError("Use uma cor HEX com 6 caracteres. Exemplo: #00FFFF.")
    return discord.Color(int(texto, 16))


def formatar_cor_hex(embed):
    cor = embed.color or EMBED_COLOR_PADRAO
    return f"#{cor.value:06X}"


def normalizar_inline(valor):
    texto = str(valor or "").strip().casefold()
    return texto not in {"n", "nao", "não", "no", "false", "0"}


def contar_caracteres_embed(embed):
    total = len(embed.title or "") + len(embed.description or "")
    total += len(getattr(embed.footer, "text", "") or "")
    total += len(getattr(embed.author, "name", "") or "")

    for campo in embed.fields:
        total += len(campo.name or "")
        total += len(campo.value or "")

    return total


def validar_embed(embed):
    erros = []
    titulo = embed.title or ""
    descricao = embed.description or ""
    autor = getattr(embed.author, "name", "") or ""
    autor_icone = obter_url_proxy(embed.author, "icon_url")
    footer = getattr(embed.footer, "text", "") or ""
    footer_icone = obter_url_proxy(embed.footer, "icon_url")
    imagem = obter_url_proxy(embed.image, "url")
    thumbnail = obter_url_proxy(embed.thumbnail, "url")

    if len(titulo) > 256:
        erros.append("O título pode ter no máximo 256 caracteres.")
    if len(descricao) > 4096:
        erros.append("A descrição pode ter no máximo 4096 caracteres.")
    if len(autor) > 256:
        erros.append("O autor pode ter no máximo 256 caracteres.")
    if len(footer) > 2048:
        erros.append("O footer pode ter no máximo 2048 caracteres.")
    if len(embed.fields) > 25:
        erros.append("A embed pode ter no máximo 25 campos.")

    for indice, campo in enumerate(embed.fields, start=1):
        if not str(campo.name or "").strip():
            erros.append(f"O nome do campo {indice} não pode ficar vazio.")
        if not str(campo.value or "").strip():
            erros.append(f"O conteúdo do campo {indice} não pode ficar vazio.")
        if len(campo.name or "") > 256:
            erros.append(f"O nome do campo {indice} pode ter no máximo 256 caracteres.")
        if len(campo.value or "") > 1024:
            erros.append(f"O conteúdo do campo {indice} pode ter no máximo 1024 caracteres.")

    for rotulo, url in (
        ("imagem", imagem),
        ("thumbnail", thumbnail),
        ("ícone do autor", autor_icone),
        ("ícone do footer", footer_icone),
    ):
        if not url_valida(url):
            erros.append(f"A URL de {rotulo} precisa começar com http:// ou https://.")

    if autor_icone and not autor:
        erros.append("Informe o nome do autor para usar o ícone do autor.")
    if footer_icone and not footer:
        erros.append("Informe o texto do footer para usar o ícone do footer.")

    total = contar_caracteres_embed(embed)
    if total > EMBED_TOTAL_MAXIMO:
        erros.append(f"A embed possui {total} caracteres. O limite total é {EMBED_TOTAL_MAXIMO}.")

    if not any((titulo, descricao, autor, footer, imagem, thumbnail, embed.fields)):
        erros.append("A embed precisa ter algum conteúdo antes de ser enviada.")

    return erros


def criar_embed_previa(embed):
    previa = copiar_embed(embed)
    if not validar_embed(previa):
        return previa
    return discord.Embed(
        title="Prévia indisponível",
        description="Corrija os erros indicados no painel antes de visualizar a embed.",
        color=discord.Color.orange(),
    )


@dataclass
class EmbedEditorSession:
    owner_id: int
    mode: str
    embed: discord.Embed
    target_channel: discord.TextChannel | None = None
    target_message: discord.Message | None = None
    extra_embeds: list[discord.Embed] = field(default_factory=list)
    panel_message: discord.InteractionMessage | None = None
    finished: bool = False


def criar_embed_painel(session):
    erros = validar_embed(session.embed)
    modo = "Criação" if session.mode == "create" else "Edição"

    if session.mode == "create":
        destino = session.target_channel.mention if session.target_channel else "Não informado"
    else:
        destino = (
            f"[Abrir mensagem]({session.target_message.jump_url})"
            if session.target_message
            else "Mensagem não encontrada"
        )

    status = "✅ Pronta para confirmar." if not erros else "⚠️ " + "\n⚠️ ".join(erros[:5])
    if len(erros) > 5:
        status += f"\n⚠️ Mais {len(erros) - 5} erro(s)."

    embed = discord.Embed(
        title=f"📝 Gerenciador de Embeds — {modo}",
        description=(
            "Use o menu abaixo para alterar somente a seção desejada.\n"
            "A mensagem real só será publicada ou editada após a confirmação."
        ),
        color=EMBED_COLOR_PADRAO,
    )
    embed.add_field(name="Destino", value=destino, inline=False)
    embed.add_field(
        name="Resumo",
        value=(
            f"Título: {limitar_texto(session.embed.title or 'Sem título', 150)}\n"
            f"Cor: {formatar_cor_hex(session.embed)}\n"
            f"Campos: {len(session.embed.fields)} de 25\n"
            f"Caracteres: {contar_caracteres_embed(session.embed)} de {EMBED_TOTAL_MAXIMO}"
        ),
        inline=False,
    )
    embed.add_field(name="Validação", value=limitar_texto(status, 1024), inline=False)
    embed.set_footer(text="FDN • Gerenciador de Embeds")
    return embed


async def responder_ephemeral(interaction, mensagem):
    if interaction.response.is_done():
        await interaction.followup.send(mensagem, ephemeral=True)
    else:
        await interaction.response.send_message(mensagem, ephemeral=True)


async def validar_dono_sessao(interaction, session):
    if interaction.user.id != session.owner_id:
        await responder_ephemeral(interaction, "Este painel não pertence a você.")
        return False
    if session.finished:
        await responder_ephemeral(interaction, "Este painel já foi encerrado.")
        return False
    return True


async def atualizar_painel(session, desativado=False):
    if session.panel_message is None:
        return False

    try:
        await session.panel_message.edit(
            embed=criar_embed_painel(session),
            view=EmbedEditorView(session, disabled=desativado),
        )
        return True
    except Exception:
        return False


async def aplicar_embed_na_sessao(interaction, session, embed):
    erros = validar_embed(embed)
    if erros:
        await responder_ephemeral(interaction, "❌ " + "\n❌ ".join(erros[:5]))
        return False

    session.embed = embed
    if not interaction.response.is_done():
        await interaction.response.defer()
    await atualizar_painel(session)
    return True


class EmbedContentModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Editar conteúdo da embed")
        self.session = session
        self.titulo = discord.ui.TextInput(
            label="Título",
            default=session.embed.title or "",
            required=False,
            max_length=256,
        )
        self.descricao = discord.ui.TextInput(
            label="Descrição",
            default=session.embed.description or "",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=4000,
        )
        self.cor = discord.ui.TextInput(
            label="Cor HEX",
            default=formatar_cor_hex(session.embed),
            placeholder="#00FFFF",
            required=True,
            max_length=7,
        )
        self.add_item(self.titulo)
        self.add_item(self.descricao)
        self.add_item(self.cor)

    async def on_submit(self, interaction):
        if not await validar_dono_sessao(interaction, self.session):
            return

        try:
            cor = converter_cor_hex(self.cor.value)
        except ValueError as erro:
            await responder_ephemeral(interaction, f"❌ {erro}")
            return

        embed = copiar_embed(self.session.embed)
        embed.title = self.titulo.value.strip() or None
        embed.description = self.descricao.value.strip() or None
        embed.color = cor
        await aplicar_embed_na_sessao(interaction, self.session, embed)


class EmbedMediaModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Editar mídia da embed")
        self.session = session
        self.imagem = discord.ui.TextInput(
            label="URL da imagem grande",
            default=obter_url_proxy(session.embed.image, "url"),
            placeholder="https://exemplo.com/imagem.png",
            required=False,
            max_length=1000,
        )
        self.thumbnail = discord.ui.TextInput(
            label="URL da thumbnail",
            default=obter_url_proxy(session.embed.thumbnail, "url"),
            placeholder="https://exemplo.com/thumbnail.png",
            required=False,
            max_length=1000,
        )
        self.add_item(self.imagem)
        self.add_item(self.thumbnail)

    async def on_submit(self, interaction):
        if not await validar_dono_sessao(interaction, self.session):
            return

        imagem = self.imagem.value.strip()
        thumbnail = self.thumbnail.value.strip()
        if not url_valida(imagem) or not url_valida(thumbnail):
            await responder_ephemeral(interaction, "❌ Use URLs começando com http:// ou https://.")
            return

        embed = copiar_embed(self.session.embed)
        embed.set_image(url=imagem or None)
        embed.set_thumbnail(url=thumbnail or None)
        await aplicar_embed_na_sessao(interaction, self.session, embed)


class EmbedAuthorModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Editar autor da embed")
        self.session = session
        self.nome = discord.ui.TextInput(
            label="Autor",
            default=getattr(session.embed.author, "name", "") or "",
            required=False,
            max_length=256,
        )
        self.icone = discord.ui.TextInput(
            label="URL do ícone do autor",
            default=obter_url_proxy(session.embed.author, "icon_url"),
            placeholder="https://exemplo.com/icone.png",
            required=False,
            max_length=1000,
        )
        self.add_item(self.nome)
        self.add_item(self.icone)

    async def on_submit(self, interaction):
        if not await validar_dono_sessao(interaction, self.session):
            return

        nome = self.nome.value.strip()
        icone = self.icone.value.strip()
        if not url_valida(icone):
            await responder_ephemeral(interaction, "❌ A URL do ícone precisa começar com http:// ou https://.")
            return
        if icone and not nome:
            await responder_ephemeral(interaction, "❌ Informe o nome do autor para usar um ícone.")
            return

        embed = copiar_embed(self.session.embed)
        if nome:
            embed.set_author(name=nome, icon_url=icone or None)
        else:
            embed.remove_author()
        await aplicar_embed_na_sessao(interaction, self.session, embed)


class EmbedFooterModal(discord.ui.Modal):
    def __init__(self, session):
        super().__init__(title="Editar footer da embed")
        self.session = session
        self.texto = discord.ui.TextInput(
            label="Footer",
            default=getattr(session.embed.footer, "text", "") or "",
            required=False,
            max_length=2048,
        )
        self.icone = discord.ui.TextInput(
            label="URL do ícone do footer",
            default=obter_url_proxy(session.embed.footer, "icon_url"),
            placeholder="https://exemplo.com/icone.png",
            required=False,
            max_length=1000,
        )
        self.add_item(self.texto)
        self.add_item(self.icone)

    async def on_submit(self, interaction):
        if not await validar_dono_sessao(interaction, self.session):
            return

        texto = self.texto.value.strip()
        icone = self.icone.value.strip()
        if not url_valida(icone):
            await responder_ephemeral(interaction, "❌ A URL do ícone precisa começar com http:// ou https://.")
            return
        if icone and not texto:
            await responder_ephemeral(interaction, "❌ Informe o texto do footer para usar um ícone.")
            return

        embed = copiar_embed(self.session.embed)
        if texto:
            embed.set_footer(text=texto, icon_url=icone or None)
        else:
            embed.remove_footer()
        await aplicar_embed_na_sessao(interaction, self.session, embed)


class EmbedFieldModal(discord.ui.Modal):
    def __init__(self, session, index=None):
        titulo = "Adicionar campo" if index is None else "Editar campo"
        super().__init__(title=titulo)
        self.session = session
        self.index = index
        campo = session.embed.fields[index] if index is not None else None

        self.nome = discord.ui.TextInput(
            label="Nome do campo",
            default=campo.name if campo else "",
            required=True,
            max_length=256,
        )
        self.valor = discord.ui.TextInput(
            label="Conteúdo do campo",
            default=campo.value if campo else "",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1024,
        )
        self.inline = discord.ui.TextInput(
            label="Campo inline? Digite Sim ou Não",
            default="Sim" if campo and campo.inline else "Não",
            required=True,
            max_length=3,
        )
        self.add_item(self.nome)
        self.add_item(self.valor)
        self.add_item(self.inline)

    async def on_submit(self, interaction):
        if not await validar_dono_sessao(interaction, self.session):
            return

        embed = copiar_embed(self.session.embed)
        if self.index is None:
            if len(embed.fields) >= 25:
                await responder_ephemeral(interaction, "❌ A embed já possui o limite de 25 campos.")
                return
            embed.add_field(
                name=self.nome.value.strip(),
                value=self.valor.value.strip(),
                inline=normalizar_inline(self.inline.value),
            )
        else:
            if self.index >= len(embed.fields):
                await responder_ephemeral(interaction, "❌ Este campo não existe mais.")
                return
            embed.set_field_at(
                self.index,
                name=self.nome.value.strip(),
                value=self.valor.value.strip(),
                inline=normalizar_inline(self.inline.value),
            )

        await aplicar_embed_na_sessao(interaction, self.session, embed)


class EmbedFieldPickerSelect(discord.ui.Select):
    def __init__(self, session, action):
        self.session = session
        self.action = action
        options = [
            discord.SelectOption(
                label=limitar_texto(campo.name or f"Campo {indice + 1}", 100),
                value=str(indice),
                description=limitar_texto(campo.value or "Sem conteúdo", 100),
            )
            for indice, campo in enumerate(session.embed.fields)
        ]
        super().__init__(
            placeholder="Escolha um campo",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        if not await validar_dono_sessao(interaction, self.session):
            return

        indice = int(self.values[0])
        if self.action == "edit":
            await interaction.response.send_modal(EmbedFieldModal(self.session, index=indice))
            return

        embed = copiar_embed(self.session.embed)
        if indice >= len(embed.fields):
            await responder_ephemeral(interaction, "❌ Este campo não existe mais.")
            return

        embed.remove_field(indice)
        if not interaction.response.is_done():
            await interaction.response.defer()
        self.session.embed = embed
        await atualizar_painel(self.session)
        await interaction.followup.send("✅ Campo removido.", ephemeral=True)


class EmbedFieldPickerView(discord.ui.View):
    def __init__(self, session, action):
        super().__init__(timeout=300)
        self.session = session
        self.add_item(EmbedFieldPickerSelect(session, action))

    async def interaction_check(self, interaction):
        return await validar_dono_sessao(interaction, self.session)


class EmbedEditorSelect(discord.ui.Select):
    def __init__(self, session, disabled=False):
        self.session = session
        options = [
            discord.SelectOption(label="Conteúdo", value="content", description="Editar título, descrição e cor."),
            discord.SelectOption(label="Mídia", value="media", description="Editar imagem grande e thumbnail."),
            discord.SelectOption(label="Autor", value="author", description="Editar autor e ícone do autor."),
            discord.SelectOption(label="Footer", value="footer", description="Editar footer e ícone do footer."),
            discord.SelectOption(label="Adicionar campo", value="field_add", description="Adicionar um novo field."),
            discord.SelectOption(label="Editar campo", value="field_edit", description="Alterar um field existente."),
            discord.SelectOption(label="Remover campo", value="field_remove", description="Excluir um field existente."),
            discord.SelectOption(label="Limpar imagem", value="clear_image", description="Remover a imagem grande."),
            discord.SelectOption(label="Limpar thumbnail", value="clear_thumbnail", description="Remover a thumbnail."),
            discord.SelectOption(label="Limpar autor", value="clear_author", description="Remover autor e ícone."),
            discord.SelectOption(label="Limpar footer", value="clear_footer", description="Remover footer e ícone."),
        ]
        super().__init__(
            placeholder="Escolha o que deseja alterar",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
        )

    async def callback(self, interaction):
        if not await validar_dono_sessao(interaction, self.session):
            return

        action = self.values[0]
        if action == "content":
            await interaction.response.send_modal(EmbedContentModal(self.session))
            return
        if action == "media":
            await interaction.response.send_modal(EmbedMediaModal(self.session))
            return
        if action == "author":
            await interaction.response.send_modal(EmbedAuthorModal(self.session))
            return
        if action == "footer":
            await interaction.response.send_modal(EmbedFooterModal(self.session))
            return
        if action == "field_add":
            await interaction.response.send_modal(EmbedFieldModal(self.session))
            return
        if action in {"field_edit", "field_remove"}:
            if not self.session.embed.fields:
                await responder_ephemeral(interaction, "❌ Esta embed ainda não possui campos.")
                return
            await interaction.response.send_message(
                "Escolha o campo desejado:",
                view=EmbedFieldPickerView(
                    self.session,
                    "edit" if action == "field_edit" else "remove",
                ),
                ephemeral=True,
            )
            return

        embed = copiar_embed(self.session.embed)
        if action == "clear_image":
            embed.set_image(url=None)
        elif action == "clear_thumbnail":
            embed.set_thumbnail(url=None)
        elif action == "clear_author":
            embed.remove_author()
        elif action == "clear_footer":
            embed.remove_footer()

        await aplicar_embed_na_sessao(interaction, self.session, embed)


class EmbedEditorView(discord.ui.View):
    def __init__(self, session, disabled=False):
        super().__init__(timeout=900)
        self.session = session
        self.add_item(EmbedEditorSelect(session, disabled=disabled))

        if disabled:
            for child in self.children:
                child.disabled = True

    async def interaction_check(self, interaction):
        return await validar_dono_sessao(interaction, self.session)

    @discord.ui.button(label="Pré-visualizar", emoji="👁️", style=discord.ButtonStyle.secondary)
    async def preview(self, interaction, button):
        await interaction.response.send_message(
            embed=criar_embed_previa(self.session.embed),
            ephemeral=True,
        )

    @discord.ui.button(label="Confirmar", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        erros = validar_embed(self.session.embed)
        if erros:
            await responder_ephemeral(interaction, "❌ " + "\n❌ ".join(erros[:5]))
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if self.session.mode == "create":
                mensagem = await self.session.target_channel.send(embed=copiar_embed(self.session.embed))
                print(
                    f"[EMBED] Criada | staff={interaction.user} ({interaction.user.id}) | "
                    f"canal={mensagem.channel.id} | mensagem={mensagem.id}"
                )
                resposta = f"✅ Embed enviada: {mensagem.jump_url}"
            else:
                embeds = [copiar_embed(self.session.embed), *copiar_embeds(self.session.extra_embeds)]
                await self.session.target_message.edit(embeds=embeds)
                print(
                    f"[EMBED] Editada | staff={interaction.user} ({interaction.user.id}) | "
                    f"canal={self.session.target_message.channel.id} | mensagem={self.session.target_message.id}"
                )
                resposta = f"✅ Embed atualizada: {self.session.target_message.jump_url}"
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Não tenho permissão para enviar ou editar essa mensagem.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as erro:
            await interaction.followup.send(
                f"❌ O Discord recusou a embed (HTTP {erro.status}). Verifique os dados informados.",
                ephemeral=True,
            )
            return
        except Exception as erro:
            print(f"[EMBED] Erro inesperado ao confirmar operação: {erro}")
            await interaction.followup.send(
                "❌ Não consegui concluir a operação agora. Tente novamente.",
                ephemeral=True,
            )
            return

        self.session.finished = True
        await atualizar_painel(self.session, desativado=True)
        await interaction.followup.send(resposta, ephemeral=True)

    @discord.ui.button(label="Cancelar", emoji="✖️", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        await interaction.response.defer()
        self.session.finished = True
        await atualizar_painel(self.session, desativado=True)
        await interaction.followup.send("✅ Operação cancelada.", ephemeral=True)


class EmbedManagerCog(commands.Cog):
    embed_group = app_commands.Group(name="embed", description="Cria e edita embeds do bot.")

    def __init__(self, bot):
        self.bot = bot

    async def iniciar_painel(self, interaction, session):
        await interaction.response.send_message(
            embed=criar_embed_painel(session),
            view=EmbedEditorView(session),
            ephemeral=True,
        )
        session.panel_message = await interaction.original_response()

    async def validar_staff(self, interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Esse comando só pode ser usado em servidor.",
                ephemeral=True,
            )
            return False

        if not membro_eh_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Você não tem permissão para usar este comando.",
                ephemeral=True,
            )
            return False

        return True

    async def resolver_mensagem_edicao(self, interaction, mensagem_link, canal, mensagem_id):
        canal_resolvido = canal
        mensagem_id_resolvida = str(mensagem_id or "").strip()

        if mensagem_link:
            resultado = LINK_MENSAGEM_REGEX.fullmatch(str(mensagem_link).strip())
            if not resultado:
                return None, "❌ Informe um link válido de mensagem do Discord."

            if int(resultado.group("guild_id")) != interaction.guild.id:
                return None, "❌ A mensagem precisa pertencer a este servidor."

            channel_id = int(resultado.group("channel_id"))
            mensagem_id_resolvida = resultado.group("message_id")
            canal_resolvido = interaction.guild.get_channel(channel_id)
            if canal_resolvido is None:
                try:
                    canal_resolvido = await self.bot.fetch_channel(channel_id)
                except Exception:
                    return None, "❌ Não consegui encontrar o canal informado no link."

        if canal_resolvido is None or not mensagem_id_resolvida:
            return None, "❌ Informe o link da mensagem ou preencha canal e ID da mensagem."
        if not mensagem_id_resolvida.isdigit():
            return None, "❌ O ID da mensagem precisa conter apenas números."
        if getattr(canal_resolvido, "guild", None) != interaction.guild:
            return None, "❌ O canal precisa pertencer a este servidor."
        if not hasattr(canal_resolvido, "fetch_message"):
            return None, "❌ Não consigo buscar mensagens nesse canal."

        try:
            mensagem = await canal_resolvido.fetch_message(int(mensagem_id_resolvida))
        except discord.NotFound:
            return None, "❌ Não encontrei essa mensagem."
        except discord.Forbidden:
            return None, "❌ Não tenho acesso a essa mensagem."
        except discord.HTTPException:
            return None, "❌ O Discord não permitiu buscar essa mensagem agora."

        if not self.bot.user or mensagem.author.id != self.bot.user.id:
            return None, "❌ Só posso editar mensagens enviadas por mim."
        if not mensagem.embeds:
            return None, "❌ Essa mensagem não possui embed."

        return mensagem, None

    @embed_group.command(name="criar", description="Cria uma embed completa em um canal.")
    @app_commands.describe(canal="Canal onde a embed será publicada.")
    async def embed_criar(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not await self.validar_staff(interaction):
            return

        session = EmbedEditorSession(
            owner_id=interaction.user.id,
            mode="create",
            embed=discord.Embed(title="Nova embed", color=EMBED_COLOR_PADRAO),
            target_channel=canal,
        )
        await self.iniciar_painel(interaction, session)

    @embed_group.command(name="editar", description="Edita uma embed que já foi enviada pelo bot.")
    @app_commands.describe(
        mensagem_link="Link completo da mensagem do Discord.",
        canal="Canal da mensagem, caso não use o link.",
        mensagem_id="ID da mensagem, caso não use o link.",
    )
    async def embed_editar(
        self,
        interaction: discord.Interaction,
        mensagem_link: str | None = None,
        canal: discord.TextChannel | None = None,
        mensagem_id: str | None = None,
    ):
        if not await self.validar_staff(interaction):
            return

        mensagem, erro = await self.resolver_mensagem_edicao(
            interaction,
            mensagem_link,
            canal,
            mensagem_id,
        )
        if erro:
            await interaction.response.send_message(erro, ephemeral=True)
            return

        session = EmbedEditorSession(
            owner_id=interaction.user.id,
            mode="edit",
            embed=copiar_embed(mensagem.embeds[0]),
            target_channel=mensagem.channel,
            target_message=mensagem,
            extra_embeds=copiar_embeds(mensagem.embeds[1:]),
        )
        await self.iniciar_painel(interaction, session)


async def setup(bot):
    await bot.add_cog(EmbedManagerCog(bot))
