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
            
            # Vanna stress test
            if vanna is not None:
                vanna_test = await self.claude.stress_test_greeks(
                    short_leg_greeks,
                    iv_change=5.0
                )
                
                if vanna_test.get('safe', False):
                    results['vanna_check'] = True
                    logger.info(
                        f"✅ Vanna stress test PASSED: "
                        f"Delta would move to {vanna_test['projected_delta']:.3f} on +5% IV"
                    )
                else:
                    results['issues'].append(
                        vanna_test.get('warning', 'Vanna risk too high')
                    )
                    logger.warning(f"❌ Vanna stress test FAILED: {vanna_test.get('warning')}")
            else:
                # If Vanna not available, proceed with caution
                results['vanna_check'] = True  # Don't block trade
                logger.warning("⚠️ Vanna not available, proceeding with caution")
            
            # Overall pass
            results['passed'] = (
                results['delta_check'] and
                results['theta_check'] and
                results['vanna_check']
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


# Singleton instance
_greeks_validator: Optional[GreeksValidator] = None


def get_greeks_validator() -> GreeksValidator:
    """Get or create singleton Greeks validator instance"""
    global _greeks_validator
    if _greeks_validator is None:
        _greeks_validator = GreeksValidator()
    return _greeks_validator
