import discord

from config import (
    ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID,
    RAVEN_FAN_LOG_CHANNEL_ID,
    XP_ANNOUNCE_CHANNEL_ID,
)
from services.server_config import obter_valor_config


COR_FDN = 0x00FFFF
RODAPE_FDN = "FDN — Filhos da Noite"

CONQUISTA_EMBEDS = {
    "corvo_noturno": {
        "titulo": "🐦‍⬛ Um novo Corvo despertou!",
        "descricao": (
            "Parabéns, {member_mention}!\n\n"
            "Você alcançou **20.000 XP** e conquistou o cargo **𓆩✦ Corvo Noturno ✦𓆪**.\n\n"
            "Sua presença começou a ecoar pela noite da FDN."
        ),
        "cargo_nome": "𓆩✦ Corvo Noturno ✦𓆪",
        "categoria": "XP do Chat",
        "campos": (
            ("Conquista", "Corvo Noturno"),
            ("Categoria", "XP do Chat"),
            ("XP alcançado", "20.000 XP"),
            ("Próxima meta", "50.000 XP — Corvo Lunar"),
        ),
        "canal_config": "XP_ANNOUNCE_CHANNEL_ID",
        "canal_padrao": XP_ANNOUNCE_CHANNEL_ID,
    },
    "corvo_lunar": {
        "titulo": "🌙 O Corvo subiu sob a luz da Lua!",
        "descricao": (
            "Parabéns, {member_mention}!\n\n"
            "Você alcançou **50.000 XP** e evoluiu para **𓆩✦ Corvo Lunar ✦𓆪**.\n\n"
            "A lua reconheceu sua constância, sua presença e sua marca dentro da FDN."
        ),
        "cargo_nome": "𓆩✦ Corvo Lunar ✦𓆪",
        "categoria": "XP do Chat",
        "campos": (
            ("Conquista", "Corvo Lunar"),
            ("Categoria", "XP do Chat"),
            ("XP alcançado", "50.000 XP"),
            ("Próxima meta", "100.000 XP — Corvo Celestial"),
        ),
        "canal_config": "XP_ANNOUNCE_CHANNEL_ID",
        "canal_padrao": XP_ANNOUNCE_CHANNEL_ID,
    },
    "corvo_celestial": {
        "titulo": "🌌 Um Corvo alcançou o céu da FDN!",
        "descricao": (
            "Parabéns, {member_mention}!\n\n"
            "Você alcançou **100.000 XP** e conquistou o cargo máximo **𓆩✦ Corvo Celestial ✦𓆪**.\n\n"
            "Seu nome agora brilha entre os mais presentes da noite."
        ),
        "cargo_nome": "𓆩✦ Corvo Celestial ✦𓆪",
        "categoria": "XP do Chat",
        "campos": (
            ("Conquista", "Corvo Celestial"),
            ("Categoria", "XP do Chat"),
            ("XP alcançado", "100.000 XP"),
            ("Status", "Cargo máximo de XP alcançado"),
        ),
        "canal_config": "XP_ANNOUNCE_CHANNEL_ID",
        "canal_padrao": XP_ANNOUNCE_CHANNEL_ID,
    },
    "invasor_noturno": {
        "titulo": "🌑 A noite marcou sua presença!",
        "descricao": (
            "Parabéns, {member_mention}!\n\n"
            "Você completou **10 presenças em invasões** e conquistou o cargo **𓆩✦ Invasor Noturno ✦𓆪**.\n\n"
            "Mapa após mapa, dança após dança, sua presença fez parte da marca da FDN."
        ),
        "cargo_nome": "𓆩✦ Invasor Noturno ✦𓆪",
        "categoria": "Presença em Invasões",
        "campos": (
            ("Conquista", "Invasor Noturno"),
            ("Categoria", "Presença em Invasões"),
            ("Progresso", "{progresso}"),
            ("Status", "Conquista desbloqueada"),
        ),
        "progresso_padrao": "10/10",
        "canal_config": "ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID",
        "canal_padrao": ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID,
    },
    "jogador_abissal": {
        "titulo": "🎮 O abismo chamou, e você respondeu!",
        "descricao": (
            "Parabéns, {member_mention}!\n\n"
            "Você completou **10 presenças em jogatinas** e conquistou o cargo **𓆩✦ Jogador Abissal ✦𓆪**.\n\n"
            "Entre desafios, caos e partidas, você provou que faz parte da diversão da noite."
        ),
        "cargo_nome": "𓆩✦ Jogador Abissal ✦𓆪",
        "categoria": "Presença em Jogatinas",
        "campos": (
            ("Conquista", "Jogador Abissal"),
            ("Categoria", "Presença em Jogatinas"),
            ("Progresso", "{progresso}"),
            ("Status", "Conquista desbloqueada"),
        ),
        "progresso_padrao": "10/10",
        "canal_config": "ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID",
        "canal_padrao": ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID,
    },
    "cinefilo_estelar": {
        "titulo": "🍿 As estrelas abriram a sessão!",
        "descricao": (
            "Parabéns, {member_mention}!\n\n"
            "Você completou **6 presenças no Cinema FDN** e conquistou o cargo **𓆩✦ Cinéfilo Estelar ✦𓆪**.\n\n"
            "Entre filmes, surtos, risadas e comentários, você garantiu seu lugar na plateia da noite."
        ),
        "cargo_nome": "𓆩✦ Cinéfilo Estelar ✦𓆪",
        "categoria": "Cinema FDN",
        "campos": (
            ("Conquista", "Cinéfilo Estelar"),
            ("Categoria", "Cinema FDN"),
            ("Progresso", "{progresso}"),
            ("Status", "Conquista desbloqueada"),
        ),
        "progresso_padrao": "6/6",
        "canal_config": "ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID",
        "canal_padrao": ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID,
    },
    "fa_do_raven": {
        "titulo": "🐦‍⬛ O Raven reconheceu sua voz!",
        "descricao": (
            "Parabéns, {member_mention}!\n\n"
            "Você respondeu **35 perguntas diárias do Raven** dentro do prazo e conquistou o cargo **𓆩✦ Fã do Raven ✦𓆪**.\n\n"
            "Nem toda resposta passa despercebida. O corvo observou cada uma."
        ),
        "cargo_nome": "𓆩✦ Fã do Raven ✦𓆪",
        "categoria": "Perguntas do Raven",
        "campos": (
            ("Conquista", "Fã do Raven"),
            ("Categoria", "Perguntas do Raven"),
            ("Progresso", "{progresso}"),
            ("Status", "Conquista desbloqueada"),
        ),
        "progresso_padrao": "35/35",
        "canal_config": "RAVEN_FAN_LOG_CHANNEL_ID",
        "canal_padrao": RAVEN_FAN_LOG_CHANNEL_ID,
    },
    "mensageiro_da_noite": {
        "titulo": "📢 A voz da noite foi ouvida!",
        "descricao": (
            "Parabéns, {member_mention}!\n\n"
            "Você alcançou **5 pontos nas votações da staff** e conquistou o cargo **𓆩✦ Mensageiro da Noite ✦𓆪**.\n\n"
            "Sua voz ecoou nas invasões, chamou presença e ajudou a espalhar o nome da FDN pelos mapas."
        ),
        "cargo_nome": "𓆩✦ Mensageiro da Noite ✦𓆪",
        "categoria": "Destaque de Invasão",
        "campos": (
            ("Conquista", "Mensageiro da Noite"),
            ("Categoria", "Destaque de Invasão"),
            ("Progresso", "{progresso}"),
            ("Status", "Conquista desbloqueada"),
        ),
        "progresso_padrao": "5/5",
        "canal_config": "ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID",
        "canal_padrao": ACHIEVEMENTS_ANNOUNCE_CHANNEL_ID,
    },
}


