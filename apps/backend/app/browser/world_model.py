"""
MATRIOSHAI World Model Engine (Phase 7)

Canonical state synthesizer, snapshot engine, diff engine, element resolution,
and self-healing reconciliation manager for the MATRIOSHAI Agent Runtime.
"""

import time
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    BrowserWorldModel,
    BrowserWorldSnapshot,
    WorldStateDiff,
    EntityDiff,
    WorldStateTransition,
    WorldWindowState,
    WorldTabState,
    WorldPageState,
    WorldFrameState,
    FrameTree,
    FrameTreeNode,
    WorldElement,
    WorldElementRef,
    WorldElementResolution,
    NavigationState,
    BrowserSessionState,
    BrowserCapabilities,
    WorldHealth,
    WorldQuery,
    WorldQueryResult
)

class WorldModelEngine:
    """
    World Model Engine maintaining the single source of truth for browser world state.
    """

    def __init__(self, state_store=None):
        self.state_store = state_store or browser_state_store

    def build_current_world(self, bridge_connected: bool = True, session_id: Optional[str] = None) -> BrowserWorldModel:
        """
        Assemble the current mutable BrowserWorldModel from all tracked subsystems.
        """
        store = self.state_store
        now = datetime.now(timezone.utc).isoformat()

        # Session State
        session = BrowserSessionState(
            browser_session_id=store.browser_id,
            extension_session_id=session_id or f"ext_{secrets.token_hex(4)}",
            connected=bridge_connected,
            timestamp=now,
            capabilities=[
                "tabObservation",
                "pageObservation",
                "semanticObservation",
                "screenshotCapture",
                "frameObservation"
            ],
            active_window_id=None,
            active_tab_id=store.active_tab_id
        )

        # Windows
        world_windows: List[WorldWindowState] = []
        for w in store.get_windows():
            ww = WorldWindowState(
                window_id=w.window_id,
                focused=w.focused,
                state=w.state if w.state in ["normal", "minimized", "maximized", "fullscreen"] else "normal",
                tab_ids=w.tab_ids,
                active_tab_id=w.active_tab_id
            )
            world_windows.append(ww)
            if w.focused:
                session.active_window_id = w.window_id

        # Tabs
        world_tabs: List[WorldTabState] = []
        for t in store.get_tabs():
            wt = WorldTabState(
                tab_id=t.tab_id,
                window_id=t.window_id,
                index=t.index,
                active=t.active,
                highlighted=t.active,
                pinned=False,
                url=t.url,
                title=t.title,
                status=t.status,
                favIconUrl=t.favIconUrl,
                last_updated=t.last_updated
            )
            world_tabs.append(wt)

        # Active Window
        active_win = next((w for w in world_windows if w.focused), (world_windows[0] if world_windows else None))

        # Page States
        pages = list(store.page_states.values())

        # Frame Trees
        frame_trees = dict(store.frame_trees)

        # References
        observations: Dict[int, str] = {}
        for tid, obs in store.latest_observations.items():
            observations[tid] = obs.observation_id

        semantic_models: Dict[int, str] = {}
        for tid, sem in store.latest_semantic_models.items():
            semantic_models[tid] = sem.semantic_model_id

        visual_models: Dict[int, str] = {}
        for tid, vis in store.latest_visual_models.items():
            visual_models[tid] = vis.visual_model_id

        # Navigation States
        nav_states: Dict[int, NavigationState] = {}
        for tid, tab in store.tabs.items():
            history = store.navigation_histories.get(tid, [])
            nav_states[tid] = NavigationState(
                current_url=tab.url,
                navigation_id=history[-1].navigation_id if history else f"nav_{tid}_init",
                navigation_type="INITIAL" if not history else "SPA",
                started_at=now,
                completed_at=now,
                status="navigation_completed",
                history=history
            )

        # Transitions
        transitions = store.get_world_transitions()

        # Health
        health = self.check_health(bridge_connected)

        world_model = BrowserWorldModel(
            world_model_id=f"world_{store.world_model_version}_{int(time.time())}",
            world_model_version=store.world_model_version,
            browser_session=session,
            active_window=active_win,
            windows=world_windows,
            tabs=world_tabs,
            active_tab_id=store.active_tab_id,
            pages=pages,
            frame_trees=frame_trees,
            observations=observations,
            semantic_models=semantic_models,
            visual_models=visual_models,
            navigation_states=nav_states,
            temporal_transitions=transitions,
            capabilities=BrowserCapabilities(),
            status=health.status,
            health=health,
            timestamp=now,
            metadata={
                "windows_count": len(world_windows),
                "tabs_count": len(world_tabs),
                "pages_count": len(pages),
                "snapshots_count": len(store.world_snapshots)
            }
        )

        store.current_world = world_model
        return world_model

    def create_snapshot(self, reason: Optional[str] = None, bridge_connected: bool = True) -> BrowserWorldSnapshot:
        """
        Create an immutable historical snapshot representing the world state at this exact moment.
        """
        world = self.build_current_world(bridge_connected)
        now = datetime.now(timezone.utc).isoformat()

        active_nav = None
        if world.active_tab_id and world.active_tab_id in world.navigation_states:
            active_nav = world.navigation_states[world.active_tab_id]

        snapshot = BrowserWorldSnapshot(
            snapshot_id=f"snap_{world.world_model_version}_{int(time.time()*1000)}",
            timestamp=now,
            world_model_version=world.world_model_version,
            active_tab_id=world.active_tab_id,
            tab_states=[t.model_copy(deep=True) for t in world.tabs],
            page_states=[p.model_copy(deep=True) for p in world.pages],
            semantic_references=dict(world.semantic_models),
            visual_references=dict(world.visual_models),
            navigation_state=active_nav.model_copy(deep=True) if active_nav else None,
            reason=reason or "manual_snapshot"
        )

        self.state_store.append_world_snapshot(snapshot)
        logger.info(f"[MATRIOSHAI][WorldModel] Created immutable snapshot '{snapshot.snapshot_id}' (v{snapshot.world_model_version})")
        return snapshot

    def diff_world(self, before: BrowserWorldSnapshot, after: BrowserWorldSnapshot) -> WorldStateDiff:
        """
        Compute deterministic structural and semantic difference between two immutable snapshots.
        """
        diff_id = f"diff_{before.world_model_version}_to_{after.world_model_version}"
        summary: List[str] = []

        # Tabs diff
        before_tabs = {t.tab_id: t for t in before.tab_states}
        after_tabs = {t.tab_id: t for t in after.tab_states}

        tabs_added = [t for tid, t in after_tabs.items() if tid not in before_tabs]
        tabs_removed = [t for tid, t in before_tabs.items() if tid not in after_tabs]
        tabs_changed = [
            {"before": before_tabs[tid].model_dump(), "after": after_tabs[tid].model_dump()}
            for tid in before_tabs if tid in after_tabs and before_tabs[tid].url != after_tabs[tid].url
        ]

        if tabs_added:
            summary.append(f"Added {len(tabs_added)} tab(s)")
        if tabs_removed:
            summary.append(f"Removed {len(tabs_removed)} tab(s)")
        if tabs_changed:
            summary.append(f"Updated {len(tabs_changed)} tab(s)")

        tabs_diff = EntityDiff(
            added=[t.model_dump() for t in tabs_added],
            removed=[t.model_dump() for t in tabs_removed],
            changed=tabs_changed,
            unchanged_count=len(before_tabs) - len(tabs_removed) - len(tabs_changed)
        )

        # Pages diff
        before_pages = {p.page_id: p for p in before.page_states}
        after_pages = {p.page_id: p for p in after.page_states}

        pages_added = [p for pid, p in after_pages.items() if pid not in before_pages]
        pages_removed = [p for pid, p in before_pages.items() if pid not in after_pages]
        pages_changed = [
            {"before": before_pages[pid].model_dump(), "after": after_pages[pid].model_dump()}
            for pid in before_pages if pid in after_pages and before_pages[pid].page_version != after_pages[pid].page_version
        ]

        if pages_added:
            summary.append(f"Added {len(pages_added)} page state(s)")
        if pages_changed:
            summary.append(f"Page version advanced on {len(pages_changed)} page(s)")

        pages_diff = EntityDiff(
            added=[p.model_dump() for p in pages_added],
            removed=[p.model_dump() for p in pages_removed],
            changed=pages_changed,
            unchanged_count=len(before_pages) - len(pages_removed) - len(pages_changed)
        )

        # Dialogs diff
        before_dialogs = set()
        for p in before.page_states:
            before_dialogs.update(p.active_dialogs)

        after_dialogs = set()
        for p in after.page_states:
            after_dialogs.update(p.active_dialogs)

        dialogs_added = list(after_dialogs - before_dialogs)
        dialogs_removed = list(before_dialogs - after_dialogs)
        if dialogs_added:
            summary.append(f"Opened dialog(s): {', '.join(dialogs_added)}")
        if dialogs_removed:
            summary.append(f"Closed dialog(s): {', '.join(dialogs_removed)}")

        dialogs_diff = EntityDiff(
            added=dialogs_added,
            removed=dialogs_removed,
            changed=[],
            unchanged_count=len(before_dialogs.intersection(after_dialogs))
        )

        # Navigation change check
        nav_changed = False
        if before.navigation_state and after.navigation_state:
            nav_changed = before.navigation_state.current_url != after.navigation_state.current_url
        elif before.active_tab_id != after.active_tab_id:
            nav_changed = True

        if nav_changed:
            summary.append("Navigation state transitioned")

        if not summary:
            summary.append("No structural changes detected between snapshots")

        return WorldStateDiff(
            diff_id=diff_id,
            source_snapshot_id=before.snapshot_id,
            target_snapshot_id=after.snapshot_id,
            source_version=before.world_model_version,
            target_version=after.world_model_version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tabs_diff=tabs_diff,
            pages_diff=pages_diff,
            elements_diff=EntityDiff(),
            dialogs_diff=dialogs_diff,
            navigation_changed=nav_changed,
            summary=summary
        )

    def resolve_world_element(self, ref: WorldElementRef, tab_id: Optional[int] = None) -> WorldElementResolution:
        """
        Deterministically resolve a WorldElementRef against the current state store.
        """
        store = self.state_store
        target_tab = tab_id or store.active_tab_id
        if not target_tab:
            return WorldElementResolution(
                status="TAB_CLOSED",
                reference=ref,
                candidates=[],
                message="No active tab available for element resolution"
            )

        # Check if tab closed
        if target_tab not in store.tabs:
            return WorldElementResolution(
                status="TAB_CLOSED",
                reference=ref,
                candidates=[],
                message=f"Tab {target_tab} is closed."
            )

        current_page = store.page_states.get(target_tab)

        # 1. Page identity check
        if current_page and ref.page_id and ref.page_id != current_page.page_id:
            return WorldElementResolution(
                status="PAGE_CHANGED",
                reference=ref,
                candidates=[],
                message=f"Reference page_id '{ref.page_id}' does not match current page_id '{current_page.page_id}'"
            )

        # 2. Page version check
        if current_page and ref.page_version < current_page.page_version:
            elements = store.world_elements.get(target_tab, [])
            candidates = [
                el.element_ref for el in elements
                if el.role == ref.role and el.name == ref.name
            ]
            return WorldElementResolution(
                status="STALE",
                reference=ref,
                candidates=candidates,
                message=f"Reference version v{ref.page_version} is older than current page version v{current_page.page_version}."
            )

        # 3. Exact element lookup
        elements = store.world_elements.get(target_tab, [])
        for el in elements:
            if el.element_ref.element_id == ref.element_id:
                return WorldElementResolution(
                    status="FOUND",
                    element=el,
                    reference=ref,
                    candidates=[el.element_ref],
                    message="Resolved unique world element"
                )

        # 4. Fallback search by role and name
        matching = [el for el in elements if el.role == ref.role and el.name == ref.name]
        if len(matching) == 1:
            return WorldElementResolution(
                status="FOUND",
                element=matching[0],
                reference=ref,
                candidates=[matching[0].element_ref],
                message="Resolved via role and accessible name match"
            )
        elif len(matching) > 1:
            return WorldElementResolution(
                status="AMBIGUOUS",
                reference=ref,
                candidates=[m.element_ref for m in matching],
                message=f"Ambiguity detected: found {len(matching)} matching elements"
            )

        return WorldElementResolution(
            status="NOT_FOUND",
            reference=ref,
            candidates=[],
            message=f"Element '{ref.element_id}' not found in current world state."
        )

    def validate_world(self, model: BrowserWorldModel) -> Dict[str, Any]:
        """
        Validate internal consistency of a BrowserWorldModel.
        """
        errors: List[str] = []

        # 1. Active tab check
        if model.active_tab_id is not None:
            tab_ids = [t.tab_id for t in model.tabs]
            if model.active_tab_id not in tab_ids:
                errors.append(f"Active tab_id {model.active_tab_id} does not exist in tabs list")

        # 2. Window-tab containment check
        all_window_tab_ids: Set[int] = set()
        for w in model.windows:
            for tid in w.tab_ids:
                all_window_tab_ids.add(tid)

        for t in model.tabs:
            if t.tab_id not in all_window_tab_ids and len(model.windows) > 0:
                errors.append(f"Tab {t.tab_id} is not contained in any window's tab_ids")

        # 3. Stale references check
        for p in model.pages:
            if p.observation_id and p.tab_id in model.observations:
                if p.observation_id != model.observations[p.tab_id]:
                    errors.append(f"Page observation mismatch for tab {p.tab_id}")

        is_valid = len(errors) == 0
        return {
            "status": "VALID" if is_valid else "INVALID",
            "is_valid": is_valid,
            "errors": errors,
            "version": model.world_model_version,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def reconcile_world(self, actual_windows: List[Dict[str, Any]], actual_tabs: List[Dict[str, Any]], active_tab: Optional[Dict[str, Any]] = None) -> BrowserWorldModel:
        """
        Repair inconsistencies when out-of-order asynchronous browser events occur.
        """
        self.state_store.reconcile_state(actual_windows, actual_tabs, active_tab)
        return self.build_current_world(bridge_connected=True)

    def query_world(self, query: WorldQuery) -> WorldQueryResult:
        """
        Execute deterministic structured query across the World Model.
        """
        store = self.state_store
        q_type = query.type.lower()

        if q_type == "element":
            target_tab = query.tab_id or store.active_tab_id
            elements = store.world_elements.get(target_tab, []) if target_tab else []

            matches = []
            for el in elements:
                if query.role and el.role.lower() != query.role.lower():
                    continue
                if query.name and query.name.lower() not in el.name.lower():
                    continue
                if query.interactive_only and not el.enabled:
                    continue
                if query.visible_only and not el.visible:
                    continue
                matches.append(el)

            status = "FOUND" if matches else "NOT_FOUND"
            return WorldQueryResult(
                status=status,
                query=query,
                elements=matches,
                pages=[],
                tabs=[],
                count=len(matches),
                message=f"Found {len(matches)} element(s) matching query"
            )

        elif q_type == "tab":
            tabs = store.get_tabs()
            return WorldQueryResult(
                status="FOUND" if tabs else "NOT_FOUND",
                query=query,
                elements=[],
                pages=[],
                tabs=[
                    WorldTabState(
                        tab_id=t.tab_id,
                        window_id=t.window_id,
                        index=t.index,
                        active=t.active,
                        highlighted=t.active,
                        pinned=False,
                        url=t.url,
                        title=t.title,
                        status=t.status,
                        favIconUrl=t.favIconUrl,
                        last_updated=t.last_updated
                    ) for t in tabs
                ],
                count=len(tabs),
                message=f"Found {len(tabs)} tab(s)"
            )

        elif q_type == "page":
            pages = list(store.page_states.values())
            if query.tab_id:
                pages = [p for p in pages if p.tab_id == query.tab_id]

            return WorldQueryResult(
                status="FOUND" if pages else "NOT_FOUND",
                query=query,
                elements=[],
                pages=pages,
                tabs=[],
                count=len(pages),
                message=f"Found {len(pages)} page state(s)"
            )

        return WorldQueryResult(
            status="NOT_FOUND",
            query=query,
            elements=[],
            pages=[],
            tabs=[],
            count=0,
            message=f"Unsupported query type '{query.type}'"
        )

    def check_health(self, bridge_connected: bool = True) -> WorldHealth:
        """
        Evaluate health metrics across the World Model.
        """
        store = self.state_store
        has_active_tab = store.active_tab_id is not None and store.active_tab_id in store.tabs
        obs_avail = len(store.latest_observations) > 0
        sem_avail = len(store.latest_semantic_models) > 0
        vis_avail = len(store.latest_visual_models) > 0
        stale_count = store.get_stale_artifacts_count()

        if not bridge_connected:
            health_status = "DISCONNECTED"
        elif not vis_avail and sem_avail:
            health_status = "DEGRADED"
        elif not has_active_tab:
            health_status = "STALE"
        else:
            health_status = "READY"

        return WorldHealth(
            status=health_status,
            browser_connected=bridge_connected,
            active_tab_available=has_active_tab,
            page_observation_available=obs_avail,
            semantic_model_available=sem_avail,
            visual_model_available=vis_avail,
            stale_artifacts=stale_count,
            unresolved_references=0,
            last_reconciliation_time=store.last_seen
        )

world_model_engine = WorldModelEngine()
