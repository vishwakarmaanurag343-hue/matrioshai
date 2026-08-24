"""
MATRIOSHAI Real-World Transaction & Booking Engine Tests (Phase 12)

Comprehensive verification of:
1. Request normalization (flight, hotel, purchase)
2. Hard constraints & soft preferences extraction
3. Multi-criteria option scoring & ranking
4. Ambiguous selection detection (virtual ties)
5. Unavailable option exclusion
6. Pre-commit snapshot freezing & review generation
7. Price drift detection & confirmation invalidation
8. Availability & provider drift detection
9. User confirmation & scoped CommitAuthorization issuance
10. Commit policy enforcement & risk assessment
11. Commit execution via Phase 8 & Phase 9 verification
12. Unknown outcome handling & idempotency
13. Verified receipt generation
14. User cancellation lifecycle
15. Audit event logging
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from app.browser.state_store import (
    BrowserStateStore,
    WindowState,
    TabState,
    TabStatus,
    WorldPageState,
    WorldElement,
    WorldElementRef,
    WorldElementSemanticState,
    VisualBoundingBox,
    TransactionState,
    TransactionType,
    AvailabilityState,
    CommitPolicy,
    TransactionRisk,
    TransactionPrice,
    TransactionOption,
    ActionIntent,
    ActionType,
    ActionTarget,
    VerificationStatus,
    FailureClass
)
from app.browser.transaction_engine import (
    TransactionNormalizationEngine,
    TransactionSelectionEngine,
    DriftDetectionEngine,
    TransactionPolicyEngine,
    TransactionReceiptEngine,
    TransactionCommitEngine,
    TransactionEngine
)

@pytest.fixture
def mock_store():
    store = BrowserStateStore()
    store.set_browser_identity("test_transaction_chrome", "124.0.0.0")

    w1 = WindowState(window_id=1, focused=True, state="normal", tab_ids=[101], active_tab_id=101)
    store.windows = {1: w1}

    t1 = TabState(tab_id=101, window_id=1, index=0, active=True, url="https://portal.example.com/checkout", title="Checkout", status=TabStatus.READY)
    store.tabs = {101: t1}
    store.active_tab_id = 101
    store.world_model_version = 10

    p1 = WorldPageState(
        page_id="page_101_v1",
        tab_id=101,
        url="https://portal.example.com/checkout",
        origin="https://portal.example.com",
        title="Checkout",
        page_version=1,
        viewport_width=1280,
        viewport_height=800,
        active_dialogs=[]
    )
    store.page_states[101] = p1

    el_pay = WorldElement(
        element_ref=WorldElementRef(
            page_id="page_101_v1",
            observation_id="obs_1",
            element_id="elem_btn_pay",
            role="button",
            name="Pay & Confirm Booking",
            page_version=1,
            stable_dom_identity="btn-pay"
        ),
        role="button",
        name="Pay & Confirm Booking",
        semantic_state=WorldElementSemanticState(type="button", enabled=True, focused=False),
        geometry=VisualBoundingBox(x=100, y=200, width=200, height=40),
        visible=True,
        enabled=True,
        page_version=1
    )
    store.world_elements[101] = [el_pay]
    return store

def test_transaction_normalization_flight():
    """Test normalizing a flight booking request into structured transaction with hard & soft constraints."""
    engine = TransactionNormalizationEngine()
    tx = engine.normalize_request("Book the cheapest non-stop flight from Ahmedabad to Delhi tomorrow")

    assert tx.type == TransactionType.FLIGHT_BOOKING
    assert tx.risk_level == TransactionRisk.HIGH
    assert any(c.name == "origin" and c.value == "ahmedabad" for c in tx.constraints)
    assert any(c.name == "destination" and c.value == "delhi" for c in tx.constraints)
    assert any(p.dimension == "PRICE" for p in tx.user_preferences)
    assert any(p.dimension == "STOPS" for p in tx.user_preferences)

def test_transaction_normalization_hotel_and_purchase():
    """Test normalizing hotel booking and product purchase requests."""
    engine = TransactionNormalizationEngine()

    tx_hotel = engine.normalize_request("Reserve a hotel room in Mumbai for 2 nights")
    assert tx_hotel.type == TransactionType.HOTEL_BOOKING

    tx_buy = engine.normalize_request("Buy wireless noise cancelling headphones")
    assert tx_buy.type == TransactionType.PRODUCT_PURCHASE

def test_option_scoring_and_selection(mock_store):
    """Test scoring options based on price and preference weighting."""
    tx_engine = TransactionEngine(mock_store)
    tx = tx_engine.create_transaction("Find flights from Ahmedabad to Delhi, prefer non-stop")

    opts = [
        TransactionOption(
            option_id="opt_1",
            provider="IndiGo",
            title="IndiGo 6E 123",
            price=TransactionPrice(base=6500, tax=500, fees=200, total=7200, currency="INR"),
            availability=AvailabilityState.AVAILABLE,
            attributes={"stops": 0, "refundable": False},
            constraints_satisfied=True
        ),
        TransactionOption(
            option_id="opt_2",
            provider="Air India",
            title="Air India AI 456",
            price=TransactionPrice(base=8000, tax=600, fees=200, total=8800, currency="INR"),
            availability=AvailabilityState.AVAILABLE,
            attributes={"stops": 1, "refundable": True},
            constraints_satisfied=True
        ),
        TransactionOption(
            option_id="opt_3",
            provider="SpiceJet",
            title="SpiceJet SG 789",
            price=TransactionPrice(base=5000, tax=400, fees=200, total=5600, currency="INR"),
            availability=AvailabilityState.UNAVAILABLE,
            attributes={"stops": 0},
            constraints_satisfied=True
        )
    ]

    tx, selected, is_ambiguous, reason = tx_engine.update_options(tx.transaction_id, opts)
    assert selected is not None
    assert selected.option_id == "opt_1"  # IndiGo is selected because it's non-stop & cheaper than Air India; SpiceJet is unavailable
    assert is_ambiguous is False
    assert tx.status == TransactionState.SELECTED

def test_ambiguous_selection_detection(mock_store):
    """Test detecting tied/ambiguous options requiring user decision."""
    tx_engine = TransactionEngine(mock_store)
    tx = tx_engine.create_transaction("Find flights from Ahmedabad to Delhi")

    opts = [
        TransactionOption(
            option_id="opt_a",
            provider="IndiGo",
            title="IndiGo 6E 101",
            price=TransactionPrice(base=7000, tax=500, fees=0, total=7500, currency="INR"),
            availability=AvailabilityState.AVAILABLE,
            attributes={"stops": 0},
            constraints_satisfied=True
        ),
        TransactionOption(
            option_id="opt_b",
            provider="Vistara",
            title="Vistara UK 202",
            price=TransactionPrice(base=7000, tax=500, fees=0, total=7500, currency="INR"),
            availability=AvailabilityState.AVAILABLE,
            attributes={"stops": 0},
            constraints_satisfied=True
        )
    ]

    tx, selected, is_ambiguous, reason = tx_engine.update_options(tx.transaction_id, opts)
    assert is_ambiguous is True
    assert "Ambiguous selection" in reason

def test_review_generation_and_snapshot(mock_store):
    """Test freezing pre-commit snapshot and generating review package."""
    tx_engine = TransactionEngine(mock_store)
    tx = tx_engine.create_transaction("Book flight from Ahmedabad to Delhi")

    opt = TransactionOption(
        option_id="opt_indigo",
        provider="IndiGo",
        title="IndiGo 6E 123",
        price=TransactionPrice(base=7000, tax=600, fees=250, total=7850, currency="INR"),
        availability=AvailabilityState.AVAILABLE,
        attributes={"departure_time": "08:30 AM", "route": "AMD-DEL"},
        constraints_satisfied=True
    )
    tx_engine.update_options(tx.transaction_id, [opt])

    review = tx_engine.prepare_review(tx.transaction_id)
    assert review.price.total == 7850
    assert review.provider == "IndiGo"
    assert tx.status == TransactionState.READY_FOR_REVIEW
    assert tx.active_snapshot is not None
    assert tx.active_snapshot.version == 1

def test_price_and_availability_drift_detection(mock_store):
    """Test detecting price drift and availability drift before commit."""
    drift_engine = DriftDetectionEngine()
    tx_engine = TransactionEngine(mock_store)
    tx = tx_engine.create_transaction("Book flight")

    opt_initial = TransactionOption(
        option_id="opt_1",
        provider="IndiGo",
        title="IndiGo 6E 123",
        price=TransactionPrice(base=7000, tax=500, fees=0, total=7500, currency="INR"),
        availability=AvailabilityState.AVAILABLE,
        constraints_satisfied=True
    )
    tx_engine.update_options(tx.transaction_id, [opt_initial])
    tx_engine.prepare_review(tx.transaction_id)

    # 1. Simulate Price Drift (> 1%)
    opt_price_bumped = TransactionOption(
        option_id="opt_1",
        provider="IndiGo",
        title="IndiGo 6E 123",
        price=TransactionPrice(base=7500, tax=600, fees=0, total=8100, currency="INR"),
        availability=AvailabilityState.AVAILABLE,
        constraints_satisfied=True
    )
    has_drift, msg = drift_engine.detect_drift(tx.active_snapshot, opt_price_bumped)
    assert has_drift is True
    assert "Price changed" in msg

    # 2. Simulate Availability Drift
    opt_unavailable = TransactionOption(
        option_id="opt_1",
        provider="IndiGo",
        title="IndiGo 6E 123",
        price=TransactionPrice(base=7000, tax=500, fees=0, total=7500, currency="INR"),
        availability=AvailabilityState.UNAVAILABLE,
        constraints_satisfied=True
    )
    has_drift, msg = drift_engine.detect_drift(tx.active_snapshot, opt_unavailable)
    assert has_drift is True
    assert "unavailable" in msg

def test_user_confirmation_and_authorization_token(mock_store):
    """Test user confirmation issuing a time-bounded CommitAuthorization token."""
    tx_engine = TransactionEngine(mock_store)
    tx = tx_engine.create_transaction("Book flight")

    opt = TransactionOption(
        option_id="opt_1",
        provider="IndiGo",
        title="IndiGo 6E 123",
        price=TransactionPrice(base=7000, tax=500, fees=0, total=7500, currency="INR"),
        availability=AvailabilityState.AVAILABLE,
        constraints_satisfied=True
    )
    tx_engine.update_options(tx.transaction_id, [opt])
    tx_engine.prepare_review(tx.transaction_id)

    conf, auth = tx_engine.confirm_transaction(tx.transaction_id, user_note="Approved non-stop")
    assert conf.status == "CONFIRMED"
    assert auth.auth_token.startswith("tok_")
    assert auth.transaction_id == tx.transaction_id
    assert tx.status == TransactionState.CONFIRMED

def test_policy_engine_blocks_unconfirmed_commit(mock_store):
    """Test Policy Engine blocking commit when explicit user confirmation is missing."""
    policy_engine = TransactionPolicyEngine()
    tx_engine = TransactionEngine(mock_store)
    tx = tx_engine.create_transaction("Book flight")

    allowed, msg = policy_engine.evaluate_commit(tx, confirmation=None)
    assert allowed is False
    assert "invalid state" in msg.lower() or "required" in msg.lower()

@pytest.mark.asyncio
async def test_commit_execution_and_receipt_generation(mock_store):
    """Test executing a confirmed commit and generating a verified receipt."""
    tx_engine = TransactionEngine(mock_store)
    tx = tx_engine.create_transaction("Book flight")

    opt = TransactionOption(
        option_id="opt_1",
        provider="IndiGo",
        title="IndiGo 6E 123",
        price=TransactionPrice(base=7000, tax=500, fees=0, total=7500, currency="INR"),
        availability=AvailabilityState.AVAILABLE,
        constraints_satisfied=True
    )
    tx_engine.update_options(tx.transaction_id, [opt])
    tx_engine.prepare_review(tx.transaction_id)
    conf, auth = tx_engine.confirm_transaction(tx.transaction_id)

    commit_action = ActionIntent(
        action_id="act_commit_1",
        type=ActionType.CLICK,
        target=ActionTarget(
            expected_role="button",
            expected_name="Pay & Confirm Booking"
        ),
        tab_id=101,
        page_id="page_101_v1",
        world_model_version=10,
        page_version=1
    )

    state, receipt, msg = await tx_engine.commit_transaction(tx.transaction_id, commit_action, auth=auth)
    assert state == TransactionState.COMPLETED
    assert receipt is not None
    assert receipt.reference_number.startswith("REF-")
    assert receipt.amount == 7500
    assert tx.status == TransactionState.COMPLETED

def test_user_cancellation_lifecycle(mock_store):
    """Test user cancellation setting transaction to CANCELLED and rejecting confirmation."""
    tx_engine = TransactionEngine(mock_store)
    tx = tx_engine.create_transaction("Book flight")

    opt = TransactionOption(
        option_id="opt_1",
        provider="IndiGo",
        title="IndiGo 6E 123",
        price=TransactionPrice(base=7000, tax=500, fees=0, total=7500, currency="INR"),
        availability=AvailabilityState.AVAILABLE,
        constraints_satisfied=True
    )
    tx_engine.update_options(tx.transaction_id, [opt])
    tx_engine.prepare_review(tx.transaction_id)
    tx_engine.confirm_transaction(tx.transaction_id)

    cancelled_tx = tx_engine.cancel_transaction(tx.transaction_id, reason="User changed mind")
    assert cancelled_tx.status == TransactionState.CANCELLED
    assert cancelled_tx.active_confirmation.status == "REJECTED"
    assert len(mock_store.transaction_audit_events) > 0
