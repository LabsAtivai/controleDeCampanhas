from datetime import date


def iso_date(value, name='data'):
    if not isinstance(value, str):
        raise ValueError(f'{name}: use uma data YYYY-MM-DD.')
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{name}: data inválida.') from None
    if parsed.isoformat() != value:
        raise ValueError(f'{name}: use YYYY-MM-DD.')
    return parsed


def period(inicio=None, fim=None, max_days=None):
    start = iso_date(inicio, 'inicio') if inicio else None
    end = iso_date(fim, 'fim') if fim else None
    if start and end and end < start:
        raise ValueError('fim não pode ser anterior a inicio.')
    if start and end and max_days and (end - start).days + 1 > max_days:
        raise ValueError(f'Intervalo máximo: {max_days} dias, inclusive.')
    return start, end


def json_object(request):
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError('Envie um objeto JSON válido.')
    return value
