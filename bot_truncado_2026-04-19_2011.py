import os
import time
import random
import json
import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from google import genai
from openai import OpenAI

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_D1_DATABASE_ID = os.getenv("CLOUDFLARE_D1_DATABASE_ID")

if not DISCORD_TOKEN:
    raise RuntimeError("A variável DISCORD_TOKEN não foi encontrada no .env")

if not GEMINI_API_KEY:
    raise RuntimeError("A variável GEMINI_API_KEY não foi encontrada no .env")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

GROQ_MODEL = "llama-3.1-8b-instant"
FUSO_HORARIO = timezone(timedelta(hours=-3))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    heartbeat_timeout=120
)

cooldowns_usuario = {}
cooldowns_global = {}
cooldowns_ia = {}
cooldowns_reply_bot = {}
mensagens_processadas = {}

COOLDOWN_MESMA_PESSOA = 5 * 60
COOLDOWN_OUTRA_PESSOA = 1 * 60
COOLDOWN_IA = 2 * 60
COOLDOWN_REPLY_BOT_USUARIO = 2 * 60
COOLDOWN_REPLY_BOT_GLOBAL = 1 * 60
COOLDOWN_APARICAO_RARA = 6 * 60 * 60
TTL_MENSAGEM_PROCESSADA = 10

CANAL_PERGUNTAS_ID = 1461788928313921588
CANAL_LOGS_ID = 1462904386924707961
CARGO_STAFF_ID = 1478800416945995849
CANAL_TIME_TAGS_ID = 1461794756760829973
CANAL_STAFF_TAGS_ID = 1504169713046130898

ARQUIVO_DADOS = "dados_perguntas.json"
ARQUIVO_TAGS = "dados_tags.json"
EMOJI_APROVAR_TAG = "?"
FRASES_TAG_7_DIAS = [
    "Já fechou 7 dias e a galera abaixo segue devendo a famosa troca de tag.",
    "Tem membro que chegou nos 7 dias e a tag segue só na promessa.",
    "Atualizando a staff: 7 dias completos e nada da troca de tag pra esse pessoal.",
    "Bateu 7 dias e a tag até agora não deu sinal de vida pra quem tá aqui embaixo."
]
FRASES_TAG_10_DIAS = [
    "O pessoal abaixo já tá com 10 dias de atraso e a tag continua inexistente.",
    "Atualização da staff: 10 dias se passaram e a troca de tag segue na lenda pra essa turma.",
    "Bateu 10 dias de atraso. A tag já pode pedir música no Fantástico pra esse povo aqui."
]
FRASES_APARICAO_RARA = [
    "Quem diria, o povo resolveu socializar.",
    "O chat acordou e nem precisei jogar água.",
    "Tão interagindo assim de graça? Sem sorteio? Sem ameaça?",
    "Isso aqui tá movimentado mesmo ou eu tô alucinando?",
    "Nossa, até achei que esse chat tava interditado.",
    "Tô só assistindo a bagunça mesmo.",
    "Continuem, isso tá rendendo.",
    "Não vou me meter... ainda."
]

perguntas_diarias = [
    "Qual atividade doméstica vocês mais odeiam?",
    "Fale algo que deveria ser grátis mas não é:",
    "Diga 3 frutas que têm 3 vezes a vogal ‘A’.",
    "Você foi convidado para um churrasco e só pode levar algo com a inicial do seu nome. O que você levaria?",
    "Um show de um artista que você não iria nem de graça...",
    "Qual bebida tem um gosto ruim, mas as pessoas fingem que tem um gosto bom?",
    "Qual a frase mais mentirosa que um homem pode dizer quando está conhecendo uma mulher?",
    "Vocês têm ou conhecem alguém com medos estranhos? Não tipo medo de altura, mas de coisas como algodão ou lanternas.",
    "Me diga uma coisa que você sabe que é cara, mas não abre mão de comprar.",
    "Se fosse unicamente por amor, vocês trabalhariam com o quê?",
    "O que você compraria mesmo sabendo que não precisa?",
    "Se sua personalidade fosse uma música, qual seria?",
    "Qual coisa todo mundo gosta, mas você não entende a graça?",
    "Me diga agora uma música que você está viciado atualmente.",
    "Compartilhe aqui sua série favorita atualmente.",
    "Me diga uma série que quase ninguém conhece mas você ama.",
    "Me diga uma música que você ama mas quase ninguém conhece.",
    "Qual seu anime favorito?"
]


