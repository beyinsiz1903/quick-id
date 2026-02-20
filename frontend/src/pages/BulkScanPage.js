import React, { useState, useCallback } from 'react';
import { toast } from 'sonner';
import CameraCapture from '../components/CameraCapture';
import ExtractionForm from '../components/ExtractionForm';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { StatusBadge } from '../components/StatusBadges';
import { api } from '../lib/api';
import { Layers, Undo2, Check, Camera, Loader2, Users } from 'lucide-react';

export default function BulkScanPage() {
  const [extractedData, setExtractedData] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scanId, setScanId] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [scannedGuests, setScannedGuests] = useState([]);
  const [cameraKey, setCameraKey] = useState(0);

  const handleCapture = useCallback(async (imageDataUrl) => {
    setExtracting(true);
    setExtractedData(null);
    setWarnings([]);
    
    try {
      const result = await api.scanId(imageDataUrl);
      
      if (result.success && result.extracted_data) {
        const data = result.extracted_data;
        setExtractedData({
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
        });
        setWarnings(data.warnings || []);
        setScanId(result.scan?.id || null);
        
        if (data.is_valid) {
          toast.success('Kimlik okundu!');
        } else {
          toast.warning('Kısmi bilgi alındı, kontrol edin.');
        }
      }
    } catch (err) {
      toast.error(`Tarama hatası: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  }, []);

  const handleSave = useCallback(async () => {
    if (!extractedData) return;
    
    setSaving(true);
    try {
      const payload = { ...extractedData, scan_id: scanId };
      delete payload.is_valid;
      
      const result = await api.createGuest(payload);
      if (result.success) {
        setScannedGuests(prev => [result.guest, ...prev]);
        toast.success(`${extractedData.first_name} ${extractedData.last_name} kaydedildi!`);
        
        // Reset for next scan
        setExtractedData(null);
        setScanId(null);
        setWarnings([]);
        setCameraKey(prev => prev + 1); // Reset camera
      }
    } catch (err) {
      toast.error(`Kaydetme hatası: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [extractedData, scanId]);

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
            onSave={handleSave}
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
    </div>
  );
}
