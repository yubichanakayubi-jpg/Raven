import json
import os

from config import ARQUIVO_DADOS_GATILHOS, GATILHOS_CONFIG


def carregar_ultimas_respostas_gatilho():
    if not os.path.exists(ARQUIVO_DADOS_GATILHOS):
        return {}

    try:
        with open(ARQUIVO_DADOS_GATILHOS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except Exception:
        return {}

    valores = dados.get("ultimas_respostas_gatilho", {})
    if not isinstance(valores, dict):
        return {}

    resultado = {}
    for chave, resposta in valores.items():
        if isinstance(chave, str) and isinstance(resposta, str) and resposta.strip():
            resultado[chave] = resposta

    return resultado


def carregar_usuarios_gatilhos_permanentes():
    if not os.path.exists(ARQUIVO_DADOS_GATILHOS):
        return {}

    try:
        with open(ARQUIVO_DADOS_GATILHOS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except Exception:
        return {}

    valores = dados.get("usuarios_gatilhos_permanentes", {})
    if not isinstance(valores, dict):
        return {}

    resultado = {}
    for chave, usuarios in valores.items():
        if not isinstance(chave, str) or not isinstance(usuarios, list):
            continue
        resultado[chave] = [str(usuario) for usuario in usuarios if str(usuario).strip()]

    return resultado


def salvar_ultimas_respostas_gatilho():
    dados = {
        "ultimas_respostas_gatilho": ultimas_respostas_gatilho,
        "usuarios_gatilhos_permanentes": usuarios_gatilhos_permanentes,
    }

    try:
        with open(ARQUIVO_DADOS_GATILHOS, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=4)
    except Exception as erro:
        print(f"[GATILHOS] Não consegui salvar o estado dos gatilhos: {erro}")

cooldowns_usuario = {}
cooldowns_global = {}
cooldowns_ia = {}
cooldowns_reply_bot = {}
cooldowns_recrutamento = {}
mensagens_processadas = {}
ultimas_respostas_gatilho = carregar_ultimas_respostas_gatilho()
usuarios_gatilhos_permanentes = carregar_usuarios_gatilhos_permanentes()
tarefas_background = set()
ultima_mensagem_usuario = {}
bot_desconectado_desde = None
contexto_respostas_bot = {}
respostas_unicas_pergunta_diaria = {}
indice_boas_vindas = -1
feedback_tickets_pendentes = {}
ia_confusao_usuarios = {}
raven_conversas = {}
raven_conversas_por_usuario = {}
raven_sessoes_por_mensagem = {}

GATILHOS = json.loads(json.dumps(GATILHOS_CONFIG))
GATILHOS_BASE = json.loads(json.dumps(GATILHOS_CONFIG))
