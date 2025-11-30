"""
Greeks Validator
Validates option Greeks according to trading rules.
"""
from typing import Dict, Any, Optional
from loguru import logger
from config import get_config
from ai.claude_client import get_claude_client


class GreeksValidator:
    """Validate Greeks for trade safety"""
    
    def __init__(self):
        self.config = get_config().greeks
        self.claude = get_claude_client()
        self.portfolio_greeks = {'delta': 0.0, 'theta': 0.0, 'vega': 0.0, 'gamma': 0.0}
    
    async def validate_credit_spread(
        self,
        short_leg_greeks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate Greeks for credit spread short leg
        
        Args:
            short_leg_greeks: Greeks data for short option
            
        Returns:
            Dict with validation results
        """
        try:
            delta = short_leg_greeks.get('delta')
            theta = short_leg_greeks.get('theta')
            vanna = short_leg_greeks.get('vanna')
            
            results = {
                'passed': False,
                'delta_check': False,
                'theta_check': False,
                'vanna_check': False,
                'issues': []
            }
            
            # Delta check
            if delta is not None:
                abs_delta = abs(delta)
                if self.config.credit_spread_min_delta <= abs_delta <= self.config.credit_spread_max_delta:
                    results['delta_check'] = True
                    logger.info(f"✅ Delta check PASSED: {delta:.3f}")
                else:
                    results['issues'].append(
                        f"Delta {delta:.3f} outside range "
                        f"[{self.config.credit_spread_min_delta}, {self.config.credit_spread_max_delta}]"
                    )
                    logger.warning(f"❌ Delta check FAILED: {delta:.3f}")
            else:
                results['issues'].append("Delta not available")
            
            # Theta check
            if theta is not None:
                # Theta should be positive for credit spreads (we collect theta decay)
                # Note: Some brokers report theta as negative decay per day
                # Adjust sign if needed based on your broker's convention
                daily_theta = abs(theta)
                
                if daily_theta >= self.config.min_theta_daily:
                    results['theta_check'] = True
                    logger.info(f"✅ Theta check PASSED: ${daily_theta:.2f}/day")
                else:
                    results['issues'].append(
                        f"Theta ${daily_theta:.2f}/day below minimum ${self.config.min_theta_daily}"
                    )
                    logger.warning(f"❌ Theta check FAILED: ${daily_theta:.2f}/day")
            else:
                results['issues'].append("Theta not available")
            
            # Gamma check (NEW)
            gamma = short_leg_greeks.get('gamma')
            if gamma is not None:
                abs_gamma = abs(gamma)
                max_gamma = self.config.max_gamma if hasattr(self.config, 'max_gamma') else 0.05
                
                if abs_gamma <= max_gamma:
                    results['gamma_check'] = True
                    logger.info(f"✅ Gamma check PASSED: {abs_gamma:.4f}")
                else:
                    results['issues'].append(f"Gamma {abs_gamma:.4f} exceeds max {max_gamma}")
                    logger.warning(f"❌ Gamma check FAILED: {abs_gamma:.4f}")
            else:
                results['gamma_check'] = True  # Don't block if unavailable
            
            # Enhanced Vanna stress test (multi-scenario)
            if vanna is not None:
                vanna_tests = await self._multi_scenario_vanna_test(short_leg_greeks)
                
                if vanna_tests['all_safe']:
                    results['vanna_check'] = True
                    logger.info(
                        f"✅ Vanna stress test PASSED: "
                        f"All scenarios safe (worst delta: {vanna_tests['worst_delta']:.3f})"
                    )
                else:
                    results['issues'].append(
                        f"Vanna risk in scenario: {vanna_tests['failed_scenario']}"
                    )
                    logger.warning(f"❌ Vanna stress test FAILED: {vanna_tests['failed_scenario']}")
            else:
                # If Vanna not available, proceed with caution
                results['vanna_check'] = True  # Don't block trade
                logger.warning("⚠️ Vanna not available, proceeding with caution")
            
            # Overall pass (including gamma)
            results['passed'] = (
                results['delta_check'] and
                results['theta_check'] and
                results['vanna_check'] and
                results.get('gamma_check', True)
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating credit spread Greeks: {e}")
            return {
                'passed': False,
                'issues': [f'Validation error: {str(e)}']
            }
    
    async def validate_debit_spread(
        self,
        long_leg_greeks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate Greeks for debit spread long leg
        
        Args:
            long_leg_greeks: Greeks data for long option
            
        Returns:
            Dict with validation results
        """
        try:
            delta = long_leg_greeks.get('delta')
            
            results = {
                'passed': False,
                'delta_check': False,
                'issues': []
            }
            
            # Delta check for debit spreads (ITM options)
            if delta is not None:
                abs_delta = abs(delta)
                if self.config.debit_spread_min_delta <= abs_delta <= self.config.debit_spread_max_delta:
                    results['delta_check'] = True
                    results['passed'] = True
                    logger.info(f"✅ Debit spread Delta check PASSED: {delta:.3f}")
                else:
                    results['issues'].append(
                        f"Delta {delta:.3f} outside range "
                        f"[{self.config.debit_spread_min_delta}, {self.config.debit_spread_max_delta}]"
                    )
                    logger.warning(f"❌ Debit spread Delta check FAILED: {delta:.3f}")
            else:
                results['issues'].append("Delta not available")
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating debit spread Greeks: {e}")
            return {
                'passed': False,
                'issues': [f'Validation error: {str(e)}']
            }
    
    async def _multi_scenario_vanna_test(
        self,
        greeks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run Vanna stress test across multiple IV scenarios
        
        Args:
            greeks: Option Greeks
            
        Returns:
            Dict with test results
        """
        scenarios = [
            {'name': 'IV_UP_5', 'iv_change': 5.0},
            {'name': 'IV_UP_10', 'iv_change': 10.0},
            {'name': 'IV_DOWN_5', 'iv_change': -5.0},
        ]
        
        results = []
        worst_delta = 0.0
        failed_scenario = None
        
        for scenario in scenarios:
            test = await self.claude.stress_test_greeks(
                greeks,
                iv_change=scenario['iv_change']
            )
            
            results.append({
                'scenario': scenario['name'],
                'iv_change': scenario['iv_change'],
                'safe': test.get('safe', False),
                'projected_delta': test.get('projected_delta', 0)
            })
            
            projected_delta = abs(test.get('projected_delta', 0))
            if projected_delta > abs(worst_delta):
                worst_delta = test.get('projected_delta', 0)
            
            if not test.get('safe', False):
                failed_scenario = scenario['name']
        
        return {
            'all_safe': failed_scenario is None,
            'scenarios': results,
            'worst_delta': worst_delta,
            'failed_scenario': failed_scenario
        }
    
    def update_portfolio_greeks(
        self,
        position_greeks: Dict[str, float],
        contracts: int,
        action: str = 'ADD'
    ):
        """
        Update portfolio-level Greeks aggregation
        
        Args:
            position_greeks: Greeks for new position
            contracts: Number of contracts
            action: 'ADD' or 'REMOVE'
        """
        multiplier = contracts * (1 if action == 'ADD' else -1)
        
        for greek in ['delta', 'theta', 'vega', 'gamma']:
            value = position_greeks.get(greek, 0)
            self.portfolio_greeks[greek] += value * multiplier
        
        logger.info(f"Portfolio Greeks updated ({action}): {self.portfolio_greeks}")
    
    def get_portfolio_greeks(self) -> Dict[str, float]:
        """
        Get current portfolio-level Greeks
        
        Returns:
            Dict with aggregated Greeks
        """
        return self.portfolio_greeks.copy()
    
    def check_portfolio_limits(self) -> Dict[str, Any]:
        """
        Check if portfolio Greeks are within safe limits
        
        Returns:
            Dict with limit check results
        """
        # Define portfolio limits
        max_portfolio_delta = 1.0  # Max net delta exposure
        max_portfolio_vega = 10.0  # Max vega exposure
        
        results = {
            'within_limits': True,
            'issues': []
        }
        
        # Check delta
        if abs(self.portfolio_greeks['delta']) > max_portfolio_delta:
            results['within_limits'] = False
            results['issues'].append(
                f"Portfolio delta {self.portfolio_greeks['delta']:.2f} exceeds limit {max_portfolio_delta}"
            )
        
        # Check vega
        if abs(self.portfolio_greeks['vega']) > max_portfolio_vega:
            results['within_limits'] = False
            results['issues'].append(
                f"Portfolio vega {self.portfolio_greeks['vega']:.2f} exceeds limit {max_portfolio_vega}"
            )
        
        return results


# Singleton instance
_greeks_validator: Optional[GreeksValidator] = None


def get_greeks_validator() -> GreeksValidator:
    """Get or create singleton Greeks validator instance"""
    global _greeks_validator
    if _greeks_validator is None:
        _greeks_validator = GreeksValidator()
    return _greeks_validator
