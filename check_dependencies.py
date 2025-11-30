#!/usr/bin/env python3
"""
Dependency Checker - Verify all required packages are installed
Run this before starting the trading system.
"""
import sys
from typing import List, Tuple

def check_dependencies() -> List[Tuple[str, bool, str]]:
    """
    Check if all critical dependencies are installed
    
    Returns:
        List of (package_name, installed, version/error)
    """
    results = []
    
    # Critical packages
    critical_packages = [
        'ib_insync',
        'google.generativeai',
        'anthropic',
        'scipy',
        'numpy',
        'pandas',
        'aiosqlite',
        'loguru',
        'yfinance',
        'newsapi',
        'pandas_ta',
        'py_vollib'
    ]
    
    for package in critical_packages:
        try:
            if package == 'google.generativeai':
                import google.generativeai as genai
                version = getattr(genai, '__version__', 'unknown')
            elif package == 'newsapi':
                from newsapi import NewsApiClient
                version = 'installed'
            else:
                mod = __import__(package.replace('-', '_'))
                version = getattr(mod, '__version__', 'unknown')
            
            results.append((package, True, version))
            
        except ImportError as e:
            results.append((package, False, str(e)))
    
    return results


def verify_scipy():
    """Specific test for scipy (critical for Vanna calculation)"""
    try:
        from scipy.stats import norm
        import numpy as np
        
        # Test basic functionality
        test_val = norm.pdf(0)  # Should be ~0.399
        assert 0.39 < test_val < 0.40, "scipy.stats.norm not working correctly"
        
        return True, f"scipy working (norm.pdf(0) = {test_val:.4f})"
    except Exception as e:
        return False, f"scipy error: {e}"


def verify_vanna_calculator():
    """Test VannaCalculator can be imported and used"""
    try:
        from risk.vanna_calculator import get_vanna_calculator
        
        calc = get_vanna_calculator()
        
        # Test calculation
        vanna = calc.calculate_vanna(
            S=100, K=105, T=0.1, sigma=0.30, option_type='call'
        )
        
        if vanna is None:
            return False, "Vanna calculation returned None"
        
        return True, f"VannaCalculator working (test vanna={vanna:.6f})"
        
    except Exception as e:
        return False, f"VannaCalculator error: {e}"


if __name__ == "__main__":
    print("=" * 60)
    print("Gemini Trader AI - Dependency Check")
    print("=" * 60)
    print()
    
    # Check all dependencies
    results = check_dependencies()
    
    missing = []
    installed = []
    
    for package, is_installed, info in results:
        if is_installed:
            print(f"✅ {package:25s} {info}")
            installed.append(package)
        else:
            print(f"❌ {package:25s} MISSING")
            missing.append(package)
    
    print()
    print("-" * 60)
    print(f"Installed: {len(installed)}/{len(results)}")
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("\nInstall with:")
        print("  pip install -r requirements.txt")
        print()
    
    # Special scipy verification
    print("\n" + "=" * 60)
    print("Critical Component Tests")
    print("=" * 60)
    
    scipy_ok, scipy_msg = verify_scipy()
    print(f"{'✅' if scipy_ok else '❌'} scipy: {scipy_msg}")
    
    vanna_ok, vanna_msg = verify_vanna_calculator()
    print(f"{'✅' if vanna_ok else '❌'} VannaCalculator: {vanna_msg}")
    
    print()
    print("=" * 60)
    
    if missing or not scipy_ok or not vanna_ok:
        print("❌ Dependency check FAILED")
        print("\nAction required:")
        if missing:
            print("  1. Run: pip install -r requirements.txt")
        if not scipy_ok:
            print("  2. Run: pip install --upgrade scipy numpy")
        if not vanna_ok:
            print("  3. Check risk/vanna_calculator.py for errors")
        sys.exit(1)
    else:
        print("✅ All dependencies OK - System ready!")
        sys.exit(0)
