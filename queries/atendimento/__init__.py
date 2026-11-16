from pathlib import Path
from typing import Final, TypedDict


class AtendimentoQueries(TypedDict):
    get_company_params: Path
    """
    :param cnpj (string)
    :return: DataFrame[
        "rodovia" (int), "km_inicial" (float), "km_final" (float), "tipo_recurso" (string),
        "tipo_parametro" (int), "valor" (int), "tipo_servico" (string), "nome_trecho" (string)
    ]
    """
    get_company_time_range: Path
    """
    :param cnpj (string)
    :return: DataFrame["min_date" (datetime), "max_date" (datetime)]
    """
    get_first_calls: Path
    """
    :param cnpj (string), threshold_dist (float), threshold_time (float), date_start (string#date), date_end (string#date)
    :return: DataFrame (check the query for details)
    """
    get_gaps: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["date" (date), "count" (int)]
    """
    get_locations: Path
    """
    :param cnpj (string), resolution (int), date_start (string#date), date_end (string#date)
    :return: DataFrame["h3" (int), "count" (int)]
    """
    get_total_count: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["count" (int)]
    """
    get_zeroed_registers: Path
    """
    :param cnpj (string), threshold_dist (float), threshold_time (float), date_start (string#date), date_end (string#date)
    :return: DataFrame["DT_MES" (datetime), "count" (int), "cnt_z" (int), "cnt_z_autoacionado" (int), "cnt_z_invalido" (int)]
    """


AVAILABLE_ATENDIMENTO_QUERIES: Final[AtendimentoQueries] = {
    "get_company_params": Path("queries", "atendimento", "get_company_params.sql"),
    "get_company_time_range": Path(
        "queries", "atendimento", "get_company_time_range.sql"
    ),
    "get_first_calls": Path("queries", "atendimento", "get_first_calls.sql"),
    "get_gaps": Path("queries", "atendimento", "get_gaps.sql"),
    "get_locations": Path("queries", "atendimento", "get_locations.sql"),
    "get_total_count": Path("queries", "atendimento", "get_total_count.sql"),
    "get_zeroed_registers": Path("queries", "atendimento", "get_zeroed_registers.sql"),
}
