import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Mapping from wiki-link identifiers to tab navigation targets.
 * Key: section_id used in [[section_id|Display Text]]
 * Value: { tab, subTarget? } - tab to navigate to, optional sub-target
 */
const WIKI_LINK_MAP = {
  // Company Info tab
  company_profile: { tab: 'company_info' },

  // Maturity tab
  maturity_assessment: { tab: 'maturity' },

  // CRISP-DM tab (Step 4 findings)
  business_objectives: { tab: 'crisp_dm', subTarget: 'business_objectives' },
  situation_assessment: { tab: 'crisp_dm', subTarget: 'situation_assessment' },
  ai_goals: { tab: 'crisp_dm', subTarget: 'ai_goals' },
  project_plan: { tab: 'crisp_dm', subTarget: 'project_plan' },

  // Business Case tab (Step 5a findings)
  business_case: { tab: 'business_case' },
  business_case_classification: { tab: 'business_case', subTarget: 'classification' },
  business_case_calculation: { tab: 'business_case', subTarget: 'calculation' },
  business_case_validation: { tab: 'business_case', subTarget: 'validation' },
  business_case_pitch: { tab: 'business_case', subTarget: 'pitch' },

  // Cost Estimation tab (Step 5b findings)
  cost_tco: { tab: 'costs' },
  cost_complexity: { tab: 'costs', subTarget: 'complexity' },
  cost_initial: { tab: 'costs', subTarget: 'initial' },
  cost_recurring: { tab: 'costs', subTarget: 'recurring' },
  cost_maintenance: { tab: 'costs', subTarget: 'maintenance' },
  cost_drivers: { tab: 'costs', subTarget: 'drivers' },
  cost_optimization: { tab: 'costs', subTarget: 'optimization' },
  cost_roi: { tab: 'costs', subTarget: 'roi' },

  // Analysis tabs
  swot_analysis: { tab: 'swot' },
  technical_briefing: { tab: 'briefing' },
};

/**
 * Human-readable labels for finding types
 */
const FINDING_TYPE_LABELS = {
  company_profile: 'Company Profile',
  maturity_assessment: 'Maturity Assessment',
  business_objectives: 'Business Objectives',
  situation_assessment: 'Situation Assessment',
  ai_goals: 'AI Goals',
  project_plan: 'Project Plan',
  business_case_classification: 'Value Classification',
  business_case_calculation: 'Financial Calculation',
  business_case_validation: 'Validation Questions',
  business_case_pitch: 'Management Pitch',
  cost_complexity: 'Complexity Assessment',
  cost_initial: 'Initial Investment',
  cost_recurring: 'Recurring Costs',
  cost_maintenance: 'Maintenance Costs',
  cost_tco: 'Total Cost of Ownership',
  cost_drivers: 'Cost Drivers',
  cost_optimization: 'Cost Optimization',
  cost_roi: 'ROI Analysis',
  swot_analysis: 'SWOT Analysis',
  technical_briefing: 'Technical Briefing',
};

/**
 * Auto-detection patterns for finding type mentions in text.
 * These will be converted to wiki-links if not already linked.
 */
const AUTO_DETECT_PATTERNS = [
  // English patterns
  { pattern: /\b(Company Profile)\b/gi, target: 'company_profile' },
  { pattern: /\b(Maturity Assessment|Digital Maturity)\b/gi, target: 'maturity_assessment' },
  { pattern: /\b(Business Objectives)\b/gi, target: 'business_objectives' },
  { pattern: /\b(Situation Assessment)\b/gi, target: 'situation_assessment' },
  { pattern: /\b(AI Goals|AI\/Data Mining Goals)\b/gi, target: 'ai_goals' },
  { pattern: /\b(Project Plan)\b/gi, target: 'project_plan' },
  { pattern: /\b(Business Case)\b/gi, target: 'business_case' },
  { pattern: /\b(Cost Estimation|TCO|Total Cost of Ownership)\b/gi, target: 'cost_tco' },
  { pattern: /\b(SWOT Analysis|SWOT)\b/gi, target: 'swot_analysis' },
  { pattern: /\b(Technical Briefing|Transition Briefing)\b/gi, target: 'technical_briefing' },

  // German patterns
  { pattern: /\b(Unternehmensprofil)\b/gi, target: 'company_profile' },
  { pattern: /\b(Reifegradanalyse|Digitaler Reifegrad)\b/gi, target: 'maturity_assessment' },
  { pattern: /\b(Geschäftsziele)\b/gi, target: 'business_objectives' },
  { pattern: /\b(Situationsanalyse)\b/gi, target: 'situation_assessment' },
  { pattern: /\b(KI-Ziele|KI-\/Data-Mining-Ziele)\b/gi, target: 'ai_goals' },
  { pattern: /\b(Projektplan)\b/gi, target: 'project_plan' },
  { pattern: /\b(Kostenschätzung|Gesamtbetriebskosten)\b/gi, target: 'cost_tco' },
  { pattern: /\b(SWOT-Analyse)\b/gi, target: 'swot_analysis' },
];

