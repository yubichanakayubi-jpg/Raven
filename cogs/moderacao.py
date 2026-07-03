import discord
from discord import app_commands
from discord.ext import commands

from services.logs import enviar_log_bot
from utils.discord_helpers import criar_embed_tags, limpar_mensagens_do_canal, membro_eh_staff


EXPULSAR_ALLOWED_ROLE_IDS = {
    1461789051047772293,  # Fundadora
    1463388653307957362,  # Lider
    1461789052427567145,  # Sub
}


def _limitar_texto(valor, limite):
    texto = str(valor or "").strip()
    if len(texto) <= limite:
        return texto
    return texto[: max(0, limite - 3)] + "..."


async def _responder_slash(interaction, mensagem):
    if interaction.response.is_done():
        await interaction.followup.send(mensagem, ephemeral=True)
    else:
        await interaction.response.send_message(mensagem, ephemeral=True)


async def _responder_limpar_privado(ctx, *, content=None, embed=None, delete_after=10):
    if getattr(ctx, "interaction", None) is not None:
        return await ctx.send(content, embed=embed)

    try:
        return await ctx.author.send(content, embed=embed)
    except Exception:
        return await ctx.send(content, embed=embed, delete_after=delete_after)


def _membro_pode_expulsar(membro):
    if not hasattr(membro, "roles"):
        return False

    return any(cargo.id in EXPULSAR_ALLOWED_ROLE_IDS for cargo in membro.roles)


class ModeracaoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="expulsar", description="Expulsa um membro e envia o motivo por DM.")
    @app_commands.describe(
        membro="Membro que sera expulso.",
        motivo="Motivo da expulsao.",
        arquivo="Arquivo opcional para enviar na DM do membro.",
    )
    @app_commands.guild_only()
    async def slash_expulsar(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str,
        arquivo: discord.Attachment | None = None,
    ):
        guild = interaction.guild
        autor = interaction.user
        motivo = (motivo or "").strip()

        if guild is None or not isinstance(autor, discord.Member):
            await _responder_slash(interaction, "Esse comando so pode ser usado em servidor.")
            return

        if not _membro_pode_expulsar(autor):
            await _responder_slash(interaction, "Apenas Fundadora, Lider ou Sub podem usar /expulsar.")
            return

        if not motivo:
            await _responder_slash(interaction, "Informe o motivo da expulsao.")
            return

        if membro.id == autor.id:
            await _responder_slash(interaction, "Voce nao pode expulsar voce mesmo.")
            return

        if self.bot.user and membro.id == self.bot.user.id:
            await _responder_slash(interaction, "Eu nao posso expulsar a mim mesmo.")
            return

        if membro.id == guild.owner_id:
            await _responder_slash(interaction, "Nao posso expulsar o dono do servidor.")
            return

        bot_member = guild.me
        if bot_member is None and self.bot.user is not None:
            bot_member = guild.get_member(self.bot.user.id)

        if bot_member is None:
            await _responder_slash(interaction, "Nao consegui confirmar meu cargo no servidor.")
            return

        if not bot_member.guild_permissions.kick_members:
            await _responder_slash(interaction, "Eu nao tenho permissao de expulsar membros.")
            return

        if guild.owner_id != autor.id and membro.top_role >= autor.top_role:
            await _responder_slash(interaction, "Voce nao pode expulsar alguem com cargo igual ou acima do seu.")
            return

        if membro.top_role >= bot_member.top_role:
            await _responder_slash(interaction, "Meu cargo precisa ficar acima do cargo do membro para expulsar.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        embed_dm = discord.Embed(
            title=f"Voce foi expulso de {guild.name}",
            description="A staff informou o motivo abaixo.",
            color=discord.Color.red(),
        )
        embed_dm.add_field(name="Motivo", value=_limitar_texto(motivo, 1024), inline=False)
        embed_dm.set_footer(text="FDN - Moderacao")

        arquivo_dm = None
        anexo_enviado = False
        dm_enviada = False
        observacao_dm = ""

        if arquivo is not None:
            try:
                arquivo_dm = await arquivo.to_file()
            except Exception as erro:
                observacao_dm = "Nao consegui baixar o arquivo para enviar na DM."
                print(
                    f"[EXPULSAR] Erro ao baixar anexo | guild={guild.id} | "
                    f"membro={membro.id} | arquivo={getattr(arquivo, 'filename', 'desconhecido')} | "
                    f"erro={repr(erro)}"
                )

        try:
            kwargs = {"embed": embed_dm}
            if arquivo_dm is not None:
                kwargs["file"] = arquivo_dm
            await membro.send(**kwargs)
            dm_enviada = True
            anexo_enviado = arquivo_dm is not None
        except discord.Forbidden as erro:
            observacao_dm = "Nao consegui enviar DM. O membro pode estar com a DM fechada."
            print(f"[EXPULSAR] Forbidden ao enviar DM | guild={guild.id} | membro={membro.id} | erro={repr(erro)}")
        except discord.HTTPException as erro:
            if arquivo_dm is not None:
                try:
                    await membro.send(embed=embed_dm)
                    dm_enviada = True
                    observacao_dm = "A DM foi enviada, mas o arquivo nao foi anexado."
                except Exception as erro_sem_anexo:
                    observacao_dm = "Nao consegui enviar DM para o membro."
                    print(
                        f"[EXPULSAR] Erro ao enviar DM sem anexo | guild={guild.id} | "
                        f"membro={membro.id} | erro={repr(erro_sem_anexo)}"
                    )
            else:
                observacao_dm = "Nao consegui enviar DM para o membro."
            print(f"[EXPULSAR] HTTPException ao enviar DM | guild={guild.id} | membro={membro.id} | erro={repr(erro)}")
        except Exception as erro:
            observacao_dm = "Nao consegui enviar DM para o membro."
            print(f"[EXPULSAR] Erro ao enviar DM | guild={guild.id} | membro={membro.id} | erro={repr(erro)}")

        razao_auditoria = _limitar_texto(
            f"{motivo} | Expulso por {autor} ({autor.id})",
            512,
        )

        try:
            await guild.kick(membro, reason=razao_auditoria)
        except discord.Forbidden as erro:
            print(f"[EXPULSAR] Forbidden ao expulsar | guild={guild.id} | membro={membro.id} | erro={repr(erro)}")
            await _responder_slash(interaction, "Nao consegui expulsar. Verifique permissao e hierarquia de cargos.")
            return
        except discord.HTTPException as erro:
            print(f"[EXPULSAR] HTTPException ao expulsar | guild={guild.id} | membro={membro.id} | erro={repr(erro)}")
            await _responder_slash(interaction, f"Nao consegui expulsar por erro do Discord (HTTP {erro.status}).")
            return

        try:
            await enviar_log_bot(
                "Expulsao aplicada",
                (
                    f"**Membro:** {membro.mention} (`{membro.id}`)\n"
                    f"**Staff:** {autor.mention} (`{autor.id}`)\n"
                    f"**Motivo:** {_limitar_texto(motivo, 1500)}\n"
                    f"**DM enviada:** {'Sim' if dm_enviada else 'Nao'}\n"
                    f"**Arquivo enviado:** {'Sim' if anexo_enviado else 'Nao'}"
                ),
            )
        except Exception as erro:
            print(f"[EXPULSAR] Erro ao enviar log | guild={guild.id} | membro={membro.id} | erro={repr(erro)}")

        resposta = (
            f"Expulsao aplicada em {membro.mention} (`{membro.id}`).\n"
            f"DM enviada: {'Sim' if dm_enviada else 'Nao'}.\n"
            f"Arquivo enviado: {'Sim' if anexo_enviado else 'Nao'}."
        )
        if observacao_dm:
            resposta += f"\nObs: {observacao_dm}"

        await _responder_slash(interaction, resposta)

    @commands.command(name="limpar", aliases=["clear"])
    async def limpar(self, ctx, quantidade=None):
        if not membro_eh_staff(ctx.author):
            await _responder_limpar_privado(
                ctx,
                embed=criar_embed_tags("Sem permissao", "Voce nao tem permissao pra usar esse comando."),
            )
            return

        if quantidade is None:
            await _responder_limpar_privado(
                ctx,
                embed=criar_embed_tags("Limpar chat", "Use assim: `!limpar 50` ou `/limpar quantidade:50`"),
            )
            return

        try:
            quantidade = int(quantidade)
        except ValueError:
            await _responder_limpar_privado(
                ctx,
                embed=criar_embed_tags("Quantidade invalida", "A quantidade precisa ser um numero inteiro."),
            )
            return

        if quantidade <= 0:
            await _responder_limpar_privado(
                ctx,
                embed=criar_embed_tags("Quantidade invalida", "A quantidade precisa ser maior que zero."),
            )
            return

        async def avisar_limpeza_lenta(total_antigas, total_encontradas):
            await _responder_limpar_privado(
                ctx,
                embed=criar_embed_tags(
                    "Limpeza pode demorar",
                    (
                        f"Encontrei **{total_antigas}** mensagem(ns) antiga(s) entre as **{total_encontradas}** selecionadas.\n"
                        "O Discord limita esse tipo de exclusao, entao a limpeza pode ficar um pouco mais lenta."
                    ),
                ),
                delete_after=8,
            )

        detalhes_limpeza = await limpar_mensagens_do_canal(
            ctx.channel,
            quantidade,
            ignorar_message_id=ctx.message.id,
            aviso_callback=avisar_limpeza_lenta,
            retornar_detalhes=True
        )
        removidas = detalhes_limpeza["removidas"]

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await _responder_limpar_privado(
            ctx,
            embed=criar_embed_tags(
                "Chat limpo",
                f"Removi **{removidas}** mensagem(ns) de <#{ctx.channel.id}>.",
            ),
            delete_after=8,
        )

        await enviar_log_bot(
            "🧹 Limpeza manual de chat",
            (
                f"**Staff:** {ctx.author.mention}\n"
                f"**Canal:** {ctx.channel.mention}\n"
                f"**Quantidade pedida:** {quantidade}\n"
                f"**Quantidade removida:** {removidas}"
            )
        )


async def setup(bot):
    await bot.add_cog(ModeracaoCog(bot))
