import React from 'react';
import { EmptyState, DimensionScore } from './SharedWidgets';

const CompanyProfileTab = ({ findings, session, t, onNavigate }) => {
  const structuredProfile = findings?.company_info?.structured_profile;
  const rawInfo = findings?.company_info?.raw_info || [];
  const maturity = findings?.maturity;

  if (!structuredProfile && rawInfo.length === 0 && !maturity) {
    return <EmptyState message={t('step6.incomplete.companyProfile')} />;
  }

  const getScoreColor = (score) => {
    if (score < 2) return 'bg-red-500';
    if (score < 3) return 'bg-orange-500';
    if (score < 4) return 'bg-yellow-500';
    if (score < 5) return 'bg-blue-500';
    return 'bg-green-500';
  };

  const ProfileField = ({ label, value }) => {
    if (!value) return null;
    const displayValue = Array.isArray(value) ? value.join(', ') : value;
    return (
      <div className="py-2 border-b border-gray-100 last:border-0">
        <dt className="text-sm font-medium text-gray-500">{label}</dt>
        <dd className="mt-1 text-sm text-gray-900">{displayValue}</dd>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-gray-900">
        {structuredProfile?.name || session?.company_name || t('step6.unknownCompany')}
      </h3>

      {structuredProfile && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.basic')}</h4>
            <dl>
              <ProfileField label={t('companyProfile.fields.industry')} value={structuredProfile.industry} />
              <ProfileField label={t('companyProfile.fields.subIndustry')} value={structuredProfile.sub_industry} />
              <ProfileField label={t('companyProfile.fields.employeeCount')} value={structuredProfile.employee_count} />
              <ProfileField label={t('companyProfile.fields.foundingYear')} value={structuredProfile.founding_year} />
              <ProfileField label={t('companyProfile.fields.ownership')} value={structuredProfile.ownership} />
            </dl>
          </div>

          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.location')}</h4>
            <dl>
              <ProfileField label={t('companyProfile.fields.headquarters')} value={structuredProfile.headquarters} />
              <ProfileField label={t('companyProfile.fields.otherLocations')} value={structuredProfile.other_locations} />
              <ProfileField label={t('companyProfile.fields.marketsServed')} value={structuredProfile.markets_served} />
            </dl>
          </div>

          {(structuredProfile.annual_revenue || structuredProfile.profit_margin || structuredProfile.growth_rate) && (
            <div className="bg-blue-50 rounded-lg p-4">
              <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.financial')}</h4>
              <dl>
                <ProfileField label={t('companyProfile.fields.annualRevenue')} value={structuredProfile.annual_revenue} />
                <ProfileField label={t('companyProfile.fields.profitMargin')} value={structuredProfile.profit_margin} />
                <ProfileField label={t('companyProfile.fields.growthRate')} value={structuredProfile.growth_rate} />
                <ProfileField label={t('companyProfile.fields.cashFlowStatus')} value={structuredProfile.cash_flow_status} />
              </dl>
            </div>
          )}

          {(structuredProfile.production_volume || structuredProfile.capacity_utilization) && (
            <div className="bg-blue-50 rounded-lg p-4">
              <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.operational')}</h4>
              <dl>
                <ProfileField label={t('companyProfile.fields.productionVolume')} value={structuredProfile.production_volume} />
                <ProfileField label={t('companyProfile.fields.capacityUtilization')} value={structuredProfile.capacity_utilization} />
              </dl>
            </div>
          )}

          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.business')}</h4>
            <dl>
              <ProfileField label={t('companyProfile.fields.coreBusiness')} value={structuredProfile.core_business} />
              <ProfileField label={t('companyProfile.fields.productsServices')} value={structuredProfile.products_services} />
              <ProfileField label={t('companyProfile.fields.customerSegments')} value={structuredProfile.customer_segments} />
              <ProfileField label={t('companyProfile.fields.keyProcesses')} value={structuredProfile.key_processes} />
            </dl>
          </div>

          {(structuredProfile.current_systems || structuredProfile.data_sources || structuredProfile.automation_level) && (
            <div className="bg-blue-50 rounded-lg p-4">
              <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.technology')}</h4>
              <dl>
                <ProfileField label={t('companyProfile.fields.currentSystems')} value={structuredProfile.current_systems} />
                <ProfileField label={t('companyProfile.fields.dataSources')} value={structuredProfile.data_sources} />
                <ProfileField label={t('companyProfile.fields.automationLevel')} value={structuredProfile.automation_level} />
              </dl>
            </div>
          )}

          {(structuredProfile.pain_points || structuredProfile.digitalization_goals || structuredProfile.competitive_pressures) && (
            <div className="bg-blue-50 rounded-lg p-4 lg:col-span-2">
              <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.challenges')}</h4>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-4">
                <ProfileField label={t('companyProfile.fields.painPoints')} value={structuredProfile.pain_points} />
                <ProfileField label={t('companyProfile.fields.digitalizationGoals')} value={structuredProfile.digitalization_goals} />
                <ProfileField label={t('companyProfile.fields.competitivePressures')} value={structuredProfile.competitive_pressures} />
              </dl>
            </div>
          )}
        </div>
      )}

      {maturity && (
        <div className="bg-purple-50 rounded-lg p-4">
          <h4 className="font-medium text-purple-800 mb-4">{t('step6.sections.maturity')}</h4>
          <div className="flex items-center gap-4 mb-4">
            <span className={`px-4 py-2 rounded-full text-white font-bold text-lg ${getScoreColor(maturity.overall_score)}`}>
              {maturity.overall_score?.toFixed(1)}/6
            </span>
            <span className="text-xl font-medium text-gray-700">{maturity.maturity_level}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <DimensionScore label={t('step6.maturity.resources')} score={maturity.resources_score} />
            <DimensionScore label={t('step6.maturity.infoSystems')} score={maturity.information_systems_score} />
            <DimensionScore label={t('step6.maturity.culture')} score={maturity.culture_score} />
            <DimensionScore label={t('step6.maturity.orgStructure')} score={maturity.organizational_structure_score} />
          </div>
        </div>
      )}

      {!structuredProfile && rawInfo.length > 0 && (
        <div className="space-y-4">
          <h4 className="font-medium text-gray-800">{t('step6.rawInfo')}</h4>
          {rawInfo.map((info, index) => (
            <div key={index} className="bg-gray-50 rounded-lg p-4">
              <p className="text-sm font-medium text-gray-600 mb-1">{info.info_type}</p>
              <p className="text-gray-700 whitespace-pre-wrap">{info.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CompanyProfileTab;
