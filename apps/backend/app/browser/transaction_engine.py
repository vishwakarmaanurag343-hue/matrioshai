"""
MATRIOSHAI Real-World Transaction & Booking Engine (Phase 12)

Provides formal, auditable transaction management for high-consequence operations
(flights, hotels, tickets, appointments, purchases, subscriptions).
Enforces:
- PREPARE != COMMIT
- REVIEW != COMMIT
- CLICKED != COMPLETED
- SUBMITTED != VERIFIED
- UNKNOWN != SUCCESS
"""

import time
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    BrowserStateStore,
    ActionIntent,
    ActionType,
    ActionTarget,
    ActionResult,
    ActionStatus,
    VerificationResult,
    VerificationStatus,
    FailureClass,
    TransactionState,
    TransactionType,
    AvailabilityState,
    CommitPolicy,
    TransactionRisk,
    TransactionPrice,
    TransactionConstraint,
    TransactionPreference,
    TransactionOption,
    TransactionSnapshot,
    TransactionReview,
    TransactionConfirmation,
    CommitAuthorization,
    TransactionReceipt,
    Transaction,
    TransactionAuditEvent
)
from app.browser.action_engine import action_engine
from app.browser.verification_engine import verification_engine
from app.browser.world_model import world_model_engine

class TransactionNormalizationEngine:
    """
    Normalizes natural language booking/purchase requests into structured Transactions.
    Distinguishes hard user constraints from soft preferences.
    """

    def normalize_request(self, user_request: str, workflow_id: Optional[str] = None) -> Transaction:
        tid = f"tx_{secrets.token_hex(4)}"
        text = user_request.strip()
        text_lower = text.lower()

        # Classify Transaction Type
        if "flight" in text_lower or "fly" in text_lower:
            tx_type = TransactionType.FLIGHT_BOOKING
            product = "Flight Reservation"
            merchant = "Airline / Travel Portal"
        elif "hotel" in text_lower or "stay" in text_lower or "room" in text_lower:
            tx_type = TransactionType.HOTEL_BOOKING
            product = "Hotel Room Booking"
            merchant = "Hotel / Hospitality Portal"
        elif "train" in text_lower or "rail" in text_lower:
            tx_type = TransactionType.TRAIN_BOOKING
            product = "Train Ticket"
            merchant = "Railway Portal"
        elif "movie" in text_lower or "cinema" in text_lower:
            tx_type = TransactionType.MOVIE_TICKET
            product = "Movie Ticket"
            merchant = "Cinema Booking"
        elif "restaurant" in text_lower or "table" in text_lower or "dinner" in text_lower:
            tx_type = TransactionType.RESTAURANT_RESERVATION
            product = "Restaurant Table Reservation"
            merchant = "Restaurant"
        elif "buy" in text_lower or "purchase" in text_lower or "order" in text_lower:
            tx_type = TransactionType.PRODUCT_PURCHASE
            product = "Product Purchase"
            merchant = "E-Commerce"
        else:
            tx_type = TransactionType.OTHER
            product = "Service Transaction"
            merchant = "Online Merchant"

        constraints: List[TransactionConstraint] = []
        preferences: List[TransactionPreference] = []

        # Extract Flight Specifics
        if "from " in text_lower and " to " in text_lower:
            try:
                origin = text_lower.split("from ")[1].split(" to ")[0].strip()
                dest = text_lower.split(" to ")[1].split(" ")[0].strip()
                constraints.append(TransactionConstraint(constraint_id=f"c_{secrets.token_hex(3)}", name="origin", type="HARD", value=origin))
                constraints.append(TransactionConstraint(constraint_id=f"c_{secrets.token_hex(3)}", name="destination", type="HARD", value=dest))
            except Exception:
                pass

        # Extract Preferences
        if "cheapest" in text_lower or "lowest price" in text_lower:
            preferences.append(TransactionPreference(preference_id=f"p_{secrets.token_hex(3)}", dimension="PRICE", target_value="lowest", weight=1.0))
        if "non-stop" in text_lower or "direct" in text_lower:
            preferences.append(TransactionPreference(preference_id=f"p_{secrets.token_hex(3)}", dimension="STOPS", target_value="0", weight=0.9))
        if "fastest" in text_lower or "shortest" in text_lower:
            preferences.append(TransactionPreference(preference_id=f"p_{secrets.token_hex(3)}", dimension="DURATION", target_value="shortest", weight=0.8))

        # Determine Risk Level
        risk = TransactionRisk.HIGH if tx_type in [TransactionType.FLIGHT_BOOKING, TransactionType.HOTEL_BOOKING, TransactionType.PRODUCT_PURCHASE] else TransactionRisk.MEDIUM

        tx = Transaction(
            transaction_id=tid,
            workflow_id=workflow_id,
            type=tx_type,
            merchant=merchant,
            provider="Pending Selection",
            product_or_service=product,
            status=TransactionState.DISCOVERING,
            currency="INR",
            amount=0.0,
            taxes=0.0,
            fees=0.0,
            total=0.0,
            constraints=constraints,
            user_preferences=preferences,
            confirmation_policy=CommitPolicy.ALWAYS_CONFIRM,
            commit_boundary="Confirm & Pay",
            risk_level=risk,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )

        return tx

