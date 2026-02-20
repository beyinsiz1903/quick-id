import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import CameraCapture from '../components/CameraCapture';
import ExtractionForm from '../components/ExtractionForm';
import { Button } from '../components/ui/button';
import { api } from '../lib/api';
import { ScanLine, Loader2 } from 'lucide-react';

export default function ScanPage() {
  const navigate = useNavigate();
  const [extractedData, setExtractedData] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scanId, setScanId] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [capturedImage, setCapturedImage] = useState(null);

  const handleCapture = useCallback(async (imageDataUrl) => {
    setCapturedImage(imageDataUrl);
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
          mother_name: data.mother_name || '',
          father_name: data.father_name || '',
          is_valid: data.is_valid,
          notes: '',
        });
        setWarnings(data.warnings || []);
        setScanId(result.scan?.id || null);
        
        if (data.is_valid) {
          toast.success('Kimlik başarıyla okundu!');
        } else {
          toast.warning('Kimlik okunamadı veya kısmi bilgi alındı. Lütfen kontrol edin.');
        }
      }
    } catch (err) {
      console.error('Scan error:', err);
      toast.error(`Tarama hatası: ${err.message}`);
      setExtractedData(null);
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
        toast.success('Misafir başarıyla kaydedildi!');
        navigate(`/guests/${result.guest.id}`);
      }
    } catch (err) {
      console.error('Save error:', err);
      toast.error(`Kaydetme hatası: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [extractedData, scanId, navigate]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--brand-ink)]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          Kimlik Tarama
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Kimlik kartını kameraya gösterin, bilgiler otomatik çıkarılacak
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
          <ExtractionForm
            data={extractedData}
            onChange={setExtractedData}
            onSave={handleSave}
            loading={saving}
            extracting={extracting}
            warnings={warnings}
          />
        </div>
      </div>
    </div>
  );
}
