import json
import os
import re
import unicodedata
from datetime import datetime, timezone


ARQUIVO_CADASTROS = "dados_cadastros.json"
NAO_IDENTIFICADO = "Não identificado"
NAO_INFORMADO = NAO_IDENTIFICADO


CAMPOS_CADASTRO = [
    "nick_discord",
    "username_roblox",
    "nome_atual_roblox",
    "idade",
    "ja_foi_de_outro_cla",
    "quais_clas",
    "motivo_saida",
    "disponibilidade",
    "participa_jogatinas",
    "consegue_colocar_tag",
    "consegue_seguir_instrucoes",
    "aceita_cores_fdn",
]


ALIASES_CAMPOS = {
    "nick_discord": ["nick no discord", "nick discord", "nick do discord", "discord", "nick"],
    "username_roblox": ["username roblox", "user roblox", "@ roblox", "roblox @", "username"],
    "nome_atual_roblox": [
        "nome atual no roblox",
        "nome atual",
        "nick no roblox",
        "nick roblox",
        "display name",
        "nome de exibicao",
        "tag do roblox",
        "tag roblox",
    ],
    "idade": ["idade", "age"],
    "ja_foi_de_outro_cla": [
        "ja foi de outro cla",
        "foi de outro cla",
        "ja participou de outros clas",
        "participou de outros clas",
        "clas anteriores",
    ],
    "quais_clas": [
        "se sim quais clas",
        "se sim, quais clas",
        "quais clas",
        "quais clans",
        "quais",
        "clas",
        "clans",
    ],
    "motivo_saida": [
        "quais motivos levaram a sua saida desses clas",
        "motivo da saida",
        "motivo",
    ],
    "disponibilidade": [
        "em quais periodos voce costuma estar disponivel",
        "periodos disponivel",
        "disponibilidade",
        "horario",
        "turno",
    ],
    "participa_jogatinas": [
        "costuma participar de invasoes e atividades em grupo",
        "invasoes e atividades em grupo",
        "participa de jogatinas",
        "participa de invasoes",
        "jogatinas",
        "invasoes",
    ],
    "consegue_colocar_tag": [
        "consegue colocar a tag agora",
        "consegue colocar tag",
        "tag agora",
        "pode colocar tag",
    ],
    "consegue_seguir_instrucoes": [
        "seguir instrucoes e manter atencao",
        "consegue seguir instrucoes",
        "manter atencao durante eventos",
    ],
    "aceita_cores_fdn": [
        "voce aceita fazer parte da fdn",
        "aceita fazer parte da fdn",
        "aceita as cores",
        "aceita ciano e preto",
        "cores ciano e preto",
        "nossas cores sao ciano e preto",
    ],
}


OPCOES_CAMPOS = {
    "ja_foi_de_outro_cla": ["Sim", "Não"],
    "disponibilidade": ["Manhã", "Tarde", "Noite", "Madrugada"],
    "participa_jogatinas": ["Sim", "Às vezes", "Não muito", "Não"],
    "consegue_colocar_tag": ["Sim", "Ainda não"],
    "consegue_seguir_instrucoes": ["Sim", "Não"],
    "aceita_cores_fdn": ["Sim", "Não"],
}


def normalizar_texto(texto):
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return texto.casefold().strip()


def normalizar_chave(valor):
    valor = normalizar_texto(valor)
    valor = re.sub(r"\s+", " ", valor)
    return valor


def carregar_dados_cadastros():
    dados_padrao = {
        "cadastros": {},
        "indices": {
            "autor_id": {},
            "member_id": {},
            "nick_discord": {},
            "username_roblox": {},
            "nome_atual_roblox": {},
            "status": {},
        },
    }

    if not os.path.exists(ARQUIVO_CADASTROS):
        return dados_padrao

    try:
        with open(ARQUIVO_CADASTROS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError, TypeError):
        return dados_padrao

    if not isinstance(dados, dict):
        return dados_padrao

    cadastros = dados.get("cadastros", {})
    if not isinstance(cadastros, dict):
        cadastros = {}

    return {
        "cadastros": cadastros,
        "indices": reconstruir_indices(cadastros),
    }


