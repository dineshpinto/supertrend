import datetime
import hmac
import time
import urllib.parse
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
from ciso8601 import parse_datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta
from requests import Request, Session, Response


def str_to_datetime(str_days_ago: str) -> datetime.datetime:
    now = datetime.datetime.now()
    split_string = str_days_ago.split()
    if len(split_string) == 1 and split_string[0].lower() == 'today':
        return now
    elif len(split_string) == 1 and split_string[0].lower() == 'yesterday':
        date = now - relativedelta(days=1)
        return date
    elif split_string[1].lower() in ['hour', 'hours', 'hr', 'hrs', 'h']:
        date = datetime.datetime.now() - relativedelta(hours=int(split_string[0]))
        return date
    elif split_string[1].lower() in ['day', 'days', 'd']:
        date = now - relativedelta(days=int(split_string[0]))
        return date
    elif split_string[1].lower() in ['wk', 'wks', 'week', 'weeks', 'w']:
        date = now - relativedelta(weeks=int(split_string[0]))
        return date
    elif split_string[1].lower() in ['mon', 'mons', 'month', 'months', 'm']:
        date = now - relativedelta(months=int(split_string[0]))
        return date
    elif split_string[1].lower() in ['yrs', 'yr', 'years', 'year', 'y']:
        date = now - relativedelta(years=int(split_string[0]))
        return date
    else:
        raise ValueError("Wrong Argument format")


def interval_to_seconds_converter(interval: str) -> int:
    value = int(interval[:-1])
    if interval.endswith("s"):
        return int(value)
    elif interval.endswith("m"):
        return int(value * 60)
    elif interval.endswith("h"):
        return int(value * 3600)
    elif interval.endswith("d"):
        return int(value * 216000)
    else:
        raise ValueError("Invalid interval format: Use 's', 'm', 'h' or 'd'")


