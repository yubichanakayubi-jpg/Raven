from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from config import FUSO_HORARIO
from services.candidaturas import (
    atualizar_candidatura,
    gerar_id_candidatura,
    obter_candidatura,
    obter_candidatura_por_message_id,
    salvar_candidatura,
)
from services.server_config import obter_valor_config
from utils.discord_helpers import membro_eh_staff


APPLICATION_COLOR = discord.Color.from_rgb(0, 255, 255)
APPLICATION_FOOTER = "FDN - Sistema de Candidaturas"
DEFAULT_ANALYSIS_CHANNEL_ID = 1462901201069932544
FINAL_STATUSES = {"Aprovado", "Reprovado"}
DISCORD_PAYLOAD_TOO_LARGE_CODE = 40005


STAFF_SUPORTE_QUESTIONS = [
    "Um membro novo acabou de entrar no servidor e parece perdido. Como você receberia essa pessoa e explicaria o básico da FDN?",
    "Um membro faz uma pergunta que já está respondida nas regras, mas ele não viu. Como você responderia sem parecer grosso ou impaciente?",
    "Dois membros começam uma discussão em um canal público. O que você faria primeiro como Suporte?",
    "Um membro faz uma brincadeira que deixou outra pessoa desconfortável, mas ele diz que “era só brincadeira”. Como você lidaria com isso?",
    "Durante uma call, um membro começa a gritar, falar coisas ofensivas ou atrapalhar a conversa. Como você agiria?",
    "Um membro começa a divulgar outro servidor ou mandar links sem autorização. O que você faria?",
    "Um membro questiona uma decisão da staff em público e começa a gerar discussão. Como você orientaria essa pessoa?",
    "Você chamou atenção de um membro com educação, mas ele ignorou, debochou ou continuou fazendo errado. Qual seria seu próximo passo?",
    "Um membro conta uma informação pessoal de outra pessoa no chat. Como você agiria nessa situação?",
    "Na sua visão, qual é a diferença entre orientar um membro e tentar mandar nele?",
]

STAFF_MODERADOR_QUESTIONS = [
    "Por que você quer ser Moderador de Chat da FDN?",
    "Um membro começa a mandar várias mensagens repetidas no chat, atrapalhando a conversa. Como você agiria?",
    "Um membro faz uma ofensa direta contra outro membro no chat. Qual seria sua atitude?",
    "Dois membros começam uma discussão pública e outros membros começam a se envolver. Como você controlaria a situação?",
    "Um membro faz uma “brincadeira” que claramente deixou outra pessoa desconfortável. Como você avaliaria se deve apenas orientar ou aplicar punição?",
    "Você percebe que um amigo seu quebrou uma regra no chat. Como você lidaria com isso?",
    "Um membro questiona uma punição em público e começa a dizer que a staff é injusta. O que você faria?",
    "Um membro apaga mensagens depois de causar confusão, tentando esconder o que fez. Como você agiria?",
    "Quando uma situação deve ser resolvida por você e quando deve ser levada para um ADM responsável?",
    "Na sua opinião, o que um Moderador de Chat nunca deve fazer ao lidar com membros?",
]

STAFF_MODERADOR_CALL_QUESTIONS = [
    "Por que você quer ser Moderador de Call da FDN?",
    "Durante uma call, um membro começa a gritar muito e atrapalhar a conversa dos outros. Como você agiria?",
    "Dois membros começam uma discussão em call e o clima fica pesado. O que você faria para controlar a situação?",
    "Um membro faz uma brincadeira em call que deixa outra pessoa desconfortável, mas diz que era só zoeira. Como você lidaria com isso?",
    "Um membro começa a falar coisas ofensivas ou desrespeitosas durante uma call. Qual seria sua atitude?",
    "Você percebe que um amigo seu está atrapalhando a call ou quebrando uma regra. Como você agiria?",
    "Um membro não aceita sua orientação, debocha ou continua atrapalhando mesmo após ser avisado. Qual seria seu próximo passo?",
    "Em qual situação você acha que um Moderador de Call deve aplicar uma ação leve, como mover, silenciar ou chamar atenção? Explique.",
    "Quando uma situação em call deve ser resolvida por você e quando deve ser levada para um ADM ou para a liderança?",
    "Na sua opinião, o que um Moderador de Call nunca deve fazer ao lidar com membros em uma chamada?",
]

