import os
from datetime import timedelta, timezone

import discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_D1_DATABASE_ID = os.getenv("CLOUDFLARE_D1_DATABASE_ID")

if not DISCORD_TOKEN:
    raise RuntimeError("A variável DISCORD_TOKEN não foi encontrada no .env")

if not GEMINI_API_KEY:
    raise RuntimeError("A variável GEMINI_API_KEY não foi encontrada no .env")

COMMAND_PREFIX = "!"
HEARTBEAT_TIMEOUT = 300
GROQ_MODEL = "llama-3.1-8b-instant"
FUSO_HORARIO = timezone(timedelta(hours=-3))

COOLDOWN_MESMA_PESSOA = 5 * 60
COOLDOWN_OUTRA_PESSOA = 1 * 60
COOLDOWN_IA = 0
COOLDOWN_REPLY_BOT_USUARIO = 2 * 60
COOLDOWN_REPLY_BOT_GLOBAL = 1 * 60
COOLDOWN_RECRUTAMENTO = 5
TTL_MENSAGEM_PROCESSADA = 10

CANAL_PERGUNTAS_ID = 1461788928313921588
CANAL_GERAL_ID = 1461788928313921588
CANAL_ANIVERSARIO_ID = 1461788932541780115
CARGO_ANIVERSARIANTE_ID = 1478878533257396465
CANAL_LOGS_ID = 1495834345011937532
CANAL_FEEDBACK_ID = 1496573221196140564
CARGO_STAFF_ID = 1478800416945995849
# ID do canal onde o bot vai publicar as histórias/imagens.
HISTORIAS_CHANNEL_ID = 0
# ID do cargo da staff que pode publicar histórias.
# Se já existir uma variável de staff no projeto, pode reaproveitar.
HISTORIAS_STAFF_ROLE_ID = 1461789051047772293
# ID do canal onde o bot enviará os registros de presença/ausência dos eventos.
AUSENCIA_CHANNEL_ID = 1504257798966476890
ACHIEVEMENTS_CHANNEL_ID = 1482903234086567977
ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID = 1484155700493160469
RAVEN_ACHIEVEMENTS_CHANNEL_ID = 1521654695159005377
RAVEN_FAN_LOG_CHANNEL_ID = 1521631012172595290
# ID do canal onde ficará o painel fixo do sistema de presença/ausência.
AUSENCIA_PANEL_CHANNEL_ID = 0
# ID do cargo da staff que pode criar eventos de presença/ausência.
AUSENCIA_STAFF_ROLE_ID = CARGO_STAFF_ID
# ID do canal onde serão enviadas as advertências automáticas por falta de resposta em eventos.
ADVERTENCIA_CHANNEL_ID = 1507388610117238824
# ID do cargo que será mencionado na mensagem final da lista de ausentes.
AUSENCIA_AUSENTES_MENTION_ROLE_ID = 1463399349294731335
# Cargos que serão mencionados quando um novo evento for criado.
AUSENCIA_MENTION_ROLE_IDS = [1463399349294731335, 1465032635133858035]
CARGO_RECRUTAMENTO_ID = 1461789056668008711
CARGO_MEMBRO_ID = 1463399349294731335
BOAS_VINDAS_ROLE_ID = 1461789054986223650
CARGO_AVISO_REACAO_ID = 1463399349294731335
CANAL_TIME_TAGS_ID = 1461794756760829973
CANAL_TAGS_FINAL_ID = 1461792528058548508
CANAL_STAFF_TAGS_ID = 1504169713046130898
# Canal do conselho onde as candidaturas serao enviadas para analise.
CANAL_CONSELHO_ID = 1462901201069932544
# Canais privados onde as candidaturas serao enviadas para analise.
CANDIDATURA_STAFF_CHANNEL_ID = CANAL_CONSELHO_ID
CANDIDATURA_NUCLEO_CHANNEL_ID = CANAL_CONSELHO_ID
# Canal onde ficará o painel fixo de controle de tags.
TAG_PANEL_CHANNEL_ID = 1497954911395123230
# Emojis personalizados do painel fixo de tags.
TAG_PANEL_EMOJI_TITLE = "<:moonfdn:1501329435222216857>"
TAG_PANEL_EMOJI_PENDING = "<:clipboardfdn:1501699960348082227>"
TAG_PANEL_EMOJI_LATE = "<:clockFDN:1501711193465815080>"
TAG_PANEL_EMOJI_DONE = "<:VerifyFDN:1501712135921729727>"
TAG_PANEL_EMOJI_SEARCH = "<:searchFDN:1501711807239159943>"
TAG_PANEL_EMOJI_UPDATE = "<:loadingFDN:1501716904987988119>"
# Canal onde serão enviados os logs do sistema de tags/timetag.
TAG_LOG_CHANNEL_ID = 1497954324070793327
CANAL_CONTAGEM_ID = 1482067281474228347
CANAL_RECRUTADORES_ID = 1462902961289039974
XP_CHANNEL_ID = 1521722064115859566
XP_ANNOUNCE_CHANNEL_ID = 1484155700493160469
MENSAGEIRO_DA_NOITE_ROLE_ID = 1521632860157513749
XP_GENERAL_CHANNEL_IDS = [1461788928313921588]
XP_MEDIA_CHANNEL_IDS = [1461788929131938014]
XP_ROLE_IDS = {
    "corvo_noturno": 1482888021790429315,
    "corvo_lunar": 1482879827454459974,
    "corvo_celestial": 1482941698496790588,
}
XP_DAILY_LIMIT = 700
XP_GENERAL_COOLDOWN_SECONDS = 60
XP_MEDIA_COOLDOWN_SECONDS = 60 * 60
NPC_SEM_QUEST_ROLE_ID = 1521633921882787994
NPC_SEM_QUEST_COOLDOWN_SECONDS = 6 * 60 * 60
# Canal onde ficará o painel fixo do sistema de recrutamento.
REC_PANEL_CHANNEL_ID = 1496697765953277972
REC_EMOJI_TITLE = "<:moonfdn:1501329435222216857>"
REC_EMOJI_RANKING = "<:trofeu:1501334993899618445> "
REC_EMOJI_INFO = "<:searchFDN:1501711807239159943>"
REC_EMOJI_ADD = "<:addFDN:1501711659176300665>"
REC_EMOJI_REMOVE = "<:removeFDN:1501711716713500812>"
REC_EMOJI_MSG = "<:chat:1501335384167288963> "
REC_EMOJI_UPDATE = "<:loadingFDN:1501716904987988119>"
# ID do canal de texto onde as fichas de recrutamento serão enviadas para análise.
CADASTRO_CHANNEL_ID = 1498004687759347762
# ID do canal antigo de cadastros, usado apenas para importar fichas antigas.
CADASTRO_OLD_CHANNEL_ID = 1464647753799041227
# Canal onde o bot enviará logs de fichas salvas/aprovadas/reprovadas.
CADASTRO_LOG_CHANNEL_ID = 1497982450394071061
# ID do canal onde ficará o painel fixo de consulta de cadastros.
CADASTRO_PANEL_CHANNEL_ID = 1498378701921062964
CADASTRO_PANEL_EMOJI_TITLE = "<:moonfdn:1501329435222216857>"
CADASTRO_PANEL_EMOJI_APPROVED = "<:VerifyFDN:1501712135921729727>"
CADASTRO_PANEL_EMOJI_REJECTED = "<:Xfdn:1501712074412134501>"
CADASTRO_PANEL_EMOJI_IMPORTED = "<:importFDN:1501716630260945046>"
CADASTRO_PANEL_EMOJI_UPDATE = "<:loadingFDN:1501716904987988119>"
# Troque pelos IDs reais da categoria e do cargo de tickets se forem diferentes no seu servidor.
TICKET_CATEGORY_ID = 1496246919666602125
TICKET_PANEL_EMOJI_TITLE = "<:moonfdn:1501329435222216857>"
TICKET_PANEL_EMOJI_OPEN = "<:ticketfdn:1501345916861415434>"
TICKET_PANEL_TITLE_TEXT = "Atendimento — Filhos da Noite"
TICKET_PANEL_DESCRIPTION_TEXT = (
    "Abra um ticket para tratar assuntos relacionados ao servidor, recrutamento, "
    "parcerias, denúncias ou dúvidas gerais.\n\n"
    "**Caso você esteja aqui para se tornar membro, abra um ticket na opção Recrutamento.**\n\n"
    "<:clockFDN:1501711193465815080>  Horário de atendimento\n"
    "Este painel de tickets funciona das 10h às 00h.\n\n"
    "✦ Antes de abrir um ticket\n\n"
    "• Explique sua solicitação com clareza.\n"
    "• Escolha a categoria correta para o seu atendimento.\n"
    "• Evite abrir tickets sem necessidade.\n"
    "• Aguarde a resposta da staff com paciência.\n\n"
    "Clique no botão abaixo para iniciar o atendimento."
)
TICKET_PANEL_FOOTER_TEXT = "FDN • Filhos da Noite"
TICKET_PANEL_OPEN_BUTTON_LABEL = "Abrir Ticket"
TICKET_CATEGORY_SELECT_PLACEHOLDER = "Selecione a categoria do seu atendimento."
TICKET_WELCOME_TITLE_TEXT = "🌙 FDN — Sistema de Atendimento"
TICKET_SYSTEM_FOOTER_TEXT = "FDN • Sistema de Tickets"
TICKET_STAFF_ROLE_ID = 1497649650189205554
TICKET_STAFF_ROLE_IDS = [
    1461789056668008711,  # Recrutadores
    1497649650189205554,  # Atendimento de tickets
    1461789053237071955,  # ADM
    1463389335465492530,  # Suporte
    1463388653307957362,  # Lider
    1461789051047772293,  # Fundadora
]
TICKET_LOG_CHANNEL_ID = 1496253228126437526
# Define quantos segundos o bot espera antes de apagar o canal após o fechamento.
TICKET_DELETE_DELAY_SECONDS = 10
# ID do canal onde serão enviados os feedbacks dos tickets.
TICKET_FEEDBACK_LOG_CHANNEL_ID = 1496573221196140564
# Tempo máximo que o bot espera pela avaliação antes de encerrar o canal automaticamente.
TICKET_FEEDBACK_TIMEOUT_SECONDS = 120
BOT_GUILD_NICKNAME = None
BOT_GUILD_AVATAR_PATH = None
BOT_GUILD_BANNER_PATH = None

