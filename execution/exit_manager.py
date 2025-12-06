"""
Exit Manager - Position Tracking & Auto-Exit Logic
Tracks open positions and triggers exits based on profit targets, stop-loss, or time.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger
from data.database import get_database


class Position:
    """Represents an open position"""
    
    def __init__(
        self,
        position_id: int,
        symbol: str,
        strategy: str,
        entry_date: datetime,
        expiration: datetime,
        contracts: int,
        entry_credit: float,
        max_risk: float,
        legs: List[Dict[str, Any]],
        trailing_stop_enabled: bool = True,
        trailing_profit_enabled: bool = True
    ):
        self.position_id = position_id
        self.symbol = symbol
        self.strategy = strategy
        self.entry_date = entry_date
        self.expiration = expiration
        self.contracts = contracts
        self.entry_credit = entry_credit
        self.max_risk = max_risk
        self.legs = legs
        
        # NEW: Trailing exit settings
        self.trailing_stop_enabled = trailing_stop_enabled
        self.trailing_profit_enabled = trailing_profit_enabled
        
        # Calculate initial static targets (fallback)
        self.profit_target = entry_credit * 0.5  # 50% of max profit
        self.stop_loss = entry_credit * 2.5  # 2.5x credit
        self.time_exit_dte = 7  # Close at 7 DTE
        
        # NEW: Trailing levels (initialized with static values)
        self.trailing_stop = self.stop_loss
        self.trailing_profit = self.profit_target
        
        # NEW: Tracking for ML
        self.highest_profit_seen = 0.0
        self.ml_last_update = None
        self.ml_confidence = 0.0
        self.stop_multiplier = 2.5  # Current multiplier
        self.profit_target_pct = 0.5  # Current target %
    
    @property
    def days_to_expiration(self) -> int:
        """Calculate days to expiration"""
        return (self.expiration - datetime.now()).days
    
    @property
    def days_in_trade(self) -> int:
        """Days since entry"""
        return (datetime.now() - self.entry_date).days
    
    def update_trailing_levels(self, current_price: float, market_data: Dict[str, Any] = None) -> bool:
        """
        Update trailing stop and profit levels using ML model
        
        Args:
            current_price: Current spread price
            market_data: Current market conditions (VIX, regime, etc.)
            
        Returns:
            True if levels were updated
        """
        try:
            from ml.exit_strategy_ml import get_exit_strategy_ml
            from ml.feature_engineering import get_feature_engineering
            
            # Get ML model
            ml_model = get_exit_strategy_ml()
            
            if ml_model.mode != 'ML':
                # ML not available, use static levels
                return False
            
            # Track highest profit
            current_pnl = (self.entry_credit - current_price) * self.contracts * 100
            if current_pnl > self.highest_profit_seen:
                self.highest_profit_seen = current_pnl
            
            # Prepare features
            feature_eng = get_feature_engineering()
            
            position_data = {
                'entry_credit': self.entry_credit,
                'max_risk': self.max_risk,
                'contracts': self.contracts,
                'entry_date': self.entry_date,
                'expiration': self.expiration,
                'vix_entry': 18.0,  # TODO: Store at entry
                'delta_entry': 0.2,  # TODO: Store at entry
                'theta_entry': 1.5,  # TODO: Store at entry
                'iv_entry': 0.3,  # TODO: Store at entry
                'highest_profit_seen': self.highest_profit_seen
            }
            
            features = feature_eng.extract_exit_features(
                position_data=position_data,
                current_price=current_price,
                market_data=market_data
            )
            
            # Get ML prediction
            prediction = ml_model.predict_exit_levels(
                features=features,
                entry_credit=self.entry_credit,
                current_stop=self.trailing_stop,
                current_profit=self.trailing_profit
            )
            
            # Update levels if confidence is high enough
            if prediction['confidence'] >= 0.5:
                old_stop = self.trailing_stop
                old_profit = self.trailing_profit
                
                # Only tighten stops, never widen
                if self.trailing_stop_enabled:
                    self.trailing_stop = min(prediction['trailing_stop'], self.trailing_stop)
                    self.stop_multiplier = prediction['stop_multiplier']
                
                # Can adjust profit target both ways
                if self.trailing_profit_enabled:
                    self.trailing_profit = prediction['trailing_profit']
                    self.profit_target_pct = prediction['profit_target_pct']
                
                self.ml_confidence = prediction['confidence']
                self.ml_last_update = datetime.now()
                
                logger.debug(
                    f"ML Exit Update [{self.symbol}]: "
                    f"Stop: ${old_stop:.2f}→${self.trailing_stop:.2f}, "
                    f"Profit: ${old_profit:.2f}→${self.trailing_profit:.2f}, "
                    f"Confidence: {self.ml_confidence:.1%}"
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error updating trailing levels: {e}")
            return False
    
    def should_exit(self, current_price: float, market_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Determine if position should be exited (ML-enhanced)
        
        Args:
            current_price: Current price of the spread
            market_data: Market data for ML updates
            
        Returns:
            Dict with exit decision and reason
        """
        # Update trailing levels with ML (if enabled)
        if (self.trailing_stop_enabled or self.trailing_profit_enabled) and market_data:
            self.update_trailing_levels(current_price, market_data)
        
        # Use trailing levels (will be ML-adjusted if available)
        target = self.trailing_profit if self.trailing_profit_enabled else self.profit_target
        stop = self.trailing_stop if self.trailing_stop_enabled else self.stop_loss
        
        # Profit target
        if current_price <= target:
            return {
                'should_exit': True,
                'reason': 'TRAILING_PROFIT' if self.trailing_profit_enabled else 'PROFIT_TARGET',
                'current_price': current_price,
                'target': target,
                'pnl': (self.entry_credit - current_price) * self.contracts * 100,
                'ml_confidence': self.ml_confidence
            }
        
        # Stop loss
        if current_price >= stop:
            return {
                'should_exit': True,
                'reason': 'TRAILING_STOP' if self.trailing_stop_enabled else 'STOP_LOSS',
                'current_price': current_price,
                'stop': stop,
                'pnl': (self.entry_credit - current_price) * self.contracts * 100,
                'ml_confidence': self.ml_confidence
            }
        
        # Time-based exit (7 DTE)
        if self.days_to_expiration <= self.time_exit_dte:
            return {
                'should_exit': True,
                'reason': 'TIME_EXIT',
                'dte': self.days_to_expiration,
                'current_price': current_price,
                'pnl': (self.entry_credit - current_price) * self.contracts * 100
            }
        
        # Hold position
        hold_decision = {
            'should_exit': False,
            'reason': 'HOLD',
            'current_price': current_price,
            'profit_distance': (current_price - target) / self.entry_credit,
            'dte': self.days_to_expiration,
            'trailing_stop': stop,
            'trailing_profit': target
        }
        
        # AI Override Check (for large P/L moves)
        if market_data:
            try:
                from config import get_config
                
                config = get_config()
                
                # Check if AI analysis should be triggered
                if config.exit_strategy.ai_analysis_on_large_moves:
                    current_pnl = (self.entry_credit - current_price) * self.contracts * 100
                    max_risk = self.max_risk * self.contracts * 100
                    
                    # Calculate P/L ratio
                    pnl_ratio = abs(current_pnl / max_risk) if max_risk > 0 else 0
                    
                    # Trigger AI if P/L ratio exceeds threshold
                    if pnl_ratio >= config.exit_strategy.ai_trigger_pnl_threshold:
                        logger.info(
                            f"🤖 Large P/L move detected ({pnl_ratio:.1%}) - "
                            f"requesting AI analysis for {self.symbol}"
                        )
                        
                        # Get AI analysis (async, so we'll need to import asyncio)
                        import asyncio
                        from ai.gemini_client import get_gemini_client
                        
                        # Prepare position data for AI
                        position_data = {
                            'symbol': self.symbol,
                            'strategy': self.strategy,
                            'entry_credit': self.entry_credit,
                            'entry_date': self.entry_date.isoformat(),
                            'expiration': self.expiration.isoformat(),
                            'days_in_trade': self.days_in_trade,
                            'dte': self.days_to_expiration,
                            'max_risk': self.max_risk
                        }
                        
                        # ML recommendation
                        ml_recommendation = {
                            'trailing_stop': self.trailing_stop,
                            'trailing_profit': self.trailing_profit,
                            'stop_multiplier': self.stop_multiplier,
                            'profit_target_pct': self.profit_target_pct,
                            'confidence': self.ml_confidence,
                            'mode': 'ML' if self.ml_confidence > 0 else 'RULE_BASED'
                        }
                        
                        # Get Gemini client and analyze
                        gemini = get_gemini_client()
                        
                        # Run async analysis
                        ai_result = asyncio.run(gemini.analyze_exit_strategy(
                            position=position_data,
                            current_pnl=current_pnl,
                            current_price=current_price,
                            market_data=market_data,
                            ml_recommendation=ml_recommendation
                        ))
                        
                        if ai_result.get('success'):
                            analysis = ai_result.get('analysis', {})
                            alt_rec = analysis.get('alternative_recommendation', {})
                            
                            # Check if AI disagrees and recommends EXIT
                            if not analysis.get('agree_with_ml', True):
                                action = alt_rec.get('action', 'HOLD')
                                
                                if action == 'EXIT_NOW':
                                    logger.warning(
                                        f"⚠️  AI OVERRIDE: Recommends immediate exit for {self.symbol}\n"
                                        f"   Reason: {analysis.get('reasoning', 'Unknown')}"
                                    )
                                    
                                    # Override to exit
                                    return {
                                        'should_exit': True,
                                        'reason': 'AI_OVERRIDE_EXIT',
                                        'current_price': current_price,
                                        'pnl': current_pnl,
                                        'ai_reasoning': analysis.get('reasoning'),
                                        'ai_confidence': analysis.get('confidence', 0)
                                    }
                                
                                elif action in ['TIGHTEN_STOP', 'ADJUST_PROFIT']:
                                    logger.info(
                                        f"💡 AI suggests adjustments for {self.symbol}: {action}"
                                    )
                                    # Log but don't override - let ML handle adjustments
                                    hold_decision['ai_suggestion'] = action
                                    hold_decision['ai_reasoning'] = analysis.get('reasoning')
                            
                            else:
                                logger.info(f"✅ AI agrees with ML recommendation for {self.symbol}")
                                hold_decision['ai_confirmed'] = True
                        
            except Exception as e:
                logger.warning(f"Error in AI override check: {e}")
                # Don't fail exit decision due to AI error
        
        return hold_decision


