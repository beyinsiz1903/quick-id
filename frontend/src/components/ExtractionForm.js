import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { Skeleton } from './ui/skeleton';
import { Save, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

const DOC_TYPES = [
  { value: 'tc_kimlik', label: 'TC Kimlik' },
  { value: 'passport', label: 'Pasaport' },
  { value: 'drivers_license', label: 'Ehliyet' },
  { value: 'old_nufus_cuzdani', label: 'Eski Nüfus Cüzdanı' },
  { value: 'other', label: 'Diğer' },
];

const GENDER_OPTIONS = [
  { value: 'M', label: 'Erkek' },
  { value: 'F', label: 'Kadın' },
];

export default function ExtractionForm({ data, onChange, onSave, loading, extracting, warnings }) {
  if (extracting) {
    return (
      <Card className="bg-white">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-[var(--brand-sky)]" />
            AI Çıkarım Yapılıyor...
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-1.5">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-9 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="bg-white">
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="w-16 h-16 rounded-full bg-[hsl(var(--secondary))] flex items-center justify-center mb-4">
            <AlertCircle className="w-8 h-8 text-muted-foreground" />
          </div>
          <p className="text-sm text-muted-foreground text-center">
            Kimlik kartı fotoğrafı çekin,<br />bilgiler otomatik çıkarılacak.
          </p>
        </CardContent>
      </Card>
    );
  }

  const handleChange = (field, value) => {
    if (onChange) {
      onChange({ ...data, [field]: value });
    }
  };

  return (
    <Card className="bg-white">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Kimlik Bilgileri</CardTitle>
          {data.is_valid === false && (
            <Badge variant="outline" className="bg-[var(--brand-warning-soft)] text-[var(--brand-warning)] border-[#FED7AA]">
              İnceleme Gerekli
            </Badge>
          )}
        </div>
        {warnings && warnings.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {warnings.map((w, i) => (
              <span key={i} className="text-xs text-[var(--brand-warning)] bg-[var(--brand-warning-soft)] px-2 py-0.5 rounded-full">
                {w}
              </span>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Document Type */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Belge Türü</Label>
          <Select
            value={data.document_type || ''}
            onValueChange={(v) => handleChange('document_type', v)}
          >
            <SelectTrigger data-testid="guest-document-type-select">
              <SelectValue placeholder="Belge türü seçin" />
            </SelectTrigger>
            <SelectContent>
              {DOC_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Name fields */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Ad</Label>
            <Input
              value={data.first_name || ''}
              onChange={(e) => handleChange('first_name', e.target.value)}
              placeholder="Ad"
              data-testid="guest-first-name-input"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Soyad</Label>
            <Input
              value={data.last_name || ''}
              onChange={(e) => handleChange('last_name', e.target.value)}
              placeholder="Soyad"
              data-testid="guest-last-name-input"
            />
          </div>
        </div>

        {/* ID Number */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">TCKN / Pasaport No</Label>
          <Input
            value={data.id_number || ''}
            onChange={(e) => handleChange('id_number', e.target.value)}
            placeholder="Kimlik numarası"
            data-testid="guest-document-number-input"
          />
        </div>

        {/* Birth Date & Gender */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Doğum Tarihi</Label>
            <Input
              type="date"
              value={data.birth_date || ''}
              onChange={(e) => handleChange('birth_date', e.target.value)}
              data-testid="guest-birthdate-input"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Cinsiyet</Label>
            <Select
              value={data.gender || ''}
              onValueChange={(v) => handleChange('gender', v)}
            >
              <SelectTrigger data-testid="guest-gender-select">
                <SelectValue placeholder="Seçin" />
              </SelectTrigger>
              <SelectContent>
                {GENDER_OPTIONS.map((g) => (
                  <SelectItem key={g.value} value={g.value}>{g.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Nationality */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Uyruk</Label>
          <Input
            value={data.nationality || ''}
            onChange={(e) => handleChange('nationality', e.target.value)}
            placeholder="Uyruk"
            data-testid="guest-nationality-input"
          />
        </div>

        {/* Birth place */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Doğum Yeri</Label>
          <Input
            value={data.birth_place || ''}
            onChange={(e) => handleChange('birth_place', e.target.value)}
            placeholder="Doğum yeri"
          />
        </div>

        {/* Expiry & Issue dates */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Veriliş Tarihi</Label>
            <Input
              type="date"
              value={data.issue_date || ''}
              onChange={(e) => handleChange('issue_date', e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Geçerlilik Tarihi</Label>
            <Input
              type="date"
              value={data.expiry_date || ''}
              onChange={(e) => handleChange('expiry_date', e.target.value)}
            />
          </div>
        </div>

        {/* Notes */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Not</Label>
          <Textarea
            value={data.notes || ''}
            onChange={(e) => handleChange('notes', e.target.value)}
            placeholder="Ek notlar..."
            rows={2}
          />
        </div>

        {/* Save button */}
        <Button
          onClick={onSave}
          disabled={loading || !data.first_name}
          className="w-full bg-[var(--brand-sky)] hover:bg-[#094C6E] text-white mt-2"
          data-testid="scan-save-button"
        >
          {loading ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Kaydediliyor...</>
          ) : (
            <><Save className="w-4 h-4 mr-2" /> Misafir Olarak Kaydet</>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
