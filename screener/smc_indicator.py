import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SMCIndicator:
    """
    Smart Money Concept (SMC) Indicator
    Detects: BOS, CHOCH, Order Blocks, FVG, Liquidity Sweeps
    """
    
    def __init__(self, lookback: int = 200, min_swing_size: float = 0.005):
        """
        Initialize SMC Indicator
        
        Args:
            lookback: Number of candles to analyze
            min_swing_size: Minimum move size as percentage
        """
        self.lookback = lookback
        self.min_swing_size = min_swing_size
        self.df = None
        self.analysis_result = {}
    
    def analyze(self, candles_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Complete SMC analysis on candle data
        
        Args:
            candles_df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
        
        Returns:
            Dictionary with all SMC signals
        """
        self.df = candles_df.copy()
        
        if len(self.df) < 50:
            logger.warning("Not enough candle data for analysis")
            return self._empty_result()
        
        # Run all analyses
        swing_highs = self._find_swing_highs()
        swing_lows = self._find_swing_lows()
        bos = self.detect_bos(swing_highs, swing_lows)
        choch = self.detect_choch()
        order_blocks = self.identify_order_blocks()
        fvgs = self.detect_fvg()
        sweeps = self.detect_liquidity_sweeps()
        
        self.analysis_result = {
            'bos': bos,
            'choch': choch,
            'order_blocks': order_blocks,
            'fvgs': fvgs,
            'sweeps': sweeps,
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'timestamp': datetime.now()
        }
        
        return self.analysis_result
    
    def _find_swing_highs(self, period: int = 5) -> List[Dict]:
        """Find swing highs in price action"""
        swing_highs = []
        highs = self.df['high'].values
        closes = self.df['close'].values
        
        for i in range(period, len(highs) - period):
            window_highs = highs[i-period:i+period+1]
            
            if highs[i] == window_highs.max():
                swing_highs.append({
                    'index': i,
                    'price': float(highs[i]),
                    'close': float(closes[i]),
                    'timestamp': self.df.index[i],
                    'type': 'SWING_HIGH'
                })
        
        return swing_highs
    
    def _find_swing_lows(self, period: int = 5) -> List[Dict]:
        """Find swing lows in price action"""
        swing_lows = []
        lows = self.df['low'].values
        closes = self.df['close'].values
        
        for i in range(period, len(lows) - period):
            window_lows = lows[i-period:i+period+1]
            
            if lows[i] == window_lows.min():
                swing_lows.append({
                    'index': i,
                    'price': float(lows[i]),
                    'close': float(closes[i]),
                    'timestamp': self.df.index[i],
                    'type': 'SWING_LOW'
                })
        
        return swing_lows
    
    def detect_bos(self, swing_highs: List[Dict], 
                   swing_lows: List[Dict]) -> List[Dict]:
        """
        Break of Structure (BOS) Detection
        """
        bos_signals = []
        closes = self.df['close'].values
        highs = self.df['high'].values
        lows = self.df['low'].values
        volumes = self.df['volume'].values
        
        window = 20
        avg_volume = np.mean(volumes[-window:]) if window <= len(volumes) else np.mean(volumes)
        
        for i in range(len(closes)):
            volume_ratio = volumes[i] / avg_volume if avg_volume > 0 else 0
            
            # Bullish BOS
            if swing_highs:
                last_swing_high = swing_highs[-1]['price']
                
                if closes[i] > last_swing_high and volume_ratio > 1.2:
                    swing_indices = [sh['index'] for sh in swing_highs]
                    
                    if max(swing_indices) < i:
                        strength = ((closes[i] - last_swing_high) / last_swing_high) * 100
                        
                        bos_signals.append({
                            'type': 'BULLISH_BOS',
                            'level': float(last_swing_high),
                            'index': i,
                            'timestamp': self.df.index[i],
                            'close': float(closes[i]),
                            'high': float(highs[i]),
                            'low': float(lows[i]),
                            'strength_pct': float(strength),
                            'volume_ratio': float(volume_ratio),
                            'signal_strength': self._classify_strength(strength, volume_ratio),
                            'confirmation': 'STRONG' if volume_ratio > 1.5 else 'MODERATE'
                        })
            
            # Bearish BOS
            if swing_lows:
                last_swing_low = swing_lows[-1]['price']
                
                if closes[i] < last_swing_low and volume_ratio > 1.2:
                    swing_indices = [sl['index'] for sl in swing_lows]
                    
                    if max(swing_indices) < i:
                        strength = ((last_swing_low - closes[i]) / last_swing_low) * 100
                        
                        bos_signals.append({
                            'type': 'BEARISH_BOS',
                            'level': float(last_swing_low),
                            'index': i,
                            'timestamp': self.df.index[i],
                            'close': float(closes[i]),
                            'high': float(highs[i]),
                            'low': float(lows[i]),
                            'strength_pct': float(strength),
                            'volume_ratio': float(volume_ratio),
                            'signal_strength': self._classify_strength(strength, volume_ratio),
                            'confirmation': 'STRONG' if volume_ratio > 1.5 else 'MODERATE'
                        })
        
        return bos_signals
    
    def detect_choch(self) -> List[Dict]:
        """Change of Character (CHOCH) Detection"""
        choch_points = []
        highs = self.df['high'].values
        lows = self.df['low'].values
        closes = self.df['close'].values
        
        window = 10
        
        if len(highs) < window * 3:
            return choch_points
        
        for i in range(window * 2, len(highs)):
            prev_highs = highs[i-window*2:i-window]
            prev_lows = lows[i-window*2:i-window]
            
            curr_highs = highs[i-window:i]
            curr_lows = lows[i-window:i]
            
            prev_is_uptrend = (len(prev_highs) >= 2 and 
                              prev_highs[-1] > prev_highs[-2] and 
                              prev_lows[-1] > prev_lows[-2])
            
            prev_is_downtrend = (len(prev_highs) >= 2 and
                                prev_highs[-1] < prev_highs[-2] and 
                                prev_lows[-1] < prev_lows[-2])
            
            curr_is_uptrend = (len(curr_highs) >= 2 and
                              curr_highs[-1] > curr_highs[-2] and 
                              curr_lows[-1] > curr_lows[-2])
            
            curr_is_downtrend = (len(curr_highs) >= 2 and
                                curr_highs[-1] < curr_highs[-2] and 
                                curr_lows[-1] < curr_lows[-2])
            
            if prev_is_uptrend and curr_is_downtrend:
                reversal_level = float(curr_highs[-1])
                reversal_strength = self._calculate_choch_strength(prev_lows, curr_lows)
                
                choch_points.append({
                    'type': 'DOWNTREND_CHOCH',
                    'index': i,
                    'timestamp': self.df.index[i],
                    'level': reversal_level,
                    'close': float(closes[i]),
                    'previous_trend': 'UPTREND',
                    'current_trend': 'DOWNTREND',
                    'reversal_strength': float(reversal_strength),
                    'signal_quality': 'STRONG' if reversal_strength > 0.5 else 'MODERATE'
                })
            
            elif prev_is_downtrend and curr_is_uptrend:
                reversal_level = float(curr_lows[-1])
                reversal_strength = self._calculate_choch_strength(prev_highs, curr_highs)
                
                choch_points.append({
                    'type': 'UPTREND_CHOCH',
                    'index': i,
                    'timestamp': self.df.index[i],
                    'level': reversal_level,
                    'close': float(closes[i]),
                    'previous_trend': 'DOWNTREND',
                    'current_trend': 'UPTREND',
                    'reversal_strength': float(reversal_strength),
                    'signal_quality': 'STRONG' if reversal_strength > 0.5 else 'MODERATE'
                })
        
        return choch_points
    
    def identify_order_blocks(self, sensitivity: int = 20) -> List[Dict]:
        """Order Block Identification"""
        order_blocks = []
        closes = self.df['close'].values
        opens = self.df['open'].values
        highs = self.df['high'].values
        lows = self.df['low'].values
        volumes = self.df['volume'].values
        
        if len(volumes) < sensitivity:
            return order_blocks
        
        avg_volume = np.mean(volumes[-sensitivity:])
        volume_threshold = avg_volume * 1.8
        
        for i in range(sensitivity, len(closes)):
            candle_range = highs[i] - lows[i]
            avg_range = np.mean(highs[i-sensitivity:i] - lows[i-sensitivity:i])
            
            body_size = abs(closes[i] - opens[i])
            body_ratio = body_size / candle_range if candle_range > 0 else 0
            
            vol_ratio = volumes[i] / avg_volume if avg_volume > 0 else 0
            
            # ACCUMULATION
            if (volumes[i] > volume_threshold and 
                candle_range < avg_range * 0.8 and 
                closes[i] > opens[i] and
                body_ratio > 0.5):
                
                ob_strength = (vol_ratio * 0.6 + body_ratio * 0.4)
                
                order_blocks.append({
                    'type': 'ACCUMULATION_OB',
                    'index': i,
                    'timestamp': self.df.index[i],
                    'high': float(highs[i]),
                    'low': float(lows[i]),
                    'open': float(opens[i]),
                    'close': float(closes[i]),
                    'volume': float(volumes[i]),
                    'volume_ratio': float(vol_ratio),
                    'candle_range': float(candle_range),
                    'body_size': float(body_size),
                    'body_ratio': float(body_ratio),
                    'strength': float(ob_strength),
                    'quality': 'STRONG' if ob_strength > 0.7 else 'MODERATE',
                    'description': 'Smart money buying zone'
                })
            
            # DISTRIBUTION
            elif (volumes[i] > volume_threshold and 
                  candle_range < avg_range * 0.8 and 
                  closes[i] < opens[i] and
                  body_ratio > 0.5):
                
                ob_strength = (vol_ratio * 0.6 + body_ratio * 0.4)
                
                order_blocks.append({
                    'type': 'DISTRIBUTION_OB',
                    'index': i,
                    'timestamp': self.df.index[i],
                    'high': float(highs[i]),
                    'low': float(lows[i]),
                    'open': float(opens[i]),
                    'close': float(closes[i]),
                    'volume': float(volumes[i]),
                    'volume_ratio': float(vol_ratio),
                    'candle_range': float(candle_range),
                    'body_size': float(body_size),
                    'body_ratio': float(body_ratio),
                    'strength': float(ob_strength),
                    'quality': 'STRONG' if ob_strength > 0.7 else 'MODERATE',
                    'description': 'Smart money selling zone'
                })
        
        return order_blocks
    
    def detect_fvg(self, min_gap_pct: float = 0.1) -> List[Dict]:
        """Fair Value Gap (FVG) Detection"""
        fvgs = []
        highs = self.df['high'].values
        lows = self.df['low'].values
        closes = self.df['close'].values
        
        for i in range(2, len(highs)):
            # Bullish FVG
            if lows[i] > highs[i-2]:
                gap_size = lows[i] - highs[i-2]
                gap_pct = (gap_size / highs[i-2]) * 100 if highs[i-2] > 0 else 0
                
                if gap_pct >= min_gap_pct:
                    fvgs.append({
                        'type': 'BULLISH_FVG',
                        'index': i,
                        'timestamp': self.df.index[i],
                        'top': float(lows[i]),
                        'bottom': float(highs[i-2]),
                        'midpoint': float((lows[i] + highs[i-2]) / 2),
                        'gap_size': float(gap_size),
                        'gap_pct': float(gap_pct),
                        'height': float(gap_size),
                        'close': float(closes[i]),
                        'mitigation_likelihood': 0.75,
                        'fill_probability': self._calculate_fvg_fill_probability(gap_pct),
                        'status': 'OPEN',
                        'description': 'Bullish gap - likely to fill'
                    })
            
            # Bearish FVG
            elif highs[i] < lows[i-2]:
                gap_size = lows[i-2] - highs[i]
                gap_pct = (gap_size / lows[i-2]) * 100 if lows[i-2] > 0 else 0
                
                if gap_pct >= min_gap_pct:
                    fvgs.append({
                        'type': 'BEARISH_FVG',
                        'index': i,
                        'timestamp': self.df.index[i],
                        'top': float(lows[i-2]),
                        'bottom': float(highs[i]),
                        'midpoint': float((lows[i-2] + highs[i]) / 2),
                        'gap_size': float(gap_size),
                        'gap_pct': float(gap_pct),
                        'height': float(gap_size),
                        'close': float(closes[i]),
                        'mitigation_likelihood': 0.75,
                        'fill_probability': self._calculate_fvg_fill_probability(gap_pct),
                        'status': 'OPEN',
                        'description': 'Bearish gap - likely to fill'
                    })
        
        return fvgs
    
    def detect_liquidity_sweeps(self, lookback: int = 50) -> List[Dict]:
        """Liquidity Sweep Detection"""
        sweeps = []
        highs = self.df['high'].values
        lows = self.df['low'].values
        closes = self.df['close'].values
        opens = self.df['open'].values
        volumes = self.df['volume'].values
        
        if len(highs) < lookback:
            return sweeps
        
        recent_high = np.max(highs[-lookback:])
        recent_low = np.min(lows[-lookback:])
        
        for i in range(1, len(closes)):
            # Bearish sweep
            if lows[i] < recent_low:
                recovery = closes[i] - lows[i]
                recovery_pct = (recovery / recent_low) * 100 if recent_low > 0 else 0
                
                if recovery > 0 and recovery_pct > 0.15:
                    is_bullish_candle = closes[i] > opens[i]
                    wick_ratio = recovery / (highs[i] - lows[i]) if (highs[i] - lows[i]) > 0 else 0
                    
                    sweeps.append({
                        'type': 'BEARISH_SWEEP',
                        'index': i,
                        'timestamp': self.df.index[i],
                        'level_touched': float(lows[i]),
                        'level_exceeded_by': float(abs(lows[i] - recent_low)),
                        'support_level': float(recent_low),
                        'recovery_price': float(closes[i]),
                        'recovery_amount': float(recovery),
                        'recovery_pct': float(recovery_pct),
                        'open': float(opens[i]),
                        'close': float(closes[i]),
                        'high': float(highs[i]),
                        'low': float(lows[i]),
                        'body_direction': 'BULLISH' if is_bullish_candle else 'BEARISH',
                        'signal_strength': 'STRONG' if is_bullish_candle and recovery_pct > 0.5 else 'MODERATE',
                        'volume': float(volumes[i]),
                        'wick_ratio': float(wick_ratio),
                        'description': 'Stop hunt below support - Bullish signal'
                    })
            
            # Bullish sweep
            elif highs[i] > recent_high:
                pullback = highs[i] - closes[i]
                pullback_pct = (pullback / recent_high) * 100 if recent_high > 0 else 0
                
                if pullback > 0 and pullback_pct > 0.15:
                    is_bearish_candle = closes[i] < opens[i]
                    wick_ratio = pullback / (highs[i] - lows[i]) if (highs[i] - lows[i]) > 0 else 0
                    
                    sweeps.append({
                        'type': 'BULLISH_SWEEP',
                        'index': i,
                        'timestamp': self.df.index[i],
                        'level_touched': float(highs[i]),
                        'level_exceeded_by': float(highs[i] - recent_high),
                        'resistance_level': float(recent_high),
                        'pullback_price': float(closes[i]),
                        'pullback_amount': float(pullback),
                        'pullback_pct': float(pullback_pct),
                        'open': float(opens[i]),
                        'close': float(closes[i]),
                        'high': float(highs[i]),
                        'low': float(lows[i]),
                        'body_direction': 'BEARISH' if is_bearish_candle else 'BULLISH',
                        'signal_strength': 'STRONG' if is_bearish_candle and pullback_pct > 0.5 else 'MODERATE',
                        'volume': float(volumes[i]),
                        'wick_ratio': float(wick_ratio),
                        'description': 'Stop hunt above resistance - Bearish signal'
                    })
        
        return sweeps
    
    @staticmethod
    def _classify_strength(strength_pct: float, volume_ratio: float) -> str:
        """Classify signal strength"""
        score = strength_pct * 0.5 + (volume_ratio - 1) * 50
        
        if score > 2.5:
            return 'VERY_STRONG'
        elif score > 1.5:
            return 'STRONG'
        elif score > 0.5:
            return 'MODERATE'
        else:
            return 'WEAK'
    
    @staticmethod
    def _calculate_choch_strength(prev_values: np.ndarray, 
                                  curr_values: np.ndarray) -> float:
        """Calculate CHOCH reversal strength"""
        if len(prev_values) < 2 or len(curr_values) < 2:
            return 0.0
        
        try:
            prev_trend = np.polyfit(range(len(prev_values)), prev_values, 1)[0]
            curr_trend = np.polyfit(range(len(curr_values)), curr_values, 1)[0]
            
            reversal_strength = abs(prev_trend - curr_trend)
            return min(float(reversal_strength / 100), 1.0)
        except:
            return 0.0
    
    @staticmethod
    def _calculate_fvg_fill_probability(gap_pct: float) -> float:
        """Calculate FVG fill probability"""
        if gap_pct < 0.5:
            return 0.95
        elif gap_pct < 1.0:
            return 0.85
        elif gap_pct < 1.5:
            return 0.75
        elif gap_pct < 2.0:
            return 0.65
        else:
            return 0.50
    
    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            'bos': [],
            'choch': [],
            'order_blocks': [],
            'fvgs': [],
            'sweeps': [],
            'swing_highs': [],
            'swing_lows': [],
            'timestamp': datetime.now()
        }
    
    def get_latest_signal(self) -> Dict:
        """Get the latest generated signal"""
        if not self.analysis_result:
            return {'signal': 'NO_DATA', 'description': 'No analysis performed yet'}
        
        latest_bos = self.analysis_result['bos'][-1] if self.analysis_result['bos'] else None
        latest_choch = self.analysis_result['choch'][-1] if self.analysis_result['choch'] else None
        latest_sweep = self.analysis_result['sweeps'][-1] if self.analysis_result['sweeps'] else None
        
        if latest_bos:
            if 'BULLISH' in latest_bos['type']:
                signal = 'BULLISH'
            else:
                signal = 'BEARISH'
        elif latest_choch:
            signal = 'REVERSAL'
        elif latest_sweep:
            signal = 'BOUNCE'
        else:
            signal = 'NEUTRAL'
        
        return {
            'signal': signal,
            'latest_bos': latest_bos,
            'latest_choch': latest_choch,
            'latest_sweep': latest_sweep
        }
    
    def get_statistics(self) -> Dict:
        """Get analysis statistics"""
        if not self.analysis_result:
            return {}
        
        return {
            'total_bos': len(self.analysis_result['bos']),
            'bullish_bos': len([b for b in self.analysis_result['bos'] if 'BULLISH' in b['type']]),
            'bearish_bos': len([b for b in self.analysis_result['bos'] if 'BEARISH' in b['type']]),
            'total_choch': len(self.analysis_result['choch']),
            'uptrend_choch': len([c for c in self.analysis_result['choch'] if 'UPTREND' in c['type']]),
            'downtrend_choch': len([c for c in self.analysis_result['choch'] if 'DOWNTREND' in c['type']]),
            'total_order_blocks': len(self.analysis_result['order_blocks']),
            'accumulation_ob': len([o for o in self.analysis_result['order_blocks'] if 'ACCUMULATION' in o['type']]),
            'distribution_ob': len([o for o in self.analysis_result['order_blocks'] if 'DISTRIBUTION' in o['type']]),
            'total_fvg': len(self.analysis_result['fvgs']),
            'bullish_fvg': len([f for f in self.analysis_result['fvgs'] if 'BULLISH' in f['type']]),
            'bearish_fvg': len([f for f in self.analysis_result['fvgs'] if 'BEARISH' in f['type']]),
            'total_sweeps': len(self.analysis_result['sweeps']),
            'bearish_sweeps': len([s for s in self.analysis_result['sweeps'] if 'BEARISH' in s['type']]),
            'bullish_sweeps': len([s for s in self.analysis_result['sweeps'] if 'BULLISH' in s['type']]),
        }