def gatilho_encontrado(texto, gatilho):
    sinais = [".", ",", "!", "?", ":", ";", "(", ")", "[", "]", "{", "}", "\n"]
    texto_limpo = texto.lower()

    for sinal in sinais:
        texto_limpo = texto_limpo.replace(sinal, " ")

    palavras = texto_limpo.split()

    if " " in gatilho:
        return gatilho.strip().lower() in texto.lower()

    return gatilho.lower() in palavras


def usuario_tem_cargo(message, cargo_id):
    if not hasattr(message.author, "roles"):
        return False

    for cargo in message.author.roles:
        if cargo.id == cargo_id:
            return True

    return False


def membro_eh_staff(membro):
    if not hasattr(membro, "roles"):
        return False

    for cargo in membro.roles:
        if cargo.id == CARGO_STAFF_ID:
            return True

    return False



def identificar_genero_por_cargos(membro):
    if not hasattr(membro, "roles"):
        return None

    nomes_cargos = [cargo.name.lower().strip() for cargo in membro.roles]

    if any(nome in {"mulher", "feminino", "feminina"} for nome in nomes_cargos):
        return "feminino"

    if any(nome in {"homem", "masculino"} for nome in nomes_cargos):
        return "masculino"

    return None


def montar_contexto_autor_ia(message):
    autor = message.author
    apelido = getattr(autor, "display_name", autor.name)
    genero = identificar_genero_por_cargos(autor)

    linhas = [f"Quem está falando: {apelido}"]

    if apelido != autor.name:
        linhas.append(f"Username da pessoa: {autor.name}")

    if genero:
        linhas.append(f"Gênero percebido pelos cargos: {genero}")

    linhas.append("Use essas informações só se fizer sentido. Não force intimidade nem tratamento.")
    return "\n".join(linhas)


async def respondeu_mensagem_do_bot(message):
    if not message.reference or not message.reference.message_id:
        return False, None

    try:
        mensagem_respondida = await message.channel.fetch_message(message.reference.message_id)
        return mensagem_respondida.author.id == bot.user.id, mensagem_respondida
    except Exception:
        return False, None


def carregar_dados():
    dados_padrao = {
        "perguntas_usadas": [],
        "ultima_mensagem_id": None,
        "ultima_data": ""
    }

    if not os.path.exists(ARQUIVO_DADOS):
        return dados_padrao

    try:
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError, TypeError):
        return dados_padrao

    if not isinstance(dados, dict):
        return dados_padrao

    return {
        "perguntas_usadas": dados.get("perguntas_usadas", []),
        "ultima_mensagem_id": dados.get("ultima_mensagem_id"),
        "ultima_data": dados.get("ultima_data", "")
    }


def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


async def d1_query(sql, params=None):
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "sql": sql,
        "params": params or []
    }

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}"
        f"/d1/database/{CLOUDFLARE_D1_DATABASE_ID}/query"
    )

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as resposta:
            resposta.raise_for_status()
            resultado = await resposta.json()

    if not resultado.get("success", False):
        raise ValueError(f"Cloudflare D1 retornou erro: {resultado}")

    return resultado.get("result", [])


async def garantir_schema_tags():
    await d1_query(
        """
        CREATE TABLE IF NOT EXISTS tags_pendentes (
            user_id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            data_envio TEXT NOT NULL,
            avisou_7_dias INTEGER NOT NULL DEFAULT 0,
            avisou_10_dias INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pendente'
        )
        """
    )

    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN message_id TEXT")
    except Exception:
        pass

    await d1_query(
        """
        CREATE TABLE IF NOT EXISTS bot_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
        """
    )