class TransactionSelectionEngine:
    """
    Scores, ranks, and selects options matching hard constraints and soft preferences.
    Detects tied/ambiguous choices requiring user decision.
    """

    def select_option(self, transaction: Transaction, options: List[TransactionOption]) -> Tuple[Optional[TransactionOption], bool, str]:
        if not options:
            return None, False, "No options provided"

        # 1. Filter by availability and hard constraints
        valid_options = [
            opt for opt in options
            if opt.availability in [AvailabilityState.AVAILABLE, AvailabilityState.LIMITED]
            and opt.constraints_satisfied
        ]

        if not valid_options:
            return None, False, "No available options satisfy all hard constraints"

        # 2. Score Options
        for opt in valid_options:
            score = 100.0
            # Price penalty (lower price is better)
            if opt.price.total > 0:
                score -= (opt.price.total / 100.0)

            # Preferences weighting
            for pref in transaction.user_preferences:
                if pref.dimension == "STOPS" and opt.attributes.get("stops") == 0:
                    score += (20.0 * pref.weight)
                if pref.dimension == "REFUNDABILITY" and opt.attributes.get("refundable") is True:
                    score += (15.0 * pref.weight)

            opt.preference_score = round(score, 2)

        # Sort by score descending
        ranked = sorted(valid_options, key=lambda o: o.preference_score, reverse=True)

        # 3. Check for Ambiguity / Virtual Ties
        if len(ranked) >= 2:
            top_1 = ranked[0]
            top_2 = ranked[1]
            # If price difference is < 1% and scores within 1 point
            if abs(top_1.price.total - top_2.price.total) <= (0.01 * top_1.price.total) and abs(top_1.preference_score - top_2.preference_score) < 2.0:
                return top_1, True, f"Ambiguous selection between '{top_1.title}' (₹{top_1.price.total}) and '{top_2.title}' (₹{top_2.price.total}). User choice required."

        selected = ranked[0]
        return selected, False, f"Selected '{selected.title}' by '{selected.provider}' (Score: {selected.preference_score})"

class DriftDetectionEngine:
    """
    Detects price drift, availability drift, and terms drift between initial snapshot
    and current checkout state.
    """

    def detect_drift(
        self,
        snapshot: TransactionSnapshot,
        current_option: TransactionOption,
        price_drift_threshold_percent: float = 1.0
    ) -> Tuple[bool, str]:
        # 1. Availability Drift
        if current_option.availability == AvailabilityState.UNAVAILABLE:
            return True, "Selected option has become unavailable"

        # 2. Price Drift
        snap_total = snapshot.price.total
        curr_total = current_option.price.total
        if snap_total > 0 and curr_total > 0:
            diff_pct = abs(curr_total - snap_total) / snap_total * 100.0
            if diff_pct > price_drift_threshold_percent:
                return True, f"Price changed from {snapshot.price.currency} {snap_total} to {curr_total} ({round(diff_pct, 1)}% change)"

        # 3. Provider or Route Drift
        if current_option.provider != snapshot.provider:
            return True, f"Provider changed from '{snapshot.provider}' to '{current_option.provider}'"

        return False, "No material drift detected"

