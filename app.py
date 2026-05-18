import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ccxt
from datetime import datetime, timedelta
import sys
import os

# Import SMC Indicator
from screener.smc_indicator import SMCIndicator

# Page configuration
st.set_page_config(
    page_title="SMC Crypto Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .signal-bullish {
        color: #00FF00;
        font-weight: bold;
        font-size: 1.2em;
        padding: 10px;
        background-color: rgba(0, 255, 0, 0.1);
        border-radius: 5px;
        border-left: 4px solid #00FF00;
    }
    .signal-bearish {
        color: #FF3333;
        font-weight: bold;
        font-size: 1.2em;
        padding: 10px;
        background-color: rgba(255, 51, 51, 0.1);
        border-radius: 5px;
        border-left: 4px solid #FF3333;
    }
    .signal-neutral {
        color: #9999FF;
        font-weight: bold;
        font-size: 1.2em;
        padding: 10px;
        background-color: rgba(153, 153, 255, 0.1);
        border-radius: 5px;
        border-left: 4px solid #9999FF;
    }
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def init_exchange():
    """Initialize Binance exchange"""
    return ccxt.binance({
        'enableRateLimit': True,
        'timeout': 30000,
    })


@st.cache_data(ttl=300)
def fetch_candles(symbol, timeframe, limit=200):
    """Fetch OHLCV candles from Binance"""
    try:
        exchange = init_exchange()
        candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(
            candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
    except Exception as e:
        st.error(f"❌ Error fetching data: {e}")
        return None


def plot_chart_with_smc(df, smc_data, symbol):
    """Plot candlestick chart with SMC indicators"""
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{symbol} - SMC Analysis", "Volume")
    )
    
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price',
            row=1, col=1
        )
    )
    
    # Moving averages
    sma_20 = df['close'].rolling(20).mean()
    sma_50 = df['close'].rolling(50).mean()
    
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=sma_20,
            name='SMA 20',
            line=dict(color='orange', width=1),
            row=1, col=1
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=sma_50,
            name='SMA 50',
            line=dict(color='purple', width=1),
            row=1, col=1
        )
    )
    
    # Swing Highs
    swing_highs = smc_data.get('swing_highs', [])
    if swing_highs:
        sh_indices = [sh['index'] for sh in swing_highs[-10:]]
        sh_prices = [sh['price'] for sh in swing_highs[-10:]]
        sh_times = [df.index[i] if i < len(df) else None for i in sh_indices]
        
        fig.add_trace(
            go.Scatter(
                x=sh_times,
                y=sh_prices,
                mode='markers',
                marker=dict(size=10, color='red', symbol='inverted-triangle'),
                name='Swing High',
                row=1, col=1
            )
        )
    
    # Swing Lows
    swing_lows = smc_data.get('swing_lows', [])
    if swing_lows:
        sl_indices = [sl['index'] for sl in swing_lows[-10:]]
        sl_prices = [sl['price'] for sl in swing_lows[-10:]]
        sl_times = [df.index[i] if i < len(df) else None for i in sl_indices]
        
        fig.add_trace(
            go.Scatter(
                x=sl_times,
                y=sl_prices,
                mode='markers',
                marker=dict(size=10, color='green', symbol='triangle'),
                name='Swing Low',
                row=1, col=1
            )
        )
    
    # Order Blocks
    order_blocks = smc_data.get('order_blocks', [])
    for ob in order_blocks[-5:]:
        ob_time = df.index[ob['index']] if ob['index'] < len(df) else None
        color = 'rgba(0, 255, 0, 0.2)' if 'ACCUMULATION' in ob['type'] else 'rgba(255, 0, 0, 0.2)'
        
        fig.add_vrect(
            x0=ob_time,
            x1=ob_time,
            fillcolor=color,
            opacity=0.2,
            layer="below",
            line_width=0,
            row=1, col=1
        )
    
    # FVGs
    fvgs = smc_data.get('fvgs', [])
    for fvg in fvgs[-5:]:
        color = 'blue' if 'BULLISH' in fvg['type'] else 'orange'
        
        fig.add_hrect(
            y0=min(fvg['bottom'], fvg['top']),
            y1=max(fvg['bottom'], fvg['top']),
            fillcolor=color,
            opacity=0.15,
            layer="below",
            line_width=1,
            line_color=color,
            row=1, col=1
        )
    
    # BOS Levels
    bos_signals = smc_data.get('bos', [])
    for bos in bos_signals[-3:]:
        color = 'blue' if 'BULLISH' in bos['type'] else 'red'
        
        fig.add_hline(
            y=bos['level'],
            line_dash="dash",
            line_color=color,
            annotation_text=f"BOS: {bos['level']:.2f}",
            row=1, col=1
        )
    
    # Volume
    colors = ['red' if df['close'].iloc[i] < df['open'].iloc[i] else 'green'
              for i in range(len(df))]
    
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['volume'],
            marker_color=colors,
            name='Volume',
            row=2, col=1,
            showlegend=False
        )
    )
    
    fig.update_layout(
        title=f"<b>{symbol} - Smart Money Concept Analysis</b>",
        yaxis_title='Price (USDT)',
        yaxis2_title='Volume',
        xaxis_title='Time',
        hovermode='x unified',
        template='plotly_dark',
        height=800,
        showlegend=True
    )
    
    return fig


