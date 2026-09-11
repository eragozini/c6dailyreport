# C6 Daily Report

Gera um fechamento diário de mercados em PNG e PDF, acompanhado de um JSON de auditoria com os valores, variações, fontes e datas efetivas de cada série.

## Correções de dados

- **Dia:** último fechamento dividido pelo fechamento imediatamente anterior.
- **Mês (MTD):** último fechamento dividido pelo último fechamento anterior ao primeiro dia do mês. Não é mais uma janela móvel de 30 dias.
- **Ano (YTD):** último fechamento dividido pelo último fechamento do ano anterior. Não usa mais o primeiro pregão do próprio ano.
- **IFIX:** índice real em pontos obtido no portal público da B3. O ETF `XFIX11` não é mais apresentado como se fosse o IFIX.
- **Selic diária acumulada:** série SGS 11 do Banco Central, acumulada até a data-base do relatório e com o ano calculado dinamicamente.
- **Ausências:** dado crítico ausente ou histórico insuficiente interrompe a geração. O sistema nunca converte uma falha em `+0,00%`.

A data exibida no relatório é a data do último fechamento do Ibovespa, e não a data do runner. O JSON registra a data individual de cada ativo e eventuais diferenças entre calendários de mercado.

## Execução local

Requer Python 3.12.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r requirements.lock   # Windows
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python build_single_page.py
```

Em Linux/macOS, use `.venv/bin/python`. Os artefatos são gravados em `out/`:

- `fechamento_YYYYMMDD.pdf`
- `fechamento_YYYYMMDD.png`
- `fechamento_YYYYMMDD.json`

O JSON é a trilha de auditoria indicada para investigar divergências sem extrair texto do PDF.

## Automação e e-mail

O workflow diário roda às 19:17 em `America/Sao_Paulo`, de segunda a sexta. Se o Ibovespa ainda não tiver fechamento da data corrente, o envio é ignorado para evitar relatório antigo com data nova ou duplicidade em feriados.

Configure os secrets:

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_TO` (lista separada por vírgulas).

Opcionalmente, configure a variável `SMTP_SECURITY` como `starttls` (padrão), `ssl` ou `none`, e os ambientes locais `SMTP_FROM` e `SMTP_TIMEOUT`.

Para envio manual:

```bash
python send_email.py --pdf out/fechamento_20260910.pdf --report-date 2026-09-10
```

## Fontes e limitações

- IFIX: portal público da B3.
- Selic diária: API SGS do Banco Central do Brasil.
- Demais cotações: Yahoo Finance por meio de `yfinance`.

O Yahoo Finance pode ter ajustes, horários e termos de uso próprios; valide o uso pretendido antes de distribuição comercial. O arquivo de apresentação compactado existente no repositório é material de design e não participa da execução. O projeto ainda não declara uma licença de código — essa escolha deve ser feita pelo proprietário.
