import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ModelTierConfig } from '@/components/model/ModelTierConfig';
import type { ProviderModelsData } from '@/components/model/types';
import { useAllModels } from '@/hooks/useAllModels';
import { useConfiguredProviders } from '@/hooks/useConfiguredProviders';
import { useFilteredModels } from '@/hooks/useFilteredModels';
import type { ModelMetadataEntry } from '@/hooks/useFilteredModels';
import { useModelAccessMap } from '@/hooks/usePlatformModels';
import { usePreferences } from '@/hooks/usePreferences';
import { useUpdatePreferences } from '@/hooks/useUpdatePreferences';
import { useTranslation } from 'react-i18next';

// ---------------------------------------------------------------------------
// DefaultsStep — Step 5: Set default primary + flash models
// ---------------------------------------------------------------------------

export default function DefaultsStep() {
  const navigate = useNavigate();
  const { models, platform, isLoading: modelsLoading } = useAllModels();
  const { providers: configuredProviders } = useConfiguredProviders();
  const { preferences } = usePreferences();
  const updatePreferences = useUpdatePreferences();
  const { t } = useTranslation();

  // ---------------------------------------------------------------------------
  // Filter models to only those the user has access to.
  //
  // Uses the shared filterModelsByAccess logic which checks both the model's
  // own provider (direct match) and the groupKey fallback (only when the
  // configured provider's access_type matches the model's access_type).
  // This prevents OAuth/coding_plan variants from leaking through groupKey.
  // ---------------------------------------------------------------------------

  const { providerMap, metadata } = useMemo(() => {
    if (!models) return { providerMap: {} as Record<string, ProviderModelsData>, metadata: {} as Record<string, ModelMetadataEntry> };
    const raw = models as Record<string, unknown>;
    const rawProviderMap = (raw.models ?? raw) as Record<string, Record<string, unknown>>;
    const rawMetadata = (raw.model_metadata ?? {}) as Record<string, ModelMetadataEntry>;

    const pm: Record<string, ProviderModelsData> = {};
    for (const [groupKey, data] of Object.entries(rawProviderMap)) {
      if (!data || typeof data !== 'object') continue;
      pm[groupKey] = {
        models: (data.models as string[]) ?? [],
        display_name: (data.display_name as string) ?? groupKey,
      };
    }
    return { providerMap: pm, metadata: rawMetadata };
  }, [models]);

  const accessFilteredModels = useFilteredModels(providerMap, metadata, configuredProviders);
  // In platform mode, providerMap is already tier-filtered by useAllModels.
  // In OSS mode, filter by configured providers.
  const normalizedModels = platform ? providerMap : accessFilteredModels;

  const modelAccessMap = useModelAccessMap(normalizedModels, metadata, platform);

  // System defaults from models response
  const systemDefaults = useMemo(() => {
    if (!models) return undefined;
    const raw = models as Record<string, unknown>;
    return raw.system_defaults as {
      default_model?: string;
      flash_model?: string;
      summarization_model?: string;
      fetch_model?: string;
      fallback_models?: string[];
    } | undefined;
  }, [models]);

  // ---------------------------------------------------------------------------
  // Selection state — seed from existing preferences if available
  // ---------------------------------------------------------------------------

  const prefs = preferences as Record<string, unknown> | null;
  const otherPref = (prefs?.other_preference ?? {}) as Record<string, unknown>;

  const [primaryModel, setPrimaryModel] = useState<string>(
    () => (otherPref.preferred_model as string) ?? '',
  );
  const [flashModel, setFlashModel] = useState<string>(
    () => (otherPref.preferred_flash_model as string) ?? '',
  );
  const [advancedModels, setAdvancedModels] = useState<{
    summarizationModel: string;
    fetchModel: string;
    fallbackModels: string[];
  }>({
    summarizationModel: (otherPref.summarization_model as string) ?? '',
    fetchModel: (otherPref.fetch_model as string) ?? '',
    fallbackModels: (otherPref.fallback_models as string[]) ?? [],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canContinue = Boolean(primaryModel && flashModel);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleBack = useCallback(() => {
    navigate('/setup/models');
  }, [navigate]);

  const handleAdvancedChange = useCallback(
    (updated: { summarizationModel?: string; fetchModel?: string; fallbackModels?: string[] }) => {
      setAdvancedModels((prev) => ({ ...prev, ...updated }));
    },
    [],
  );

  const handleNext = useCallback(async () => {
    if (!primaryModel || !flashModel) return;

    setSaving(true);
    setError(null);

    try {
      // Summarization + fetch default to flash model if not explicitly set
      const summarization = advancedModels.summarizationModel || flashModel;
      const fetchModel = advancedModels.fetchModel || flashModel;

      await updatePreferences.mutateAsync({
        other_preference: {
          preferred_model: primaryModel,
          preferred_flash_model: flashModel,
          summarization_model: summarization,
          fetch_model: fetchModel,
          fallback_models: advancedModels.fallbackModels,
        },
      });

      navigate('/setup/ready');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : err?.message ?? t('setup.errorSavePrefs'));
    } finally {
      setSaving(false);
    }
  }, [primaryModel, flashModel, advancedModels, updatePreferences, navigate, t]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (modelsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 sm:gap-6">
      {/* Section heading */}
      <div className="flex flex-col gap-1">
        <h2
          className="font-semibold"
          style={{ fontSize: '1.125rem', color: 'var(--color-text-primary)' }}
        >
          {t('setup.chooseYourModels')}
        </h2>
        <p
          className="text-sm"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {t('setup.chooseYourModelsDesc')}
        </p>
      </div>

      {/* Model access reminder */}
      <div
        className="flex items-start gap-2.5 rounded-lg px-3.5 py-3"
        style={{
          background: 'var(--color-accent-soft)',
          border: '1px solid var(--color-accent-primary)',
        }}
      >
        <Info
          className="h-4 w-4 shrink-0 mt-0.5"
          style={{ color: 'var(--color-accent-primary)' }}
        />
        <p
          className="text-xs leading-relaxed"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {t('setup.modelAccessReminder')}
        </p>
      </div>

      {/* Model tier config — no filterProviders needed, models are pre-filtered */}
      <ModelTierConfig
        models={normalizedModels}
        primaryModel={primaryModel}
        onPrimaryModelChange={setPrimaryModel}
        flashModel={flashModel}
        onFlashModelChange={setFlashModel}
        showExplainer
        showAdvanced
        advancedModels={advancedModels}
        onAdvancedModelsChange={handleAdvancedChange}
        systemDefaults={systemDefaults}
        modelAccess={modelAccessMap}
      />

      {/* Error */}
      {error && (
        <p className="text-sm" style={{ color: 'var(--color-loss)' }}>
          {error}
        </p>
      )}

      {/* Navigation buttons */}
      <div className="flex items-center justify-between pt-2">
        <Button variant="outline" onClick={handleBack}>
          {t('setup.back')}
        </Button>
        <Button
          variant="default"
          disabled={saving || !canContinue}
          onClick={handleNext}
          className="min-w-[120px]"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
              {t('setup.saving')}
            </>
          ) : (
            t('setup.continue')
          )}
        </Button>
      </div>
    </div>
  );
}
