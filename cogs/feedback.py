from datetime import datetime, timezone

import discord
from discord.ext import commands

from config import CANAL_FEEDBACK_ID
from services.logs import enviar_log_bot
from utils.discord_helpers import criar_embed_tags, membro_eh_staff
from utils.text_utils import estrelas_texto


class FeedbackModal(discord.ui.Modal):
    def __init__(
        self,
        membro_avaliador,
        nota,
        canal_ticket_id,
        staff_id,
        mensagem_feedback_id=None,
        canal_mensagem_id=None,
        ticket_label=None,
    ):
        super().__init__(title=f"Feedback - {estrelas_texto(nota)}")
        self.membro_avaliador = membro_avaliador
        self.nota = nota
        self.canal_ticket_id = canal_ticket_id
        self.staff_id = staff_id
        self.mensagem_feedback_id = mensagem_feedback_id
        self.canal_mensagem_id = canal_mensagem_id if canal_mensagem_id is not None else canal_ticket_id
        self.ticket_label = ticket_label or f"<#{canal_ticket_id}>"

        self.pergunta_1 = discord.ui.TextInput(
            label="Como foi seu atendimento?",
            placeholder="Ex.: foi rapido, atencioso, resolveu meu problema...",
            required=True,
            max_length=300
        )
        self.pergunta_2 = discord.ui.TextInput(
            label="Quer deixar um comentario extra?",
            placeholder="Opcional",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.pergunta_1)
        self.add_item(self.pergunta_2)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.membro_avaliador.id:
            await interaction.response.send_message("So a pessoa marcada para avaliar pode enviar esse feedback.", ephemeral=True)
            return

        canal_feedback = interaction.client.get_channel(CANAL_FEEDBACK_ID)
        if not canal_feedback:
            try:
                canal_feedback = await interaction.client.fetch_channel(CANAL_FEEDBACK_ID)
            except Exception:
                await interaction.response.send_message("Nao consegui encontrar o canal de feedback configurado.", ephemeral=True)
                return

        staff_mention = f"<@{self.staff_id}>"
        canal_ticket_mention = self.ticket_label

        embed = discord.Embed(
            title="Novo feedback de atendimento",
            color=discord.Color.from_rgb(69, 211, 232),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name="Raven Feedback")
        embed.add_field(name="Usuario", value=self.membro_avaliador.mention, inline=False)
        embed.add_field(name="Nota", value=estrelas_texto(self.nota), inline=False)
        embed.add_field(name="Atendido por", value=staff_mention, inline=False)
        embed.add_field(name="Ticket", value=canal_ticket_mention, inline=False)
        embed.add_field(name="Como foi o atendimento?", value=self.pergunta_1.value, inline=False)

        comentario_extra = self.pergunta_2.value.strip() if self.pergunta_2.value else "Nao deixou comentario extra."
        embed.add_field(name="Comentario extra", value=comentario_extra, inline=False)
        await canal_feedback.send(embed=embed)

        await interaction.response.send_message("Feedback enviado com sucesso. Obrigado!", ephemeral=True)
        await self.apagar_mensagem_feedback(interaction)

        try:
            await enviar_log_bot(
                "Feedback enviado",
                (
                    f"**Usuario:** {self.membro_avaliador.mention}\n"
                    f"**Nota:** {estrelas_texto(self.nota)}\n"
                    f"**Atendido por:** {staff_mention}\n"
                    f"**Ticket:** {canal_ticket_mention}"
                )
            )
        except Exception:
            pass

    async def apagar_mensagem_feedback(self, interaction: discord.Interaction):
        if not self.mensagem_feedback_id or not self.canal_mensagem_id:
            return

        try:
            canal_ticket = interaction.client.get_channel(self.canal_mensagem_id)
            if not canal_ticket:
                canal_ticket = await interaction.client.fetch_channel(self.canal_mensagem_id)

            mensagem_feedback = await canal_ticket.fetch_message(self.mensagem_feedback_id)
            await mensagem_feedback.delete()
        except Exception:
            return


