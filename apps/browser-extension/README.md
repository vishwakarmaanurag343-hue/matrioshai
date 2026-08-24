# MATRIOSHAI Browser Extension — Production Hardening & Autonomous Runtime (Phase 14)

The official Chrome Extension execution, observation, semantic, visual, unified world state intelligence, deterministic action, outcome verification, closed-loop agent loop, high-consequence transaction, security/human-in-the-loop, and production-hardened autonomous runtime for the **MATRIOSHAI Unified Personal AI Operating System**.

---

## 1. Architecture Overview

```
                         USER
                           │
                           ▼
                 ┌──────────────────┐
                 │ SECURITY CENTER  │
                 │    PHASE 13      │
                 └────────┬─────────┘
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
          PERMISSION   POLICY      CONFIRMATION
              │           │            │
              └───────────┼────────────┘
                          ▼
                     WORKFLOW
                     PHASE 11
                          │
                          ▼
                       AGENT
                     PHASE 10
                          │
                          ▼
                    TRANSACTION
                     PHASE 12
                          │
                          ▼
                    ACTION ENGINE
                      PHASE 8
                          │
                          ▼
                       BROWSER
                          │
                          ▼
                    WORLD MODEL
                      PHASE 7
                          │
                          ▼
                    VERIFICATION
                      PHASE 9
```
         ↕  [localhost-only, token-authenticated, versioned protocol v1.0]
Chrome Extension Background Service Worker (BrowserBridgeClient)
        ┌────────┴────────┐
        │                 │
  BrowserController   EventEngine
  (chrome.tabs/wins)  (Real-time event stream)
        │
        ▼ (chrome.tabs.sendMessage)
  Content Script
  ├── ActionDomExecutor      (Phase 8 Safe Event Dispatchers: click, type, clear, select, check, focus, scroll, key_press)
  ├── WorldModelExtractor    (Phase 7 World Model Extraction)
  ├── PageObservationEngine  (Phase 4 Observation)
  ├── SemanticPageAnalyzer   (Phase 5 Semantic Intelligence)
  ├── SemanticQueryEngine    (Phase 5 Search & Ambiguity Detection)
  ├── DomMutationTracker     (Phases 5-12 Model Invalidation & Versioning)
  ├── VisualGeometry         (Phase 6 Coordinate Transformations & Math)
  ├── VisualRedactor         (Phase 6 Client-Side Privacy Redaction)
  ├── VisualExtractor        (Phase 6 Canvas/SVG/Media/Overlay Extractor)
  ├── VisualEngine           (Phase 6 Visual Page Intelligence Orchestrator)
  └── VisualQueryEngine      (Phase 6 Visual Queries & Point Queries)
        │
        ▼ [Post-Action Snapshot & Diff]
  VerificationEngine (app/browser/verification_engine.py)
  ├── PostconditionEngine (ALL, ANY, AT_LEAST_N evaluation)
  ├── PageErrorDetector (Server errors, inline validations, auth modals, CAPTCHAs, rate limits)
  ├── FailureClassifier (18 discrete failure types)
  ├── RecoveryEngine (Idempotency-gated recommendations & Human Intervention Handoff)
  ├── InvalidationManager (Selective scopes: ELEMENT, PAGE, FRAME, TAB, WORLD)
  └── WorkflowCheckpointManager (Resumable autonomy checkpoints)
        │
        ▼
   Live Web Page, DOM, Semantic Model, Visual Geometry & Frame Hierarchy