/**
 * Escape special regex characters in a string
 */
function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Process content to convert wiki-links, LLM-extracted cross-references, and auto-detect references.
 *
 * @param {string} content - The markdown content to process
 * @param {Array} crossReferences - LLM-extracted cross-references for this finding
 * @param {boolean} enableAutoDetect - Whether to auto-detect finding mentions
 * @returns {string} - Processed content with wiki-links marked
 */
function processWikiLinks(content, crossReferences = [], enableAutoDetect = true) {
  if (!content) return '';

  let processed = content;
  const linkedPhrases = new Set(); // Track phrases we've already linked

  // Step 1: Convert explicit wiki-links [[target|text]] or [[target]]
  const wikiLinkRegex = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;
  processed = processed.replace(wikiLinkRegex, (match, target, displayText) => {
    const text = displayText || target;
    linkedPhrases.add(text.toLowerCase());
    return `<wiki-link target="${target}">${text}</wiki-link>`;
  });

  // Step 2: Apply LLM-extracted cross-references (highest priority after explicit)
  if (crossReferences && crossReferences.length > 0) {
    // Sort by phrase length (descending) to match longer phrases first
    const sortedRefs = [...crossReferences].sort(
      (a, b) => (b.phrase?.length || 0) - (a.phrase?.length || 0)
    );

    for (const ref of sortedRefs) {
      if (!ref.phrase || !ref.target || linkedPhrases.has(ref.phrase.toLowerCase())) {
        continue;
      }

      // Only link if confidence is above threshold
      if (ref.confidence && ref.confidence < 60) {
        continue;
      }

      // Create a regex that matches the exact phrase (case insensitive)
      const phraseRegex = new RegExp(`\\b(${escapeRegex(ref.phrase)})\\b`, 'gi');

      // Only replace the first occurrence to avoid over-linking
      let replaced = false;
      processed = processed.replace(phraseRegex, (match) => {
        if (replaced || linkedPhrases.has(match.toLowerCase())) {
          return match;
        }
        replaced = true;
        linkedPhrases.add(match.toLowerCase());
        return `<wiki-link target="${ref.target}" relationship="${ref.relationship || 'references'}">${match}</wiki-link>`;
      });
    }
  }

  // Step 3: Auto-detect finding type mentions (fallback, only if not already linked)
  if (enableAutoDetect) {
    for (const { pattern, target } of AUTO_DETECT_PATTERNS) {
      processed = processed.replace(pattern, (match) => {
        if (linkedPhrases.has(match.toLowerCase())) {
          return match;
        }
        linkedPhrases.add(match.toLowerCase());
        return `<wiki-link target="${target}">${match}</wiki-link>`;
      });
    }
  }

  return processed;
}

/**
 * Custom component to render wiki-links as clickable elements.
 */
const WikiLinkComponent = ({ target, relationship, children, onNavigate, sectionContents }) => {
  const mapping = WIKI_LINK_MAP[target];

  if (!mapping) {
    // Unknown target - render as plain text
    return <span className="text-gray-600">{children}</span>;
  }

  const handleClick = (e) => {
    e.preventDefault();
    if (onNavigate) {
      onNavigate(mapping.tab, mapping.subTarget);
    }
  };

  // Different styles for different relationship types
  const relationshipStyles = {
    depends_on: 'text-purple-600 hover:text-purple-800',
    supports: 'text-green-600 hover:text-green-800',
    contradicts: 'text-red-600 hover:text-red-800',
    quantifies: 'text-orange-600 hover:text-orange-800',
    elaborates: 'text-teal-600 hover:text-teal-800',
    references: 'text-blue-600 hover:text-blue-800',
  };

  const colorClass = relationshipStyles[relationship] || relationshipStyles.references;

  // Build tooltip: content preview takes priority, fall back to relationship label
  const contentPreview = sectionContents?.[target]?.substring(0, 120);
  const tooltipText = contentPreview
    ? `${contentPreview}…`
    : relationship
    ? `${relationship} → ${FINDING_TYPE_LABELS[target] || target}`
    : FINDING_TYPE_LABELS[target] || target;

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`${colorClass} hover:underline font-medium cursor-pointer bg-transparent border-none p-0 inline`}
      title={tooltipText}
    >
      {children}
    </button>
  );
};

/**
 * WikiLinkMarkdown Component
 *
 * Renders markdown content with support for wiki-style cross-references.
 *
 * Wiki-link syntax:
 * - [[target]] - Links to target section with target as display text
 * - [[target|Display Text]] - Links to target section with custom display text
 *
 * @param {string} content - The markdown content to render
 * @param {function} onNavigate - Callback when a wiki-link is clicked: (tab, subTarget?) => void
 * @param {string} className - Additional CSS classes
 * @param {Array} crossReferences - LLM-extracted cross-references [{phrase, target, relationship, confidence}]
 * @param {boolean} enableAutoDetect - Whether to auto-detect finding mentions (default: true)
 * @param {Object} sectionContents - Map of section_id → text content for tooltip previews
 */
