import pandas as pd
import os
import time
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv
import math
import csv
from datetime import datetime
import requests

load_dotenv()

api_key = os.getenv("KEY_BINANCE")
secret_key = os.getenv("SECRET_BINANCE")

cliente_binance = Client(api_key, secret_key)

codigo_operado = "ETHUSDT"
ativo_operado = "ETH"
periodo_candle = Client.KLINE_INTERVAL_1MINUTE
quantidade = 0.015
modo_simulacao = True
saldo_ficticio_usdt = 100.0
saldo_ficticio_ativo = 0.0
preco_ultima_compra = None

def registrar_operacao_simulada(tipo, quantidade, preco, saldo_usdt, saldo_ativo):
    with open('operacoes_simuladas_feargreed.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), tipo, quantidade, preco, saldo_usdt, saldo_ativo
        ])

def arredondar_quantidade(qty, step):
    return math.floor(qty / step) * step

def pegar_step_min_qty(codigo_ativo):
    try:
        symbol_info = cliente_binance.get_symbol_info(codigo_ativo)
        lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
        min_qty = float(lot_size_filter['minQty'])
        step_size = float(lot_size_filter['stepSize'])
        return min_qty, step_size
    except Exception as e:
        print(f"Erro ao pegar step/min qty: {e}")
        return 0.0, 0.0

def pegar_fear_and_greed_index():
    try:
        url = 'https://api.alternative.me/fng/'
        response = requests.get(url)
        data = response.json()
        valor = int(data['data'][0]['value'])
        classificacao = data['data'][0]['value_classification']
        return valor, classificacao
    except Exception as e:
        print(f"Erro ao buscar Fear and Greed Index: {e}")
        return None, None

def pegando_dados(codigo, intervalo):
    try:
        candles = cliente_binance.get_klines(symbol=codigo, interval=intervalo, limit=1000)
        precos = pd.DataFrame(candles)
        precos.columns = ["tempo_abertura", "abertura", "maxima", "minima", "fechamento", "volume", "tempo_fechamento", "moedas_negociadas", "numero_trades",
                          "volume_ativo_base_compra", "volume_ativo_cotação", "-"]
        precos = precos[["fechamento", "tempo_fechamento"]]
        precos["fechamento"] = precos["fechamento"].astype(float)
        precos["tempo_fechamento"] = pd.to_datetime(precos["tempo_fechamento"], unit="ms").dt.tz_localize("UTC")
        precos["tempo_fechamento"] = precos["tempo_fechamento"].dt.tz_convert("America/Sao_Paulo")
        return precos
    except Exception as e:
        print(f"Erro ao pegar dados: {e}")
        return None

def estrategia_trade(dados, codigo_ativo, ativo_operado, quantidade):
    global saldo_ficticio_usdt, saldo_ficticio_ativo, preco_ultima_compra
    if dados is None:
        print("Dados não disponíveis para estratégia.")
        return
    indice_fg, classificacao_fg = pegar_fear_and_greed_index()
    if indice_fg is None:
        print("Não foi possível obter o Fear and Greed Index. Pulando ciclo.")
        return
    print(f"Fear and Greed Index: {indice_fg} ({classificacao_fg})")
    taxa_binance = 0.002
    min_qty, step_size = pegar_step_min_qty(codigo_ativo) if not modo_simulacao else (0.001, 0.001)
    preco_atual = dados["fechamento"].iloc[-1]
    motivo_compra = []
    motivo_venda = []
    # Compra
    if saldo_ficticio_ativo < min_qty and saldo_ficticio_usdt > 1:
        if indice_fg > 35:
            motivo_compra.append(f"Fear and Greed Index ({indice_fg}) não está em medo (0-35)")
            print(f"[SIMULAÇÃO] Não comprou: {'; '.join(motivo_compra)}")
        else:
            quantidade_ajustada = (saldo_ficticio_usdt * (1 - taxa_binance)) / preco_atual
            quantidade_ajustada = arredondar_quantidade(quantidade_ajustada, step_size)
            custo = quantidade_ajustada * preco_atual / (1 - taxa_binance)
            if quantidade_ajustada >= min_qty and saldo_ficticio_usdt >= custo:
                saldo_ficticio_usdt -= custo
                saldo_ficticio_ativo += quantidade_ajustada
                preco_ultima_compra = preco_atual
                registrar_operacao_simulada('COMPRA', quantidade_ajustada, preco_atual, saldo_ficticio_usdt, saldo_ficticio_ativo)
                print(f"[SIMULAÇÃO] COMPRA: Fear and Greed Index={indice_fg} ({classificacao_fg}). Comprou {quantidade_ajustada} ETH a {preco_atual} USDT")
            else:
                print("[SIMULAÇÃO] Saldo USDT insuficiente para comprar.")
    # Venda
    if saldo_ficticio_ativo >= min_qty and saldo_ficticio_usdt < 1:
        if indice_fg < 65:
            motivo_venda.append(f"Fear and Greed Index ({indice_fg}) não está em ganância (65+)")
            print(f"[SIMULAÇÃO] Não vendeu: {'; '.join(motivo_venda)}")
        elif preco_ultima_compra is not None:
            if preco_atual > preco_ultima_compra:
                quantidade_ajustada = arredondar_quantidade(saldo_ficticio_ativo, step_size)
                receita = quantidade_ajustada * preco_atual * (1 - taxa_binance)
                if quantidade_ajustada >= min_qty and saldo_ficticio_ativo >= quantidade_ajustada:
                    saldo_ficticio_ativo -= quantidade_ajustada
                    saldo_ficticio_usdt += receita
                    registrar_operacao_simulada('VENDA', quantidade_ajustada, preco_atual, saldo_ficticio_usdt, saldo_ficticio_ativo)
                    print(f"[SIMULAÇÃO] VENDA: Fear and Greed Index={indice_fg} ({classificacao_fg}). Vendeu {quantidade_ajustada} ETH a {preco_atual} USDT")
                    preco_ultima_compra = None
                else:
                    print("[SIMULAÇÃO] Saldo de ETH insuficiente para vender.")
            else:
                print(f"[SIMULAÇÃO] Não vendeu: Preço atual ({preco_atual:.2f}) não é maior que o preço de compra ({preco_ultima_compra:.2f})")

while True:
    dados_atualizados = pegando_dados(codigo=codigo_operado, intervalo=periodo_candle)
    estrategia_trade(dados_atualizados, codigo_ativo=codigo_operado, ativo_operado=ativo_operado, quantidade=quantidade)
    print("Aguardando próximo candle...")
    time.sleep(60) 