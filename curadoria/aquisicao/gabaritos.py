"""
Vocabulário de gabaritos (motivos geométricos) — modelo por OCORRÊNCIA.

Um gabarito NÃO é uma categoria do perfil. É um motivo geométrico LOCAL e
independente. Um mesmo perfil pode ter vários motivos ao mesmo tempo e várias
ocorrências do mesmo motivo:

    SU-053  → olhal + escovinha
    SU-225  → olhal + escovinha (2 ocorrências, regiões diferentes)
    LG-004  → olhal + gancho J Gold
    LG-006  → olhal + escovinha

Por isso o modelo é:

    perfil → [ocorrências de motivo]      (NÃO: perfil → um gabarito)

e a validação é sempre por ocorrência. A exclusividade existe SOMENTE entre
variantes incompatíveis do MESMO motivo (escovinha Suprema × escovinha Gold).
Não existe exclusividade entre escovinha, olhal, gancho, mão de amigo etc.

A planilha canônica é SOMENTE leitura, nunca staged/commitada:
  curadoria/insumos/MAPEAMENTO_GABARITOS_SUPREMA_GOLD.xlsx
Se não existir EXATAMENTE nesse caminho, falha com mensagem clara — proibido
procurar outra planilha parecida. Só linhas "Confirmado pelo Bruno" alimentam
o pipeline. SU-235, SU-272 e SU-027 permanecem bloqueados como precedentes.

Detecção automática de motivos é EXPERIMENTAL e não bloqueia o gate.
"""
from __future__ import annotations

from pathlib import Path

CAMINHO_CANONICO = Path(
    "/home/bruno/Documentos/esquadriacore/curadoria/insumos/"
    "MAPEAMENTO_GABARITOS_SUPREMA_GOLD.xlsx")

BLOQUEADOS = {"SU-235", "SU-272", "SU-027"}

# Encaixe do baguete: DOIS lados complementares que trabalham em paralelo
# (arbitragem do Bruno, 25/07/2026). Nunca tratar como um detalhe genérico só.
# Baguetes confirmados: Suprema SU-102 · Gold LG-057.
ENCAIXE_BAGUETE_INTERNO = "MOTIVO-ENCAIXE-BAGUETE-INTERNO"
ENCAIXE_BAGUETE_EXTERNO = "MOTIVO-ENCAIXE-BAGUETE-EXTERNO"

# Marcações de EVIDÊNCIA/CURADORIA — não são motivos geométricos do perfil-base.
# O card pode trazer o perfil principal em traço cheio e um perfil complementar
# em linha fina como referência de aplicação. A interface é o par de superfícies
# complementares: uma pertence ao perfil-base, a outra ao perfil desenhado.
INTERFACE_BAGUETE_REPRESENTADA = "INTERFACE-BAGUETE-REPRESENTADA"
CONTORNO_DE_REFERENCIA = "CONTORNO-DE-REFERENCIA-DE-OUTRO-PERFIL"
MARCACOES_DE_EVIDENCIA = {INTERFACE_BAGUETE_REPRESENTADA, CONTORNO_DE_REFERENCIA}

GABARITOS_VALIDOS = {
    "GAB-OLHAL-01",
    ENCAIXE_BAGUETE_INTERNO,
    ENCAIXE_BAGUETE_EXTERNO,
    "GAB-ESCOVINHA-SU-01",
    "GAB-ESCOVINHA-LG-01",
    "GAB-MA-DIAG-01",
    "GAB-MA-DIAG-ESC-01",
    "GAB-TRILHO-J-SU-01",
    "GAB-TRILHO-J-LG-01",
}

# Motivo BASE de cada gabarito. Duas variantes do mesmo motivo base são
# mutuamente exclusivas NUMA MESMA OCORRÊNCIA; motivos base diferentes nunca
# se excluem.
MOTIVO_BASE = {
    "GAB-OLHAL-01": "OLHAL",
    ENCAIXE_BAGUETE_INTERNO: "BAGUETE-INTERNO",   # bases distintas: interno e
    ENCAIXE_BAGUETE_EXTERNO: "BAGUETE-EXTERNO",   # externo NUNCA se excluem
    "GAB-ESCOVINHA-SU-01": "ESCOVINHA",
    "GAB-ESCOVINHA-LG-01": "ESCOVINHA",
    "GAB-MA-DIAG-01": "MA-DIAG",
    "GAB-MA-DIAG-ESC-01": "MA-DIAG-ESC",
    "GAB-TRILHO-J-SU-01": "TRILHO-J",
    "GAB-TRILHO-J-LG-01": "TRILHO-J",
}