async def _resolver_canal(bot, guild, canal_id):
    if bot is None or guild is None or not canal_id:
        return None

    try:
        canal_id = int(canal_id)
    except (TypeError, ValueError):
        return None

    canal = bot.get_channel(canal_id)
    if canal is not None:
        return canal

    try:
        return await bot.fetch_channel(canal_id)
    except Exception:
        return None


def obter_meta_anuncio_conquista(cargo_key):
    return CONQUISTA_EMBEDS.get(str(cargo_key or "").strip().lower())


async def enviar_embed_conquista(bot, membro, cargo_key, canal_id=None, progresso=None):
    meta = obter_meta_anuncio_conquista(cargo_key)
    guild = getattr(membro, "guild", None)
    if meta is None or membro is None or guild is None:
        return False

    canal_destino_id = canal_id
    if canal_destino_id is None:
        canal_destino_id = obter_valor_config(guild, meta["canal_config"], meta["canal_padrao"])

    canal = await _resolver_canal(bot, guild, canal_destino_id)
    if canal is None:
        return False

    progresso_final = str(progresso or meta.get("progresso_padrao") or "").strip()
    descricao = meta["descricao"].format(member_mention=membro.mention)

    embed = discord.Embed(
        title=meta["titulo"],
        description=descricao,
        color=discord.Color(COR_FDN),
    )

    for nome, valor in meta.get("campos", ()):
        embed.add_field(
            name=nome,
            value=str(valor).format(progresso=progresso_final),
            inline=False,
        )

    embed.set_footer(text=RODAPE_FDN)

    try:
        await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    except Exception:
        return False

    return True


async def enviar_anuncio_conquista(
    guild,
    membro,
    cargo,
    nome_conquista,
    tipo_conquista,
    canal_id,
    progresso=None,
    proxima_meta=None,
    bot=None,
):
    cargo_key = str(cargo or nome_conquista or "").strip().lower()
    if cargo_key not in CONQUISTA_EMBEDS:
        return False
    return await enviar_embed_conquista(
        bot,
        membro,
        cargo_key,
        canal_id=canal_id,
        progresso=progresso,
    )