CANAIS_REACAO = {
    "jogatina": 1461799633561976933,
    "invasão": 1462882658408206532,
    "invasao": 1462882658408206532,
    "cronograma": 1461788925369782334,
    "avisos": 1461799397632376832,
}

CARGOS_LIDERANCA_IDS = {
    1461789051047772293,
    1463388653307957362,
}

GATILHO_BOM_DIA_ATIVO = True
BOT_IA_ATIVA = True

SERVER_CONFIG_DEFAULTS = {
    "CANAL_PERGUNTAS_ID": CANAL_PERGUNTAS_ID,
    "CANAL_GERAL_ID": CANAL_GERAL_ID,
    "CANAL_ANIVERSARIO_ID": CANAL_ANIVERSARIO_ID,
    "CARGO_ANIVERSARIANTE_ID": CARGO_ANIVERSARIANTE_ID,
    "CANAL_LOGS_ID": CANAL_LOGS_ID,
    "CANAL_FEEDBACK_ID": CANAL_FEEDBACK_ID,
    "GATILHO_BOM_DIA_ATIVO": GATILHO_BOM_DIA_ATIVO,
    "BOT_IA_ATIVA": BOT_IA_ATIVA,
    "CARGO_STAFF_ID": CARGO_STAFF_ID,
    "AUSENCIA_CHANNEL_ID": AUSENCIA_CHANNEL_ID,
    "ACHIEVEMENTS_CHANNEL_ID": ACHIEVEMENTS_CHANNEL_ID,
    "ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID": ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID,
    "RAVEN_ACHIEVEMENTS_CHANNEL_ID": RAVEN_ACHIEVEMENTS_CHANNEL_ID,
    "RAVEN_FAN_LOG_CHANNEL_ID": RAVEN_FAN_LOG_CHANNEL_ID,
    "AUSENCIA_PANEL_CHANNEL_ID": AUSENCIA_PANEL_CHANNEL_ID,
    "AUSENCIA_STAFF_ROLE_ID": AUSENCIA_STAFF_ROLE_ID,
    "ADVERTENCIA_CHANNEL_ID": ADVERTENCIA_CHANNEL_ID,
    "AUSENCIA_AUSENTES_MENTION_ROLE_ID": AUSENCIA_AUSENTES_MENTION_ROLE_ID,
    "AUSENCIA_MENTION_ROLE_IDS": list(AUSENCIA_MENTION_ROLE_IDS),
    "CARGO_RECRUTAMENTO_ID": CARGO_RECRUTAMENTO_ID,
    "CARGO_MEMBRO_ID": CARGO_MEMBRO_ID,
    "BOAS_VINDAS_ROLE_ID": BOAS_VINDAS_ROLE_ID,
    "CARGO_AVISO_REACAO_ID": CARGO_AVISO_REACAO_ID,
    "CANAL_TIME_TAGS_ID": CANAL_TIME_TAGS_ID,
    "CANAL_TAGS_FINAL_ID": CANAL_TAGS_FINAL_ID,
    "CANAL_STAFF_TAGS_ID": CANAL_STAFF_TAGS_ID,
    "CANAL_CONSELHO_ID": CANAL_CONSELHO_ID,
    "CANDIDATURA_STAFF_CHANNEL_ID": CANDIDATURA_STAFF_CHANNEL_ID,
    "CANDIDATURA_NUCLEO_CHANNEL_ID": CANDIDATURA_NUCLEO_CHANNEL_ID,
    "TAG_PANEL_CHANNEL_ID": TAG_PANEL_CHANNEL_ID,
    "TAG_LOG_CHANNEL_ID": TAG_LOG_CHANNEL_ID,
    "CANAL_CONTAGEM_ID": CANAL_CONTAGEM_ID,
    "CANAL_RECRUTADORES_ID": CANAL_RECRUTADORES_ID,
    "XP_CHANNEL_ID": XP_CHANNEL_ID,
    "XP_ANNOUNCE_CHANNEL_ID": XP_ANNOUNCE_CHANNEL_ID,
    "MENSAGEIRO_DA_NOITE_ROLE_ID": MENSAGEIRO_DA_NOITE_ROLE_ID,
    "XP_GENERAL_CHANNEL_IDS": list(XP_GENERAL_CHANNEL_IDS),
    "XP_MEDIA_CHANNEL_IDS": list(XP_MEDIA_CHANNEL_IDS),
    "XP_ROLE_IDS": dict(XP_ROLE_IDS),
    "XP_DAILY_LIMIT": XP_DAILY_LIMIT,
    "XP_GENERAL_COOLDOWN_SECONDS": XP_GENERAL_COOLDOWN_SECONDS,
    "XP_MEDIA_COOLDOWN_SECONDS": XP_MEDIA_COOLDOWN_SECONDS,
    "NPC_SEM_QUEST_ROLE_ID": NPC_SEM_QUEST_ROLE_ID,
    "NPC_SEM_QUEST_COOLDOWN_SECONDS": NPC_SEM_QUEST_COOLDOWN_SECONDS,
    "REC_PANEL_CHANNEL_ID": REC_PANEL_CHANNEL_ID,
    "CADASTRO_CHANNEL_ID": CADASTRO_CHANNEL_ID,
    "CADASTRO_OLD_CHANNEL_ID": CADASTRO_OLD_CHANNEL_ID,
    "CADASTRO_LOG_CHANNEL_ID": CADASTRO_LOG_CHANNEL_ID,
    "CADASTRO_PANEL_CHANNEL_ID": CADASTRO_PANEL_CHANNEL_ID,
    "TICKET_CATEGORY_ID": TICKET_CATEGORY_ID,
    "TICKET_STAFF_ROLE_ID": TICKET_STAFF_ROLE_ID,
    "TICKET_STAFF_ROLE_IDS": list(TICKET_STAFF_ROLE_IDS),
    "TICKET_LOG_CHANNEL_ID": TICKET_LOG_CHANNEL_ID,
    "TICKET_FEEDBACK_LOG_CHANNEL_ID": TICKET_FEEDBACK_LOG_CHANNEL_ID,
    "TICKET_PANEL_TITLE_TEXT": TICKET_PANEL_TITLE_TEXT,
    "TICKET_PANEL_DESCRIPTION_TEXT": TICKET_PANEL_DESCRIPTION_TEXT,
    "TICKET_PANEL_FOOTER_TEXT": TICKET_PANEL_FOOTER_TEXT,
    "TICKET_PANEL_OPEN_BUTTON_LABEL": TICKET_PANEL_OPEN_BUTTON_LABEL,
    "TICKET_CATEGORY_SELECT_PLACEHOLDER": TICKET_CATEGORY_SELECT_PLACEHOLDER,
    "TICKET_WELCOME_TITLE_TEXT": TICKET_WELCOME_TITLE_TEXT,
    "TICKET_SYSTEM_FOOTER_TEXT": TICKET_SYSTEM_FOOTER_TEXT,
    "TICKET_CATEGORIAS": {},
    "TICKET_CATEGORIAS_ORDEM": [],
    "TICKET_FORMULARIOS": {},
    "BOT_GUILD_NICKNAME": BOT_GUILD_NICKNAME,
    "BOT_GUILD_AVATAR_PATH": BOT_GUILD_AVATAR_PATH,
    "BOT_GUILD_BANNER_PATH": BOT_GUILD_BANNER_PATH,
    "CANAIS_REACAO": dict(CANAIS_REACAO),
    "CARGOS_LIDERANCA_IDS": list(CARGOS_LIDERANCA_IDS),
    "REC_EMOJI_TITLE": REC_EMOJI_TITLE,
    "REC_EMOJI_RANKING": REC_EMOJI_RANKING,
    "REC_EMOJI_INFO": REC_EMOJI_INFO,
    "REC_EMOJI_ADD": REC_EMOJI_ADD,
    "REC_EMOJI_REMOVE": REC_EMOJI_REMOVE,
    "REC_EMOJI_MSG": REC_EMOJI_MSG,
    "REC_EMOJI_UPDATE": REC_EMOJI_UPDATE,
    "TAG_PANEL_EMOJI_TITLE": TAG_PANEL_EMOJI_TITLE,
    "TAG_PANEL_EMOJI_PENDING": TAG_PANEL_EMOJI_PENDING,
    "TAG_PANEL_EMOJI_LATE": TAG_PANEL_EMOJI_LATE,
    "TAG_PANEL_EMOJI_DONE": TAG_PANEL_EMOJI_DONE,
    "TAG_PANEL_EMOJI_SEARCH": TAG_PANEL_EMOJI_SEARCH,
    "TAG_PANEL_EMOJI_UPDATE": TAG_PANEL_EMOJI_UPDATE,
    "CADASTRO_PANEL_EMOJI_TITLE": CADASTRO_PANEL_EMOJI_TITLE,
    "CADASTRO_PANEL_EMOJI_APPROVED": CADASTRO_PANEL_EMOJI_APPROVED,
    "CADASTRO_PANEL_EMOJI_REJECTED": CADASTRO_PANEL_EMOJI_REJECTED,
    "CADASTRO_PANEL_EMOJI_IMPORTED": CADASTRO_PANEL_EMOJI_IMPORTED,
    "CADASTRO_PANEL_EMOJI_UPDATE": CADASTRO_PANEL_EMOJI_UPDATE,
    "TICKET_PANEL_EMOJI_TITLE": TICKET_PANEL_EMOJI_TITLE,
    "TICKET_PANEL_EMOJI_OPEN": TICKET_PANEL_EMOJI_OPEN,
}

