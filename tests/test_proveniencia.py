"""Sprint E.4F — proveniência das evidências primárias externas ao repositório.

Estes testes cobrem o que a rodada entrega: referência segura a acervo externo,
separação entre validação estrutural e verificação física, natureza da fonte
separada da prova de independência dos casos, papel da fonte em cada afirmação
e o manifesto da Suprema 2F com os 112 artefatos reais.

O que eles NÃO cobrem, porque não existe: fórmula dimensional, regra de vidro,
regra de baguete, tolerância, offset entre planos e equivalência TMS/SU. Duas
afirmações continuam PENDENTES de propósito, e há teste garantindo que elas
continuem assim — travar aqui um valor que ninguém arbitrou transformaria
palpite em regressão protegida.
"""
import hashlib
import os
import stat
import threading
from decimal import Decimal
from pathlib import Path

import pytest

from composicao import fontes, proveniencia, receita as receita_mod, validar
from composicao.modelos import (ABRANGENCIA_COMPARTILHADA,
                                ABRANGENCIA_EXEMPLAR, ESTADOS_CONFIRMADOS,
                                FORMA_ACERVO_EXTERNO, FORMA_ARQUIVO,
                                TIPOS_DE_EVIDENCIA_PRIMARIA,
                                TIPOS_SEM_AUTORIDADE_FISICA,
                                CasoRealFabricacao, CorteReal,
                                EstadoConhecimento, FonteEvidencia,
                                ReceitaErro, VidroReal,
                                fingerprints_primarios_do_caso)
from composicao.proveniencia import (PapelDaFonte, AfirmacaoDeProveniencia,
                                     CitacaoDeFonte, ConflitoRegistrado,
                                     ManifestoProveniencia, carregar_manifesto,
                                     id_de_artefato, inventariar_acervo,
                                     manifesto_de_dict, validar_manifesto,
                                     verificar_acervo_do_manifesto)

RAIZ = Path(__file__).resolve().parent.parent
MANIFESTO = RAIZ / "composicao/insumos/proveniencia_suprema_2f.yaml"

RAIZ_LOGICA = "SUPREMA_CORRER_2F"

# Números do inventário forense da Rodada 1, conferidos contra os arquivos
# reais. Não são estimativa: são o que o acervo tem.
TOTAL_DE_ARTEFATOS = 112
TOTAL_DE_BYTES = 22_401_782


@pytest.fixture(scope="module")
def manifesto():
    return carregar_manifesto(MANIFESTO)


def _fonte_externa(**kwargs) -> FonteEvidencia:
    base = dict(id_fonte="FONTE-TESTE", tipo="foto",
                referencia="02_janela_pequena/foto.jpeg", descricao="teste",
                estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                forma_referencia=FORMA_ACERVO_EXTERNO,
                raiz_logica=RAIZ_LOGICA, sha256="a" * 64, tamanho_bytes=10)
    base.update(kwargs)
    return FonteEvidencia(**base)


@pytest.fixture
def acervo(tmp_path):
    """Acervo mínimo em disco, com hash e tamanho reais."""
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    alvo = raiz / "02_janela_pequena" / "foto.jpeg"
    conteudo = b"bytes da foto"
    alvo.write_bytes(conteudo)
    fonte = _fonte_externa(sha256=hashlib.sha256(conteudo).hexdigest(),
                           tamanho_bytes=len(conteudo))
    return raiz, fonte


# ---------------------------------------------------------------------------
# T01–T05 · segurança de caminho
# ---------------------------------------------------------------------------

def test_t01_manifesto_nao_contem_caminho_absoluto(manifesto):
    """Nenhum artefato guarda endereço de máquina — nem no texto do arquivo."""
    for f in manifesto.artefatos_externos:
        assert not f.referencia.startswith("/")
        assert not f.referencia.startswith("~")
        assert ".." not in f.referencia.split("/")
    texto = MANIFESTO.read_text(encoding="utf-8")
    assert "/home/" not in texto
    assert "~/" not in texto


@pytest.mark.parametrize("referencia", [
    "/acervo/evidencias/foto.jpeg",
    "C:/acervo/foto.jpeg",
    "~/acervo/foto.jpeg",
])
def test_t02_recusa_caminho_absoluto_em_artefato_externo(referencia):
    with pytest.raises(ReceitaErro, match="absoluto|usuário"):
        _fonte_externa(referencia=referencia)


def test_t03_recusa_travessia_com_ponto_ponto():
    with pytest.raises(ReceitaErro, match=r"travessia"):
        _fonte_externa(referencia="02_janela_pequena/../../etc/passwd")


def test_t04_verificacao_recusa_escape_da_raiz(tmp_path):
    """Caminho que sairia do acervo não é conferido: é reprovado.

    O nome pode ser inocente e o destino não. Desde a Rodada 3 a contenção não
    é medida depois de resolver — a descida por descritor com `O_NOFOLLOW`
    simplesmente não segue o desvio."""
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "foto.jpeg").write_bytes(b"x")
    (raiz / "02_janela_pequena" / "atalho").symlink_to(fora)

    fonte = _fonte_externa(referencia="02_janela_pequena/atalho/foto.jpeg")
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("symlink" in f["regra"] for f in r.falhas)


def test_t05_verificacao_recusa_symlink_que_escapa(tmp_path):
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    externo = tmp_path / "externo.jpeg"
    externo.write_bytes(b"conteudo de fora")
    (raiz / "02_janela_pequena" / "foto.jpeg").symlink_to(externo)

    fonte = _fonte_externa(sha256=hashlib.sha256(b"conteudo de fora").hexdigest(),
                           tamanho_bytes=16)
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("symlink" in f["regra"] for f in r.falhas), (
        "hash bater não basta: seguir link para fora traria bytes de "
        "qualquer lugar da máquina para dentro da prova")


def test_symlink_interno_ao_acervo_tambem_e_recusado(tmp_path):
    """Política da Rodada 3: o acervo externo não aceita symlink em nível nenhum.

    Mais estrita do que a regra dos arquivos do repositório, e de propósito.
    Aceitar symlink interno exigiria decidir por CAMINHO se o destino está
    dentro da raiz, e é essa decisão por caminho que abre a janela entre a
    checagem e a leitura. O acervo real tem zero symlinks: o caso recusado não
    existe na prática."""
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    real = raiz / "02_janela_pequena" / "real.jpeg"
    real.write_bytes(b"dentro")
    (raiz / "02_janela_pequena" / "foto.jpeg").symlink_to(real)

    fonte = _fonte_externa(sha256=hashlib.sha256(b"dentro").hexdigest(),
                           tamanho_bytes=6)
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("symlink" in f["regra"] for f in r.falhas)


def test_acervo_real_nao_tem_symlink_algum():
    """A política estrita não custa nada porque o acervo não usa symlink."""
    raizes = validar.raizes_fisicas_do_ambiente()
    if RAIZ_LOGICA not in raizes:
        pytest.skip("acervo externo não montado")
    raiz = raizes[RAIZ_LOGICA]
    assert not [p for p in raiz.rglob("*") if p.is_symlink()]


# ---------------------------------------------------------------------------
# T31–T38 · TOCTOU e objetos não regulares (Rodada 3)
# ---------------------------------------------------------------------------

def test_t31_arquivo_regular_correto_passa(acervo):
    raiz, fonte = acervo
    assert validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz}).ok