STAFF_ORGANIZADOR_QUESTIONS = [
    "Por que você quer ser Organizador da FDN?",
    "Uma invasão vai acontecer amanhã em um mapa de dança. Como você começaria a organizar os membros antes do evento?",
    "Como você faria para explicar uma formação para membros que estão confusos ou não entenderam onde devem ficar?",
    "Durante a invasão, um membro fica saindo da posição toda hora e atrapalhando o alinhamento. O que você faria?",
    "Um membro sai do jogo no meio da invasão e deixa um espaço vazio na formação. Como você reorganizaria o grupo?",
    "Dois membros querem ficar juntos na invasão, mas na formação atual não tem espaço para os dois ficarem lado a lado sem bagunçar o alinhamento. Como você lidaria com essa situação?",
    "A liderança pede uma formação bonita e organizada para uma apresentação de dança. Que tipo de formação você pensaria e por quê?",
    "Durante a invasão, alguns membros estão animados e conversando, mas começam a se distrair no momento de alinhar ou trocar de formação. Como você chamaria a atenção sem cortar o clima divertido do evento?",
    "Durante uma invasão, a formação precisa ser ajustada rapidamente porque o mapa, o espaço ou a quantidade de membros mudou. Como você reorganizaria os membros sem causar confusão?",
    "Na sua opinião, o que um Organizador nunca deve fazer durante uma invasão?",
]

STAFF_ADMINISTRADOR_QUESTIONS = [
    "Por que você quer ser Administrador da FDN?",
    "Um Moderador ou Suporte está agindo de forma errada, sendo grosso com membros ou usando o cargo de forma inadequada. Como você lidaria com essa situação?",
    "Um membro causa problemas com frequência, mas sempre tenta justificar dizendo que foi brincadeira. Como você avaliaria se deve apenas orientar ou aplicar advertência?",
    "Dois membros da staff discordam publicamente sobre uma decisão tomada. Como você agiria para manter a organização e evitar exposição da equipe?",
    "Você percebe que o clã está ficando parado, com pouca participação em eventos, jogatinas ou invasões. O que você faria para ajudar a movimentar o clã?",
    "Um membro se destaca bastante, ajuda o clã e parece ter potencial para subir de cargo. Como você avaliaria se deve recomendar essa pessoa para a liderança?",
    "Um membro questiona uma advertência aplicada por você e começa a dizer que foi injusto. Como você responderia?",
    "Uma situação começa pequena, mas se repete várias vezes com o mesmo membro. Quando você levaria esse caso para o Sub-Líder ou Líder?",
    "Como você garantiria que Moderadores e Suporte estejam seguindo o padrão da FDN sem parecer autoritário ou controlador demais?",
    "Na sua opinião, o que um Administrador nunca deve fazer dentro da staff?",
]

NUCLEO_RECRUTADOR_QUESTIONS = [
    "Por que você quer ser Recrutador da FDN?",
    "Como você abordaria uma pessoa nova sem parecer invasivo ou insistente?",
    "O que você faria se alguém demonstrasse interesse na FDN, mas estivesse inseguro sobre entrar?",
    "Como você explicaria a proposta da FDN para alguém que ainda não conhece o clã?",
    "Na sua opinião, o que um Recrutador nunca deve fazer ao conversar com possíveis membros?",
]

NUCLEO_FILMMAKER_QUESTIONS = [
    "Por que você quer ser Filmmaker da FDN?",
    "Você grava pelo celular ou PC? A qualidade da sua gravação é boa?",
    "Você se considera ativo no clã? Teria disponibilidade para participar das invasões e eventos quando fosse necessário gravar?",
    "Durante uma invasão, como você faria para gravar de forma organizada sem atrapalhar a formação ou a experiência dos membros?",
    "Se você não pudesse comparecer a uma invasão ou entregar uma gravação combinada, o que faria?",
]

NUCLEO_TIKTOK_QUESTIONS = [
    "Seu perfil no TikTok tem pelo menos 1.000 seguidores? Se sim, envie o @ do perfil.",
    "Você se considera um membro ativo no clã?",
    "Você já se envolveu em alguma situação, polêmica ou exposição no TikTok que poderia afetar sua imagem ou a imagem da FDN? Se sim, explique.",
    "Você entende que, ao fazer parte do Núcleo de TikTok, precisará postar vídeos representando o clã de vez em quando?",
    "A FDN possui um canal de collabs para membros chamarem outras pessoas para gravar juntos. Você usaria esse canal para combinar gravações e criar conteúdos com o clã?",
]


