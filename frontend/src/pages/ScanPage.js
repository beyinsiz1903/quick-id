import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import CameraCapture from '../components/CameraCapture';
import ExtractionForm from '../components/ExtractionForm';
import DuplicateWarning from '../components/DuplicateWarning';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { api } from '../lib/api';
import {
  Loader2, ChevronLeft, ChevronRight, Users, AlertTriangle, CheckCircle2,
  Wifi, WifiOff, Zap, Brain, Globe, Settings2, DollarSign, Shield,
  Focus, Sun, Sparkles, Maximize, RotateCcw, Info
} from 'lucide-react';

const PROVIDER_OPTIONS = [
  { id: 'auto', label: 'Akıllı Mod', icon: Brain, description: 'Kaliteye göre otomatik seçim', color: 'text-purple-600', bg: 'bg-purple-50', border: 'border-purple-200' },
  { id: 'gpt-4o', label: 'GPT-4o', icon: Brain, description: 'En yüksek doğruluk', color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200', cost: '$0.015' },
  { id: 'gpt-4o-mini', label: 'GPT-4o Mini', icon: Zap, description: 'Hızlı ve ucuz', color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200', cost: '$0.003' },
  { id: 'gemini-flash', label: 'Gemini Flash', icon: Globe, description: 'Google alternatifi', color: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200', cost: '$0.004' },
  { id: 'tesseract', label: 'Offline OCR', icon: WifiOff, description: 'İnternet gerektirmez', color: 'text-gray-600', bg: 'bg-gray-50', border: 'border-gray-200', cost: 'Ücretsiz' },
];

const RECOMMENDATION_ICONS = {
  focus: Focus,
  sun: Sun,
  'sun-dim': Sun,
  sparkles: Sparkles,
  contrast: Settings2,
  maximize: Maximize,
  rotate: RotateCcw,
};

export default function ScanPage() {
  const navigate = useNavigate();
  const [allDocuments, setAllDocuments] = useState([]);
  const [currentDocIndex, setCurrentDocIndex] = useState(0);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scanId, setScanId] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [originalExtractedList, setOriginalExtractedList] = useState([]);
  const [imageQuality, setImageQuality] = useState(null);
  const [mrzResults, setMrzResults] = useState([]);
  const [lastCapturedImage, setLastCapturedImage] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState('auto');
  const [providerInfo, setProviderInfo] = useState(null);
  const [showProviderPanel, setShowProviderPanel] = useState(false);

  // Duplicate handling
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [pendingDuplicates, setPendingDuplicates] = useState([]);

  const currentData = allDocuments[currentDocIndex] || null;

  const setCurrentData = (data) => {
    setAllDocuments(prev => {
      const updated = [...prev];
      updated[currentDocIndex] = data;
      return updated;
    });
  };

  const handleCapture = useCallback(async (imageDataUrl) => {
    setExtracting(true);
    setAllDocuments([]);
    setCurrentDocIndex(0);
    setWarnings([]);
    setImageQuality(null);
    setMrzResults([]);
    setLastCapturedImage(imageDataUrl);
    setProviderInfo(null);

    try {
      let result;
      const isOffline = selectedProvider === 'tesseract';
      const isAuto = selectedProvider === 'auto';

      if (isOffline) {
        // Offline OCR
        result = await api.scanWithOcr(imageDataUrl);
        result = {
          success: true,
          documents: result.documents || [],
          document_count: result.documents?.length || 0,
          image_quality: result.image_quality,
          confidence: result.confidence,
          provider: 'tesseract',
          provider_info: { name: 'Tesseract OCR', cost: 0 },
        };
      } else {
        // AI scan with provider selection
        const provider = isAuto ? null : selectedProvider;
        result = await api.scanId(imageDataUrl, provider, isAuto);
      }

      if (result.success) {
        const documents = result.documents || [];
        const docCount = result.document_count || documents.length;

        // Store metadata
        if (result.image_quality) setImageQuality(result.image_quality);
        if (result.mrz_results) setMrzResults(result.mrz_results);
        if (result.provider_info) setProviderInfo({
          ...result.provider_info,
          provider: result.provider,
          fallback_used: result.fallback_used || false,
        });

        if (documents.length === 0) {
          toast.error('Kimlik belgesi algilanamadi.');
          setExtracting(false);
          return;
        }

        const extractedList = documents.map(data => ({
          first_name: data.first_name || '',
          last_name: data.last_name || '',
          id_number: data.id_number || data.document_number || '',
          birth_date: data.birth_date || '',
          gender: data.gender || '',
          nationality: data.nationality || '',
          document_type: data.document_type || '',
          document_number: data.document_number || '',
          birth_place: data.birth_place || '',
          expiry_date: data.expiry_date || '',
          issue_date: data.issue_date || '',
          mother_name: data.mother_name || '',
          father_name: data.father_name || '',
          is_valid: data.is_valid,
          notes: '',
        }));

        setAllDocuments(extractedList);
        setOriginalExtractedList(extractedList.map(d => ({ ...d })));
        setWarnings(documents.flatMap(d => d.warnings || []));
        setScanId(result.scan?.id || null);
        setCurrentDocIndex(0);

        // Fallback notification
        if (result.fallback_used) {
          toast.warning('AI tarama basarisiz oldu, Tesseract OCR ile tarandi. Sonuclari kontrol edin.');
        } else if (docCount > 1) {
          toast.success(`${docCount} kimlik algilandi! Aralarinda gecis yapabilirsiniz.`);
        } else if (documents[0]?.is_valid) {
          toast.success(`Kimlik basariyla okundu! (${result.provider || 'AI'})`);
        } else {
          toast.warning('Kimlik okunamadi veya kismi bilgi alindi.');
        }
      }
    } catch (err) {
      toast.error(`Tarama hatasi: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  }, [selectedProvider]);

  const handleSave = useCallback(async (forceCreate = false) => {
    if (!currentData) return;

    setSaving(true);
    try {
      const original = originalExtractedList[currentDocIndex] || null;
      const payload = {
        ...currentData,
        scan_id: scanId,
        original_extracted_data: original,
        force_create: forceCreate,
      };
      delete payload.is_valid;

      const result = await api.createGuest(payload);

      if (result.duplicate_detected && !forceCreate) {
        setPendingDuplicates(result.duplicates || []);
        setDuplicateDialogOpen(true);
        setSaving(false);
        return;
      }

      if (result.success) {
        toast.success(`${currentData.first_name} ${currentData.last_name} kaydedildi!`);

        if (currentDocIndex < allDocuments.length - 1) {
          setCurrentDocIndex(prev => prev + 1);
          toast.info('Sonraki kimlik bilgilerini kontrol edin.');
        } else {
          navigate(`/guests/${result.guest.id}`);
        }
      }
    } catch (err) {
      toast.error(`Kaydetme hatasi: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [currentData, currentDocIndex, allDocuments, scanId, originalExtractedList, navigate]);

  const handleForceCreate = useCallback(async () => {
    setDuplicateDialogOpen(false);
    await handleSave(true);
  }, [handleSave]);

  const handleViewExisting = useCallback((guestId) => {
    setDuplicateDialogOpen(false);
    navigate(`/guests/${guestId}`);
  }, [navigate]);

  const selectedProviderOption = PROVIDER_OPTIONS.find(p => p.id === selectedProvider);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--brand-ink)]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          Kimlik Tarama
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Kimlik kartını kameraya gösterin, bilgiler otomatik çıkarılacak (çoklu kimlik destekli)
        </p>

        {/* Provider Selection Toggle */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowProviderPanel(!showProviderPanel)}
            className={`${selectedProviderOption?.bg} ${selectedProviderOption?.border} ${selectedProviderOption?.color}`}
          >
            {selectedProviderOption && <selectedProviderOption.icon className="w-4 h-4 mr-1.5" />}
            {selectedProviderOption?.label || 'Provider Sec'}
            <Settings2 className="w-3.5 h-3.5 ml-1.5 opacity-60" />
          </Button>

          {selectedProvider !== 'auto' && selectedProvider !== 'tesseract' && (
            <Badge variant="outline" className="text-xs">
              <DollarSign className="w-3 h-3 mr-0.5" />
              {PROVIDER_OPTIONS.find(p => p.id === selectedProvider)?.cost || ''}
            </Badge>
          )}

          {selectedProvider === 'tesseract' && (
            <Badge variant="outline" className="text-amber-600 border-amber-200 bg-amber-50">
              <WifiOff className="w-3 h-3 mr-1" />
              Offline OCR - Dusuk dogruluk
            </Badge>
          )}

          {selectedProvider === 'auto' && (
            <Badge variant="outline" className="text-purple-600 border-purple-200 bg-purple-50">
              <Brain className="w-3 h-3 mr-1" />
              Goruntu kalitesine gore otomatik secim
            </Badge>
          )}
        </div>

        {/* Provider Selection Panel */}
        {showProviderPanel && (
          <Card className="mt-3 border-2">
            <CardContent className="p-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium">Tarama Saglayicisi Sec</p>
                <Button variant="ghost" size="sm" onClick={() => setShowProviderPanel(false)} className="h-6 px-2 text-xs">
                  Kapat
                </Button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
                {PROVIDER_OPTIONS.map((option) => {
                  const Icon = option.icon;
                  const isSelected = selectedProvider === option.id;
                  return (
                    <button
                      key={option.id}
                      onClick={() => { setSelectedProvider(option.id); setShowProviderPanel(false); }}
                      className={`flex flex-col items-start p-2.5 rounded-lg border-2 text-left transition-all ${
                        isSelected
                          ? `${option.border} ${option.bg} ring-2 ring-offset-1 ring-current`
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <Icon className={`w-4 h-4 ${isSelected ? option.color : 'text-gray-400'}`} />
                        <span className={`text-sm font-medium ${isSelected ? option.color : 'text-gray-700'}`}>
                          {option.label}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-tight">{option.description}</p>
                      {option.cost && (
                        <span className="text-[10px] mt-1 px-1.5 py-0.5 rounded bg-white/80 border text-muted-foreground">
                          {option.cost}/tarama
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
              <div className="mt-2 p-2 rounded-md bg-blue-50 border border-blue-200">
                <div className="flex items-start gap-1.5">
                  <Info className="w-3.5 h-3.5 text-blue-500 mt-0.5 shrink-0" />
                  <p className="text-[11px] text-blue-700">
                    <strong>Akilli Mod</strong> goruntu kalitesine gore en uygun saglayiciyi otomatik secer.
                    Yuksek kaliteli goruntulerde ucuz provider, dusuk kalitede en iyi provider kullanilir.
                    AI basarisiz olursa Tesseract OCR otomatik devreye girer.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Image Quality Warning (Enhanced) */}
      {imageQuality && imageQuality.quality_checked && imageQuality.warnings?.length > 0 && (
        <Card className={`border-2 ${imageQuality.overall_quality === 'poor' ? 'border-red-200 bg-red-50/50' : 'border-amber-200 bg-amber-50/50'}`}>
          <CardContent className="p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className={`w-5 h-5 mt-0.5 shrink-0 ${imageQuality.overall_quality === 'poor' ? 'text-red-500' : 'text-amber-500'}`} />
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-medium text-sm">
                    Goruntu Kalitesi: {imageQuality.overall_quality === 'good' ? 'Iyi' : imageQuality.overall_quality === 'acceptable' ? 'Kabul Edilebilir' : 'Dusuk'}
                  </p>
                  <Badge variant="outline" className={`text-xs ${
                    imageQuality.overall_score >= 80 ? 'text-green-600 border-green-200' :
                    imageQuality.overall_score >= 50 ? 'text-amber-600 border-amber-200' :
                    'text-red-600 border-red-200'
                  }`}>
                    {imageQuality.overall_score}/100
                  </Badge>
                  {imageQuality.suggested_provider && (
                    <Badge variant="outline" className="text-xs text-blue-600 border-blue-200">
                      Onerilen: {imageQuality.suggested_provider}
                    </Badge>
                  )}
                </div>
                <ul className="text-xs text-muted-foreground mt-1 space-y-0.5">
                  {imageQuality.warnings.map((w, i) => <li key={i}>&#8226; {w}</li>)}
                </ul>

                {/* Enhancement Recommendations */}
                {imageQuality.recommendations && imageQuality.recommendations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {imageQuality.recommendations.map((rec, i) => {
                      const RecIcon = RECOMMENDATION_ICONS[rec.icon] || AlertTriangle;
                      return (
                        <div key={i} className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] ${
                          rec.priority === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                        }`}>
                          <RecIcon className="w-3 h-3" />
                          <span>{rec.action}</span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Quality Detail Checks */}
                {imageQuality.checks && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {Object.entries(imageQuality.checks).map(([key, check]) => {
                      const isOk = check.score_penalty === 0;
                      const label = {
                        blur: 'Netlik', brightness: 'Aydinlik', resolution: 'Cozunurluk',
                        contrast: 'Kontrast', glare: 'Parlama', document_edges: 'Kenar',
                        skew: 'Egiklik'
                      }[key] || key;
                      return (
                        <span key={key} className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] ${
                          isOk ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {isOk ? '✓' : '✗'} {label}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Provider Info */}
      {providerInfo && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="p-2.5">
            <div className="flex items-center gap-2 flex-wrap">
              <Shield className="w-4 h-4 text-blue-500" />
              <span className="text-xs font-medium text-blue-700">
                Tarama: {providerInfo.name || providerInfo.provider}
              </span>
              {providerInfo.response_time && (
                <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-200">
                  {providerInfo.response_time}s
                </Badge>
              )}
              {providerInfo.cost !== undefined && providerInfo.cost > 0 && (
                <Badge variant="outline" className="text-[10px] text-green-600 border-green-200">
                  ~${providerInfo.cost}
                </Badge>
              )}
              {providerInfo.fallback_used && (
                <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-200 bg-amber-50">
                  Fallback kullanildi
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* MRZ Results (Enhanced) */}
      {mrzResults.length > 0 && (
        <Card className="border-green-200 bg-green-50/50">
          <CardContent className="p-3">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="font-medium text-sm text-green-700">MRZ Bolgesi Okundu</p>
                <p className="text-xs text-green-600">{mrzResults[0]?.message}</p>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {mrzResults[0]?.mrz_type && (
                    <Badge variant="outline" className="text-[10px] text-green-600 border-green-200">
                      {mrzResults[0].mrz_type} Format
                    </Badge>
                  )}
                  {mrzResults[0]?.icao_compliant && (
                    <Badge variant="outline" className="text-[10px] text-green-600 border-green-200">
                      ICAO 9303 Uyumlu
                    </Badge>
                  )}
                  {mrzResults[0]?.ocr_corrected && (
                    <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-200">
                      OCR Duzeltme Uygulandi
                    </Badge>
                  )}
                  {mrzResults[0]?.fuzzy_matched && (
                    <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-200">
                      Fuzzy Esleme
                    </Badge>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Split Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(520px,1fr)_520px] gap-4">
        {/* Camera */}
        <CameraCapture onCapture={handleCapture} disabled={extracting} />

        {/* Form */}
        <div>
          {extracting && (
            <div className="mb-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--brand-sky-soft)] text-[var(--brand-sky)] text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              {selectedProvider === 'tesseract'
                ? 'Offline OCR tarama yapiliyor...'
                : selectedProvider === 'auto'
                  ? 'Akilli tarama yapiliyor (en uygun provider seciliyor)...'
                  : `${selectedProviderOption?.label} ile tarama yapiliyor...`
              }
            </div>
          )}

          {/* Multi-document navigator */}
          {allDocuments.length > 1 && (
            <Card className="bg-white mb-3">
              <CardContent className="p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-[var(--brand-sky)]" />
                    <span className="text-sm font-medium">
                      {allDocuments.length} kimlik algilandi
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8"
                      disabled={currentDocIndex === 0}
                      onClick={() => setCurrentDocIndex(i => i - 1)}
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </Button>
                    <Badge variant="outline" className="bg-[var(--brand-sky-soft)] text-[var(--brand-sky)] border-[var(--brand-sky)] px-3 font-semibold">
                      {currentDocIndex + 1} / {allDocuments.length}
                    </Badge>
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8"
                      disabled={currentDocIndex === allDocuments.length - 1}
                      onClick={() => setCurrentDocIndex(i => i + 1)}
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                {/* Document tabs */}
                <div className="flex gap-1.5 mt-2">
                  {allDocuments.map((doc, i) => (
                    <button
                      key={i}
                      onClick={() => setCurrentDocIndex(i)}
                      className={`flex-1 text-xs py-1.5 px-2 rounded-md transition-colors ${
                        i === currentDocIndex
                          ? 'bg-[var(--brand-sky)] text-white'
                          : 'bg-[hsl(var(--secondary))] text-muted-foreground hover:bg-[hsl(var(--border))]'
                      }`}
                    >
                      {doc.first_name || doc.last_name
                        ? `${doc.first_name} ${doc.last_name}`.trim()
                        : `Kimlik ${i + 1}`}
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <ExtractionForm
            data={currentData}
            onChange={setCurrentData}
            onSave={() => handleSave(false)}
            loading={saving}
            extracting={extracting}
            warnings={currentData ? (allDocuments[currentDocIndex]?.warnings || warnings) : warnings}
          />
        </div>
      </div>

      {/* Duplicate Warning */}
      <DuplicateWarning
        open={duplicateDialogOpen}
        onClose={() => setDuplicateDialogOpen(false)}
        duplicates={pendingDuplicates}
        onForceCreate={handleForceCreate}
        onViewExisting={handleViewExisting}
      />
    </div>
  );
}