ARQUIVO_DADOS = "dados_perguntas.json"
ARQUIVO_CONFIG_SERVIDORES = "dados_servidores.json"
ARQUIVO_AUSENCIAS = "dados_ausencias.json"
ARQUIVO_CONQUISTAS = "dados_conquistas.json"
ARQUIVO_ADVERTENCIAS = "dados_advertencias.json"
ARQUIVO_DADOS_BOAS_VINDAS = "dados_boas_vindas.json"
ARQUIVO_DADOS_GATILHOS = "dados_gatilhos_estado.json"
ARQUIVO_TAGS = "dados_tags.json"
ARQUIVO_ANIVERSARIOS = "dados_aniversarios.json"
ARQUIVO_XP = "dados_xp.json"
EMOJI_APROVAR_TAG = "✅"

GATILHOS_ATIVOS = False

FRASES_TAG_7_DIAS = [
    "Já fechou 7 dias e a galera abaixo segue devendo a famosa troca de tag.",
    "Tem membro que chegou nos 7 dias e a tag segue só na promessa.",
    "Atualizando a staff: 7 dias completos e nada da troca de tag pra esse pessoal.",
    "Bateu 7 dias e a tag até agora não deu sinal de vida pra quem tá aqui embaixo.",
]
FRASES_TAG_10_DIAS = [
    "O pessoal abaixo já tá com 10 dias de atraso e a tag continua inexistente.",
    "Atualização da staff: 10 dias se passaram e a troca de tag segue na lenda pra essa turma.",
    "Bateu 10 dias de atraso. A tag já pode pedir música no Fantástico pra esse povo aqui.",
]
FRASES_MENCAO_VAZIA = [
    "Tem que falar meu nome três vezes olhando pro espelho",
    "apareci, agora desenvolve",
    "Está carente?",
    "fui chamado com zero informações, excelente!",
    "me invocou, agora arque com as consequências",
    "me invocaram de novo, o tédio realmente venceu",
    "falar meu nome sem motivo é hobby agora?",
]
FRASES_RESPOSTA_MANUAL = [
    "jáe então!",
    "faz o pix!",
    "não quero, obrigado!",
    "estou ocupado no momento!",
    "eu nem existo",
    "vou fingir que estou entendendo",
    "Se falar minha lingua eu consigo responder",
    "Tem que traduzir?",
    "está carente amigo(a) ?",
    "É muito ego e pouca pika!",
    "vamos fingir que a pessoa respondeu em espírito",
]
FRASE_SEM_RESPOSTA_BOAS_VINDAS = None
FRASES_BEM_VINDO_MANUAL = [
    "<@&1463399349294731335> 🚨 novo membro entrou: {membro}. escondam a vergonha e deem boas-vindas. 😌",
    "<@&1463399349294731335> <:moonfdn:1501329435222216857> bem-vindo(a), {membro}! qualquer semelhança com o caps é coincidência 👀 brincadeirinha hahaha.",
    "<@&1463399349294731335> 🖤 {membro}, bem-vindo(a)! prometemos nada e entregamos entretenimento. ✨",
    "<@&1463399349294731335> 🚨 ALERTA: entrou gente nova no servidor... bem-vindo(a), {membro}! 🐦‍⬛<:moonfdn:1501329435222216857>",
]