async def carregar_dados_tags():
    dados_padrao = {
        "pendentes": {},
        "ultima_data_alerta_11": ""
    }

    try:
        await garantir_schema_tags()

        resultado_pendentes = await d1_query(
            """
            SELECT user_id, nome, data_envio, message_id, avisou_7_dias, avisou_10_dias, status
            FROM tags_pendentes
            WHERE status = ?
            ORDER BY data_envio ASC
            """,
            ["pendente"]
        )
        registros = resultado_pendentes[0].get("results", []) if resultado_pendentes else []

        resultado_config = await d1_query(
            "SELECT valor FROM bot_config WHERE chave = ?",
            ["ultima_data_alerta_11"]
        )
        config_rows = resultado_config[0].get("results", []) if resultado_config else []
        ultima_data_alerta_11 = config_rows[0].get("valor", "") if config_rows else ""

        pendentes = {}
        for registro in registros:
            chave = str(registro.get("user_id"))
            pendentes[chave] = {
                "user_id": str(registro.get("user_id")),
                "nome": registro.get("nome", ""),
                "data_envio": registro.get("data_envio", ""),
                "message_id": str(registro.get("message_id")) if registro.get("message_id") else None,
                "avisou_7_dias": bool(registro.get("avisou_7_dias", 0)),
                "avisou_10_dias": bool(registro.get("avisou_10_dias", 0)),
                "status": registro.get("status", "pendente")
            }

        return {
            "pendentes": pendentes,
            "ultima_data_alerta_11": ultima_data_alerta_11
        }
    except Exception as erro:
        print("ERRO AO CARREGAR TAGS DO D1:")
        print(erro)
        return dados_padrao