def test_t32_arquivo_final_symlink_para_fora_e_recusado(tmp_path):
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    externo = tmp_path / "externo.jpeg"
    externo.write_bytes(b"conteudo de fora")
    (raiz / "02_janela_pequena" / "foto.jpeg").symlink_to(externo)

    fonte = _fonte_externa(sha256=hashlib.sha256(b"conteudo de fora").hexdigest(),
                           tamanho_bytes=16)
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("symlink" in f["regra"] for f in r.falhas), (
        "o hash bater não é permissão para ler de fora da raiz")


def test_t33_componente_intermediario_symlink_para_fora_e_recusado(tmp_path):
    """O último componente ser inocente não basta: o pai também é caminho."""
    raiz = tmp_path / "acervo"
    raiz.mkdir()
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "foto.jpeg").write_bytes(b"bytes de fora")
    (raiz / "02_janela_pequena").symlink_to(fora)

    fonte = _fonte_externa(sha256=hashlib.sha256(b"bytes de fora").hexdigest(),
                           tamanho_bytes=13)
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("symlink" in f["regra"] for f in r.falhas)


def test_t34_cadeia_de_symlinks_e_recusada(tmp_path):
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    alvo = tmp_path / "final.jpeg"
    alvo.write_bytes(b"fim da cadeia")
    (tmp_path / "elo2.jpeg").symlink_to(alvo)
    (tmp_path / "elo1.jpeg").symlink_to(tmp_path / "elo2.jpeg")
    (raiz / "02_janela_pequena" / "foto.jpeg").symlink_to(tmp_path / "elo1.jpeg")

    fonte = _fonte_externa(sha256=hashlib.sha256(b"fim da cadeia").hexdigest(),
                           tamanho_bytes=13)
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("symlink" in f["regra"] for f in r.falhas)


def test_t35_fifo_nao_e_arquivo_regular_e_nao_pendura(tmp_path):
    """FIFO sem escritor penduraria um `open` bloqueante. Não pode acontecer."""
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    os.mkfifo(raiz / "02_janela_pequena" / "foto.jpeg")

    fonte = _fonte_externa()
    concluido = []

    def verificar():
        r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
        concluido.append(r)

    t = threading.Thread(target=verificar, daemon=True)
    t.start()
    t.join(timeout=10)
    assert not t.is_alive(), "verificação bloqueou num FIFO sem escritor"
    r = concluido[0]
    assert not r.ok
    assert any("não é arquivo regular" in f["regra"] for f in r.falhas)


def test_t36_diretorio_nao_e_artefato_regular(tmp_path):
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena" / "foto.jpeg").mkdir(parents=True)
    fonte = _fonte_externa()
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("não é arquivo regular" in f["regra"] for f in r.falhas)


def test_t37_o_objeto_hasheado_e_o_objeto_aberto(tmp_path, monkeypatch):
    """Trocar o ARQUIVO no caminho depois da abertura não muda o que é lido.

    O `fstat` acontece entre a abertura e a leitura; trocamos o caminho
    exatamente aí. Se a leitura fosse por caminho, o hash passaria a ser o do
    intruso e a verificação reprovaria. Como a leitura é pelo descritor já
    aberto, o hash continua sendo o do artefato legítimo."""
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    alvo = raiz / "02_janela_pequena" / "foto.jpeg"
    legitimo = b"bytes legitimos do artefato"
    alvo.write_bytes(legitimo)

    fstat_real = os.fstat
    trocas = []

    def fstat_e_troca(fd):
        situacao = fstat_real(fd)
        # Só no artefato final: o `fstat` do diretório intermediário acontece
        # ANTES da abertura do arquivo, e trocar ali não testaria nada.
        if stat.S_ISREG(situacao.st_mode) and not trocas:
            trocas.append(True)
            alvo.unlink()
            alvo.write_bytes(b"BYTES DO INTRUSO TROCADOS NO MEIO")
        return situacao

    monkeypatch.setattr(os, "fstat", fstat_e_troca)

    fonte = _fonte_externa(sha256=hashlib.sha256(legitimo).hexdigest(),
                           tamanho_bytes=len(legitimo))
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert trocas, "a troca não chegou a acontecer — teste não pressionou nada"
    assert r.ok, (
        "o hash mudou junto com o caminho: a leitura não está presa ao "
        "descritor aberto")
    assert alvo.read_bytes() != legitimo   # o intruso está lá, e foi ignorado


def test_t38_troca_por_symlink_entre_inspecao_e_abertura_nao_escapa(tmp_path,
                                                                    monkeypatch):
    """Trocar o alvo por symlink para fora, no instante da abertura, não passa.

    Simula a corrida no ponto exato onde ela seria explorável: logo antes do
    `os.open` do último componente. Como a abertura usa `O_NOFOLLOW`, o que
    entrou no lugar é recusado em vez de seguido."""
    raiz = tmp_path / "acervo"
    (raiz / "02_janela_pequena").mkdir(parents=True)
    alvo = raiz / "02_janela_pequena" / "foto.jpeg"
    legitimo = b"bytes legitimos"
    alvo.write_bytes(legitimo)
    fora = tmp_path / "segredo.jpeg"
    fora.write_bytes(legitimo)          # mesmo conteúdo: o hash bateria

    open_real = os.open
    trocas = []

    def open_e_troca(caminho, *a, **k):
        if caminho == "foto.jpeg" and not trocas:
            trocas.append(True)
            alvo.unlink()
            alvo.symlink_to(fora)
        return open_real(caminho, *a, **k)

    monkeypatch.setattr(os, "open", open_e_troca)

    fonte = _fonte_externa(sha256=hashlib.sha256(legitimo).hexdigest(),
                           tamanho_bytes=len(legitimo))
    r = validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz})
    assert trocas
    assert not r.ok, "symlink inserido na janela de corrida foi seguido"
    assert any("symlink" in f["regra"] for f in r.falhas)


def test_verificacao_nao_le_artefato_externo_por_caminho(acervo, monkeypatch):
    """Nenhuma leitura por caminho sobra no fluxo — a garantia é estrutural."""
    raiz, fonte = acervo

    def proibido(*a, **k):                     # pragma: no cover
        raise AssertionError("artefato externo lido por caminho, não por fd")

    monkeypatch.setattr(Path, "read_bytes", proibido)
    assert validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz}).ok


def test_caminho_com_ponto_ponto_recusado_na_descida(tmp_path):
    """Defesa em profundidade: `..` já é recusado na construção da fonte."""
    raiz = tmp_path / "acervo"
    raiz.mkdir()
    with pytest.raises(validar._AcervoRecusado):
        validar._abrir_artefato_do_acervo(raiz, "a/../../etc/passwd")


# ---------------------------------------------------------------------------
# T06–T10 · validação estrutural × verificação física
# ---------------------------------------------------------------------------

def test_t06_validacao_estrutural_funciona_sem_raiz_fisica(manifesto):
    """Quem clona o repositório sem o acervo ainda valida o manifesto."""
    assert validar_manifesto(manifesto).ok
    for f in manifesto.artefatos_externos:
        assert validar.validar_artefato_de_evidencia(f, RAIZ).ok, (
            "artefato externo não pode ser cobrado da raiz do repositório")


def test_t07_verificacao_fisica_falha_sem_raiz(manifesto):
    """Raiz ausente é REPROVAÇÃO, nunca 'pulado'."""
    r = verificar_acervo_do_manifesto(manifesto, {})
    assert not r.ok
    assert len(r.falhas) == TOTAL_DE_ARTEFATOS
    assert all("raiz física do acervo não fornecida" == f["regra"]
               for f in r.falhas)


