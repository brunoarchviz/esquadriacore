# Plano de Curadoria — EsquadriaCore

Priorização de curadoria baseada em conhecimento de mercado do Bruno
(especialista de domínio). Define o que homologar primeiro no Sprint E.

## Priorização de Famílias (por uso comercial real)

| Família | Prioridade | Sistema | Observação de mercado |
|---|---|---|---|
| Suprema | ★★★★★ | Correr | Mais vendida — melhor custo-benefício, bitola 25mm |
| Gold | ★★★★★ | Correr | 2ª principal — perfis mais robustos/bonitos, mais pesada e cara, bitola 32mm. Tem subdivisão Gold 3 e Gold 4 (diferença a confirmar) |
| Linha 30 | ★★★☆☆ | Giro/Pivotante | Sem sistema de correr no catálogo. Excelente para porta de giro/pivotante |
| Linha 25 | ★★★☆☆ | Giro/Pivotante | Mesma lógica da Linha 30, bitola menor |
| Linha 42 | ★★☆☆☆ | Giro/Pivotante | Nicho caro — perfis bem maiores que os convencionais, esteticamente marcantes |

## Observações de Mercado (conhecimento empírico — não vem de catálogo)

- Suprema e Gold são AS duas linhas principais do mercado de esquadrias — juntas
  dominam as vendas.
- A APLICAÇÃO define a família tanto quanto a geometria: Suprema/Gold = correr;
  Linha 25/30/42 = giro/pivotante. Não são intercambiáveis por sistema.
- Linha 25/30 têm bitola parecida com Suprema, mas NÃO são a mesma família —
  distinção funcional (sistema construtivo), não só dimensional. (confirma decisão
  registrada desde a v1.0)
- Gold pesa mais que Suprema → custa mais → escolha do cliente é custo vs. estética.

## Sequência de homologação (Sprint E)

1. Suprema — começar pelos 8 códigos confirmados em 2+ fabricantes
   (SU-005, SU-009, SU-024, SU-025, SU-056, SU-228, SU-230, SU-280)
2. Gold — depois de confirmar a diferença Gold 3 vs Gold 4
3. Linha 30, depois 25 e 42 — conforme necessidade

## Pendências de investigação do Bruno
- [x] Diferença real entre Gold 3 e Gold 4 — RESPONDIDA em 2026-07-10, ver
      "Gold 3 × Gold 4" nos Achados abaixo

## Achados de Curadoria (Sprint E, sessão 1)

### Mapeamento de FamíliaMercado por fabricante (ADR-004 em ação)
O mesmo código SU-XXX aparece sob nomes comerciais diferentes por fabricante:
- Alcoa: "Suprema"
- Vitral Sul: "Nobile 2.5"
Confirma que FamiliaMercado é vocabulário, não identidade. "Suprema" (Alcoa) e
"Nobile 2.5" (Vitral Sul) são aliases da MESMA família de mercado. Já estava
previsto no ADR-004; agora é dado confirmado, não hipótese.

### Códigos legados como chave de rastreabilidade
A Alcoa referencia códigos legados entre parênteses (ex: SU-005 = "P-634/E").
Podem servir como chave histórica de rastreabilidade. Registrar quando aparecerem,
não estruturar ainda (ADR-007).

### Gold 3 × Gold 4 — gerações, não subdivisão (achado 2026-07-10)
Evidência dos catálogos (alcoa_gold3.pdf, ~2004 × CATALOGO_IVGOLD.pdf, Hydro):
- Gold 3 = "Linha III Gold" (era Alcoa), 93 códigos LG-.
- Gold 4 = "Linha IV Gold" / "Gold IV®", 139 códigos LG- no IVGold.
- Núcleo compartilhado: 35 códigos LG- presentes nas duas gerações.
  58 códigos do Gold 3 saíram; 104 novos no Gold 4 (quase todos LG-100+).
Conclusão: sucessão geracional da mesma linha de bitola 32mm, com ~1/3 de
continuidade de perfis — não é subdivisão estética.

CORREÇÃO (2026-07-10, com catálogos adicionais): Gold 4 NÃO nasceu na Hydro —
alcoa_gold-4.pdf prova que a geração IV já existia na era Alcoa (112 dos seus
122 códigos LG estão no IVGold da Hydro; a Hydro CONTINUOU a linha).
Nota de grafia: catálogos da era Hydro escrevem os códigos sem hífen ("LG159");
os da era Alcoa, com hífen ("LG-159") — parsers precisam de hífen opcional.
catalogo_ivgold-r06.pdf é revisão contida no IVGold de referência (111 ⊂ 139).

### O risco geracional mora na troca de ERA, não de geração (achado 2026-07-10)
Comparação de pesos com dado real (curadoria/comparar_gold_geracoes.py):
- Gold 3 × Gold 4 DENTRO da era Alcoa: 38 códigos comuns com peso, 30 com
  peso IDÊNTICO (0.0%), 7 com Δ ≤ 2.2%. Único divergente: LG-020 (9.0%).