PERGUNTAS_DIARIAS = [
    "Desafio da vergonha: mande a pior desculpa possível para chegar atrasado em um evento do clã.",
    "Pergunta final do caos: se o servidor virasse um reality show, qual seria o nome do programa?",
    "Pergunta criminosa: qual comida você acha que deveria ser ilegal misturar com outra?",
    "Qual coisa você julgava antes e hoje faz igual?",
    "Qual seria a pior mensagem pra receber às 3 da manhã?",
    "Que coisa você compra achando que vai usar e nunca usa?",
    "Você prefere filme de terror, romance, comédia ou ação (cite um)?",
    "Qual música te dá nostalgia?",
    "Fale um filme que você gosta e tem o melhor plot twist.",
]
GATILHOS_CONFIG = {
    "comando_invasao": {
        "palavras": ["!invasão", "!invasao"],
        "exato": True,
        "apenas_staff": True,
        "sem_cooldown": True,
        "respostas": [
            "Invasão? Quem for lagando já ganha ponto extra de participação.",
            "Bora invadir! O mapa não vai lotar sozinho.",
            "Quem tá online tem que aparecer na invasão.",
            "Tá online em outro jogo e a invasão te esperando… interessante essa vida dupla aí. ?? <@&1463399349294731335>",
            "Jogando escondido durante a invasão né? Eu vi, mas não sei guardar segredo. ?? <@&1463399349294731335>",
            "Apareceu online em tudo, menos onde precisava né? Que talento ?? <@&1463399349294731335>",
            "Dá tempo de trocar esse jogo pela invasão e fingir que nada aconteceu, tá? <@&1463399349294731335>",
            "Bora pra invasão meus lindos <a:firecyan:1464014359234740244>\n<@&1463399349294731335>",
        ],
    },
    "comando_inativos": {
        "palavras": ["!inativos"],
        "exato": True,
        "apenas_staff": True,
        "sem_cooldown": True,
        "respostas": [
            "Inatividade de alguns membros detectada <@&1463399349294731335>",
            "Aparece ai corvinhos. Até eu que sou um bot tenho mais presença que vocês.?? <@&1463399349294731335>",
            "Inativo desse jeito, o líder nem precisa indicar... pegou a referência? ?? <@&1463399349294731335>",
            "Cuidado corvinho: quem some demais vira opção de voto ?? <@&1463399349294731335>",
        ],
    },
    "comando_recrutadores": {
        "palavras": ["!recrutar"],
        "exato": True,
        "apenas_staff": True,
        "sem_cooldown": True,
        "respostas": [
            "Bora recrutar corvinhos. O clã não cresce só com pensamento positivo ?? <@&1461789056668008711>",
            "Quem recrutar hoje ganha +1 no coração da staff e na contagem também <a:heartcyan:1464014951650689056> <@&1461789056668008711>",
            "Vamo recrutar, mas sem assustar né… ninguém quer recrutador parecendo vendedor de loja de roupas ?? <@&1461789056668008711>",
            "Recrutadores, bora movimentar isso aí. Membro novo não cai do céu, infelizmente. <@&1461789056668008711>",
        ],
    },
    "comando_jogatina": {
        "palavras": ["!jogatina"],
        "exato": True,
        "apenas_staff": True,
        "sem_cooldown": True,
        "respostas": [
            "O corvo avisou: quem tá online tem que aparecer na jogatina.",
            "FDN convocada: parem de fingir que estão ocupados e venham jogar.",
            "Jogatina na área! O corvo já pousou, só falta vocês.",
            "Venham jogar antes que eu comece a contar os sumidos.",
        ],
    },
    "comando_conselho": {
        "palavras": ["!conselho"],
        "exato": True,
        "apenas_staff": True,
        "sem_cooldown": True,
        "respostas": [
            "Conselho do dia: Lembra: vergonha passa, print fica",
            "Conselho do dia: Faz o mínimo bem feito antes de inventar moda",
            "Conselho do dia: Ás vezes o universo não te odeia, você só fez besteira mesmo",
            "Conselho do dia: Tem dores que só um bolo de chocolate bem chocolatudo pode curar.",
            "Conselho do dia: Não alimenta teu drama antes de alimentar teu estômago",
            "Conselho do dia: Não transforma fofoca em TCC",
            "Conselho do dia: Nem tudo precisa da tua opinião, mas o caos agradece.",
            "Conselho do dia: Economiza drama, o mês ainda nem acabou",
            "Conselho do dia: Ás vezes a resposta não é insistir, é ter amor-próprio.",
        ],
    },
    "comando_interagir": {
        "palavras": ["!interagir"],
        "exato": True,
        "apenas_staff": True,
        "sem_cooldown": True,
        "respostas": [
            "Alguém fala alguma coisa antes que eu comece a conversar sozinho. <@&1463399349294731335>",
            "Quem puxar assunto agora ganha o prêmio de pessoa menos tímida do dia ?? <@&1463399349294731335>",
            "Se ninguém falar nada, vou começar a inventar fofoca. <@&1463399349294731335>",
            "Alguém fala “oi” só pra eu saber que não tô em servidor abandonado. <@&1463399349294731335>",
            "Bora interagir corvinhos, digam oi pra mim que eu conto uma fofoca <@&1463399349294731335>",
        ],
    },
    "oi": {
        "palavras": ["oi"],
        "exato": True,
        "respostas": [
            "Só “oi”? eu ia contar uma fofoca mas até desanimei",
            "“Oi” seco assim eu quase fui beber água.",
            "Gostei da interação minimalista.",
            "Oi oi! Qual a boa?",
        ],
    },
    "bom_dia": {
        "palavras": ["bom dia"],
        "exato": False,
        "cooldown_global": 10 * 60,
        "bloquear_usuario_permanente": True,
        "respostas": [
            "Bom dia meus pagadores de impostos.",
            "Bom dia meus boletinhos atrasados",
            "Nunca foi azar, sempre foi falta de heran\u00e7a.\nBom dia corvinhos!",
            "motivacao do dia:\nvoc\u00ea \u00e9 pobre, acorda! Bom diaaaa kkkkk",
            "O pior vazio, \u00e9 o da carteira.\nbom dia e bora trabalhar n\u00e9",
            "bom dia meus trabalhadores assalariados",
            "N\u00e3o importa o quanto a hist\u00f3ria do outro seja triste, nunca empreste o seu cart\u00e3o.\nBom dia filhos da noite!",
            "bom dia meus guerreiros endividados",
            "nunca \u00e9 tarde pra acordar pra vida, bom dia!",
            "bom dia a todos, menos em quem acredita no merc\u00fario retr\u00f3grado. Brincadeirinha kkkkkkk",
            "Levanta que as contas n\u00e3o se pagam s\u00f3, bom dia!",
            "conselho para vida:\nVIVE A TUA\nbom dia!",
            "Hoje eu escolhi ser simp\u00e1tico mas vamos ver, ainda \u00e9 cedo. bom dia!",
        ],
    },
    "boa_tarde": {
        "palavras": ["boa tarde"],
        "exato": False,
        "cooldown_global": 24 * 60 * 60,
        "uma_vez_por_dia_global": True,
        "respostas": [
            "Boa tarde, meu consagrado. Hoje tá rendendo ou só existindo?",
            "Boa tarde, família. Já beberam água hoje?",
            "Boa tarde, meu fi. Que hoje ninguém te estresse além do necessário.",
            "Boa tarde, jovem!",
        ],
    },
    "banho": {
        "palavras": ["banho"],
        "exato": False,
        "cooldown_global": 24 * 60 * 60,
        "uma_vez_por_dia_global": True,
        "respostas": [
            "Prepara o shampoo anti-caatinga pro seu coro carecudo. - Div 2026",
            "Tô sentindo um cheirinho de catinga no ar.",
            "Sábado é dia de banho, viu gente? Só avisando mesmo.",
        ],
    },
    "Juro": {
        "palavras": ["juro", "juro vei", "Juro"],
        "exato": False,
        "sem_cooldown": True,
        "respostas": [
            "Juro o que fia, conversa direito",
            "iiiiiih Jurou neh?",
        ],
    },
    "fofoca": {
        "palavras": ["fofoca"],
        "exato": False,
        "cooldown_global": 24 * 60 * 60,
        "uma_vez_por_dia_global": True,
        "respostas": [
            "O chat ficou 90% mais atento.",
            "Pode começar, estamos fingindo maturidade.",
            "Já avisando que fofoca sem detalhes é crime social.",
            "Pode falar, eu sou um bot, mas também sou curioso.",
        ],
    },
    "pix": {
        "palavras": ["pix"],
        "exato": False,
        "cooldown_global": 24 * 60 * 60,
        "uma_vez_por_dia_global": True,
        "respostas": [
            "Manda o comprovante que eu finjo surpresa.",
            "Erro 404: dinheiro não encontrado na minha conta.",
            "Aceitamos pix, robux e elogios sinceros.",
            "FDN informa: pix é sempre bem-vindo.",
        ],
    },
    "paulista": {
        "palavras": ["!paulista"],
        "exato": True,
        "respostas": [
            "Paulista não conversa, faz networking.",
            "Paulista vê trânsito parado e fala: “hoje tá tranquilo”.",
            "Paulista escuta buzina e acha que é música ambiente.",
            "Paulista não anda na rua, ele desfila com pressa.",
            "Paulista chama garoa de tempestade emocional.",
            "Paulista quando visita outro estado pergunta: “mas aqui fecha cedo por quê?”",
            "Paulista não pega bronzeado, pega camada de poluição.",
            "Em São Paulo o céu às vezes tá cinza só por costume.",
        ],
    },
    "nordestino": {
        "palavras": ["!nordestino"],
        "exato": True,
        "respostas": [
            "Nordestino toma água gelada e ainda fala: “oxe, tá quente”.",
            "Nordestino vê chuva e já vira evento histórico.",
            "O ventilador no Nordeste trabalha mais que muita gente.",
            "Nordestino reclama do calor... rindo e tomando café quente.",
            "Ar-condicionado no Nordeste é tratado como membro da família.",
            "O cuscuz no Nordeste vale mais que muito luxo por aí.",
            "Oxe é resposta, pergunta, susto e filosofia ao mesmo tempo.",
        ],
    },
    "baiano": {
        "palavras": ["!baiano"],
        "exato": True,
        "respostas": [
            "Baiano é tão tranquilo que até o relógio espera ele.",
            "Se o mundo acabar, o baiano fala: “oxente, amanhã eu vejo isso”.",
            "O estresse tenta pegar o baiano e desiste no meio do caminho.",
            "Se pressa matasse, o baiano tava imortal.",
            "O descanso do baiano é descansar do descanso.",
            "A rede do baiano é mais disputada que vaga na sombra.",
        ],
    },
    "carioca": {
        "palavras": ["!carioca"],
        "exato": True,
        "respostas": [
            "Carioca fala “já tô chegando” e ainda tá saindo do banho.",
            "Carioca fala alto porque nasceu competindo com o barulho da cidade.",
            "No Rio, se alguém corre do nada, metade corre junto sem perguntar.",
            "No Rio, errar entrada pode virar passeio radical.",
            "No Rio tem bairro que o agachamento vem no reflexo.",
        ],
    },
    "portugal": {
        "palavras": ["!portugal"],
        "exato": True,
        "respostas": [
            "Português fala “rapariga” e metade do Brasil se sente ofendido.",
            "Português: “não tenho culpa.” Brasileiro: “então ajuda a parcelar.”",
        ],
    },
    "sulista": {
        "palavras": ["!sulista"],
        "exato": True,
        "respostas": [
            "No Sul, se fez 18 graus, alguém já fala: “hoje tá calorzinho”.",
        ],
    },
    "vituw": {
        "palavras": ["vituw"],
        "exato": False,
        "respostas": [
            "Vituw mencionado. A Yamaha acabou de sentir uma presença forte no chat.",
            "Vituw online. Se ele não falar da Tracer 900GT em 10 segundos, chamem ajuda.",
            "Vituw mencionado. A Yamaha acabou de sentir uma presença forte no chat.",
            "Vituw online. Se ele não falar da Tracer 900GT em 10 segundos, chamem ajuda.",
            "Falaram Vituw e o ego dele abriu em tela cheia.",
            "Vituw já inventou alguma fofoca hoje? ",
            "Vituw cuidado! tem mulheres de olho na sua mulher 👀",
        ],
    },
    "umbra": {
        "palavras": ["umbra"],
        "exato": False,
        "respostas": [
            "Umbra online. Cuidado, o nepotismo chegou com carisma.",
            "Umbra apareceu. A mini Vituw foi ativada.",
            "A veia das invasões foi invocada.",
            "Quinta-feira sem Umbra já virou evento fixo da FDN.",
            "Umbra sumiu? Confere o calendário. Se for quinta, tá explicado.",
            "Respeita a vovó da linha de frente",
            "Falaram Umbra e a bengala das invasões já foi equipada.",
            "A skin da Umbra é de velha porque ela já viu tanta invasão que virou patrimônio.",
        ],
    },
    "akayubi": {
        "palavras": ["akayubi"],
        "exato": False,
        "respostas": [
            "Akay online. A dona apareceu, finjam que estavam se comportando.",
            "Akayubi apareceu. se o servidor cair ela levanta no ódio.",
            "Akay detectada. Modo dev ativado, paciência desativada.",
            "FDN funcionando porque a Akay sofre em silêncio nos bastidores.",
            "Akay online. O Vituw perdeu 30% da pose e 100% da razão.",
            "Akay me criou e agora eu espalho gatilho como se fosse herança genética.",
            "Umbra, tua mãe chegou.",
        ],
    },
    "Lilly": {
        "palavras": ["lilly"],
        "exato": False,
        "respostas": [
            "Lilly online. A recrutadora chegou, provavelmente atrasada, mas chegou.",
            "Lilly presente. Yuzuro ausente, como manda a tradição.",
            "Lilly online. Agora falta o Yuzuro lembrar que também existe no clã.",
            "Se citar Lilly três vezes, aparece uma recrutadora com ficha pronta e cachorro dançando.",
        ],
    },
    "trabalho": {
        "palavras": ["trabalho"],
        "exato": True,
        "respostas": [
            "A vida do CLT é praticamente um regime semiaberto: trabalha de dia e volta à noite só para dormir.",
        ],
    },
    "miss": {
        "palavras": ["miss"],
        "exato": False,
        "respostas": [
            "Miss online. A recrutadora importada de Portugal chegou.",
            "A Miss pode sumir nos eventos, mas no recrutamento ela entrega.",
            "Miss apareceu. Alguém abriu ticket ou Portugal liberou ela?",
            "Miss online. Ou ela venceu o sono, ou amanhã tem arrependimento.",
            "Miss sumiu do evento. Provavelmente dormiu antes da invasão começar.",
            "Miss chegou. A caixa de sapato mais carismática da FDN.",
            "Falaram Miss e alguém já procurou a embalagem dela.",
            "Miss vai pra invasão/jogatina? Cuidado pra não confundirem com entrega dos Correios.",
            "Chegou a Miss, diretamente do setor de embalagens da FDN.",
            "Miss online. O pacote chegou, favor não amassar.",
            "Miss online. Procurar no chat não adianta, procura no Lord.",
            "A Miss vive tanto no Lord que já deve pagar aluguel lá.",
            "Falaram Ampox e a Miss já veio lembrar que ele é da pré-história.",
            "Ampox apareceu e a Miss já abriu a exposição “fósseis da FDN”.",
            "Falaram Ampox perto da Miss e ela já pegou a pá de escavação.",
        ],
    },
    "monny": {
        "palavras": ["monny"],
        "exato": False,
        "respostas": [
            "Monny apareceu. A sync saiu do modo invisível.",
            "A nossa sync apareceu. Milagre registrado nos logs da FDN.",
            "Falaram Monny e ela provavelmente vai responder daqui a 3 dias ou no PV da Akay.",
            "Se a Monny apareceu no chat, a lua deve estar em alinhamento perfeito.",
            "Monny online. Reagir no aviso continua sendo uma missão secundária.",
            "Monny e Akay são amigas de antes da FDN ser FDN. Respeita a lore.",
            "Falaram Monny e a call ganhou uma voz fofinha com potencial de bagunça.",
            "Monny pode sumir do chat, mas em dia de evento ela aparece pra honrar.",
        ],
    },
    "ampox": {
        "palavras": ["ampox"],
        "exato": False,
        "respostas": [
            "Ampox apareceu. Preparem o psicológico e escondam os pontos fracos.",
            "Falaram Ampox e a língua afiada já veio com atualização nova",
            "Ampox não perdoa ninguém, ele só escolhe a ordem das vítimas.",
            "Akay, cuidado. O Ampox tá rondando o Vituw de novo.",
            "Ampox e Miss no mesmo chat é briga de idosos com energia adolescente.",
            "Ampox chegou. O museu perdeu uma peça rara.",
            "O Ampox é tão antigo que a primeira call dele foi por sinal de fumaça.",
            "Falaram Ampox e um dinossauro sentiu representatividade.",
            "Alguém falou six seven e o Ampox já pediu ban com urgência.",
            "O antigo voltou do sarcófago.",
        ],
    },
    "ren": {
        "palavras": ["ren"],
        "exato": False,
        "respostas": [
            "Ren apareceu. Alerta de raposa no território dos corvos.",
            "Ren chegou. Favor verificar se ele veio em paz ou veio chamar nossos corvos de urubu.",
            "A raposa da FOX apareceu. Corvos, mantenham a elegância.",
            "Ren online. Hoje é parceria ou provocação interclã?",
            "Ren foi citado. Akay, esconde o Vituw.",
            "Ren chegou. Umbra, vem buscar tua raposa antes que ele dê em cima do Vituw.",
            "Ren é líder da FOX… até o Vituw chegar com miojo de tomate e Tang.",
            "Falaram Ren e a FOX já recebeu proposta de compra por lanche escolar.",
            "Ren online. A FOX segue avaliada em uma refeição duvidosa.",
            "Ren apareceu. Vituw, cadê o Tang pra fechar a compra?",
            "Ren detectado. Akay, prepara o deboche e o suporte técnico.",
            "A FOX mandou o lobo-guará.",
            "A FOX tem raposa, a FDN tem corvo. Um rouba galinha, o outro observa sua alma.",
        ],
    },
}


def criar_intents():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    return intents
