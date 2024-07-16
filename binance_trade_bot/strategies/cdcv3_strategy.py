import random
import sys
import numpy as np
import pandas_ta as ta
from datetime import timedelta

from binance_trade_bot.auto_trader import AutoTrader
from binance_trade_bot.models.coin import Coin
from binance_trade_bot.strategies.base.technical_indicator_strategy import TAStrategy


class Strategy(TAStrategy):
    def initialize(self):
        super().initialize()
        self.config_fast_ema = self.config.STRATEGY_CONFIG["fast_ema_period"]
        self.config_slow_ema = self.config.STRATEGY_CONFIG["slow_ema_period"]

        self.start_delay_seconds = self.config.STRATEGY_CONFIG["start_delay_seconds"]

        self.prev_current_date = {}
        for coin in self.target_coins:
            self.prev_current_date[coin.symbol] = self.get_current_date()

    def ema(self, source, timeperiod):
        alpha = 2 / (timeperiod + 1)
        prev_ema = source[0]

        for price in source[1:]:
            new_ema = alpha * price + (1 - alpha) * prev_ema
            prev_ema = new_ema

        return new_ema

    def get_coin_ema_in_range(self, pair_symbol, start_date, end_date, range):
        prev_prices = self.get_prev_prices_in_range(
            pair_symbol, start_date, end_date, range
        )
        # print("get_coin_ema_in_range >> prev_prices_raw:", prev_prices_raw, ", start_date:", start_date, ", end_date:", end_date)
        if prev_prices is None:
            return None, None

        ema = self.ema(prev_prices, timeperiod=range)

        if ema is None:
            return None, None

        # print(end_date, "ema:", ema)
        return ema, prev_prices

    def get_coin_fast_slow_ema(self, symbol):
        current_date = self.get_current_date()
        if self.prev_current_date[symbol] == current_date:
            return None, None, None

        self.prev_current_date[symbol] = current_date
        prev_date_fast = current_date - timedelta(
            minutes=self.config_fast_ema * self.multiplier * 3
        )
        prev_date_slow = current_date - timedelta(
            minutes=self.config_slow_ema * self.multiplier * 3
        )

        # self.logger.info(f"get_coin_fast_slow_ema >> current_date: {current_date} prev_date_fast: {prev_date_fast}, prev_date_slow: {prev_date_slow}, fast_ema: {self.config_fast_ema}, slow_ema: {self.config_slow_ema}")

        fast_ema, prev_prices_raw_fast = self.get_coin_ema_in_range(
            symbol + self.config.BRIDGE_SYMBOL,
            prev_date_fast,
            current_date,
            self.config_fast_ema,
        )
        if prev_prices_raw_fast is None or len(prev_prices_raw_fast) == 0:
            return None, None, None

        slow_ema, prev_prices_raw_slow = self.get_coin_ema_in_range(
            symbol + self.config.BRIDGE_SYMBOL,
            prev_date_slow,
            current_date,
            self.config_slow_ema,
        )
        if prev_prices_raw_slow is None or len(prev_prices_raw_slow) == 0:
            return None, None, None

        return fast_ema, slow_ema, prev_prices_raw_slow

    def get_signal(self, coim_symbol):
        fast_ema, slow_ema, prices = self.get_coin_fast_slow_ema(coim_symbol)
        if fast_ema is None or slow_ema is None or prices is None:
            return None, None
        # print(self.manager.now(), ", current_price:", current_price, ", fast_ema:", fast_ema, ", slow_ema:", slow_ema, "prev_fast_ema:", prev_fast_ema, ", prev_slow_ema:", prev_slow_ema)

        current_price = prices[:-1][-1]

        bull = fast_ema > slow_ema
        bear = fast_ema < slow_ema

        buy = bull and current_price > fast_ema
        sell = bear and current_price < fast_ema

        if buy:
            signal = "buy"
        elif sell:
            signal = "sell"
        else:
            signal = "-"

        # print(self.manager.now(), ", signal:", signal, ", fast_ema:", fast_ema, ", slow_ema:", slow_ema, ", current_price:", current_price)

        return signal, {
            "fast_ema": fast_ema,
            "slow_ema": slow_ema,
        }  # , "prices": raw_prices
