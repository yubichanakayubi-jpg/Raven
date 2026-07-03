import random
import re
import unicodedata

import data.runtime as runtime


def classificar_intencao_mensagem(texto):
    if not texto:
        return "comentario"

    texto_limpo = " ".join(texto.strip().lower().split())
    if not texto_limpo:
        return "comentario"

    texto_limpo = unicodedata.normalize("NFKD", texto_limpo).encode("ascii", "ignore").decode("ascii")

    if "?" in texto_limpo:
        return "pergunta"

    inicios_de_pergunta = (
        "como ",
        "quando ",
        "onde ",
        "qual ",
        "quais ",
        "quem ",
        "porque ",
        "por que ",
        "pra que ",
        "para que ",
        "o que ",
        "que horas",
        "cade ",
        "sera que ",
        "tem como ",
        "tem chance ",
        "pode ",
        "poderia ",
        "consegue ",
        "conseguiria ",
        "da pra ",
        "vai ter ",
        "tu vai ",
        "voce vai ",
        "vc vai ",
        "ce vai ",
    )

    if texto_limpo.startswith(inicios_de_pergunta):
        return "pergunta"

    inicios_de_pedido = (
        "paga ",
        "manda ",
        "me da ",
        "da um ",
        "faz ",
        "fala ",
        "responde ",
        "explica ",
        "olha ",
        "pega ",
        "solta ",
        "conta ",
        "chama ",
        "bota ",
        "envia ",
        "traz ",
        "me arruma ",
        "me passa ",
        "manda ai ",
        "manda ae ",
    )

    if texto_limpo.startswith(inicios_de_pedido):
        return "pedido"

    return "comentario"


def mensagem_parece_pergunta(texto):
    return classificar_intencao_mensagem(texto) == "pergunta"


def gatilho_encontrado(texto, gatilho):
    sinais = [".", ",", "!", "?", ":", ";", "(", ")", "[", "]", "{", "}", "\n"]
    texto_limpo = texto.lower()

    for sinal in sinais:
        texto_limpo = texto_limpo.replace(sinal, " ")

    palavras = texto_limpo.split()

    if " " in gatilho:
        return gatilho.strip().lower() in texto.lower()

    return gatilho.lower() in palavras


def limitar_emojis_por_frase(texto, max_emojis_por_frase=1):
    if not texto:
        return texto

    emojis_comuns = {
        "Ã°Å¸Ëœâ‚¬", "Ã°Å¸ËœÆ’", "Ã°Å¸Ëœâ€ž", "Ã°Å¸ËœÂ", "Ã°Å¸Ëœâ€ ", "Ã°Å¸Ëœâ€¦", "Ã°Å¸Ëœâ€š", "Ã°Å¸Â¤Â£", "Ã°Å¸ËœÅ ", "Ã°Å¸Ëœâ€¡", "Ã°Å¸â„¢â€š", "Ã°Å¸â„¢Æ’", "Ã°Å¸Ëœâ€°", "Ã°Å¸ËœÂ", "Ã°Å¸Â¥Â°",
        "Ã°Å¸ËœËœ", "Ã°Å¸Ëœâ€¹", "Ã°Å¸ËœÅ½", "Ã°Å¸Â¤â€", "Ã°Å¸ËœÂ", "Ã°Å¸Ëœâ€˜", "Ã°Å¸ËœÂ¶", "Ã°Å¸â„¢â€ž", "Ã°Å¸ËœÂ", "Ã°Å¸ËœÂ£", "Ã°Å¸ËœÂ¥", "Ã°Å¸ËœÂ®", "Ã°Å¸Â¤Â", "Ã°Å¸ËœÂ¯", "Ã°Å¸ËœÂª",
        "Ã°Å¸ËœÂ«", "Ã°Å¸Â¥Â±", "Ã°Å¸ËœÂ´", "Ã°Å¸ËœÅ’", "Ã°Å¸Ëœâ€º", "Ã°Å¸ËœÅ“", "Ã°Å¸ËœÂ", "Ã°Å¸Â¤Â¤", "Ã°Å¸Ëœâ€™", "Ã°Å¸Ëœâ€œ", "Ã°Å¸Ëœâ€", "Ã°Å¸Ëœâ€¢", "Ã°Å¸â„¢Â", "Ã¢ËœÂ¹", "Ã¢ËœÂ¹Ã¯Â¸Â", "Ã°Å¸Ëœâ€“",
        "Ã°Å¸ËœÅ¾", "Ã°Å¸ËœÅ¸", "Ã°Å¸ËœÂ­", "Ã°Å¸ËœÂ¤", "Ã°Å¸ËœÂ¢", "Ã°Å¸ËœÂ©", "Ã°Å¸ËœÂ¡", "Ã°Å¸ËœÂ ", "Ã°Å¸Â¤Â¬", "Ã°Å¸ËœÂ³", "Ã°Å¸Â¥Âµ", "Ã°Å¸Â¥Â¶", "Ã°Å¸ËœÂ±", "Ã°Å¸ËœÂ¨", "Ã°Å¸ËœÂ°",
        "Ã°Å¸ËœÂ¬", "Ã°Å¸Â¤Â¯", "Ã°Å¸Â¤Â¡", "Ã°Å¸â€™â‚¬", "Ã¢ËœÂ ", "Ã¢ËœÂ Ã¯Â¸Â", "Ã°Å¸â€˜â‚¬", "Ã°Å¸â€Â¥", "Ã¢Å“Â¨", "Ã°Å¸â€™â€¦", "Ã°Å¸Â¤Â", "Ã¢ÂÂ¤Ã¯Â¸Â", "Ã¢ÂÂ¤", "Ã°Å¸â€™â€", "Ã°Å¸â€™â€¢", "Ã°Å¸â€™â€“",
        "Ã°Å¸â€™â„¢", "Ã°Å¸â€“Â¤", "Ã°Å¸Â¤Â", "Ã°Å¸â€˜Â", "Ã°Å¸â€˜Å½", "Ã°Å¸â„¢Â", "Ã°Å¸Â¤Â·", "Ã°Å¸Â¤Â¦", "Ã°Å¸Â¥Â²", "Ã°Å¸ËœÂµ", "Ã°Å¸ËœÂµÃ¢â‚¬ÂÃ°Å¸â€™Â«"
    }

    frases = []
    atual = ""

    for char in texto:
        atual += char
        if char in ".!?":
            frases.append(atual)
            atual = ""

    if atual.strip():
        frases.append(atual)

    frases_processadas = []

    for frase in frases:
        contador = 0
        nova_frase = ""

        i = 0
        while i < len(frase):
            char = frase[i]

            if char in emojis_comuns:
                if contador < max_emojis_por_frase:
                    nova_frase += char
                    contador += 1
            else:
                nova_frase += char

            i += 1

        frases_processadas.append(" ".join(nova_frase.split()))

    return " ".join(frases_processadas).strip()