class FeedbackStarsView(discord.ui.View):
    def __init__(
        self,
        membro_avaliador,
        staff_id,
        canal_ticket_id,
        mensagem_feedback_id=None,
        canal_mensagem_id=None,
        ticket_label=None,
    ):
        super().__init__(timeout=1800)
        self.membro_avaliador = membro_avaliador
        self.staff_id = staff_id
        self.canal_ticket_id = canal_ticket_id
        self.mensagem_feedback_id = mensagem_feedback_id
        self.canal_mensagem_id = canal_mensagem_id if canal_mensagem_id is not None else canal_ticket_id
        self.ticket_label = ticket_label or f"<#{canal_ticket_id}>"
        self.estrela_1.label = estrelas_texto(1)
        self.estrela_2.label = estrelas_texto(2)
        self.estrela_3.label = estrelas_texto(3)
        self.estrela_4.label = estrelas_texto(4)
        self.estrela_5.label = estrelas_texto(5)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.membro_avaliador.id:
            await interaction.response.send_message("Esse feedback e so para a pessoa marcada.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary)
    async def estrela_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            FeedbackModal(
                self.membro_avaliador,
                1,
                self.canal_ticket_id,
                self.staff_id,
                self.mensagem_feedback_id,
                self.canal_mensagem_id,
                self.ticket_label,
            )
        )

    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary)
    async def estrela_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            FeedbackModal(
                self.membro_avaliador,
                2,
                self.canal_ticket_id,
                self.staff_id,
                self.mensagem_feedback_id,
                self.canal_mensagem_id,
                self.ticket_label,
            )
        )

    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary)
    async def estrela_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            FeedbackModal(
                self.membro_avaliador,
                3,
                self.canal_ticket_id,
                self.staff_id,
                self.mensagem_feedback_id,
                self.canal_mensagem_id,
                self.ticket_label,
            )
        )

    @discord.ui.button(label="4", style=discord.ButtonStyle.secondary)
    async def estrela_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            FeedbackModal(
                self.membro_avaliador,
                4,
                self.canal_ticket_id,
                self.staff_id,
                self.mensagem_feedback_id,
                self.canal_mensagem_id,
                self.ticket_label,
            )
        )

    @discord.ui.button(label="5", style=discord.ButtonStyle.success)
    async def estrela_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            FeedbackModal(
                self.membro_avaliador,
                5,
                self.canal_ticket_id,
                self.staff_id,
                self.mensagem_feedback_id,
                self.canal_mensagem_id,
                self.ticket_label,
            )
        )


class FeedbackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def criar_embed_feedback_manual(membro, atendente):
        embed = discord.Embed(
            title="Como foi seu atendimento?",
            description=(
                f"{membro.mention}, seu atendimento foi finalizado.\n\n"
                "Escolha uma nota nas estrelas abaixo e depois responda o formulario."
            ),
            color=discord.Color.from_rgb(69, 211, 232)
        )
        embed.set_author(name="Raven Feedback")
        embed.add_field(name="Atendido por", value=atendente.mention, inline=False)
        embed.add_field(name="Observacao", value="So a pessoa marcada consegue enviar esse feedback.", inline=False)
        return embed

    @commands.command(name="feedback", aliases=["feedbackpedir", "feedback_ticket"])
    async def feedback(self, ctx, membro: discord.Member = None, atendente: discord.Member = None):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("Sem permissao", "Voce nao tem permissao pra usar esse comando."))
            return

        if membro is None:
            await ctx.send(embed=criar_embed_tags("Pedir feedback", "Use assim: `!feedback @membro @atendente` ou `!feedback ID_MEMBRO ID_ATENDENTE`"))
            return

        atendente = atendente or ctx.author

        embed = self.criar_embed_feedback_manual(membro, atendente)
        view = FeedbackStarsView(
            membro_avaliador=membro,
            staff_id=atendente.id,
            canal_ticket_id=ctx.channel.id,
            canal_mensagem_id=ctx.channel.id,
            ticket_label=ctx.channel.mention,
        )
        mensagem_feedback = await ctx.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions(users=True))
        view.mensagem_feedback_id = mensagem_feedback.id

        await enviar_log_bot(
            "Pedido de feedback enviado",
            (
                f"**Staff:** {ctx.author.mention}\n"
                f"**Usuario:** {membro.mention}\n"
                f"**Atendido por:** {atendente.mention}\n"
                f"**Ticket:** {ctx.channel.mention}"
            )
        )

    @commands.command(name="feedbackpv")
    async def feedbackpv(self, ctx, membro: discord.Member = None, atendente: discord.Member = None):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("Sem permissao", "Voce nao tem permissao pra usar esse comando."))
            return

        if membro is None or atendente is None:
            await ctx.send(embed=criar_embed_tags("Pedir feedback", "Use assim: `!feedbackpv @membro @atendente` ou `!feedbackpv ID_MEMBRO ID_ATENDENTE`"))
            return

        embed = self.criar_embed_feedback_manual(membro, atendente)
        view = FeedbackStarsView(
            membro_avaliador=membro,
            staff_id=atendente.id,
            canal_ticket_id=ctx.channel.id,
            canal_mensagem_id=None,
            ticket_label=f"Feedback manual enviado por PV | canal de origem: {ctx.channel.mention}",
        )

        try:
            await membro.send(embed=embed, view=view)
        except discord.Forbidden:
            await ctx.send(embed=criar_embed_tags("DM fechada", "Nao consegui enviar o feedback por PV para esse membro."))
            return
        except discord.HTTPException:
            await ctx.send(embed=criar_embed_tags("Erro ao enviar", "O Discord recusou o envio do feedback por PV. Tente novamente."))
            return

        await ctx.send(
            embed=criar_embed_tags(
                "Feedback enviado",
                f"Enviei a avaliação por PV para {membro.mention} com atendimento atribuído a {atendente.mention}.",
            )
        )

        await enviar_log_bot(
            "Pedido de feedback por PV enviado",
            (
                f"**Staff:** {ctx.author.mention}\n"
                f"**Usuario:** {membro.mention}\n"
                f"**Atendido por:** {atendente.mention}\n"
                f"**Canal de origem:** {ctx.channel.mention}"
            )
        )


async def setup(bot):
    await bot.add_cog(FeedbackCog(bot))