```

```
apps/browser-extension/
├── manifest.json                  # Manifest V3 (storage, activeTab, tabs)
├── package.json                   # Build & test scripts
├── tsconfig.json                  # Strict TypeScript configuration
├── vite.config.ts                 # Multi-entry build bundler
├── assets/
│   └── icons/                     # Extension icons (16x16, 48x48, 128x128)
├── src/
│   ├── background/
│   │   └── service-worker.ts      # Service worker lifecycle & event engine bootstrap
│   ├── content/
│   │   ├── content-script.ts      # Content script message router
│   │   ├── observation-engine.ts  # Phase 4 Page Observation Engine
│   │   ├── semantic-analyzer.ts   # Phase 5 Semantic & Accessibility Intelligence
│   │   ├── semantic-query-engine.ts # Phase 5 Query & Element Resolution Engine
│   │   ├── mutation-tracker.ts    # Phase 5/6/7 Mutation & Staleness Invalidation Observer
│   │   ├── visual-geometry.ts     # Phase 6 Coordinate Conversions & Bounding Box Math
│   │   ├── visual-redactor.ts     # Phase 6 Client-Side Privacy Redaction Filter
│   │   ├── visual-extractor.ts    # Phase 6 Visual Element & Region Extractor
│   │   ├── visual-query-engine.ts # Phase 6 Z-Order Point & Region Query Engine
│   │   ├── visual-engine.ts       # Phase 6 Visual Page Model Orchestrator
│   │   └── world-model-extractor.ts # Phase 7 Page State, Frame Tree & Element Synthesizer
│   ├── popup/
│   │   ├── popup.html             # Browser Control & Observation popup UI
│   │   ├── popup.css              # Dark-mode glassmorphic styling
│   │   └── popup.ts               # Status query controller
│   ├── core/
│   │   ├── browser-bridge.ts      # WebSocket bridge client & action dispatcher
│   │   ├── browser-controller.ts  # Chrome window, tab, navigation, screenshot execution
│   │   ├── event-engine.ts        # Real-time Chrome event streaming
│   │   └── extension-state.ts     # Centralized extension state manager
│   ├── shared/
│   │   ├── constants.ts           # Protocol constants, capabilities, config
│   │   ├── logger.ts              # Scoped logger
│   │   └── types.ts               # Strongly-typed bridge, observation, semantic, visual, world models
│   └── __tests__/
│       ├── bridge.test.ts         # Bridge client connection & capability tests
│       ├── contracts.test.ts      # Structural contract tests
│       ├── controller.test.ts     # Browser controller tests
│       ├── logger.test.ts         # Logger test suite
│       ├── manifest.test.ts       # Manifest validation tests
│       ├── observation.test.ts    # Observation extraction tests
│       ├── semantic_analyzer.test.ts # Semantic intelligence tests
│       ├── state.test.ts          # State manager tests
│       ├── visual_geometry.test.ts # Coordinate transformation tests
│       ├── visual_engine.test.ts  # Visual page model & point query tests
│       └── world_model.test.ts    # World model extraction & element resolution tests
```

---

## 2. Supported World Model Capabilities (Phase 7)

1. **Unified State Graph**:
   - `BrowserWorldModel`: Synthesizes session identity, windows, tabs, active focus, page states, frame trees, observation IDs, semantic model IDs, visual model IDs, navigation states, and temporal transitions into a coherent single source of truth.
2. **Immutable Snapshotting & Bounded History**:
   - `create_world_snapshot(reason)`: Produces an immutable, deep-copied representation of the world state and maintains a bounded historical buffer (maximum 20 snapshots with automatic FIFO eviction).
3. **Deterministic State Diff Engine**:
   - `diff_world(before, after)`: Calculates structural and semantic differences across tabs, pages, elements, dialogs, and navigation states without guessing or scraping.
4. **Canonical Element Identity & Resolution**:
   - `WorldElementRef` and `resolve_world_element()`: Deterministically verifies element validity across page IDs, version numbers, stable DOM identifiers, and semantic roles, returning explicit statuses: `FOUND`, `NOT_FOUND`, `AMBIGUOUS`, `STALE`, `PAGE_CHANGED`, or `TAB_CLOSED`.
5. **Self-Healing Reconciliation**:
   - `reconcile_world()`: Repairs dropped or out-of-order asynchronous browser events by querying the underlying Chrome state directly.
6. **Strict Security & Non-Action Invariant**:
   - Zero storage of passwords, cookies, authorization tokens, or credit card numbers. Zero execution of browser actions (no clicking, typing, scrolling, or navigating).
