import { useState, useRef } from "react";
import { Upload, X, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

interface FileUploadAreaProps {
  files: File[];
  onChange: (files: File[]) => void;
  maxSize?: number; // in MB
}

export function FileUploadArea({ files, onChange, maxSize = 25 }: FileUploadAreaProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles = droppedFiles.filter((file) => {
      const sizeMB = file.size / (1024 * 1024);
      return sizeMB <= maxSize;
    });

    if (validFiles.length > 0) {
      onChange([...files, ...validFiles]);
    }

    if (validFiles.length < droppedFiles.length) {
      alert(`Alguns arquivos excedem o limite de ${maxSize}MB`);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    onChange([...files, ...selectedFiles]);
  };

  const removeFile = (index: number) => {
    onChange(files.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
  };

  return (
    <div className="space-y-4">
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`relative rounded-lg border-2 border-dashed transition-all ${
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border/40 bg-muted/30 hover:border-primary/50"
        }`}
      >
        <div className="p-8 text-center">
          <div className="flex justify-center mb-4">
            <div className={`rounded-full p-3 ${isDragging ? "bg-primary/10" : "bg-muted"}`}>
              <Upload
                className={`w-6 h-6 transition-colors ${
                  isDragging ? "text-primary" : "text-muted-foreground"
                }`}
              />
            </div>
          </div>

          <h3 className="font-semibold text-sm mb-1">Arraste arquivos aqui</h3>
          <p className="text-xs text-muted-foreground mb-4">
            ou clique para selecionar (máx. {maxSize}MB por arquivo)
          </p>

          <input
            ref={inputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            accept="*"
          />

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => inputRef.current?.click()}
            className="h-9"
          >
            Selecionar Arquivos
          </Button>
        </div>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {files.length} {files.length === 1 ? "arquivo" : "arquivos"} selecionado(s)
          </p>
          <div className="space-y-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="flex items-center gap-3 rounded-lg bg-muted/50 p-3 border border-border/40"
              >
                <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  className="flex-shrink-0 p-1 hover:bg-destructive/10 rounded transition-colors"
                  aria-label="Remover arquivo"
                >
                  <X className="w-4 h-4 text-muted-foreground hover:text-destructive" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
