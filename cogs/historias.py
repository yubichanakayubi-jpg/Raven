from datetime import datetime, timedelta, timezone
import asyncio
import json
from pathlib import Path, PurePath
import shlex
import traceback

import discord
from discord import app_commands
from discord.ext import commands

from config import CANAL_LOGS_ID, HISTORIAS_CHANNEL_ID, HISTORIAS_STAFF_ROLE_ID


FORMATOS_IMAGEM = (".png", ".jpg", ".jpeg", ".webp", ".gif")
COR_HISTORIAS = discord.Color.from_rgb(0, 255, 255)
FUSO_BRASIL = timezone(timedelta(hours=-3))
ARQUIVO_HISTORIAS = Path(__file__).resolve().parents[1] / "dados_historias.json"
COMENTARIOS_POR_PAGINA = 5
MAX_IMAGENS_HISTORIA = 10


def agora_br() -> datetime:
    return datetime.now(FUSO_BRASIL)


def data_atual_br() -> str:
    return agora_br().strftime("%d/%m/%Y")


def membro_pode_publicar_historias(membro) -> bool:
    if not isinstance(membro, discord.Member):
        return False

    if membro.guild_permissions.administrator:
        return True

    return any(cargo.id == HISTORIAS_STAFF_ROLE_ID for cargo in membro.roles)


def anexo_eh_imagem(anexo: discord.Attachment) -> bool:
    return anexo.filename.lower().endswith(FORMATOS_IMAGEM)


def imagens_anexadas(anexos: list[discord.Attachment], limite: int = MAX_IMAGENS_HISTORIA) -> list[discord.Attachment]:
    imagens = []

    for anexo in anexos:
        if anexo_eh_imagem(anexo):
            imagens.append(anexo)
            if len(imagens) >= limite:
                break

    return imagens


def nome_arquivo_seguro(nome_original: str, indice: int | None = None) -> str:
    extensao = PurePath(nome_original or "historia.png").suffix.lower()

    if extensao not in FORMATOS_IMAGEM:
        extensao = ".png"

    sufixo = f"_{indice}" if indice is not None else ""
    return f"historia{sufixo}{extensao}"


def limitar_texto(texto: str, limite: int) -> str:
    texto = str(texto or "").strip()

    if len(texto) <= limite:
        return texto

    return texto[: max(0, limite - 3)].rstrip() + "..."


def carregar_dados_historias() -> dict:
    if not ARQUIVO_HISTORIAS.exists():
        return {"historias": {}}

    try:
        with ARQUIVO_HISTORIAS.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except Exception:
        traceback.print_exc()
        return {"historias": {}}

    if not isinstance(dados, dict):
        return {"historias": {}}

    if "historias" not in dados or not isinstance(dados["historias"], dict):
        return {"historias": dados}

    return dados


def salvar_dados_historias(dados: dict):
    ARQUIVO_HISTORIAS.parent.mkdir(parents=True, exist_ok=True)
    temporario = ARQUIVO_HISTORIAS.with_suffix(".tmp")

    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)

    temporario.replace(ARQUIVO_HISTORIAS)


def carregar_historia(historia_id: str) -> dict | None:
    dados = carregar_dados_historias()
    return dados.get("historias", {}).get(str(historia_id))


def listar_historias_salvas() -> list[dict]:
    dados = carregar_dados_historias()
    return list(dados.get("historias", {}).values())


def extrair_titulo_data(argumento: str) -> tuple[str, str]:
    texto = (argumento or "").strip()

    if not texto:
        return "", data_atual_br()

    if not texto.startswith(('"', "'")):
        return texto, data_atual_br()

    try:
        partes = shlex.split(texto)
    except ValueError:
        return texto.strip('"').strip("'"), data_atual_br()

    titulo = partes[0].strip() if partes else ""
    data_historia = partes[1].strip() if len(partes) > 1 else data_atual_br()
    return titulo, data_historia or data_atual_br()


