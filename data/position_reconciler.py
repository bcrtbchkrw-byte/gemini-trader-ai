"""
Position Reconciliation - Sync DB with IBKR Reality
Critical for production: Ensures DB matches actual IBKR portfolio after restart.
"""
from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime


class PositionReconciler:
    """Reconcile database positions with actual IBKR portfolio"""
    
    def __init__(self, db, ibkr_connection):
        self.db = db
        self.ibkr = ibkr_connection
    
    async def reconcile_positions(self) -> Dict[str, Any]:
        """
        Reconcile DB positions with IBKR portfolio
        
        This is CRITICAL for production:
        - Bot restarts → DB may have stale data
        - Manual closes in TWS → DB doesn't know
        - Margin calls → IBKR closed positions
        
        Returns:
            Reconciliation report
        """
        try:
            logger.info("=" * 60)
            logger.info("🔄 POSITION RECONCILIATION - Syncing DB with IBKR")
            logger.info("=" * 60)
            
            # Step 1: Get positions from DB
            db_positions = await self._get_db_positions()
            logger.info(f"📊 Database: {len(db_positions)} open positions")
            
            # Step 2: Get actual IBKR portfolio
            ibkr_positions = await self._get_ibkr_portfolio()
            logger.info(f"📈 IBKR Portfolio: {len(ibkr_positions)} positions")
            
            # Step 3: Reconcile
            report = await self._reconcile(db_positions, ibkr_positions)
            
            # Step 4: Log results
            self._log_report(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Reconciliation error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_db_positions(self) -> List[Dict[str, Any]]:
        """Get all OPEN positions from database"""
        try:
            query = """
                SELECT id, symbol, strategy, contracts, entry_date, status
                FROM positions
                WHERE status IN ('OPEN', 'ACTIVE')
                ORDER BY entry_date DESC
            """
            
            result = await self.db.execute(query)
            positions = await result.fetchall()
            
            return [
                {
                    'id': p[0],
                    'symbol': p[1],
                    'strategy': p[2],
                    'contracts': p[3],
                    'entry_date': p[4],
                    'status': p[5]
                }
                for p in positions
            ]
            
        except Exception as e:
            logger.error(f"Error fetching DB positions: {e}")
            return []
    
    async def _get_ibkr_portfolio(self) -> Dict[str, Any]:
        """Get actual portfolio from IBKR"""
        try:
            ib = self.ibkr.get_client()
            
            if not ib or not ib.isConnected():
                logger.error("Not connected to IBKR for reconciliation")
                return {}
            
            # Get portfolio positions
            portfolio_items = ib.portfolio()
            
            # Group by symbol (underlying)
            positions_by_symbol = {}
            
            for item in portfolio_items:
                contract = item.contract
                
                # Only care about options
                if contract.secType != 'OPT':
                    continue
                
                symbol = contract.symbol
                
                if symbol not in positions_by_symbol:
                    positions_by_symbol[symbol] = {
                        'symbol': symbol,
                        'positions': [],
                        'total_contracts': 0
                    }
                
                positions_by_symbol[symbol]['positions'].append({
                    'contract': contract,
                    'position': item.position,
                    'market_value': item.marketValue,
                    'avg_cost': item.averageCost
                })
                
                positions_by_symbol[symbol]['total_contracts'] += abs(item.position)
            
            logger.debug(f"IBKR has positions in: {list(positions_by_symbol.keys())}")
            
            return positions_by_symbol
            
        except Exception as e:
            logger.error(f"Error fetching IBKR portfolio: {e}")
            return {}
    
    async def _reconcile(
        self,
        db_positions: List[Dict[str, Any]],
        ibkr_positions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare DB vs IBKR and fix discrepancies
        
        Returns:
            Reconciliation report
        """
        report = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'matched': [],
            'closed_externally': [],
            'new_in_ibkr': [],
            'errors': []
        }
        
        # Check each DB position
        for db_pos in db_positions:
            symbol = db_pos['symbol']
            
            # Does this position exist in IBKR?
            if symbol in ibkr_positions:
                # Position exists - MATCH
                report['matched'].append({
                    'symbol': symbol,
                    'db_id': db_pos['id'],
                    'contracts': db_pos['contracts']
                })
                
                logger.debug(f"✅ {symbol}: Position matched in IBKR")
                
            else:
                # Position NOT in IBKR - Mark as CLOSED_EXTERNALLY
                logger.warning(
                    f"⚠️  {symbol}: DB shows OPEN but NOT in IBKR portfolio! "
                    f"(Closed externally?)"
                )
                
                # Update DB
                await self._mark_closed_externally(db_pos)
                
                report['closed_externally'].append({
                    'symbol': symbol,
                    'db_id': db_pos['id'],
                    'contracts': db_pos['contracts'],
                    'entry_date': db_pos['entry_date']
                })
        
        # Check for positions in IBKR but not in DB
        db_symbols = {p['symbol'] for p in db_positions}
        for symbol in ibkr_positions:
            if symbol not in db_symbols:
                logger.warning(
                    f"⚠️  {symbol}: In IBKR portfolio but NOT in DB "
                    f"(Manual entry?)"
                )
                
                report['new_in_ibkr'].append({
                    'symbol': symbol,
                    'contracts': ibkr_positions[symbol]['total_contracts']
                })
        
        return report
    
    async def _mark_closed_externally(self, position: Dict[str, Any]):
        """Mark position as closed externally in DB"""
        try:
            query = """
                UPDATE positions
                SET 
                    status = 'CLOSED_EXTERNALLY',
                    exit_date = ?,
                    exit_reason = 'External close detected during reconciliation'
                WHERE id = ?
            """
            
            await self.db.execute(
                query,
                (datetime.now().isoformat(), position['id'])
            )
            
            await self.db.commit()
            
            logger.info(
                f"📝 Marked position {position['symbol']} (ID: {position['id']}) "
                f"as CLOSED_EXTERNALLY"
            )
            
        except Exception as e:
            logger.error(f"Error marking position closed: {e}")
    
    def _log_report(self, report: Dict[str, Any]):
        """Log reconciliation report"""
        if not report.get('success'):
            logger.error(f"❌ Reconciliation failed: {report.get('error')}")
            return
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 RECONCILIATION REPORT")
        logger.info("=" * 60)
        
        matched = len(report['matched'])
        closed = len(report['closed_externally'])
        new = len(report['new_in_ibkr'])
        
        logger.info(f"✅ Matched: {matched} positions")
        
        if closed > 0:
            logger.warning(f"⚠️  Closed Externally: {closed} positions")
            for pos in report['closed_externally']:
                logger.warning(
                    f"   - {pos['symbol']}: {pos['contracts']} contracts "
                    f"(entry: {pos['entry_date']})"
                )
        
        if new > 0:
            logger.warning(f"⚠️  New in IBKR (not in DB): {new} positions")
            for pos in report['new_in_ibkr']:
                logger.warning(
                    f"   - {pos['symbol']}: {pos['contracts']} contracts"
                )
        
        if closed == 0 and new == 0:
            logger.info("✅ All positions in sync!")
        
        logger.info("=" * 60 + "\n")


# Singleton
_reconciler: Optional[PositionReconciler] = None


def get_position_reconciler(db, ibkr_connection) -> PositionReconciler:
    """Get or create position reconciler"""
    global _reconciler
    if _reconciler is None:
        _reconciler = PositionReconciler(db, ibkr_connection)
    return _reconciler