def test_t07b_verificacao_fisica_falha_se_raiz_fornecida_nao_existe(tmp_path):
    fonte = _fonte_externa()
    r = validar.verificar_artefato_no_acervo(
        fonte, {RAIZ_LOGICA: tmp_path / "nao-existe"})
    assert not r.ok
    assert any("inexistente" in f["regra"] for f in r.falhas)


def test_t08_verificacao_fisica_detecta_hash_divergente(acervo):
    raiz, fonte = acervo
    trocada = FonteEvidencia(**{**fonte.para_dict(),
                                "estado": fonte.estado,
                                "sha256": "b" * 64})
    r = validar.verificar_artefato_no_acervo(trocada, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("alterado após o registro" in f["regra"] for f in r.falhas)


def test_t09_verificacao_fisica_detecta_tamanho_divergente(acervo):
    raiz, fonte = acervo
    trocada = FonteEvidencia(**{**fonte.para_dict(),
                                "estado": fonte.estado,
                                "tamanho_bytes": fonte.tamanho_bytes + 1})
    r = validar.verificar_artefato_no_acervo(trocada, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("tamanho" in f["regra"] for f in r.falhas)


def test_t10_verificacao_fisica_passa_para_arquivo_correto(acervo):
    raiz, fonte = acervo
    assert validar.verificar_artefato_no_acervo(fonte, {RAIZ_LOGICA: raiz}).ok


def test_verificacao_exige_sha256_no_artefato_externo(acervo):
    raiz, fonte = acervo
    sem_hash = FonteEvidencia(**{**fonte.para_dict(), "estado": fonte.estado,
                                 "sha256": None})
    r = validar.verificar_artefato_no_acervo(sem_hash, {RAIZ_LOGICA: raiz})
    assert not r.ok
    assert any("sem sha256" in f["regra"] for f in r.falhas)


def test_raizes_fisicas_vem_do_ambiente():
    ambiente = {"ESQUADRIACORE_ACERVO_SUPREMA_CORRER_2F": "/qualquer/lugar",
                "PATH": "/usr/bin"}
    raizes = validar.raizes_fisicas_do_ambiente(ambiente)
    assert set(raizes) == {RAIZ_LOGICA}
    assert Path("/qualquer/lugar") == raizes[RAIZ_LOGICA]


def test_ambiente_vazio_nao_inventa_raiz():
    assert validar.raizes_fisicas_do_ambiente({}) == {}


# ---------------------------------------------------------------------------
# T11–T12 · natureza da evidência × prova de independência
# ---------------------------------------------------------------------------

def test_t11_registro_de_campo_e_primario_sem_identificar_exemplar():
    """A ficha continua primária. O que muda é a ABRANGÊNCIA dela.

    Rebaixar a ficha a 'não primária' para o fingerprint passar seria mentir
    sobre a origem do dado: quem a preencheu estava na frente da janela."""
    assert "registro_de_campo" in TIPOS_DE_EVIDENCIA_PRIMARIA

    ficha = FonteEvidencia(
        id_fonte="FONTE-FICHA", tipo="registro_de_campo",
        referencia="01_ficha_campo/ficha.docx", descricao="ficha",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        forma_referencia=FORMA_ACERVO_EXTERNO, raiz_logica=RAIZ_LOGICA,
        sha256="c" * 64, tamanho_bytes=100,
        abrangencia=ABRANGENCIA_COMPARTILHADA)

    assert ficha.tipo in TIPOS_DE_EVIDENCIA_PRIMARIA   # natureza: primária
    assert not ficha.identifica_exemplar               # abrangência: partilhada


def test_t11b_mesma_ficha_como_exemplar_identifica():
    """A abrangência é do ARTEFATO, não do tipo: uma ficha por janela conta."""
    ficha = FonteEvidencia(
        id_fonte="FONTE-FICHA-A", tipo="registro_de_campo",
        referencia="ficha_a.docx", descricao="ficha só da janela A",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        sha256="d" * 64, tamanho_bytes=100)
    assert ficha.abrangencia == ABRANGENCIA_EXEMPLAR   # default retrocompatível
    assert ficha.identifica_exemplar


def _caso(identificador, exemplar, largura, fontes_do_caso):
    largura = Decimal(largura)
    return CasoRealFabricacao(
        identificador=identificador, id_exemplar=exemplar,
        largura_total_mm=largura, altura_total_mm=Decimal(740),
        fontes=fontes_do_caso,
        cortes=(CorteReal(perfil="SU-001", comprimento_mm=largura,
                          quantidade=1,
                          estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                          fontes_ids=(fontes_do_caso[0].id_fonte,)),),
        vidros=(VidroReal(folha="1", largura_mm=largura - 100,
                          altura_mm=Decimal(600), espessura_mm=Decimal(6),
                          estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
                          fontes_ids=(fontes_do_caso[0].id_fonte,)),))


def test_t12_fonte_compartilhada_nao_destroi_independencia():
    """Uma ficha em comum + fotos exclusivas = três casos independentes.

    O contrário — a ficha compartilhada reprovando os três — puniria o
    levantamento por ter sido feito de uma vez só."""
    ficha = FonteEvidencia(
        id_fonte="FONTE-FICHA-UNICA", tipo="registro_de_campo",
        referencia="01_ficha_campo/ficha.docx", descricao="cobre as três",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        sha256="e" * 64, tamanho_bytes=100,
        abrangencia=ABRANGENCIA_COMPARTILHADA)

    casos = []
    for i, (ident, largura) in enumerate([("CASO_A_PEQUENO", 2015),
                                          ("CASO_B_MEDIO", 1972),
                                          ("CASO_C_GRANDE", 2203)]):
        foto = FonteEvidencia(
            id_fonte=f"FONTE-FOTO-{i}", tipo="foto",
            referencia=f"0{i + 2}_janela/foto.jpeg", descricao="exclusiva",
            estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
            forma_referencia=FORMA_ACERVO_EXTERNO, raiz_logica=RAIZ_LOGICA,
            sha256=f"{i}" * 64, tamanho_bytes=50)
        casos.append(_caso(ident, f"OP-{i}", largura, (foto, ficha)))

    r = validar.validar_independencia_dos_casos(casos)
    assert r.ok, r.descrever()
    for c in casos:
        assert len(fingerprints_primarios_do_caso(c)) == 1


def test_t12b_ficha_marcada_como_exemplar_reprova_os_tres():
    """Sem a distinção de abrangência, o artefato partilhado colide — e deve.

    Este teste guarda a regra pelo avesso: se alguém declarar a ficha única
    como EXEMPLAR, os três casos passam a compartilhar o mesmo fingerprint e a
    independência cai. É o comportamento antigo, preservado."""
    ficha = FonteEvidencia(
        id_fonte="FONTE-FICHA-UNICA", tipo="registro_de_campo",
        referencia="01_ficha_campo/ficha.docx", descricao="cobre as três",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL,
        sha256="e" * 64, tamanho_bytes=100)      # EXEMPLAR por default

    casos = [_caso(ident, f"OP-{i}", largura, (ficha,))
             for i, (ident, largura) in enumerate([("CASO_A_PEQUENO", 2015),
                                                   ("CASO_B_MEDIO", 1972),
                                                   ("CASO_C_GRANDE", 2203)])]
    r = validar.validar_independencia_dos_casos(casos)
    assert not r.ok
    assert any("reutilizado entre casos" in f["regra"] for f in r.falhas)


# ---------------------------------------------------------------------------
# T13–T15 · autoridade das fontes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tipo", sorted(TIPOS_SEM_AUTORIDADE_FISICA))
@pytest.mark.parametrize("estado", sorted(ESTADOS_CONFIRMADOS,
                                          key=lambda e: e.value))
def test_t13_t14_benchmark_e_sistema_anterior_nao_confirmam(tipo, estado):
    """Wvetro e VidroSys não abrem confirmação — a recusa é na construção."""
    with pytest.raises(ReceitaErro, match="não confirma nada"):
        FonteEvidencia(id_fonte="FONTE-X", tipo=tipo, referencia="a.pdf",
                       descricao="x", estado=estado)


def test_t13b_benchmark_nao_entra_em_fingerprint_fisico():
    assert "benchmark_externo" not in TIPOS_DE_EVIDENCIA_PRIMARIA
    assert "referencia_sistema_anterior" not in TIPOS_DE_EVIDENCIA_PRIMARIA


def test_t13c_benchmark_nao_sustenta_afirmacao_no_manifesto():
    """Mesmo citado como DIRETA, o benchmark é recusado pela validação."""
    dados = {
        "versao_manifesto": 1, "conjunto": "X", "raiz_logica": "X",
        "grupos": [{"grupo": "g", "tipo": "benchmark_externo",
                    "estado": "PENDENTE", "descricao": "wvetro"}],
        "artefatos": [{"id_fonte": "FONTE-BENCH", "grupo": "g",
                       "caminho_relativo": "g/rel.pdf", "sha256": "f" * 64,
                       "tamanho_bytes": 10}],
        "afirmacoes": [{"identificador": "A01", "texto": "algo",
                        "estado": "CONFIRMADO_CASO_REAL",
                        "citacoes": [{"id_fonte": "FONTE-BENCH",
                                      "papel": "DIRETA"}]}],
    }
    r = validar_manifesto(manifesto_de_dict(dados))
    assert not r.ok
    assert any("benchmark ou sistema anterior sustentando" in f["regra"]
               for f in r.falhas)


def test_t15_arbitragem_de_especialista_fora_do_fingerprint_fisico(manifesto):
    """FONTE-TOPOLOGIA-E4E prova a integridade do documento, não a janela."""
    topologia = manifesto.indice_de_fontes()["FONTE-TOPOLOGIA-E4E"]
    assert topologia.tipo == "especialista_de_dominio"
    assert topologia.tipo not in TIPOS_DE_EVIDENCIA_PRIMARIA
    assert not topologia.identifica_exemplar
    assert topologia.forma_referencia == FORMA_ARQUIVO   # vive no repositório
    assert topologia.sha256 == receita_mod.FONTE_TOPOLOGIA_E4E.sha256
    assert topologia.tamanho_bytes == receita_mod.FONTE_TOPOLOGIA_E4E.tamanho_bytes


def test_arbitragem_do_manifesto_continua_integra():
    """O hash citado tem de bater com o arquivo — senão a citação é fóssil."""
    alvo = RAIZ / receita_mod.FONTE_TOPOLOGIA_E4E.referencia
    dados = alvo.read_bytes()
    assert hashlib.sha256(dados).hexdigest() == \
        receita_mod.FONTE_TOPOLOGIA_E4E.sha256
    assert len(dados) == receita_mod.FONTE_TOPOLOGIA_E4E.tamanho_bytes


# ---------------------------------------------------------------------------
# T16–T18 · afirmações, papéis e derivação
# ---------------------------------------------------------------------------

def test_t16_afirmacao_aceita_multiplas_fontes(manifesto):
    a02 = manifesto.afirmacao("A02")
    assert len(a02.citacoes) > 1
    assert len({c.id_fonte for c in a02.citacoes}) == len(a02.citacoes)


def test_t16b_afirmacao_recusa_a_mesma_fonte_duas_vezes():
    with pytest.raises(ReceitaErro, match="citada duas vezes"):
        AfirmacaoDeProveniencia(
            identificador="A99", texto="x",
            estado=EstadoConhecimento.PENDENTE,
            citacoes=(CitacaoDeFonte("FONTE-A", PapelDaFonte.DIRETA),
                      CitacaoDeFonte("FONTE-A", PapelDaFonte.CORROBORATIVA)))


def test_t17_papeis_sao_distintos():
    assert len({p.value for p in PapelDaFonte}) == 4
    assert CitacaoDeFonte("FONTE-A", PapelDaFonte.DIRETA).sustenta
    assert CitacaoDeFonte("FONTE-A", PapelDaFonte.DERIVADA).sustenta
    assert not CitacaoDeFonte("FONTE-A", PapelDaFonte.CORROBORATIVA).sustenta
    assert not CitacaoDeFonte("FONTE-A", PapelDaFonte.CONFLITANTE).sustenta


def test_t17b_corroboracao_sozinha_nao_confirma():
    """Compatível com a tese não é o mesmo que provar a tese."""
    dados = {
        "versao_manifesto": 1, "conjunto": "X", "raiz_logica": "X",
        "grupos": [{"grupo": "g", "tipo": "foto",
                    "estado": "CONFIRMADO_CASO_REAL", "descricao": "foto"}],
        "artefatos": [{"id_fonte": "FONTE-F", "grupo": "g",
                       "caminho_relativo": "g/f.jpeg", "sha256": "1" * 64,
                       "tamanho_bytes": 10}],
        "afirmacoes": [{"identificador": "A01", "texto": "algo",
                        "estado": "CONFIRMADO_CASO_REAL",
                        "citacoes": [{"id_fonte": "FONTE-F",
                                      "papel": "CORROBORATIVA"}]}],
    }
    r = validar_manifesto(manifesto_de_dict(dados))
    assert not r.ok
    assert any("sem fonte que a sustente" in f["regra"] for f in r.falhas)


def test_t18_a16_e_derivada_nao_observacao_direta(manifesto):
    """Não existe foto mostrando vinte peças — o total é agregação."""
    a16 = manifesto.afirmacao("A16")
    assert a16.derivada
    assert set(a16.derivada_de) == {"A03", "A04", "A05", "A06", "A07", "A08",
                                    "A09", "A12"}
    assert not a16.citacoes_com_papel(PapelDaFonte.DIRETA)
    assert a16.citacoes_com_papel(PapelDaFonte.DERIVADA)


def test_afirmacao_nao_pode_derivar_de_si_mesma():
    dados = {
        "versao_manifesto": 1, "conjunto": "X", "raiz_logica": "X",
        "afirmacoes": [{"identificador": "A01", "texto": "x",
                        "estado": "PENDENTE", "derivada_de": ["A01"]}],
    }
    r = validar_manifesto(manifesto_de_dict(dados))
    assert not r.ok
    assert any("deriva de si" in f["regra"] for f in r.falhas)


# ---------------------------------------------------------------------------
# C01–C05 · grafo de derivação (Rodada 3)
# ---------------------------------------------------------------------------

def _afirmacao_crua(identificador, deriva=(), estado="PENDENTE"):
    return {"identificador": identificador, "texto": f"texto de {identificador}",
            "estado": estado, "derivada_de": list(deriva)}


def _manifesto_cru(afirmacoes, conflitos=()):
    return manifesto_de_dict({"versao_manifesto": 1, "conjunto": "X",
                              "raiz_logica": "X",
                              "afirmacoes": list(afirmacoes),
                              "conflitos": list(conflitos)})


def _ciclos_reprovados(manifesto):
    return [f["encontrado"] for f in validar_manifesto(manifesto).falhas
            if f["regra"] == "derivação circular"]


def test_c01_ciclo_de_dois_nos_e_rejeitado():
    """A01 <- A02 <- A01: cada uma se apoia na outra e nenhuma tem origem."""
    man = _manifesto_cru([_afirmacao_crua("A01", ["A02"]),
                          _afirmacao_crua("A02", ["A01"])])
    assert _ciclos_reprovados(man) == ["A01 -> A02 -> A01"]


def test_c02_ciclo_de_tres_nos_e_rejeitado():
    man = _manifesto_cru([_afirmacao_crua("A01", ["A02"]),
                          _afirmacao_crua("A02", ["A03"]),
                          _afirmacao_crua("A03", ["A01"])])
    assert _ciclos_reprovados(man) == ["A01 -> A02 -> A03 -> A01"]


def test_c02b_ciclo_escondido_dentro_de_grafo_maior_e_rejeitado():
    """O ciclo não está na raiz do grafo nem no começo da lista."""
    man = _manifesto_cru([
        _afirmacao_crua("A01"),
        _afirmacao_crua("A02", ["A01"]),
        _afirmacao_crua("A03", ["A02", "A04"]),
        _afirmacao_crua("A04", ["A05"]),
        _afirmacao_crua("A05", ["A06"]),
        _afirmacao_crua("A06", ["A04"]),      # ciclo A04 -> A05 -> A06 -> A04
        _afirmacao_crua("A07", ["A01", "A02"]),
    ])
    assert _ciclos_reprovados(man) == ["A04 -> A05 -> A06 -> A04"]


def test_c03_dag_valido_continua_aceito():
    """Losango de derivação, com nó citado por dois caminhos: é válido."""
    man = _manifesto_cru([
        _afirmacao_crua("A01"),
        _afirmacao_crua("A02", ["A01"]),
        _afirmacao_crua("A03", ["A01"]),
        _afirmacao_crua("A04", ["A02", "A03"]),
        _afirmacao_crua("A05", ["A04", "A01"]),
    ])
    assert not _ciclos_reprovados(man)
    assert validar_manifesto(man).ok


def test_c04_ordem_no_yaml_nao_altera_o_resultado():
    """Mesmo grafo, três ordens de escrita, mesmo veredito e mesma mensagem."""
    afirmacoes = [_afirmacao_crua("A01", ["A02"]),
                  _afirmacao_crua("A02", ["A03"]),
                  _afirmacao_crua("A03", ["A01"])]
    vereditos = {tuple(_ciclos_reprovados(_manifesto_cru(ordem)))
                 for ordem in (afirmacoes,
                               list(reversed(afirmacoes)),
                               [afirmacoes[1], afirmacoes[2], afirmacoes[0]])}
    assert vereditos == {("A01 -> A02 -> A03 -> A01",)}


def test_c05_derivacao_de_afirmacao_inexistente_e_rejeitada():
    man = _manifesto_cru([_afirmacao_crua("A01", ["A99-FANTASMA"])])
    r = validar_manifesto(man)
    assert not r.ok
    assert any("deriva de afirmação inexistente" in f["regra"]
               for f in r.falhas)


def test_c05b_autorreferencia_continua_rejeitada():
    """A regra antiga não foi substituída pela nova — as duas valem."""
    r = validar_manifesto(_manifesto_cru([_afirmacao_crua("A01", ["A01"])]))
    assert not r.ok
    assert any("deriva de si" in f["regra"] for f in r.falhas)


def test_cadeia_longa_de_derivacao_nao_estoura_a_pilha():
    """Grafo profundo é dado, não defeito: não pode virar RecursionError."""
    cadeia = [_afirmacao_crua("A0", [])]
    cadeia += [_afirmacao_crua(f"A{i}", [f"A{i - 1}"]) for i in range(1, 400)]
    assert validar_manifesto(_manifesto_cru(cadeia)).ok


# ---------------------------------------------------------------------------
# K01–K03 · identidade dos conflitos (Rodada 3)
# ---------------------------------------------------------------------------

def _conflito_cru(identificador):
    return {"identificador": identificador, "descricao": "divergência",
            "valores": ["a", "b"], "estado": "PENDENTE"}


def test_k01_dois_conflitos_com_mesmo_id_sao_rejeitados():
    r = validar_manifesto(_manifesto_cru(
        [], [_conflito_cru("K1"), _conflito_cru("K1")]))
    assert not r.ok
    assert any(f["regra"] == "conflito repetido" for f in r.falhas)


def test_k02_conflitos_com_ids_diferentes_sao_aceitos():
    assert validar_manifesto(_manifesto_cru(
        [], [_conflito_cru("K1"), _conflito_cru("K2")])).ok


def test_k03_afirmacao_e_conflito_dividem_o_mesmo_namespace():
    """POLÍTICA ADOTADA: namespace global do manifesto.

    Afirmação e conflito são citados do mesmo jeito em relatório e em
    arbitragem — "pendência A07" ao lado de "pendência K2". Se os dois
    pudessem se chamar A07, a citação passaria a depender de quem lê. A
    restrição é deliberada e está testada para não virar acidente."""
    r = validar_manifesto(_manifesto_cru([_afirmacao_crua("K9")],
                                         [_conflito_cru("K9")]))
    assert not r.ok
    assert any(f["regra"] == "identificador usado por afirmação e por conflito"
               for f in r.falhas)


def test_k03b_manifesto_real_respeita_o_namespace_global(manifesto):
    ids_afirmacao = {a.identificador for a in manifesto.afirmacoes}
    ids_conflito = {c.identificador for c in manifesto.conflitos}
    assert not (ids_afirmacao & ids_conflito)


def test_citacao_para_fonte_inexistente_reprova():
    dados = {
        "versao_manifesto": 1, "conjunto": "X", "raiz_logica": "X",
        "afirmacoes": [{"identificador": "A01", "texto": "x",
                        "estado": "PENDENTE",
                        "citacoes": [{"id_fonte": "FONTE-FANTASMA",
                                      "papel": "DIRETA"}]}],
    }
    r = validar_manifesto(manifesto_de_dict(dados))
    assert not r.ok
    assert any("fonte inexistente" in f["regra"] for f in r.falhas)


# ---------------------------------------------------------------------------
# T19–T22 · limites de domínio preservados
# ---------------------------------------------------------------------------

def test_t19_tms001_permanece_literal_no_benchmark(manifesto):
    texto = MANIFESTO.read_text(encoding="utf-8")
    assert "TMS001" in texto


def test_t20_nenhuma_associacao_tms001_para_su001(manifesto):
    """Equivalência não declarada não vira alias silencioso.

    A única equivalência SU/TMS homologada no projeto é SU-102 x TMS-102, e ela
    não autoriza generalizar para o 001."""
    for f in manifesto.fontes:
        assert "TMS001" not in (f.referencia or "")
    for a in manifesto.afirmacoes:
        assert "TMS001" not in a.texto
    # Nenhuma nota afirma equivalência: onde TMS001 aparece, aparece negando.
    notas_com_tms = [n for n in manifesto.notas if "TMS001" in n]
    assert notas_com_tms
    for n in notas_com_tms:
        assert "NENHUMA associação" in n or "não corresponde" in n


def test_t21_conflito_934_994_registrado_sem_escolha(manifesto):
    conflito = next(c for c in manifesto.conflitos
                    if c.identificador == "K2-VIDRO-FOLHA-2")
    assert conflito.estado not in ESTADOS_CONFIRMADOS
    assert len(conflito.valores) == 2
    assert any("994" in v for v in conflito.valores)
    assert any("934" in v for v in conflito.valores)
    assert all(c.papel is PapelDaFonte.CONFLITANTE for c in conflito.citacoes)


def test_conflito_nao_pode_nascer_confirmado():
    """Conflito CONFIRMADO seria escolha automática entre valores divergentes."""
    with pytest.raises(ReceitaErro, match="escolha automática"):
        ConflitoRegistrado(identificador="K9", descricao="x",
                           valores=("a", "b"),
                           estado=EstadoConhecimento.CONFIRMADO_CASO_REAL)


def test_t22_a07_e_a08_continuam_pendentes(manifesto):
    """"Trilho interno" da ficha ainda não foi declarado igual a PLANO_INTERNO.

    Este teste existe para que a pendência não seja fechada por descuido: se
    alguém marcar A07 como confirmada sem arbitragem, o teste cai."""
    for ident in ("A07", "A08"):
        a = manifesto.afirmacao(ident)
        assert a.estado is EstadoConhecimento.PENDENTE
        assert "trilho" in (a.observacao or "").lower()
    assert validar_manifesto(manifesto).ok, (
        "afirmação pendente não pode quebrar o manifesto")


def test_a13_independe_da_arbitragem_de_plano(manifesto):
    """Folhas DIFERENTES é observável; QUAL é a interna é que está pendente."""
    a13 = manifesto.afirmacao("A13")
    assert a13.estado is EstadoConhecimento.CONFIRMADO_CASO_REAL
    assert "A13" not in manifesto.afirmacao("A07").derivada_de


def test_a02_nao_apoia_dois_planos_nas_fotos_contra_luz(manifesto):
    """A prova forte é o trilho superior da Pequena, não o quadro sem folhas.

    Nove das dez fotos do quadro sem folhas estão fortemente contra-luz. Elas
    corroboram; promovê-las a prova direta seria fingir nitidez que não há."""
    a02 = manifesto.afirmacao("A02")
    diretas = a02.citacoes_com_papel(PapelDaFonte.DIRETA)
    assert len(diretas) == 1
    assert diretas[0].id_fonte == \
        "FONTE-02-JANELA-PEQUENA-LADO-ESQUERDO-DO-TRILHO-SUPERIOR-JPEG"
    for c in a02.citacoes:
        if "QUADRO-SEM-FOLHAS" in c.id_fonte:
            assert c.papel is PapelDaFonte.CORROBORATIVA


def test_nenhuma_foto_sozinha_prova_codigo_su(manifesto):
    """Afirmação de código de perfil nunca tem foto como fonte DIRETA.

    Nenhum perfil fotografado tem código legível. Quem nomeia é a ficha."""
    indice = manifesto.indice_de_fontes()
    for ident in ("A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10"):
        a = manifesto.afirmacao(ident)
        for c in a.citacoes_com_papel(PapelDaFonte.DIRETA):
            assert indice[c.id_fonte].tipo != "foto", (
                f"{ident}: foto como prova direta de código SU")


# ---------------------------------------------------------------------------
# T23–T26 · o acervo da Suprema 2F
# ---------------------------------------------------------------------------

def test_t23_manifesto_tem_112_artefatos(manifesto):
    assert len(manifesto.artefatos_externos) == TOTAL_DE_ARTEFATOS


def test_t24_112_hashes_distintos(manifesto):
    hashes = [f.sha256 for f in manifesto.artefatos_externos]
    assert all(hashes)
    assert len(set(hashes)) == TOTAL_DE_ARTEFATOS


def test_t25_soma_dos_tamanhos(manifesto):
    assert manifesto.total_de_bytes == TOTAL_DE_BYTES


def test_t26_pares_de_reemissao_wvetro_permanecem_distintos(manifesto):
    """`X.pdf` e `X (1).pdf` têm bytes diferentes: são dois artefatos.

    Colapsá-los escolheria em silêncio qual das duas emissões é "a certa" —
    exatamente a decisão que a ARB-7 reservou para a arbitragem."""
    externos = {f.referencia: f for f in manifesto.artefatos_externos}
    pares = [(r, r.replace(" (1).pdf", ".pdf")) for r in externos
             if r.endswith(" (1).pdf")]
    assert len(pares) == 6, (
        "a Rodada 1 registrou cinco pares; o acervo real tem seis — o sexto é "
        "o de extensão dupla Orcamento_Acessorios_Fonecedor.pdf")
    for reemissao, original in pares:
        assert original in externos, f"par incompleto: {reemissao}"
        assert externos[reemissao].sha256 != externos[original].sha256
        assert externos[reemissao].id_fonte != externos[original].id_fonte


def test_pares_de_foto_com_sufixo_um_tambem_sao_distintos(manifesto):
    """O padrão `X (1)` também ocorre em 15 fotos — evidência primária.

    Ali a diferença de tamanho chega a dezenas de por cento, o que não é
    reemissão do mesmo arquivo. Todos ficam registrados separadamente até a
    ARB-7 decidir; nenhum é descartado como duplicata."""
    externos = {f.referencia: f for f in manifesto.artefatos_externos}
    pares = [(r, r.replace(" (1).jpeg", ".jpeg")) for r in externos
             if r.endswith(" (1).jpeg")]
    assert len(pares) == 15
    for reemissao, original in pares:
        assert original in externos
        assert externos[reemissao].sha256 != externos[original].sha256


def test_classificacao_dos_grupos(manifesto):
    """Cada grupo tem a natureza que a auditoria estabeleceu — sem promoções."""
    por_tipo = {}
    for f in manifesto.artefatos_externos:
        por_tipo.setdefault(f.tipo, []).append(f)
    assert len(por_tipo["registro_de_campo"]) == 1
    assert len(por_tipo["foto"]) == 78
    assert len(por_tipo["benchmark_externo"]) == 30
    assert len(por_tipo["referencia_sistema_anterior"]) == 3

    assert all(f.abrangencia == ABRANGENCIA_COMPARTILHADA
               for f in por_tipo["registro_de_campo"])
    assert all(f.abrangencia == ABRANGENCIA_EXEMPLAR
               for f in por_tipo["foto"])
    assert all(f.estado is EstadoConhecimento.PENDENTE
               for f in por_tipo["benchmark_externo"]
               + por_tipo["referencia_sistema_anterior"])


def test_fotos_exclusivas_por_caso(manifesto):
    """21 / 23 / 34 fotos, cada janela com as suas — a base da independência."""
    por_caso = {}
    for f in manifesto.artefatos_externos:
        if f.tipo != "foto":
            continue
        caso = f.referencia.split("/", 1)[0]
        por_caso.setdefault(caso, set()).add(f.sha256)
    assert {k: len(v) for k, v in sorted(por_caso.items())} == {
        "02_janela_pequena": 21, "03_janela_media": 23,
        "04_janela_grande": 34}
    todos = [h for v in por_caso.values() for h in v]
    assert len(set(todos)) == len(todos), "foto compartilhada entre janelas"


# ---------------------------------------------------------------------------
# T27 · compatibilidade
# ---------------------------------------------------------------------------

def test_t27_fonte_antiga_continua_valida_sem_campos_novos():
    """Os campos novos têm default; registro da E.4D/E.4E não muda de sentido."""
    antiga = FonteEvidencia(
        id_fonte="FONTE-ANTIGA", tipo="foto", referencia="docs/foto.jpeg",
        descricao="registrada antes da E.4F",
        estado=EstadoConhecimento.CONFIRMADO_CASO_REAL)
    assert antiga.forma_referencia == FORMA_ARQUIVO
    assert antiga.raiz_logica is None
    assert antiga.abrangencia == ABRANGENCIA_EXEMPLAR
    assert antiga.identifica_exemplar


def test_t27b_receita_e_gates_da_e4e_intactos():
    rec = receita_mod.construir_receita_preliminar()
    assert len(rec.componentes) == 20
    assert len(rec.relacoes) == 1
    topologia = next(f for f in rec.fontes
                     if f.id_fonte == "FONTE-TOPOLOGIA-E4E")
    assert topologia.raiz_logica is None
    assert all(f.abrangencia == ABRANGENCIA_EXEMPLAR for f in rec.fontes)


def test_t27c_para_dict_da_fonte_faz_round_trip():
    original = _fonte_externa(abrangencia=ABRANGENCIA_COMPARTILHADA)
    d = original.para_dict()
    assert d["raiz_logica"] == RAIZ_LOGICA
    assert d["abrangencia"] == ABRANGENCIA_COMPARTILHADA
    refeita = FonteEvidencia(**{**d, "estado": original.estado})
    assert refeita == original


def test_t27d_manifesto_recusa_versao_desconhecida():
    with pytest.raises(ReceitaErro, match="não suportada"):
        manifesto_de_dict({"versao_manifesto": 99, "conjunto": "X",
                           "raiz_logica": "X"})


def test_raiz_logica_so_existe_com_forma_de_acervo_externo():
    with pytest.raises(ReceitaErro, match="só faz sentido"):
        FonteEvidencia(id_fonte="FONTE-X", tipo="foto", referencia="a.jpeg",
                       descricao="x", estado=EstadoConhecimento.PENDENTE,
                       raiz_logica=RAIZ_LOGICA)


def test_acervo_externo_exige_raiz_logica():
    with pytest.raises(ReceitaErro, match="exige raiz_logica"):
        FonteEvidencia(id_fonte="FONTE-X", tipo="foto",
                       referencia="a/b.jpeg", descricao="x",
                       estado=EstadoConhecimento.PENDENTE,
                       forma_referencia=FORMA_ACERVO_EXTERNO)


def test_raiz_logica_nao_aceita_caminho():
    with pytest.raises(ReceitaErro, match="raiz_logica inválida"):
        _fonte_externa(raiz_logica="/acervo/evidencias")


# ---------------------------------------------------------------------------
# T28–T29 · gates continuam fechados
# ---------------------------------------------------------------------------

def test_t28_gate_de_calculo_continua_bloqueado():
    rec = receita_mod.construir_receita_preliminar()
    bib = fontes.carregar_biblioteca_oficial()
    r = validar.validar_prontidao_para_calculo(rec, bib, RAIZ)
    assert not r.ok, "a E.4F registra proveniência; ela não confirma regra"


def test_t29_gate_de_producao_continua_bloqueado():
    rec = receita_mod.construir_receita_preliminar()
    bib = fontes.carregar_biblioteca_oficial()
    assert not validar.validar_prontidao_para_producao(rec, bib, RAIZ).ok


def test_manifesto_nao_altera_a_receita(manifesto):
    """O manifesto NÃO é receita: nenhum artefato entra na composição.

    Ligar as 112 fontes à receita faria a evidência herdar os gates dela e
    daria a impressão de que registrar foto confirma regra de corte."""
    rec = receita_mod.construir_receita_preliminar()
    ids_da_receita = {f.id_fonte for f in rec.fontes}
    ids_externos = {f.id_fonte for f in manifesto.artefatos_externos}
    assert not (ids_da_receita & ids_externos)


# ---------------------------------------------------------------------------
# T30 · o manifesto carrega sem o acervo
# ---------------------------------------------------------------------------

def test_t30_carregar_manifesto_nao_toca_no_acervo(monkeypatch):
    """Nem a variável de ambiente é consultada para carregar e validar."""
    monkeypatch.delenv("ESQUADRIACORE_ACERVO_SUPREMA_CORRER_2F", raising=False)

    def proibido(*a, **k):                     # pragma: no cover
        raise AssertionError("validação estrutural leu bytes do acervo")

    monkeypatch.setattr(Path, "read_bytes", proibido)
    man = carregar_manifesto(MANIFESTO)
    assert validar_manifesto(man).ok
    assert len(man.artefatos_externos) == TOTAL_DE_ARTEFATOS


# ---------------------------------------------------------------------------
# Identidade dos artefatos
# ---------------------------------------------------------------------------

def test_id_de_artefato_e_deterministico_e_legivel():
    caminho = "02_janela_pequena/lado esquerdo do trilho superior.jpeg"
    assert id_de_artefato(caminho) == id_de_artefato(caminho)
    assert id_de_artefato(caminho) == \
        "FONTE-02-JANELA-PEQUENA-LADO-ESQUERDO-DO-TRILHO-SUPERIOR-JPEG"


def test_id_de_artefato_nao_depende_de_posicao_nem_de_hash():
    """Inserir arquivo no meio do acervo não renumera os outros."""
    a = id_de_artefato("g/a.jpeg")
    b = id_de_artefato("g/b.jpeg")
    assert a != b
    assert id_de_artefato("g/a.jpeg") == a


def test_id_de_artefato_separa_extensoes():
    assert id_de_artefato("g/croqui.pdf") != id_de_artefato("g/croqui.jpeg")


def test_id_de_artefato_normaliza_acento_sem_colidir():
    assert id_de_artefato("05_Wvetro/Produção/x.pdf") == \
        "FONTE-05-WVETRO-PRODUCAO-X-PDF"


def test_inventariar_acervo_le_metadado_e_nao_copia_bytes(tmp_path):
    (tmp_path / "g").mkdir()
    (tmp_path / "g" / "a.txt").write_bytes(b"abc")
    itens = inventariar_acervo(tmp_path, RAIZ_LOGICA)
    assert len(itens) == 1
    assert itens[0]["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert itens[0]["tamanho_bytes"] == 3
    assert itens[0]["grupo"] == "g"
    assert itens[0]["caminho_relativo"] == "g/a.txt"
    assert "conteudo" not in itens[0]


def test_inventariar_acervo_recusa_symlink(tmp_path):
    (tmp_path / "g").mkdir()
    alvo = tmp_path / "g" / "a.txt"
    alvo.write_bytes(b"abc")
    (tmp_path / "g" / "atalho.txt").symlink_to(alvo)
    with pytest.raises(ReceitaErro, match="symlink"):
        inventariar_acervo(tmp_path, RAIZ_LOGICA)


def test_inventariar_acervo_recusa_raiz_inexistente(tmp_path):
    with pytest.raises(ReceitaErro, match="inexistente"):
        inventariar_acervo(tmp_path / "nada", RAIZ_LOGICA)


# ---------------------------------------------------------------------------
# Manifesto real — coerência geral
# ---------------------------------------------------------------------------

def test_manifesto_real_valida(manifesto):
    assert validar_manifesto(manifesto).ok, \
        validar_manifesto(manifesto).descrever()


def test_manifesto_tem_as_vinte_afirmacoes(manifesto):
    """A01–A16 são a topologia (E.4F); A17–A20, a referência dimensional (E.4G)."""
    assert [a.identificador for a in manifesto.afirmacoes] == \
        [f"A{i:02d}" for i in range(1, 21)]


def test_toda_afirmacao_confirmada_tem_sustentacao(manifesto):
    indice = manifesto.indice_de_fontes()
    for a in manifesto.afirmacoes:
        if a.estado not in ESTADOS_CONFIRMADOS:
            continue
        sustentam = [c for c in a.citacoes if c.sustenta
                     and indice[c.id_fonte].estado is a.estado]
        assert sustentam, f"{a.identificador} confirmada sem sustentação"


def test_todo_artefato_externo_tem_hash_e_tamanho(manifesto):
    for f in manifesto.artefatos_externos:
        assert f.sha256 and len(f.sha256) == 64
        assert f.tamanho_bytes and f.tamanho_bytes > 0
        assert f.raiz_logica == RAIZ_LOGICA


# ---------------------------------------------------------------------------
# E.4G · referência dimensional — arbitragem, não medição
# ---------------------------------------------------------------------------

ARBITRAGEM_E4G = RAIZ / "curadoria/handoffs/e4g/referencia_dimensional_suprema_2f.md"


def test_arbitragem_dimensional_e4g_esta_integra(manifesto):
    """O hash citado tem de bater com o arquivo — senão a citação é fóssil."""
    fonte = manifesto.indice_de_fontes()["FONTE-REFERENCIA-DIMENSIONAL-E4G"]
    dados = (RAIZ / fonte.referencia).read_bytes()
    assert hashlib.sha256(dados).hexdigest() == fonte.sha256
    assert len(dados) == fonte.tamanho_bytes


def test_arbitragem_dimensional_nao_e_evidencia_fisica_primaria(manifesto):
    """Registra que um especialista decidiu, não que alguém mediu."""
    fonte = manifesto.indice_de_fontes()["FONTE-REFERENCIA-DIMENSIONAL-E4G"]
    assert fonte.tipo == "especialista_de_dominio"
    assert fonte.tipo not in TIPOS_DE_EVIDENCIA_PRIMARIA
    assert not fonte.identifica_exemplar
    assert fonte.estado is EstadoConhecimento.CONFIRMADO_ESPECIALISTA
    assert fonte.autoria_completa            # quem, quando e onde


def test_a17_registra_l_e_h_como_vao(manifesto):
    a17 = manifesto.afirmacao("A17")
    assert a17.estado is EstadoConhecimento.CONFIRMADO_ESPECIALISTA
    texto = a17.texto.upper()
    assert "LARGURA DO VÃO" in texto and "ALTURA DO VÃO" in texto
    sustentam = [c.id_fonte for c in a17.citacoes if c.sustenta]
    assert sustentam == ["FONTE-REFERENCIA-DIMENSIONAL-E4G"], (
        "quem sustenta A17 é a arbitragem; a ficha só corrobora, porque ela "
        "não declara o significado de L e H")


def test_a17_registra_que_a_aritmetica_nao_decidiria_sozinha(manifesto):
    """A coincidência algébrica não pode ser lida como se fosse a prova."""
    obs = manifesto.afirmacao("A17").observacao.lower()
    assert "coincidência algébrica não é definição de variável" in obs


def test_a19_preserva_a_fracao_sem_escolher_politica(manifesto):
    """957,5 calculado × 957 medido — registrado, não resolvido."""
    a19 = manifesto.afirmacao("A19")
    assert "957,5" in a19.texto and "957" in a19.texto
    obs = a19.observacao.lower()
    assert "pendente" in obs
    assert "floor e trunc devolvem o mesmo resultado" in obs, (
        "para comprimentos positivos as duas operações são indistinguíveis; "
        "o registro não pode sugerir que uma medição futura as separa")


def test_expressoes_continuam_candidatas_sem_validacao_multicaso(manifesto):
    """Um caso com corte real não é validação multicaso."""
    obs = manifesto.afirmacao("A18").observacao.lower()
    assert "um caso" in obs
    assert "candidatas" in obs
    assert "não têm saída de corte real" in obs


def test_arbitragem_dimensional_nao_contem_formula_executavel():
    """O registro é documento. Não pode virar código por descuido."""
    texto = ARBITRAGEM_E4G.read_text(encoding="utf-8")
    for proibido in ("def ", "lambda", "eval(", "import ", "return "):
        assert proibido not in texto, f"código executável no registro: {proibido!r}"


FORMULAS_CANDIDATAS = ("L-32", "H-5", "H-55", "(L-132)/2")
RESSALVAS = ("candidat", "nenhuma", "não", "proibid", "pendente", "empír")


def test_manifesto_nao_promove_formula_a_regra(manifesto):
    """Citar a expressão é permitido; registrá-la sem ressalva não é.

    A E.4G precisou nomear as expressões para dizer o que elas reproduzem. O
    que continua proibido é a expressão aparecer como se fosse regra — por isso
    a checagem é por REGISTRO (texto + observação), e não por linha solta: a
    ressalva de uma afirmação mora na observação dela."""
    registros = [(a.identificador, f"{a.texto} {a.observacao or ''}")
                 for a in manifesto.afirmacoes]
    registros += [(f"nota[{i}]", n) for i, n in enumerate(manifesto.notas)]
    registros += [(c.identificador, f"{c.descricao} {' '.join(c.valores)}")
                  for c in manifesto.conflitos]
    for ident, conteudo in registros:
        if not any(f in conteudo for f in FORMULAS_CANDIDATAS):
            continue
        assert any(r in conteudo.lower() for r in RESSALVAS), (
            f"{ident}: expressão dimensional citada sem ressalva")


def test_manifesto_nao_tem_campo_de_formula_executavel():
    """A garantia estrutural: o schema do manifesto não carrega expressão.

    Enquanto não existir campo, nenhum consumidor pode confundir o registro com
    entrada de motor de cálculo."""
    import yaml
    dados = yaml.safe_load(MANIFESTO.read_text(encoding="utf-8"))
    proibidos = {"formula", "formula_medida", "expressao", "formula_largura",
                 "formula_altura", "regra_dimensional"}

    def varrer(no, caminho="raiz"):
        if isinstance(no, dict):
            for k, v in no.items():
                assert k not in proibidos, f"campo de fórmula em {caminho}: {k}"
                varrer(v, f"{caminho}.{k}")
        elif isinstance(no, list):
            for i, v in enumerate(no):
                varrer(v, f"{caminho}[{i}]")

    varrer(dados)


def test_acervo_real_confere_quando_montado(manifesto):
    """Prova de ponta a ponta — pulada quando o acervo não está na máquina."""
    raizes = validar.raizes_fisicas_do_ambiente()
    if RAIZ_LOGICA not in raizes:
        pytest.skip(f"defina ESQUADRIACORE_ACERVO_{RAIZ_LOGICA} para conferir "
                    f"os bytes reais do acervo externo")
    r = verificar_acervo_do_manifesto(manifesto, raizes)
    assert r.ok, r.descrever()
