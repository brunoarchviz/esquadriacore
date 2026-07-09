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
- [ ] Diferença real entre Gold 3 e Gold 4

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

### SU-005 — primeira homologação de alta confiança
- Função idêntica: TRAVESSA BANDEIRA / MARCO / CORRER 2 (Alcoa e Vitral Sul)
- Peso idêntico: 1.108 kg/m (delta 0.0%)
- Cotas idênticas: largura 69.6, altura 46, espaçamento trilhos 35
- Fabricantes independentes (sem vínculo societário)
- Candidato a GEO-SU-005 compartilhada, nivel_de_confianca = alto
