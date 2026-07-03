from discord.ext import commands

from services.d1 import salvar_frase_custom_d1
from services.logs import enviar_log_bot
from utils.discord_helpers import criar_embed_tags, listar_nomes_gatilhos, membro_eh_staff, obter_gatilho


class GatilhosCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="gatilho", aliases=["gatilhos"])
    async def gatilho(self, ctx, acao=None, *args):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if acao is None or acao.lower() == "listar":
            nomes = listar_nomes_gatilhos()
            if not nomes:
                await ctx.send(embed=criar_embed_tags("📋 Gatilhos", "Não há gatilhos cadastrados."))
                return

            linhas = [f"• `{nome}`" for nome in nomes]
            partes = [linhas[i:i + 20] for i in range(0, len(linhas), 20)]
            for i, parte in enumerate(partes, start=1):
                titulo = "📋 Gatilhos disponíveis"
                if len(partes) > 1:
                    titulo += f" ({i}/{len(partes)})"
                await ctx.send(embed=criar_embed_tags(titulo, "\n".join(parte)))
            return

        if acao.lower() == "info":
            if not args:
                await ctx.send(embed=criar_embed_tags("📌 Info do gatilho", "Use assim: `!gatilho info nome_do_gatilho`"))
                return

            nome = args[0].lower()
            gatilho_obj = obter_gatilho(nome)
            if not gatilho_obj:
                await ctx.send(embed=criar_embed_tags("❌ Gatilho não encontrado", f"O gatilho `{nome}` não existe."))
                return

            palavras = ", ".join([f"`{p}`" for p in gatilho_obj.get("palavras", [])]) or "Nenhuma"
            total_respostas = len(gatilho_obj.get("respostas", []))
            exato = "Sim" if gatilho_obj.get("exato", False) else "Não"
            apenas_staff = "Sim" if gatilho_obj.get("apenas_staff", False) else "Não"
            sem_cooldown = "Sim" if gatilho_obj.get("sem_cooldown", False) else "Não"

            descricao = (
                f"**Nome:** `{nome}`\n"
                f"**Palavras:** {palavras}\n"
                f"**Total de respostas:** {total_respostas}\n"
                f"**Exato:** {exato}\n"
                f"**Apenas staff:** {apenas_staff}\n"
                f"**Sem cooldown:** {sem_cooldown}"
            )
            await ctx.send(embed=criar_embed_tags("📌 Info do gatilho", descricao))
            return

        await ctx.send(embed=criar_embed_tags("❌ Ação inválida", "Use `!gatilho listar` ou `!gatilho info nome_do_gatilho`."))

    @commands.command(name="frase", aliases=["frases"])
    async def frase(self, ctx, acao=None, *args):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if acao is None:
            await ctx.send(embed=criar_embed_tags(
                "📘 Comandos de frases",
                (
                    "`!frase listar nome_do_gatilho` — lista as frases do gatilho\n"
                    "`!frase add nome_do_gatilho texto...` — adiciona uma nova frase\n"
                    "`!frase remover nome_do_gatilho numero` — remove a frase pelo número"
                )
            ))
            return

        acao = acao.lower()

        if acao == "listar":
            if not args:
                await ctx.send(embed=criar_embed_tags("📋 Listar frases", "Use assim: `!frase listar nome_do_gatilho`"))
                return

            nome = args[0].lower()
            gatilho_obj = obter_gatilho(nome)
            if not gatilho_obj:
                await ctx.send(embed=criar_embed_tags("❌ Gatilho não encontrado", f"O gatilho `{nome}` não existe."))
                return

            respostas = gatilho_obj.get("respostas", [])
            if not respostas:
                await ctx.send(embed=criar_embed_tags("📋 Frases do gatilho", f"O gatilho `{nome}` não tem frases cadastradas."))
                return

            linhas = [f"`{i}.` {frase}" for i, frase in enumerate(respostas, start=1)]
            partes = [linhas[i:i + 10] for i in range(0, len(linhas), 10)]
            for i, parte in enumerate(partes, start=1):
                titulo = f"📋 Frases de `{nome}`"
                if len(partes) > 1:
                    titulo += f" ({i}/{len(partes)})"
                await ctx.send(embed=criar_embed_tags(titulo, "\n".join(parte)))
            return

        if acao == "add":
            if len(args) < 2:
                await ctx.send(embed=criar_embed_tags("➕ Adicionar frase", "Use assim: `!frase add nome_do_gatilho texto_da_frase`"))
                return

            nome = args[0].lower()
            nova_frase = " ".join(args[1:]).strip()
            gatilho_obj = obter_gatilho(nome)
            if not gatilho_obj:
                await ctx.send(embed=criar_embed_tags("❌ Gatilho não encontrado", f"O gatilho `{nome}` não existe."))
                return
            if not nova_frase:
                await ctx.send(embed=criar_embed_tags("❌ Frase inválida", "A frase não pode ficar vazia."))
                return

            respostas = gatilho_obj.setdefault("respostas", [])
            if nova_frase in respostas:
                await ctx.send(embed=criar_embed_tags("⚠️ Frase já existe", f"Essa frase já está cadastrada no gatilho `{nome}`."))
                return

            respostas.append(nova_frase)
            await salvar_frase_custom_d1(nome, nova_frase, "add")
            await ctx.send(embed=criar_embed_tags(
                "✅ Frase adicionada",
                f"**Gatilho:** `{nome}`\n**Nova frase:** {nova_frase}\n**Total agora:** {len(respostas)}"
            ))
            await enviar_log_bot(
                "➕ Frase adicionada em gatilho",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Gatilho:** `{nome}`\n"
                    f"**Frase:** {nova_frase}\n"
                    f"**Canal:** {ctx.channel.mention}"
                )
            )
            return

        if acao == "remover":
            if len(args) < 2:
                await ctx.send(embed=criar_embed_tags("➖ Remover frase", "Use assim: `!frase remover nome_do_gatilho numero`"))
                return

            nome = args[0].lower()
            gatilho_obj = obter_gatilho(nome)
            if not gatilho_obj:
                await ctx.send(embed=criar_embed_tags("❌ Gatilho não encontrado", f"O gatilho `{nome}` não existe."))
                return

            try:
                indice = int(args[1])
            except ValueError:
                await ctx.send(embed=criar_embed_tags("❌ Número inválido", "O número da frase precisa ser um valor inteiro."))
                return

            respostas = gatilho_obj.get("respostas", [])
            if indice < 1 or indice > len(respostas):
                await ctx.send(embed=criar_embed_tags("❌ Número inválido", f"O gatilho `{nome}` tem {len(respostas)} frase(s)."))
                return

            removida = respostas.pop(indice - 1)
            await salvar_frase_custom_d1(nome, removida, "remove")
            await ctx.send(embed=criar_embed_tags(
                "✅ Frase removida",
                f"**Gatilho:** `{nome}`\n**Frase removida:** {removida}\n**Total agora:** {len(respostas)}"
            ))
            await enviar_log_bot(
                "➖ Frase removida de gatilho",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Gatilho:** `{nome}`\n"
                    f"**Frase removida:** {removida}\n"
                    f"**Canal:** {ctx.channel.mention}"
                )
            )
            return

        await ctx.send(embed=criar_embed_tags(
            "❌ Ação inválida",
            "Use `!frase listar nome_do_gatilho`, `!frase add nome_do_gatilho texto...` ou `!frase remover nome_do_gatilho numero`."
        ))


async def setup(bot):
    await bot.add_cog(GatilhosCog(bot))
