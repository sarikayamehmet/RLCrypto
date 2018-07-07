# -*- coding:utf-8 -*-
import time

import numpy as np
import pandas as pd

from utils.HuobiServices import *

lmap = lambda func, it: list(map(lambda x: func(x), it))
lfilter = lambda func, it: list(filter(lambda x: func(x), it))


def kline(asset, base_currency='btc', interval='60min', count=2000):
    s = get_kline('{0}{1}'.format(asset, base_currency), interval, count)
    if s is None: return None
    s = s['data']
    s = pd.DataFrame(s)[::-1]
    if s.shape[0] < count:
        return None
    s.index = pd.DatetimeIndex(s['id'].apply(lambda x: datetime.datetime.utcfromtimestamp(x) + datetime.timedelta(hours=8)))
    s = s.drop('id', axis=1)
    s['avg'] = (np.mean(s[['open', 'high', 'low', 'close']], axis=1))
    s['diff'] = np.log(s['close'] / s['close'].shift(1)).fillna(0)
    return s


def klines(assets, base_currency='btc', interval='60min', count=2000):
    return lfilter(lambda x: x[1] is not None, lmap(lambda x: (x, kline(x, base_currency=base_currency, interval=interval, count=count)), assets))


def re_balance(target_percent, symbol, asset, portfolio, base_currency, order_type='limit', price_discount=0, amount_discount=0.05, debug=True, max_asset_percent=1.0):
    portfolio = portfolio + [base_currency]
    current_order_info = orders_list(symbol=symbol, states='submitted')['data']
    # print('current order info', current_order_info)
    if len(current_order_info) > 0:
        for order in current_order_info:
            order_id = order['id']
            print('cancel previous order:', order)
            if not debug:
                cancel_order(order_id=order_id)
            else:
                print('cancel order debugging')
    
    balance_info = get_balance()
    asset_info = lfilter(lambda x: x['base-currency'] == asset and x['quote-currency'] == 'btc', get_symbols()['data'])
    amount_precision = asset_info[0]['amount-precision']
    price_precision = asset_info[0]['price-precision']
    
    market_price = np.inf
    limit_buy_price = np.inf
    limit_sell_price = np.inf
    
    portfolio_value = 0
    base_balance = 0
    asset_balance = 0
    for currency in portfolio:
        balance = list(filter(lambda x: x['currency'] == currency and x['type'] == 'trade', balance_info['data']['list']))
        if len(balance) > 0:
            if currency == base_currency:
                base_balance = float(balance[0]['balance'])
                portfolio_value += base_balance
            else:
                ticker = get_ticker(currency + base_currency)['tick']
                price = ticker['close']
                asset_value = float(balance[0]['balance']) * price
                portfolio_value += asset_value
                if currency == asset:
                    asset_balance = float(balance[0]['balance'])
                    market_price = round(ticker['close'], price_precision)
                    limit_buy_price = round(float(ticker['bid'][0]) * (1 - price_discount), price_precision)
                    limit_sell_price = round(float(ticker['ask'][0]) * (1 + price_discount), price_precision)
    
    max_asset_value = portfolio_value * max_asset_percent if base_balance > portfolio_value * max_asset_percent else base_balance
    max_asset_balance = max_asset_value / market_price
    max_buy_amount = max_asset_balance - asset_balance
    holding_percent = asset_balance / max_asset_balance
    if target_percent > 0.9:
        target_percent = 1
    elif target_percent < 0.1:
        target_percent = 0
    trade_percent = target_percent - holding_percent
    print('holding: {0}% number:{1}'.format(holding_percent, asset_balance))
    if trade_percent > 0.1:
        target_buy_amount = max_asset_balance * trade_percent * (1 - amount_discount)
        if target_buy_amount > max_buy_amount:
            target_buy_amount = max_buy_amount
        target_buy_amount = round(target_buy_amount, amount_precision)
        if amount_precision == 0:
            target_buy_amount = int(target_buy_amount)
        if order_type == 'limit':
            print('send limit-buy order: buy {0}, target holding {1}%, at price {2} on {3}'.format(target_buy_amount, target_percent * 100, limit_buy_price, symbol))
        else:
            print('send market-buy order: buy {0}, target holding {1}%, at price {2} on {3}'.format(target_buy_amount, target_percent * 100, market_price, symbol))
        if not debug:
            if order_type == 'limit':
                order = send_order(symbol=symbol, source='api', amount=target_buy_amount, _type='buy-limit', price=limit_buy_price)
                print(order)
                return order['data']
            else:
                order = send_order(symbol=symbol, source='api', amount=target_buy_amount, _type='buy-market')
                print(order)
                return order['data']
        else:
            print('debugging')
            return 'debugging'
    elif trade_percent < -0.01:
        target_sell_amount = max_asset_balance * np.abs(trade_percent) * (1 - amount_discount)
        if target_sell_amount > asset_balance:
            target_sell_amount = asset_balance
        target_sell_amount = round(target_sell_amount, amount_precision)
        if amount_precision == 0:
            target_sell_amount = int(target_sell_amount)
        if order_type == 'limit':
            print('send market-sell order: sell {0}, target holding {1}%, at price {2} on {3}'.format(target_sell_amount, target_percent * 100, limit_sell_price, symbol))
        else:
            print('send market-sell order: sell {0}, target holding {1}%, at price {2} on {3}'.format(target_sell_amount, target_percent * 100, market_price, symbol))
        if not debug:
            if order_type == 'limit':
                order = send_order(symbol=symbol, source='api', amount=target_sell_amount, _type='sell-limit', price=limit_sell_price)
                print(order)
                return order['data']
            else:
                order = send_order(symbol=symbol, source='api', amount=target_sell_amount, _type='sell-market')
                print(order)
                return order['data']
        else:
            print('debugging')
            return 'debugging'