def normalizar_ids(lista) -> list[int]:
    ids = []
    vistos = set()

    for item in lista or []:
        try:
            user_id = int(item)
        except (TypeError, ValueError):
            continue

        if user_id not in vistos:
            ids.append(user_id)
            vistos.add(user_id)

    return ids


def obter_imagens_historia(historia: dict) -> list[str]:
    imagens = historia.get("image_urls")
    if isinstance(imagens, list):
        urls = [str(url or "").strip() for url in imagens if str(url or "").strip()]
        if urls:
            return urls

    imagem = str(historia.get("image_url") or "").strip()
    return [imagem] if imagem else []


def obter_indice_imagem_historia(historia: dict) -> int:
    imagens = obter_imagens_historia(historia)
    if not imagens:
        return 0

    try:
        indice = int(historia.get("current_image_index") or 0)
    except (TypeError, ValueError):
        indice = 0

    return min(max(0, indice), len(imagens) - 1)


def criar_embed_historia(
    historia: dict,
    image_url: str | None = None,
    indice_imagem: int | None = None,
) -> discord.Embed:
    likes = normalizar_ids(historia.get("likes", []))
    laughs = normalizar_ids(historia.get("laughs", []))
    imagens = obter_imagens_historia(historia)
    if indice_imagem is None:
        indice_imagem = 0

    if imagens:
        indice_imagem = min(max(0, indice_imagem), len(imagens) - 1)
    else:
        indice_imagem = 0

    imagem = image_url or (imagens[indice_imagem] if imagens else None)

    embed = discord.Embed(
        title=f"🌙 {historia.get('titulo', 'História')}",
        description="A noite guarda mais um capítulo da nossa história.",
        color=COR_HISTORIAS,
    )
    embed.add_field(
        name="Data",
        value=historia.get("data_historia") or data_atual_br(),
        inline=False,
    )
    embed.add_field(
        name="Interações",
        value=(
            f"❤️ Curtidas: {len(likes)}\n"
            f"😂 Risos: {len(laughs)}"
        ),
        inline=False,
    )
    if len(imagens) > 1:
        embed.set_footer(text=f"FDN • Histórias • Imagem {indice_imagem + 1}/{len(imagens)}")
    else:
        embed.set_footer(text="FDN • Histórias")

    if imagem:
        embed.set_image(url=imagem)

    return embed


