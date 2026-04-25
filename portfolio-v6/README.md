# 📊 Portfolio Terminal

Dashboard pessoal tipo "Bloomberg Terminal" construído em Streamlit + Plotly.

**Destaques v2:** sparklines inline, hero numbers editoriais, badges de classe/sinal, watchlist com sinal automático, form de transacções, feed de notícias por ticker.

## 🚀 Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate        # Windows
pip install -r requirements.txt
streamlit run app.py
```

Abre automaticamente em `http://localhost:8501`.

## 📑 Páginas

| # | Página | Conteúdo |
|---|--------|----------|
| — | **Dashboard** (main) | Hero P/L com movimento do dia · alocações (classe/sector/moeda) · holdings com sparklines 30d · rentabilidade acumulada vs S&P · métricas de risco · correlação · alertas · performance 12m |
| 1 | **Holdings** | Filtros + deep-dive por posição com linhas de PM/stop/TP no gráfico 2A + R/R ratio |
| 2 | **Watchlist** | Cards com sinal calculado automaticamente (Zona de compra / Monitorizar / Já correu / Stop atingido) + formulário de add/remove |
| 3 | **Nova Transação** | Form que actualiza o `portfolio.json` automaticamente: BUY faz média ponderada do PM, SELL reduz ou fecha. Histórico de transacções registado |
| 4 | **Notícias** | Feed via Yahoo Finance por ticker, agrupado em tabs + vista consolidada |
| 5 | **Risco** | Drawdown histórico · volatilidade rolling 30d · Monte Carlo customizável com 5 percentis |
| 6 | **Macro** | VIX · EUR/USD · ouro · Brent · DXY · S&P · NASDAQ · STOXX |
| 7 | **Projeções** | DCA composto com 3 cenários + ajuste inflação |
| 8 | **Config** | Editor visual do JSON completo (perfil, posições, watchlist) |

## ⚙️ Ficheiros

```
portfolio-dashboard/
├── app.py                      # Dashboard principal
├── pages/                      # 8 páginas adicionais
├── utils/
│   ├── data.py                 # yfinance, news, transactions, watchlist
│   ├── metrics.py              # Sharpe, Sortino, beta, alpha, drawdown, HHI
│   └── styling.py              # Tipografia JetBrains Mono + Instrument Serif, badges
├── data/portfolio.json         # Posições + watchlist + transactions log
├── .streamlit/config.toml      # Tema dark
└── requirements.txt
```

## 🎨 Design

- **Tipografia:** Instrument Serif (display) + Inter (UI) + JetBrains Mono (números tabulares)
- **Paleta:** Navy #0a0e17 base · Teal #00d4aa (ganhos) · Coral #ff5c7a (perdas) · Âmbar #ffb74d (avisos)
- **Densidade Bloomberg:** tabular-nums em toda a parte, sparklines inline, R/R ratios, badges de classe

## 🔗 Tickers Yahoo Finance

| Mercado | Exemplo | Sufixo |
|---------|---------|--------|
| EUA | `MSFT`, `NVDA`, `TSM`, `ASML` | — |
| Londres | `VUAA.L`, `EXUS.L` | `.L` |
| Xetra | `SXR8.DE`, `IWDA.DE` | `.DE` |
| Amesterdão | `IWDA.AS` | `.AS` |
| Milão | `VUAA.MI` | `.MI` |
| Câmbios | `EURUSD=X` | `=X` |
| Commodities | `GC=F` (ouro), `CL=F` (crude) | `=F` |
| Índices | `^GSPC`, `^NDX`, `^STOXX` | `^` |

## ⚠️ Avisos

- Dados Yahoo Finance têm atraso 15-20 min
- Notícias via API pública do Yahoo (pode ter rate limit)
- Não é aconselhamento financeiro

## 🔮 Próximos Passos

- Sincronização bidireccional com Notion
- Alertas por email/Telegram quando preço atinge stop/TP
- Fundamentais (PE, EPS, revenue growth) via `yfinance.Ticker.info`
- Scanner dos teus 9 filtros como página separada
- Deploy Streamlit Cloud (grátis, acesso mobile)
