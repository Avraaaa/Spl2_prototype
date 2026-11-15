import { useId, useRef, useState, type DragEvent } from 'react';

type DropzoneProps = {
  accept: string;
  disabled?: boolean;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  helper?: string;
  label?: string;
};

export function Dropzone({
  accept,
  disabled = false,
  multiple = true,
  onFiles,
  helper,
  label = 'Add attachments',
}: DropzoneProps) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const choose = (files: FileList | null) => {
    if (files?.length) onFiles(Array.from(files));
    if (input.current) input.current.value = '';
  };
  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!disabled) choose(event.dataTransfer.files);
  };
  return (
    <div className="dropzone-wrap">
      <div
        className={`dropzone${dragging ? ' is-dragging' : ''}${disabled ? ' is-disabled' : ''}`}
        onDragEnter={event => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={event => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
      >
        <input
          ref={input}
          id={id}
          className="sr-only"
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={disabled}
          onChange={event => choose(event.target.files)}
        />
        <strong>{label}</strong>
        <span className="muted">Drag files here, or</span>
        <button type="button" className="btn small" disabled={disabled} onClick={() => input.current?.click()}>
          Browse files
        </button>
      </div>
      {helper && <p className="helper-text">{helper}</p>}
    </div>
  );
}
