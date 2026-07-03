import time
import traceback
from datetime import datetime

import data.runtime as runtime
import discord
from discord import app_commands
from discord.ext import commands

from config import FUSO_HORARIO, MENSAGEIRO_DA_NOITE_ROLE_ID, NPC_SEM_QUEST_ROLE_ID, XP_CHANNEL_ID
from services.conquista_anuncios import enviar_embed_conquista
from services.conquistas_mensageiro import (
    CONQUISTA_MENSAGEIRO_DA_NOITE,
    adicionar_pontos_mensageiro,
    obter_estado_mensageiro,
    salvar_estado_mensageiro,
)
from services.conquistas_presenca import CONQUISTAS_PRESENCA, carregar_dados_conquistas, salvar_dados_conquistas
from services.conquistas_raven import (
    CONQUISTA_FA_DO_RAVEN,
    formatar_data_iso_local,
    obter_estado_fa_do_raven,
)
from services.logs import registrar_exclusao_temporaria
from services.server_config import obter_valor_config
from services.xp import (
    XP_ROLE_THRESHOLDS,
    adicionar_xp_manual,
    carregar_dados_xp,
    obter_estado_xp_usuario,
    obter_proxima_meta_xp,
    ranking_xp,
    remover_xp_manual,
    resetar_xp_diario_se_preciso,
    resetar_xp_usuario,
    salvar_dados_xp,
)


class SlashMessageAdapter:
    def __init__(self, interaction: discord.Interaction):
        self.id = interaction.id
        self.author = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.attachments = []
        self.content = ""

    async def delete(self, *args, **kwargs):
        return None


class SlashContextAdapter:
    def __init__(self, interaction: discord.Interaction, ephemeral: bool):
        self.interaction = interaction
        self.bot = interaction.client
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.message = SlashMessageAdapter(interaction)
        self.invoked_subcommand = None
        self.prefix = "/"
        self.ephemeral = ephemeral
        self.sent_count = 0

    async def send(self, content=None, **kwargs):
        delete_after = kwargs.pop("delete_after", None)
        kwargs.setdefault("ephemeral", self.ephemeral)

        mensagem = await self.interaction.followup.send(
            content=content,
            wait=delete_after is not None,
            **kwargs,
        )

        self.sent_count += 1

        if delete_after is not None and mensagem is not None:
            try:
                await mensagem.delete(delay=delete_after)
                await registrar_exclusao_temporaria(
                    origem="Resposta temporaria de slash",
                    canal=self.channel,
                    guild_ou_id=self.guild,
                    autor=self.author,
                    delay=delete_after,
                    mensagem_id=getattr(mensagem, "id", None),
                    conteudo=content,
                    alvo="mensagem temporaria",
                )
            except Exception:
                pass

        return mensagem