ROLE_DEFINITIONS = {
    "suporte": {
        "categoria_key": "staff",
        "categoria_nome": "Staff",
        "cargo_nome": "𓆩✦ Suporte ✦𓆪",
        "questions": STAFF_SUPORTE_QUESTIONS,
        "criterios": "Educação, paciência, comunicação, bom senso, respeito à hierarquia, saber chamar moderação e maturidade.",
        "requires_attachment": False,
    },
    "moderador_chat": {
        "categoria_key": "staff",
        "categoria_nome": "Staff",
        "cargo_nome": "𓆩✦ Moderador de Chat ✦𓆪",
        "questions": STAFF_MODERADOR_QUESTIONS,
        "criterios": "Controle emocional, imparcialidade, responsabilidade, conhecimento das regras, comunicação clara, bom senso para punições leves e saber quando chamar ADM.",
        "requires_attachment": False,
    },
    "moderador_call": {
        "categoria_key": "staff",
        "categoria_nome": "Staff",
        "cargo_nome": "𓆩✆ Moderador de Call ✆𓆪",
        "questions": STAFF_MODERADOR_CALL_QUESTIONS,
        "criterios": "Controle de call, postura, imparcialidade, firmeza, bom senso, respeito aos membros e saber quando escalar para ADM ou liderança.",
        "requires_attachment": False,
    },
    "organizador": {
        "categoria_key": "staff",
        "categoria_nome": "Staff",
        "cargo_nome": "𓆩✧ Organizador ✧𓆪",
        "questions": STAFF_ORGANIZADOR_QUESTIONS,
        "criterios": "Organização, criatividade, liderança, comunicação clara, paciência, atividade nas invasões, saber orientar sem ser autoritário e saber criar formações.",
        "requires_attachment": True,
    },
    "administrador": {
        "categoria_key": "staff",
        "categoria_nome": "Staff",
        "cargo_nome": "𓆩✦ Administrador ✦𓆪",
        "questions": STAFF_ADMINISTRADOR_QUESTIONS,
        "criterios": "Liderança, imparcialidade, responsabilidade, controle emocional, bom senso para aplicar advertências, capacidade de supervisionar staff, saber resolver problemas do dia a dia, saber quando chamar Sub-Líder ou Líder, iniciativa para movimentar o clã e respeito à hierarquia.",
        "requires_attachment": False,
    },
    "recrutador": {
        "categoria_key": "nucleo",
        "categoria_nome": "Núcleo",
        "cargo_nome": "𓆩🜂 Recrutador 🜂𓆪",
        "questions": NUCLEO_RECRUTADOR_QUESTIONS,
        "criterios": "Comunicação, paciência, postura, clareza, respeito e bom senso ao recrutar.",
        "requires_attachment": False,
    },
    "filmmaker": {
        "categoria_key": "nucleo",
        "categoria_nome": "Núcleo",
        "cargo_nome": "𓆩✧ Filmmaker ✧𓆪",
        "questions": NUCLEO_FILMMAKER_QUESTIONS,
        "criterios": "Atividade, qualidade de gravação, organização durante eventos, responsabilidade com entregas e postura dentro do clã.",
        "requires_attachment": False,
        "optional_attachment": True,
        "attachment_prompt": (
            "Se quiser, envie aqui no privado um exemplo de gravação, teste ou anexo mostrando a qualidade do seu vídeo.\n\n"
            "Essa etapa é opcional. Se não quiser enviar agora, digite `pular` para concluir a candidatura."
        ),
    },
    "tiktok": {
        "categoria_key": "nucleo",
        "categoria_nome": "Núcleo",
        "cargo_nome": "𓆩★ Tiktok ★𓆪",
        "questions": NUCLEO_TIKTOK_QUESTIONS,
        "criterios": "Atividade, imagem pública, responsabilidade ao representar a FDN, disponibilidade para gravar e bom uso do canal de collabs.",
        "requires_attachment": False,
    },
}

CATEGORY_ROLES = {
    "staff": ["moderador_chat"],
    "nucleo": ["recrutador", "filmmaker"],
}


@dataclass
class ApplicationSession:
    guild_id: int
    user_id: int
    user_name: str
    categoria_key: str
    role_key: str
    respostas: dict[int, str] = field(default_factory=dict)
    anexos: list[dict[str, str]] = field(default_factory=list)
    aguardando_anexo: bool = False
    anexo_opcional: bool = False
    finalizando: bool = False

    @property
    def role(self):
        return ROLE_DEFINITIONS[self.role_key]


def limitar_texto(valor, limite):
    texto = str(valor or "").strip()
    if len(texto) <= limite:
        return texto or "Não informado"
    return texto[: max(0, limite - 3)].rstrip() + "..."


def formatar_data_iso(valor):
    if not valor:
        return "Não informado"
    try:
        data = datetime.fromisoformat(valor)
        return data.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        return str(valor)


def contar_caracteres_embed(embed):
    total = len(embed.title or "") + len(embed.description or "")
    total += len(getattr(embed.footer, "text", "") or "")
    for campo in embed.fields:
        total += len(campo.name or "") + len(campo.value or "")
    return total


