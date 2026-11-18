---
name: responder-sugestoes
description: Fluxo padrão para tratar as sugestões que a equipe escreve de dentro do Cycle Navigator (botão da lâmpada). Usar SEMPRE que o Osmar pedir para olhar/rodar a fila de sugestões, no início de uma sessão de trabalho no programa, ou ao responder qualquer sugestão.
---

# Responder sugestões (padrão trazido do iRest/Ricco)

Quem usa o programa escreve a melhoria no próprio programa (lâmpada na barra de cima). A sugestão sai
carimbada com a foto da janela e o contexto (safra, mês, camada, talhão aberto, faixas, versão) e cai
numa pasta: `<dados>/sugestoes/<id>.json` + `<id>.png` (no Air: `~/CycleNavigator/dados/sugestoes`).
O dev (você) lê, passa pelo crivo do Osmar, implementa e RESPONDE NA FILA; quem pediu vê o status e a
resposta na janela de Sugestões, e um aviso ao abrir o programa.

## Fluxo (na ordem)

1. **Ler a fila** — `~/ENV/navigator/bin/python tools/sugestoes.py` (abertas e em andamento; REABERTA
   tem prioridade sobre nova). `… todas` mostra o histórico.
2. **Ver cada uma** — `… ver <id>`: conversa, contexto e o caminho da foto. **Abrir a foto com Read**:
   é a tela de que a pessoa está falando.
3. **CRIVO DO OSMAR — obrigatório antes de QUALQUER implementação** ("o time pode pedir algo que não é
   bom"): apresentar no chat quem pediu, a tela, o texto e a SUA recomendação (implementar assim /
   adaptar / descartar porque…). **Aguardar o OK explícito.** Sem OK: nada de código, a sugestão fica
   `aberta`. Exceção única: PERGUNTA informativa (zero mudança de código) — responder direto e avisar
   o Osmar com 1 linha.
4. **Com o OK** — `… responder <id> em_desenvolvimento ""`; implementar de forma CIRÚRGICA (só o
   necessário; não aproveitar para refatorar); rodar os testes (`python -m pytest -q`, com `CN_CONFIG`
   numa cópia de teste dos dados, nunca nos pontos reais) e olhar a tela por foto offscreen.
   Vetada pelo Osmar: `descartada` com justificativa educada — nunca ignorar em silêncio.
5. **Responder** — `… responder <id> implementada resposta.txt`, só DEPOIS de a mudança estar no
   aplicativo que a pessoa usa (o `.app` recompilado e instalado). Português, direto, sem jargão, em
   bullets (a janela renderiza `- ` como marcador e linha terminada em `:` como título):

   ```
   O que mudou:
   - <mudança, na linguagem de quem usa>

   Onde ver:
   - <tela e caminho>

   Observações:
   - <limite ou próximo passo, se houver>
   ```
6. **Fechar o ciclo** — conferir que a fila zerou e avisar o Osmar em 1 linha por sugestão respondida.

## Regras

- **Não quebrar o que funciona**: mudança cirúrgica, testes antes e depois, vizinhança exercitada.
- **Fidelidade**: a resposta descreve o que REALMENTE foi entregue; nunca prometer.
- **Nunca implementar sem o crivo do Osmar**, nem as "obviamente boas".
- As regras do CLAUDE.md valem igual: não apagar nada, commit/push só neste repositório e só com o ok.

## Vigia (acordar a sessão quando chega sugestão)

`~/ENV/navigator/bin/python tools/vigia_sugestoes.py --pasta ~/CycleNavigator/dados/sugestoes`, com
`run_in_background`. Ele termina quando cai sugestão nova ou reaberta, e isso acorda a sessão com o
texto e o caminho da foto. Depois de tratar (ou de apresentar ao Osmar), **religar o vigia**. Instância
única por trava; as já vistas ficam em `<pasta>/.vistas`.
