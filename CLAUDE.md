# EsquadriaCore — Contexto para Claude Code

## O que é este projeto
Plataforma de conhecimento técnico para a indústria de esquadrias de alumínio.
Missão: transformar conhecimento técnico fragmentado em domínio estruturado,
reutilizável e independente de fabricantes.

## Estado atual (Sprint 3.5 concluído)
- Documentação v1.0 congelada em docs/
- 10/10 testes passando (runner próprio; pytest precisa ser instalado)
- 2 testes xfail aguardando OCR (Sprint D)
- Auditoria arquitetural: nenhuma questão crítica encontrada

## Estrutura
- domain/      → entidades do domínio + erros (nunca importa outros módulos)
- providers/   → base.py (contrato Provider ABC) + pdf_texto.py (implementação)
- pipeline/    → orquestração da aquisição
- core_engine/ → renderer matplotlib + resolução de geometria
- tests/       → unitários + regressão (Centenário) + xfail (Alcoa, Vitral Sul)
- docs/        → documentação v1.0 completa (NÃO alterar)

## Sprint D — Provider de OCR (em andamento)
OcrProvider implementado em providers/ocr.py (pdftoppm + Tesseract), seguindo
o contrato Provider (providers/base.py).

Casos reais (verificados em 2026-07-09 contra os PDFs em dados_exemplo/):
- Alcoa ("catalago-alcoa (1).pdf"): OCR puro. Seção Suprema págs 170-183 é
  vetor sem texto extraível (só o cabeçalho "LINHA SUPREMA" está na camada de
  texto). OcrProvider extraiu ~38 perfis (19 SU-), 17 com peso válido.
- Vitral Sul (PERFIS-DE-ALUMINIO-02-07-2026.pdf): caso HÍBRIDO, não OCR puro
  (CORREÇÃO da premissa original "desenho como JPEG raster"). Os códigos
  SU-XXX são texto nativo nas págs 71-93 (e 221) — PdfTextoProvider cobre.
  Só os desenhos são JPEG raster; a maioria dos pesos não está na camada de
  texto, então peso_suspeito=True é o comportamento correto (Volume 9).
  Atenção: peso aparece como "kg/m" e também "kg/mt".

Os dois testes de regressão em tests/test_basicos.py cobrem esses casos
(Alcoa via OcrProvider, Vitral Sul via PdfTextoProvider) — pulados se os
PDFs não estiverem em dados_exemplo/.

## Regras inegociáveis (ADRs)
- ADR-001: geometria é a única fonte de verdade (nunca armazenar imagem)
- ADR-002: Renderer nunca conhece regra de engenharia
- ADR-003: Provider abstrai a origem — Pipeline nunca depende do formato
- ADR-004: FamíliaMercado é vocabulário de mercado, nunca implica intercambiabilidade
- ADR-005: GeometriaPadrao é ativo compartilhado, associação via PerfilGeometria (auditável)
- ADR-007: preservar conhecimento bruto mesmo sem modelo ainda

## Regra geral
Nenhuma entidade nova sem evidência prática. Nenhuma abstração sem necessidade real.
Zero funcionalidade nova fora do escopo do Sprint em curso.

## Como rodar os testes
pip install pytest numpy matplotlib
sudo apt install poppler-utils tesseract-ocr tesseract-ocr-por
pytest tests/ -v
# Regressão do Centenário: coloque Centenário.pdf em dados_exemplo/