def display_signals_table(smc_data):
    """Display signals in organized tables"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔴 BOS Signals")
        bos_signals = smc_data.get('bos', [])
        if bos_signals:
            bos_df = pd.DataFrame([
                {
                    'Time': bs['timestamp'].strftime('%Y-%m-%d %H:%M'),
                    'Type': bs['type'],
                    'Level': f"${bs['level']:.2f}",
                    'Close': f"${bs['close']:.2f}",
                    'Strength': f"{bs['strength_pct']:.2f}%",
                    'Vol Ratio': f"{bs['volume_ratio']:.2f}x",
                    'Quality': bs['signal_strength']
                }
                for bs in bos_signals[-10:]
            ])
            st.dataframe(bos_df, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No BOS signals detected")
    
    with col2:
        st.subheader("⚡ CHOCH Signals")
        choch_signals = smc_data.get('choch', [])
        if choch_signals:
            choch_df = pd.DataFrame([
                {
                    'Time': cs['timestamp'].strftime('%Y-%m-%d %H:%M'),
                    'Type': cs['type'],
                    'Level': f"${cs['level']:.2f}",
                    'Close': f"${cs['close']:.2f}",
                    'Strength': f"{cs['reversal_strength']:.2f}",
                    'Quality': cs['signal_quality']
                }
                for cs in choch_signals[-10:]
            ])
            st.dataframe(choch_df, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No CHOCH signals detected")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("📦 Order Blocks")
        order_blocks = smc_data.get('order_blocks', [])
        if order_blocks:
            ob_df = pd.DataFrame([
                {
                    'Time': ob['timestamp'].strftime('%Y-%m-%d %H:%M'),
                    'Type': ob['type'],
                    'High': f"${ob['high']:.2f}",
                    'Low': f"${ob['low']:.2f}",
                    'Vol Ratio': f"{ob['volume_ratio']:.2f}x",
                    'Strength': f"{ob['strength']:.2f}",
                    'Quality': ob['quality']
                }
                for ob in order_blocks[-10:]
            ])
            st.dataframe(ob_df, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No Order Blocks detected")
    
    with col4:
        st.subheader("📊 Fair Value Gaps")
        fvgs = smc_data.get('fvgs', [])
        if fvgs:
            fvg_df = pd.DataFrame([
                {
                    'Time': fvg['timestamp'].strftime('%Y-%m-%d %H:%M'),
                    'Type': fvg['type'],
                    'Top': f"${fvg['top']:.2f}",
                    'Bottom': f"${fvg['bottom']:.2f}",
                    'Gap %': f"{fvg['gap_pct']:.2f}%",
                    'Fill Prob': f"{fvg['fill_probability']:.0%}",
                }
                for fvg in fvgs[-10:]
            ])
            st.dataframe(fvg_df, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No FVGs detected")


def display_liquidity_sweeps(smc_data):
    """Display liquidity sweeps"""
    st.subheader("💧 Liquidity Sweeps")
    
    sweeps = smc_data.get('sweeps', [])
    if sweeps:
        sweep_df = pd.DataFrame([
            {
                'Time': sp['timestamp'].strftime('%Y-%m-%d %H:%M'),
                'Type': sp['type'],
                'Level Hit': f"${sp['level_touched']:.2f}",
                'Exceeded': f"${sp['level_exceeded_by']:.2f}",
                'Recovery/Pullback': f"{sp['recovery_pct']:.2f}%" if sp['type'] == 'BEARISH_SWEEP' 
                                     else f"{sp['pullback_pct']:.2f}%",
                'Strength': sp['signal_strength'],
            }
            for sp in sweeps[-15:]
        ])
        st.dataframe(sweep_df, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No Liquidity Sweeps detected")


def display_statistics(smc_data):
    """Display analysis statistics"""
    st.subheader("📈 Analysis Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total BOS", len(smc_data.get('bos', [])))
        st.metric("Bullish BOS", len([b for b in smc_data.get('bos', []) if 'BULLISH' in b['type']]))
        st.metric("Bearish BOS", len([b for b in smc_data.get('bos', []) if 'BEARISH' in b['type']]))
    
    with col2:
        st.metric("Total CHOCH", len(smc_data.get('choch', [])))
        st.metric("Uptrend CHOCH", len([c for c in smc_data.get('choch', []) if 'UPTREND' in c['type']]))
        st.metric("Downtrend CHOCH", len([c for c in smc_data.get('choch', []) if 'DOWNTREND' in c['type']]))
    
    with col3:
        st.metric("Total Order Blocks", len(smc_data.get('order_blocks', [])))
        st.metric("Accumulation OB", len([o for o in smc_data.get('order_blocks', []) if 'ACCUMULATION' in o['type']]))
        st.metric("Distribution OB", len([o for o in smc_data.get('order_blocks', []) if 'DISTRIBUTION' in o['type']]))
    
    with col4:
        st.metric("Total FVG", len(smc_data.get('fvgs', [])))
        st.metric("Bullish FVG", len([f for f in smc_data.get('fvgs', []) if 'BULLISH' in f['type']]))
        st.metric("Bearish FVG", len([f for f in smc_data.get('fvgs', []) if 'BEARISH' in f['type']]))


def main():
    st.title("🤖 SMC Crypto Screener")
    st.markdown("**Smart Money Concept (SMC) - Technical Analysis Tool**")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Symbol selection
        symbol = st.selectbox(
            "📍 Select Trading Pair",
            options=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT', 'BNB/USDT', 'DOGE/USDT'],
            index=0
        )
        
        # Timeframe selection
        timeframe = st.selectbox(
            "⏱️ Select Timeframe",
            options=['15m', '1h', '4h', '1d'],
            index=2
        )
        
        st.markdown("---")
        st.subheader("SMC Parameters")
        
        lookback = st.slider(
            "Lookback Period",
            min_value=50,
            max_value=500,
            value=200,
            step=10
        )
        
        min_gap_pct = st.slider(
            "Minimum FVG Gap %",
            min_value=0.05,
            max_value=1.0,
            value=0.1,
            step=0.05
        )
        
        st.markdown("---")
        
        # Fetch button
        if st.button("🔄 Fetch & Analyze", use_container_width=True, type="primary"):
            st.session_state.should_fetch = True
    
    # Main content
    if st.session_state.get('should_fetch', False):
        with st.spinner(f"⏳ Fetching data for {symbol} {timeframe}..."):
            df = fetch_candles(symbol, timeframe, limit=lookback)
            
            if df is not None and len(df) > 0:
                # Run SMC Analysis
                with st.spinner("🔍 Running SMC Analysis..."):
                    smc = SMCIndicator(lookback=lookback, min_swing_size=0.005)
                    smc_data = smc.analyze(df)
                
                # Display price info
                col1, col2, col3, col4 = st.columns(4)
                
                current_price = df['close'].iloc[-1]
                price_change = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100 if len(df) > 1 else 0
                
                with col1:
                    st.metric(
                        f"💰 {symbol}",
                        f"${current_price:.2f}",
                        f"{price_change:+.2f}%",
                        delta_color="inverse"
                    )
                
                with col2:
                    st.metric(
                        "📈 24h High",
                        f"${df['high'].iloc[-24:].max():.2f}" if len(df) >= 24 else "N/A"
                    )
                
                with col3:
                    st.metric(
                        "📉 24h Low",
                        f"${df['low'].iloc[-24:].min():.2f}" if len(df) >= 24 else "N/A"
                    )
                
                with col4:
                    st.metric(
                        "📊 Volume",
                        f"${df['volume'].iloc[-1]/1000000:.2f}M"
                    )
                
                st.markdown("---")
                
                # Chart
                st.subheader("📈 Price Chart with SMC Indicators")
                chart = plot_chart_with_smc(df, smc_data, symbol)
                st.plotly_chart(chart, use_container_width=True)
                
                st.markdown("---")
                
                # Signals
                display_signals_table(smc_data)
                
                st.markdown("---")
                
                # Sweeps
                display_liquidity_sweeps(smc_data)
                
                st.markdown("---")
                
                # Statistics
                display_statistics(smc_data)
                
                st.markdown("---")
                
                # Signal Summary
                st.subheader("📋 Signal Summary")
                
                latest_signal = smc.get_latest_signal()
                signal = latest_signal.get('signal', 'NEUTRAL')
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Latest Signal:**")
                    if signal == 'BULLISH':
                        st.markdown('<div class="signal-bullish">🟢 BULLISH</div>', unsafe_allow_html=True)
                    elif signal == 'BEARISH':
                        st.markdown('<div class="signal-bearish">🔴 BEARISH</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="signal-neutral">🟡 NEUTRAL</div>', unsafe_allow_html=True)
                
                with col2:
                    st.write("**Signal Sources:**")
                    if latest_signal.get('latest_bos'):
                        st.write(f"✓ BOS: {latest_signal['latest_bos']['type']}")
                    if latest_signal.get('latest_choch'):
                        st.write(f"✓ CHOCH: {latest_signal['latest_choch']['type']}")
                    if latest_signal.get('latest_sweep'):
                        st.write(f"✓ Sweep: {latest_signal['latest_sweep']['type']}")
            else:
                st.error("❌ Failed to fetch data. Please try again.")
        
        st.session_state.should_fetch = False
    else:
        st.info("👈 Use the sidebar to select a trading pair and click 'Fetch & Analyze'")
        
        # Info sections
        with st.expander("ℹ️ How to Use"):
            st.markdown("""
            ### SMC Indicators Explained:
            
            **1. Break of Structure (BOS)**
            - Bullish: Price closes above recent swing high
            - Bearish: Price closes below recent swing low
            - Signal: Trend continuation
            
            **2. Change of Character (CHOCH)**
            - HH/HL → LL/LH = Uptrend reversal
            - LL/LH → HH/HL = Downtrend reversal
            - Signal: Major reversal
            
            **3. Order Blocks**
            - Accumulation: Smart money buying (bullish)
            - Distribution: Smart money selling (bearish)
            
            **4. Fair Value Gaps (FVG)**
            - 75% probability of being filled
            - Acts as support/resistance
            
            **5. Liquidity Sweeps**
            - Stop hunt + reversal
            - Strong directional signal
            """)
        
        with st.expander("📚 Trading Strategy Tips"):
            st.markdown("""
            **Entry Strategy:**
            - Wait for BOS + Order Block confirmation
            - Enter on liquidity sweep recovery
            - Target FVG zones
            
            **Risk Management:**
            - Risk 1-2% per trade
            - Stop loss at swing levels
            - 1.5:1 minimum risk-reward ratio
            
            **Best Practices:**
            - Use multiple timeframes
            - Confirm signals across TF
            - Backtest your strategy
            """)


if __name__ == "__main__":
    # Initialize session state
    if 'should_fetch' not in st.session_state:
        st.session_state.should_fetch = False
    
    main()
