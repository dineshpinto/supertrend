from bfxapi.client import BfxRest


class BitfinexAPI(BfxRest):
    def __init__(self):
        super().__init__(
            API_KEY=None,
            API_SECRET=None,
            host='https://api-pub.bitfinex.com/v2',
            logLevel='INFO',
            parse_float=float,
        )

    async def get_funding_stats(self, symbol: str) -> list:
        funding_stats = await self.get_public_funding_stats(f"f{symbol}")
        return funding_stats[0]

    async def get_funding_rate(self, symbol: str) -> float:
        funding_stats = await self.get_public_funding_stats(f"f{symbol}")
        funding_stats = funding_stats[0]
        timestamp, frr, funding_amount, funding_amount_used = funding_stats[0], funding_stats[3], funding_stats[7], \
                                                              funding_stats[8]

        if funding_amount > funding_amount_used:
            multiplier = -1
        else:
            multiplier = 1

        daily_funding_rate_pct = frr * 365 * 100 * multiplier
        return daily_funding_rate_pct


if __name__ == "__main__":
    bf_api = BitfinexAPI()

    funding_rate = await bf_api.get_funding_rate("BTC")
    print(funding_rate)
