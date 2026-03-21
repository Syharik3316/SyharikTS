import React, { useCallback, useState } from 'react';
import styles from './HoldToRevealPasswordField.module.css';

function EyeIcon() {
  return (
    <svg
      className={styles.eyeIcon}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M12 5C7 5 2.73 8.11 1 12c1.73 3.89 6 7 11 7s9.27-3.11 11-7c-1.73-3.89-5-7-11-7z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="3.25" stroke="currentColor" strokeWidth="1.75" />
    </svg>
  );
}

/**
 * Поле пароля: удержание «глаза» (ЛКМ / касание) показывает символы, отпускание скрывает.
 */
export default function HoldToRevealPasswordField({
  id,
  label,
  value,
  onChange,
  placeholder,
  name,
  autoComplete,
  errorText,
  hasError,
}) {
  const [revealed, setRevealed] = useState(false);

  const attachGlobalRelease = useCallback(() => {
    const hide = () => {
      setRevealed(false);
      window.removeEventListener('pointerup', hide);
      window.removeEventListener('pointercancel', hide);
    };
    window.addEventListener('pointerup', hide);
    window.addEventListener('pointercancel', hide);
  }, []);

  const handleEyePointerDown = (e) => {
    e.preventDefault();
    setRevealed(true);
    attachGlobalRelease();
  };

  return (
    <div className={styles.wrap}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <div className={styles.inputRow}>
        <input
          id={id}
          name={name}
          className={`${styles.input} ${hasError || errorText ? styles.inputError : ''}`}
          type={revealed ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={autoComplete}
        />
        <button
          type="button"
          className={styles.eyeBtn}
          aria-label="Удерживайте, чтобы показать пароль"
          onPointerDown={handleEyePointerDown}
        >
          <EyeIcon />
        </button>
      </div>
      {errorText ? (
        <p className={styles.fieldError} role="alert">
          {errorText}
        </p>
      ) : null}
    </div>
  );
}