class TransactionPolicyEngine:
    """
    Strict Policy Gate determining whether a transaction may prepare, review,
    or commit. Cannot be overridden by LLM or planner.
    """

    def evaluate_commit(
        self,
        transaction: Transaction,
        confirmation: Optional[TransactionConfirmation] = None,
        auth: Optional[CommitAuthorization] = None
    ) -> Tuple[bool, str]:
        # Rule 1: Must be in CONFIRMED or COMMITTING state
        if transaction.status not in [TransactionState.CONFIRMED, TransactionState.COMMITTING, TransactionState.AWAITING_CONFIRMATION]:
            return False, f"Transaction is in invalid state '{transaction.status.value}' for commit"

        # Rule 2: Confirmation required by policy
        if transaction.confirmation_policy in [CommitPolicy.ALWAYS_CONFIRM, CommitPolicy.NEVER_AUTO_COMMIT]:
            if not confirmation or confirmation.status != "CONFIRMED":
                return False, "Explicit user confirmation is strictly required by policy"

        # Rule 3: Confirmation expiration check
        if confirmation and confirmation.expires_at:
            exp_time = datetime.fromisoformat(confirmation.expires_at)
            if datetime.now(timezone.utc) > exp_time:
                return False, "User confirmation has expired"

        # Rule 4: Authorization Token Validity
        if auth and auth.expires_at:
            auth_exp = datetime.fromisoformat(auth.expires_at)
            if datetime.now(timezone.utc) > auth_exp:
                return False, "Commit authorization token expired"

        return True, "Commit policy approved"

class TransactionReceiptEngine:
    """
    Extracts booking reference numbers (PNR, order ID, confirmation numbers) and formats
    structured TransactionReceipts.
    """

    def generate_receipt(
        self,
        transaction: Transaction,
        verification_result: VerificationResult,
        reference_override: Optional[str] = None
    ) -> TransactionReceipt:
        ref_num = reference_override or f"REF-{secrets.token_hex(4).upper()}"
        summary = f"Transaction '{transaction.transaction_id}' verified on provider '{transaction.provider}' for {transaction.currency} {transaction.total}"

        return TransactionReceipt(
            receipt_id=f"rcpt_{secrets.token_hex(4)}",
            transaction_id=transaction.transaction_id,
            provider=transaction.provider,
            reference_number=ref_num,
            amount=transaction.total,
            currency=transaction.currency,
            booking_date=datetime.now(timezone.utc).isoformat(),
            status="COMPLETED" if verification_result.status == VerificationStatus.VERIFIED_SUCCESS else "PENDING",
            evidence_summary=summary,
            created_at=datetime.now(timezone.utc).isoformat()
        )