def salvar_dados_cadastros(dados):
    dados["indices"] = reconstruir_indices(dados.get("cadastros", {}))
    with open(ARQUIVO_CADASTROS, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def adicionar_indice(indices, nome_indice, chave, message_id):
    if not chave or chave in {NAO_INFORMADO, "Não informado"}:
        return

    chave_normalizada = normalizar_chave(str(chave))
    if not chave_normalizada:
        return

    valores = indices[nome_indice].setdefault(chave_normalizada, [])
    if message_id not in valores:
        valores.append(message_id)


def reconstruir_indices(cadastros):
    indices = {
        "autor_id": {},
        "member_id": {},
        "nick_discord": {},
        "username_roblox": {},
        "nome_atual_roblox": {},
        "status": {},
    }

    for message_id, registro in cadastros.items():
        campos = registro.get("campos", {})
        adicionar_indice(indices, "autor_id", registro.get("autor_id"), message_id)
        adicionar_indice(indices, "member_id", registro.get("member_id") or registro.get("autor_id"), message_id)
        adicionar_indice(indices, "nick_discord", registro.get("nick_discord") or campos.get("nick_discord"), message_id)
        adicionar_indice(indices, "username_roblox", registro.get("username_roblox") or campos.get("username_roblox"), message_id)
        adicionar_indice(indices, "nome_atual_roblox", registro.get("nome_atual_roblox") or campos.get("nome_atual_roblox"), message_id)
        adicionar_indice(indices, "status", registro.get("status"), message_id)

    return indices


def todos_aliases():
    aliases = []
    for campo, nomes in ALIASES_CAMPOS.items():
        for nome in nomes:
            aliases.append((campo, normalizar_texto(nome)))
    aliases.sort(key=lambda item: len(item[1]), reverse=True)
    return aliases


def limpar_linha_rotulo(linha):
    linha = re.sub(r"^[>\-\*\s•]+", "", linha or "").strip()
    linha = re.sub(r"^\d+\s*[\.\)\-]?\s*", "", linha).strip()
    return linha.strip("*_` ")


def valor_apos_pergunta(linha):
    match = re.search(r"[?？]\s*[,;:\-–—]?\s*(.+)$", linha or "")
    if not match:
        return ""

    valor = match.group(1).strip()
    if not valor or valor.startswith(("(", "[", "✅")):
        return ""
    return valor


def comeca_com_alias(texto_normalizado, alias):
    if texto_normalizado == alias:
        return True
    return re.match(rf"^{re.escape(alias)}(?:\s|[?:：,;.!])", texto_normalizado) is not None


def alias_colide_com_motivo(texto_normalizado, alias):
    return alias in {"quais", "clas", "clans"} and texto_normalizado.startswith("quais motivos")


def detectar_campo_na_linha(linha):
    linha_limpa = limpar_linha_rotulo(linha)
    linha_normalizada = normalizar_texto(linha_limpa)
    if not linha_normalizada:
        return None, ""

    partes = re.split(r"\s*[:：]\s*|\s+[–—-]\s+", linha_limpa, maxsplit=1)
    prefixo = normalizar_texto(partes[0])
    prefixo_base = prefixo.rstrip("?.!")

    for campo, alias in todos_aliases():
        if alias_colide_com_motivo(prefixo, alias):
            continue
        if prefixo_base == alias or comeca_com_alias(prefixo, alias):
            valor = partes[1].strip() if len(partes) > 1 else valor_apos_pergunta(linha_limpa)
            return campo, valor

    for campo, alias in todos_aliases():
        if alias_colide_com_motivo(linha_normalizada, alias):
            continue
        linha_base = linha_normalizada.rstrip("?.!")
        if (linha_base == alias or comeca_com_alias(linha_normalizada, alias)) and len(linha_normalizada) <= 160:
            return campo, valor_apos_pergunta(linha_limpa)

    return None, ""


def linha_eh_rotulo(linha):
    campo, _ = detectar_campo_na_linha(linha)
    return campo is not None


def obter_bloco_campo(linhas, campo_procurado):
    for indice, linha in enumerate(linhas):
        campo, valor_linha = detectar_campo_na_linha(linha)
        if campo != campo_procurado:
            continue

        bloco = []
        if valor_linha:
            bloco.append(valor_linha)
        elif campo == campo_procurado and campo in OPCOES_CAMPOS:
            bloco.append(linha)

        for proxima in linhas[indice + 1:]:
            if linha_eh_rotulo(proxima):
                break
            if proxima.strip():
                bloco.append(proxima.strip())

        return bloco

    return []


def valor_curto_seguro(valor, max_length=80):
    valor = (valor or "").strip()
    if not valor:
        return ""
    if "\n" in valor or len(valor) > max_length:
        return ""
    if linha_eh_rotulo(valor):
        return ""
    if valor.count(":") > 1:
        return ""
    return valor


def linha_explicativa(linha):
    linha_normalizada = normalizar_texto(linha)
    if not linha_normalizada:
        return True

    if linha_normalizada.startswith("(") and "opcional" in linha_normalizada:
        return True
    if "responda apenas" in linha_normalizada:
        return True
    if "se sentir confortavel" in linha_normalizada:
        return True

    return False


def obter_valor_texto(linhas, campo, max_length=80):
    bloco = obter_bloco_campo(linhas, campo)
    if not bloco:
        return NAO_IDENTIFICADO

    for linha in bloco:
        if linha_explicativa(linha):
            continue

        valor = valor_curto_seguro(linha, max_length=max_length)
        if valor and not valor.startswith(("(", "[", "✅")):
            return valor

    return NAO_IDENTIFICADO


def obter_idade(linhas):
    valor = obter_valor_texto(linhas, "idade", max_length=20)
    if valor == NAO_IDENTIFICADO:
        return valor

    match = re.search(r"\b([1-9][0-9]?)\b", valor)
    if not match:
        return NAO_IDENTIFICADO

    idade = int(match.group(1))
    if idade < 10 or idade > 99:
        return NAO_IDENTIFICADO

    return match.group(1)


def extrair_opcoes_marcadas(texto, opcoes, multiplo=False):
    texto_normalizado = normalizar_texto(texto)
    encontradas = []

    for opcao in sorted(opcoes, key=lambda item: len(normalizar_texto(item)), reverse=True):
        opcao_normalizada = normalizar_texto(opcao)
        padroes = [
            rf"[\(\[]\s*[xX✓✅]\s*[\)\]]\s*{re.escape(opcao_normalizada)}",
            rf"✅\s*{re.escape(opcao_normalizada)}",
            rf"{re.escape(opcao_normalizada)}\s*✅",
        ]

        for padrao in padroes:
            match = re.search(padrao, texto_normalizado)
            if match:
                encontradas.append((match.start(), opcao))
                break

    if encontradas:
        encontradas.sort(key=lambda item: item[0])
        valores = [opcao for _, opcao in encontradas]
        return ", ".join(valores) if multiplo else valores[0]

    texto_limpo = re.sub(r"[\(\[\]xX✓✅]", " ", texto_normalizado)
    texto_limpo = re.sub(r"\s+", " ", texto_limpo)
    opcoes_presentes = [opcao for opcao in opcoes if normalizar_texto(opcao) in texto_limpo]
    if len(opcoes_presentes) == 1:
        return opcoes_presentes[0]

    return NAO_IDENTIFICADO


def extrair_ficha_recrutamento(texto):
    linhas = [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]
    texto_normalizado = normalizar_texto(texto)
    possui_cabecalho = "ficha de recrutamento" in texto_normalizado
    campos_detectados = set()
    for linha in linhas:
        campo, _ = detectar_campo_na_linha(linha)
        if campo:
            campos_detectados.add(campo)

    def opcoes(campo, multiplo=False):
        bloco = obter_bloco_campo(linhas, campo)
        if not bloco:
            return NAO_IDENTIFICADO
        return extrair_opcoes_marcadas("\n".join(bloco), OPCOES_CAMPOS[campo], multiplo=multiplo)

    campos = {
        "nick_discord": obter_valor_texto(linhas, "nick_discord"),
        "username_roblox": obter_valor_texto(linhas, "username_roblox"),
        "nome_atual_roblox": obter_valor_texto(linhas, "nome_atual_roblox"),
        "idade": obter_idade(linhas),
        "ja_foi_de_outro_cla": opcoes("ja_foi_de_outro_cla"),
        "quais_clas": obter_valor_texto(linhas, "quais_clas", max_length=120),
        "motivo_saida": obter_valor_texto(linhas, "motivo_saida", max_length=120),
        "disponibilidade": opcoes("disponibilidade", multiplo=True),
        "participa_jogatinas": opcoes("participa_jogatinas"),
        "consegue_colocar_tag": opcoes("consegue_colocar_tag"),
        "consegue_seguir_instrucoes": opcoes("consegue_seguir_instrucoes"),
        "aceita_cores_fdn": opcoes("aceita_cores_fdn"),
    }

    for chave in CAMPOS_CADASTRO:
        if not campos.get(chave):
            campos[chave] = NAO_IDENTIFICADO

    return {
        "campos": campos,
        "formato_diferente": (not possui_cabecalho) or len(campos_detectados) < 6,
    }


def montar_registro_cadastro(message, staff, campos):
    return {
        "autor_id": str(message.author.id),
        "autor_nome": str(message.author),
        "message_id": str(message.id),
        "message_link": message.jump_url,
        "raw_content": message.content or "",
        "data_envio": message.created_at.astimezone(timezone.utc).isoformat(),
        "staff_validacao_id": str(staff.id),
        "staff_validacao_nome": str(staff),
        "data_validacao": datetime.now(timezone.utc).isoformat(),
        "status": "aprovado",
        "formato_diferente": campos.get("formato_diferente", False),
        "campos": campos.get("campos", campos),
    }


def salvar_ficha_recrutamento(message, staff, campos):
    dados = carregar_dados_cadastros()
    message_id = str(message.id)
    ja_existia = message_id in dados["cadastros"]
    dados["cadastros"][message_id] = montar_registro_cadastro(message, staff, campos)
    salvar_dados_cadastros(dados)
    return "atualizado" if ja_existia else "criado", dados["cadastros"][message_id]


def chave_cadastro_forum(registro):
    forum_message_id = registro.get("forum_message_id")
    if forum_message_id:
        return str(forum_message_id)

    partes = [
        str(registro.get("member_id", "")),
        str(registro.get("ticket_origem_id", "")),
        str(registro.get("created_at", "")),
    ]
    return "forum-" + "-".join(partes)


def encontrar_chave_por_forum_message_id(cadastros, forum_message_id):
    if not forum_message_id:
        return None

    forum_message_id = str(forum_message_id)
    if forum_message_id in cadastros:
        return forum_message_id

    for chave, registro in cadastros.items():
        if str(registro.get("forum_message_id", "")) == forum_message_id:
            return chave

    return None


def salvar_cadastro_forum(registro):
    dados = carregar_dados_cadastros()
    agora = datetime.now(timezone.utc).isoformat()

    chave = encontrar_chave_por_forum_message_id(
        dados["cadastros"],
        registro.get("forum_message_id"),
    )
    if not chave:
        chave = chave_cadastro_forum(registro)

    existente = dados["cadastros"].get(chave, {})
    registro_salvo = {
        **existente,
        **registro,
        "created_at": existente.get("created_at") or registro.get("created_at") or agora,
        "updated_at": agora,
    }

    dados["cadastros"][chave] = registro_salvo
    salvar_dados_cadastros(dados)
    return registro_salvo


def encontrar_chave_por_imported_message_id(cadastros, imported_message_id):
    if not imported_message_id:
        return None

    imported_message_id = str(imported_message_id)
    if imported_message_id in cadastros:
        return imported_message_id

    for chave, registro in cadastros.items():
        if str(registro.get("imported_message_id", "")) == imported_message_id:
            return chave

    return None


def salvar_cadastro_importado(message, staff, campos_extraidos):
    dados = carregar_dados_cadastros()
    agora = datetime.now(timezone.utc).isoformat()
    message_id = str(message.id)
    chave = encontrar_chave_por_imported_message_id(dados["cadastros"], message_id) or message_id
    existente = dados["cadastros"].get(chave, {})
    campos = campos_extraidos.get("campos", campos_extraidos) if isinstance(campos_extraidos, dict) else {}

    registro = {
        **existente,
        "imported_message_id": message_id,
        "message_id": message_id,
        "message_link": message.jump_url,
        "raw_content": message.content or "",
        "nick_discord": campos.get("nick_discord") or NAO_IDENTIFICADO,
        "username_roblox": campos.get("username_roblox") or NAO_IDENTIFICADO,
        "nome_atual_roblox": campos.get("nome_atual_roblox") or NAO_IDENTIFICADO,
        "idade": campos.get("idade") or NAO_IDENTIFICADO,
        "campos": {
            **existente.get("campos", {}),
            "nick_discord": campos.get("nick_discord") or NAO_IDENTIFICADO,
            "username_roblox": campos.get("username_roblox") or NAO_IDENTIFICADO,
            "nome_atual_roblox": campos.get("nome_atual_roblox") or NAO_IDENTIFICADO,
            "idade": campos.get("idade") or NAO_IDENTIFICADO,
        },
        "status": "importado",
        "importado_por_id": str(staff.id),
        "importado_por_nome": str(staff),
        "data_importacao": agora,
        "created_at": existente.get("created_at") or agora,
        "updated_at": agora,
    }

    dados["cadastros"][chave] = registro
    salvar_dados_cadastros(dados)
    return "atualizado" if existente else "criado", registro