# Família da variante. `None` = motivo sem variante por linha.
FAMILIA_DO_GABARITO = {
    "GAB-ESCOVINHA-SU-01": "Suprema",
    "GAB-ESCOVINHA-LG-01": "Gold",
    "GAB-TRILHO-J-SU-01": "Suprema",
    "GAB-TRILHO-J-LG-01": "Gold",
    "GAB-OLHAL-01": None,
    ENCAIXE_BAGUETE_INTERNO: None,
    ENCAIXE_BAGUETE_EXTERNO: None,
    "GAB-MA-DIAG-01": None,
    "GAB-MA-DIAG-ESC-01": None,
}

# Identificadores antigos, ambíguos entre as linhas. Mapeiam para o motivo
# base; a variante depende da família do perfil da OCORRÊNCIA.
ALIASES_AMBIGUOS = {
    "GAB-ESCOVINHA-01": {"Suprema": "GAB-ESCOVINHA-SU-01",
                         "Gold": "GAB-ESCOVINHA-LG-01"},
    "GAB-TRILHO-J-01": {"Suprema": "GAB-TRILHO-J-SU-01",
                        "Gold": "GAB-TRILHO-J-LG-01"},
}

PREFIXO_FAMILIA = {"SU": "Suprema", "LG": "Gold"}

ORIENTACOES_VALIDAS = {"superior", "inferior", "esquerda", "direita",
                       "exterior", "camara_interna"}


class GabaritoAmbiguo(ValueError):
    """Alias legado sem família conhecida: não se assume nenhuma linha."""


def familia_do_perfil(codigo: str | None) -> str | None:
    """Suprema para SU-xxx, Gold para LG-xxx (código de mercado)."""
    if not codigo:
        return None
    return PREFIXO_FAMILIA.get(str(codigo).strip()[:2].upper())


def resolver_gabarito(identificador: str, codigo_perfil: str | None = None,
                      *, para_leitura: bool = False) -> str:
    """Resolve um identificador para a variante canônica DAQUELA ocorrência.

    - perfil Gold conhecido    → variante Gold
    - perfil Suprema conhecido → variante Suprema
    - família desconhecida     → `GabaritoAmbiguo` (NÃO assume Gold)

    `para_leitura=True` devolve o identificador antigo intacto quando a
    família é desconhecida, para continuar lendo artefatos já produzidos sem
    introduzir classificação errada em artefatos novos.
    """
    ident = str(identificador).strip()
    if ident not in ALIASES_AMBIGUOS:
        return ident
    familia = familia_do_perfil(codigo_perfil)
    variantes = ALIASES_AMBIGUOS[ident]
    if familia in variantes:
        return variantes[familia]
    if para_leitura:
        return ident
    raise GabaritoAmbiguo(
        f"{ident!r} é ambíguo entre {sorted(variantes)}: sem a família do "
        f"perfil (recebido codigo_perfil={codigo_perfil!r}) não é possível "
        f"escolher a variante. Informe o código do perfil ou use "
        f"para_leitura=True para apenas ler artefatos antigos.")


def ocorrencia_compativel(gabarito_id: str, codigo_perfil: str) -> bool:
    """A variante serve para ESTA ocorrência, neste perfil?

    Valida UMA ocorrência. Não diz nada sobre os demais motivos do perfil:
    reprovar a escovinha Gold num perfil Suprema não bloqueia o olhal, o
    gancho J, a mão de amigo nem qualquer outro motivo confirmado.
    """
    canonico = resolver_gabarito(gabarito_id, codigo_perfil, para_leitura=True)
    familia_gab = FAMILIA_DO_GABARITO.get(canonico)
    return familia_gab is None or familia_gab == familia_do_perfil(codigo_perfil)


def conflita_com(gabarito_a: str, gabarito_b: str) -> bool:
    """Dois gabaritos são mutuamente exclusivos NA MESMA ocorrência?

    Só quando são variantes distintas do MESMO motivo base. Escovinha × olhal,
    gancho × escovinha, mão de amigo × qualquer outro: nunca conflitam.
    """
    if gabarito_a == gabarito_b:
        return False
    base_a = MOTIVO_BASE.get(gabarito_a)
    base_b = MOTIVO_BASE.get(gabarito_b)
    return base_a is not None and base_a == base_b


