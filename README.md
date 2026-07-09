# EsquadriaCore

Plataforma de conhecimento técnico para o setor de esquadrias de alumínio.

> "Transformar o conhecimento técnico fragmentado da indústria de esquadrias em
> um domínio estruturado, reutilizável e independente de fabricantes."

Documentação completa (Constituição + 9 Volumes + ADRs): ver `docs/`.

## Estrutura do repositório

```
esquadriacore/
├── domain/          Entidades do Modelo de Domínio (Volume 3) + erros (Volume 9)
├── providers/       Contrato Provider (ADR-003) + PdfTextoProvider
├── pipeline/        Orquestração da aquisição (Volume 6)
├── core_engine/     Renderer + resolução de geometria (Volume 7, ADR-005)
├── tests/           Suíte do Volume 10 (unitários + regressão + xfail p/ OCR)
├── dados_exemplo/   Coloque aqui os PDFs de catálogo para os testes de regressão
└── docs/            Documentação v1.0 congelada
```

## Como rodar localmente

Requisitos: Python 3.10+, poppler-utils (`pdftotext`, para o PdfTextoProvider).

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. (Debian/Ubuntu) garantir poppler para extração de PDF
sudo apt install poppler-utils

# 3. Rodar os testes
pytest tests/ -v

# Os testes de regressão de catálogo só rodam se os PDFs estiverem em
# dados_exemplo/ (ex: dados_exemplo/Centenário.pdf). Sem eles, são pulados
# automaticamente (skipif) — os demais testes rodam normalmente.
```

## Exemplo mínimo de uso

```python
from providers.pdf_texto import PdfTextoProvider
from pipeline.aquisicao import executar_aquisicao, resumo_extracao

provider = PdfTextoProvider(
    "dados_exemplo/Centenário.pdf",
    pagina_inicio=87, pagina_fim=103,
    fabricante="Centenário",
)
perfis = executar_aquisicao(provider)
print(resumo_extracao(perfis))
# {'total': 73, 'com_peso': 73, 'peso_suspeito': [], 'indice_medio_qualidade': 2.0}
```

## Estado atual (Sprint 3.5 — Consolidação do Código)

- ✅ Protótipos das Fases 0-4 migrados e unificados (parsers Linha 25/30 eram
  código duplicado — agora uma implementação parametrizada)
- ✅ 9/9 testes passando, incluindo regressão contra o catálogo Centenário real
- ✅ Zero funcionalidade nova (regra do Sprint 3.5)
- ⏳ Dois testes `xfail` aguardando o Provider de OCR (Sprint D): Alcoa (vetor
  sem texto) e Vitral Sul (raster embutido)

## Regras do projeto (resumo — detalhes em docs/)

1. Nenhuma entidade nova sem evidência prática.
2. Geometria é a única fonte de verdade (ADR-001).
3. Renderer nunca conhece regra de engenharia (ADR-002).
4. Provider abstrai a origem dos dados (ADR-003).
5. Curadoria de geometria compartilhada é sempre humana e auditável (ADR-005).
