/**
 * MATRIOSHAI Semantic Query & Element Resolution Engine (Phase 5)
 *
 * Provides deterministic semantic search and reference resolution across SemanticPageModel.
 * Strictly avoids guessing or auto-selecting when multiple elements match (returns AMBIGUOUS).
 * Detects stale references when the page model has been invalidated by navigation or DOM mutations.
 */

import {
  type SemanticPageModel,
  type SemanticElement,
  type SemanticElementRef,
  type SemanticQuery,
  type QueryResult,
  type ResolveResult
} from '../shared/types';

export class SemanticQueryEngine {
  /**
   * Deterministically query elements from the SemanticPageModel
   */
  public query(model: SemanticPageModel, spec: SemanticQuery): QueryResult {
    if (model.is_stale) {
      return {
        status: 'STALE',
        matches: [],
        confidence: 'LOW',
        query: spec,
        message: 'The current SemanticPageModel is stale. A fresh observation is required.'
      };
    }

    const candidateIds = this.findCandidateElementIds(model, spec);
    const elements = candidateIds
      .map((id) => model.interactive_elements.find((el) => el.element_id === id))
      .filter((el): el is SemanticElement => el !== undefined);

    const matches: SemanticElementRef[] = elements.map((el) => this.toElementRef(model, el));

    if (matches.length === 0) {
      return {
        status: 'NOT_FOUND',
        matches: [],
        confidence: 'HIGH',
        query: spec,
        message: `No element found matching query: ${JSON.stringify(spec)}`
      };
    }

    if (matches.length === 1) {
      const element = elements[0];
      return {
        status: 'FOUND',
        element,
        matches,
        confidence: element.confidence,
        query: spec,
        message: `Found unique element [${element.element_id}] matching query.`
      };
    }

    // MULTIPLE MATCHES -> AMBIGUOUS (Never silently choose one)
    return {
      status: 'AMBIGUOUS',
      matches,
      confidence: 'MEDIUM',
      query: spec,
      message: `Query matched ${matches.length} elements. Ambiguity detected — explicit disambiguation required.`
    };
  }

  /**
   * Resolve an existing SemanticElementRef against the current SemanticPageModel
   */
  public resolveElement(model: SemanticPageModel, ref: SemanticElementRef): ResolveResult {
    if (model.is_stale) {
      return {
        status: 'STALE',
        matches: [],
        reference: ref,
        message: 'The referenced SemanticPageModel is stale due to navigation or DOM mutations.'
      };
    }

    // 1. Direct lookup by element_id
    const directMatch = model.interactive_elements.find((el) => el.element_id === ref.element_id);
    if (directMatch) {
      // Verify role & tag consistency
      if (
        directMatch.role.toLowerCase() === ref.role.toLowerCase() &&
        directMatch.tag_name.toLowerCase() === ref.tag_name.toLowerCase()
      ) {
        return {
          status: 'FOUND',
          element: directMatch,
          matches: [this.toElementRef(model, directMatch)],
          reference: ref,
          message: `Resolved element [${directMatch.element_id}] directly.`
        };
      }
    }

    // 2. Fallback resolution using stable attributes
    const candidateQuery: SemanticQuery = {
      role: ref.role,
      name: ref.name,
      id: ref.stable_id || undefined,
      exact: true
    };

    const queryResult = this.query(model, candidateQuery);
    if (queryResult.status === 'FOUND' && queryResult.element) {
      return {
        status: 'FOUND',
        element: queryResult.element,
        matches: queryResult.matches,
        reference: ref,
        message: `Resolved element [${queryResult.element.element_id}] via stable descriptor fallback.`
      };
    }

    if (queryResult.status === 'AMBIGUOUS') {
      return {
        status: 'AMBIGUOUS',
        matches: queryResult.matches,
        reference: ref,
        message: 'Reference matches multiple candidates in the current page model.'
      };
    }

    return {
      status: 'NOT_FOUND',
      matches: [],
      reference: ref,
      message: `Element reference [${ref.element_id}] could not be resolved in the current model.`
    };
  }

  private findCandidateElementIds(model: SemanticPageModel, spec: SemanticQuery): string[] {
    const indexes = model.indexes;
    let candidates: Set<string> | null = null;

    // 1. ID Match (Highest Priority)
    if (spec.id) {
      const idKey = spec.id.trim();
      const matchedElementId = indexes.byId[idKey];
      if (matchedElementId) {
        candidates = new Set([matchedElementId]);
      } else {
        return [];
      }
    }

    // 2. Role Match
    if (spec.role) {
      const roleKey = spec.role.toLowerCase().trim();
      const roleMatches = new Set(indexes.byRole[roleKey] || []);
      if (candidates === null) {
        candidates = roleMatches;
      } else {
        candidates = new Set([...candidates].filter((x) => roleMatches.has(x)));
      }
    }

    // 3. Name Match
    if (spec.name) {
      const nameKey = spec.name.toLowerCase().trim();
      const nameMatches = new Set(indexes.byName[nameKey] || []);
      if (candidates === null) {
        candidates = nameMatches;
      } else {
        candidates = new Set([...candidates].filter((x) => nameMatches.has(x)));
      }
    }

    // 4. Label Match
    if (spec.label) {
      const labelKey = spec.label.toLowerCase().trim();
      const labelMatches = new Set(indexes.byLabel[labelKey] || []);
      if (candidates === null) {
        candidates = labelMatches;
      } else {
        candidates = new Set([...candidates].filter((x) => labelMatches.has(x)));
      }
    }

    // 5. Type Match
    if (spec.type) {
      const typeKey = spec.type.toLowerCase().trim();
      const typeMatches = new Set(indexes.byType[typeKey] || []);
      if (candidates === null) {
        candidates = typeMatches;
      } else {
        candidates = new Set([...candidates].filter((x) => typeMatches.has(x)));
      }
    }

    // 6. Text / Content Search (if text given and no exact match found yet)
    if (spec.text && (candidates === null || candidates.size === 0)) {
      const textKey = spec.text.toLowerCase().trim();
      const matched = model.interactive_elements
        .filter((el) => el.name.toLowerCase().includes(textKey) || (el.description && el.description.toLowerCase().includes(textKey)))
        .map((el) => el.element_id);
      candidates = new Set(matched);
    }

    return candidates ? Array.from(candidates) : [];
  }

  private toElementRef(model: SemanticPageModel, el: SemanticElement): SemanticElementRef {
    return {
      semantic_model_id: model.semantic_model_id,
      observation_id: model.observation_id,
      element_id: el.element_id,
      role: el.role,
      name: el.name,
      tag_name: el.tag_name,
      stable_id: el.attributes.id || null,
      attributes: el.attributes
    };
  }
}

export const semanticQueryEngine = new SemanticQueryEngine();