def criar_embed_painel_candidatura():
    embed = discord.Embed(
        title="📋 Candidaturas FDN",
        description=(
            "Use este painel para se candidatar a cargos da FDN.\n\n"
            "Clique no botão abaixo, escolha a área desejada e responda o formulário com atenção.\n\n"
            "Importante: para se candidatar, deixe sua DM aberta para que o bot possa enviar as perguntas no privado."
        ),
        color=APPLICATION_COLOR,
    )
    embed.set_footer(text=APPLICATION_FOOTER)
    return embed


def criar_embed_pergunta_dm(session: ApplicationSession):
    perguntas = session.role["questions"]
    indice = len(session.respostas) + 1
    pergunta = perguntas[indice - 1]
    embed = discord.Embed(
        title=f"📝 Candidatura — Pergunta {indice}/{len(perguntas)}",
        description=(
            f"Cargo: **{session.role['cargo_nome']}**\n\n"
            f"**Pergunta {indice}**\n"
            f"{pergunta}\n\n"
            "Responda esta mensagem com sua resposta.\n"
            "Digite `cancelar` se quiser cancelar a candidatura."
        ),
        color=APPLICATION_COLOR,
    )
    embed.set_footer(text=APPLICATION_FOOTER)
    return embed


def criar_embed_anexo_dm(session: ApplicationSession):
    role = session.role
    descricao = role.get("attachment_prompt") or (
        "Agora envie aqui no privado uma imagem, desenho ou esboço mostrando "
        "como você faria uma formação para uma invasão de dança da FDN.\n\n"
        "Assim que eu receber o anexo, sua candidatura será enviada para análise da staff.\n"
        "Digite `cancelar` se quiser cancelar a candidatura."
    )
    if role.get("optional_attachment") and "`pular`" not in descricao:
        descricao = f"{descricao}\n\nEssa etapa é opcional. Digite `pular` para concluir sem anexo."

    embed = discord.Embed(
        title="📎 Anexo opcional" if role.get("optional_attachment") else "📎 Anexo obrigatório",
        description=(
            f"Cargo: **{session.role['cargo_nome']}**\n\n"
            f"{descricao}"
        ),
        color=APPLICATION_COLOR,
    )
    embed.set_footer(text=APPLICATION_FOOTER)
    return embed


def criar_embed_candidatura(registro):
    status = registro.get("status") or "Pendente"
    cargo = registro.get("cargo") or "Não informado"
    categoria = registro.get("categoria") or "Não informado"
    responsavel_id = registro.get("responsavel_id")
    responsavel = f"<@{responsavel_id}>" if responsavel_id else "Nenhum"
    candidato_id = registro.get("user_id")
    candidato = f"<@{candidato_id}>" if candidato_id else registro.get("user_name", "Não informado")

    embed = discord.Embed(
        title=f"📋 Candidatura — {cargo}",
        color=APPLICATION_COLOR,
        timestamp=datetime.now(FUSO_HORARIO),
    )
    embed.add_field(name="Candidato", value=candidato, inline=True)
    embed.add_field(name="Categoria", value=categoria, inline=True)
    embed.add_field(name="Cargo escolhido", value=cargo, inline=False)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Responsável", value=responsavel, inline=True)
    embed.add_field(name="Data de envio", value=formatar_data_iso(registro.get("data_envio")), inline=False)

    motivo = registro.get("motivo_reprovacao")
    if motivo:
        embed.add_field(name="Motivo da reprovação", value=limitar_texto(motivo, 1024), inline=False)

    dm_status = registro.get("dm_status")
    if dm_status:
        embed.add_field(name="Status da DM", value=limitar_texto(dm_status, 1024), inline=False)

    anexos = registro.get("anexos") or []
    if anexos:
        linhas = []
        for anexo in anexos[:5]:
            nome = anexo.get("filename") or "Anexo"
            url = anexo.get("url") or anexo.get("source_url") or ""
            linhas.append(f"[{limitar_texto(nome, 80)}]({url})" if url else limitar_texto(nome, 80))
        embed.add_field(name="Anexo", value="\n".join(linhas), inline=False)

    criterios = registro.get("criterios")
    if criterios:
        embed.add_field(name="Critérios", value=limitar_texto(criterios, 900), inline=False)

    embed.set_footer(text=f"{APPLICATION_FOOTER} • {registro.get('id', 'sem-id')}")
    return embed


def criar_embeds_candidatura(registro):
    return [criar_embed_candidatura(registro)]