def carregar_planilha() -> dict:
    """codigo_mercado -> lista de IDs de gabarito confirmados pelo Bruno.
    Uma linha por relação: o mesmo perfil aparece uma vez por motivo."""
    if not CAMINHO_CANONICO.exists():
        raise FileNotFoundError(
            f"Planilha de gabaritos NÃO encontrada no caminho canônico:\n"
            f"  {CAMINHO_CANONICO}\n"
            f"O Bruno deve colocar a versão revisada nesse caminho exato. "
            f"É proibido usar outra planilha parecida silenciosamente.")
    import openpyxl
    wb = openpyxl.load_workbook(CAMINHO_CANONICO, data_only=True)
    ws = wb["Mapeamento"]
    linhas = list(ws.iter_rows(values_only=True))
    cab = list(linhas[0])
    i_mercado = cab.index("Código mercado")
    i_gab = cab.index("ID gabarito")
    i_class = cab.index("Classificação final")
    mapa: dict = {}
    for linha in linhas[1:]:
        if not linha or linha[i_mercado] is None:
            continue
        if str(linha[i_class]).strip() != "Confirmado pelo Bruno":
            continue
        codigo = str(linha[i_mercado]).strip()
        if codigo in BLOQUEADOS:
            continue
        mapa.setdefault(codigo, []).append(str(linha[i_gab]).strip())
    return mapa


def motivos_do_perfil(codigo: str, config_perfil: dict) -> list[dict]:
    """Ocorrências de motivo esperadas para o perfil.

    Cada item é uma OCORRÊNCIA independente:
        {"id", "ocorrencia", "orientacao", "zona_protegida", "posicao_rel"}

    A lista vem do config (que carrega posição/orientação medidas). A planilha
    canônica, quando existir, é a autoridade sobre QUAIS motivos esperar e é
    conferida contra o config — divergência é reportada, não silenciada.
    """
    declaradas = [dict(m) for m in config_perfil.get("motivos", [])]
    for m in declaradas:
        m["id"] = resolver_gabarito(m["id"], codigo, para_leitura=True)
    try:
        da_planilha = {resolver_gabarito(g, codigo, para_leitura=True)
                       for g in carregar_planilha().get(codigo, [])}
    except FileNotFoundError:
        return declaradas               # pendência já reportada ao Bruno
    declarados_ids = {m["id"] for m in declaradas}
    for faltando in sorted(da_planilha - declarados_ids):
        declaradas.append({"id": faltando, "ocorrencia": 1,
                           "orientacao": [], "zona_protegida": None,
                           "_origem": "planilha (sem geometria no config)"})
    return declaradas


def contagem_por_motivo(motivos: list[dict]) -> dict[str, int]:
    """Quantas ocorrências de cada gabarito — permite `escovinha × 2`."""
    contagem: dict[str, int] = {}
    for m in motivos:
        contagem[m["id"]] = contagem.get(m["id"], 0) + 1
    return contagem


def zonas_protecao(config_perfil: dict) -> list:
    """Zonas [[x0,y0,x1,y1] mm] das ocorrências — a limpeza não pode alterá-las.
    Cada ocorrência contribui a sua própria zona (uma escovinha não protege a
    outra por acidente: cada uma tem a sua)."""
    zonas = []
    for m in config_perfil.get("motivos", []):
        z = m.get("zona_protegida")
        if z:
            zonas.append(list(z))
    zonas.extend(list(z) for z in config_perfil.get("zonas_protegidas", []))
    return zonas


def politica_limpeza(identificador: str, config: dict,
                     codigo_perfil: str | None = None) -> dict:
    """Política de limpeza da OCORRÊNCIA. Levanta KeyError com mensagem clara
    se o gabarito não tiver política; GabaritoAmbiguo se o alias legado vier
    sem família."""
    canonico = resolver_gabarito(identificador, codigo_perfil)
    politicas = config.get("gabaritos", {})
    if canonico not in politicas:
        raise KeyError(
            f"gabarito {canonico!r} sem política de limpeza no config "
            f"(disponíveis: {sorted(k for k in politicas if not k.startswith('_'))})")
    return politicas[canonico]


# Estados possíveis de uma ocorrência. `nao_focado` é essencial: quando o motivo
# não aparece enquadrado na ROI, isso NÃO significa que ele não existe no perfil
# (arbitragem do Bruno, 25/07/2026).
ESTADOS_OCORRENCIA = {
    "confirmado_bruno",     # arbitrado por ele sobre o painel numerado
    "pendente_bruno",       # candidato aguardando arbitragem
    "nao_focado",           # esperado no perfil, fora do enquadramento atual
    "nao_evidenciado",      # esperado, mas a ROI atual não permite delimitar
    "sem_motivo",           # região examinada e descartada como motivo
}


def eh_marcacao_de_evidencia(identificador: str) -> bool:
    """Marcação de curadoria (interface, contorno de referência) não é motivo
    geométrico do perfil-base e nunca entra na contagem de gabaritos."""
    return identificador in MARCACOES_DE_EVIDENCIA


def classificacao_humana_prevalece(automatica: str | None,
                                   confirmada: str | None) -> str | None:
    """A arbitragem do Bruno substitui qualquer inferência automática
    conflitante. O detector nunca sobrescreve o que ele classificou."""
    return confirmada if confirmada else automatica
