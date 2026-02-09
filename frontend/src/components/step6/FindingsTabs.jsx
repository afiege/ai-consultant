import React from 'react';
import { WikiLinkMarkdown, RelatedSections } from '../common/WikiLinkMarkdown';
import { EmptyState } from './SharedWidgets';

export const CrispDmTab = ({ findings, t, onNavigate, crossReferences }) => {
  const crisp = findings?.crisp_dm;

  const sections = [
    { id: 'business_objectives', key: 'objectives', data: crisp?.business_objectives },
    { id: 'situation_assessment', key: 'situation', data: crisp?.situation_assessment },
    { id: 'ai_goals', key: 'aiGoals', data: crisp?.ai_goals },
    { id: 'project_plan', key: 'projectPlan', data: crisp?.project_plan },
  ];

  const hasAnyData = sections.some(section => section.data?.text);

  if (!hasAnyData) {
    return <EmptyState message={t('step6.incomplete.crispDm')} />;
  }

  return (
    <div className="space-y-6">
      {sections.map(section => section.data?.text && (
        <div key={section.id} id={`finding-${section.id}`} className="bg-green-50 rounded-lg p-4">
          <h4 className="font-medium text-green-800 mb-2">{t(`step6.crispDm.${section.key}`)}</h4>
          <WikiLinkMarkdown
            content={section.data.text}
            onNavigate={onNavigate}
            className="text-green-700"
            crossReferences={crossReferences?.[section.id] || []}
          />
          <RelatedSections crossReferences={crossReferences?.[section.id] || []} onNavigate={onNavigate} />
        </div>
      ))}
    </div>
  );
};

export const BusinessCaseTab = ({ findings, t, onNavigate, crossReferences }) => {
  const bc = findings?.business_case;

  const sections = [
    { id: 'classification', key: 'classification', data: bc?.classification },
    { id: 'calculation', key: 'calculation', data: bc?.calculation },
    { id: 'validation_questions', key: 'validation', data: bc?.validation_questions },
    { id: 'management_pitch', key: 'pitch', data: bc?.management_pitch },
  ];

  const hasAnyData = sections.some(section => section.data?.text);

  if (!hasAnyData) {
    return <EmptyState message={t('step6.incomplete.businessCase')} />;
  }

  return (
    <div className="space-y-6">
      {sections.map(section => section.data?.text && (
        <div key={section.id} id={`finding-${section.id}`} className="bg-orange-50 rounded-lg p-4">
          <h4 className="font-medium text-orange-800 mb-2">{t(`step6.businessCase.${section.key}`)}</h4>
          <WikiLinkMarkdown
            content={section.data.text}
            onNavigate={onNavigate}
            className="text-orange-700"
            crossReferences={crossReferences?.[`business_case_${section.id}`] || []}
          />
          <RelatedSections crossReferences={crossReferences?.[`business_case_${section.id}`] || []} onNavigate={onNavigate} />
        </div>
      ))}
    </div>
  );
};

export const CostsTab = ({ findings, t, onNavigate, crossReferences }) => {
  const costs = findings?.costs;

  const sections = [
    { id: 'complexity', key: 'complexity', data: costs?.complexity },
    { id: 'initial_investment', key: 'initial', data: costs?.initial_investment },
    { id: 'recurring_costs', key: 'recurring', data: costs?.recurring_costs },
    { id: 'maintenance', key: 'maintenance', data: costs?.maintenance },
    { id: 'tco', key: 'tco', data: costs?.tco },
    { id: 'cost_drivers', key: 'drivers', data: costs?.cost_drivers },
    { id: 'optimization', key: 'optimization', data: costs?.optimization },
    { id: 'roi_analysis', key: 'roi', data: costs?.roi_analysis },
  ];

  const hasAnyData = sections.some(section => section.data?.text);

  if (!hasAnyData) {
    return <EmptyState message={t('step6.incomplete.costs')} />;
  }

  return (
    <div className="space-y-6">
      {sections.map(section => section.data?.text && (
        <div key={section.id} id={`finding-${section.id}`} className="bg-red-50 rounded-lg p-4">
          <h4 className="font-medium text-red-800 mb-2">{t(`step6.costs.${section.key}`)}</h4>
          <WikiLinkMarkdown
            content={section.data.text}
            onNavigate={onNavigate}
            className="text-red-700"
            crossReferences={crossReferences?.[`cost_${section.id}`] || []}
          />
          <RelatedSections crossReferences={crossReferences?.[`cost_${section.id}`] || []} onNavigate={onNavigate} />
        </div>
      ))}
    </div>
  );
};