class FtxClient:
    _ENDPOINT = 'https://ftx.com/api/'

    def __init__(self, api_key=None, api_secret=None, subaccount_name=None) -> None:
        self._session = Session()
        self._api_key = api_key
        self._api_secret = api_secret
        self._subaccount_name = subaccount_name

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('GET', path, params=params)

    def _post(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('POST', path, json=params)

    def _delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('DELETE', path, json=params)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        request = Request(method, self._ENDPOINT + path, **kwargs)
        self._sign_request(request)
        response = self._session.send(request.prepare())
        return self._process_response(response)

    def _sign_request(self, request: Request) -> None:
        ts = int(time.time() * 1000)
        prepared = request.prepare()
        signature_payload = f'{ts}{prepared.method}{prepared.path_url}'.encode()
        if prepared.body:
            signature_payload += prepared.body
        signature = hmac.new(self._api_secret.encode(), signature_payload, 'sha256').hexdigest()
        request.headers['FTX-KEY'] = self._api_key
        request.headers['FTX-SIGN'] = signature
        request.headers['FTX-TS'] = str(ts)
        if self._subaccount_name:
            request.headers['FTX-SUBACCOUNT'] = urllib.parse.quote(self._subaccount_name)

    @staticmethod
    def _process_response(response: Response) -> Any:
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise
        else:
            if not data['success']:
                raise Exception(data['error'])
            return data['result']

    def list_futures(self) -> List[dict]:
        return self._get('futures')

    def list_markets(self) -> List[dict]:
        return self._get('markets')

    def get_orderbook(self, market: str, depth: int = None) -> dict:
        return self._get(f'markets/{market}/orderbook', {'depth': depth})

    def get_trades(self, market: str) -> dict:
        return self._get(f'markets/{market}/trades')

    def get_account_info(self) -> dict:
        return self._get(f'account')

    def get_historical_prices(self, market: str, resolution: int, start_time: int) -> dict:
        return self._get(f'markets/{market}/candles', {'resolution': resolution, "start_time": start_time})

    def get_open_orders(self, market: str = None) -> List[dict]:
        return self._get(f'orders', {'market': market})

    def get_order_history(self, market: str = None, side: str = None, order_type: str = None, start_time: float = None,
                          end_time: float = None) -> List[dict]:
        return self._get(f'orders/history',
                         {'market': market, 'side': side, 'orderType': order_type, 'start_time': start_time,
                          'end_time': end_time})

    def get_conditional_order_history(self, market: str = None, side: str = None, type: str = None,
                                      order_type: str = None, start_time: float = None, end_time: float = None) \
            -> List[dict]:
        return self._get(f'conditional_orders/history',
                         {'market': market, 'side': side, 'type': type, 'orderType': order_type,
                          'start_time': start_time, 'end_time': end_time})

    def modify_order(
            self, existing_order_id: Optional[str] = None,
            existing_client_order_id: Optional[str] = None, price: Optional[float] = None,
            size: Optional[float] = None, client_order_id: Optional[str] = None,
    ) -> dict:
        assert (existing_order_id is None) ^ (existing_client_order_id is None), \
            'Must supply exactly one ID for the order to modify'
        assert (price is None) or (size is None), 'Must modify price or size of order'
        path = f'orders/{existing_order_id}/modify' if existing_order_id is not None else \
            f'orders/by_client_id/{existing_client_order_id}/modify'
        return self._post(path, {
            **({'size': size} if size is not None else {}),
            **({'price': price} if price is not None else {}),
            **({'clientId': client_order_id} if client_order_id is not None else {}),
        })

    def get_conditional_orders(self, market: str = None) -> List[dict]:
        return self._get(f'conditional_orders', {'market': market})

    def place_order(self, market: str, side: str, price: float, size: float, type: str = 'limit',
                    reduce_only: bool = False, ioc: bool = False, post_only: bool = False,
                    client_id: str = None) -> dict:
        return self._post('orders', {'market': market,
                                     'side': side,
                                     'price': price,
                                     'size': size,
                                     'type': type,
                                     'reduceOnly': reduce_only,
                                     'ioc': ioc,
                                     'postOnly': post_only,
                                     'clientId': client_id,
                                     })

    def place_conditional_order(
            self, market: str, side: str, size: float, type: str = 'stop',
            limit_price: float = None, reduce_only: bool = False, cancel: bool = True,
            trigger_price: float = None, trail_value: float = None
    ) -> dict:
        """
        To send a Stop Market order, set type='stop' and supply a trigger_price
        To send a Stop Limit order, also supply a limit_price
        To send a Take Profit Market order, set type='trailing_stop' and supply a trigger_price
        To send a Trailing Stop order, set type='trailing_stop' and supply a trail_value
        """
        assert type in ('stop', 'take_profit', 'trailing_stop')
        assert type not in ('stop', 'take_profit') or trigger_price is not None, \
            'Need trigger prices for stop losses and take profits'
        assert type not in ('trailing_stop',) or (trigger_price is None and trail_value is not None), \
            'Trailing stops need a trail value and cannot take a trigger price'

        return self._post('conditional_orders',
                          {'market': market, 'side': side, 'triggerPrice': trigger_price,
                           'size': size, 'reduceOnly': reduce_only, 'type': 'stop',
                           'cancelLimitOnTrigger': cancel, 'orderPrice': limit_price})

    def cancel_order(self, order_id: str) -> dict:
        return self._delete(f'orders/{order_id}')

    def cancel_orders(self, market_name: str = None, conditional_orders: bool = False,
                      limit_orders: bool = False) -> dict:
        return self._delete(f'orders', {'market': market_name,
                                        'conditionalOrdersOnly': conditional_orders,
                                        'limitOrdersOnly': limit_orders,
                                        })

    def get_fills(self) -> List[dict]:
        return self._get(f'fills')

    def get_balances(self) -> List[dict]:
        return self._get('wallet/balances')

    def get_deposit_address(self, ticker: str) -> dict:
        return self._get(f'wallet/deposit_address/{ticker}')

    def get_positions(self, show_avg_price: bool = False) -> List[dict]:
        return self._get('positions', {'showAvgPrice': show_avg_price})

    def get_position(self, name: str, show_avg_price: bool = False) -> dict:
        return next(filter(lambda x: x['future'] == name, self.get_positions(show_avg_price)), None)

    def get_all_trades(self, market: str, start_time: float = None, end_time: float = None) -> List:
        ids = set()
        limit = 100
        results = []
        while True:
            response = self._get(f'markets/{market}/trades', {
                'end_time': end_time,
                'start_time': start_time,
            })
            deduped_trades = [r for r in response if r['id'] not in ids]
            results.extend(deduped_trades)
            ids |= {r['id'] for r in deduped_trades}
            print(f'Adding {len(response)} trades with end time {end_time}')
            if len(response) == 0:
                break
            end_time = min(parse_datetime(t['time']) for t in response).timestamp()
            if len(response) < limit:
                break
        return results

    # Additional functions

    def get_historical_market_data(self, market: str, interval: str, start_time: str) -> pd.DataFrame:
        interval_to_seconds = {"15s": 15, "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}

        if interval in interval_to_seconds:
            resolution = interval_to_seconds[interval]
        else:
            raise ValueError(f"Use a valid time interval: {interval_to_seconds.keys()}")

        start_time = int(datetime.datetime.timestamp(str_to_datetime(start_time)))

        data = self.get_historical_prices(market, resolution, start_time)

        df = pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close', 'volume'])

        for idx, item in enumerate(data):
            df.loc[idx] = [parser.parse(item["startTime"]), item["open"], item["high"], item["low"], item["close"],
                           item["volume"]]

        df = df.set_index("time")
        return df

    def check_open_position(self, market: str) -> dict:
        position = self.get_position(market)
        if position is not None:
            if position["size"] != 0:
                return position
        return {}

    def modify_trigger_order(self, order_id: str, size: float, trigger_price: float):
        path = f"conditional_orders/{order_id}/modify"
        return self._post(path, {
            "triggerPrice": trigger_price,
            "size": size
        })

    def update_stop_loss(self, market: str, stop_loss: float) -> float:
        for trigger_order in self.get_conditional_orders(market):
            if trigger_order["type"] == "stop":
                if trigger_order["triggerPrice"] != stop_loss:
                    response = self.modify_trigger_order(
                        order_id=str(trigger_order["id"]),
                        size=trigger_order["size"],
                        trigger_price=stop_loss
                    )
                    return response["triggerPrice"]
        return 0

    def market_close_and_cancel_orders(self, market: str, side: str, size: float) -> Tuple[bool, dict]:
        response = self.place_order(market, side=side, size=size, type="market", price=0)
        self.cancel_orders(market, conditional_orders=True)

        # Wait until position is closed
        idx = 0
        while self.check_open_position(market):
            time.sleep(2)
            idx += 1
            if idx == 5:
                return False, response
        return True, response

    def get_coin_balance(self, coin: str = "USD") -> float:
        coin_balance = 0
        for balance in self.get_balances():
            if balance["coin"] == coin:
                coin_balance = float(balance["free"])
        return coin_balance

    def get_size_precision(self, market: str) -> float:
        order_book = self.get_orderbook(market, depth=1)
        return len(str(order_book["asks"][0][1]).split(".")[1])

    def get_price_precision(self, market: str) -> float:
        order_book = self.get_orderbook(market, depth=1)
        return len(str(order_book["asks"][0][0]).split(".")[1])

    def get_latest_price(self, market: str, side: str) -> float:
        order_book = self.get_orderbook(market, depth=1)
        if side == "sell":
            return float(order_book["asks"][0][0])
        elif side == "buy":
            return float(order_book["bids"][0][0])
        return 0

    def generate_order_size(self, price: float, market: str, percent: int) -> float:
        usd_balance = self.get_coin_balance(coin="USD")
        leverage = self.get_account_info()["leverage"]
        usable_usd_balance = usd_balance * percent / 100 * leverage
        size_precision = self.get_size_precision(market)
        size = round(usable_usd_balance / float(price), size_precision)
        return size

    def get_stop_loss_price(self, price: float, percent: float, side: str, market: str):
        if side == "sell":
            sl_price = price + price * percent / 100
        elif side == "buy":
            sl_price = price - price * percent / 100
        return round(sl_price, self.get_price_precision(market))

    def get_take_profit_price(self, price: float, percent: float, side: str, market: str):
        if side == "sell":
            tp_price = price - price * percent / 100
        elif side == "buy":
            tp_price = price + price * percent / 100
        return round(tp_price, self.get_price_precision(market))

    @staticmethod
    def _inverse_position(side: str) -> str:
        if side == "buy":
            return "sell"
        elif side == "sell":
            return "buy"

    def generate_order(self, order: dict, account_percent: int = 10, stop_loss_percent: float = 5) \
            -> Tuple[dict, dict]:
        size = self.generate_order_size(order["entry"], order["market"], percent=account_percent)
        price = self.get_latest_price(order["market"], order["side"])
        stop_loss_price = self.get_stop_loss_price(price, stop_loss_percent, order["side"], order["market"])

        order_to_place = {
            "market": order["market"],
            "side": order["side"],
            "price": price,
            "size": size,
            "type": "limit",
        }

        stop_loss_order = {
            "market": order["market"],
            "side": self._inverse_position(order["side"]),
            "size": size,
            "type": "stop",
            "reduce_only": True,
            "trigger_price": stop_loss_price,
        }

        return order_to_place, stop_loss_order
