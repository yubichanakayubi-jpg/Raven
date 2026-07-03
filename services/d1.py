from datetime import timedelta

import aiohttp

import data.runtime as runtime
from config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_D1_DATABASE_ID
from utils.time_utils import mes_referencia_atual, parse_iso_datetime, utc_agora_iso


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
            avisou_dm_prazo INTEGER NOT NULL DEFAULT 0,
            avisou_10_dias INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pendente'
        )
        """
    )

    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN avisou_dm_prazo INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN message_id TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN prazo_troca TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN canal_origem_id TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN staff_registro_id TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN staff_registro_nome TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN message_link TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN data_conclusao TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN staff_conclusao_id TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN staff_conclusao_nome TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN conclusao_message_id TEXT")
    except Exception:
        pass
    try:
        await d1_query("ALTER TABLE tags_pendentes ADD COLUMN conclusao_message_link TEXT")
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
            SELECT
                user_id,
                nome,
                data_envio,
                message_id,
                prazo_troca,
                canal_origem_id,
                staff_registro_id,
                staff_registro_nome,
                message_link,
                data_conclusao,
                staff_conclusao_id,
                staff_conclusao_nome,
                conclusao_message_id,
                conclusao_message_link,
                avisou_7_dias,
                avisou_dm_prazo,
                avisou_10_dias,
                status
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
                "prazo_troca": registro.get("prazo_troca", ""),
                "canal_origem_id": str(registro.get("canal_origem_id")) if registro.get("canal_origem_id") else None,
                "staff_registro_id": str(registro.get("staff_registro_id")) if registro.get("staff_registro_id") else None,
                "staff_registro_nome": registro.get("staff_registro_nome", ""),
                "message_link": registro.get("message_link", ""),
                "data_conclusao": registro.get("data_conclusao", ""),
                "staff_conclusao_id": str(registro.get("staff_conclusao_id")) if registro.get("staff_conclusao_id") else None,
                "staff_conclusao_nome": registro.get("staff_conclusao_nome", ""),
                "conclusao_message_id": str(registro.get("conclusao_message_id")) if registro.get("conclusao_message_id") else None,
                "conclusao_message_link": registro.get("conclusao_message_link", ""),
                "avisou_7_dias": bool(registro.get("avisou_7_dias", 0)),
                "avisou_dm_prazo": bool(registro.get("avisou_dm_prazo", 0)),
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

        pendentes_atuais = dados.get("pendentes", {})
        ids_atuais = [str(chave) for chave in pendentes_atuais.keys()]

        if ids_atuais:
            placeholders = ", ".join(["?"] * len(ids_atuais))
            await d1_query(
                f"DELETE FROM tags_pendentes WHERE status = ? AND user_id NOT IN ({placeholders})",
                ["pendente", *ids_atuais]
            )
        else:
            await d1_query("DELETE FROM tags_pendentes WHERE status = ?", ["pendente"])

        for registro in pendentes_atuais.values():
            await d1_query(
                """
                INSERT OR REPLACE INTO tags_pendentes (
                    user_id, nome, data_envio, message_id, prazo_troca, canal_origem_id,
                    staff_registro_id, staff_registro_nome, message_link, data_conclusao,
                    staff_conclusao_id, staff_conclusao_nome, conclusao_message_id,
                    conclusao_message_link, avisou_7_dias, avisou_dm_prazo, avisou_10_dias, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    str(registro.get("user_id")),
                    registro.get("nome", ""),
                    registro.get("data_envio", ""),
                    str(registro.get("message_id")) if registro.get("message_id") else None,
                    registro.get("prazo_troca", ""),
                    str(registro.get("canal_origem_id")) if registro.get("canal_origem_id") else None,
                    str(registro.get("staff_registro_id")) if registro.get("staff_registro_id") else None,
                    registro.get("staff_registro_nome", ""),
                    registro.get("message_link", ""),
                    registro.get("data_conclusao", ""),
                    str(registro.get("staff_conclusao_id")) if registro.get("staff_conclusao_id") else None,
                    registro.get("staff_conclusao_nome", ""),
                    str(registro.get("conclusao_message_id")) if registro.get("conclusao_message_id") else None,
                    registro.get("conclusao_message_link", ""),
                    1 if registro.get("avisou_7_dias", False) else 0,
                    1 if registro.get("avisou_dm_prazo", False) else 0,
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


def normalizar_registro_tag(registro):
    return {
        "user_id": str(registro.get("user_id")),
        "nome": registro.get("nome", ""),
        "data_envio": registro.get("data_envio", ""),
        "message_id": str(registro.get("message_id")) if registro.get("message_id") else None,
        "prazo_troca": registro.get("prazo_troca", ""),
        "canal_origem_id": str(registro.get("canal_origem_id")) if registro.get("canal_origem_id") else None,
        "staff_registro_id": str(registro.get("staff_registro_id")) if registro.get("staff_registro_id") else None,
        "staff_registro_nome": registro.get("staff_registro_nome", ""),
        "message_link": registro.get("message_link", ""),
        "data_conclusao": registro.get("data_conclusao", ""),
        "staff_conclusao_id": str(registro.get("staff_conclusao_id")) if registro.get("staff_conclusao_id") else None,
        "staff_conclusao_nome": registro.get("staff_conclusao_nome", ""),
        "conclusao_message_id": str(registro.get("conclusao_message_id")) if registro.get("conclusao_message_id") else None,
        "conclusao_message_link": registro.get("conclusao_message_link", ""),
        "avisou_7_dias": bool(registro.get("avisou_7_dias", 0)),
        "avisou_dm_prazo": bool(registro.get("avisou_dm_prazo", 0)),
        "avisou_10_dias": bool(registro.get("avisou_10_dias", 0)),
        "status": registro.get("status", "pendente"),
    }


async def listar_tags_concluidas(limite=10):
    try:
        await garantir_schema_tags()
        resultado = await d1_query(
            """
            SELECT
                user_id,
                nome,
                data_envio,
                message_id,
                prazo_troca,
                canal_origem_id,
                staff_registro_id,
                staff_registro_nome,
                message_link,
                data_conclusao,
                staff_conclusao_id,
                staff_conclusao_nome,
                conclusao_message_id,
                conclusao_message_link,
                avisou_7_dias,
                avisou_dm_prazo,
                avisou_10_dias,
                status
            FROM tags_pendentes
            WHERE status = ?
            ORDER BY data_conclusao DESC
            LIMIT ?
            """,
            ["concluido", int(limite)],
        )
        registros = resultado[0].get("results", []) if resultado else []
        return [normalizar_registro_tag(registro) for registro in registros]
    except Exception as erro:
        print("ERRO AO LISTAR TAGS CONCLUIDAS NO D1:")
        print(erro)
        return []


async def buscar_registro_tag_por_usuario(usuario_id):
    try:
        await garantir_schema_tags()
        resultado = await d1_query(
            """
            SELECT
                user_id,
                nome,
                data_envio,
                message_id,
                prazo_troca,
                canal_origem_id,
                staff_registro_id,
                staff_registro_nome,
                message_link,
                data_conclusao,
                staff_conclusao_id,
                staff_conclusao_nome,
                conclusao_message_id,
                conclusao_message_link,
                avisou_7_dias,
                avisou_dm_prazo,
                avisou_10_dias,
                status
            FROM tags_pendentes
            WHERE user_id = ?
            ORDER BY
                CASE status
                    WHEN 'pendente' THEN 0
                    WHEN 'concluido' THEN 1
                    ELSE 2
                END,
                data_conclusao DESC
            LIMIT 1
            """,
            [str(usuario_id)],
        )
        registros = resultado[0].get("results", []) if resultado else []
        if not registros:
            return None
        return normalizar_registro_tag(registros[0])
    except Exception as erro:
        print("ERRO AO BUSCAR REGISTRO DE TAG NO D1:")
        print(erro)
        return None


async def garantir_schema_recrutamento():
    await d1_query(
        """
        CREATE TABLE IF NOT EXISTS recrutamentos (
            message_id TEXT PRIMARY KEY,
            recrutador_id TEXT NOT NULL,
            recrutador_nome TEXT NOT NULL,
            recrutado_texto TEXT,
            canal_id TEXT NOT NULL,
            data_criacao TEXT NOT NULL,
            mes_referencia TEXT NOT NULL,
            origem TEXT NOT NULL DEFAULT 'chat'
        )
        """
    )


async def garantir_schema_frases():
    await d1_query(
        """
        CREATE TABLE IF NOT EXISTS gatilho_frases_custom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gatilho_nome TEXT NOT NULL,
            frase TEXT NOT NULL,
            acao TEXT NOT NULL,
            data_criacao TEXT NOT NULL
        )
        """
    )


async def registrar_recrutamento(message_id, recrutador_id, recrutador_nome, canal_id, recrutado_texto=None, origem="chat"):
    await garantir_schema_recrutamento()

    ja_existe = await d1_query(
        "SELECT message_id FROM recrutamentos WHERE message_id = ?",
        [str(message_id)]
    )
    rows = ja_existe[0].get("results", []) if ja_existe else []
    if rows:
        return False

    await d1_query(
        """
        INSERT INTO recrutamentos (
            message_id, recrutador_id, recrutador_nome, recrutado_texto,
            canal_id, data_criacao, mes_referencia, origem
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(message_id),
            str(recrutador_id),
            recrutador_nome,
            recrutado_texto,
            str(canal_id),
            utc_agora_iso(),
            mes_referencia_atual(),
            origem
        ]
    )
    return True


async def total_recrutamentos_mes(recrutador_id, mes_referencia=None):
    await garantir_schema_recrutamento()

    if not mes_referencia:
        mes_referencia = mes_referencia_atual()

    resultado = await d1_query(
        """
        SELECT COUNT(*) AS total
        FROM recrutamentos
        WHERE recrutador_id = ? AND mes_referencia = ?
        """,
        [str(recrutador_id), mes_referencia]
    )
    rows = resultado[0].get("results", []) if resultado else []
    if not rows:
        return 0
    return int(rows[0].get("total", 0))


async def ranking_recrutadores_mes(mes_referencia=None):
    await garantir_schema_recrutamento()

    if not mes_referencia:
        mes_referencia = mes_referencia_atual()

    resultado = await d1_query(
        """
        SELECT recrutador_id, MAX(recrutador_nome) AS recrutador_nome, COUNT(*) AS total
        FROM recrutamentos
        WHERE mes_referencia = ?
        GROUP BY recrutador_id
        ORDER BY total DESC, recrutador_nome ASC
        """,
        [mes_referencia]
    )
    return resultado[0].get("results", []) if resultado else []


async def buscar_recrutamentos_do_recrutador(recrutador_id, mes_referencia=None):
    await garantir_schema_recrutamento()

    if not mes_referencia:
        mes_referencia = mes_referencia_atual()

    resultado = await d1_query(
        """
        SELECT message_id, recrutado_texto, data_criacao, origem
        FROM recrutamentos
        WHERE recrutador_id = ? AND mes_referencia = ?
        ORDER BY data_criacao DESC
        """,
        [str(recrutador_id), mes_referencia]
    )
    return resultado[0].get("results", []) if resultado else []


async def remover_ultimo_recrutamento_do_recrutador(recrutador_id, mes_referencia=None):
    await garantir_schema_recrutamento()

    if not mes_referencia:
        mes_referencia = mes_referencia_atual()

    resultado = await d1_query(
        """
        SELECT message_id
        FROM recrutamentos
        WHERE recrutador_id = ? AND mes_referencia = ?
        ORDER BY data_criacao DESC
        LIMIT 1
        """,
        [str(recrutador_id), mes_referencia]
    )
    rows = resultado[0].get("results", []) if resultado else []
    if not rows:
        return False

    message_id = rows[0].get("message_id")

    await d1_query(
        "DELETE FROM recrutamentos WHERE message_id = ?",
        [str(message_id)]
    )
    return True


async def resetar_recrutamentos_mes(mes_referencia=None):
    await garantir_schema_recrutamento()

    if not mes_referencia:
        mes_referencia = mes_referencia_atual()

    await d1_query(
        "DELETE FROM recrutamentos WHERE mes_referencia = ?",
        [mes_referencia]
    )


async def salvar_frase_custom_d1(gatilho_nome, frase, acao):
    await garantir_schema_frases()

    await d1_query(
        """
        INSERT INTO gatilho_frases_custom (
            gatilho_nome, frase, acao, data_criacao
        ) VALUES (?, ?, ?, ?)
        """,
        [
            gatilho_nome.lower(),
            frase,
            acao,
            utc_agora_iso()
        ]
    )


async def carregar_frases_custom_d1():
    await garantir_schema_frases()

    resultado = await d1_query(
        """
        SELECT gatilho_nome, frase, acao, data_criacao
        FROM gatilho_frases_custom
        ORDER BY id ASC
        """
    )

    return resultado[0].get("results", []) if resultado else []


async def aplicar_frases_custom_nos_gatilhos():
    registros = await carregar_frases_custom_d1()

    for registro in registros:
        gatilho_nome = str(registro.get("gatilho_nome", "")).lower()
        frase = registro.get("frase", "")
        acao = registro.get("acao", "")

        if not gatilho_nome or gatilho_nome not in runtime.GATILHOS:
            continue

        respostas = runtime.GATILHOS[gatilho_nome].setdefault("respostas", [])

        if acao == "add":
            if frase and frase not in respostas:
                respostas.append(frase)

        elif acao == "remove":
            if frase in respostas:
                respostas.remove(frase)


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
    data_base = parse_iso_datetime(data_envio)
    prazo_troca = (
        (data_base + timedelta(days=7)).isoformat()
        if data_base
        else ""
    )

    dados["pendentes"][chave] = {
        "user_id": str(usuario_id),
        "nome": nome_usuario,
        "data_envio": data_envio,
        "message_id": str(message_id) if message_id else None,
        "prazo_troca": prazo_troca,
        "canal_origem_id": None,
        "staff_registro_id": None,
        "staff_registro_nome": "",
        "message_link": "",
        "data_conclusao": "",
        "staff_conclusao_id": None,
        "staff_conclusao_nome": "",
        "conclusao_message_id": None,
        "conclusao_message_link": "",
        "avisou_7_dias": False,
        "avisou_dm_prazo": False,
        "avisou_10_dias": False,
        "status": "pendente"
    }

    await salvar_dados_tags(dados)


async def obter_registro_tag_pendente(usuario_id):
    dados = await carregar_dados_tags()
    return dados.get("pendentes", {}).get(str(usuario_id))


async def registrar_timetag_pendente(
    usuario_id,
    nome_usuario,
    canal_origem_id,
    staff_registro_id,
    staff_registro_nome,
    message_id=None,
    message_link=None,
):
    dados = await carregar_dados_tags()
    chave = str(usuario_id)
    registro_existente = dados.get("pendentes", {}).get(chave)
    if registro_existente and registro_existente.get("status") == "pendente":
        return "duplicado", registro_existente

    data_registro = utc_agora_iso()
    data_base = parse_iso_datetime(data_registro)
    prazo_troca = (
        (data_base + timedelta(days=7)).isoformat()
        if data_base
        else ""
    )

    registro = {
        "user_id": str(usuario_id),
        "nome": nome_usuario,
        "status": "pendente",
        "data_envio": data_registro,
        "prazo_troca": prazo_troca,
        "message_id": str(message_id) if message_id else None,
        "canal_origem_id": str(canal_origem_id) if canal_origem_id else None,
        "staff_registro_id": str(staff_registro_id) if staff_registro_id else None,
        "staff_registro_nome": staff_registro_nome or "",
        "message_link": message_link or "",
        "data_conclusao": "",
        "staff_conclusao_id": None,
        "staff_conclusao_nome": "",
        "conclusao_message_id": None,
        "conclusao_message_link": "",
        "avisou_7_dias": False,
        "avisou_dm_prazo": False,
        "avisou_10_dias": False,
    }

    dados["pendentes"][chave] = registro
    await salvar_dados_tags(dados)
    return "criado", registro


async def concluir_tag_pendente_com_detalhes(
    usuario_id,
    staff_conclusao_id,
    staff_conclusao_nome,
    message_id=None,
    message_link=None,
):
    dados = await carregar_dados_tags()
    chave = str(usuario_id)
    registro = dados.get("pendentes", {}).get(chave)
    if not registro:
        return None

    data_conclusao = utc_agora_iso()
    registro_concluido = {
        **registro,
        "status": "concluido",
        "data_conclusao": data_conclusao,
        "staff_conclusao_id": str(staff_conclusao_id) if staff_conclusao_id else None,
        "staff_conclusao_nome": staff_conclusao_nome or "",
        "conclusao_message_id": str(message_id) if message_id else None,
        "conclusao_message_link": message_link or "",
    }

    await garantir_schema_tags()
    await d1_query(
        """
        UPDATE tags_pendentes
        SET status = ?, data_conclusao = ?, staff_conclusao_id = ?, staff_conclusao_nome = ?,
            conclusao_message_id = ?, conclusao_message_link = ?
        WHERE user_id = ?
        """,
        [
            "concluido",
            registro_concluido.get("data_conclusao", ""),
            registro_concluido.get("staff_conclusao_id"),
            registro_concluido.get("staff_conclusao_nome", ""),
            registro_concluido.get("conclusao_message_id"),
            registro_concluido.get("conclusao_message_link", ""),
            chave,
        ],
    )

    del dados["pendentes"][chave]
    await salvar_dados_tags(dados)
    return registro_concluido


async def concluir_tag_pendente(usuario_id):
    dados = await carregar_dados_tags()
    chave = str(usuario_id)

    if chave not in dados["pendentes"]:
        return False

    del dados["pendentes"][chave]
    await salvar_dados_tags(dados)
    return True


async def concluir_tag_ou_aprovar(usuario_id):
    dados = await carregar_dados_tags()
    chave = str(usuario_id)

    if chave in dados["pendentes"]:
        del dados["pendentes"][chave]
        await salvar_dados_tags(dados)
        return "concluido"

    return "aprovado_sem_pendencia"
