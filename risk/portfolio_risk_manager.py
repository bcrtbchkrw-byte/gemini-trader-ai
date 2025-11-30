"""
Portfolio Risk Manager - Beta-weighted Delta & Directional Exposure
Prevents over-concentration in one direction (bullish/bearish).
"""
from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime


class PortfolioRiskManager:
    """
    Manage portfolio-level risk with beta-weighted delta
    
    Key metrics:
    - Beta-weighted Delta: Position delta adjusted for underlying beta
    - Directional exposure: Net bullish/bearish exposure
    - Position limits: Max delta exposure allowed
    """
    
    def __init__(
        self,
        max_beta_weighted_delta: float = 100.0,
        max_net_delta: float = 50.0,
        spy_beta: float = 1.0
    ):
        """
        Initialize portfolio risk manager
        
        Args:
            max_beta_weighted_delta: Max absolute beta-weighted delta
            max_net_delta: Max absolute net delta (non-beta-weighted)
            spy_beta: Beta of SPY (reference = 1.0)
        """
        self.max_beta_weighted_delta = max_beta_weighted_delta
        self.max_net_delta = max_net_delta
        self.spy_beta = spy_beta
        
        # Portfolio state
        self.positions = {}  # symbol -> position data
        self.beta_cache = {}  # symbol -> beta value
        
    def calculate_beta_weighted_delta(
        self,
        symbol: str,
        position_delta: float,
        beta: Optional[float] = None
    ) -> float:
        """
        Calculate beta-weighted delta for a position
        
        Beta-weighted delta = Position Delta × Beta
        
        This normalizes all positions to SPY-equivalent exposure.
        
        Args:
            symbol: Stock ticker
            position_delta: Position's net delta (contracts × delta × 100)
            beta: Stock's beta (vs SPY). If None, fetched from cache/API
            
        Returns:
            Beta-weighted delta (SPY-equivalent)
        """
        try:
            # Get beta
            if beta is None:
                beta = self.get_beta(symbol)
            
            # Beta-weight the delta
            bw_delta = position_delta * beta
            
            logger.debug(
                f"{symbol}: Delta={position_delta:.2f}, Beta={beta:.2f}, "
                f"BW-Delta={bw_delta:.2f}"
            )
            
            return bw_delta
            
        except Exception as e:
            logger.error(f"Error calculating beta-weighted delta for {symbol}: {e}")
            return position_delta  # Fallback to unweighted
    
    def get_beta(self, symbol: str) -> float:
        """
        Get beta for symbol (cached or fetched)
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Beta value (default 1.0 if unavailable)
        """
        # Check cache
        if symbol in self.beta_cache:
            return self.beta_cache[symbol]
        
        # SPY is always 1.0
        if symbol == 'SPY':
            self.beta_cache[symbol] = 1.0
            return 1.0
        
        try:
            # Get actual beta from IBKR
            from ibkr.data_fetcher import get_data_fetcher
            
            fetcher = get_data_fetcher()
            beta = await fetcher.get_beta(symbol)
            
            self.beta_cache[symbol] = beta
            
            logger.debug(f"Beta for {symbol}: {beta:.3f}")
            return beta
            
        except Exception as e:
            logger.warning(f"Could not fetch beta for {symbol}: {e}, using 1.0")
            self.beta_cache[symbol] = 1.0
            return 1.0
    
    def add_position(
        self,
        symbol: str,
        contracts: int,
        delta_per_contract: float,
        strategy_type: str,
        beta: Optional[float] = None
    ):
        """
        Add position to portfolio tracking
        
        Args:
            symbol: Stock ticker
            contracts: Number of contracts (negative for short)
            delta_per_contract: Delta per contract
            strategy_type: e.g., "IRON_CONDOR", "PUT_SPREAD"
            beta: Stock beta (optional, will be fetched if None)
        """
        # Calculate position delta
        position_delta = contracts * delta_per_contract * 100  # Options multiplier
        
        # Calculate beta-weighted delta
        bw_delta = self.calculate_beta_weighted_delta(symbol, position_delta, beta)
        
        self.positions[symbol] = {
            'symbol': symbol,
            'contracts': contracts,
            'delta_per_contract': delta_per_contract,
            'position_delta': position_delta,
            'beta': self.get_beta(symbol),
            'beta_weighted_delta': bw_delta,
            'strategy_type': strategy_type,
            'added_at': datetime.now().isoformat()
        }
        
        logger.info(
            f"Added position: {symbol} {contracts} contracts, "
            f"Delta={position_delta:.2f}, BW-Delta={bw_delta:.2f}"
        )
    
    def remove_position(self, symbol: str):
        """Remove position from portfolio"""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"Removed position: {symbol}")
    
    def get_portfolio_metrics(self) -> Dict[str, Any]:
        """
        Calculate current portfolio metrics
        
        Returns:
            Dict with:
            - net_delta: Raw net delta
            - beta_weighted_delta: Net beta-weighted delta
            - position_count: Number of positions
            - bullish_delta: Positive delta exposure
            - bearish_delta: Negative delta exposure
        """
        if not self.positions:
            return {
                'net_delta': 0.0,
                'beta_weighted_delta': 0.0,
                'position_count': 0,
                'bullish_delta': 0.0,
                'bearish_delta': 0.0
            }
        
        net_delta = sum(p['position_delta'] for p in self.positions.values())
        bw_delta = sum(p['beta_weighted_delta'] for p in self.positions.values())
        
        # Split by direction
        bullish = sum(
            p['beta_weighted_delta'] 
            for p in self.positions.values() 
            if p['beta_weighted_delta'] > 0
        )
        bearish = sum(
            p['beta_weighted_delta'] 
            for p in self.positions.values() 
            if p['beta_weighted_delta'] < 0
        )
        
        return {
            'net_delta': net_delta,
            'beta_weighted_delta': bw_delta,
            'position_count': len(self.positions),
            'bullish_delta': bullish,
            'bearish_delta': bearish,
            'positions': list(self.positions.values())
        }
    
    def check_new_trade(
        self,
        symbol: str,
        proposed_delta: float,
        beta: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Check if new trade would exceed risk limits
        
        Args:
            symbol: Stock ticker
            proposed_delta: Delta of proposed trade
            beta: Stock beta (optional)
            
        Returns:
            Dict with approval status and reason
        """
        # Get current metrics
        current = self.get_portfolio_metrics()
        
        # Calculate proposed beta-weighted delta
        proposed_bw_delta = self.calculate_beta_weighted_delta(
            symbol, proposed_delta, beta
        )
        
        # Calculate new totals
        new_bw_delta = current['beta_weighted_delta'] + proposed_bw_delta
        new_net_delta = current['net_delta'] + proposed_delta
        
        # Check limits
        issues = []
        
        # Beta-weighted delta limit
        if abs(new_bw_delta) > self.max_beta_weighted_delta:
            issues.append(
                f"Beta-weighted delta {new_bw_delta:.1f} exceeds limit "
                f"{self.max_beta_weighted_delta:.1f}"
            )
        
        # Net delta limit
        if abs(new_net_delta) > self.max_net_delta:
            issues.append(
                f"Net delta {new_net_delta:.1f} exceeds limit "
                f"{self.max_net_delta:.1f}"
            )
        
        # Check directional concentration
        if proposed_bw_delta > 0:  # Bullish trade
            new_bullish = current['bullish_delta'] + proposed_bw_delta
            if new_bullish > self.max_beta_weighted_delta * 0.8:
                issues.append(
                    f"Bullish exposure {new_bullish:.1f} too high "
                    f"(80% of limit)"
                )
        else:  # Bearish trade
            new_bearish = current['bearish_delta'] + proposed_bw_delta
            if abs(new_bearish) > self.max_beta_weighted_delta * 0.8:
                issues.append(
                    f"Bearish exposure {abs(new_bearish):.1f} too high "
                    f"(80% of limit)"
                )
        
        approved = len(issues) == 0
        
        result = {
            'approved': approved,
            'current_bw_delta': current['beta_weighted_delta'],
            'proposed_bw_delta': proposed_bw_delta,
            'new_bw_delta': new_bw_delta,
            'current_net_delta': current['net_delta'],
            'new_net_delta': new_net_delta,
            'issues': issues,
            'limits': {
                'max_beta_weighted_delta': self.max_beta_weighted_delta,
                'max_net_delta': self.max_net_delta
            }
        }
        
        if approved:
            logger.info(
                f"✅ Trade approved: {symbol} BWD={proposed_bw_delta:.1f}, "
                f"Portfolio BWD={current['beta_weighted_delta']:.1f} -> {new_bw_delta:.1f}"
            )
        else:
            logger.warning(
                f"❌ Trade REJECTED: {symbol} - {'; '.join(issues)}"
            )
        
        return result
    
    def get_risk_report(self) -> str:
        """
        Generate human-readable risk report
        
        Returns:
            Formatted risk report string
        """
        metrics = self.get_portfolio_metrics()
        
        report = f"""
{'='*60}
Portfolio Risk Report
{'='*60}

Position Count: {metrics['position_count']}

Delta Metrics:
  Net Delta:              {metrics['net_delta']:+.2f}
  Beta-Weighted Delta:    {metrics['beta_weighted_delta']:+.2f}
  Bullish Exposure:       {metrics['bullish_delta']:+.2f}
  Bearish Exposure:       {metrics['bearish_delta']:+.2f}

Limits:
  Max Beta-Weighted:      {self.max_beta_weighted_delta:.2f}
  Max Net Delta:          {self.max_net_delta:.2f}

Utilization:
  BW Delta:               {abs(metrics['beta_weighted_delta'])/self.max_beta_weighted_delta*100:.1f}%
  Net Delta:              {abs(metrics['net_delta'])/self.max_net_delta*100:.1f}%

{'='*60}
"""
        return report


# Singleton
_portfolio_risk_manager: Optional[PortfolioRiskManager] = None


def get_portfolio_risk_manager(
    max_beta_weighted_delta: float = 100.0,
    max_net_delta: float = 50.0
) -> PortfolioRiskManager:
    """Get or create singleton portfolio risk manager"""
    global _portfolio_risk_manager
    if _portfolio_risk_manager is None:
        _portfolio_risk_manager = PortfolioRiskManager(
            max_beta_weighted_delta=max_beta_weighted_delta,
            max_net_delta=max_net_delta
        )
    return _portfolio_risk_manager
