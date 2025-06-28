import pandas as pd
import os
import time
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv
import math
import csv
from datetime import datetime
from pandas_ta import rsi, macd
import requests

load_dotenv()

api_key = os.getenv("KEY_BINANCE")
secret_key = os.getenv("SECRET_BINANCE")
lucro_minimo = float(os.getenv("PROFITABILITY", "0.02"))  # Take profit padrão 2%
stop_loss = 0.03  # Stop loss agora é 3%

cliente_binance = Client(api_key, secret_key)

codigo_operado = "ETHUSDT"
ativo_operado = "ETH"
periodo_candle = Client.KLINE_INTERVAL_1MINUTE
quantidade = 0.015
modo_simulacao = False  # Opera com dinheiro real
preco_ultima_compra = None
ordem_aberta = False

# Função para registrar operações em CSV (opcional, para histórico)
def registrar_operacao(tipo, quantidade, preco):
    with open('operacoes_real_rsi.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), tipo, quantidade, preco
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
    global preco_ultima_compra, ordem_aberta
    if dados is None:
        print("Dados não disponíveis para estratégia.")
        return
    dados['RSI'] = rsi(dados['fechamento'], length=14)
    macd_result = macd(dados['fechamento'], fast=12, slow=26, signal=9)
    dados['MACD'] = macd_result['MACD_12_26_9']
    dados['MACDsinal'] = macd_result['MACDs_12_26_9']
    rsi_atual = dados['RSI'].iloc[-1]
    macd_atual = dados['MACD'].iloc[-1]
    macd_sinal_atual = dados['MACDsinal'].iloc[-1]
    macd_anterior = dados['MACD'].iloc[-2]
    macd_sinal_anterior = dados['MACDsinal'].iloc[-2]
    preco_atual = dados["fechamento"].iloc[-1]
    min_qty, step_size = pegar_step_min_qty(codigo_ativo)
    print(f"RSI: {rsi_atual:.2f} | MACD: {macd_atual:.6f} | Sinal MACD: {macd_sinal_atual:.6f} | Preço: {preco_atual}")

    # COMPRA: RSI < 35 e MACD cruza para cima da Signal Line
    cruzamento_macd_compra = macd_anterior < macd_sinal_anterior and macd_atual > macd_sinal_atual
    if not ordem_aberta and rsi_atual < 35 and cruzamento_macd_compra:
        quantidade_ajustada = max(arredondar_quantidade(quantidade, step_size), min_qty)
        try:
            order = cliente_binance.create_order(
                symbol=codigo_ativo,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantidade_ajustada
            )
            preco_ultima_compra = float(order['fills'][0]['price'])
            ordem_aberta = True
            registrar_operacao('COMPRA', quantidade_ajustada, preco_ultima_compra)
            print(f"[REAL] COMPRA: RSI={rsi_atual:.2f}, MACD cruzou para cima. Comprou {quantidade_ajustada} ETH a {preco_ultima_compra} USDT")
        except Exception as e:
            print(f"Erro ao comprar: {e}")

    # TAKE PROFIT
    if ordem_aberta and preco_ultima_compra and preco_atual >= preco_ultima_compra * (1 + lucro_minimo):
        quantidade_ajustada = max(arredondar_quantidade(quantidade, step_size), min_qty)
        try:
            order = cliente_binance.create_order(
                symbol=codigo_ativo,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantidade_ajustada
            )
            preco_venda = float(order['fills'][0]['price'])
            registrar_operacao('VENDA_TAKE_PROFIT', quantidade_ajustada, preco_venda)
            print(f"[REAL] VENDA (TAKE PROFIT): Vendeu {quantidade_ajustada} ETH a {preco_venda} USDT (lucro atingido)")
            ordem_aberta = False
            preco_ultima_compra = None
        except Exception as e:
            print(f"Erro ao vender (take profit): {e}")

    # STOP LOSS
    if ordem_aberta and preco_ultima_compra and preco_atual <= preco_ultima_compra * (1 - stop_loss):
        quantidade_ajustada = max(arredondar_quantidade(quantidade, step_size), min_qty)
        try:
            order = cliente_binance.create_order(
                symbol=codigo_ativo,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantidade_ajustada
            )
            preco_venda = float(order['fills'][0]['price'])
            registrar_operacao('VENDA_STOP_LOSS', quantidade_ajustada, preco_venda)
            print(f"[REAL] VENDA (STOP LOSS): Vendeu {quantidade_ajustada} ETH a {preco_venda} USDT (stop atingido)")
            ordem_aberta = False
            preco_ultima_compra = None
        except Exception as e:
            print(f"Erro ao vender (stop loss): {e}")

    # VENDA: RSI > 65 e MACD cruza para baixo da Signal Line
    cruzamento_macd_venda = macd_anterior > macd_sinal_anterior and macd_atual < macd_sinal_atual
    if ordem_aberta and rsi_atual > 65 and cruzamento_macd_venda:
        quantidade_ajustada = max(arredondar_quantidade(quantidade, step_size), min_qty)
        try:
            order = cliente_binance.create_order(
                symbol=codigo_ativo,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantidade_ajustada
            )
            preco_venda = float(order['fills'][0]['price'])
            registrar_operacao('VENDA', quantidade_ajustada, preco_venda)
            print(f"[REAL] VENDA: RSI={rsi_atual:.2f}, MACD cruzou para baixo. Vendeu {quantidade_ajustada} ETH a {preco_venda} USDT")
            ordem_aberta = False
            preco_ultima_compra = None
        except Exception as e:
            print(f"Erro ao vender: {e}")

while True:
    dados_atualizados = pegando_dados(codigo=codigo_operado, intervalo=periodo_candle)
    estrategia_trade(dados_atualizados, codigo_ativo=codigo_operado, ativo_operado=ativo_operado, quantidade=quantidade)
    print("Aguardando próximo candle...")
    time.sleep(60) 