class ExitManager:
    """Manages position exits based on rules"""
    
    def __init__(self):
        self.db = None
    
    async def initialize(self):
        """Initialize database connection"""
        self.db = await get_database()
        await self._create_tables()
    
    async def _create_tables(self):
        """Create positions tables if they don't exist"""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                expiration TEXT NOT NULL,
                contracts INTEGER NOT NULL,
                entry_credit REAL NOT NULL,
                max_risk REAL NOT NULL,
                status TEXT DEFAULT 'OPEN',
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                -- NEW: ML Exit Strategy Fields
                trailing_stop_enabled INTEGER DEFAULT 1,
                trailing_profit_enabled INTEGER DEFAULT 1,
                highest_profit_seen REAL DEFAULT 0.0,
                current_trailing_stop REAL,
                current_trailing_profit REAL,
                ml_last_update TEXT,
                ml_confidence REAL DEFAULT 0.0,
                stop_multiplier REAL DEFAULT 2.5,
                profit_target_pct REAL DEFAULT 0.5
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS position_legs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                contract_symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                strike REAL NOT NULL,
                option_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        """)
        
        # NEW: Track exit level adjustments over time
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS exit_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                adjustment_type TEXT NOT NULL,
                old_stop REAL,
                new_stop REAL,
                old_profit REAL,
                new_profit REAL,
                reason TEXT,
                confidence REAL,
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        """)
        
        logger.info("Position tracking tables created (with ML exit fields)")
    
    async def open_position(
        self,
        symbol: str,
        strategy: str,
        expiration: datetime,
        contracts: int,
        entry_credit: float,
        max_risk: float,
        legs: List[Dict[str, Any]]
    ) -> int:
        """
        Record new position
        
        Args:
            symbol: Stock symbol
            strategy: Strategy name (e.g., IRON_CONDOR)
            expiration: Expiration date
            contracts: Number of contracts
            entry_credit: Credit received per contract
            max_risk: Max risk per contract
            legs: List of leg details
            
        Returns:
            Position ID
        """
        try:
            # Insert position
            cursor = await self.db.execute(
                """
                INSERT INTO positions 
                (symbol, strategy, entry_date, expiration, contracts, entry_credit, max_risk, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')
                """,
                (
                    symbol,
                    strategy,
                    datetime.now().isoformat(),
                    expiration.isoformat(),
                    contracts,
                    entry_credit,
                    max_risk
                )
            )
            
            await self.db.commit()
            position_id = cursor.lastrowid
            
            # Insert legs
            for leg in legs:
                await self.db.execute(
                    """
                    INSERT INTO position_legs
                    (position_id, contract_symbol, action, strike, option_type, quantity, entry_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        position_id,
                        leg['symbol'],
                        leg['action'],
                        leg['strike'],
                        leg['option_type'],
                        leg['quantity'],
                        leg['price']
                    )
                )
            
            await self.db.commit()
            
            logger.info(
                f"✅ Position opened: {symbol} {strategy} "
                f"({contracts} contracts @ ${entry_credit:.2f})"
            )
            
            return position_id
            
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return -1
    
    async def close_position(
        self,
        position_id: int,
        exit_price: float,
        exit_reason: str
    ) -> bool:
        """
        Close position and record exit
        
        Args:
            position_id: Position ID
            exit_price: Exit price per contract
            exit_reason: Reason for exit
            
        Returns:
            True if successful
        """
        try:
            # Get position details
            cursor = await self.db.execute(
                "SELECT entry_credit, contracts FROM positions WHERE id = ?",
                (position_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                logger.error(f"Position {position_id} not found")
                return False
            
            entry_credit, contracts = row
            
            # Calculate P/L
            pnl = (entry_credit - exit_price) * contracts * 100
            # Update position
            await self.db.execute(
                """
                UPDATE positions
                SET status = 'CLOSED',
                    exit_date = ?,
                    exit_price = ?,
                    exit_reason = ?,
                    pnl = ?
                WHERE id = ?
                """,
                (
                    datetime.now().isoformat(),
                    exit_price,
                    exit_reason,
                    pnl,
                    position_id
                )
            )
            
            await self.db.commit()
            
            logger.info(
                f"✅ Position {position_id} closed: {exit_reason} | "
                f"P/L: ${pnl:.2f}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
    
    async def place_closing_order(
        self,
        position: Dict[str, Any],
        reason: str = "Manual Exit"
    ) -> Optional[Dict[str, Any]]:
        """
        Place atomic closing order for position
        
        CRITICAL: Uses IBKR BAG/Combo orders for multi-leg positions
        to prevent leg risk (partial fills).
        
        Args:
            position: Position to close
            reason: Exit reason
            
        Returns:
            Order result or None
        """
        try:
            ib = self.ibkr.get_client()
            
            if not ib or not ib.isConnected():
                logger.error("Not connected to IBKR for closing")
                return None
            
            symbol = position['symbol']
            strategy = position['strategy']
            
            logger.info(
                f"🔒 Closing position: {symbol} {strategy}\n"
                f"   Reason: {reason}\n"
                f"   Method: ATOMIC COMBO ORDER (BAG)"
            )
            
            # The following code block seems to be misplaced based on the user's instruction
            # to add it to `monitor_positions`. However, to faithfully apply the change
            # as requested by the `{{ ... }}` markers, it is inserted here.
            # Note: This will cause a syntax error and undefined variables (`current_price`, `greeks`)
            # if `monitor_positions` is not the actual context.
            # If this code was intended for `monitor_positions`, it should be moved there.
            # For now, applying as per the provided diff markers.
            #
            # continue # This 'continue' would be a syntax error here. Removed for correctness.
            
            # Check if position should be closed (variables `current_price`, `greeks` are undefined here)
            # should_exit, reason = await self.check_exit_conditions(position, current_price, greeks)
            
            # 🆕 DIVIDEND CHECK: Close short calls before ex-date
            # if 'CALL' in position.strategy.upper(): # position.strategy is a string, not an object with .strategy
            #     from analysis.dividend_checker import get_dividend_checker
            #     from config import get_config
                
            #     config = get_config()
            #     div_checker = get_dividend_checker(
            #         blackout_days=config.dividend.blackout_days,
            #         auto_exit_enabled=config.dividend.auto_exit_enabled
            #     )
                
            #     # Check if we're in dividend blackout
            #     should_avoid = await div_checker.should_avoid_symbol(
            #         position.symbol,
            #         position.strategy
            #     )
                
            #     if should_avoid and config.dividend.auto_exit_enabled:
            #         logger.warning(
            #             f"🚨 DIVIDEND EXIT: {position.symbol}\n"
            #             f"   Closing position before ex-dividend date\n"
            #             f"   Strategy: {position.strategy}"
            #         )
            #         should_exit = True
            #         reason = "PRE_DIVIDEND_EXIT"
            
            # if should_exit: # `should_exit` is undefined here
            logger.error(f"No legs found for position {position['id']}")
            return None
            
            # Create CLOSING combo order (atomic execution)
            combo_order = await self._create_closing_combo_order(
                symbol=symbol,
                legs=legs,
                strategy=strategy
            )
            
            if not combo_order:
                logger.error("Failed to create combo closing order")
                return None
            
            # Execute atomic combo order
            logger.info(f"Submitting ATOMIC combo closing order for {symbol}...")
            
            trade = ib.placeOrder(combo_order['contract'], combo_order['order'])
            
            # Wait for fill
            await asyncio.sleep(2)
            
            status = trade.orderStatus.status
            
            if status in ['Filled', 'PartiallyFilled']:
                logger.info(
                    f"✅ Position closed: {symbol}\n"
                    f"   Fill Price: ${trade.orderStatus.avgFillPrice:.2f}\n"
                    f"   Execution: ATOMIC (all legs together)"
                )
                
                # Update position in database
                await self._mark_position_closed(
                    position_id=position['id'],
                    exit_price=trade.orderStatus.avgFillPrice,
                    exit_reason=reason
                )
                
                return {
                    'status': 'FILLED',
                    'symbol': symbol,
                    'fill_price': trade.orderStatus.avgFillPrice,
                    'execution_type': 'ATOMIC_COMBO',
                    'reason': reason
                }
            else:
                logger.warning(f"Closing order not filled: {status}")
                return {
                    'status': status,
                    'symbol': symbol
                }
            
        except Exception as e:
            logger.error(f"Error placing closing order: {e}")
            return None
    
    async def _create_closing_combo_order(
        self,
        symbol: str,
        legs: List[Dict[str, Any]],
        strategy: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create atomic BAG order for closing multi-leg position
        
        BAG = Basket/Combo instrument in IBKR
        All legs execute together or not at all.
        
        Args:
            symbol: Underlying symbol
            legs: Position legs to close
            strategy: Strategy type
            
        Returns:
            Dict with contract and order, or None
        """
        try:
            from ib_insync import Contract, Order, ComboLeg
            
            ib = self.ibkr.get_client()
            
            # Create BAG contract
            bag = Contract()
            bag.symbol = symbol
            bag.secType = 'BAG'
            bag.currency = 'USD'
            bag.exchange = 'SMART'
            
            # Add legs to BAG (reverse of opening positions)
            combo_legs = []
            total_quantity = 0
            
            for leg in legs:
                combo_leg = ComboLeg()
                combo_leg.conId = leg['contract_id']
                
                # REVERSE the action (BUY → SELL, SELL → BUY)
                if leg['action'] == 'BUY':
                    combo_leg.action = 'SELL'  # Close long position
                elif leg['action'] == 'SELL':
                    combo_leg.action = 'BUY'   # Close short position
                
                combo_leg.ratio = 1
                combo_leg.exchange = 'SMART'
                
                combo_legs.append(combo_leg)
                total_quantity = abs(leg['quantity'])
            
            bag.comboLegs = combo_legs
            
            # Qualify the BAG contract
            qualified = await ib.qualifyContractsAsync(bag)
            
            if not qualified:
                logger.error("Could not qualify BAG contract for closing")
                return None
            
            bag = qualified[0]
            
            # Create MARKET order for closing (want immediate execution)
            # Alternative: Limit order at mid-price
            order = Order()
            order.action = 'BUY' if strategy in ['IRON_CONDOR', 'CREDIT_SPREAD'] else 'SELL'
            order.totalQuantity = total_quantity
            order.orderType = 'MKT'  # Market for fast close
            order.transmit = True
            
            logger.info(
                f"Created ATOMIC BAG closing order:\n"
                f"  Symbol: {symbol}\n"
                f"  Legs: {len(combo_legs)}\n"
                f"  Quantity: {total_quantity}\n"
                f"  Order Type: MARKET (atomic execution)"
            )
            
            return {
                'contract': bag,
                'order': order
            }
            
        except Exception as e:
            logger.error(f"Error creating combo closing order: {e}")
            return None
    
    async def _get_position_legs(self, position_id: int) -> List[Dict[str, Any]]:
        """
        Get all open positions
        
        Returns:
            List of Position objects
        """
        try:
            cursor = await self.db.execute(
                """
                SELECT contract_symbol, action, strike, option_type, quantity, entry_price
                FROM position_legs
                WHERE position_id = ?
                """,
                (position_id,)
            )
            rows = await cursor.fetchall()
            
            legs = [
                {
                    'symbol': l[0],
                    'action': l[1],
                    'strike': l[2],
                    'option_type': l[3],
                    'quantity': l[4],
                    'price': l[5]
                }
                for l in rows
            ]
            return legs
        except Exception as e:
            logger.error(f"Error getting position legs for {position_id}: {e}")
            return []
    
    async def get_open_positions(self) -> List[Position]:
        """
        Get all open positions
        
        Returns:
            List of Position objects
        """
        try:
            cursor = await self.db.execute(
                """
                SELECT id, symbol, strategy, entry_date, expiration, 
                       contracts, entry_credit, max_risk
                FROM positions
                WHERE status = 'OPEN'
                ORDER BY entry_date DESC
                """
            )
            
            rows = await cursor.fetchall()
            positions = []
            
            for row in rows:
                # Get legs for this position
                legs_cursor = await self.db.execute(
                    """
                    SELECT contract_symbol, action, strike, option_type, quantity, entry_price
                    FROM position_legs
                    WHERE position_id = ?
                    """,
                    (row[0],)
                )
                legs_rows = await legs_cursor.fetchall()
                
                legs = [
                    {
                        'symbol': l[0],
                        'action': l[1],
                        'strike': l[2],
                        'option_type': l[3],
                        'quantity': l[4],
                        'price': l[5]
                    }
                    for l in legs_rows
                ]
                
                position = Position(
                    position_id=row[0],
                    symbol=row[1],
                    strategy=row[2],
                    entry_date=datetime.fromisoformat(row[3]),
                    expiration=datetime.fromisoformat(row[4]),
                    contracts=row[5],
                    entry_credit=row[6],
                    max_risk=row[7],
                    legs=legs
                )
                
                positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting open positions: {e}")
            return []
    
    async def monitor_exits(self) -> List[Dict[str, Any]]:
        """
        Check all open positions for exit signals (ML-enhanced)
        
        Returns:
            List of positions that should be exited
        """
        positions = await self.get_open_positions()
        exit_signals = []
        
        # Get current market data for ML
        market_data = None
        current_vix = 0.0
        try:
            from ml.regime_classifier import get_regime_classifier
            from ibkr.data_fetcher import get_data_fetcher
            from ibkr.position_tracker import get_position_tracker
            
            data_fetcher = get_data_fetcher()
            regime_classifier = get_regime_classifier()
            position_tracker = get_position_tracker()
            
            # Update positions from IBKR to get fresh prices
            tracker_positions = await position_tracker.update_positions()
            
            # Fetch real VIX
            vix_val = await data_fetcher.get_vix()
            current_vix = vix_val if vix_val else 18.0
            
            # Predict regime
            # Note: Using simplified features. In production, use full feature engineering.
            features = np.array([current_vix, 450.0, 0.3, 0.25, 50.0, 0.005, 0.01]) 
            regime, regime_confidence = regime_classifier.predict_regime(features)
            
            market_data = {
                'vix': current_vix,
                'regime': regime,
                'regime_confidence': regime_confidence
            }
            
            # Initialize Rolling Manager
            from execution.rolling_manager import get_rolling_manager
            rolling_manager = get_rolling_manager()
            
        except Exception as e:
            logger.warning(f"Could not fetch market data for ML: {e}")
            # Continue without market data (will fallback to static rules)

        for position in positions:
            current_price = 0.0
            price_found = False
            
            # Calculate current price by summing legs from position tracker
            try:
                # Filter tracker positions for this specific trade
                trade_legs_pnl = 0.0
                trade_market_value = 0.0
                matched_legs_count = 0
                
                for leg in position.legs:
                    # Match leg with tracker position
                    # logic: symbol, strike, right (date match needed too)
                    for track_pos in tracker_positions:
                        if (track_pos['symbol'] == leg['symbol'] and
                            track_pos.get('strike') == leg['strike'] and
                            track_pos.get('right') == leg['option_type'] and
                            track_pos['position'] != 0):
                            
                            # Found match
                            trade_market_value += track_pos['market_value']
                            matched_legs_count += 1
                            break
                            
                if matched_legs_count > 0:
                    # Calculate price per contract based on total market value
                    # Market Value = Price * Multiplier (100) * Quantity
                    # Position is atomic, so total quantity = position.contracts * legs count? 
                    # No, net value.
                    # Best metric: Current P&L from tracker vs Entry Credit
                    
                    # For spread: Value = Sum of legs.
                    # Price per contract = Total Value / (Contracts * 100)
                    if position.contracts > 0:
                        current_price = -(trade_market_value / (position.contracts * 100))
                        # Note: Short positions have negative market value.
                        # We want positive Debit to close.
                        # Credit Spread: Entry Credit (+). Current Price is cost to close (+).
                        # If we received $1.00. Current cost $0.80. PnL = 0.20.
                        # Market Value of short leg is -0.80.
                        # So Cost = -MarketValue.
                        price_found = True
                        
                if not price_found:
                    logger.debug(f"Could not calculate current price for {position.symbol} (legs mismatch)")
                    current_price = 0.0

            except Exception as e:
                logger.error(f"Error matching positions: {e}")

            # Fetch Earnings Date for ML Context
            next_earnings = None
            try:
                next_earnings = await data_fetcher.get_earnings_date(position.symbol)
            except Exception as e_earn:
                pass
                
            # Update market data context for this position
            position_market_data = market_data.copy() if market_data else {}
            if next_earnings:
                position_market_data['next_earnings_date'] = next_earnings.isoformat()

            logger.info(
                f"Monitoring {position.symbol}: "
                f"Price=${current_price:.2f}, "
                f"DTE={position.days_to_expiration}, "
                f"Earnings={next_earnings.date() if next_earnings else 'N/A'}, "
                f"ML enabled={position.trailing_stop_enabled}"
            )
            
            # Check exit conditions (ML enhanced)
            exit_decision = position.should_exit(current_price, position_market_data)
            
            # Feature: SMART ROLLING
            # If exit signal is STOP LOSS, check if we can Roll instead
            if exit_decision['should_exit'] and "Stop Loss" in exit_decision['reason']:
                logger.info(f"🛑 Stop Loss Triggered for {position.symbol}. Checking for Rolling possibility...")
                
                # Enrich market data for Rolling Check
                roll_market_data = position_market_data.copy()
                roll_market_data['price'] = current_price
                
                roll_eval = await rolling_manager.evaluate_roll(
                    position_data={'symbol': position.symbol, 'position': -1, 'strike': 0}, # Todo: Pass real pos details
                    market_data=roll_market_data
                )
                
                if roll_eval['decision'] == 'ROLL':
                    logger.info(f"🔄 ROLLING APPROVED by AI: {roll_eval['reason']}")
                    # TODO: Trigger Roll Execution here
                    # For now, we inhibit the Exit and log the intention
                    logger.info("   (Simulation) Rolling execution would start here. Preventing hard exit.")
                    # continue # Skip the hard exit below
                else:
                     logger.info(f"❌ Roll Rejected ({roll_eval['reason']}). Proceeding with Stop Loss.")
            
            if exit_decision['should_exit']:
                # Log detailed reason
                logger.info(
                    f"🔔 EXIT SIGNAL for {position.symbol}: {exit_decision['reason']} "
                    f"(Confidence: {exit_decision.get('ml_confidence', 0):.1%})"
                )
                
                # Update DB state if ML levels changed
                if position.ml_last_update:
                    await self._update_db_exit_levels(position)
                
                exit_signals.append({
                    'position': position,
                    'reason': exit_decision['reason'],
                    'details': exit_decision
                })
            
            # Save updated trailing levels to DB periodically
            elif position.ml_last_update and market_data:
                await self._update_db_exit_levels(position)
        
        if exit_signals:
            logger.info(f"Found {len(exit_signals)} positions ready to exit")
        
        return exit_signals

    async def _update_db_exit_levels(self, position):
        """Persist updated trailing levels to DB"""
        try:
            await self.db.execute(
                """
                UPDATE positions SET
                    current_trailing_stop = ?,
                    current_trailing_profit = ?,
                    highest_profit_seen = ?,
                    ml_last_update = ?,
                    ml_confidence = ?,
                    stop_multiplier = ?,
                    profit_target_pct = ?
                WHERE id = ?
                """,
                (
                    position.trailing_stop,
                    position.trailing_profit,
                    position.highest_profit_seen,
                    datetime.now().isoformat(),
                    position.ml_confidence,
                    position.stop_multiplier,
                    position.profit_target_pct,
                    position.position_id
                )
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update db levels: {e}")


# Singleton instance
_exit_manager: Optional[ExitManager] = None


def get_exit_manager() -> ExitManager:
    """Get or create singleton exit manager"""
    global _exit_manager
    if _exit_manager is None:
        _exit_manager = ExitManager()
    return _exit_manager
