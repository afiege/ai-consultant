import React from 'react';

/**
 * Reusable skeleton/shimmer loading components.
 * Replace full-screen LoadingOverlay with contextual placeholders
 * that match the shape of the content being loaded.
 */

const shimmerClass =
  'animate-pulse bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 bg-[length:200%_100%] rounded';

/** A single rectangular block */
export const SkeletonBlock = ({ className = '' }) => (
  <div className={`${shimmerClass} ${className}`} />
);

/** A text-like line (thin) */
export const SkeletonLine = ({ width = 'w-full', className = '' }) => (
  <div className={`${shimmerClass} h-4 ${width} ${className}`} />
);

/** Several text lines to mimic a paragraph */
export const SkeletonParagraph = ({ lines = 3, className = '' }) => (
  <div className={`space-y-2 ${className}`}>
    {Array.from({ length: lines }).map((_, i) => (
      <SkeletonLine key={i} width={i === lines - 1 ? 'w-3/4' : 'w-full'} />
    ))}
  </div>
);

/** A circle (avatar, icon, etc.) */
export const SkeletonCircle = ({ size = 'w-10 h-10', className = '' }) => (
  <div className={`${shimmerClass} !rounded-full ${size} ${className}`} />
);

/** Card-shaped placeholder with title + body lines */
export const SkeletonCard = ({ className = '' }) => (
  <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
    <SkeletonLine width="w-1/3" className="h-5 mb-4" />
    <SkeletonParagraph lines={3} />
  </div>
);

/** Chat message placeholder (avatar + bubble) */
export const SkeletonChatMessage = ({ isUser = false, className = '' }) => (
  <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} ${className}`}>
    <SkeletonCircle size="w-8 h-8" />
    <div className={`flex-1 max-w-[70%] ${isUser ? 'ml-auto' : ''}`}>
      <SkeletonBlock className="h-20 rounded-lg" />
    </div>
  </div>
);

/** Chat page skeleton: header + message list + input */
export const SkeletonChat = ({ messageCount = 4, className = '' }) => (
  <div className={`space-y-6 ${className}`}>
    {/* Header area */}
    <div className="flex items-center gap-4">
      <SkeletonBlock className="h-8 w-48" />
      <SkeletonBlock className="h-8 w-24 ml-auto" />
    </div>
    {/* Messages */}
    <div className="space-y-4">
      {Array.from({ length: messageCount }).map((_, i) => (
        <SkeletonChatMessage key={i} isUser={i % 2 === 1} />
      ))}
    </div>
    {/* Input area */}
    <SkeletonBlock className="h-12 rounded-lg" />
  </div>
);

/** Session / data loading skeleton: a grid of cards */
export const SkeletonPageGrid = ({ cards = 3, columns = 2, className = '' }) => (
  <div className={`space-y-6 ${className}`}>
    <SkeletonBlock className="h-8 w-64 mb-2" />
    <SkeletonLine width="w-96" className="mb-6" />
    <div className={`grid grid-cols-1 lg:grid-cols-${columns} gap-6`}>
      {Array.from({ length: cards }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  </div>
);

/** Step 6 tabs skeleton */
export const SkeletonTabs = ({ tabCount = 5, className = '' }) => (
  <div className={`space-y-6 ${className}`}>
    {/* Tab bar */}
    <div className="flex gap-2 border-b border-gray-200 pb-3">
      {Array.from({ length: tabCount }).map((_, i) => (
        <SkeletonBlock key={i} className="h-9 w-24 rounded-md" />
      ))}
    </div>
    {/* Tab content */}
    <SkeletonCard />
    <SkeletonParagraph lines={4} />
  </div>
);

/** Inline loading placeholder for a section within an already-rendered page */
export const SkeletonSection = ({ className = '' }) => (
  <div className={`p-6 ${className}`}>
    <SkeletonLine width="w-48" className="h-5 mb-4" />
    <SkeletonParagraph lines={4} />
  </div>
);

export default {
  Block: SkeletonBlock,
  Line: SkeletonLine,
  Paragraph: SkeletonParagraph,
  Circle: SkeletonCircle,
  Card: SkeletonCard,
  ChatMessage: SkeletonChatMessage,
  Chat: SkeletonChat,
  PageGrid: SkeletonPageGrid,
  Tabs: SkeletonTabs,
  Section: SkeletonSection,
};