def criar_embeds_respostas_candidatura(registro):
    embeds = []
    perguntas = registro.get("perguntas") or []
    respostas = registro.get("respostas") or {}
    candidatura_id = registro.get("id", "sem-id")

    embed_atual = None
    for indice, pergunta in enumerate(perguntas, start=1):
        if embed_atual is None:
            embed_atual = discord.Embed(
                title=f"Respostas da candidatura — {candidatura_id}",
                color=APPLICATION_COLOR,
            )
            embed_atual.set_footer(text=APPLICATION_FOOTER)

        resposta = respostas.get(str(indice)) or respostas.get(indice) or "Não informado"
        valor = f"**{pergunta}**\n{limitar_texto(resposta, 850)}"
        valor = limitar_texto(valor, 1024)

        teste = discord.Embed.from_dict(embed_atual.to_dict())
        teste.add_field(name=f"Pergunta {indice}", value=valor, inline=False)
        if contar_caracteres_embed(teste) > 5600 or len(teste.fields) > 8:
            embeds.append(embed_atual)
            embed_atual = discord.Embed(
                title=f"Respostas da candidatura — {candidatura_id}",
                color=APPLICATION_COLOR,
            )
            embed_atual.set_footer(text=APPLICATION_FOOTER)

        embed_atual.add_field(name=f"Pergunta {indice}", value=valor, inline=False)

    if embed_atual and embed_atual.fields:
        embeds.append(embed_atual)

    return embeds[:10]


def view_analise_para_status(status):
    if status in FINAL_STATUSES:
        return None
    return ApplicationReviewView()


async def responder_ephemeral(interaction, conteudo, **kwargs):
    if interaction.response.is_done():
        await interaction.followup.send(conteudo, ephemeral=True, **kwargs)
    else:
        await interaction.response.send_message(conteudo, ephemeral=True, **kwargs)


async def enviar_dm_candidato(bot, registro, conteudo):
    user_id = registro.get("user_id")
    if not user_id:
        return "Não foi possível enviar DM: candidato sem ID salvo."

    usuario = bot.get_user(int(user_id))
    if not usuario:
        try:
            usuario = await bot.fetch_user(int(user_id))
        except Exception:
            usuario = None

    if not usuario:
        return "Não foi possível enviar DM: usuário não localizado."

    try:
        await usuario.send(conteudo)
        return "DM enviada com sucesso."
    except (discord.Forbidden, discord.HTTPException):
        print(f"[CANDIDATURA] Não foi possível enviar DM para {usuario}.")
        return "Não foi possível enviar DM: privado fechado ou bloqueado."
    except Exception as erro:
        print(f"[CANDIDATURA] Erro ao enviar DM para {usuario}: {erro!r}")
        return "Não foi possível enviar DM: erro inesperado."


class ApplicationPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Candidatar-se",
        emoji="📋",
        style=discord.ButtonStyle.primary,
        custom_id="application_panel_open",
    )
    async def open_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("ApplicationsCog")
        if not cog:
            await responder_ephemeral(interaction, "Sistema de candidaturas indisponível no momento.")
            return

        await interaction.response.send_message(
            "Escolha o tipo de candidatura:",
            view=ApplicationCategoryView(cog, interaction.user.id),
            ephemeral=True,
        )


class ApplicationCategoryView(discord.ui.View):
    def __init__(self, cog, author_id):
        super().__init__(timeout=180)
        self.cog = cog
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await responder_ephemeral(interaction, "Essa candidatura não é sua.")
            return False
        return True

    @discord.ui.button(label="Staff", emoji="🛡️", style=discord.ButtonStyle.secondary)
    async def staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Escolha o cargo de Staff:",
            view=ApplicationRoleSelectView(self.cog, self.author_id, "staff"),
        )

    @discord.ui.button(label="Núcleo", emoji="🌙", style=discord.ButtonStyle.secondary)
    async def nucleo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Escolha o cargo do Núcleo:",
            view=ApplicationRoleSelectView(self.cog, self.author_id, "nucleo"),
        )


