import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

const GlowContext = createContext(null);

export function useGlow() {
  const ctx = useContext(GlowContext);
  if (!ctx) {
    throw new Error('useGlow должен использоваться внутри GlowProvider');
  }
  return ctx;
}

export function GlowProvider({ children }) {
  const hideTimerRef = useRef(0);

  const [pulse, setPulse] = useState({
    x: 0,
    y: 0,
    visible: false,
    variant: 'click',
  });
  const [cursorGlow, setCursorGlow] = useState({
    x: 0,
    y: 0,
    visible: false,
  });

  const triggerGlow = useCallback((clientX, clientY, variant = 'click') => {
    window.clearTimeout(hideTimerRef.current);

    setPulse({
      x: clientX,
      y: clientY,
      visible: true,
      variant,
    });

    if (variant === 'hover') {
      hideTimerRef.current = window.setTimeout(() => {
        setPulse((p) => ({ ...p, visible: false }));
      }, 1200);
    } else {
      hideTimerRef.current = window.setTimeout(() => {
        setPulse((p) => ({ ...p, visible: false }));
      }, 950);
    }
  }, []);

  const moveCursorGlow = useCallback((clientX, clientY) => {
    setCursorGlow({
      x: clientX,
      y: clientY,
      visible: true,
    });
  }, []);

  const value = useMemo(
    () => ({ triggerGlow, moveCursorGlow }),
    [triggerGlow, moveCursorGlow],
  );

  return (
    <GlowContext.Provider value={value}>
      {children}
      <div
        aria-hidden="true"
        className="glowPulse"
        data-variant={pulse.variant}
        data-visible={pulse.visible ? 'true' : 'false'}
        style={
          {
            left: `${pulse.x}px`,
            top: `${pulse.y}px`,
          }
        }
      />
      <div
        aria-hidden="true"
        className="glowCursor"
        data-visible={cursorGlow.visible ? 'true' : 'false'}
        style={{
          left: `${cursorGlow.x}px`,
          top: `${cursorGlow.y}px`,
        }}
      />
    </GlowContext.Provider>
  );
}

