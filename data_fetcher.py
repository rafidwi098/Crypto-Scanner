import pandas as pd
import requests
import numpy as np
from datetime import datetime, timedelta
import time

class CoinGeckoFetcher:
    """Fetch cryptocurrency data dari CoinGecko API (No Restrictions)"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # Mapping trading pairs ke CoinGecko coin IDs
    COIN_IDS = {
        'BTC/USDT': 'bitcoin',
        'ETH/USDT': 'ethereum',
        'SOL/USDT': 'solana',
        'XRP/USDT': 'ripple',
        'ADA/USDT': 'cardano',
        'BNB/USDT': 'binancecoin',
        'DOGE/USDT': 'dogecoin',
        'MATIC/USDT': 'matic-network',
        'AVAX/USDT': 'avalanche-2',
        'DOT/USDT': 'polkadot',
    }
    
    @staticmethod
    def fetch_ohlcv(symbol: str, days: int = 200):
        """
        Fetch OHLCV data dari CoinGecko
        
        Args:
            symbol: Trading pair (contoh: 'BTC/USDT')
            days: Jumlah hari historical data
        
        Returns:
            DataFrame dengan columns: open, high, low, close, volume
        """
        try:
            coin_id = CoinGeckoFetcher.COIN_IDS.get(symbol)
            if not coin_id:
                raise ValueError(f"❌ Symbol {symbol} tidak tersupport di CoinGecko")
            
            print(f"📡 Fetching {symbol} ({coin_id}) dari CoinGecko...")
            
            # API endpoint untuk market data
            url = f"{CoinGeckoFetcher.BASE_URL}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'daily'
            }
            
            # Fetch data
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract data
            prices = data.get('prices', [])
            volumes = data.get('total_volumes', [])
            market_caps = data.get('market_caps', [])
            
            if not prices:
                raise ValueError("❌ No data returned dari CoinGecko")
            
            # Create DataFrame dengan OHLCV
            df_list = []
            
            for i in range(len(prices) - 1):
                timestamp_ms, price = prices[i]
                next_price = prices[i + 1][1] if i + 1 < len(prices) else price
                volume = volumes[i][1] if i < len(volumes) else 0
                
                # Convert timestamp
                dt = datetime.fromtimestamp(timestamp_ms / 1000)
                
                # CoinGecko hanya sediakan close price, jadi kita approximate:
                # High = close * 1.015 (assume 1.5% variation)
                # Low = close * 0.985
                # Open = average dari 2 consecutive closes
                open_price = (price + (prices[i-1][1] if i > 0 else price)) / 2
                
                df_list.append({
                    'timestamp': dt,
                    'open': float(open_price),
                    'high': float(price * 1.02),    # Approximate high
                    'low': float(price * 0.98),     # Approximate low
                    'close': float(price),
                    'volume': float(volume)
                })
            
            # Create DataFrame
            df = pd.DataFrame(df_list)
            df.set_index('timestamp', inplace=True)
            
            print(f"✅ Berhasil fetch {len(df)} candles untuk {symbol}")
            return df
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {e}")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    @staticmethod
    def get_current_price(symbol: str) -> float:
        """Get harga terbaru cryptocurrency"""
        try:
            coin_id = CoinGeckoFetcher.COIN_IDS.get(symbol)
            if not coin_id:
                return None
            
            url = f"{CoinGeckoFetcher.BASE_URL}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return float(data[coin_id]['usd'])
        
        except Exception as e:
            print(f"❌ Error getting current price: {e}")
            return None
    
    @staticmethod
    def get_market_data(symbol: str) -> dict:
        """Get market info (market cap, volume, dll)"""
        try:
            coin_id = CoinGeckoFetcher.COIN_IDS.get(symbol)
            if not coin_id:
                return None
            
            url = f"{CoinGeckoFetcher.BASE_URL}/coins/{coin_id}"
            params = {
                'localization': 'false',
                'market_data': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            market_data = data.get('market_data', {})
            
            return {
                'current_price': market_data.get('current_price', {}).get('usd'),
                'market_cap': market_data.get('market_cap', {}).get('usd'),
                'total_volume': market_data.get('total_volume', {}).get('usd'),
                'high_24h': market_data.get('high_24h', {}).get('usd'),
                'low_24h': market_data.get('low_24h', {}).get('usd'),
                'price_change_24h': market_data.get('price_change_percentage_24h'),
                'circulating_supply': market_data.get('circulating_supply'),
            }
        
        except Exception as e:
            print(f"❌ Error getting market data: {e}")
            return None