class SlashBridgeCog(commands.Cog):
    rec = app_commands.Group(name="rec", description="Comandos de recrutamento.")
    recrutamento = app_commands.Group(name="recrutamento", description="Atalho para comandos de recrutamento.")
    recrutador = app_commands.Group(name="recrutador", description="Atalho para comandos de recrutamento.")
    tag = app_commands.Group(name="tag", description="Comandos do sistema de tags.")
    tags = app_commands.Group(name="tags", description="Atalho para comandos do sistema de tags.")
    cadastro = app_commands.Group(name="cadastro", description="Comandos de cadastro.")
    ravenconquista = app_commands.Group(name="ravenconquista", description="Comandos da conquista Fã do Raven.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def usuario_eh_staff(self, interaction: discord.Interaction) -> bool:
        membro = interaction.user
        guild = interaction.guild
        cargo_staff_id = obter_valor_config(guild, "CARGO_STAFF_ID")
        return any(getattr(cargo, "id", None) == cargo_staff_id for cargo in getattr(membro, "roles", []))

    @staticmethod
    def formatar_numero(valor: int) -> str:
        return f"{int(valor):,}".replace(",", ".")

    @staticmethod
    def criar_barra_progresso(atual: int, total: int, blocos: int = 10) -> str:
        total = max(1, int(total))
        atual = max(0, min(int(atual), total))
        preenchidos = round((atual / total) * blocos)
        preenchidos = max(0, min(preenchidos, blocos))
        return f"{'▰' * preenchidos}{'▱' * (blocos - preenchidos)} {atual}/{total}"

    @staticmethod
    def membro_tem_cargo_por_nome(membro: discord.Member, nome_cargo: str) -> bool:
        return any((getattr(cargo, "name", None) or "") == nome_cargo for cargo in getattr(membro, "roles", []))

    @staticmethod
    def membro_tem_cargo_por_id(membro: discord.Member, cargo_id: int | None) -> bool:
        if not cargo_id:
            return False
        return any(getattr(cargo, "id", None) == int(cargo_id) for cargo in getattr(membro, "roles", []))

    async def responder_sem_permissao(self, interaction: discord.Interaction):
        if interaction.response.is_done():
            await interaction.followup.send("Você não tem permissão para usar esse comando.", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para usar esse comando.", ephemeral=True)

    def montar_texto_conquista_presenca(self, membro: discord.Member, estado: dict, meta: dict) -> str:
        possui_cargo = bool(estado.get("possui_cargo")) or self.membro_tem_cargo_por_nome(membro, meta["cargo_nome"])
        progresso = int(estado.get("progresso", 0) or 0)
        objetivo = int(meta["objetivo"])
        if possui_cargo:
            manutencao = int(estado.get("ausencias_com_cargo", 0) or 0)
            return (
                "Status: Conquistado ✅\n"
                f"Manutenção: {manutencao}/{int(meta['perda_depois_ganhar'])} ausências antes de perder"
            )

        ausencias = int(estado.get("ausencias_seguidas", 0) or 0)
        return (
            f"Progresso: {self.criar_barra_progresso(progresso, objetivo)}\n"
            f"Ausências seguidas: {ausencias}/{int(meta['reset_antes_ganhar'])}\n"
            "Status: Em andamento"
        )

    def montar_texto_conquista_raven(self, membro: discord.Member, estado: dict) -> str:
        possui_cargo = bool(estado.get("possui_cargo")) or self.membro_tem_cargo_por_nome(
            membro,
            CONQUISTA_FA_DO_RAVEN["cargo_nome"],
        )
        progresso = int(estado.get("progresso", 0) or 0)
        objetivo = int(CONQUISTA_FA_DO_RAVEN["objetivo"])
        if possui_cargo:
            faltas = int(estado.get("faltas_com_cargo", 0) or 0)
            return (
                "Status: Conquistado ✅\n"
                f"Manutenção: {faltas}/{int(CONQUISTA_FA_DO_RAVEN['faltas_perda'])} faltas antes de perder"
            )

        faltas = int(estado.get("faltas_antes_cargo", 0) or 0)
        return (
            f"Progresso: {self.criar_barra_progresso(progresso, objetivo)}\n"
            f"Faltas: {faltas}/{int(CONQUISTA_FA_DO_RAVEN['faltas_reset'])}\n"
            "Status: Em andamento"
        )

    async def montar_texto_xp_conquistas(self, membro: discord.Member) -> str:
        dados = carregar_dados_xp()
        estado = obter_estado_xp_usuario(dados, membro.guild, membro.id, criar=True)
        resetar_xp_diario_se_preciso(estado)
        salvar_dados_xp(dados)

        xp_total = int(estado.get("xp_total", 0) or 0)
        xp_diario = int(estado.get("xp_diario", 0) or 0)
        cargo_atual = estado.get("cargo_atual")
        proxima_role_key, proxima_meta = obter_proxima_meta_xp(xp_total)
        cargos = await self.obter_cargos_xp(membro.guild)
        cargo_atual_nome = getattr(cargos.get(cargo_atual), "name", "nenhum") if cargo_atual else "nenhum"
        if proxima_meta is None:
            proxima_meta_texto = "cargo máximo alcançado."
        else:
            proximo_nome = getattr(cargos.get(proxima_role_key), "name", proxima_role_key or "desconhecido")
            proxima_meta_texto = f"{self.formatar_numero(int(proxima_meta))} XP — {proximo_nome}"

        limite_diario = int(obter_valor_config(membro.guild, "XP_DAILY_LIMIT", 700))
        return (
            f"XP total: {self.formatar_numero(xp_total)}\n"
            f"XP diário: {xp_diario}/{limite_diario}\n"
            f"Cargo atual: {cargo_atual_nome}\n"
            f"Próxima meta: {proxima_meta_texto}"
        )

    def montar_texto_mensageiro(self, membro: discord.Member) -> str:
        dados = carregar_dados_conquistas()
        estado = obter_estado_mensageiro(dados, membro.guild, membro.id, criar=True)
        salvar_dados_conquistas(dados)

        cargo_id = int(
            obter_valor_config(
                membro.guild,
                "MENSAGEIRO_DA_NOITE_ROLE_ID",
                MENSAGEIRO_DA_NOITE_ROLE_ID,
            ) or MENSAGEIRO_DA_NOITE_ROLE_ID
        )
        objetivo = int(CONQUISTA_MENSAGEIRO_DA_NOITE["objetivo"])
        conquistado = bool(estado.get("possui_cargo")) or self.membro_tem_cargo_por_id(membro, cargo_id)
        pontos = objetivo if conquistado else min(objetivo, int(estado.get("progresso", 0) or 0))
        status = "Conquistado ✅" if conquistado else "Em andamento"
        return f"Pontos: {self.criar_barra_progresso(pontos, objetivo)}\nStatus: {status}"

    def montar_texto_npc_sem_quest(self, membro: discord.Member) -> str | None:
        cargo_id = int(
            obter_valor_config(
                membro.guild,
                "NPC_SEM_QUEST_ROLE_ID",
                NPC_SEM_QUEST_ROLE_ID,
            ) or NPC_SEM_QUEST_ROLE_ID
        )
        if not self.membro_tem_cargo_por_id(membro, cargo_id):
            return None
        return "Status: Ativo\nMensagem: Você está com o cargo 𓆩✦ NPC sem quest ✦𓆪."

    async def criar_embed_conquistas(self, membro: discord.Member) -> discord.Embed:
        dados_conquistas = carregar_dados_conquistas()
        membros_guild = (
            dados_conquistas
            .get("guilds", {})
            .get(str(membro.guild.id), {})
            .get("membros", {})
        )
        dados_membro = membros_guild.get(str(membro.id), {}) if isinstance(membros_guild, dict) else {}

        embed = discord.Embed(
            title="🏆 Progresso de Conquistas",
            description=f"Aqui está o progresso atual de {membro.mention} nas conquistas da FDN.",
            color=0x00FFFF,
        )

        linhas_presenca = []
        for tipo in ("invasao", "jogatina", "cinema"):
            meta = CONQUISTAS_PRESENCA[tipo]
            estado = dados_membro.get(meta["tipo"], {}) if isinstance(dados_membro, dict) else {}
            linhas_presenca.append(
                f"**{meta['cargo_nome']}**\n{self.montar_texto_conquista_presenca(membro, estado, meta)}"
            )
        embed.add_field(name="Presença em eventos", value="\n\n".join(linhas_presenca), inline=False)

        estado_raven = obter_estado_fa_do_raven(dados_conquistas, membro.guild, membro.id, criar=True)
        embed.add_field(
            name=CONQUISTA_FA_DO_RAVEN["cargo_nome"],
            value=self.montar_texto_conquista_raven(membro, estado_raven),
            inline=False,
        )
        embed.add_field(name="XP do chat", value=await self.montar_texto_xp_conquistas(membro), inline=False)
        embed.add_field(name="𓆩✦ Mensageiro da Noite ✦𓆪", value=self.montar_texto_mensageiro(membro), inline=False)

        texto_npc = self.montar_texto_npc_sem_quest(membro)
        if texto_npc:
            embed.add_field(name="💀 NPC sem quest", value=texto_npc, inline=False)

        embed.set_footer(text="FDN — Sistema de Conquistas")
        return embed

    def criar_embed_status_raven(self, membro: discord.Member, estado: dict):
        possui_cargo = bool(estado.get("possui_cargo"))
        faltas = int(estado.get("faltas_com_cargo", 0) or 0) if possui_cargo else int(estado.get("faltas_antes_cargo", 0) or 0)
        limite_faltas = CONQUISTA_FA_DO_RAVEN["faltas_perda"] if possui_cargo else CONQUISTA_FA_DO_RAVEN["faltas_reset"]
        status = "Conquista alcançada!" if possui_cargo else "Em andamento"

        embed = discord.Embed(
            title="🐦‍⬛ Progresso Fã do Raven",
            description=f"{membro.mention} no acompanhamento atual da conquista.",
            color=discord.Color.from_rgb(0, 255, 255),
        )
        embed.add_field(name="Membro", value=membro.mention, inline=False)
        embed.add_field(name="Progresso", value=f"{int(estado.get('progresso', 0) or 0)}/{CONQUISTA_FA_DO_RAVEN['objetivo']}", inline=True)
        embed.add_field(name="Faltas", value=f"{faltas}/{limite_faltas}", inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Possui cargo", value="Sim" if possui_cargo else "Não", inline=True)
        embed.add_field(name="Última resposta válida", value=formatar_data_iso_local(estado.get("ultima_resposta_valida")), inline=True)
        embed.set_footer(text="FDN • Conquista Fã do Raven")
        return embed

    async def obter_cargo_fa_do_raven(self, guild: discord.Guild):
        if guild is None:
            return None
        for cargo in getattr(guild, "roles", []) or []:
            if getattr(cargo, "name", None) == CONQUISTA_FA_DO_RAVEN["cargo_nome"]:
                return cargo
        try:
            cargos = await guild.fetch_roles()
        except Exception:
            return None
        return discord.utils.get(cargos, name=CONQUISTA_FA_DO_RAVEN["cargo_nome"])

    async def obter_cargos_xp(self, guild: discord.Guild):
        role_ids = dict(obter_valor_config(guild, "XP_ROLE_IDS", {}))
        cargos = {}
        for role_key, role_id in role_ids.items():
            cargo = guild.get_role(int(role_id)) if guild and role_id else None
            if cargo is None and guild and role_id:
                try:
                    roles = await guild.fetch_roles()
                    cargo = discord.utils.get(roles, id=int(role_id))
                except Exception:
                    cargo = None
            cargos[role_key] = cargo
        return cargos

    async def sincronizar_cargos_xp(self, membro: discord.Member, role_key_novo):
        cargos = await self.obter_cargos_xp(membro.guild)
        cargo_adicionado = False
        cargos_para_remover = [
            cargo
            for chave, cargo in cargos.items()
            if cargo is not None and chave != role_key_novo and cargo in getattr(membro, "roles", [])
        ]
        if cargos_para_remover:
            try:
                await membro.remove_roles(*cargos_para_remover, reason="Correção manual de XP")
            except Exception:
                pass

        cargo_novo = cargos.get(role_key_novo)
        if role_key_novo and cargo_novo is not None and cargo_novo not in getattr(membro, "roles", []):
            try:
                await membro.add_roles(cargo_novo, reason="Correção manual de XP")
            except Exception:
                return cargo_novo, False
            cargo_adicionado = True
        return cargo_novo, cargo_adicionado

    async def criar_embed_status_xp(self, membro: discord.Member):
        dados = carregar_dados_xp()
        estado = obter_estado_xp_usuario(dados, membro.guild, membro.id, criar=True)
        resetar_xp_diario_se_preciso(estado)
        salvar_dados_xp(dados)

        xp_total = int(estado.get("xp_total", 0) or 0)
        xp_diario = int(estado.get("xp_diario", 0) or 0)
        cargo_atual = estado.get("cargo_atual")
        proxima_role_key, proxima_meta = obter_proxima_meta_xp(xp_total)
        cargos = await self.obter_cargos_xp(membro.guild)
        cargo_atual_nome = getattr(cargos.get(cargo_atual), "name", "nenhum") if cargo_atual else "nenhum"
        proxima_meta_nome = (
            getattr(cargos.get(proxima_role_key), "name", proxima_role_key)
            if proxima_role_key else "cargo máximo alcançado."
        )

        embed = discord.Embed(
            title="🐦‍⬛ Sistema de XP",
            description=membro.mention,
            color=discord.Color.from_rgb(0, 255, 255),
        )
        embed.add_field(name="XP total", value=f"{xp_total:,}".replace(",", "."), inline=True)
        embed.add_field(name="XP diário", value=f"{xp_diario}/{int(obter_valor_config(membro.guild, 'XP_DAILY_LIMIT', 700))}", inline=True)
        embed.add_field(name="Cargo atual", value=cargo_atual_nome, inline=False)
        if proxima_meta is None:
            embed.add_field(name="Próxima meta", value="cargo máximo alcançado.", inline=False)
        else:
            embed.add_field(
                name="Próxima meta",
                value=f"{int(proxima_meta):,} XP — {proxima_meta_nome}".replace(",", "."),
                inline=False,
            )
        embed.set_footer(text="FDN • Sistema de XP")
        return embed

    def criar_embed_ranking_xp(self, guild, ranking):
        linhas = []
        for indice, (user_id, xp_total) in enumerate(ranking, start=1):
            membro_rank = guild.get_member(int(user_id)) if guild else None
            nome = getattr(membro_rank, "display_name", f"ID {user_id}")
            linhas.append(f"{indice}. {nome} — {int(xp_total):,} XP".replace(",", "."))

        embed = discord.Embed(
            title="🏆 Ranking de XP",
            description="\n".join(linhas) if linhas else "Ainda não há XP registrado no servidor.",
            color=discord.Color.from_rgb(0, 255, 255),
        )
        embed.set_footer(text="FDN • Sistema de XP")
        return embed

    async def executar_prefixo(
        self,
        interaction: discord.Interaction,
        nome_comando: str,
        *args,
        ephemeral: bool = False,
        sucesso_silencioso: str | None = None,
    ):
        if interaction.guild is None:
            if interaction.response.is_done():
                await interaction.followup.send("Esse comando só pode ser usado em servidor.", ephemeral=True)
            else:
                await interaction.response.send_message("Esse comando só pode ser usado em servidor.", ephemeral=True)
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=ephemeral, thinking=True)

            comando = self.bot.get_command(nome_comando)
            if comando is None:
                await interaction.followup.send("Comando interno não encontrado.", ephemeral=True)
                return

            ctx = SlashContextAdapter(interaction, ephemeral=ephemeral)

            if comando.cog is not None:
                await comando.callback(comando.cog, ctx, *args)
            else:
                await comando.callback(ctx, *args)

            if ctx.sent_count == 0 and sucesso_silencioso:
                await interaction.followup.send(sucesso_silencioso, ephemeral=True)

        except Exception:
            traceback.print_exc()
            if interaction.response.is_done():
                await interaction.followup.send("Ocorreu um erro ao executar o comando.", ephemeral=True)
            else:
                await interaction.response.send_message("Ocorreu um erro ao executar o comando.", ephemeral=True)

    @app_commands.command(name="ajuda", description="Mostra a central de ajuda da staff.")
    @app_commands.describe(categoria="Categoria da ajuda. Exemplo: tag, rec, reacao, frase ou gatilho.")
    async def slash_ajuda(self, interaction: discord.Interaction, categoria: str | None = None):
        await self.executar_prefixo(interaction, "ajuda", categoria)

    @app_commands.command(name="help", description="Atalho para a central de ajuda da staff.")
    @app_commands.describe(categoria="Categoria da ajuda. Exemplo: tag, rec, reacao, frase ou gatilho.")
    async def slash_help(self, interaction: discord.Interaction, categoria: str | None = None):
        await self.executar_prefixo(interaction, "ajuda", categoria)

    @app_commands.command(name="limpar", description="Limpa mensagens do canal atual.")
    @app_commands.describe(quantidade="Quantidade de mensagens que devem ser removidas.")
    async def slash_limpar(self, interaction: discord.Interaction, quantidade: int):
        await self.executar_prefixo(interaction, "limpar", str(quantidade), ephemeral=True)

    @app_commands.command(name="clear", description="Atalho para limpar mensagens do canal atual.")
    @app_commands.describe(quantidade="Quantidade de mensagens que devem ser removidas.")
    async def slash_clear(self, interaction: discord.Interaction, quantidade: int):
        await self.executar_prefixo(interaction, "limpar", str(quantidade), ephemeral=True)

    @app_commands.command(name="conselho", description="Envia um conselho no canal geral.")
    async def slash_conselho(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "conselho", ephemeral=True)

    @app_commands.command(name="interagir", description="Envia uma mensagem de interação no canal geral.")
    async def slash_interagir(self, interaction: discord.Interaction):
        await self.executar_prefixo(
            interaction,
            "interagir",
            sucesso_silencioso="✅ Mensagem de interação enviada.",
        )

    @app_commands.command(name="recrutar", description="Envia uma mensagem para recrutadores.")
    async def slash_recrutar(self, interaction: discord.Interaction):
        await self.executar_prefixo(
            interaction,
            "recrutar",
            ephemeral=True,
            sucesso_silencioso="✅ Mensagem de recrutamento enviada.",
        )

    @app_commands.command(name="reacao", description="Envia aviso para reagirem em um canal.")
    @app_commands.describe(destino="Destino do aviso.")
    @app_commands.choices(destino=[
        app_commands.Choice(name="jogatina", value="jogatina"),
        app_commands.Choice(name="invasao", value="invasao"),
        app_commands.Choice(name="cronograma", value="cronograma"),
        app_commands.Choice(name="avisos", value="avisos"),
    ])
    async def slash_reacao(self, interaction: discord.Interaction, destino: app_commands.Choice[str]):
        await self.executar_prefixo(interaction, "reação", "em", destino.value, ephemeral=True)

    @app_commands.command(name="responderaven", description="Responde uma menção antiga ao Raven.")
    @app_commands.describe(
        id_mensagem="ID da mensagem que será respondida.",
        opcao_frase="Número da frase pronta, se quiser usar uma resposta específica.",
    )
    async def slash_responderaven(
        self,
        interaction: discord.Interaction,
        id_mensagem: str,
        opcao_frase: int | None = None,
    ):
        await self.executar_prefixo(
            interaction,
            "responderaven",
            id_mensagem,
            str(opcao_frase) if opcao_frase is not None else None,
            ephemeral=True,
        )

    @app_commands.command(name="bemvindo", description="Envia boas-vindas manualmente no canal geral.")
    @app_commands.describe(membro="Membro que receberá as boas-vindas.")
    async def slash_bemvindo(self, interaction: discord.Interaction, membro: discord.Member):
        await self.executar_prefixo(interaction, "bemvindo", str(membro.id), ephemeral=True)

    @app_commands.command(name="boasvindas", description="Atalho para enviar boas-vindas manualmente.")
    @app_commands.describe(membro="Membro que receberá as boas-vindas.")
    async def slash_boasvindas(self, interaction: discord.Interaction, membro: discord.Member):
        await self.executar_prefixo(interaction, "bemvindo", str(membro.id), ephemeral=True)

    @app_commands.command(name="aniversario", description="Salva o aniversário de até 5 membros.")
    @app_commands.describe(
        membro1="Primeiro aniversariante.",
        dia="Dia do aniversário.",
        mes="Mês do aniversário.",
        membro2="Segundo aniversariante (opcional).",
        membro3="Terceiro aniversariante (opcional).",
        membro4="Quarto aniversariante (opcional).",
        membro5="Quinto aniversariante (opcional).",
    )
    @app_commands.choices(
        mes=[
            app_commands.Choice(name="Janeiro", value=1),
            app_commands.Choice(name="Fevereiro", value=2),
            app_commands.Choice(name="Março", value=3),
            app_commands.Choice(name="Abril", value=4),
            app_commands.Choice(name="Maio", value=5),
            app_commands.Choice(name="Junho", value=6),
            app_commands.Choice(name="Julho", value=7),
            app_commands.Choice(name="Agosto", value=8),
            app_commands.Choice(name="Setembro", value=9),
            app_commands.Choice(name="Outubro", value=10),
            app_commands.Choice(name="Novembro", value=11),
            app_commands.Choice(name="Dezembro", value=12),
        ]
    )
    async def slash_aniversario(
        self,
        interaction: discord.Interaction,
        membro1: discord.Member,
        dia: int,
        mes: app_commands.Choice[int],
        membro2: discord.Member | None = None,
        membro3: discord.Member | None = None,
        membro4: discord.Member | None = None,
        membro5: discord.Member | None = None,
    ):
        await self.executar_prefixo(
            interaction,
            "aniversario",
            membro1,
            dia,
            mes.value,
            membro2,
            membro3,
            membro4,
            membro5,
            ephemeral=True,
        )

    @app_commands.command(name="listadeaniversarios", description="Mostra a lista de aniversários de um mês.")
    @app_commands.describe(mes="Mês que você quer consultar.")
    @app_commands.choices(
        mes=[
            app_commands.Choice(name="Janeiro", value=1),
            app_commands.Choice(name="Fevereiro", value=2),
            app_commands.Choice(name="Março", value=3),
            app_commands.Choice(name="Abril", value=4),
            app_commands.Choice(name="Maio", value=5),
            app_commands.Choice(name="Junho", value=6),
            app_commands.Choice(name="Julho", value=7),
            app_commands.Choice(name="Agosto", value=8),
            app_commands.Choice(name="Setembro", value=9),
            app_commands.Choice(name="Outubro", value=10),
            app_commands.Choice(name="Novembro", value=11),
            app_commands.Choice(name="Dezembro", value=12),
        ]
    )
    async def slash_listadeaniversarios(self, interaction: discord.Interaction, mes: app_commands.Choice[int]):
        await self.executar_prefixo(interaction, "listadeaniversarios", mes.value, ephemeral=True)

    @app_commands.command(name="atualizaraniversariohoje", description="Consolida a mensagem de aniversário de hoje.")
    async def slash_atualizaraniversariohoje(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "atualizaraniversariohoje", ephemeral=True)

    @rec.command(name="ranking", description="Mostra o ranking de recrutadores do mês.")
    async def slash_rec_ranking(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "rec", "ranking")

    @rec.command(name="info", description="Mostra os recrutamentos de um membro.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_rec_info(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "rec", "info", nome)

    @rec.command(name="add", description="Adiciona recrutamentos manualmente.")
    @app_commands.describe(
        nome="Nome, menção ou ID do recrutador.",
        quantidade="Quantidade de recrutamentos.",
        recrutado="Nome do recrutado, se quiser registrar.",
    )
    async def slash_rec_add(
        self,
        interaction: discord.Interaction,
        nome: str,
        quantidade: int,
        recrutado: str | None = None,
    ):
        args = ["add", nome, str(quantidade)]
        if recrutado:
            args.append(recrutado)
        await self.executar_prefixo(interaction, "rec", *args, ephemeral=True)

    @rec.command(name="addmsg", description="Adiciona recrutamento usando uma mensagem antiga de +1.")
    @app_commands.describe(id_mensagem="ID da mensagem antiga.")
    async def slash_rec_addmsg(self, interaction: discord.Interaction, id_mensagem: str):
        await self.executar_prefixo(interaction, "rec", "addmsg", id_mensagem, ephemeral=True)

    @rec.command(name="remove", description="Remove o último recrutamento de um membro.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_rec_remove(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "rec", "remove", nome, ephemeral=True)

    @rec.command(name="resetmes", description="Reseta os recrutamentos do mês atual.")
    async def slash_rec_resetmes(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "rec", "resetmes", ephemeral=True)

    @recrutamento.command(name="ranking", description="Mostra o ranking de recrutadores do mês.")
    async def slash_recrutamento_ranking(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "rec", "ranking")

    @recrutamento.command(name="info", description="Mostra os recrutamentos de um membro.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_recrutamento_info(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "rec", "info", nome)

    @recrutamento.command(name="add", description="Adiciona recrutamentos manualmente.")
    @app_commands.describe(
        nome="Nome, menção ou ID do recrutador.",
        quantidade="Quantidade de recrutamentos.",
        recrutado="Nome do recrutado, se quiser registrar.",
    )
    async def slash_recrutamento_add(
        self,
        interaction: discord.Interaction,
        nome: str,
        quantidade: int,
        recrutado: str | None = None,
    ):
        args = ["add", nome, str(quantidade)]
        if recrutado:
            args.append(recrutado)
        await self.executar_prefixo(interaction, "rec", *args, ephemeral=True)

    @recrutamento.command(name="addmsg", description="Adiciona recrutamento usando uma mensagem antiga de +1.")
    @app_commands.describe(id_mensagem="ID da mensagem antiga.")
    async def slash_recrutamento_addmsg(self, interaction: discord.Interaction, id_mensagem: str):
        await self.executar_prefixo(interaction, "rec", "addmsg", id_mensagem, ephemeral=True)

    @recrutamento.command(name="remove", description="Remove o último recrutamento de um membro.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_recrutamento_remove(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "rec", "remove", nome, ephemeral=True)

    @recrutamento.command(name="resetmes", description="Reseta os recrutamentos do mês atual.")
    async def slash_recrutamento_resetmes(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "rec", "resetmes", ephemeral=True)

    @recrutador.command(name="ranking", description="Mostra o ranking de recrutadores do mês.")
    async def slash_recrutador_ranking(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "rec", "ranking")

    @recrutador.command(name="info", description="Mostra os recrutamentos de um membro.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_recrutador_info(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "rec", "info", nome)

    @recrutador.command(name="add", description="Adiciona recrutamentos manualmente.")
    @app_commands.describe(
        nome="Nome, menção ou ID do recrutador.",
        quantidade="Quantidade de recrutamentos.",
        recrutado="Nome do recrutado, se quiser registrar.",
    )
    async def slash_recrutador_add(
        self,
        interaction: discord.Interaction,
        nome: str,
        quantidade: int,
        recrutado: str | None = None,
    ):
        args = ["add", nome, str(quantidade)]
        if recrutado:
            args.append(recrutado)
        await self.executar_prefixo(interaction, "rec", *args, ephemeral=True)

    @recrutador.command(name="addmsg", description="Adiciona recrutamento usando uma mensagem antiga de +1.")
    @app_commands.describe(id_mensagem="ID da mensagem antiga.")
    async def slash_recrutador_addmsg(self, interaction: discord.Interaction, id_mensagem: str):
        await self.executar_prefixo(interaction, "rec", "addmsg", id_mensagem, ephemeral=True)

    @recrutador.command(name="remove", description="Remove o último recrutamento de um membro.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_recrutador_remove(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "rec", "remove", nome, ephemeral=True)

    @recrutador.command(name="resetmes", description="Reseta os recrutamentos do mês atual.")
    async def slash_recrutador_resetmes(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "rec", "resetmes", ephemeral=True)

    @tag.command(name="lista", description="Mostra quem está pendente de tag.")
    async def slash_tag_lista(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "tag", "lista")

    @tag.command(name="atrasados", description="Mostra membros com tag atrasada.")
    @app_commands.describe(dias="Dias mínimos de atraso. Padrão: 7.")
    async def slash_tag_atrasados(self, interaction: discord.Interaction, dias: int | None = None):
        args = ["atrasados"]
        if dias is not None:
            args.append(str(dias))
        await self.executar_prefixo(interaction, "tag", *args)

    @tag.command(name="info", description="Mostra detalhes de tag de um membro.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_tag_info(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "tag", "info", nome)

    @tag.command(name="concluir", description="Remove um membro da lista de pendentes.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_tag_concluir(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "tag", "concluir", nome, ephemeral=True)

    @tag.command(name="remover", description="Remove um membro da lista sem concluir a tag.")
    @app_commands.describe(nome_ou_id="Nome, menção ou ID do membro.")
    async def slash_tag_remover(self, interaction: discord.Interaction, nome_ou_id: str):
        await self.executar_prefixo(interaction, "tag", "remover", nome_ou_id, ephemeral=True)

    @tag.command(name="adicionar", description="Adiciona um membro manualmente à lista de pendentes.")
    @app_commands.describe(
        nome="Nome, menção ou ID do membro.",
        data="Data manual no formato DD/MM/AAAA.",
    )
    async def slash_tag_adicionar(self, interaction: discord.Interaction, nome: str, data: str | None = None):
        args = ["adicionar", nome]
        if data:
            args.append(data)
        await self.executar_prefixo(interaction, "tag", *args, ephemeral=True)

    @tags.command(name="lista", description="Mostra quem está pendente de tag.")
    async def slash_tags_lista(self, interaction: discord.Interaction):
        await self.executar_prefixo(interaction, "tag", "lista")

    @tags.command(name="atrasados", description="Mostra membros com tag atrasada.")
    @app_commands.describe(dias="Dias mínimos de atraso. Padrão: 7.")
    async def slash_tags_atrasados(self, interaction: discord.Interaction, dias: int | None = None):
        args = ["atrasados"]
        if dias is not None:
            args.append(str(dias))
        await self.executar_prefixo(interaction, "tag", *args)

    @tags.command(name="info", description="Mostra detalhes de tag de um membro.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_tags_info(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "tag", "info", nome)

    @tags.command(name="concluir", description="Remove um membro da lista de pendentes.")
    @app_commands.describe(nome="Nome, menção ou ID do membro.")
    async def slash_tags_concluir(self, interaction: discord.Interaction, nome: str):
        await self.executar_prefixo(interaction, "tag", "concluir", nome, ephemeral=True)

    @tags.command(name="remover", description="Remove um membro da lista sem concluir a tag.")
    @app_commands.describe(nome_ou_id="Nome, menção ou ID do membro.")
    async def slash_tags_remover(self, interaction: discord.Interaction, nome_ou_id: str):
        await self.executar_prefixo(interaction, "tag", "remover", nome_ou_id, ephemeral=True)

    @tags.command(name="adicionar", description="Adiciona um membro manualmente à lista de pendentes.")
    @app_commands.describe(
        nome="Nome, menção ou ID do membro.",
        data="Data manual no formato DD/MM/AAAA.",
    )
    async def slash_tags_adicionar(self, interaction: discord.Interaction, nome: str, data: str | None = None):
        args = ["adicionar", nome]
        if data:
            args.append(data)
        await self.executar_prefixo(interaction, "tag", *args, ephemeral=True)

    @cadastro.command(name="importar", description="Importa uma ficha antiga pelo ID da mensagem.")
    @app_commands.describe(id_mensagem="ID da mensagem da ficha antiga.")
    async def slash_cadastro_importar(self, interaction: discord.Interaction, id_mensagem: str):
        try:
            message_id = int(id_mensagem)
        except ValueError:
            await interaction.response.send_message("O ID da mensagem precisa ser numérico.", ephemeral=True)
            return

        await self.executar_prefixo(interaction, "cadastro importar", message_id, ephemeral=True)

    @cadastro.command(name="ajuda", description="Mostra como importar uma ficha antiga.")
    async def slash_cadastro_ajuda(self, interaction: discord.Interaction):
        await interaction.response.send_message("Use: `/cadastro importar id_mensagem`", ephemeral=True)

    @ravenconquista.command(name="membro", description="Mostra o progresso de um membro em Fã do Raven.")
    @app_commands.describe(membro="Membro que será consultado.")
    async def slash_ravenconquista_membro(self, interaction: discord.Interaction, membro: discord.Member):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        dados = carregar_dados_conquistas()
        estado = obter_estado_fa_do_raven(dados, interaction.guild, membro.id, criar=True)
        await interaction.response.send_message(embed=self.criar_embed_status_raven(membro, estado), ephemeral=True)

    @ravenconquista.command(name="ajustar", description="Ajusta manualmente os dados da conquista Fã do Raven.")
    @app_commands.describe(
        membro="Membro que será ajustado.",
        campo="Campo que será alterado.",
        quantidade="Novo valor do campo.",
    )
    @app_commands.choices(
        campo=[
            app_commands.Choice(name="progresso", value="progresso"),
            app_commands.Choice(name="faltas_antes_cargo", value="faltas_antes_cargo"),
            app_commands.Choice(name="faltas_com_cargo", value="faltas_com_cargo"),
        ]
    )
    async def slash_ravenconquista_ajustar(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        campo: app_commands.Choice[str],
        quantidade: int,
    ):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        dados = carregar_dados_conquistas()
        estado = obter_estado_fa_do_raven(dados, interaction.guild, membro.id, criar=True)
        valor = max(0, int(quantidade))
        if campo.value == "progresso":
            valor = min(CONQUISTA_FA_DO_RAVEN["objetivo"], valor)
        estado[campo.value] = valor
        if campo.value == "progresso":
            cargo = await self.obter_cargo_fa_do_raven(interaction.guild)
            if valor >= CONQUISTA_FA_DO_RAVEN["objetivo"]:
                estado["possui_cargo"] = True
                if cargo is not None and cargo not in getattr(membro, "roles", []):
                    try:
                        await membro.add_roles(cargo, reason="Ajuste manual da conquista Fã do Raven")
                        await enviar_embed_conquista(self.bot, membro, "fa_do_raven", progresso="35/35")
                    except Exception:
                        pass
            else:
                estado["possui_cargo"] = False
                if cargo is not None and cargo in getattr(membro, "roles", []):
                    try:
                        await membro.remove_roles(cargo, reason="Ajuste manual da conquista Fã do Raven")
                    except Exception:
                        pass
        salvar_dados_conquistas(dados)

        embed = self.criar_embed_status_raven(membro, estado)
        embed.description = f"{membro.mention} teve o campo `{campo.value}` ajustado manualmente."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ravenconquista.command(name="resetar", description="Reseta a conquista Fã do Raven de um membro.")
    @app_commands.describe(membro="Membro que será resetado.")
    async def slash_ravenconquista_resetar(self, interaction: discord.Interaction, membro: discord.Member):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        dados = carregar_dados_conquistas()
        estado = obter_estado_fa_do_raven(dados, interaction.guild, membro.id, criar=True)
        estado["progresso"] = 0
        estado["faltas_antes_cargo"] = 0
        estado["faltas_com_cargo"] = 0
        estado["possui_cargo"] = False
        estado["perguntas_respondidas"] = []
        estado["ultima_resposta_valida"] = None
        cargo = await self.obter_cargo_fa_do_raven(interaction.guild)
        if cargo is not None and cargo in getattr(membro, "roles", []):
            try:
                await membro.remove_roles(cargo, reason="Reset manual da conquista Fã do Raven")
            except Exception:
                pass
        salvar_dados_conquistas(dados)

        embed = self.criar_embed_status_raven(membro, estado)
        embed.description = f"{membro.mention} teve a conquista resetada manualmente."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ravenconquista.command(name="processarhoje", description="Força o processamento da pergunta diária de hoje.")
    async def slash_ravenconquista_processarhoje(self, interaction: discord.Interaction):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        events_cog = self.bot.get_cog("EventsCog")
        if events_cog is None:
            await interaction.response.send_message("Não consegui localizar o sistema de eventos do bot.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        total = await events_cog.processar_conquista_fa_do_raven_guild(interaction.guild, forcar=True)
        if total <= 0:
            await interaction.followup.send("Não encontrei pergunta diária pendente para processar agora.", ephemeral=True)
            return

        agora = datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y às %H:%M")
        await interaction.followup.send(
            f"✅ Processamento concluído. Perguntas fechadas agora: `{total}` às `{agora}`.",
            ephemeral=True,
        )

    @app_commands.command(name="conquistas", description="Mostra o progresso geral de conquistas.")
    @app_commands.describe(membro="Membro que será consultado. Apenas staff pode consultar outra pessoa.")
    async def slash_conquistas(self, interaction: discord.Interaction, membro: discord.Member | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("Esse comando só pode ser usado em servidor.", ephemeral=True)
            return

        membro_consultado = membro or interaction.user
        if membro is not None and membro.id != interaction.user.id and not self.usuario_eh_staff(interaction):
            await interaction.response.send_message(
                "Você só pode consultar as suas próprias conquistas.",
                ephemeral=True,
            )
            return

        embed = await self.criar_embed_conquistas(membro_consultado)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="adicionarpontos", description="Adiciona pontos de Mensageiro da Noite para um membro.")
    @app_commands.describe(
        membro="Membro vencedor da votaÃ§Ã£o.",
        quantidade="Quantidade de pontos a adicionar.",
    )
    async def slash_adicionarpontos(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int = 1):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        pontos_solicitados = max(1, abs(int(quantidade or 1)))
        dados = carregar_dados_conquistas()
        resultado = adicionar_pontos_mensageiro(dados, interaction.guild, membro.id, pontos_solicitados)
        salvar_estado_mensageiro(dados)

        cargo_id = int(
            obter_valor_config(
                interaction.guild,
                "MENSAGEIRO_DA_NOITE_ROLE_ID",
                MENSAGEIRO_DA_NOITE_ROLE_ID,
            ) or MENSAGEIRO_DA_NOITE_ROLE_ID
        )
        cargo = interaction.guild.get_role(cargo_id) if interaction.guild else None
        ganhou_cargo = False
        aviso = None

        if resultado.get("conquistado_agora"):
            if cargo is None:
                aviso = "O cargo de Mensageiro da Noite nÃ£o foi encontrado no servidor."
            elif not self.membro_tem_cargo_por_id(membro, cargo_id):
                try:
                    await membro.add_roles(cargo, reason="Conquista manual: Mensageiro da Noite")
                    ganhou_cargo = True
                except discord.HTTPException:
                    aviso = "NÃ£o consegui entregar o cargo automaticamente, mas os pontos foram salvos."

        if ganhou_cargo:
            await enviar_embed_conquista(
                self.bot,
                membro,
                "mensageiro_da_noite",
                progresso=f"{resultado['atual']}/{resultado['objetivo']}",
            )

        embed = await self.criar_embed_conquistas(membro)
        ganho_aplicado = int(resultado.get("ganho_aplicado", 0) or 0)
        if ganho_aplicado <= 0:
            embed.description = f"{membro.mention} jÃ¡ estÃ¡ com a pontuaÃ§Ã£o mÃ¡xima de Mensageiro da Noite."
        else:
            embed.description = (
                f"{membro.mention} recebeu `{ganho_aplicado}` ponto(s) de Mensageiro da Noite.\n"
                f"PontuaÃ§Ã£o atual: `{resultado['atual']}/{resultado['objetivo']}`."
            )
        if aviso:
            embed.add_field(name="Aviso", value=aviso, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="xp", description="Consulta o XP de um membro ou o ranking.")
    @app_commands.describe(
        membro="Membro que você quer consultar.",
        ranking="Marque como verdadeiro para ver o ranking.",
    )
    async def slash_xp(
        self,
        interaction: discord.Interaction,
        membro: discord.Member | None = None,
        ranking: bool = False,
    ):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        if ranking:
            dados = carregar_dados_xp()
            top = ranking_xp(dados, interaction.guild, limite=10)
            if not top:
                await interaction.response.send_message("Ainda não há XP registrado no servidor.", ephemeral=True)
                return
            embed = self.criar_embed_ranking_xp(interaction.guild, top)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if membro is None:
            await interaction.response.send_message(
                "Use `/meuxp` para ver o seu XP ou `/xp membro:@usuario` / `/xp ranking:true` para consulta da staff.",
                ephemeral=True,
            )
            return

        embed = await self.criar_embed_status_xp(membro)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="meuxp", description="Mostra o seu XP.")
    async def slash_meuxp(self, interaction: discord.Interaction):
        canal_xp_id = int(obter_valor_config(interaction.guild, "XP_CHANNEL_ID", XP_CHANNEL_ID) or XP_CHANNEL_ID)
        if getattr(interaction.channel, "id", None) != canal_xp_id:
            await interaction.response.send_message(
                f"Use esse comando apenas em <#{canal_xp_id}>.",
                ephemeral=True,
            )
            return

        chave_cooldown = f"meuxp:{interaction.guild_id}:{interaction.user.id}"
        agora = time.time()
        ultimo_uso = runtime.cooldowns_usuario.get(chave_cooldown, 0)
        cooldown = 30 * 60
        restante = int(cooldown - (agora - ultimo_uso))
        if restante > 0:
            minutos = max(1, (restante + 59) // 60)
            await interaction.response.send_message(
                f"Volte daqui a {minutos} minuto(s) para usar `/meuxp` de novo.",
                ephemeral=True,
            )
            return

        runtime.cooldowns_usuario[chave_cooldown] = agora
        embed = await self.criar_embed_status_xp(interaction.user)
        await interaction.response.send_message(embed=embed)
        try:
            mensagem = await interaction.original_response()
            await mensagem.delete(delay=3600)
            await registrar_exclusao_temporaria(
                origem="/meuxp",
                canal=interaction.channel,
                guild_ou_id=interaction.guild,
                autor=interaction.user,
                delay=3600,
                mensagem_id=getattr(mensagem, "id", None),
                conteudo="Embed publica do /meuxp",
                alvo="embed de XP",
            )
        except (discord.HTTPException, discord.NotFound):
            pass

    @app_commands.command(name="xpranking", description="Mostra o ranking de XP do servidor.")
    async def slash_xpranking(self, interaction: discord.Interaction):
        chave_cooldown = f"xpranking:{interaction.guild_id}:{interaction.user.id}"
        agora = time.time()
        ultimo_uso = runtime.cooldowns_usuario.get(chave_cooldown, 0)
        cooldown = 60 * 60
        restante = int(cooldown - (agora - ultimo_uso))
        if restante > 0:
            minutos = max(1, (restante + 59) // 60)
            await interaction.response.send_message(
                f"Volte daqui a {minutos} minuto(s) para usar `/xpranking` de novo.",
                ephemeral=True,
            )
            return

        dados = carregar_dados_xp()
        top = ranking_xp(dados, interaction.guild, limite=10)
        if not top:
            await interaction.response.send_message("Ainda não há XP registrado no servidor.", ephemeral=True)
            return
        runtime.cooldowns_usuario[chave_cooldown] = agora
        await interaction.response.send_message(
            embed=self.criar_embed_ranking_xp(interaction.guild, top),
        )

    @app_commands.command(name="xpadicionar", description="Adiciona XP manualmente para um membro.")
    @app_commands.describe(membro="Membro que receberá o XP.", quantidade="Quantidade de XP a adicionar.")
    async def slash_xpadicionar(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        dados = carregar_dados_xp()
        resultado = adicionar_xp_manual(dados, interaction.guild, membro.id, abs(int(quantidade)))
        salvar_dados_xp(dados)
        _, cargo_ganho = await self.sincronizar_cargos_xp(membro, resultado.get("role_key_novo"))
        if cargo_ganho:
            await enviar_embed_conquista(self.bot, membro, resultado.get("role_key_novo"))
        embed = await self.criar_embed_status_xp(membro)
        embed.description = f"{membro.mention} recebeu `{abs(int(quantidade))}` XP manualmente."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="xpremover", description="Remove XP manualmente de um membro.")
    @app_commands.describe(membro="Membro que perderá o XP.", quantidade="Quantidade de XP a remover.")
    async def slash_xpremover(self, interaction: discord.Interaction, membro: discord.Member, quantidade: int):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        dados = carregar_dados_xp()
        resultado = remover_xp_manual(dados, interaction.guild, membro.id, abs(int(quantidade)))
        salvar_dados_xp(dados)
        await self.sincronizar_cargos_xp(membro, resultado.get("role_key_novo"))
        embed = await self.criar_embed_status_xp(membro)
        embed.description = f"{membro.mention} perdeu `{abs(int(quantidade))}` XP manualmente."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="xpresetar", description="Reseta o XP de um membro.")
    @app_commands.describe(membro="Membro que terá o XP resetado.")
    async def slash_xpresetar(self, interaction: discord.Interaction, membro: discord.Member):
        if not self.usuario_eh_staff(interaction):
            await self.responder_sem_permissao(interaction)
            return

        dados = carregar_dados_xp()
        resetar_xp_usuario(dados, interaction.guild, membro.id)
        salvar_dados_xp(dados)
        await self.sincronizar_cargos_xp(membro, None)
        embed = await self.criar_embed_status_xp(membro)
        embed.description = f"{membro.mention} teve o XP resetado manualmente."
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashBridgeCog(bot))
