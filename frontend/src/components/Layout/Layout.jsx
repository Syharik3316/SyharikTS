import React from 'react';
import Header from '../Header/Header.jsx';
import Footer from '../Footer/Footer.jsx';
import styles from './Layout.module.css';
import { GlowProvider, useGlow } from '../../glow/GlowProvider.jsx';

function LayoutInner({ children }) {
  const { moveCursorGlow } = useGlow();

  return (
    <div
      className={styles.page}
      onPointerMove={(e) => moveCursorGlow(e.clientX, e.clientY)}
    >
      <Header />

      <main className={styles.main}>
        <div className={styles.container}>{children}</div>
      </main>

      <Footer />
    </div>
  );
}

export default function Layout({ children }) {
  return (
    <GlowProvider>
      <LayoutInner>{children}</LayoutInner>
    </GlowProvider>
  );
}

