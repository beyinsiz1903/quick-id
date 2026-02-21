import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import CameraCapture from '../components/CameraCapture';
import ExtractionForm from '../components/ExtractionForm';
import DuplicateWarning from '../components/DuplicateWarning';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { api } from '../lib/api';
import { Loader2, ChevronLeft, ChevronRight, Users, AlertTriangle, CheckCircle2, Wifi, WifiOff } from 'lucide-react';

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
  const [ocrFallbackMode, setOcrFallbackMode] = useState(false);

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

    try {
      let result;
      if (ocrFallbackMode) {
        // Use offline OCR
        const token = localStorage.getItem('token');
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/scan/ocr-fallback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ image_base64: imageDataUrl }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail?.message || data.detail || 'OCR hatası');
        result = { success: true, documents: data.documents || [], document_count: data.documents?.length || 0, image_quality: data.image_quality };
      } else {
        result = await api.scanId(imageDataUrl);
      }

      if (result.success) {
        const documents = result.documents || [];
        const docCount = result.document_count || documents.length;

        // Store image quality and MRZ data
        if (result.image_quality) setImageQuality(result.image_quality);
        if (result.mrz_results) setMrzResults(result.mrz_results);

        if (documents.length === 0) {
          toast.error('Kimlik belgesi algılanamadı.');
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

        if (docCount > 1) {
          toast.success(`${docCount} kimlik algılandı! Aralarında geçiş yapabilirsiniz.`);
        } else if (documents[0]?.is_valid) {
          toast.success('Kimlik başarıyla okundu!');
        } else {
          toast.warning('Kimlik okunamadı veya kısmi bilgi alındı.');
        }
      }
    } catch (err) {
      toast.error(`Tarama hatası: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  }, []);

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

        // If there are more documents, go to next
        if (currentDocIndex < allDocuments.length - 1) {
          setCurrentDocIndex(prev => prev + 1);
          toast.info('Sonraki kimlik bilgilerini kontrol edin.');
        } else {
          navigate(`/guests/${result.guest.id}`);
        }
      }
    } catch (err) {
      toast.error(`Kaydetme hatası: ${err.message}`);
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
      </div>

      {/* Split Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(520px,1fr)_520px] gap-4">
        {/* Camera */}
        <CameraCapture onCapture={handleCapture} disabled={extracting} />

        {/* Form */}
        <div>
          {extracting && (
            <div className="mb-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--brand-sky-soft)] text-[var(--brand-sky)] text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              AI kimlik okuma yapılıyor, lütfen bekleyin...
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
                      {allDocuments.length} kimlik algılandı
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
