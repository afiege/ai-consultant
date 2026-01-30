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
 * Process content to convert wiki-links and auto-detect references.
 *
 * @param {string} content - The markdown content to process
 * @param {boolean} enableAutoDetect - Whether to auto-detect finding mentions
 * @returns {string} - Processed content with wiki-links marked
 */
function processWikiLinks(content, enableAutoDetect = true) {
  if (!content) return '';

  let processed = content;

  // Step 1: Convert explicit wiki-links [[target|text]] or [[target]]
  // Match [[target|display text]] or [[target]]
  const wikiLinkRegex = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;
  processed = processed.replace(wikiLinkRegex, (match, target, displayText) => {
    const text = displayText || target;
    // Convert to a special marker that we'll render as a clickable link
    return `<wiki-link target="${target}">${text}</wiki-link>`;
  });

  // Step 2: Auto-detect finding type mentions (only if not already linked)
  if (enableAutoDetect) {
    for (const { pattern, target } of AUTO_DETECT_PATTERNS) {
      processed = processed.replace(pattern, (match) => {
        // Don't double-link if already inside a wiki-link tag
        if (processed.includes(`<wiki-link target="${target}">${match}</wiki-link>`)) {
          return match;
        }
        return `<wiki-link target="${target}">${match}</wiki-link>`;
      });
    }
  }

  return processed;
}

/**
 * Custom component to render wiki-links as clickable elements.
 */
const WikiLinkComponent = ({ target, children, onNavigate }) => {
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

  return (
    <button
      type="button"
      onClick={handleClick}
      className="text-blue-600 hover:text-blue-800 hover:underline font-medium cursor-pointer bg-transparent border-none p-0 inline"
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
 * @param {boolean} enableAutoDetect - Whether to auto-detect finding mentions (default: true)
 */
export const WikiLinkMarkdown = ({
  content,
  onNavigate,
  className = '',
  enableAutoDetect = true
}) => {
  // Process content to mark wiki-links
  const processedContent = useMemo(() => {
    return processWikiLinks(content, enableAutoDetect);
  }, [content, enableAutoDetect]);

  // Custom components for ReactMarkdown to handle wiki-links
  const components = useMemo(() => ({
    // Handle our custom wiki-link tags embedded in the markdown
    // ReactMarkdown will treat them as raw HTML, so we use dangerouslySetInnerHTML
    // or we parse them differently
  }), [onNavigate]);

  // Since ReactMarkdown sanitizes HTML, we need to handle wiki-links differently
  // We'll post-process the rendered output to convert wiki-link markers to components

  // Alternative approach: Split content into segments and render each appropriately
  const segments = useMemo(() => {
    const result = [];
    const regex = /<wiki-link target="([^"]+)">([^<]+)<\/wiki-link>/g;
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
        text: match[2]
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
          return (
            <WikiLinkComponent
              key={index}
              target={segment.target}
              onNavigate={onNavigate}
            >
              {segment.text}
            </WikiLinkComponent>
          );
        }

        return (
          <ReactMarkdown
            key={index}
            remarkPlugins={[remarkGfm]}
            className="inline"
            components={{
              // Customize rendering as needed
              p: ({ node, ...props }) => <span {...props} />,
              // Keep other elements as-is but ensure inline wiki-links work
            }}
          >
            {segment.content}
          </ReactMarkdown>
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

export default WikiLinkMarkdown;
