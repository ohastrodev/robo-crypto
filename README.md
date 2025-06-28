# bot-python

Este projeto contém dois robôs de trading simulados para ETH/USDT:

- **robo_rsi.py**: Opera com base no indicador RSI.
- **robo_feargreed.py**: Opera com base no Fear and Greed Index.

## Pré-requisitos
- Python 3.8+
- Conta na Binance (para obter as chaves de API)

## Instalação
1. Clone o repositório.
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:
   ```env
   KEY_BINANCE=SEU_API_KEY
   SECRET_BINANCE=SEU_API_SECRET
   ```
   **Nunca suba o arquivo `.env` para o GitHub!**

## Como rodar os dois robôs simultaneamente

Execute:
```bash
python main.py
```

Os logs e operações simuladas serão salvos em arquivos CSV separados para cada bot.

## Observações
- O arquivo `.env` **não** deve ser versionado.
- Os robôs operam em modo simulação por padrão.
- Para rodar apenas um robô, execute `python robo_rsi.py` ou `python robo_feargreed.py`. 