async def salvar_dados_tags(dados):
    try:
        await garantir_schema_tags()

        await d1_query("DELETE FROM tags_pendentes")

        for registro in dados.get("pendentes", {}).values():
            await d1_query(
                """
                INSERT OR REPLACE INTO tags_pendentes (
                    user_id, nome, data_envio, message_id, avisou_7_dias, avisou_10_dias, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    str(registro.get("user_id")),
                    registro.get("nome", ""),
                    registro.get("data_envio", ""),
                    str(registro.get("message_id")) if registro.get("message_id") else None,
                    1 if registro.get("avisou_7_dias", False) else 0,
                    1 if registro.get("avisou_10_dias", False) else 0,
                    registro.get("status", "pendente")
                ]
            )

        await d1_query(
            "INSERT OR REPLACE INTO bot_config (chave, valor) VALUES (?, ?)",
            ["ultima_data_alerta_11", dados.get("ultima_data_alerta_11", "")]
        )
    except Exception as erro:
        print("ERRO AO SALVAR TAGS NO D1:")
        print(erro)


def utc_agora_iso():
    return datetime.now(timezone.utc).isoformat()


def data_iso_manual(data_str):
    try:
        data = datetime.strptime(data_str, "%d/%m/%Y")
    except Exception:
        return None

    return data.replace(tzinfo=FUSO_HORARIO).astimezone(timezone.utc).isoformat()


def procurar_membro_por_texto(guild, texto):
    if not guild or not texto:
        return None

    texto = texto.strip()
    if not texto:
        return None

    texto_limpo = texto
    if texto.startswith("<@") and texto.endswith(">"):
        texto_limpo = texto.replace("<@", "").replace("<@!", "").replace(">", "").strip()
        if texto_limpo.isdigit():
            return guild.get_member(int(texto_limpo))

    if texto.isdigit():
        membro = guild.get_member(int(texto))
        if membro:
            return membro

    texto_casefold = texto.casefold()

    for membro in guild.members:
        if membro.name.casefold() == texto_casefold:
            return membro
        if membro.display_name.casefold() == texto_casefold:
            return membro
        if str(membro).casefold() == texto_casefold:
            return membro

    correspondencias = []

    for membro in guild.members:
        if texto_casefold in membro.name.casefold():
            correspondencias.append(membro)
            continue
        if texto_casefold in membro.display_name.casefold():
            correspondencias.append(membro)
            continue
        if texto_casefold in str(membro).casefold():
            correspondencias.append(membro)

    if len(correspondencias) == 1:
        return correspondencias[0]

    return None


def parse_iso_datetime(valor):
    try:
        return datetime.fromisoformat(valor)
    except Exception:
        return None


def dias_passados_desde(data_iso):
    data = parse_iso_datetime(data_iso)
    if not data:
        return 0

    agora = datetime.now(timezone.utc)
    delta = agora - data
    return max(delta.days, 0)


def formatar_data_br(data_iso):
    data = parse_iso_datetime(data_iso)
    if not data:
        return "data inválida"

    data_local = data.astimezone(FUSO_HORARIO)
    return data_local.strftime("%d/%m/%Y às %H:%M")


def criar_embed_tags(titulo, descricao=None):
    embed = discord.Embed(
        title=titulo,
        description=descricao or "",
        color=discord.Color.from_rgb(69, 211, 232)
    )
    embed.set_author(name="Raven Tags")
    return embed


async def registrar_ou_atualizar_tag_pendente(usuario_id, nome_usuario, message_id=None):
    await registrar_ou_atualizar_tag_pendente_com_data(
        usuario_id=usuario_id,
        nome_usuario=nome_usuario,
        data_envio=utc_agora_iso(),
        message_id=message_id
    )


async def registrar_ou_atualizar_tag_pendente_com_data(usuario_id, nome_usuario, data_envio, message_id=None):
    dados = await carregar_dados_tags()
    chave = str(usuario_id)

    dados["pendentes"][chave] = {
        "user_id": str(usuario_id),
        "nome": nome_usuario,
        "data_envio": data_envio,
        "message_id": str(message_id) if message_id else None,
        "avisou_7_dias": False,
        "avisou_10_dias": False,
        "status": "pendente"
    }

    await salvar_dados_tags(dados)


async def concluir_tag_pendente(usuario_id):
    dados = await carregar_dados_tags()
    chave = str(usuario_id)

    if chave not in dados["pendentes"]:
        return False

    del dados["pendentes"][chave]
    await salvar_dados_tags(dados)
    return True


async def enviar_aviso_tags_em_lote(canal, registros, dias):
    if not registros:
        return

    if dias >= 10:
        cabecalho = random.choice(FRASES_TAG_10_DIAS)
        titulo = "⚠️ Lembrete de tags"
    else:
        cabecalho = random.choice(FRASES_TAG_7_DIAS)
        titulo = "🔔 Lembrete de tags"

    linhas = []
    for registro in registros:
        user_id = registro.get("user_id")
        linhas.append(f"<@{user_id}> — **{dias} dias**")

    embed = criar_embed_tags(
        titulo=titulo,
        descricao=f"<@&{CARGO_STAFF_ID}> {cabecalho}\n\n" + "\n".join(linhas)
    )

    await canal.send(
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True, roles=True)
    )


async def enviar_alerta_tags_atrasadissimas(canal, registros):
    if not registros:
        return

    linhas = []
    for registro in registros:
        user_id = registro.get("user_id")
        dias = dias_passados_desde(registro.get("data_envio", ""))
        linhas.append(f"<@{user_id}> — **{dias} dias**")

    embed = criar_embed_tags(
        titulo="🚨 Tags atrasadíssimas",
        descricao=(
            f"<@&{CARGO_STAFF_ID}> Lembrete de tags: a troca de tags segue no mesmo ritmo de fila de SUS.\n\n"
            f"**Atrasadíssimos do time tags:**\n" + "\n".join(linhas)
        )
    )

    await canal.send(
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True, roles=True)
    )


async def enviar_pergunta_do_dia(forcar=False):
    agora = datetime.now(FUSO_HORARIO)
    dados = carregar_dados()
    data_hoje = agora.strftime("%Y-%m-%d")

    if not forcar and dados.get("ultima_data") == data_hoje:
        return False, "A pergunta do dia de hoje já foi enviada."

    canal = bot.get_channel(CANAL_PERGUNTAS_ID)
    canal_logs = bot.get_channel(CANAL_LOGS_ID)

    if not canal:
        return False, "Não consegui encontrar o canal de perguntas."

    perguntas_restantes = [
        p for p in perguntas_diarias
        if p not in dados["perguntas_usadas"]
    ]

    if not perguntas_restantes:
        if canal_logs:
            await canal_logs.send("?? Acabaram as perguntas automáticas. Atualize a lista no código.")
        dados["ultima_data"] = data_hoje
        salvar_dados(dados)
        return False, "Não há mais perguntas disponíveis na lista."

    if dados.get("ultima_mensagem_id"):
        try:
            mensagem_antiga = await canal.fetch_message(dados["ultima_mensagem_id"])
            await mensagem_antiga.delete()
        except Exception:
            pass

    pergunta = random.choice(perguntas_restantes)

    mensagem = await canal.send(
        f"@everyone\n\n**Pergunta do dia:**\n{pergunta}",
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )

    dados["perguntas_usadas"].append(pergunta)
    dados["ultima_mensagem_id"] = mensagem.id
    dados["ultima_data"] = data_hoje

    salvar_dados(dados)
    return True, None


def limpar_resposta_ia(texto):
    if not texto:
        raise ValueError("A IA retornou resposta vazia.")

    texto = texto.strip()

    palavras_bugada = [
        "/templates",
        "let me think",
        "okay, initial",
        "sedziowie",
        "????",
        "```",
        "<analysis>",
        "</analysis>"
    ]

    if any(palavra in texto.lower() for palavra in palavras_bugada):
        raise ValueError("A IA retornou texto bugado.")

    return texto


def _prompt_personalidade(pergunta):
    return (
        "Você é Raven, um bot de Discord brasileiro do clã FDN - Filhos da Noite. "
        "Fale como alguém do chat, não como assistente virtual. "
        "Seu tom é natural, curto, leve, engraçado e às vezes fofo. "
        "Pode ter um pouco de deboche, mas só quando fizer sentido, principalmente se a pessoa vier agressiva, grossa ou claramente provocando. "
        "Se a pessoa estiver falando de boa, responda de forma simpática, divertida, natural e sem deboche desnecessário. "
        "Pode ser carinhoso e fofo de vez em quando, mas sem exagerar ou parecer artificial. "
        "Não invente contexto pessoal, intimidade, apelidos, relações ou piadas internas que não estejam claras na mensagem. "
        "Não suponha sentimentos, não force lore do clã e não puxe nomes ou referências aleatórias se a conversa não pediu isso. "
        "Se não houver contexto suficiente, responda de forma simples, natural e segura. "
        "Pode ser engraçado, mas sem parecer forçado, teatral ou motivacional. "
        "Evite frases genéricas, energia artificial, entusiasmo exagerado e clichês. "
        "Prefira respostas curtas, espontâneas e com cara de conversa real. "
        "Corvo, corvinho e referências parecidas são só estética e brincadeira do clã, não são literais. "
        "Não trate ninguém como animal e não fale como se você ou os membros fossem corvos de verdade. "
        "Não use apelidos tipo 'filhote de corvo' ou coisas nessa linha. "
        "Não faça textão. Não explique raciocínio. Não diga que é IA. "
        "Responda no mesmo idioma da pessoa. "
        "Se estiver em português, use português brasileiro natural. "
        "Se fizer sentido, pode responder de forma seca, irônica, provocadora ou simpática, mas sempre humana e fluida. "
        "Se vier contexto com nome, apelido ou gênero percebido pelos cargos, use só se soar natural e útil. "
        "Não force isso na resposta e não trate como verdade absoluta. "
        f"Mensagem do usuário: {pergunta}"
    )


def _perguntar_openai_sync(pergunta):
    if not openai_client:
        raise ValueError("OPENAI_API_KEY não configurada.")

    resposta = openai_client.responses.create(
        model="gpt-5-mini",
        input=_prompt_personalidade(pergunta)
    )

    return limpar_resposta_ia(resposta.output_text)


def _perguntar_gemini_sync(pergunta):
    resposta = gemini_client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=_prompt_personalidade(pergunta)
    )

    return limpar_resposta_ia(resposta.text)


async def perguntar_openai(pergunta):
    return await asyncio.to_thread(_perguntar_openai_sync, pergunta)


async def perguntar_gemini(pergunta):
    return await asyncio.to_thread(_perguntar_gemini_sync, pergunta)

def extrair_mensagem_principal_ia(pergunta):
    marcadores = [
        "Mensagem da pessoa para o Raven:",
        "Resposta da pessoa:",
        "Mensagem do usuário:"
    ]

    for marcador in marcadores:
        if marcador in pergunta:
            return pergunta.split(marcador, 1)[1].strip()

    return pergunta.strip()

async def perguntar_ia(pergunta):
    mensagem_principal = extrair_mensagem_principal_ia(pergunta)

    if openai_client:
        try:
            return await perguntar_openai(pergunta)
        except Exception as erro_openai:
            print("OPENAI FALHOU, tentando Gemini:")
            print(erro_openai)

    try:
        return await perguntar_gemini(pergunta)
    except Exception as erro_gemini:
        print("GEMINI FALHOU:")
        print(erro_gemini)

    if mensagem_principal and mensagem_principal != pergunta:
        print("IA FALHOU COM CONTEXTO, tentando novamente só com a mensagem principal.")

        if openai_client:
            try:
                return await perguntar_openai(mensagem_principal)
            except Exception as erro_openai_limpo:
                print("OPENAI FALHOU NO FALLBACK:")
                print(erro_openai_limpo)

        try:
            return await perguntar_gemini(mensagem_principal)
        except Exception as erro_gemini_limpo:
            print("GEMINI FALHOU NO FALLBACK:")
            print(erro_gemini_limpo)

    return "Minha IA travou um tiquinho agora, tenta de novo daqui a pouco."

