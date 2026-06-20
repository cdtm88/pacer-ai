import { useRef, useState, type DragEvent } from 'react'
import { Upload, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { uploadRide } from '../../lib/api'

// ---------------------------------------------------------------------------
// FitUploadZone — drag-and-drop or click-to-upload .FIT file zone.
// Calls uploadRide (multipart, no user_id — JWT provides identity).
// On success: sonner toast + ride list invalidation (D-08), no redirect.
// No drag-drop library (PATTERNS.md "Don't Hand-Roll" section).
// ---------------------------------------------------------------------------

export function FitUploadZone() {
  const [isDragOver, setIsDragOver] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  async function handleUpload(file: File) {
    if (isUploading) return
    setIsUploading(true)
    try {
      await uploadRide(file)
      toast.success('Ride uploaded. History updated.')
      // D-08: invalidate rides query so the list auto-refetches; no redirect
      await queryClient.invalidateQueries({ queryKey: ['rides'] })
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Unknown error'
      toast.error(`Upload failed. ${message}. Try again.`)
    } finally {
      setIsUploading(false)
    }
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(true)
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(false)
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) {
      void handleUpload(file)
    }
  }

  function handleClick() {
    inputRef.current?.click()
  }

  function handleFileChange() {
    const file = inputRef.current?.files?.[0]
    if (file) {
      void handleUpload(file)
      // Reset so the same file can be re-uploaded
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const borderColor = isDragOver
    ? 'var(--color-blue-6)'
    : 'var(--color-line)'
  const bgColor = isDragOver
    ? 'var(--color-blue-0)'
    : 'var(--color-bg-2)'

  return (
    <>
      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept=".fit"
        style={{ display: 'none' }}
        onChange={handleFileChange}
        aria-label="Upload .FIT file"
      />

      <div
        role="button"
        tabIndex={0}
        aria-label="Drop a .FIT file here, or tap to upload"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={isUploading ? undefined : handleClick}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !isUploading) {
            handleClick()
          }
        }}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          height: '80px',
          borderRadius: '8px',
          border: `2px dashed ${borderColor}`,
          backgroundColor: bgColor,
          cursor: isUploading ? 'not-allowed' : 'pointer',
          transition: 'border-color 0.15s, background-color 0.15s',
          userSelect: 'none',
        }}
      >
        {isUploading ? (
          <>
            <Loader2
              size={20}
              className="animate-spin"
              style={{ color: 'var(--color-blue-6)' }}
            />
            <span
              style={{
                fontSize: '14px',
                color: 'var(--color-ink-2)',
              }}
            >
              Uploading ride...
            </span>
          </>
        ) : (
          <>
            <Upload
              size={20}
              style={{ color: 'var(--color-ink-3)' }}
            />
            <span
              style={{
                fontSize: '14px',
                color: 'var(--color-ink-2)',
              }}
            >
              Drop a .FIT file here, or tap to upload
            </span>
          </>
        )}
      </div>
    </>
  )
}