export const WikiLinkMarkdown = ({
  content,
  onNavigate,
  className = '',
  crossReferences = [],
  enableAutoDetect = true,
  sectionContents = {}
}) => {
  // Process content to mark wiki-links
  const processedContent = useMemo(() => {
    return processWikiLinks(content, crossReferences, enableAutoDetect);
  }, [content, crossReferences, enableAutoDetect]);

  // Split content into segments (markdown + wiki-links)
  const segments = useMemo(() => {
    const result = [];
    const regex = /<wiki-link target="([^"]+)"(?: relationship="([^"]+)")?>([^<]+)<\/wiki-link>/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(processedContent)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        result.push({
          type: 'markdown',
          content: processedContent.slice(lastIndex, match.index)
        });
      }

      // Add the wiki-link
      result.push({
        type: 'wiki-link',
        target: match[1],
        relationship: match[2] || 'references',
        text: match[3]
      });

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < processedContent.length) {
      result.push({
        type: 'markdown',
        content: processedContent.slice(lastIndex)
      });
    }

    return result;
  }, [processedContent]);

  return (
    <div className={`prose prose-sm max-w-none ${className}`}>
      {segments.map((segment, index) => {
        if (segment.type === 'wiki-link') {
          // Check if we need leading/trailing space based on adjacent segments
          const prevSegment = segments[index - 1];
          const nextSegment = segments[index + 1];
          const needsLeadingSpace = prevSegment?.type === 'markdown' &&
            prevSegment.content &&
            !prevSegment.content.endsWith(' ') &&
            !prevSegment.content.endsWith('\n');
          const needsTrailingSpace = nextSegment?.type === 'markdown' &&
            nextSegment.content &&
            !nextSegment.content.startsWith(' ') &&
            !nextSegment.content.startsWith('\n') &&
            !nextSegment.content.startsWith(',') &&
            !nextSegment.content.startsWith('.') &&
            !nextSegment.content.startsWith(')');

          return (
            <span key={index}>
              {needsLeadingSpace && ' '}
              <WikiLinkComponent
                target={segment.target}
                relationship={segment.relationship}
                onNavigate={onNavigate}
                sectionContents={sectionContents}
              >
                {segment.text}
              </WikiLinkComponent>
              {needsTrailingSpace && ' '}
            </span>
          );
        }

        // For markdown segments, render directly to preserve whitespace
        // Check if it's simple text without markdown formatting
        const isSimpleText = !segment.content.includes('**') &&
                            !segment.content.includes('*') &&
                            !segment.content.includes('`') &&
                            !segment.content.includes('#') &&
                            !segment.content.includes('[');

        if (isSimpleText) {
          // Render as plain text to preserve all whitespace
          return <span key={index}>{segment.content}</span>;
        }

        return (
          <span key={index} className="inline" style={{ whiteSpace: 'pre-wrap' }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ node, ...props }) => <span {...props} />,
              }}
            >
              {segment.content}
            </ReactMarkdown>
          </span>
        );
      })}
    </div>
  );
};

/**
 * Related Sections Component
 *
 * Shows a summary of cross-references at the bottom of a finding card.
 */
export const RelatedSections = ({ crossReferences = [], onNavigate }) => {
  if (!crossReferences || crossReferences.length === 0) {
    return null;
  }

  // Group by target and take unique targets
  const uniqueTargets = [...new Set(crossReferences.map(r => r.target))];

  return (
    <div className="text-xs text-gray-500 mt-3 pt-2 border-t border-gray-200">
      <span className="font-medium">Related: </span>
      {uniqueTargets.map((target, index) => {
        const mapping = WIKI_LINK_MAP[target];
        if (!mapping) return null;

        return (
          <span key={target}>
            {index > 0 && <span className="mx-1">·</span>}
            <button
              onClick={() => onNavigate(mapping.tab, mapping.subTarget)}
              className="text-blue-500 hover:text-blue-700 hover:underline"
            >
              {FINDING_TYPE_LABELS[target] || target}
            </button>
          </span>
        );
      })}
    </div>
  );
};

/**
 * Export the wiki-link mapping for use in other components
 */
export const getWikiLinkMapping = () => WIKI_LINK_MAP;

/**
 * Get available wiki-link targets for documentation/help
 */
export const getAvailableTargets = () => Object.keys(WIKI_LINK_MAP);

/**
 * Get human-readable label for a finding type
 */
export const getFindingTypeLabel = (type) => FINDING_TYPE_LABELS[type] || type;

export default WikiLinkMarkdown;
