import json
import os
from datetime import datetime

import discord
from discord.ext import commands, tasks

from config import (
    ADVERTENCIA_CHANNEL_ID,
    ARQUIVO_ANIVERSARIOS,
    CANAIS_REACAO,
    CANAL_ANIVERSARIO_ID,
    CANAL_GERAL_ID,
    CANAL_RECRUTADORES_ID,
    CARGO_ANIVERSARIANTE_ID,
    CARGO_AVISO_REACAO_ID,
    CARGO_MEMBRO_ID,
    FUSO_HORARIO,
    FRASES_MENCAO_VAZIA,
    FRASES_RESPOSTA_MANUAL,
)
from services.boas_vindas import enviar_boas_vindas_no_geral
from services.logs import enviar_log_bot
from services.server_config import carregar_configs_servidores, salvar_configs_servidores
from services.server_config import obter_valor_config
from utils.discord_helpers import (
    buscar_mensagem_por_id_na_guild,
    criar_embed_tags,
    gerar_mensagem_reacao,
    membro_eh_lideranca,
    membro_eh_staff,
    obter_gatilho,
    procurar_membro_por_texto,
)
from utils.text_utils import escolher_resposta_gatilho


class StaffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verificador_aniversarios.start()

    def cog_unload(self):
        self.verificador_aniversarios.cancel()

    def carregar_aniversarios(self):
        if not os.path.exists(ARQUIVO_ANIVERSARIOS):
            return {"aniversarios": {}, "avisos_enviados": {}}

        try:
            with open(ARQUIVO_ANIVERSARIOS, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
        except Exception:
            return {"aniversarios": {}, "avisos_enviados": {}}

        if not isinstance(dados, dict):
            return {"aniversarios": {}, "avisos_enviados": {}}

        dados.setdefault("aniversarios", {})
        dados.setdefault("avisos_enviados", {})
        return dados

    def salvar_aniversarios(self, dados):
        with open(ARQUIVO_ANIVERSARIOS, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=4)

    def obter_texto_aniversario(self, guild, membros):
        if isinstance(membros, discord.Member):
            membros = [membros]

        cargo_membro_id = obter_valor_config(guild, "CARGO_MEMBRO_ID", CARGO_MEMBRO_ID)
        mencao_fdn = f"<@&{cargo_membro_id}>"
        mencoes = ", ".join(membro.mention for membro in membros)

        if len(membros) == 1:
            linha_aniversario = f"Hoje e aniversario de {mencoes}! 🥳✨"
            linha_carinho = "Vamos encher essa pessoa de carinho, parabens e boas energias."
        else:
            linha_aniversario = f"Hoje e aniversario de {mencoes}! 🥳✨"
            linha_carinho = "Vamos encher essas pessoas de carinho, parabens e boas energias."

        return (
            "🎉 ANIVERSARIANTE DO DIA! 🎉\n\n"
            f"{linha_aniversario}\n"
            f"{linha_carinho}\n\n"
            f"{mencao_fdn}, desejem feliz aniversario e mostrem o carinho da nossa familia FDN! 💙\n\n"
            "Que esse novo ciclo seja cheio de conquistas, alegria, saude e momentos incriveis.\n"
            "Na FDN, ninguem comemora sozinho. 🎂🌙\n"
            "Parabens!"
        )

    async def obter_canal_aniversario(self, guild):
        canal_id = obter_valor_config(guild, "CANAL_ANIVERSARIO_ID", CANAL_ANIVERSARIO_ID)
        canal = self.bot.get_channel(canal_id)
        if canal:
            return canal
        try:
            return await self.bot.fetch_channel(canal_id)
        except Exception:
            return None

    async def buscar_membro_aniversariante(self, guild, membro_id):
        membro = guild.get_member(membro_id)
        if membro is not None:
            return membro
        try:
            return await guild.fetch_member(membro_id)
        except Exception:
            return None

    async def consolidar_mensagem_aniversario(self, guild, canal, membros):
        if not membros:
            return None, 0

        conteudo = self.obter_texto_aniversario(guild, membros)
        membros_ids = {membro.id for membro in membros}
        principal = None
        duplicadas = []

        async for mensagem in canal.history(limit=40):
            if mensagem.author.id != self.bot.user.id:
                continue
            if "ANIVERSARIANTE DO DIA" not in (mensagem.content or ""):
                continue
            if not membros_ids.intersection(set(mensagem.raw_mentions)):
                continue

            if principal is None:
                principal = mensagem
            else:
                duplicadas.append(mensagem)

        if principal is None:
            principal = await canal.send(
                conteudo,
                allowed_mentions=discord.AllowedMentions(users=True, roles=True),
            )
            return principal, 0

        await principal.edit(
            content=conteudo,
            allowed_mentions=discord.AllowedMentions.none(),
        )

        removidas = 0
        for mensagem in duplicadas:
            try:
                await mensagem.delete()
                removidas += 1
            except Exception:
                continue

        return principal, removidas

    async def aplicar_cargo_aniversariante(self, guild, aniversariantes_ids):
        cargo_id = obter_valor_config(guild, "CARGO_ANIVERSARIANTE_ID", CARGO_ANIVERSARIANTE_ID)
        cargo = guild.get_role(cargo_id)
        if cargo is None:
            try:
                cargos = await guild.fetch_roles()
                cargo = discord.utils.get(cargos, id=cargo_id)
            except Exception:
                return

        ids_validos = {int(user_id) for user_id in aniversariantes_ids}
        for membro in guild.members:
            tem_cargo = cargo in getattr(membro, "roles", [])
            deve_ter = membro.id in ids_validos

            if deve_ter and not tem_cargo:
                try:
                    await membro.add_roles(cargo, reason="Aniversariante do dia na FDN")
                except Exception:
                    continue
            elif tem_cargo and not deve_ter:
                try:
                    await membro.remove_roles(cargo, reason="Fim do dia de aniversário na FDN")
                except Exception:
                    continue

    async def processar_aniversarios_guild(self, guild, dados, agora=None):
        agora = agora or datetime.now(FUSO_HORARIO)
        dia = agora.day
        mes = agora.month
        data_hoje = agora.strftime("%Y-%m-%d")
        aniversarios = dados.setdefault("aniversarios", {})
        avisos_enviados = dados.setdefault("avisos_enviados", {})

        guild_id = str(guild.id)
        registros_guild = aniversarios.get(guild_id, {})
        enviados_guild = avisos_enviados.setdefault(guild_id, {})
        enviados_hoje = set(enviados_guild.get(data_hoje, []))
        alterou = False

        aniversariantes_hoje = []
        for membro_id, registro in registros_guild.items():
            try:
                if int(registro.get("dia")) == dia and int(registro.get("mes")) == mes:
                    aniversariantes_hoje.append(int(membro_id))
            except Exception:
                continue

        await self.aplicar_cargo_aniversariante(guild, aniversariantes_hoje)

        if aniversariantes_hoje:
            canal = await self.obter_canal_aniversario(guild)
            if canal:
                membros_hoje = []
                pendentes = []
                for membro_id in aniversariantes_hoje:
                    membro = await self.buscar_membro_aniversariante(guild, membro_id)
                    if membro is None:
                        continue

                    membros_hoje.append(membro)
                    if str(membro_id) not in enviados_hoje:
                        pendentes.append(membro)
                    continue

                    try:
                        await canal.send(
                            self.obter_texto_aniversario(guild, membro),
                            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
                        )
                        enviados_hoje.add(str(membro_id))
                        alterou = True
                    except Exception as erro:
                        await enviar_log_bot(
                            "âŒ Erro ao enviar aniversÃ¡rio automÃ¡tico",
                            f"**Guild:** `{guild.id}`\n**Membro:** <@{membro_id}>\n```{erro}```",
                        )

                if pendentes:
                    try:
                        await self.consolidar_mensagem_aniversario(guild, canal, membros_hoje)
                        enviados_hoje.update(str(membro.id) for membro in membros_hoje)
                        alterou = True
                    except Exception as erro:
                        await enviar_log_bot(
                            "Erro ao enviar aniversario automatico",
                            f"**Guild:** `{guild.id}`\n**Membros:** {' '.join(f'<@{membro.id}>' for membro in membros_hoje)}\n```{erro}```",
                        )

        chaves_antigas = [chave for chave in enviados_guild if chave != data_hoje]
        for chave in chaves_antigas:
            enviados_guild.pop(chave, None)
            alterou = True

        enviados_guild[data_hoje] = sorted(enviados_hoje)
        return alterou

    @tasks.loop(minutes=15)
    async def verificador_aniversarios(self):
        dados = self.carregar_aniversarios()
        alterou = False

        for guild in self.bot.guilds:
            if await self.processar_aniversarios_guild(guild, dados):
                alterou = True
            continue

            guild_id = str(guild.id)
            registros_guild = aniversarios.get(guild_id, {})
            enviados_guild = avisos_enviados.setdefault(guild_id, {})
            enviados_hoje = set(enviados_guild.get(data_hoje, []))

            aniversariantes_hoje = []
            for membro_id, registro in registros_guild.items():
                try:
                    if int(registro.get("dia")) == dia and int(registro.get("mes")) == mes:
                        aniversariantes_hoje.append(int(membro_id))
                except Exception:
                    continue

            await self.aplicar_cargo_aniversariante(guild, aniversariantes_hoje)

            if not aniversariantes_hoje:
                continue

            canal = await self.obter_canal_aniversario(guild)
            if not canal:
                continue

            for membro_id in aniversariantes_hoje:
                if str(membro_id) in enviados_hoje:
                    continue

                membro = guild.get_member(membro_id)
                if membro is None:
                    try:
                        membro = await guild.fetch_member(membro_id)
                    except Exception:
                        continue

                try:
                    await canal.send(
                        self.obter_texto_aniversario(guild, membro),
                        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
                    )
                    enviados_hoje.add(str(membro_id))
                    alterou = True
                except Exception as erro:
                    await enviar_log_bot(
                        "❌ Erro ao enviar aniversário automático",
                        f"**Guild:** `{guild.id}`\n**Membro:** <@{membro_id}>\n```{erro}```",
                    )

            chaves_antigas = [chave for chave in enviados_guild if chave != data_hoje]
            for chave in chaves_antigas:
                enviados_guild.pop(chave, None)
                alterou = True

            enviados_guild[data_hoje] = sorted(enviados_hoje)

        if alterou:
            self.salvar_aniversarios(dados)

    @verificador_aniversarios.before_loop
    async def before_verificador_aniversarios(self):
        await self.bot.wait_until_ready()

    @commands.group(name="bot", invoke_without_command=True)
    async def comando_bot(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(
                embed=criar_embed_tags(
                    "\u274c Sem permissao",
                    "Voce nao tem permissao pra usar esse comando.",
                )
            )
            return

        await ctx.send("Use assim: `!bot off`, `!bot off ID_DO_CANAL`, `!bot ia off` ou `!bot ia on`.")

    @comando_bot.group(name="ia", invoke_without_command=True)
    async def comando_bot_ia(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(
                embed=criar_embed_tags(
                    "\u274c Sem permissao",
                    "Voce nao tem permissao pra usar esse comando.",
                )
            )
            return

        ia_ativa = bool(obter_valor_config(ctx.guild, "BOT_IA_ATIVA", True))
        status = "ligada" if ia_ativa else "desligada"
        await ctx.send(
            embed=criar_embed_tags(
                "\ud83e\udde0 Controle da IA",
                (
                    f"Status atual: **{status}**.\n\n"
                    "Use `!bot ia off` para desligar as respostas da IA.\n"
                    "Use `!bot ia on` para ligar novamente."
                ),
            )
        )

    @comando_bot_ia.command(name="off")
    async def comando_bot_ia_off(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(
                embed=criar_embed_tags(
                    "\u274c Sem permissao",
                    "Voce nao tem permissao pra usar esse comando.",
                )
            )
            return

        dados = carregar_configs_servidores()
        guild_id = str(ctx.guild.id)
        secao = dados.setdefault(guild_id, {})
        secao["BOT_IA_ATIVA"] = False
        salvar_configs_servidores(dados)

        await ctx.send(
            embed=criar_embed_tags(
                "\u2705 IA desligada",
                "O Raven nao vai mais responder por IA a mencoes nem a respostas no chat ate voce ligar de novo.",
            )
        )

    @comando_bot_ia.command(name="on")
    async def comando_bot_ia_on(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(
                embed=criar_embed_tags(
                    "\u274c Sem permissao",
                    "Voce nao tem permissao pra usar esse comando.",
                )
            )
            return

        dados = carregar_configs_servidores()
        guild_id = str(ctx.guild.id)
        secao = dados.setdefault(guild_id, {})
        secao["BOT_IA_ATIVA"] = True
        salvar_configs_servidores(dados)

        await ctx.send(
            embed=criar_embed_tags(
                "\u2705 IA ligada",
                "O Raven voltou a responder por IA normalmente no chat.",
            )
        )

    @comando_bot.command(name="off")
    async def comando_bot_off(self, ctx, canal_destino: discord.TextChannel = None):
        if not membro_eh_staff(ctx.author):
            await ctx.send(
                embed=criar_embed_tags(
                    "\u274c Sem permissao",
                    "Voce nao tem permissao pra usar esse comando.",
                )
            )
            return

        canal = canal_destino or ctx.channel
        mensagem = "Bot offline! Retorno a partir das 9h, boa noite e at\u00e9 amanh\u00e3 FDN \U0001f319"

        try:
            await canal.send(mensagem)
        except Exception:
            await ctx.send(
                embed=criar_embed_tags(
                    "\u274c Erro",
                    "Nao consegui enviar a mensagem no canal informado.",
                )
            )
            return

        if canal.id != ctx.channel.id:
            await ctx.send(
                embed=criar_embed_tags(
                    "\u2705 Aviso enviado",
                    f"Mensagem enviada em {canal.mention}.",
                )
            )

    @commands.command(name="ajuda", aliases=["help"])
    async def ajuda(self, ctx, categoria=None):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if categoria is None:
            await ctx.send(embed=criar_embed_tags(
                "📘 Central de ajuda",
                (
                    "**Categorias disponíveis:**\n"
                    "`!ajuda tag` — comandos do sistema de tags\n"
                    "`!ajuda rec` — comandos de recrutamento\n"
                    "`!ajuda reação` — comando de aviso por reação\n\n"
                    "**Comandos rápidos:**\n"
                    "`!limpar 50` — limpa mensagens do canal atual\n\n"
                    "Use `!ajuda nome_da_categoria` para ver os comandos."
                )
            ))
            return

        categoria = categoria.lower()

        if categoria == "tag":
            await ctx.send(embed=criar_embed_tags(
                "📋 Ajuda • Tags",
                (
                    "`!tag lista` — mostra quem está pendente\n"
                    "`!tag atrasados` — mostra quem está com 7+ dias\n"
                    "`!tag atrasados 10` — mostra quem está com 10+ dias\n"
                    "`!tag info nome` — mostra detalhes de um membro\n"
                    "`!tag concluir nome` — remove da lista\n"
                    "`!tag remover nome ou ID` — remove da lista sem concluir\n"
                    "`!tag adicionar nome` — adiciona manualmente\n"
                    "`!tag adicionar nome DD/MM/AAAA` — adiciona com data manual"
                )
            ))
            return

        if categoria in ["rec", "recrutamento", "recrutador"]:
            await ctx.send(embed=criar_embed_tags(
                "🏆 Ajuda • Recrutamento",
                (
                    "`+1 nome_do_discord` — registra recrutamento automático no canal de contagem\n"
                    "`+1 nick` — também funciona se for o nick usado no Discord\n"
                    "`!rec ranking` — mostra o ranking do mês\n"
                    "`!rec info nome` — mostra os recrutamentos do membro\n"
                    "`!rec add nome 5` — adiciona recrutamentos manualmente\n"
                    "`!rec add nome 5 nome do recrutado` — adiciona com recrutado\n"
                    "`!rec addmsg ID_DA_MENSAGEM` — adiciona usando uma mensagem antiga de +1\n"
                    "`!rec remove nome` — remove o último +1 do membro\n"
                    "`!rec resetmes` — reseta os recrutamentos do mês atual"
                )
            ))
            return

        if categoria in ["reação", "reacao"]:
            await ctx.send(embed=criar_embed_tags(
                "📢 Ajuda • Reação",
                (
                    "`!reação em jogatina` — envia aviso para reagirem na jogatina\n"
                    "`!reação em invasão` — envia aviso para reagirem na invasão\n"
                    "`!reação em cronograma` — envia aviso para reagirem no cronograma\n"
                    "`!reação em avisos` — envia aviso para reagirem em avisos"
                )
            ))
            return

        if categoria in ["frase", "frases"]:
            await ctx.send(embed=criar_embed_tags(
                "💬 Ajuda • Frases",
                (
                    "`!frase listar nome_do_gatilho` — lista as frases do gatilho\n"
                    "`!frase add nome_do_gatilho texto...` — adiciona uma nova frase\n"
                    "`!frase remover nome_do_gatilho numero` — remove a frase pelo número"
                )
            ))
            return

        if categoria in ["gatilho", "gatilhos"]:
            await ctx.send(embed=criar_embed_tags(
                "🎯 Ajuda • Gatilhos",
                "`!gatilho listar` — mostra os gatilhos disponíveis\n`!gatilho info nome_do_gatilho` — mostra detalhes de um gatilho"
            ))
            return

        await ctx.send(embed=criar_embed_tags(
            "❌ Categoria inválida",
            "Use uma destas opções:\n`!ajuda tag`\n`!ajuda rec`\n`!ajuda reação`"
        ))

    @commands.command(name="conselho")
    async def conselho(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        gatilho_conselho = obter_gatilho("comando_conselho")
        respostas = gatilho_conselho.get("respostas", []) if gatilho_conselho else []
        resposta = escolher_resposta_gatilho("comando_conselho", respostas)
        if not resposta:
            await ctx.send(embed=criar_embed_tags("❌ Erro", "Não consegui gerar um conselho agora."))
            return

        canal_geral = self.bot.get_channel(CANAL_GERAL_ID)
        if not canal_geral:
            try:
                canal_geral = await self.bot.fetch_channel(CANAL_GERAL_ID)
            except Exception:
                await ctx.send(embed=criar_embed_tags("❌ Canal não encontrado", "Não consegui encontrar o canal geral configurado."))
                return

        try:
            await canal_geral.send(resposta)
            await ctx.send(embed=criar_embed_tags("✅ Conselho enviado", f"**Enviado em:** <#{CANAL_GERAL_ID}>"))
            await enviar_log_bot(
                "📢 Conselho enviado",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Enviado em:** <#{CANAL_GERAL_ID}>\n"
                    f"**Canal do comando:** {ctx.channel.mention}\n"
                    f"**Mensagem:** {resposta}"
                )
            )
        except Exception as erro:
            await ctx.send(embed=criar_embed_tags("❌ Erro ao enviar conselho", "Não consegui enviar o conselho no canal geral."))
            await enviar_log_bot(
                "❌ Erro no comando de conselho",
                f"**Staff:** {ctx.author.mention}\n**Canal do comando:** {ctx.channel.mention}\n```{erro}```"
            )

    @commands.command(name="interagir")
    async def interagir(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        gatilho_interagir = obter_gatilho("comando_interagir")
        respostas = gatilho_interagir.get("respostas", []) if gatilho_interagir else []
        resposta = escolher_resposta_gatilho("comando_interagir", respostas)
        if not resposta:
            await ctx.send(embed=criar_embed_tags("❌ Erro", "Não consegui gerar a mensagem de interação agora."))
            return

        canal_geral = self.bot.get_channel(CANAL_GERAL_ID)
        if not canal_geral:
            try:
                canal_geral = await self.bot.fetch_channel(CANAL_GERAL_ID)
            except Exception:
                await ctx.send(embed=criar_embed_tags("❌ Canal não encontrado", "Não consegui encontrar o canal geral configurado."))
                return

        try:
            await canal_geral.send(resposta, allowed_mentions=discord.AllowedMentions(roles=True))

            try:
                await ctx.message.delete()
            except Exception:
                pass

            await enviar_log_bot(
                "📢 Interagir enviado",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Enviado em:** <#{CANAL_GERAL_ID}>\n"
                    f"**Canal do comando:** {ctx.channel.mention}\n"
                    f"**Mensagem:** {resposta}"
                )
            )
        except Exception as erro:
            await ctx.send(embed=criar_embed_tags("❌ Erro ao enviar interação", "Não consegui enviar a mensagem no canal geral."))
            await enviar_log_bot(
                "❌ Erro no comando interagir",
                f"**Staff:** {ctx.author.mention}\n**Canal do comando:** {ctx.channel.mention}\n```{erro}```"
            )

    @commands.command(name="recrutar")
    async def recrutar(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        gatilho_recrutadores = obter_gatilho("comando_recrutadores")
        respostas = gatilho_recrutadores.get("respostas", []) if gatilho_recrutadores else []
        resposta = escolher_resposta_gatilho("comando_recrutadores", respostas)
        if not resposta:
            await ctx.send(embed=criar_embed_tags("❌ Erro", "Não consegui gerar a mensagem de recrutamento agora."))
            return

        canal_recrutadores = self.bot.get_channel(CANAL_RECRUTADORES_ID)
        if not canal_recrutadores:
            try:
                canal_recrutadores = await self.bot.fetch_channel(CANAL_RECRUTADORES_ID)
            except Exception:
                await ctx.send(embed=criar_embed_tags("❌ Canal não encontrado", "Não consegui encontrar o canal de recrutadores configurado."))
                return

        try:
            await canal_recrutadores.send(resposta, allowed_mentions=discord.AllowedMentions(roles=True))

            try:
                await ctx.message.delete()
            except Exception:
                pass

            await enviar_log_bot(
                "📢 Recrutar enviado",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Enviado em:** <#{CANAL_RECRUTADORES_ID}>\n"
                    f"**Canal do comando:** {ctx.channel.mention}\n"
                    f"**Mensagem:** {resposta}"
                )
            )
        except Exception as erro:
            await ctx.send(embed=criar_embed_tags("❌ Erro ao enviar recrutamento", "Não consegui enviar a mensagem no canal de recrutadores."))
            await enviar_log_bot(
                "❌ Erro no comando recrutar",
                f"**Staff:** {ctx.author.mention}\n**Canal do comando:** {ctx.channel.mention}\n```{erro}```"
            )

    @commands.command(name="reação", aliases=["reacao"])
    async def reacao(self, ctx, *args):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if len(args) < 2:
            await ctx.send(embed=criar_embed_tags(
                "📘 Comando de reação",
                "Use assim: `!reação em jogatina`\n\n**Opções disponíveis:**\n`jogatina`\n`invasão`\n`cronograma`\n`avisos`"
            ))
            return

        palavra_em = args[0].lower()
        destino = " ".join(args[1:]).lower().strip()
        if palavra_em != "em":
            await ctx.send(embed=criar_embed_tags("❌ Formato inválido", "Use assim: `!reação em jogatina`"))
            return

        canal_destino_id = CANAIS_REACAO.get(destino)
        if not canal_destino_id:
            await ctx.send(embed=criar_embed_tags("❌ Opção inválida", "Use uma destas opções: `jogatina`, `invasão`, `cronograma`, `avisos`."))
            return

        canal_geral = self.bot.get_channel(CANAL_GERAL_ID)
        if not canal_geral:
            try:
                canal_geral = await self.bot.fetch_channel(CANAL_GERAL_ID)
            except Exception:
                await ctx.send(embed=criar_embed_tags("❌ Canal não encontrado", "Não consegui encontrar o canal geral configurado."))
                return

        mensagem = gerar_mensagem_reacao(destino, canal_destino_id)
        if not mensagem:
            await ctx.send(embed=criar_embed_tags("❌ Erro", "Não consegui gerar a mensagem desse aviso."))
            return

        try:
            await canal_geral.send(mensagem, allowed_mentions=discord.AllowedMentions(roles=True))
            await ctx.send(embed=criar_embed_tags(
                "✅ Aviso enviado",
                f"**Tipo:** `{destino}`\n**Canal citado:** <#{canal_destino_id}>\n**Enviado em:** <#{CANAL_GERAL_ID}>"
            ))
            await enviar_log_bot(
                "📢 Aviso de reação enviado",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Tipo:** `{destino}`\n"
                    f"**Canal citado:** <#{canal_destino_id}>\n"
                    f"**Enviado em:** <#{CANAL_GERAL_ID}>"
                )
            )
        except Exception as erro:
            await ctx.send(embed=criar_embed_tags("❌ Erro ao enviar aviso", "Não consegui enviar a mensagem no canal geral."))
            await enviar_log_bot(
                "❌ Erro no comando de reação",
                f"**Staff:** {ctx.author.mention}\n**Tipo:** `{destino}`\n```{erro}```"
            )

    @commands.command(name="responderaven")
    async def respondemencao(self, ctx, message_id=None, opcao_frase=None):
        if not membro_eh_lideranca(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if not message_id:
            await ctx.send(embed=criar_embed_tags(
                "📘 Responder menção antiga",
                (
                    "Use assim: `!responderaven ID_DA_MENSAGEM` para menção vazia.\n"
                    "Ou: `!responderaven ID_DA_MENSAGEM NUMERO` para frase pronta.\n\n"
                    "**Frases prontas:**\n"
                    "`1` — jáe então!\n`2` — faz o pix!\n`3` — não quero, obrigado!\n`4` — estou ocupado no momento!\n"
                    "`5` — eu nem existo\n`6` — vou fingir que estou entendendo\n`7` — Se falar minha lingua eu consigo responder\n"
                    "`8` — Tem que traduzir?\n`9` — está carente amigo(a) ?\n`10` — É muito ego e pouca pika!\n"
                    "`11` — vamos fingir que a pessoa respondeu em espírito\n\nPode usar em qualquer canal."
                )
            ))
            return

        if not str(message_id).isdigit():
            await ctx.send(embed=criar_embed_tags("❌ ID inválido", "O ID da mensagem precisa ser numérico."))
            return

        mensagem_alvo = await buscar_mensagem_por_id_na_guild(ctx.guild, message_id)
        if not mensagem_alvo:
            await ctx.send(embed=criar_embed_tags("❌ Mensagem não encontrada", "Não consegui encontrar essa mensagem na guild."))
            return
        if mensagem_alvo.author.bot:
            await ctx.send(embed=criar_embed_tags("❌ Mensagem inválida", "Essa mensagem foi enviada por um bot."))
            return

        menciona_bot = self.bot.user in mensagem_alvo.mentions
        texto_mencao = mensagem_alvo.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
        resposta_mencao = None

        if opcao_frase is not None:
            if not str(opcao_frase).isdigit():
                await ctx.send(embed=criar_embed_tags("❌ Opção inválida", "Escolha um número de `1` a `11` para a frase pronta."))
                return

            indice = int(opcao_frase)
            if indice < 1 or indice > len(FRASES_RESPOSTA_MANUAL):
                await ctx.send(embed=criar_embed_tags("❌ Opção inválida", "Escolha uma opção válida de `1` a `11`."))
                return
            resposta_mencao = FRASES_RESPOSTA_MANUAL[indice - 1]
        else:
            if not menciona_bot:
                await ctx.send(embed=criar_embed_tags("❌ Mensagem inválida", "Essa mensagem não menciona o bot."))
                return
            if texto_mencao:
                await ctx.send(embed=criar_embed_tags(
                    "❌ Mensagem inválida",
                    "Essa mensagem tem conteúdo além da menção.\nUse `!responderaven ID_DA_MENSAGEM NUMERO` para responder com frase pronta."
                ))
                return

        if resposta_mencao is None:
            resposta_mencao = escolher_resposta_gatilho("mencao_vazia", FRASES_MENCAO_VAZIA)
        if not resposta_mencao:
            await ctx.send(embed=criar_embed_tags("❌ Erro", "Não consegui gerar uma resposta para essa menção."))
            return

        try:
            await mensagem_alvo.reply(resposta_mencao, mention_author=False)
            await ctx.send(embed=criar_embed_tags(
                "✅ Resposta enviada",
                f"**Mensagem:** `{mensagem_alvo.id}`\n**Autor:** {mensagem_alvo.author.mention}\n**Canal:** {mensagem_alvo.channel.mention}"
            ))
            await enviar_log_bot(
                "💬 Resposta manual em menção antiga",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Autor da mensagem:** {mensagem_alvo.author.mention}\n"
                    f"**Mensagem:** `{mensagem_alvo.id}`\n"
                    f"**Canal:** {mensagem_alvo.channel.mention}"
                )
            )
        except Exception as erro:
            await ctx.send(embed=criar_embed_tags("❌ Erro ao responder", "Não consegui responder essa mensagem antiga."))
            await enviar_log_bot(
                "❌ Erro ao responder menção antiga",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Mensagem:** `{mensagem_alvo.id}`\n"
                    f"**Canal:** {mensagem_alvo.channel.mention}\n"
                    f"```{erro}```"
                )
            )

    @commands.command(name="bemvindo", aliases=["boasvindas"])
    async def bemvindo(self, ctx, alvo_texto=None):
        if not membro_eh_lideranca(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if not alvo_texto:
            await ctx.send(embed=criar_embed_tags("👋 Boas-vindas", "Use assim: `!bemvindo ID_DA_PESSOA`"))
            return

        membro = procurar_membro_por_texto(ctx.guild, str(alvo_texto))
        if not membro and str(alvo_texto).isdigit():
            try:
                membro = await ctx.guild.fetch_member(int(alvo_texto))
            except Exception:
                membro = None

        if not membro:
            await ctx.send(embed=criar_embed_tags("❌ Membro não encontrado", "Não consegui encontrar essa pessoa no servidor."))
            return

        try:
            mensagem_enviada = await enviar_boas_vindas_no_geral(membro)
            if not mensagem_enviada:
                await ctx.send(embed=criar_embed_tags("❌ Erro", "Não consegui enviar a mensagem de boas-vindas no canal geral."))
                return

            await ctx.send(embed=criar_embed_tags("✅ Boas-vindas enviadas", f"**Membro:** {membro.mention}\n**Enviado em:** <#{CANAL_GERAL_ID}>"))
            await enviar_log_bot(
                "👋 Boas-vindas enviadas manualmente",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Membro:** {membro.mention}\n"
                    f"**Canal de envio:** <#{CANAL_GERAL_ID}>"
                )
            )
        except Exception as erro:
            await ctx.send(embed=criar_embed_tags("❌ Erro ao enviar boas-vindas", "Não consegui enviar a mensagem de boas-vindas no canal geral."))
            await enviar_log_bot(
                "❌ Erro no comando de boas-vindas",
                f"**Staff:** {ctx.author.mention}\n**Membro:** {membro.mention}\n```{erro}```"
            )


    @commands.command(name="aniversario")
    async def aniversario(
        self,
        ctx,
        membro: discord.Member = None,
        dia: int = None,
        mes: int = None,
        membro2: discord.Member = None,
        membro3: discord.Member = None,
        membro4: discord.Member = None,
        membro5: discord.Member = None,
    ):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if membro is None or dia is None or mes is None:
            await ctx.send(embed=criar_embed_tags("🎂 Aniversário", "Use assim: `!aniversario @membro dia mes [@membro2] [@membro3] [@membro4] [@membro5]`"))
            return

        try:
            datetime(2000, int(mes), int(dia))
        except ValueError:
            await ctx.send(embed=criar_embed_tags("❌ Data inválida", "Não consegui salvar porque esse dia/mês não existe."))
            return

        membros = []
        vistos = set()
        for atual in (membro, membro2, membro3, membro4, membro5):
            if atual is None or atual.id in vistos:
                continue
            vistos.add(atual.id)
            membros.append(atual)

        dados = self.carregar_aniversarios()
        aniversarios = dados.setdefault("aniversarios", {})
        registros_guild = aniversarios.setdefault(str(ctx.guild.id), {})
        for aniversariante in membros:
            registros_guild[str(aniversariante.id)] = {
                "dia": int(dia),
                "mes": int(mes),
                "nome": aniversariante.display_name,
                "registrado_por": ctx.author.id,
            }
        self.salvar_aniversarios(dados)

        hoje = datetime.now(FUSO_HORARIO)
        if int(dia) == hoje.day and int(mes) == hoje.month:
            if await self.processar_aniversarios_guild(ctx.guild, dados, agora=hoje):
                self.salvar_aniversarios(dados)

        texto_membros = "\n".join(f"• {aniversariante.mention}" for aniversariante in membros)

        await ctx.send(
            embed=criar_embed_tags(
                "✅ Aniversário salvo",
                (
                    f"**Membros:**\n{texto_membros}\n"
                    f"**Data:** `{int(dia):02d}/{int(mes):02d}`\n"
                    f"**Canal do aviso:** <#{obter_valor_config(ctx.guild, 'CANAL_ANIVERSARIO_ID', CANAL_ANIVERSARIO_ID)}>\n"
                    f"**Cargo do dia:** <@&{obter_valor_config(ctx.guild, 'CARGO_ANIVERSARIANTE_ID', CARGO_ANIVERSARIANTE_ID)}>"
                ),
            )
        )
        await enviar_log_bot(
            "🎂 Aniversário salvo",
            (
                f"**Staff:** {ctx.author.mention}\n"
                f"**Membros:**\n{texto_membros}\n"
                f"**Data:** `{int(dia):02d}/{int(mes):02d}`\n"
                f"**Canal do comando:** {ctx.channel.mention}"
            ),
        )

    @commands.command(name="listadeaniversarios")
    async def listadeaniversarios(self, ctx, mes: int = None):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if mes is None or mes < 1 or mes > 12:
            await ctx.send(embed=criar_embed_tags("🎂 Lista de aniversários", "Use assim: `!listadeaniversarios mes`"))
            return

        nomes_meses = {
            1: "Janeiro",
            2: "Fevereiro",
            3: "Março",
            4: "Abril",
            5: "Maio",
            6: "Junho",
            7: "Julho",
            8: "Agosto",
            9: "Setembro",
            10: "Outubro",
            11: "Novembro",
            12: "Dezembro",
        }

        dados = self.carregar_aniversarios()
        aniversarios = dados.get("aniversarios", {})
        registros_guild = aniversarios.get(str(ctx.guild.id), {})

        aniversariantes = []
        for membro_id, registro in registros_guild.items():
            try:
                dia_registro = int(registro.get("dia"))
                mes_registro = int(registro.get("mes"))
            except (TypeError, ValueError):
                continue

            if mes_registro != int(mes):
                continue

            membro = ctx.guild.get_member(int(membro_id))
            nome_exibicao = membro.mention if membro else registro.get("nome") or f"ID {membro_id}"
            aniversariantes.append((dia_registro, nome_exibicao))

        if not aniversariantes:
            await ctx.send(
                embed=criar_embed_tags(
                    "🎂 Lista de aniversários",
                    f"Não encontrei aniversários cadastrados para **{nomes_meses[int(mes)]}**.",
                )
            )
            return

        aniversariantes.sort(key=lambda item: (item[0], item[1].lower()))
        linhas = [f"• `{dia:02d}/{int(mes):02d}` — {nome}" for dia, nome in aniversariantes]

        await ctx.send(
            embed=criar_embed_tags(
                f"🎂 Aniversários de {nomes_meses[int(mes)]}",
                "\n".join(linhas),
            )
        )

    @commands.command(name="atualizaraniversariohoje")
    async def atualizaraniversariohoje(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        hoje = datetime.now(FUSO_HORARIO)
        dados = self.carregar_aniversarios()
        aniversarios = dados.setdefault("aniversarios", {})
        registros_guild = aniversarios.get(str(ctx.guild.id), {})

        aniversariantes_ids = []
        for membro_id, registro in registros_guild.items():
            try:
                if int(registro.get("dia")) == hoje.day and int(registro.get("mes")) == hoje.month:
                    aniversariantes_ids.append(int(membro_id))
            except Exception:
                continue

        if not aniversariantes_ids:
            await ctx.send(embed=criar_embed_tags("🎂 Aniversário", "Não encontrei aniversariantes cadastrados para hoje."))
            return

        canal = await self.obter_canal_aniversario(ctx.guild)
        if canal is None:
            await ctx.send(embed=criar_embed_tags("❌ Canal não encontrado", "Não consegui encontrar o canal de aniversários configurado."))
            return

        membros = []
        for membro_id in aniversariantes_ids:
            membro = await self.buscar_membro_aniversariante(ctx.guild, membro_id)
            if membro is not None:
                membros.append(membro)

        if not membros:
            await ctx.send(embed=criar_embed_tags("🎂 Aniversário", "Não consegui localizar os membros de hoje no servidor."))
            return

        _, removidas = await self.consolidar_mensagem_aniversario(ctx.guild, canal, membros)
        await ctx.send(
            embed=criar_embed_tags(
                "✅ Aniversário atualizado",
                (
                    f"**Canal:** {canal.mention}\n"
                    f"**Membros:** {', '.join(membro.mention for membro in membros)}\n"
                    f"**Mensagens removidas:** `{removidas}`"
                ),
            )
        )
        return
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if membro is None or dia is None or mes is None:
            await ctx.send(embed=criar_embed_tags("🎂 Aniversário", "Use assim: `!aniversario @membro dia mes`"))
            return

        try:
            datetime(2000, int(mes), int(dia))
        except ValueError:
            await ctx.send(embed=criar_embed_tags("❌ Data inválida", "Não consegui salvar porque esse dia/mês não existe."))
            return

        dados = self.carregar_aniversarios()
        aniversarios = dados.setdefault("aniversarios", {})
        registros_guild = aniversarios.setdefault(str(ctx.guild.id), {})
        registros_guild[str(membro.id)] = {
            "dia": int(dia),
            "mes": int(mes),
            "nome": membro.display_name,
            "registrado_por": ctx.author.id,
        }
        self.salvar_aniversarios(dados)

        await ctx.send(
            embed=criar_embed_tags(
                "✅ Aniversário salvo",
                (
                    f"**Membro:** {membro.mention}\n"
                    f"**Data:** `{int(dia):02d}/{int(mes):02d}`\n"
                    f"**Canal do aviso:** <#{obter_valor_config(ctx.guild, 'CANAL_ANIVERSARIO_ID', CANAL_ANIVERSARIO_ID)}>\n"
                    f"**Cargo do dia:** <@&{obter_valor_config(ctx.guild, 'CARGO_ANIVERSARIANTE_ID', CARGO_ANIVERSARIANTE_ID)}>"
                ),
            )
        )
        await enviar_log_bot(
            "🎂 Aniversário salvo",
            (
                f"**Staff:** {ctx.author.mention}\n"
                f"**Membro:** {membro.mention}\n"
                f"**Data:** `{int(dia):02d}/{int(mes):02d}`\n"
                f"**Canal do comando:** {ctx.channel.mention}"
            ),
        )
    @commands.command(name="olhaadv")
    async def olhaadv(self, ctx):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        canal_advertencia_id = 1507388610117238824
        canal_advertencia = self.bot.get_channel(canal_advertencia_id)
        if not canal_advertencia:
            try:
                canal_advertencia = await self.bot.fetch_channel(canal_advertencia_id)
            except Exception:
                canal_advertencia = None

        if not canal_advertencia:
            await ctx.send(embed=criar_embed_tags("❌ Canal não encontrado", "Não consegui encontrar o canal de advertência configurado."))
            return

        mensagem = "Sinto o cheiro de ban vindo ai <@&1461789054986223650>"

        try:
            await canal_advertencia.send(
                content=mensagem,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            await ctx.send(
                embed=criar_embed_tags(
                    "✅ Aviso enviado",
                    f"**Mensagem:** {mensagem}\n**Enviado em:** <#{canal_advertencia.id}>"
                )
            )
            await enviar_log_bot(
                "⚠️ Aviso de advertência enviado",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Mensagem:** {mensagem}\n"
                    f"**Enviado em:** <#{canal_advertencia.id}>\n"
                    f"**Canal do comando:** {ctx.channel.mention}"
                )
            )
        except Exception as erro:
            await ctx.send(embed=criar_embed_tags("❌ Erro ao enviar aviso", "Não consegui enviar o aviso no canal de advertência."))
            await enviar_log_bot(
                "❌ Erro no comando olhaadv",
                f"**Staff:** {ctx.author.mention}\n**Mensagem:** {mensagem}\n**Canal do comando:** {ctx.channel.mention}\n```{erro}```"
            )

    @commands.command(name="aniversario")
    async def aniversario(self, ctx, membro: discord.Member = None, dia: int = None, mes: int = None):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if not membro:
            await ctx.send(embed=criar_embed_tags("🎂 Aniversário", "Use assim: `!aniversario @membro`"))
            return

        canal_aniversario = self.bot.get_channel(CANAL_ANIVERSARIO_ID)
        if not canal_aniversario:
            try:
                canal_aniversario = await self.bot.fetch_channel(CANAL_ANIVERSARIO_ID)
            except Exception:
                await ctx.send(embed=criar_embed_tags("❌ Canal não encontrado", "Não consegui encontrar o canal de aniversário configurado."))
                return

        embed = discord.Embed(
            title="🌙🎂 A noite está em festa!",
            description=(
                f"Hoje é um dia especial para a FDN, pois estamos celebrando o aniversário de {membro.mention}! <a:heartcyan:1464014951650689056>\n\n"
                "Que esse novo ciclo venha cheio de saúde, conquistas, boas energias, momentos felizes e muitas vitórias pela frente.\n\n"
                "A FDN deseja muitos anos de vida e que sua caminhada continue brilhando <a:estrelas:1464017832118452520>\n\n"
                f"<@&{CARGO_AVISO_REACAO_ID}> Deixem os parabéns para {membro.mention} e façam esse dia ficar ainda mais especial! 🎉"
            ),
            color=discord.Color.from_rgb(0, 255, 255),
        )
        embed.set_footer(text="Raven • Celebração FDN")

        try:
            await canal_aniversario.send(
                content=f"<@&{CARGO_AVISO_REACAO_ID}> {membro.mention}",
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=True),
            )
            await ctx.send(embed=criar_embed_tags("✅ Aniversário anunciado", f"**Membro:** {membro.mention}\n**Enviado em:** <#{CANAL_ANIVERSARIO_ID}>"))
            await enviar_log_bot(
                "🎂 Aniversário anunciado",
                (
                    f"**Staff:** {ctx.author.mention}\n"
                    f"**Aniversariante:** {membro.mention}\n"
                    f"**Enviado em:** <#{CANAL_ANIVERSARIO_ID}>\n"
                    f"**Canal do comando:** {ctx.channel.mention}"
                )
            )
        except Exception as erro:
            await ctx.send(embed=criar_embed_tags("❌ Erro ao anunciar aniversário", "Não consegui enviar a mensagem de aniversário no canal configurado."))
            await enviar_log_bot(
                "❌ Erro no comando de aniversário",
                f"**Staff:** {ctx.author.mention}\n**Membro:** {membro.mention}\n**Canal do comando:** {ctx.channel.mention}\n```{erro}```"
            )

    @commands.command(name="aniversario")
    async def aniversario(
        self,
        ctx,
        membro: discord.Member = None,
        dia: int = None,
        mes: int = None,
        membro2: discord.Member = None,
        membro3: discord.Member = None,
        membro4: discord.Member = None,
        membro5: discord.Member = None,
    ):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("❌ Sem permissão", "Você não tem permissão pra usar esse comando."))
            return

        if membro is None or dia is None or mes is None:
            await ctx.send(embed=criar_embed_tags("🎂 Aniversário", "Use assim: `!aniversario @membro dia mes [@membro2] [@membro3] [@membro4] [@membro5]`"))
            return

        try:
            datetime(2000, int(mes), int(dia))
        except ValueError:
            await ctx.send(embed=criar_embed_tags("❌ Data inválida", "Não consegui salvar porque esse dia/mês não existe."))
            return

        membros = []
        vistos = set()
        for atual in (membro, membro2, membro3, membro4, membro5):
            if atual is None or atual.id in vistos:
                continue
            vistos.add(atual.id)
            membros.append(atual)

        dados = self.carregar_aniversarios()
        aniversarios = dados.setdefault("aniversarios", {})
        registros_guild = aniversarios.setdefault(str(ctx.guild.id), {})
        for aniversariante in membros:
            registros_guild[str(aniversariante.id)] = {
                "dia": int(dia),
                "mes": int(mes),
                "nome": aniversariante.display_name,
                "registrado_por": ctx.author.id,
            }
        self.salvar_aniversarios(dados)

        texto_membros = "\n".join(f"• {aniversariante.mention}" for aniversariante in membros)

        await ctx.send(
            embed=criar_embed_tags(
                "✅ Aniversário salvo",
                (
                    f"**Membros:**\n{texto_membros}\n"
                    f"**Data:** `{int(dia):02d}/{int(mes):02d}`\n"
                    f"**Canal do aviso:** <#{obter_valor_config(ctx.guild, 'CANAL_ANIVERSARIO_ID', CANAL_ANIVERSARIO_ID)}>\n"
                    f"**Cargo do dia:** <@&{obter_valor_config(ctx.guild, 'CARGO_ANIVERSARIANTE_ID', CARGO_ANIVERSARIANTE_ID)}>"
                ),
            )
        )
        await enviar_log_bot(
            "🎂 Aniversário salvo",
            (
                f"**Staff:** {ctx.author.mention}\n"
                f"**Membros:**\n{texto_membros}\n"
                f"**Data:** `{int(dia):02d}/{int(mes):02d}`\n"
                f"**Canal do comando:** {ctx.channel.mention}"
            ),
        )


    @commands.command(name="aniversario")
    async def aniversario(
        self,
        ctx,
        membro: discord.Member = None,
        dia: int = None,
        mes: int = None,
        membro2: discord.Member = None,
        membro3: discord.Member = None,
        membro4: discord.Member = None,
        membro5: discord.Member = None,
    ):
        if not membro_eh_staff(ctx.author):
            await ctx.send(embed=criar_embed_tags("âŒ Sem permissÃ£o", "VocÃª nÃ£o tem permissÃ£o pra usar esse comando."))
            return

        if membro is None or dia is None or mes is None:
            await ctx.send(embed=criar_embed_tags("ðŸŽ‚ AniversÃ¡rio", "Use assim: `!aniversario @membro dia mes [@membro2] [@membro3] [@membro4] [@membro5]`"))
            return

        try:
            datetime(2000, int(mes), int(dia))
        except ValueError:
            await ctx.send(embed=criar_embed_tags("âŒ Data invÃ¡lida", "NÃ£o consegui salvar porque esse dia/mÃªs nÃ£o existe."))
            return

        membros = []
        vistos = set()
        for atual in (membro, membro2, membro3, membro4, membro5):
            if atual is None or atual.id in vistos:
                continue
            vistos.add(atual.id)
            membros.append(atual)

        dados = self.carregar_aniversarios()
        aniversarios = dados.setdefault("aniversarios", {})
        registros_guild = aniversarios.setdefault(str(ctx.guild.id), {})
        for aniversariante in membros:
            registros_guild[str(aniversariante.id)] = {
                "dia": int(dia),
                "mes": int(mes),
                "nome": aniversariante.display_name,
                "registrado_por": ctx.author.id,
            }

        self.salvar_aniversarios(dados)

        hoje = datetime.now(FUSO_HORARIO)
        if int(dia) == hoje.day and int(mes) == hoje.month:
            if await self.processar_aniversarios_guild(ctx.guild, dados, agora=hoje):
                self.salvar_aniversarios(dados)

        texto_membros = "\n".join(f"â€¢ {aniversariante.mention}" for aniversariante in membros)

        await ctx.send(
            embed=criar_embed_tags(
                "âœ… AniversÃ¡rio salvo",
                (
                    f"**Membros:**\n{texto_membros}\n"
                    f"**Data:** `{int(dia):02d}/{int(mes):02d}`\n"
                    f"**Canal do aviso:** <#{obter_valor_config(ctx.guild, 'CANAL_ANIVERSARIO_ID', CANAL_ANIVERSARIO_ID)}>\n"
                    f"**Cargo do dia:** <@&{obter_valor_config(ctx.guild, 'CARGO_ANIVERSARIANTE_ID', CARGO_ANIVERSARIANTE_ID)}>"
                ),
            )
        )
        await enviar_log_bot(
            "ðŸŽ‚ AniversÃ¡rio salvo",
            (
                f"**Staff:** {ctx.author.mention}\n"
                f"**Membros:**\n{texto_membros}\n"
                f"**Data:** `{int(dia):02d}/{int(mes):02d}`\n"
                f"**Canal do comando:** {ctx.channel.mention}"
            ),
        )


async def setup(bot):
    await bot.add_cog(StaffCog(bot))