class ApplicationRoleSelect(discord.ui.Select):
    def __init__(self, cog, author_id, categoria_key):
        self.cog = cog
        self.author_id = author_id
        self.categoria_key = categoria_key
        options = []
        for role_key in CATEGORY_ROLES[categoria_key]:
            role = ROLE_DEFINITIONS[role_key]
            options.append(
                discord.SelectOption(
                    label=role["cargo_nome"],
                    value=role_key,
                    description=f"Candidatura para {role['categoria_nome']}.",
                )
            )
        super().__init__(
            placeholder="Selecione o cargo desejado.",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await responder_ephemeral(interaction, "Essa candidatura não é sua.")
            return

        role_key = self.values[0]
        session = self.cog.criar_sessao(interaction, self.categoria_key, role_key)
        await interaction.response.defer()
        erro = await self.cog.iniciar_fluxo_dm(interaction, session)
        if erro:
            self.cog.remover_sessao(session)
            await interaction.edit_original_response(content=erro, embed=None, view=None)
            return
        await interaction.edit_original_response(
            content="Te enviei a primeira pergunta no privado. Responda por lá para continuar a candidatura.",
            embed=None,
            view=None,
        )


class ApplicationRoleSelectView(discord.ui.View):
    def __init__(self, cog, author_id, categoria_key):
        super().__init__(timeout=180)
        self.add_item(ApplicationRoleSelect(cog, author_id, categoria_key))


class ApplicationReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _obter_registro(self, interaction):
        registro = obter_candidatura_por_message_id(getattr(interaction.message, "id", None))
        if not registro:
            await responder_ephemeral(interaction, "Não encontrei essa candidatura nos dados salvos.")
            return None
        return registro

    async def _validar_staff(self, interaction):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode analisar candidaturas.")
            return False
        return True

    async def _editar(self, interaction, registro):
        await interaction.message.edit(
            embeds=criar_embeds_candidatura(registro),
            view=view_analise_para_status(registro.get("status")),
        )

    @discord.ui.button(
        label="Aprovar",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="application_review_approve",
    )
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._validar_staff(interaction):
            return
        registro = await self._obter_registro(interaction)
        if not registro:
            return

        await interaction.response.defer(ephemeral=True)
        dm_status = await enviar_dm_candidato(
            interaction.client,
            registro,
            f"✅ Sua candidatura para {registro.get('cargo')} foi aprovada! Aguarde as próximas orientações da equipe.",
        )
        registro = atualizar_candidatura(registro["id"], status="Aprovado", dm_status=dm_status)
        await self._editar(interaction, registro)
        await interaction.followup.send("✅ Candidatura aprovada.", ephemeral=True)

    @discord.ui.button(
        label="Reprovar",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="application_review_reject",
    )
    async def reprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._validar_staff(interaction):
            return
        registro = await self._obter_registro(interaction)
        if not registro:
            return
        await interaction.response.send_modal(ApplicationRejectModal(registro["id"], interaction.message))

class ApplicationRejectModal(discord.ui.Modal):
    def __init__(self, candidatura_id, message):
        super().__init__(title="Reprovar candidatura")
        self.candidatura_id = candidatura_id
        self.message = message
        self.motivo = discord.ui.TextInput(
            label="Motivo",
            placeholder="Informe o motivo da reprovação.",
            required=True,
            max_length=800,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode analisar candidaturas.")
            return

        registro = obter_candidatura(self.candidatura_id)
        if not registro:
            await responder_ephemeral(interaction, "Não encontrei essa candidatura nos dados salvos.")
            return

        await interaction.response.defer(ephemeral=True)
        motivo = self.motivo.value.strip()
        dm_status = await enviar_dm_candidato(
            interaction.client,
            registro,
            (
                f"❌ Sua candidatura para {registro.get('cargo')} foi analisada, "
                f"mas não foi aprovada neste momento. Motivo: {motivo}"
            ),
        )
        registro = atualizar_candidatura(
            self.candidatura_id,
            status="Reprovado",
            motivo_reprovacao=motivo,
            dm_status=dm_status,
        )
        mensagem = self.message or getattr(interaction, "message", None)
        if mensagem:
            await mensagem.edit(
                embeds=criar_embeds_candidatura(registro),
                view=view_analise_para_status("Reprovado"),
            )
        else:
            print(f"[CANDIDATURA] Não consegui editar a mensagem da candidatura {self.candidatura_id}.")
        await interaction.followup.send("❌ Candidatura reprovada.", ephemeral=True)


class ApplicationsCog(commands.Cog):
    candidatura = app_commands.Group(name="candidatura", description="Sistema de candidaturas da FDN.")

    def __init__(self, bot):
        self.bot = bot
        self.sessions: dict[tuple[int, int], ApplicationSession] = {}
        self.dm_sessions: dict[int, ApplicationSession] = {}
        self.bot.add_view(ApplicationPanelView())
        self.bot.add_view(ApplicationReviewView())

    def criar_sessao(self, interaction, categoria_key, role_key):
        session = ApplicationSession(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            user_name=str(interaction.user),
            categoria_key=categoria_key,
            role_key=role_key,
        )
        self.sessions[(session.guild_id, session.user_id)] = session
        return session

    def remover_sessao(self, session):
        self.sessions.pop((session.guild_id, session.user_id), None)
        self.dm_sessions.pop(session.user_id, None)

    async def obter_usuario_sessao(self, session):
        usuario = self.bot.get_user(session.user_id)
        if usuario:
            return usuario
        try:
            return await self.bot.fetch_user(session.user_id)
        except Exception:
            return None

    async def enviar_proxima_pergunta_dm(self, session):
        usuario = await self.obter_usuario_sessao(session)
        if not usuario:
            return "Não consegui localizar seu usuário para enviar as perguntas no privado."

        try:
            await usuario.send(embed=criar_embed_pergunta_dm(session))
        except (discord.Forbidden, discord.HTTPException):
            return "Não consegui te enviar mensagem no privado. Abra sua DM para o bot e tente de novo."
        except Exception as erro:
            print(f"[CANDIDATURA] Erro ao enviar pergunta por DM: {erro!r}")
            return "Não consegui iniciar sua candidatura no privado agora. Tente novamente."
        return None

    async def iniciar_fluxo_dm(self, interaction, session):
        self.dm_sessions[session.user_id] = session
        return await self.enviar_proxima_pergunta_dm(session)

    async def obter_canal_analise(self, guild, categoria_key):
        chave = "CANDIDATURA_NUCLEO_CHANNEL_ID" if categoria_key == "nucleo" else "CANDIDATURA_STAFF_CHANNEL_ID"
        canal_id = obter_valor_config(guild, chave, DEFAULT_ANALYSIS_CHANNEL_ID)
        canal = self.bot.get_channel(int(canal_id)) if canal_id else None
        if canal:
            return canal
        try:
            return await self.bot.fetch_channel(int(canal_id))
        except Exception:
            return None

    async def reenviar_anexos(self, anexos):
        arquivos = []
        for anexo in anexos or []:
            try:
                arquivos.append(await anexo.to_file())
            except Exception as erro:
                print(f"[CANDIDATURA] Não consegui reenviar anexo {getattr(anexo, 'filename', '')}: {erro!r}")
        return arquivos

    async def enviar_respostas_para_analise(self, canal, registro):
        for indice, embed in enumerate(criar_embeds_respostas_candidatura(registro), start=1):
            try:
                await canal.send(
                    content=f"Respostas da candidatura `{registro.get('id', 'sem-id')}` - parte {indice}",
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException as erro:
                print(
                    f"[CANDIDATURA] Erro ao enviar respostas da candidatura | "
                    f"id={registro.get('id')} | parte={indice} | erro={erro!r}"
                )
                return False
        return True

    def montar_registro(self, guild, user, session: ApplicationSession):
        role = session.role
        agora = datetime.now(FUSO_HORARIO)
        return {
            "id": gerar_id_candidatura(),
            "guild_id": guild.id,
            "user_id": user.id,
            "user_name": str(user),
            "categoria_key": role["categoria_key"],
            "categoria": role["categoria_nome"],
            "role_key": session.role_key,
            "cargo": role["cargo_nome"],
            "perguntas": list(role["questions"]),
            "respostas": {str(chave): valor for chave, valor in session.respostas.items()},
            "criterios": role.get("criterios"),
            "anexos": list(session.anexos),
            "status": "Pendente",
            "responsavel_id": None,
            "responsavel_nome": None,
            "data_envio": agora.isoformat(),
            "message_id": None,
            "analysis_channel_id": None,
            "dm_status": None,
        }

    async def enviar_para_analise(self, guild, user, session: ApplicationSession, anexos_discord=None):
        canal = await self.obter_canal_analise(guild, session.categoria_key)
        if not canal:
            return None, "Não consegui encontrar o canal de análise configurado."

        registro = self.montar_registro(guild, user, session)
        arquivos = await self.reenviar_anexos(anexos_discord)
        cargo_staff_id = obter_valor_config(guild, "CARGO_STAFF_ID")
        mencao_staff = f"<@&{cargo_staff_id}>" if cargo_staff_id else ""

        async def enviar_mensagem_analise(arquivos_envio):
            return await canal.send(
                content=f"{mencao_staff} **Nova candidatura recebida.**".strip(),
                embeds=criar_embeds_candidatura(registro),
                view=ApplicationReviewView(),
                files=arquivos_envio,
                allowed_mentions=discord.AllowedMentions(users=False, roles=True),
            )

        try:
            mensagem = await enviar_mensagem_analise(arquivos)
        except discord.HTTPException as erro:
            if arquivos and (getattr(erro, "status", None) == 413 or getattr(erro, "code", None) == DISCORD_PAYLOAD_TOO_LARGE_CODE):
                print(
                    "[CANDIDATURA] Anexo grande demais para reenviar. "
                    "Enviando candidatura com link do anexo na embed."
                )
                for arquivo in arquivos:
                    try:
                        arquivo.close()
                    except Exception:
                        pass
                try:
                    mensagem = await enviar_mensagem_analise([])
                except discord.HTTPException as erro_sem_arquivo:
                    print(f"[CANDIDATURA] Erro ao enviar candidatura para análise sem anexo: {erro_sem_arquivo!r}")
                    return None, "Não consegui enviar a candidatura para o canal de análise."
            else:
                print(f"[CANDIDATURA] Erro ao enviar candidatura para análise: {erro!r}")
                return None, "Não consegui enviar a candidatura para o canal de análise."

        if mensagem.attachments:
            registro["anexos"] = [
                {
                    "filename": anexo.filename,
                    "url": anexo.url,
                    "content_type": anexo.content_type or "",
                }
                for anexo in mensagem.attachments
            ]

        registro["message_id"] = mensagem.id
        registro["analysis_channel_id"] = canal.id
        salvar_candidatura(registro)

        if mensagem.attachments:
            await mensagem.edit(embeds=criar_embeds_candidatura(registro), view=ApplicationReviewView())

        respostas_enviadas = await self.enviar_respostas_para_analise(canal, registro)
        if not respostas_enviadas:
            await canal.send(
                f"⚠️ Não consegui enviar todas as respostas da candidatura `{registro.get('id')}`. "
                "Peça para o candidato reenviar se necessário.",
                allowed_mentions=discord.AllowedMentions.none(),
            )

        self.remover_sessao(session)
        return registro, None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        session = self.dm_sessions.get(message.author.id)
        if not session:
            return

        if message.guild is not None:
            return

        if session.finalizando:
            await message.channel.send("Sua candidatura já está sendo enviada para análise. Aguarde.")
            return

        texto = (message.content or "").strip()
        if texto.casefold() in {"cancelar", "cancel"}:
            self.remover_sessao(session)
            await message.channel.send("Candidatura cancelada.")
            return

        if session.aguardando_anexo:
            if not message.attachments:
                pular_anexo = texto.casefold() in {"pular", "skip", "nao", "não", "n", "sem anexo"}
                if session.anexo_opcional and pular_anexo:
                    guild = self.bot.get_guild(session.guild_id)
                    if not guild:
                        await message.channel.send("Não consegui localizar o servidor para enviar sua candidatura. Avise a staff.")
                        return

                    session.finalizando = True
                    registro, erro = await self.enviar_para_analise(guild, message.author, session)
                    if erro:
                        session.finalizando = False
                        await message.channel.send(f"❌ {erro}")
                        return

                    await message.channel.send("✅ Sua candidatura foi enviada para análise da staff. Aguarde.")
                    return

                if session.anexo_opcional:
                    await message.channel.send(
                        "Envie um anexo para adicionar à candidatura ou digite `pular` para concluir sem anexo."
                    )
                    return

                await message.channel.send("Envie uma imagem/anexo para concluir essa candidatura.")
                return

            session.anexos = [
                {
                    "filename": anexo.filename,
                    "source_url": anexo.url,
                    "content_type": anexo.content_type or "",
                    "size": getattr(anexo, "size", 0) or 0,
                }
                for anexo in message.attachments
            ]
            guild = self.bot.get_guild(session.guild_id)
            if not guild:
                await message.channel.send("Não consegui localizar o servidor para enviar sua candidatura. Avise a staff.")
                return

            session.finalizando = True
            registro, erro = await self.enviar_para_analise(
                guild,
                message.author,
                session,
                anexos_discord=list(message.attachments),
            )
            if erro:
                session.finalizando = False
                await message.channel.send(f"❌ {erro}")
                return

            await message.channel.send("✅ Sua candidatura foi enviada para análise da staff. Aguarde.")
            return

        if not texto:
            await message.channel.send("Responda com texto para continuar a candidatura.")
            return

        perguntas = session.role["questions"]
        if len(session.respostas) < len(perguntas):
            indice = len(session.respostas) + 1
            session.respostas[indice] = texto

        if len(session.respostas) < len(perguntas):
            erro = await self.enviar_proxima_pergunta_dm(session)
            if erro:
                await message.channel.send(f"❌ {erro}")
            return

        if session.role.get("requires_attachment") or session.role.get("optional_attachment"):
            session.aguardando_anexo = True
            session.anexo_opcional = bool(session.role.get("optional_attachment"))
            await message.channel.send(embed=criar_embed_anexo_dm(session))
            return

        guild = self.bot.get_guild(session.guild_id)
        if not guild:
            await message.channel.send("Não consegui localizar o servidor para enviar sua candidatura. Avise a staff.")
            return

        session.finalizando = True
        registro, erro = await self.enviar_para_analise(guild, message.author, session)
        if erro:
            session.finalizando = False
            await message.channel.send(f"❌ {erro}")
            return

        await message.channel.send("✅ Sua candidatura foi enviada para análise da staff. Aguarde.")

    @candidatura.command(name="painel", description="Envia o painel de candidaturas da FDN.")
    @app_commands.guild_only()
    async def slash_candidatura_painel(self, interaction: discord.Interaction):
        if not membro_eh_staff(interaction.user):
            await responder_ephemeral(interaction, "Apenas a staff pode criar o painel de candidaturas.")
            return

        await interaction.response.send_message(
            embed=criar_embed_painel_candidatura(),
            view=ApplicationPanelView(),
        )


async def setup(bot):
    await bot.add_cog(ApplicationsCog(bot))
