from datetime import datetime, timezone

from config import FUSO_HORARIO


def utc_agora_iso():
    return datetime.now(timezone.utc).isoformat()


def data_iso_manual(data_str):
    try:
        data = datetime.strptime(data_str, "%d/%m/%Y")
    except Exception:
        return None

    return data.replace(tzinfo=FUSO_HORARIO).astimezone(timezone.utc).isoformat()


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


def mes_referencia_atual():
    agora = datetime.now(FUSO_HORARIO)
    return agora.strftime("%Y-%m")
