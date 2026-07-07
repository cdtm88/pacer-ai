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
      const result = await uploadRide(file)
      if (result.duplicate) {
        toast.info('This ride is already uploaded. No duplicate was created.')
        return
      }
      toast.success('Ride uploaded. History updated.')
      // D-08: invalidate every query key affected by a new ride so History,
      // Today's PMC, and session cards all refresh. Query keys are named
      // inconsistently across screens (['pmc-history'] vs ['pmc', 'latest']),
      // so each key is listed explicitly here rather than relying on a
      // prefix-match shortcut (09-RESEARCH.md Pitfall 2 / Assumption A3).
      // If a future screen adds a new PMC/session query key, add it here too.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['rides'] }),
        queryClient.invalidateQueries({ queryKey: ['pmc', 'latest'] }),
        queryClient.invalidateQueries({ queryKey: ['pmc-history'] }),
        queryClient.invalidateQueries({ queryKey: ['session', 'today'] }),
        queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] }),
      ])
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
    if (!file) return
    // Browsers do not enforce the file-picker's accept=".fit" attribute on
    // drag-drop, so the extension must be validated here too (item 14b).
    if (!file.name.toLowerCase().endsWith('.fit')) {
      toast.error('Only .fit files are supported.')
      return
    }
    void handleUpload(file)
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
        data-testid="fit-upload-zone"
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

      {/* Indeterminate upload progress bar (09-UI-SPEC.md §4): additive to
          the existing spinner + text above, rendered only while uploading. */}
      {isUploading && (
        <div
          data-testid="upload-progress-track"
          style={{
            height: '3px',
            borderRadius: '2px',
            backgroundColor: 'var(--color-line-2)',
            width: '100%',
            marginTop: '8px',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div
            data-testid="upload-progress-fill"
            className="fit-upload-progress-sweep"
            style={{
              position: 'absolute',
              top: 0,
              height: '100%',
              width: '40%',
              borderRadius: '2px',
              backgroundColor: 'var(--color-blue-6)',
            }}
          />
        </div>
      )}
    </>
  )
}