def criar_embed_comentarios_historia(historia: dict, pagina: int = 0) -> tuple[discord.Embed, int, int]:
    comentarios = historia.get("comentarios", []) or []
    total_paginas = max(1, (len(comentarios) + COMENTARIOS_POR_PAGINA - 1) // COMENTARIOS_POR_PAGINA)
    pagina = min(max(0, pagina), total_paginas - 1)
    inicio = pagina * COMENTARIOS_POR_PAGINA
    comentarios_pagina = comentarios[inicio:inicio + COMENTARIOS_POR_PAGINA]

    embed = discord.Embed(
        title=f"💬 Comentários — {historia.get('titulo', 'História')}",
        color=COR_HISTORIAS,
    )

    if not comentarios_pagina:
        embed.description = "Nenhum comentário ainda."
    else:
        linhas = []
        for indice, comentario in enumerate(comentarios_pagina, start=inicio + 1):
            nome = limitar_texto(comentario.get("user_name", "usuário"), 60)
            texto = limitar_texto(comentario.get("comentario", ""), 850)
            linhas.append(f"**{indice}. @{nome}**\n{texto}")

        embed.description = "\n\n".join(linhas)

    embed.set_footer(text=f"Página {pagina + 1}/{total_paginas} • {len(comentarios)} comentários")
    return embed, pagina, total_paginas


class ComentarioHistoriaModal(discord.ui.Modal, title="Comentar na História"):
    comentario = discord.ui.TextInput(
        label="Comentário",
        placeholder="Escreva seu comentário sobre esta história.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000,
    )

    def __init__(self, cog, historia_id: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.historia_id = str(historia_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            comentario = str(self.comentario.value or "").strip()

            if not comentario:
                await interaction.response.send_message(
                    "❌ Comentário não pode ficar vazio.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True, thinking=False)
            await self.cog.registrar_comentario(interaction, self.historia_id, comentario)
            await interaction.followup.send("💬 Comentário enviado com sucesso.", ephemeral=True)
        except Exception:
            traceback.print_exc()

            if interaction.response.is_done():
                await interaction.followup.send("Ocorreu um erro ao comentar nesta história.", ephemeral=True)
            else:
                await interaction.response.send_message("Ocorreu um erro ao comentar nesta história.", ephemeral=True)


class ComentariosHistoriaView(discord.ui.View):
    def __init__(self, historia_id: str, pagina: int = 0):
        super().__init__(timeout=300)
        self.historia_id = str(historia_id)
        self.pagina = pagina
        self.total_paginas = 1
        self.atualizar_botoes()

    def atualizar_botoes(self):
        self.anterior.disabled = self.pagina <= 0
        self.proxima.disabled = self.pagina >= self.total_paginas - 1

    async def atualizar(self, interaction: discord.Interaction):
        historia = carregar_historia(self.historia_id)

        if not historia:
            await interaction.response.edit_message(
                content="História não encontrada.",
                embed=None,
                view=None,
            )
            return

        embed, self.pagina, self.total_paginas = criar_embed_comentarios_historia(historia, self.pagina)
        self.atualizar_botoes()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina -= 1
        await self.atualizar(interaction)

    @discord.ui.button(label="Próxima", style=discord.ButtonStyle.secondary)
    async def proxima(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina += 1
        await self.atualizar(interaction)


class HistoriaImagemView(discord.ui.View):
    def __init__(self, historia_id: str, indice: int = 0):
        super().__init__(timeout=300)
        self.historia_id = str(historia_id)
        self.indice = max(0, int(indice or 0))

        self.botao_anterior = discord.ui.Button(
            label="\u2b05\ufe0f",
            style=discord.ButtonStyle.secondary,
        )
        self.botao_anterior.callback = self.anterior
        self.add_item(self.botao_anterior)

        self.botao_proxima = discord.ui.Button(
            label="\u27a1\ufe0f",
            style=discord.ButtonStyle.secondary,
        )
        self.botao_proxima.callback = self.proxima
        self.add_item(self.botao_proxima)

        self.atualizar_botoes()

    def obter_historia(self) -> dict | None:
        return carregar_historia(self.historia_id)

    def atualizar_botoes(self):
        historia = self.obter_historia() or {}
        total = len(obter_imagens_historia(historia))
        self.indice = min(max(0, self.indice), max(0, total - 1))
        self.botao_anterior.disabled = total <= 1 or self.indice <= 0
        self.botao_proxima.disabled = total <= 1 or self.indice >= total - 1

    async def atualizar(self, interaction: discord.Interaction):
        historia = self.obter_historia()

        if not historia:
            await interaction.response.edit_message(
                content="História não encontrada.",
                embed=None,
                view=None,
            )
            return

        imagens = obter_imagens_historia(historia)
        if not imagens:
            await interaction.response.edit_message(
                content="Esta história não possui imagens.",
                embed=None,
                view=None,
            )
            return

        self.atualizar_botoes()
        embed = criar_embed_historia(historia, indice_imagem=self.indice)
        await interaction.response.edit_message(embed=embed, view=self)

    async def anterior(self, interaction: discord.Interaction):
        self.indice -= 1
        await self.atualizar(interaction)

    async def proxima(self, interaction: discord.Interaction):
        self.indice += 1
        await self.atualizar(interaction)


class HistoriaInteracoesView(discord.ui.View):
    def __init__(self, cog, historia_id: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.historia_id = str(historia_id)

        botao_like = discord.ui.Button(
            label="❤️ Curtir",
            style=discord.ButtonStyle.secondary,
            custom_id=f"historia_like:{self.historia_id}",
        )
        botao_like.callback = self.curtir
        self.add_item(botao_like)

        botao_laugh = discord.ui.Button(
            label="😂 Risos",
            style=discord.ButtonStyle.secondary,
            custom_id=f"historia_laugh:{self.historia_id}",
        )
        botao_laugh.callback = self.risos
        self.add_item(botao_laugh)

        self.botao_imagem_anterior = discord.ui.Button(
            label="\u2b05\ufe0f",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id=f"historia_image_prev:{self.historia_id}",
        )
        self.botao_imagem_anterior.callback = self.imagem_anterior
        self.add_item(self.botao_imagem_anterior)

        self.botao_proxima_imagem = discord.ui.Button(
            label="\u27a1\ufe0f",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id=f"historia_image_next:{self.historia_id}",
        )
        self.botao_proxima_imagem.callback = self.proxima_imagem
        self.add_item(self.botao_proxima_imagem)

        self.atualizar_botoes_imagem()

    def atualizar_botoes_imagem(self):
        historia = carregar_historia(self.historia_id) or {}
        imagens = obter_imagens_historia(historia)
        total = len(imagens)

        self.botao_imagem_anterior.disabled = True
        self.botao_proxima_imagem.disabled = total <= 1

    async def curtir(self, interaction: discord.Interaction):
        await self.cog.alternar_interacao(
            interaction,
            self.historia_id,
            "likes",
            "❤️ Você curtiu esta história.",
            "💔 Você removeu sua curtida desta história.",
        )

    async def risos(self, interaction: discord.Interaction):
        await self.cog.alternar_interacao(
            interaction,
            self.historia_id,
            "laughs",
            "😂 Você reagiu com risos nesta história.",
            "Você removeu sua reação de risos desta história.",
        )

    async def comentar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ComentarioHistoriaModal(self.cog, self.historia_id))

    async def ver_comentarios(self, interaction: discord.Interaction):
        historia = carregar_historia(self.historia_id)

        if not historia:
            await interaction.response.send_message("História não encontrada.", ephemeral=True)
            return

        embed, pagina, total_paginas = criar_embed_comentarios_historia(historia)
        view = ComentariosHistoriaView(self.historia_id, pagina)
        view.total_paginas = total_paginas
        view.atualizar_botoes()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def imagem_anterior(self, interaction: discord.Interaction):
        await self.cog.navegar_imagem_historia(interaction, self.historia_id, -1)

    async def proxima_imagem(self, interaction: discord.Interaction):
        await self.cog.navegar_imagem_historia(interaction, self.historia_id, 1)


class Historias(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        self.registrar_views_persistentes()

    def registrar_views_persistentes(self):
        for historia in listar_historias_salvas():
            historia_id = str(historia.get("historia_id") or historia.get("message_id") or "")

            if not historia_id.isdigit():
                continue

            try:
                self.bot.add_view(
                    HistoriaInteracoesView(self, historia_id),
                    message_id=int(historia_id),
                )
            except Exception:
                traceback.print_exc()

    async def obter_canal_destino(self, canal_fallback):
        if HISTORIAS_CHANNEL_ID == 0:
            return canal_fallback

        canal = self.bot.get_channel(HISTORIAS_CHANNEL_ID)

        if canal is None:
            try:
                canal = await self.bot.fetch_channel(HISTORIAS_CHANNEL_ID)
            except Exception:
                traceback.print_exc()
                return None

        if not hasattr(canal, "send"):
            return None

        return canal

    async def obter_canal_cache_imagens(self, canal_fallback):
        canal = self.bot.get_channel(CANAL_LOGS_ID)

        if canal is None:
            try:
                canal = await self.bot.fetch_channel(CANAL_LOGS_ID)
            except Exception:
                canal = None

        if canal is not None and hasattr(canal, "send"):
            return canal

        return canal_fallback if hasattr(canal_fallback, "send") else None

    async def obter_canal_por_id(self, channel_id: int):
        canal = self.bot.get_channel(int(channel_id))

        if canal is not None:
            return canal

        try:
            return await self.bot.fetch_channel(int(channel_id))
        except Exception:
            traceback.print_exc()
            return None

    async def obter_mensagem_historia(self, historia: dict):
        canal = await self.obter_canal_por_id(historia.get("channel_id"))

        if canal is None or not hasattr(canal, "fetch_message"):
            return None

        try:
            return await canal.fetch_message(int(historia.get("message_id")))
        except Exception:
            traceback.print_exc()
            return None

    async def navegar_imagem_historia(self, interaction: discord.Interaction, historia_id: str, direcao: int):
        historia = carregar_historia(historia_id)

        if not historia:
                await interaction.response.send_message("História não encontrada.", ephemeral=True)
                return

        imagens = obter_imagens_historia(historia)
        if len(imagens) <= 1:
                await interaction.response.send_message("Esta história tem apenas uma imagem.", ephemeral=True)
                return

        indice_inicial = 1 if direcao > 0 else 0
        indice_inicial = min(max(0, indice_inicial), len(imagens) - 1)

        embed = criar_embed_historia(historia, indice_imagem=indice_inicial)
        view = HistoriaImagemView(historia_id, indice_inicial)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def atualizar_mensagem_historia(self, historia_id: str, interaction: discord.Interaction | None = None):
        historia = carregar_historia(historia_id)

        if not historia:
            return

        embed = criar_embed_historia(historia)
        view = HistoriaInteracoesView(self, historia_id)

        try:
            mensagem_interacao = getattr(interaction, "message", None) if interaction is not None else None

            if mensagem_interacao is not None:
                await mensagem_interacao.edit(embed=embed, view=view)
                return

            mensagem = await self.obter_mensagem_historia(historia)

            if mensagem is not None:
                await mensagem.edit(embed=embed, view=view)
        except Exception:
            traceback.print_exc()

    async def atualizar_todas_historias_salvas(self) -> tuple[int, int]:
        atualizadas = 0
        falhas = 0

        for historia in listar_historias_salvas():
            historia_id = str(historia.get("historia_id") or historia.get("message_id") or "")
            mensagem = await self.obter_mensagem_historia(historia)

            if mensagem is None:
                falhas += 1
                continue

            try:
                await mensagem.edit(
                    embed=criar_embed_historia(historia),
                    view=HistoriaInteracoesView(self, historia_id),
                )
                atualizadas += 1
            except Exception:
                traceback.print_exc()
                falhas += 1

        return atualizadas, falhas

    async def publicar_historia(
        self,
        canal_fallback,
        titulo: str,
        data_historia: str,
        imagens: list[discord.Attachment],
        autor,
        cargo_mencao: discord.Role | None = None,
    ) -> bool:
        canal = await self.obter_canal_destino(canal_fallback)

        if canal is None:
            return False

        try:
            imagens = [imagem for imagem in imagens[:MAX_IMAGENS_HISTORIA] if anexo_eh_imagem(imagem)]
            if not imagens:
                return False

            canal_cache = await self.obter_canal_cache_imagens(canal)
            if canal_cache is None:
                return False

            arquivos = []
            for indice, imagem in enumerate(imagens, start=1):
                nome_arquivo = nome_arquivo_seguro(imagem.filename, indice)
                arquivos.append(await imagem.to_file(filename=nome_arquivo))

            mensagem_cache = await canal_cache.send(
                content=f"Imagens da história: {titulo}",
                files=arquivos,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            image_urls = [attachment.url for attachment in mensagem_cache.attachments]
            if not image_urls:
                return False

            embed_inicial = criar_embed_historia(
                {
                    "titulo": titulo,
                    "data_historia": data_historia,
                    "image_url": image_urls[0],
                    "image_urls": image_urls,
                    "current_image_index": 0,
                    "likes": [],
                    "laughs": [],
                    "comentarios": [],
                }
            )

            conteudo = cargo_mencao.mention if cargo_mencao is not None else None
            mensagem = await canal.send(
                content=conteudo,
                embed=embed_inicial,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            historia_id = str(mensagem.id)

            historia = {
                "historia_id": historia_id,
                "titulo": titulo,
                "data_historia": data_historia,
                "message_id": mensagem.id,
                "channel_id": mensagem.channel.id,
                "asset_message_id": mensagem_cache.id,
                "asset_channel_id": mensagem_cache.channel.id,
                "image_url": image_urls[0],
                "image_urls": image_urls,
                "current_image_index": 0,
                "criada_por_id": autor.id,
                "criada_por_nome": str(autor),
                "created_at": agora_br().isoformat(),
                "likes": [],
                "laughs": [],
                "comentarios": [],
                "cargo_mencao_id": cargo_mencao.id if cargo_mencao is not None else None,
                "cargo_mencao_nome": cargo_mencao.name if cargo_mencao is not None else "",
            }

            async with self._lock:
                dados = carregar_dados_historias()
                dados.setdefault("historias", {})[historia_id] = historia
                salvar_dados_historias(dados)

            view = HistoriaInteracoesView(self, historia_id)
            self.bot.add_view(view, message_id=mensagem.id)
            await mensagem.edit(embed=criar_embed_historia(historia), view=view)

        except Exception:
            traceback.print_exc()
            return False

        return True

    async def alternar_interacao(
        self,
        interaction: discord.Interaction,
        historia_id: str,
        chave: str,
        mensagem_adicionou: str,
        mensagem_removeu: str,
    ):
        try:
            await interaction.response.defer(ephemeral=True, thinking=False)
            user_id = int(interaction.user.id)
            mensagem = mensagem_adicionou

            async with self._lock:
                dados = carregar_dados_historias()
                historia = dados.setdefault("historias", {}).get(str(historia_id))

                if not historia:
                    await interaction.followup.send("História não encontrada.", ephemeral=True)
                    return

                lista = normalizar_ids(historia.get(chave, []))

                if user_id in lista:
                    lista.remove(user_id)
                    mensagem = mensagem_removeu
                else:
                    lista.append(user_id)

                historia[chave] = lista
                dados["historias"][str(historia_id)] = historia
                salvar_dados_historias(dados)

            await self.atualizar_mensagem_historia(historia_id, interaction=interaction)
            await interaction.followup.send(mensagem, ephemeral=True)
        except Exception:
            traceback.print_exc()

            if interaction.response.is_done():
                await interaction.followup.send("Ocorreu um erro ao interagir com esta história.", ephemeral=True)
            else:
                await interaction.response.send_message("Ocorreu um erro ao interagir com esta história.", ephemeral=True)

    async def registrar_comentario(self, interaction: discord.Interaction, historia_id: str, comentario: str):
        registro = {
            "user_id": interaction.user.id,
            "user_name": getattr(interaction.user, "display_name", str(interaction.user)),
            "comentario": comentario,
            "created_at": agora_br().isoformat(),
        }

        async with self._lock:
            dados = carregar_dados_historias()
            historia = dados.setdefault("historias", {}).get(str(historia_id))

            if not historia:
                return

            comentarios = historia.setdefault("comentarios", [])
            comentarios.append(registro)
            dados["historias"][str(historia_id)] = historia
            salvar_dados_historias(dados)

        await self.atualizar_mensagem_historia(historia_id, interaction=interaction)

    @commands.command(name="historia")
    async def historia_prefixo(self, ctx: commands.Context, *, argumento: str = ""):
        if not membro_pode_publicar_historias(ctx.author):
            await ctx.send("❌ Apenas a staff pode publicar histórias.")
            return

        titulo, data_historia = extrair_titulo_data(argumento)

        if not titulo:
            await ctx.send(
                "❌ Informe um título para a história.\n\n"
                "Exemplo:\n"
                "!historia \"História de Hoje — FDN\" \"22/05/2026\""
            )
            return

        imagens = imagens_anexadas(ctx.message.attachments)

        if not imagens:
            await ctx.send(
                "❌ Envie uma imagem junto com o comando.\n\n"
                "Exemplo:\n"
                "!historia \"História de Hoje — FDN\" \"22/05/2026\"\n"
                "com a imagem anexada na mesma mensagem."
            )
            return

        cargo_mencao = ctx.message.role_mentions[0] if ctx.message.role_mentions else None
        publicado = await self.publicar_historia(
            ctx.channel,
            titulo,
            data_historia,
            imagens,
            ctx.author,
            cargo_mencao=cargo_mencao,
        )

        if not publicado:
            await ctx.send(
                "❌ Não foi possível publicar a história. "
                "Verifique o canal configurado e as permissões do bot."
            )
            return

        await ctx.send("✅ História publicada com sucesso.")

    @commands.command(name="atualizarhistorias")
    async def atualizar_historias_prefixo(self, ctx: commands.Context):
        if not membro_pode_publicar_historias(ctx.author):
            await ctx.send("❌ Apenas a staff pode atualizar histórias.")
            return

        mensagem = await ctx.send("🔄 Atualizando histórias...")
        atualizadas, falhas = await self.atualizar_todas_historias_salvas()
        await mensagem.edit(
            content=(
                f"✅ Histórias atualizadas: {atualizadas}.\n"
                f"⚠️ Falhas ou mensagens não encontradas: {falhas}."
            )
        )

    @app_commands.command(
        name="historia",
        description="Publica uma história com imagem no canal configurado.",
    )
    @app_commands.describe(
        titulo="Título da história.",
        imagem="Imagem da história.",
        imagem2="Imagem 2 da história.",
        imagem3="Imagem 3 da história.",
        imagem4="Imagem 4 da história.",
        imagem5="Imagem 5 da história.",
        imagem6="Imagem 6 da história.",
        imagem7="Imagem 7 da história.",
        imagem8="Imagem 8 da história.",
        imagem9="Imagem 9 da história.",
        imagem10="Imagem 10 da história.",
        data="Data da história. Se ficar vazio, usa a data atual.",
        cargo="Cargo que será mencionado na história.",
    )
    async def historia_barra(
        self,
        interaction: discord.Interaction,
        titulo: str,
        imagem: discord.Attachment,
        imagem2: discord.Attachment | None = None,
        imagem3: discord.Attachment | None = None,
        imagem4: discord.Attachment | None = None,
        imagem5: discord.Attachment | None = None,
        imagem6: discord.Attachment | None = None,
        imagem7: discord.Attachment | None = None,
        imagem8: discord.Attachment | None = None,
        imagem9: discord.Attachment | None = None,
        imagem10: discord.Attachment | None = None,
        data: str | None = None,
        cargo: discord.Role | None = None,
    ):
        if not membro_pode_publicar_historias(interaction.user):
            await interaction.response.send_message(
                "❌ Apenas a staff pode publicar histórias.",
                ephemeral=True,
            )
            return

        titulo = titulo.strip()
        data_historia = (data or "").strip() or data_atual_br()
        imagens = [
            item
            for item in (imagem, imagem2, imagem3, imagem4, imagem5, imagem6, imagem7, imagem8, imagem9, imagem10)
            if item is not None
        ]

        if any(not anexo_eh_imagem(item) for item in imagens):
            await interaction.response.send_message(
                "❌ Envie imagens nos formatos .png, .jpg, .jpeg, .webp ou .gif.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        publicado = await self.publicar_historia(
            interaction.channel,
            titulo,
            data_historia,
            imagens,
            interaction.user,
            cargo_mencao=cargo,
        )

        if not publicado:
            await interaction.followup.send(
                "❌ Não foi possível publicar a história. "
                "Verifique o canal configurado e as permissões do bot.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "✅ História publicada com sucesso.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Historias(bot))
