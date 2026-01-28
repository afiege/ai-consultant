import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { companyProfileAPI, apiKeyManager } from '../../services/api';

/**
 * Editable field component for single values
 */
const EditableField = ({ label, value, onChange, placeholder, type = 'text' }) => (
  <div className="mb-3">
    <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
    {type === 'textarea' ? (
      <textarea
        value={value || ''}
        onChange={(e) => onChange(e.target.value || null)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        rows={2}
      />
    ) : (
      <input
        type={type}
        value={value || ''}
        onChange={(e) => onChange(e.target.value || null)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
      />
    )}
  </div>
);

/**
 * Editable field for lists (comma-separated)
 */
const EditableListField = ({ label, value, onChange, placeholder }) => {
  const listValue = Array.isArray(value) ? value.join(', ') : '';

  const handleChange = (text) => {
    if (!text || text.trim() === '') {
      onChange(null);
    } else {
      const items = text.split(',').map(s => s.trim()).filter(s => s);
      onChange(items.length > 0 ? items : null);
    }
  };

  return (
    <div className="mb-3">
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      <input
        type="text"
        value={listValue}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
      />
      <p className="text-xs text-gray-400 mt-1">Comma-separated</p>
    </div>
  );
};

/**
 * Section header for grouping fields
 */
const SectionHeader = ({ title, icon }) => (
  <div className="flex items-center gap-2 mb-3 mt-4 first:mt-0">
    <span className="text-gray-400">{icon}</span>
    <h4 className="text-sm font-semibold text-gray-700">{title}</h4>
  </div>
);

/**
 * Company Profile Editor Component
 *
 * Allows extraction, viewing, and editing of structured company profile.
 */
const CompanyProfileEditor = ({ sessionUuid, hasCompanyInfo, onProfileChange }) => {
  const { t } = useTranslation();

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [extractionQuality, setExtractionQuality] = useState(null);

  // Load existing profile on mount
  useEffect(() => {
    loadProfile();
  }, [sessionUuid]);

  const loadProfile = async () => {
    setLoading(true);
    try {
      const response = await companyProfileAPI.get(sessionUuid);
      if (response.data) {
        setProfile(response.data);
        setIsExpanded(true);
      }
    } catch (err) {
      // No profile yet, that's fine
      console.log('No existing profile');
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async () => {
    const apiKey = apiKeyManager.get();
    if (!apiKey) {
      setError(t('companyProfile.noApiKey'));
      return;
    }

    setExtracting(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await companyProfileAPI.extract(sessionUuid, apiKey);
      setProfile(response.data.profile);
      setExtractionQuality(response.data.extraction_quality);
      setIsExpanded(true);
      setHasChanges(false);
      setSuccess(t('companyProfile.extractionSuccess'));

      if (onProfileChange) {
        onProfileChange(response.data.profile);
      }
    } catch (err) {
      console.error('Extraction error:', err);
      setError(err.response?.data?.detail || t('companyProfile.extractionFailed'));
    } finally {
      setExtracting(false);
    }
  };

  const handleFieldChange = (field, value) => {
    setProfile(prev => ({
      ...prev,
      [field]: value
    }));
    setHasChanges(true);
    setSuccess(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      await companyProfileAPI.save(sessionUuid, profile);
      setHasChanges(false);
      setSuccess(t('companyProfile.saveSuccess'));

      if (onProfileChange) {
        onProfileChange(profile);
      }
    } catch (err) {
      console.error('Save error:', err);
      setError(err.response?.data?.detail || t('companyProfile.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm(t('companyProfile.confirmClear'))) {
      return;
    }

    try {
      await companyProfileAPI.delete(sessionUuid);
      setProfile(null);
      setHasChanges(false);
      setExtractionQuality(null);
      setSuccess(null);

      if (onProfileChange) {
        onProfileChange(null);
      }
    } catch (err) {
      console.error('Delete error:', err);
      setError(t('companyProfile.deleteFailed'));
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {t('companyProfile.title')}
              </h3>
              <p className="text-sm text-gray-500">
                {profile ? t('companyProfile.subtitleEdit') : t('companyProfile.subtitleExtract')}
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            {profile && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-2 text-gray-500 hover:text-gray-700"
              >
                <svg
                  className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="mx-6 mt-4 p-3 bg-green-50 border border-green-200 rounded-md text-sm text-green-700">
          {success}
        </div>
      )}

      {/* Content */}
      <div className="p-6">
        {!profile ? (
          // No profile yet - show extraction button
          <div className="text-center py-6">
            <p className="text-gray-600 mb-4">
              {t('companyProfile.noProfileYet')}
            </p>
            <button
              onClick={handleExtract}
              disabled={extracting || !hasCompanyInfo}
              className={`inline-flex items-center px-6 py-3 rounded-md font-medium transition-colors ${
                hasCompanyInfo && !extracting
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              {extracting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {t('companyProfile.extracting')}
                </>
              ) : (
                <>
                  <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  {t('companyProfile.extractButton')}
                </>
              )}
            </button>
            {!hasCompanyInfo && (
              <p className="text-sm text-gray-500 mt-2">
                {t('companyProfile.needCompanyInfo')}
              </p>
            )}
          </div>
        ) : isExpanded ? (
          // Expanded profile editor
          <>
            {/* Extraction Quality Indicator */}
            {extractionQuality && (
              <div className={`mb-4 p-3 rounded-md text-sm ${
                extractionQuality === 'high' ? 'bg-green-50 text-green-700' :
                extractionQuality === 'medium' ? 'bg-yellow-50 text-yellow-700' :
                'bg-orange-50 text-orange-700'
              }`}>
                {t(`companyProfile.quality.${extractionQuality}`)}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Left Column */}
              <div>
                <SectionHeader title={t('companyProfile.sections.basic')} icon="🏢" />
                <EditableField
                  label={t('companyProfile.fields.name')}
                  value={profile.name}
                  onChange={(v) => handleFieldChange('name', v)}
                  placeholder="Company Name GmbH"
                />
                <EditableField
                  label={t('companyProfile.fields.industry')}
                  value={profile.industry}
                  onChange={(v) => handleFieldChange('industry', v)}
                  placeholder="Manufacturing"
                />
                <EditableField
                  label={t('companyProfile.fields.subIndustry')}
                  value={profile.sub_industry}
                  onChange={(v) => handleFieldChange('sub_industry', v)}
                  placeholder="Automotive Supplier"
                />
                <div className="grid grid-cols-2 gap-3">
                  <EditableField
                    label={t('companyProfile.fields.employeeCount')}
                    value={profile.employee_count}
                    onChange={(v) => handleFieldChange('employee_count', v)}
                    placeholder="50-100"
                  />
                  <EditableField
                    label={t('companyProfile.fields.foundingYear')}
                    value={profile.founding_year}
                    onChange={(v) => handleFieldChange('founding_year', v ? parseInt(v) : null)}
                    placeholder="1990"
                    type="number"
                  />
                </div>
                <EditableField
                  label={t('companyProfile.fields.ownership')}
                  value={profile.ownership}
                  onChange={(v) => handleFieldChange('ownership', v)}
                  placeholder="Family-owned"
                />

                <SectionHeader title={t('companyProfile.sections.location')} icon="📍" />
                <EditableField
                  label={t('companyProfile.fields.headquarters')}
                  value={profile.headquarters}
                  onChange={(v) => handleFieldChange('headquarters', v)}
                  placeholder="Munich, Germany"
                />
                <EditableListField
                  label={t('companyProfile.fields.otherLocations')}
                  value={profile.other_locations}
                  onChange={(v) => handleFieldChange('other_locations', v)}
                  placeholder="Berlin, Prague"
                />
                <EditableListField
                  label={t('companyProfile.fields.marketsServed')}
                  value={profile.markets_served}
                  onChange={(v) => handleFieldChange('markets_served', v)}
                  placeholder="DACH, EU, Global"
                />

                <SectionHeader title={t('companyProfile.sections.financial')} icon="💰" />
                <EditableField
                  label={t('companyProfile.fields.annualRevenue')}
                  value={profile.annual_revenue}
                  onChange={(v) => handleFieldChange('annual_revenue', v)}
                  placeholder="€5-10M"
                />
                <div className="grid grid-cols-2 gap-3">
                  <EditableField
                    label={t('companyProfile.fields.profitMargin')}
                    value={profile.profit_margin}
                    onChange={(v) => handleFieldChange('profit_margin', v)}
                    placeholder="8%"
                  />
                  <EditableField
                    label={t('companyProfile.fields.growthRate')}
                    value={profile.growth_rate}
                    onChange={(v) => handleFieldChange('growth_rate', v)}
                    placeholder="10% YoY"
                  />
                </div>
                <EditableField
                  label={t('companyProfile.fields.cashFlowStatus')}
                  value={profile.cash_flow_status}
                  onChange={(v) => handleFieldChange('cash_flow_status', v)}
                  placeholder="Positive"
                />

                <SectionHeader title={t('companyProfile.sections.operational')} icon="⚙️" />
                <EditableField
                  label={t('companyProfile.fields.productionVolume')}
                  value={profile.production_volume}
                  onChange={(v) => handleFieldChange('production_volume', v)}
                  placeholder="10,000 units/year"
                />
                <EditableField
                  label={t('companyProfile.fields.capacityUtilization')}
                  value={profile.capacity_utilization}
                  onChange={(v) => handleFieldChange('capacity_utilization', v)}
                  placeholder="75%"
                />
              </div>

              {/* Right Column */}
              <div>
                <SectionHeader title={t('companyProfile.sections.business')} icon="💼" />
                <EditableField
                  label={t('companyProfile.fields.coreBusiness')}
                  value={profile.core_business}
                  onChange={(v) => handleFieldChange('core_business', v)}
                  placeholder="Manufacturing of precision components..."
                  type="textarea"
                />
                <EditableListField
                  label={t('companyProfile.fields.productsServices')}
                  value={profile.products_services}
                  onChange={(v) => handleFieldChange('products_services', v)}
                  placeholder="Product A, Service B, Product C"
                />
                <EditableListField
                  label={t('companyProfile.fields.customerSegments')}
                  value={profile.customer_segments}
                  onChange={(v) => handleFieldChange('customer_segments', v)}
                  placeholder="B2B Manufacturing, Automotive OEMs"
                />

                <SectionHeader title={t('companyProfile.sections.technology')} icon="💻" />
                <EditableListField
                  label={t('companyProfile.fields.keyProcesses')}
                  value={profile.key_processes}
                  onChange={(v) => handleFieldChange('key_processes', v)}
                  placeholder="Order Management, Production Planning"
                />
                <EditableListField
                  label={t('companyProfile.fields.currentSystems')}
                  value={profile.current_systems}
                  onChange={(v) => handleFieldChange('current_systems', v)}
                  placeholder="SAP ERP, Excel, Custom CRM"
                />
                <EditableListField
                  label={t('companyProfile.fields.dataSources')}
                  value={profile.data_sources}
                  onChange={(v) => handleFieldChange('data_sources', v)}
                  placeholder="ERP data, Machine sensors, CRM"
                />
                <EditableField
                  label={t('companyProfile.fields.automationLevel')}
                  value={profile.automation_level}
                  onChange={(v) => handleFieldChange('automation_level', v)}
                  placeholder="Partially automated"
                />

                <SectionHeader title={t('companyProfile.sections.challenges')} icon="🎯" />
                <EditableListField
                  label={t('companyProfile.fields.painPoints')}
                  value={profile.pain_points}
                  onChange={(v) => handleFieldChange('pain_points', v)}
                  placeholder="Manual processes, Data silos"
                />
                <EditableListField
                  label={t('companyProfile.fields.digitalizationGoals')}
                  value={profile.digitalization_goals}
                  onChange={(v) => handleFieldChange('digitalization_goals', v)}
                  placeholder="Automate reporting, Improve visibility"
                />
                <EditableField
                  label={t('companyProfile.fields.competitivePressures')}
                  value={profile.competitive_pressures}
                  onChange={(v) => handleFieldChange('competitive_pressures', v)}
                  placeholder="Price pressure from competitors"
                  type="textarea"
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
              <button
                onClick={handleClear}
                className="text-sm text-red-600 hover:text-red-700"
              >
                {t('companyProfile.clearProfile')}
              </button>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleExtract}
                  disabled={extracting}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                >
                  {t('companyProfile.reExtract')}
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || !hasChanges}
                  className={`px-6 py-2 text-sm font-medium rounded-md transition-colors ${
                    hasChanges && !saving
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-200 text-gray-500 cursor-not-allowed'
                  }`}
                >
                  {saving ? t('common.saving') : t('companyProfile.saveChanges')}
                </button>
              </div>
            </div>
          </>
        ) : (
          // Collapsed summary view
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900">{profile.name}</p>
              <p className="text-sm text-gray-500">
                {[profile.industry, profile.headquarters, profile.employee_count && `${profile.employee_count} employees`]
                  .filter(Boolean)
                  .join(' • ')}
              </p>
            </div>
            <button
              onClick={() => setIsExpanded(true)}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              {t('companyProfile.editProfile')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default CompanyProfileEditor;
