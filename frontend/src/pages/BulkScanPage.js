import React, { useState, useCallback, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import CameraCapture from '../components/CameraCapture';
import ExtractionForm from '../components/ExtractionForm';
import DuplicateWarning from '../components/DuplicateWarning';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { StatusBadge } from '../components/StatusBadges';
import { api } from '../lib/api';
import { Layers, Undo2, Check, Camera, Loader2, Users, Keyboard, Zap } from 'lucide-react';

export default function BulkScanPage() {
  const navigate = useNavigate();
  const [extractedData, setExtractedData] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scanId, setScanId] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [scannedGuests, setScannedGuests] = useState([]);
  const [cameraKey, setCameraKey] = useState(0);
  const [autoExtract, setAutoExtract] = useState(true);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [originalExtracted, setOriginalExtracted] = useState(null);
  
  // Duplicate handling
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [pendingDuplicates, setPendingDuplicates] = useState([]);
  
  const saveRef = useRef(null);
  saveRef.current = { extractedData, scanId, originalExtracted };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl/Cmd + S = Save
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (saveRef.current.extractedData && !saving && !extracting) {
          handleSave();
        }
      }
      // Ctrl/Cmd + R = Reset/Retake (only when not in input)
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        if (document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
          e.preventDefault();
          resetForNextScan();
        }
      }
      // Escape = Cancel/Reset
      if (e.key === 'Escape') {
        if (duplicateDialogOpen) {
          setDuplicateDialogOpen(false);
        } else {
          resetForNextScan();
        }
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [saving, extracting, duplicateDialogOpen]);

  const resetForNextScan = useCallback(() => {
    setExtractedData(null);
    setScanId(null);
    setWarnings([]);
    setOriginalExtracted(null);
    setCameraKey(prev => prev + 1);
  }, []);

  const handleCapture = useCallback(async (imageDataUrl) => {
    if (!autoExtract) {
      // Just capture, don't extract yet
      return;
    }
    
    setExtracting(true);
    setExtractedData(null);
    setWarnings([]);
    
    try {
      const result = await api.scanId(imageDataUrl);
      
      if (result.success && result.extracted_data) {
        const data = result.extracted_data;
        const extracted = {
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
          is_valid: data.is_valid,
          notes: '',
        };
        setExtractedData(extracted);
        // Store original for audit trail
        setOriginalExtracted({ ...extracted });
        setWarnings(data.warnings || []);
        setScanId(result.scan?.id || null);
        
        if (data.is_valid) {
          toast.success('Kimlik okundu! Ctrl+S ile kaydedin.');
        } else {
          toast.warning('Kısmi bilgi alındı, kontrol edin.');
        }
      }
    } catch (err) {
      toast.error(`Tarama hatası: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  }, [autoExtract]);

  const handleSave = useCallback(async (forceCreate = false) => {
    const currentData = saveRef.current.extractedData;
    const currentScanId = saveRef.current.scanId;
    const currentOriginal = saveRef.current.originalExtracted;
    if (!currentData) return;
    
    setSaving(true);
    try {
      const payload = { 
        ...currentData, 
        scan_id: currentScanId,
        original_extracted_data: currentOriginal,
        force_create: forceCreate
      };
      delete payload.is_valid;
      
      const result = await api.createGuest(payload);
      
      // Check for duplicate detection
      if (result.duplicate_detected && !forceCreate) {
        setPendingDuplicates(result.duplicates || []);
        setDuplicateDialogOpen(true);
        setSaving(false);
        return;
      }
      
      if (result.success) {
        setScannedGuests(prev => [result.guest, ...prev]);
        toast.success(`${currentData.first_name} ${currentData.last_name} kaydedildi! (Ctrl+R: Sonraki)`);
        resetForNextScan();
      }
    } catch (err) {
      toast.error(`Kaydetme hatası: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [resetForNextScan]);

  const handleForceCreate = useCallback(async () => {
    setDuplicateDialogOpen(false);
    await handleSave(true);
  }, [handleSave]);

  const handleViewExisting = useCallback((guestId) => {
    setDuplicateDialogOpen(false);
    navigate(`/guests/${guestId}`);
  }, [navigate]);

  const undoLast = useCallback(async () => {
    if (scannedGuests.length === 0) return;
    const lastGuest = scannedGuests[0];
    try {
      await api.deleteGuest(lastGuest.id);
      setScannedGuests(prev => prev.slice(1));
      toast.info('Son misafir kaydı geri alındı.');
    } catch (err) {
      toast.error('Geri alma hatası.');
    }
  }, [scannedGuests]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--brand-ink)]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            Toplu Tarama
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Ardı ardına kimlik tarayın, hızlıca kaydedin
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="h-9 px-4 text-base font-semibold bg-[var(--brand-sky-soft)] text-[var(--brand-sky)] border-[var(--brand-sky)]" data-testid="bulk-scan-counter">
            <Users className="w-4 h-4 mr-2" />
            {scannedGuests.length} Misafir
          </Badge>
          {scannedGuests.length > 0 && (
            <Button variant="outline" size="sm" onClick={undoLast} data-testid="bulk-scan-undo-button">
              <Undo2 className="w-4 h-4 mr-1" />
              Geri Al
            </Button>
          )}
        </div>
      </div>

      {/* Controls Bar */}
      <Card className="bg-white">
        <CardContent className="p-3">
          <div className="flex flex-wrap items-center gap-4 sm:gap-6">
            {/* Auto Extract Toggle */}
            <div className="flex items-center gap-2">
              <Switch
                id="auto-extract"
                checked={autoExtract}
                onCheckedChange={setAutoExtract}
                data-testid="auto-extract-toggle"
              />
              <Label htmlFor="auto-extract" className="text-sm flex items-center gap-1.5 cursor-pointer">
                <Zap className="w-3.5 h-3.5 text-[var(--brand-amber)]" />
                Otomatik Çıkarım
              </Label>
            </div>
            
            {/* Keyboard Shortcuts Info */}
            <button 
              onClick={() => setShowShortcuts(!showShortcuts)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-[var(--brand-sky)] transition-colors"
            >
              <Keyboard className="w-3.5 h-3.5" />
              Klavye Kısayolları
            </button>
            
            {showShortcuts && (
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 bg-[hsl(var(--secondary))] border border-[hsl(var(--border))] rounded text-[10px] font-mono">Ctrl+S</kbd>
                  Kaydet
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 bg-[hsl(var(--secondary))] border border-[hsl(var(--border))] rounded text-[10px] font-mono">Ctrl+R</kbd>
                  Sonraki Tarama
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 bg-[hsl(var(--secondary))] border border-[hsl(var(--border))] rounded text-[10px] font-mono">Esc</kbd>
                  İptal
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Main Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(520px,1fr)_520px] gap-4">
        {/* Camera */}
        <CameraCapture key={cameraKey} onCapture={handleCapture} disabled={extracting} />

        {/* Form + Queue */}
        <div className="space-y-4">
          {extracting && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--brand-sky-soft)] text-[var(--brand-sky)] text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              AI kimlik okuma yapılıyor...
            </div>
          )}
          
          <ExtractionForm
            data={extractedData}
            onChange={setExtractedData}
            onSave={() => handleSave(false)}
            loading={saving}
            extracting={extracting}
            warnings={warnings}
          />

          {/* Scanned Queue */}
          {scannedGuests.length > 0 && (
            <Card className="bg-white">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Taranan Misafirler</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-64 overflow-y-auto" data-testid="bulk-scan-queue-table">
                  {scannedGuests.map((guest, i) => (
                    <div key={guest.id} className="flex items-center gap-3 p-2 rounded-lg bg-[hsl(var(--secondary))]">
                      <div className="w-7 h-7 rounded-full bg-[var(--brand-success-soft)] flex items-center justify-center">
                        <Check className="w-3.5 h-3.5 text-[var(--brand-success)]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {guest.first_name} {guest.last_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {guest.id_number || '—'}
                        </p>
                      </div>
                      <span className="text-xs text-muted-foreground">#{scannedGuests.length - i}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Duplicate Warning Dialog */}
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