def manter_so_uma_resposta(texto, max_chars=320, max_linhas=3, max_frases=2):
    if not texto:
        return texto

    linhas = [" ".join(linha.split()) for linha in str(texto).splitlines() if linha.strip()]
    if linhas:
        linhas = linhas[:max_linhas]
        texto = "\n".join(linhas).strip()
    else:
        texto = " ".join(str(texto).split())

    finais = [". ", "! ", "? "]
    frases = []
    restante = texto if "\n" not in texto else None

    if restante is not None:
        while restante:
            encontrou = False
            for final in finais:
                pos = restante.find(final)
                if pos != -1:
                    frase = restante[:pos + 1].strip()
                    if frase:
                        frases.append(frase)
                    restante = restante[pos + 2:].strip()
                    encontrou = True
                    break
            if not encontrou:
                if restante.strip():
                    frases.append(restante.strip())
                break

        if len(frases) > max_frases:
            frases = frases[:max_frases]

        texto = " ".join(frases).strip()

    if len(texto) > max_chars:
        texto = texto[:max_chars].rsplit(" ", 1)[0].strip()
        texto = texto.rstrip(" ,;:-")
        if texto and texto[-1] not in ".!?":
            texto += "."

    if texto and texto[-1] not in ".!?":
        texto += "."

    return texto


def escolher_resposta_gatilho(chave, respostas):
    if not respostas:
        return None

    ultima_resposta = runtime.ultimas_respostas_gatilho.get(chave)
    opcoes = [resposta for resposta in respostas if resposta != ultima_resposta]

    if not opcoes:
        opcoes = list(respostas)

    resposta_escolhida = random.choice(opcoes)
    runtime.ultimas_respostas_gatilho[chave] = resposta_escolhida
    runtime.salvar_ultimas_respostas_gatilho()
    return resposta_escolhida


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

    linhas_limpas = [" ".join(linha.split()) for linha in texto.splitlines() if linha.strip()]
    texto = "\n".join(linhas_limpas).strip() if linhas_limpas else " ".join(texto.split())
    texto = manter_so_uma_resposta(texto, max_chars=320, max_linhas=3, max_frases=2)
    texto = limitar_emojis_por_frase(texto, max_emojis_por_frase=1)
    correcoes_simples = {
        "estavavamos": "estávamos",
        "estavavámos": "estávamos",
        "voçe": "você",
        "naum": "não",
    }
    for erro, correto in correcoes_simples.items():
        texto = re.sub(rf"\b{re.escape(erro)}\b", correto, texto, flags=re.IGNORECASE)

    return texto


def _formatar_numero_curto(valor):
    if float(valor).is_integer():
        return str(int(valor))

    return f"{valor:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def resposta_percentual_deterministica(mensagem_bot, mensagem_usuario):
    if not mensagem_bot or not mensagem_usuario:
        return None

    percentuais_bot = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", mensagem_bot)
    if len(percentuais_bot) != 1:
        return None

    match_usuario = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*%?\s*", mensagem_usuario)
    if not match_usuario:
        return None

    referencia = float(percentuais_bot[0].replace(",", "."))
    valor_usuario = float(match_usuario.group(1).replace(",", "."))
    diferenca = valor_usuario - referencia

    referencia_texto = _formatar_numero_curto(referencia)
    diferenca_texto = _formatar_numero_curto(abs(diferenca))

    if abs(diferenca) < 1e-9:
        return f"Aí sim, bateu certinho nos {referencia_texto}%."

    if diferenca > 0:
        return f"Aí ficou {diferenca_texto}% acima dos {referencia_texto}% que eu falei."

    return f"Aí ficou {diferenca_texto}% abaixo dos {referencia_texto}% que eu falei."


def estrelas_texto(nota):
    return "\u2b50" * max(1, min(5, int(nota)))
