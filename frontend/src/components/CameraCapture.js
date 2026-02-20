import React, { useRef, useState, useCallback, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Camera, RefreshCcw, SwitchCamera, AlertTriangle } from 'lucide-react';

export default function CameraCapture({ onCapture, disabled }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [error, setError] = useState(null);
  const [facingMode, setFacingMode] = useState('environment');
  const [showFlash, setShowFlash] = useState(false);
  const [capturedImage, setCapturedImage] = useState(null);

  const startCamera = useCallback(async () => {
    try {
      setError(null);
      setCameraReady(false);
      
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
      
      const constraints = {
        video: {
          facingMode: facingMode,
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        }
      };
      
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play();
          setCameraReady(true);
        };
      }
    } catch (err) {
      console.error('Camera error:', err);
      if (err.name === 'NotAllowedError') {
        setError('Kamera erişimi reddedildi. Lütfen tarayıcı izinlerini kontrol edin.');
      } else if (err.name === 'NotFoundError') {
        setError('Kamera bulunamadı. Lütfen bir kamera bağlı olduğundan emin olun.');
      } else {
        setError(`Kamera hatası: ${err.message}`);
      }
    }
  }, [facingMode]);

  useEffect(() => {
    startCamera();
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, [startCamera]);

  const capture = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    
    // Flash effect
    setShowFlash(true);
    setTimeout(() => setShowFlash(false), 200);
    
    const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
    setCapturedImage(dataUrl);
    
    if (onCapture) {
      onCapture(dataUrl);
    }
  }, [onCapture]);

  const retake = useCallback(() => {
    setCapturedImage(null);
    startCamera();
  }, [startCamera]);

  const switchCamera = useCallback(() => {
    setFacingMode(prev => prev === 'environment' ? 'user' : 'environment');
    setCapturedImage(null);
  }, []);

  return (
    <Card className="overflow-hidden bg-white">
      <div className="p-3 sm:p-4">
        <div className="relative bg-gray-900 rounded-xl overflow-hidden" style={{ aspectRatio: '4/3' }}>
          {error ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center bg-gray-50">
              <AlertTriangle className="w-12 h-12 text-[var(--brand-warning)] mb-3" />
              <p className="text-sm text-[var(--brand-slate)] mb-4" data-testid="camera-permission-alert">{error}</p>
              <Button onClick={startCamera} variant="outline" size="sm">
                <RefreshCcw className="w-4 h-4 mr-2" />
                Tekrar Dene
              </Button>
            </div>
          ) : capturedImage ? (
            <img 
              src={capturedImage} 
              alt="Yakalanan" 
              className="w-full h-full object-contain"
              data-testid="capture-thumbnail"
            />
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
                data-testid="camera-live-preview"
              />
              {/* Corner guides */}
              <div className="camera-overlay">
                <div className="camera-corner camera-corner-tl" />
                <div className="camera-corner camera-corner-tr" />
                <div className="camera-corner camera-corner-bl" />
                <div className="camera-corner camera-corner-br" />
                {!cameraReady && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                    <div className="text-white text-sm">Kamera başlatılıyor...</div>
                  </div>
                )}
              </div>
            </>
          )}
          {/* Flash overlay */}
          {showFlash && (
            <div className="absolute inset-0 bg-white camera-flash" />
          )}
        </div>
        
        <canvas ref={canvasRef} className="hidden" />
        
        <div className="flex items-center gap-2 mt-3">
          {capturedImage ? (
            <>
              <Button
                onClick={retake}
                variant="outline"
                className="flex-1"
                data-testid="camera-retake-button"
              >
                <RefreshCcw className="w-4 h-4 mr-2" />
                Yeniden Çek
              </Button>
            </>
          ) : (
            <>
              <Button
                onClick={capture}
                disabled={!cameraReady || disabled}
                className="flex-1 bg-[var(--brand-sky)] hover:bg-[#094C6E] text-white"
                data-testid="camera-capture-button"
              >
                <Camera className="w-4 h-4 mr-2" />
                Yakala
              </Button>
              <Button
                onClick={switchCamera}
                variant="outline"
                size="icon"
                data-testid="camera-switch-button"
              >
                <SwitchCamera className="w-4 h-4" />
              </Button>
            </>
          )}
        </div>
        
        {!capturedImage && !error && (
          <p className="text-xs text-center text-muted-foreground mt-2">
            Belgeyi çerçeveye hizalayın ve "Yakala"ya basın
          </p>
        )}
      </div>
    </Card>
  );
}