- Era Alcoa × era Hydro (IVGold): LG-003, LG-015 e LG-027 divergem 13-16% —
  os MESMOS códigos que batem 0.0% entre Gold 3 e Gold 4 Alcoa.
Conclusão: a transição geracional III→IV (Alcoa) preservou os perfis quase
intactos; o ponto de ruptura real é a troca de fabricante/era (Alcoa→Hydro),
onde a Hydro reprojetou perfis mantendo códigos (nova liga/ferramental/
otimização de peso — lógica de negócio plausível).
A suposição original ("geração diferente = risco") errava ONDE o risco mora;
o dado real corrigiu.

ESTRATÉGIA DA CURADORIA GOLD EM DOIS EIXOS (decisão Bruno, 2026-07-10):
- Eixo 1 (seguro): Gold 3 ↔ Gold 4 Alcoa — evidência forte, curadoria em lote
  mais ágil; atenção especial só no LG-020.
- Eixo 2 (arriscado): era Alcoa ↔ era Hydro (IVGold) — cautela dobrada,
  confirmação visual obrigatória, sem pressa.
Sequência: validar o método no Eixo 1 primeiro, depois atacar o Eixo 2.

### Nova Gold — terceira ramificação, sistema de código GN- (achado 2026-07-10)
nova_gold-r36.pdf (317 págs, Hydro) e catalogo_gold.pdf (234 págs) usam
códigos GN-, não LG-. O guarda-chuva comercial "Gold" cobre DUAS famílias de
código distintas: LG (Gold III → Gold IV → IVGold) e GN (Nova Gold).
Relação geométrica entre LG e GN ainda não investigada — não presumir
equivalência. cortes_alcoa.pdf é material de tipologias (sem códigos/pesos).

REGRA DE CURADORIA ESPECÍFICA DA GOLD (decisão Bruno, 2026-07-10): código
idêntico entre GERAÇÕES da MESMA marca é hipótese mais fraca que código
idêntico entre fabricantes independentes (caso Suprema) — a Hydro pode ter
redesenhado perfis mantendo a numeração. Confirmação visual é OBRIGATÓRIA em
TODOS os casos da Gold, não só nos de peso divergente.

### SU-005 — primeira homologação de alta confiança
- Função idêntica: TRAVESSA BANDEIRA / MARCO / CORRER 2 (Alcoa e Vitral Sul)
- Peso idêntico: 1.108 kg/m (delta 0.0%)
- Cotas idênticas: largura 69.6, altura 46, espaçamento trilhos 35
- Fabricantes independentes (sem vínculo societário)
- Candidato a GEO-SU-005 compartilhada, nivel_de_confianca = alto

## Sprint E.2 — Contornos Renderizáveis (decisão dos três: Bruno, Claude, ChatGPT)

### Princípio orientador
> Um contorno pode ser comercialmente utilizável sem ser geometricamente exato
> para fabricação.

O EsquadriaCore alimenta orçamento, imagem técnica, tipologia e comparação — não
corte/fabricação CNC. A meta dos contornos é "renderizável comercial" (reconhecível,
proporcional, coerente), NÃO "CAD exato". Isso protege o projeto de virar um poço de
esforço técnico sem retorno proporcional.

### Escala de fidelidade do contorno (metadado nivel_contorno, não entidade nova)
- 0_bruto_aproximado    — sabemos que a geometria existe, não desenhamos ainda (estado atual das 46)
- 1_envelope_funcional  — contorno simples (largura/altura/abas principais)
- 2_renderizavel_comercial — ALVO IMEDIATO: visualmente coerente, reconhecível, suficiente para orçamento/apresentação
- 3_vetorial_validado   — path extraído do PDF com confiança + validado pelo Bruno
- 4_alta_fidelidade     — futuro, talvez nunca necessário para o produto principal

### Método (híbrido e progressivo — Opção C)
1. Escolher geometria prioritária
2. Tentar extrair vetor do PDF; se limpo, usar como base
3. Se sujo, usar cotas + desenho simplificado próprio
4. Gerar preview renderizado
5. Bruno valida visualmente
6. Registrar nivel_contorno e observação; promover para renderizavel_comercial

### Nota estratégica (técnica + jurídica)
Priorizar contorno simplificado PRÓPRIO sobre cópia vetorial exata do catálogo.
Alinha o técnico com o jurídico (Modelo Paramétrico Próprio, não redistribuição).

### Escopo do Sprint E.2
Amostra inicial de 8-12 geometrias com funções variadas (marco, folha, travessa,
montante, mão de amigo, coluna). Critério de pronto: Renderer gera imagem coerente +
Bruno valida + nivel_contorno sobe para renderizavel_comercial.