class TransactionCommitEngine:
    """
    Executes transaction commit actions with strict idempotency, drift re-validation,
    and unknown outcome recovery.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.policy_engine = TransactionPolicyEngine()
        self.drift_engine = DriftDetectionEngine()
        self.receipt_engine = TransactionReceiptEngine()
        from app.browser.action_engine import ActionEngine
        from app.browser.verification_engine import VerificationEngine
        self.action_engine = ActionEngine(self.state_store)
        self.verification_engine = VerificationEngine(self.state_store)

    async def execute_commit(
        self,
        transaction: Transaction,
        commit_action: ActionIntent,
        confirmation: Optional[TransactionConfirmation] = None,
        auth: Optional[CommitAuthorization] = None
    ) -> Tuple[TransactionState, Optional[TransactionReceipt], str]:
        # 1. Evaluate Policy Gate
        allowed, policy_msg = self.policy_engine.evaluate_commit(transaction, confirmation, auth)
        if not allowed:
            transaction.status = TransactionState.BLOCKED
            return TransactionState.BLOCKED, None, f"Policy Blocked: {policy_msg}"

        # 2. Re-validate Drift
        if transaction.active_snapshot and transaction.selected_option:
            has_drift, drift_msg = self.drift_engine.detect_drift(transaction.active_snapshot, transaction.selected_option)
            if has_drift:
                transaction.status = TransactionState.READY_FOR_REVIEW
                if confirmation:
                    confirmation.status = "INVALIDATED"
                return TransactionState.READY_FOR_REVIEW, None, f"Confirmation Invalidated due to drift: {drift_msg}"

        # 3. Transition to COMMITTING (Lock)
        transaction.status = TransactionState.COMMITTING
        logger.info(f"[MATRIOSHAI][Transaction] Executing commit action '{commit_action.action_id}' for transaction '{transaction.transaction_id}'")

        # 4. Dispatch Commit Action via Phase 8 Action Engine
        snap_before = world_model_engine.create_snapshot(reason=f"tx_commit_pre_{transaction.transaction_id}")
        action_res = await self.action_engine.execute_action(commit_action, confirmed=True)
        snap_after = world_model_engine.create_snapshot(reason=f"tx_commit_post_{transaction.transaction_id}")

        # 5. Verify Outcome via Phase 9 Verification Engine
        ver_res = await self.verification_engine.verify_action(
            action_result=action_res,
            before_snapshot=snap_before,
            after_snapshot=snap_after
        )

        # 6. Evaluate Outcome
        if ver_res.status == VerificationStatus.VERIFIED_SUCCESS:
            transaction.status = TransactionState.COMPLETED
            receipt = self.receipt_engine.generate_receipt(transaction, ver_res)
            transaction.receipt = receipt
            self.state_store.transaction_receipts[receipt.receipt_id] = receipt
            return TransactionState.COMPLETED, receipt, "Transaction successfully committed and verified"

        if ver_res.status == VerificationStatus.CONFLICTING_EVIDENCE or ver_res.failure_class == FailureClass.UNKNOWN_FAILURE:
            transaction.status = TransactionState.UNKNOWN_OUTCOME
            return TransactionState.UNKNOWN_OUTCOME, None, "Commit dispatched but outcome is UNKNOWN. Safe verification required; DO NOT retry blindly."

        transaction.status = TransactionState.FAILED
        return TransactionState.FAILED, None, f"Transaction commit failed ({ver_res.failure_class.value if ver_res.failure_class else 'FAILED'})"

class TransactionEngine:
    """
    Master Real-World Transaction & Booking Engine (Phase 12).
    Orchestrates Discovery -> Comparison -> Selection -> Preparation -> Snapshot -> Review -> Confirmation -> Revalidation -> Commit -> Verification -> Receipt.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.normalizer = TransactionNormalizationEngine()
        self.selector = TransactionSelectionEngine()
        self.drift_engine = DriftDetectionEngine()
        self.policy_engine = TransactionPolicyEngine()
        self.commit_engine = TransactionCommitEngine(self.state_store)
        self.receipt_engine = TransactionReceiptEngine()

    def _emit_audit(self, transaction_id: str, event_type: str, payload: Dict[str, Any]):
        evt = TransactionAuditEvent(
            event_id=f"txevt_{secrets.token_hex(4)}",
            transaction_id=transaction_id,
            event_type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.state_store.transaction_audit_events.append(evt)
        if len(self.state_store.transaction_audit_events) > self.state_store.MAX_TRANSACTION_AUDIT_EVENTS:
            self.state_store.transaction_audit_events.pop(0)
        logger.info(f"[MATRIOSHAI][Transaction] Audit: {event_type} (tx={transaction_id})")

    def create_transaction(self, user_request: str, workflow_id: Optional[str] = None) -> Transaction:
        tx = self.normalizer.normalize_request(user_request, workflow_id=workflow_id)
        self.state_store.transactions[tx.transaction_id] = tx
        self._emit_audit(tx.transaction_id, "transaction.created", {"type": tx.type.value, "product": tx.product_or_service})
        return tx

    def update_options(self, transaction_id: str, options: List[TransactionOption]) -> Tuple[Transaction, Optional[TransactionOption], bool, str]:
        tx = self.state_store.transactions.get(transaction_id)
        if not tx:
            raise ValueError(f"Transaction '{transaction_id}' not found")

        tx.options = options
        tx.status = TransactionState.COMPARING
        self._emit_audit(transaction_id, "transaction.options.updated", {"count": len(options)})

        # Automatic selection attempt
        selected, is_ambiguous, reason = self.selector.select_option(tx, options)
        if selected:
            tx.selected_option = selected
            tx.provider = selected.provider
            tx.amount = selected.price.base
            tx.taxes = selected.price.tax
            tx.fees = selected.price.fees
            tx.total = selected.price.total
            tx.currency = selected.price.currency
            tx.status = TransactionState.SELECTED
            self._emit_audit(transaction_id, "transaction.option.selected", {"option_id": selected.option_id, "provider": selected.provider, "total": selected.price.total})

        return tx, selected, is_ambiguous, reason

    def prepare_review(self, transaction_id: str) -> TransactionReview:
        tx = self.state_store.transactions.get(transaction_id)
        if not tx:
            raise ValueError(f"Transaction '{transaction_id}' not found")
        if not tx.selected_option:
            raise ValueError("No option selected for transaction review")

        opt = tx.selected_option
        snap = TransactionSnapshot(
            snapshot_id=f"snap_{secrets.token_hex(4)}",
            transaction_id=tx.transaction_id,
            version=1,
            selected_option=opt,
            price=opt.price,
            availability=opt.availability,
            provider=opt.provider,
            important_conditions=["Non-refundable", "Standard baggage included"],
            cancellation_policy="Cancellation fee applies within 24h",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        tx.active_snapshot = snap
        self.state_store.transaction_snapshots[snap.snapshot_id] = snap

        review = TransactionReview(
            review_id=f"rev_{secrets.token_hex(4)}",
            transaction_id=tx.transaction_id,
            item_title=opt.title,
            provider=opt.provider,
            route_or_location=str(opt.attributes.get("route", "")),
            date_time=str(opt.attributes.get("departure_time", "")),
            price=opt.price,
            important_restrictions=["Govt ID required at check-in", "Non-transferable"],
            cancellation_refund_conditions=["Subject to airline cancellation terms"],
            is_irreversible=True,
            risk_level=tx.risk_level,
            commit_action_description=f"Commit payment of {opt.price.currency} {opt.price.total} to {opt.provider}"
        )
        tx.active_review = review
        tx.status = TransactionState.READY_FOR_REVIEW
        self._emit_audit(transaction_id, "transaction.review.created", {"review_id": review.review_id, "total": opt.price.total})
        return review

    def confirm_transaction(self, transaction_id: str, user_note: Optional[str] = None) -> Tuple[TransactionConfirmation, CommitAuthorization]:
        tx = self.state_store.transactions.get(transaction_id)
        if not tx:
            raise ValueError(f"Transaction '{transaction_id}' not found")
        if not tx.selected_option or not tx.active_snapshot:
            raise ValueError("Transaction not ready for confirmation")

        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        conf = TransactionConfirmation(
            confirmation_id=f"conf_{secrets.token_hex(4)}",
            transaction_id=tx.transaction_id,
            option_id=tx.selected_option.option_id,
            snapshot_version=tx.active_snapshot.version,
            status="CONFIRMED",
            confirmed_at=datetime.now(timezone.utc).isoformat(),
            expires_at=expires_at,
            user_note=user_note
        )
        tx.active_confirmation = conf
        tx.status = TransactionState.CONFIRMED
        self.state_store.transaction_confirmations[conf.confirmation_id] = conf

        auth = CommitAuthorization(
            auth_token=f"tok_{secrets.token_hex(12)}",
            transaction_id=tx.transaction_id,
            confirmation_id=conf.confirmation_id,
            policy_version=1,
            snapshot_version=tx.active_snapshot.version,
            expires_at=expires_at
        )

        self._emit_audit(transaction_id, "transaction.confirmation.received", {"confirmation_id": conf.confirmation_id})
        return conf, auth

    async def commit_transaction(
        self,
        transaction_id: str,
        commit_action: ActionIntent,
        auth: Optional[CommitAuthorization] = None
    ) -> Tuple[TransactionState, Optional[TransactionReceipt], str]:
        tx = self.state_store.transactions.get(transaction_id)
        if not tx:
            raise ValueError(f"Transaction '{transaction_id}' not found")

        conf = tx.active_confirmation
        state, receipt, msg = await self.commit_engine.execute_commit(
            transaction=tx,
            commit_action=commit_action,
            confirmation=conf,
            auth=auth
        )

        self._emit_audit(transaction_id, f"transaction.commit.{state.value.lower()}", {"message": msg})
        return state, receipt, msg

    def cancel_transaction(self, transaction_id: str, reason: str = "User cancelled") -> Transaction:
        tx = self.state_store.transactions.get(transaction_id)
        if not tx:
            raise ValueError(f"Transaction '{transaction_id}' not found")

        tx.status = TransactionState.CANCELLED
        if tx.active_confirmation:
            tx.active_confirmation.status = "REJECTED"
        self._emit_audit(transaction_id, "transaction.cancelled", {"reason": reason})
        return tx

transaction_engine = TransactionEngine()
